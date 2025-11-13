# crud/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.usage import (
    UsageDaily,
    ApiCostDaily,
    ModelUsageMonthly,
    UsageEventLLM,
    UsageEventSTT,
)


# =============================================================================
# READ-ONLY: usage_daily
# =============================================================================
def get_usage_daily(db: Session, usage_id: int) -> Optional[UsageDaily]:
    return db.get(UsageDaily, usage_id)


def list_usage_daily(
    db: Session,
    *,
    partner_id: int,
    class_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    provider: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[UsageDaily], int]:
    """
    partner.usage_daily 조회 (페이지네이션).
    ETL 집계 결과를 읽기만 한다.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [UsageDaily.partner_id == partner_id]

    if class_id is not None:
        filters.append(UsageDaily.class_id == class_id)
    if enrollment_id is not None:
        filters.append(UsageDaily.enrollment_id == enrollment_id)
    if student_id is not None:
        filters.append(UsageDaily.student_id == student_id)
    if provider is not None:
        filters.append(UsageDaily.provider == provider)
    if date_from is not None:
        filters.append(UsageDaily.usage_date >= date_from)
    if date_to is not None:
        filters.append(UsageDaily.usage_date <= date_to)

    base_stmt: Select[UsageDaily] = select(UsageDaily).where(*filters)

    # total count
    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    # page
    stmt = (
        base_stmt.order_by(UsageDaily.usage_date.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


# =============================================================================
# READ-ONLY: api_cost_daily
# =============================================================================
def get_api_cost_daily(db: Session, row_id: int) -> Optional[ApiCostDaily]:
    return db.get(ApiCostDaily, row_id)


def list_api_cost_daily(
    db: Session,
    *,
    partner_id: int,
    provider: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[ApiCostDaily], int]:
    """
    partner.api_cost_daily 조회 (파트너 일별 비용 집계).
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [ApiCostDaily.partner_id == partner_id]

    if provider is not None:
        filters.append(ApiCostDaily.provider == provider)
    if date_from is not None:
        filters.append(ApiCostDaily.usage_date >= date_from)
    if date_to is not None:
        filters.append(ApiCostDaily.usage_date <= date_to)

    base_stmt: Select[ApiCostDaily] = select(ApiCostDaily).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(ApiCostDaily.usage_date.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


# =============================================================================
# READ-ONLY: model_usage_monthly
# =============================================================================
def get_model_usage_monthly(db: Session, row_id: int) -> Optional[ModelUsageMonthly]:
    return db.get(ModelUsageMonthly, row_id)


def list_model_usage_monthly(
    db: Session,
    *,
    partner_id: int,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    month_from: Optional[date] = None,  # YYYY-MM-01
    month_to: Optional[date] = None,    # YYYY-MM-01
    page: int = 1,
    size: int = 50,
) -> Tuple[List[ModelUsageMonthly], int]:
    """
    partner.model_usage_monthly 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [ModelUsageMonthly.partner_id == partner_id]

    if provider is not None:
        filters.append(ModelUsageMonthly.provider == provider)
    if model_name is not None:
        filters.append(ModelUsageMonthly.model_name == model_name)
    if month_from is not None:
        filters.append(ModelUsageMonthly.month >= month_from)
    if month_to is not None:
        filters.append(ModelUsageMonthly.month <= month_to)

    base_stmt: Select[ModelUsageMonthly] = select(ModelUsageMonthly).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(ModelUsageMonthly.month.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


# =============================================================================
# usage_events_llm (append-only 권장)
# =============================================================================
def get_usage_event_llm(db: Session, event_id: int) -> Optional[UsageEventLLM]:
    return db.get(UsageEventLLM, event_id)


def list_usage_events_llm(
    db: Session,
    *,
    session_id: Optional[int] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    success: Optional[bool] = None,
    recorded_from: Optional[datetime] = None,
    recorded_to: Optional[datetime] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[UsageEventLLM], int]:
    """
    partner.usage_events_llm 조회.
    주로 디버깅/리포트용으로만 읽는 것을 권장.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []

    if session_id is not None:
        filters.append(UsageEventLLM.session_id == session_id)
    if class_id is not None:
        filters.append(UsageEventLLM.class_id == class_id)
    if student_id is not None:
        filters.append(UsageEventLLM.student_id == student_id)
    if provider is not None:
        filters.append(UsageEventLLM.provider == provider)
    if model_name is not None:
        filters.append(UsageEventLLM.model_name == model_name)
    if success is not None:
        filters.append(UsageEventLLM.success == success)
    if recorded_from is not None:
        filters.append(UsageEventLLM.recorded_at >= recorded_from)
    if recorded_to is not None:
        filters.append(UsageEventLLM.recorded_at <= recorded_to)

    base_stmt: Select[UsageEventLLM] = select(UsageEventLLM)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(UsageEventLLM.recorded_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_usage_event_llm(
    db: Session,
    *,
    data: Dict[str, Any],
) -> UsageEventLLM:
    """
    LLM 사용 이벤트 기록.
    - service 레이어에서 UsageEventLLMCreate.model_dump(exclude_unset=True) 넘겨주기.
    """
    obj = UsageEventLLM(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_usage_event_llm(
    db: Session,
    *,
    event: UsageEventLLM,
    data: Dict[str, Any],
) -> UsageEventLLM:
    """
    LLM 이벤트 수정 (예외 상황용).
    - append-only 정책을 기본으로 하고, 교정이 필요할 때만 사용.
    """
    for key, value in data.items():
        setattr(event, key, value)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def delete_usage_event_llm(
    db: Session,
    *,
    event: UsageEventLLM,
) -> None:
    """
    필요시 수동 정리용 삭제. (일반적인 워크플로에서는 사용 안 하는 것을 권장)
    """
    db.delete(event)
    db.commit()


# =============================================================================
# usage_events_stt (append-only 권장)
# =============================================================================

def get_usage_event_stt(db: Session, event_id: int) -> Optional[UsageEventSTT]:
    return db.get(UsageEventSTT, event_id)


def list_usage_events_stt(
    db: Session,
    *,
    session_id: Optional[int] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    provider: Optional[str] = None,
    recorded_from: Optional[datetime] = None,
    recorded_to: Optional[datetime] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[UsageEventSTT], int]:
    """
    partner.usage_events_stt 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []

    if session_id is not None:
        filters.append(UsageEventSTT.session_id == session_id)
    if class_id is not None:
        filters.append(UsageEventSTT.class_id == class_id)
    if student_id is not None:
        filters.append(UsageEventSTT.student_id == student_id)
    if provider is not None:
        filters.append(UsageEventSTT.provider == provider)
    if recorded_from is not None:
        filters.append(UsageEventSTT.recorded_at >= recorded_from)
    if recorded_to is not None:
        filters.append(UsageEventSTT.recorded_at <= recorded_to)

    base_stmt: Select[UsageEventSTT] = select(UsageEventSTT)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(UsageEventSTT.recorded_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_usage_event_stt(
    db: Session,
    *,
    data: Dict[str, Any],
) -> UsageEventSTT:
    """
    STT 사용 이벤트 기록.
    - service 레이어에서 UsageEventSTTCreate.model_dump(exclude_unset=True) 넘겨주기.
    """
    obj = UsageEventSTT(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_usage_event_stt(
    db: Session,
    *,
    event: UsageEventSTT,
    data: Dict[str, Any],
) -> UsageEventSTT:
    """
    STT 이벤트 수정 (예외 상황용).
    """
    for key, value in data.items():
        setattr(event, key, value)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def delete_usage_event_stt(
    db: Session,
    *,
    event: UsageEventSTT,
) -> None:
    db.delete(event)
    db.commit()
