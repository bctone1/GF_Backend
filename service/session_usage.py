# service/session_usage.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any, Dict
from uuid import uuid4

from sqlalchemy.orm import Session

from crud.partner import usage as usage_crud  # upsert_usage_event_idempotent 사용
from crud.supervisor.api_usage import api_usage_crud
from schemas.supervisor.api_usage import ApiUsageCreate


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_decimal(v: Decimal | float | int | str) -> Decimal:
    return Decimal(str(v or 0))


# =========================================================
# 공통: usage_events 기록 (슬림 모델 기준)
# =========================================================
def log_usage_event(
    db: Session,
    *,
    request_id: Optional[str] = None,
    turn_id: Optional[int] = None,          # meta로 저장
    partner_id: int,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    session_id: Optional[int] = None,
    response_id: Optional[int] = None,      # meta로 저장
    request_type: str,
    provider: str,
    model_name: Optional[str] = None,
    tokens_prompt: int = 0,                 # meta로 저장
    tokens_completion: int = 0,             # meta로 저장
    total_tokens: Optional[int] = None,     # 실제 컬럼에 저장
    cost_usd: Decimal | float = Decimal("0"),
    media_duration_seconds: int = 0,
    success: bool = True,
    error_code: Optional[str] = None,
    latency_ms: Optional[int] = None,
    occurred_at: Optional[datetime] = None,
    meta: Optional[Dict[str, Any]] = None,  # 확장
    commit: bool = True,
) -> None:
    rid = request_id or str(uuid4())
    ts = occurred_at or _now_utc()

    tp = int(tokens_prompt or 0)
    tc = int(tokens_completion or 0)
    tt = int(total_tokens) if total_tokens is not None else (tp + tc)

    # meta 확장(컬럼으로 없는 값은 전부 meta로 보관)
    meta_payload: Dict[str, Any] = dict(meta or {})
    if turn_id is not None:
        meta_payload["turn_id"] = turn_id
    if response_id is not None:
        meta_payload["response_id"] = response_id
    meta_payload["tokens_prompt"] = tp
    meta_payload["tokens_completion"] = tc

    usage_crud.upsert_usage_event_idempotent(
        db,
        request_id=rid,
        partner_id=partner_id,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        occurred_at=ts,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        session_id=session_id,
        total_tokens=tt,
        media_duration_seconds=int(media_duration_seconds or 0),
        latency_ms=latency_ms,
        total_cost_usd=_to_decimal(cost_usd),
        success=bool(success),
        error_code=error_code,
        meta=meta_payload,
    )

    if commit:
        db.commit()
    else:
        db.flush()


# =========================================================
# LLM 사용량 기록 (wrapper)
# =========================================================
def log_llm_usage(
    db: Session,
    *,
    request_id: Optional[str] = None,
    turn_id: Optional[int] = None,
    partner_id: int,
    session_id: Optional[int] = None,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    response_id: Optional[int] = None,
    provider: str,
    model_name: str,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    cost_usd: Decimal | float = Decimal("0"),
    success: bool = True,
    error_code: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    organization_id: Optional[int] = None,
    supervisor_user_id: Optional[int] = None,
    endpoint: str = "rag.llm",
    requested_at: Optional[datetime] = None,
    commit: bool = True,
) -> None:
    ts = requested_at or _now_utc()
    total_cost = _to_decimal(cost_usd)
    total_tokens = int(tokens_prompt or 0) + int(tokens_completion or 0)

    # usage_events는 commit=False로 넣고, 아래 api_usage까지 같이 한 번에 commit
    log_usage_event(
        db,
        request_id=request_id,
        turn_id=turn_id,
        partner_id=partner_id,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        session_id=session_id,
        response_id=response_id,
        request_type="llm_chat",
        provider=provider,
        model_name=model_name,
        tokens_prompt=int(tokens_prompt or 0),
        tokens_completion=int(tokens_completion or 0),
        total_tokens=total_tokens,
        cost_usd=total_cost,
        success=success,
        error_code=error_code,
        latency_ms=response_time_ms,
        occurred_at=ts,
        meta={"endpoint": endpoint},
        commit=False,
    )

    if organization_id is not None:
        api_usage_crud.create(
            db,
            ApiUsageCreate(
                organization_id=organization_id,
                user_id=supervisor_user_id,
                provider=provider,
                endpoint=endpoint,
                tokens=total_tokens,
                cost=total_cost,
                status="success" if success else "error",
                response_time_ms=response_time_ms,
                requested_at=ts,
            ),
        )

    if commit:
        db.commit()
    else:
        db.flush()
