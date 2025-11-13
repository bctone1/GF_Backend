# service/session_usage.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from models.partner.usage import UsageEventLLM, UsageEventSTT
from crud.supervisor.api_usage import api_usage_crud
from schemas.supervisor.api_usage import ApiUsageCreate


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# LLM 사용량 기록
# =========================================================
def log_llm_usage(
    db: Session,
    *,
    # 파트너 축
    session_id: Optional[int] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    # 모델 정보
    provider: str,
    model_name: str,
    # 토큰/비용
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    cost_usd: Decimal | float = Decimal("0"),
    # 결과 상태
    success: bool = True,
    # 응답 시간(ms) – supervisor.api_usage용 (없으면 None)
    response_time_ms: Optional[int] = None,
    # supervisor 축 (선택)
    organization_id: Optional[int] = None,
    supervisor_user_id: Optional[int] = None,
    endpoint: str = "rag.llm",
    requested_at: Optional[datetime] = None,
    # 자동 커밋 여부
    commit: bool = True,
) -> None:
    """
    RAG/LLM 호출 1회에 대한 사용량 기록 헬퍼.

    1) partner.usage_events_llm 에 1행 INSERT
    2) (옵션) supervisor.api_usage 에도 1행 INSERT

    - session_id/class_id/student_id 는 가능한 만큼 채워주면 됨.
    - organization_id 가 주어지면 supervisor.api_usage 에도 함께 남김.
    """

    # ---------- 1) partner.usage_events_llm ----------
    total_cost = Decimal(str(cost_usd))
    event = UsageEventLLM(
        session_id=session_id,
        class_id=class_id,
        student_id=student_id,
        provider=provider,
        model_name=model_name,
        tokens_prompt=int(tokens_prompt),
        tokens_completion=int(tokens_completion),
        total_cost=total_cost,
        success=success,
        # recorded_at 은 DB default func.now() 사용 (필요하면 오버라이드 가능)
    )
    db.add(event)

    # ---------- 2) supervisor.api_usage (옵션) ----------
    if organization_id is not None:
        total_tokens = int(tokens_prompt) + int(tokens_completion)
        ts = requested_at or _now_utc()

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
        # 다른 트랜잭션과 묶어서 쓸 경우를 위해 flush만 하고 넘길 수도 있음
        db.flush()


# =========================================================
# STT 사용량 기록
# =========================================================
def log_stt_usage(
    db: Session,
    *,
    # 파트너 축
    session_id: Optional[int] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    # STT 정보
    provider: str,
    media_duration_seconds: int,
    cost_usd: Decimal | float = Decimal("0"),
    # supervisor 축 (선택)
    organization_id: Optional[int] = None,
    supervisor_user_id: Optional[int] = None,
    endpoint: str = "stt.transcribe",
    requested_at: Optional[datetime] = None,
    response_time_ms: Optional[int] = None,
    commit: bool = True,
) -> None:
    """
    STT(음성 인식) 사용량 기록 헬퍼.

    1) partner.usage_events_stt 에 1행 INSERT
    2) (옵션) supervisor.api_usage 에도 1행 INSERT
    """

    total_cost = Decimal(str(cost_usd))

    # ---------- 1) partner.usage_events_stt ----------
    event = UsageEventSTT(
        session_id=session_id,
        class_id=class_id,
        student_id=student_id,
        provider=provider,
        media_duration_seconds=int(media_duration_seconds),
        total_cost=total_cost,
        # recorded_at 은 DB default func.now()
    )
    db.add(event)

    # ---------- 2) supervisor.api_usage (옵션) ----------
    if organization_id is not None:
        ts = requested_at or _now_utc()

        api_usage_crud.create(
            db,
            ApiUsageCreate(
                organization_id=organization_id,
                user_id=supervisor_user_id,
                provider=provider,
                endpoint=endpoint,
                tokens=0,  # STT는 토큰 대신 duration으로만 본다고 가정
                cost=total_cost,
                status="success",  # 실패 케이스 필요하면 인자 추가해서 분기
                response_time_ms=response_time_ms,
                requested_at=ts,
            ),
        )

    if commit:
        db.commit()
    else:
        db.flush()
