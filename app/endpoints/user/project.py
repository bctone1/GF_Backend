# app/endpoints/user/project.py
from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Path,
    status,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.project import (
    UserProjectCreate,
    UserProjectUpdate,
    UserProjectResponse,
    ProjectSessionSummaryResponse,
)
from service.user.project import (
    create_project_for_me,
    list_my_projects,
    get_my_project,
    update_my_project,
    delete_my_project,
    list_project_session_summaries_for_me,
)

router = APIRouter()


# =========================================
# 프로젝트 CRUD
# =========================================
@router.get(
    "/projects",
    response_model=Page[UserProjectResponse],
    summary="내 프로젝트 목록 조회",
    operation_id="list_my_projects",
)
def list_my_projects_endpoint(
    class_id: Optional[int] = Query(
        None,
        description="특정 class 안의 프로젝트만 보고 싶을 때 사용",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    skip = (page - 1) * size
    items, total = list_my_projects(
        db,
        me=me,
        class_id=class_id,
        skip=skip,
        limit=size,
    )
    return Page[UserProjectResponse](
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/projects",
    response_model=UserProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="새 프로젝트 생성",
    operation_id="create_project",
)
def create_project_endpoint(
    body: UserProjectCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    project = create_project_for_me(db, me=me, obj_in=body)
    return project


@router.get(
    "/projects/{project_id}",
    response_model=UserProjectResponse,
    summary="프로젝트 상세 조회",
    operation_id="get_project",
)
def get_project_endpoint(
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    project = get_my_project(db, project_id=project_id, me=me)
    return project


@router.patch(
    "/projects/{project_id}",
    response_model=UserProjectResponse,
    summary="프로젝트 정보 수정",
    operation_id="update_project",
)
def update_project_endpoint(
    project_id: int = Path(..., ge=1),
    body: UserProjectUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    project = update_my_project(
        db,
        project_id=project_id,
        me=me,
        obj_in=body,
    )
    return project


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="프로젝트 삭제",
    operation_id="delete_project",
)
def delete_project_endpoint(
    project_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    delete_my_project(db, project_id=project_id, me=me)
    # 204 이므로 바디 없이 리턴
    return None


# =========================================
# 프로젝트 안의 세션 카드 리스트
#   → 프론트에서 "프로젝트 카드 클릭" 시 호출
# =========================================
@router.get(
    "/projects/{project_id}/sessions",
    response_model=List[ProjectSessionSummaryResponse],
    summary="프로젝트 안의 세션(대화) 목록",
    operation_id="list_project_sessions",
)
def list_project_sessions_endpoint(
    project_id: int = Path(..., ge=1),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - 프로젝트를 클릭했을 때 뜨는 '대화 목록' 화면용.
    - 각 아이템: 제목, 마지막 메시지 일부, 사용 모델 태그, 마지막 활동 시간.
    """
    sessions = list_project_session_summaries_for_me(
        db,
        project_id=project_id,
        me=me,
        skip=offset,
        limit=limit,
    )
    return sessions
