# service/user/project.py
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core import config
from models.user.account import AppUser
from models.user.project import UserProject
from crud.user.project import user_project_crud
from schemas.user.project import (
    UserProjectCreate,
    UserProjectUpdate,
    UserProjectResponse,
    ProjectSessionSummaryResponse,
)


# =========================================
# helpers
# =========================================
def ensure_my_project(
    db: Session,
    project_id: int,
    me: AppUser,
) -> UserProject:
    project = user_project_crud.get(db, id=project_id)
    if not project or project.owner_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다.",
        )
    return project


def _get_model_label(model_name: str) -> str:
    """
    실습 모델 설정(config.PRACTICE_MODELS)에서 사람이 읽기 좋은 라벨 찾기.
    - 구조가 달라도 최대한 name / label / display_name 을 먼저 쓰고,
      없으면 model_name 그대로 반환.
    """
    try:
        practice_models = getattr(config, "PRACTICE_MODELS", [])
        for m in practice_models:
            # dict 형식 가정
            if not isinstance(m, dict):
                continue
            if m.get("model_name") == model_name or m.get("id") == model_name:
                return (
                    m.get("label")
                    or m.get("display_name")
                    or m.get("name")
                    or model_name
                )
    except Exception:
        # 설정이 없거나 형식이 달라도 장애 나지 않게 방어
        pass
    return model_name


# =========================================
# 기본 프로젝트 CRUD 서비스
# =========================================
def create_project_for_me(
    db: Session,
    *,
    me: AppUser,
    obj_in: UserProjectCreate,
) -> UserProject:
    return user_project_crud.create(
        db,
        obj_in=obj_in,
        owner_id=me.user_id,
    )


def list_my_projects(
    db: Session,
    *,
    me: AppUser,
    class_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[List[UserProject], int]:
    """
    내 프로젝트 목록 + total 개수 반환 (Page 응답용).
    """
    base = select(UserProject).where(UserProject.owner_id == me.user_id)
    if class_id is not None:
        base = base.where(UserProject.class_id == class_id)

    # total
    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()

    # items
    items = user_project_crud.get_multi_by_owner(
        db,
        owner_id=me.user_id,
        class_id=class_id,
        skip=skip,
        limit=limit,
    )
    return items, total


def get_my_project(
    db: Session,
    *,
    project_id: int,
    me: AppUser,
) -> UserProject:
    return ensure_my_project(db, project_id, me)


def update_my_project(
    db: Session,
    *,
    project_id: int,
    me: AppUser,
    obj_in: UserProjectUpdate,
) -> UserProject:
    project = ensure_my_project(db, project_id, me)
    project = user_project_crud.update(db, db_obj=project, obj_in=obj_in)
    return project


def delete_my_project(
    db: Session,
    *,
    project_id: int,
    me: AppUser,
) -> None:
    project = ensure_my_project(db, project_id, me)
    user_project_crud.remove(db, id=project.project_id)


# =========================================
# 프로젝트 안의 세션 카드 리스트
# =========================================
def list_project_session_summaries_for_me(
    db: Session,
    *,
    project_id: int,
    me: AppUser,
    skip: int = 0,
    limit: int = 50,
) -> List[ProjectSessionSummaryResponse]:
    """
    프로젝트를 클릭했을 때 나오는 '대화 목록' 카드 리스트.
    - 세션 제목
    - 마지막 응답 일부 (preview)
    - 사용한 모델 태그 (GPT-4, Claude 등)
    """
    # 권한 체크
    project = ensure_my_project(db, project_id, me)

    raw_list = user_project_crud.list_session_summaries(
        db,
        project_id=project.project_id,
        owner_id=me.user_id,
        skip=skip,
        limit=limit,
    )

    results: List[ProjectSessionSummaryResponse] = []
    for row in raw_list:
        model_name = row["model_name"]
        label = _get_model_label(model_name)

        item = ProjectSessionSummaryResponse(
            session_id=row["session_id"],
            project_id=row["project_id"],
            class_id=row["class_id"],
            title=row["title"] or "제목 없는 대화",
            last_message_preview=row["preview_text"] or "",
            primary_model_name=model_name,
            primary_model_label=label,
            last_activity_at=row["last_activity_at"],
        )
        results.append(item)

    return results
