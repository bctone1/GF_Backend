# app/endpoints/user/activity.py
"""읽기 전용 엔드포인트: 활동 이벤트 & 기능 사용 통계."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from crud.user.activity import activity_event_crud, practice_feature_stat_crud
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.activity import (
    UserActivityEventResponse,
    PracticeFeatureStatResponse,
)

router = APIRouter()


@router.get(
    "/events",
    response_model=Page[UserActivityEventResponse],
    operation_id="list_my_activity_events",
    summary="내활동이벤트목록",
)
def list_my_activity_events(
    event_type: Optional[str] = Query(None, description="이벤트 유형 필터"),
    related_type: Optional[str] = Query(None, description="관련 대상 유형 필터"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> dict:
    """내 활동 이벤트를 페이지네이션으로 조회합니다."""
    rows, total = activity_event_crud.list_by_user(
        db,
        user_id=me.user_id,
        event_type=event_type,
        related_type=related_type,
        page=page,
        size=size,
    )
    items = [UserActivityEventResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/events/{event_id}",
    response_model=UserActivityEventResponse,
    operation_id="get_my_activity_event",
    summary="활동이벤트단건조회",
)
def get_my_activity_event(
    event_id: int = Path(..., description="이벤트 ID"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> UserActivityEventResponse:
    """활동 이벤트 단건을 조회합니다. 본인 소유만 허용."""
    row = activity_event_crud.get(db, event_id)
    if row is None or row.user_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이벤트를 찾을 수 없습니다.",
        )
    return UserActivityEventResponse.model_validate(row)


@router.get(
    "/feature-stats",
    response_model=list[PracticeFeatureStatResponse],
    operation_id="list_my_feature_stats",
    summary="내기능사용통계",
)
def list_my_feature_stats(
    class_id: Optional[int] = Query(None, description="강의 ID 필터"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> list[PracticeFeatureStatResponse]:
    """내 실습 기능 사용 통계를 조회합니다."""
    rows = practice_feature_stat_crud.list_by_user(
        db,
        user_id=me.user_id,
        class_id=class_id,
    )
    return [PracticeFeatureStatResponse.model_validate(r) for r in rows]
