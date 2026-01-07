# service/session_usage.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from models.partner.usage import UsageEvent
from crud.supervisor.api_usage import api_usage_crud
from schemas.supervisor.api_usage import ApiUsageCreate


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_decimal(v: Decimal | float | int | str) -> Decimal:
    return Decimal(str(v))


# =========================================================
# 공통: usage_events 기록
# =========================================================
def log_usage_event(
    db: Session,
    *,
    request_id: Optional[str] = None,
    turn_id: Optional[int] = None,
    partner_id: int,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    session_id: Optional[int] = None,
    response_id: Optional[int] = None,
    request_type: str,
    provider: str,
    model_name: Optional[str] = None,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    total_tokens: Optional[int] = None,
    cost_usd: Decimal | float = Decimal("0"),
    media_duration_seconds: int = 0,
    success: bool = True,
    error_code: Optional[str] = None,
    latency_ms: Optional[int] = None,
    occurred_at: Optional[datetime] = None,
    commit: bool = True,
) -> None:
    rid = request_id or str(uuid4())
    ts = occurred_at or _now_utc()

    tp = int(tokens_prompt or 0)
    tc = int(tokens_completion or 0)
    tt = int(total_tokens) if total_tokens is not None else (tp + tc)

    event = UsageEvent(
        request_id=rid,
        turn_id=turn_id,
        occurred_at=ts,
        partner_id=partner_id,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        session_id=session_id,
        response_id=response_id,
        request_type=request_type,
        provider=provider,
        model_name=model_name,
        tokens_prompt=tp,
        tokens_completion=tc,
        total_tokens=tt,
        media_duration_seconds=int(media_duration_seconds or 0),
        latency_ms=latency_ms,
        total_cost_usd=_to_decimal(cost_usd),
        success=bool(success),
        error_code=error_code,
    )
    db.add(event)

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
    total_tokens = int(tokens_prompt) + int(tokens_completion)

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
        tokens_prompt=int(tokens_prompt),
        tokens_completion=int(tokens_completion),
        total_tokens=total_tokens,
        cost_usd=total_cost,
        success=success,
        error_code=error_code,
        latency_ms=response_time_ms,
        occurred_at=ts,
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
