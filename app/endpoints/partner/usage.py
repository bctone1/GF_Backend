# app/endpoints/partner/usage.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from crud.partner import usage as usage_crud
from schemas.partner.usage import (
    UsageDailyResponse,
    UsageDailyPage,
    ApiCostDailyResponse,
    ApiCostDailyPage,
    ModelUsageMonthlyResponse,
    ModelUsageMonthlyPage,
    UsageEventLLMCreate,
    UsageEventLLMUpdate,
    UsageEventLLMResponse,
    UsageEventLLMPage,
    UsageEventSTTCreate,
    UsageEventSTTUpdate,
    UsageEventSTTResponse,
    UsageEventSTTPage,
)

router = APIRouter()


# ==============================
# usage_daily (READ-ONLY)
# ==============================

@router.get("/daily", response_model=UsageDailyPage)
def list_usage_daily(
    partner_id: int = Path(..., ge=1),
    class_id: Optional[int] = Query(None),
    enrollment_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    partner.usage_daily 일별 집계 조회.
    """
    rows, total = usage_crud.list_usage_daily(
        db,
        partner_id=partner_id,
        class_id=class_id,
        enrollment_id=enrollment_id,
        student_id=student_id,
        provider=provider,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    items = [UsageDailyResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/daily/{usage_id}", response_model=UsageDailyResponse)
def get_usage_daily(
    partner_id: int = Path(..., ge=1),
    usage_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    usage_daily 단건 조회.
    """
    obj = usage_crud.get_usage_daily(db, usage_id=usage_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_daily not found")
    return UsageDailyResponse.model_validate(obj)


# ==============================
# api_cost_daily (READ-ONLY)
# ==============================

@router.get("/cost-daily", response_model=ApiCostDailyPage)
def list_api_cost_daily(
    partner_id: int = Path(..., ge=1),
    provider: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    partner.api_cost_daily 일별 비용 집계 조회.
    """
    rows, total = usage_crud.list_api_cost_daily(
        db,
        partner_id=partner_id,
        provider=provider,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    items = [ApiCostDailyResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/cost-daily/{row_id}", response_model=ApiCostDailyResponse)
def get_api_cost_daily(
    partner_id: int = Path(..., ge=1),
    row_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    api_cost_daily 단건 조회.
    """
    obj = usage_crud.get_api_cost_daily(db, row_id=row_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api_cost_daily not found")
    return ApiCostDailyResponse.model_validate(obj)


# ==============================
# model_usage_monthly (READ-ONLY)
# ==============================
@router.get("/model-monthly", response_model=ModelUsageMonthlyPage)
def list_model_usage_monthly(
    partner_id: int = Path(..., ge=1),
    provider: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    month_from: Optional[date] = Query(None, description="YYYY-MM-01"),
    month_to: Optional[date] = Query(None, description="YYYY-MM-01"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    partner.model_usage_monthly 월별 모델 사용량 집계 조회.
    """
    rows, total = usage_crud.list_model_usage_monthly(
        db,
        partner_id=partner_id,
        provider=provider,
        model_name=model_name,
        month_from=month_from,
        month_to=month_to,
        page=page,
        size=size,
    )
    items = [ModelUsageMonthlyResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/model-monthly/{row_id}", response_model=ModelUsageMonthlyResponse)
def get_model_usage_monthly(
    partner_id: int = Path(..., ge=1),
    row_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    model_usage_monthly 단건 조회.
    """
    obj = usage_crud.get_model_usage_monthly(db, row_id=row_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model_usage_monthly not found")
    return ModelUsageMonthlyResponse.model_validate(obj)


# ==============================
# usage_events_llm (append-only 권장)
# ==============================
@router.get("/events/llm", response_model=UsageEventLLMPage)
def list_usage_events_llm(
    partner_id: int = Path(..., ge=1),
    session_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    recorded_from: Optional[datetime] = Query(None),
    recorded_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    LLM 사용 이벤트 목록.
    partner_id 컬럼은 없어서, session/class/student 기준으로 필터링 전제.
    """
    rows, total = usage_crud.list_usage_events_llm(
        db,
        session_id=session_id,
        class_id=class_id,
        student_id=student_id,
        provider=provider,
        model_name=model_name,
        success=success,
        recorded_from=recorded_from,
        recorded_to=recorded_to,
        page=page,
        size=size,
    )
    items = [UsageEventLLMResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/events/llm",
    response_model=UsageEventLLMResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_usage_event_llm(
    partner_id: int = Path(..., ge=1),
    payload: UsageEventLLMCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    LLM 사용 이벤트 기록.
    - 일반적으로 service 레이어에서 호출.
    """
    data = payload.model_dump(exclude_unset=True)
    # 추후수정: session_id / class_id / student_id 가 partner_id 소속인지 검증 로직 추가 가능
    obj = usage_crud.create_usage_event_llm(db, data=data)
    return UsageEventLLMResponse.model_validate(obj)


@router.get("/events/llm/{event_id}", response_model=UsageEventLLMResponse)
def get_usage_event_llm(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    LLM 이벤트 단건 조회.
    """
    obj = usage_crud.get_usage_event_llm(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_llm not found")
    return UsageEventLLMResponse.model_validate(obj)


@router.patch("/events/llm/{event_id}", response_model=UsageEventLLMResponse)
def update_usage_event_llm(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    payload: UsageEventLLMUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    LLM 이벤트 수정 (예외 상황용).
    """
    obj = usage_crud.get_usage_event_llm(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_llm not found")

    data = payload.model_dump(exclude_unset=True)
    obj = usage_crud.update_usage_event_llm(db, event=obj, data=data)
    return UsageEventLLMResponse.model_validate(obj)


@router.delete("/events/llm/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_usage_event_llm(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    LLM 이벤트 삭제 (운영상 특별한 경우에만 사용 권장).
    """
    obj = usage_crud.get_usage_event_llm(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_llm not found")

    usage_crud.delete_usage_event_llm(db, event=obj)
    return None


# ==============================
# usage_events_stt (append-only 권장)
# ==============================
@router.get("/events/stt", response_model=UsageEventSTTPage)
def list_usage_events_stt(
    partner_id: int = Path(..., ge=1),
    session_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    recorded_from: Optional[datetime] = Query(None),
    recorded_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    STT 사용 이벤트 목록.
    """
    rows, total = usage_crud.list_usage_events_stt(
        db,
        session_id=session_id,
        class_id=class_id,
        student_id=student_id,
        provider=provider,
        recorded_from=recorded_from,
        recorded_to=recorded_to,
        page=page,
        size=size,
    )
    items = [UsageEventSTTResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/events/stt",
    response_model=UsageEventSTTResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_usage_event_stt(
    partner_id: int = Path(..., ge=1),
    payload: UsageEventSTTCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    STT 사용 이벤트 기록.
    """
    data = payload.model_dump(exclude_unset=True)
    # 추후수정: session_id / class_id / student_id 파트너 소속 검증 로직 추가 가능
    obj = usage_crud.create_usage_event_stt(db, data=data)
    return UsageEventSTTResponse.model_validate(obj)


@router.get("/events/stt/{event_id}", response_model=UsageEventSTTResponse)
def get_usage_event_stt(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    STT 이벤트 단건 조회.
    """
    obj = usage_crud.get_usage_event_stt(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_stt not found")
    return UsageEventSTTResponse.model_validate(obj)


@router.patch("/events/stt/{event_id}", response_model=UsageEventSTTResponse)
def update_usage_event_stt(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    payload: UsageEventSTTUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    STT 이벤트 수정 (예외 상황용).
    """
    obj = usage_crud.get_usage_event_stt(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_stt not found")

    data = payload.model_dump(exclude_unset=True)
    obj = usage_crud.update_usage_event_stt(db, event=obj, data=data)
    return UsageEventSTTResponse.model_validate(obj)


@router.delete("/events/stt/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_usage_event_stt(
    partner_id: int = Path(..., ge=1),
    event_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    STT 이벤트 삭제.
    """
    obj = usage_crud.get_usage_event_stt(db, event_id=event_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usage_event_stt not found")

    usage_crud.delete_usage_event_stt(db, event=obj)
    return None
