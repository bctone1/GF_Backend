# service/user/prompt_share.py
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.prompt import AIPrompt, PromptShare
from models.partner.course import Class
from models.partner.partner_core import Partner
from crud.user.prompt import prompt_share_crud
from schemas.user.prompt import PromptShareCreate


# ==============================
# 내부 헬퍼: 소유/권한 검증
# ==============================
def ensure_my_prompt(db: Session, *, prompt_id: int, me: AppUser) -> AIPrompt:
    """
    현재 로그인 유저(me)가 소유한 프롬프트인지 검증.
    - 못 찾으면 404
    - 내 소유가 아니면 403
    """
    stmt = select(AIPrompt).where(AIPrompt.prompt_id == prompt_id)
    prompt = db.execute(stmt).scalar_one_or_none()
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프롬프트를 찾을 수 없습니다.",
        )
    if prompt.owner_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 프롬프트에 대한 권한이 없습니다.",
        )
    return prompt


def ensure_my_class_as_teacher(db: Session, *, class_id: int, me: AppUser) -> Class:
    """
    현재 로그인 유저(me)가 이 Class 의 담당 강사(Partner)인지 검증.
    - class 자체가 없으면 404
    - class는 있는데 내가 강사가 아니면 403
    """
    exists = db.execute(select(Class).where(Class.id == class_id)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없습니다.",
        )

    stmt = (
        select(Class)
        .join(Partner, Class.partner_id == Partner.id)
        .where(
            Class.id == class_id,
            Partner.user_id == me.user_id,
            Partner.is_active.is_(True),
        )
    )
    classroom = db.execute(stmt).scalar_one_or_none()
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 강의에 대한 권한이 없습니다.",
        )
    return classroom


# ==============================
# 공유 서비스
# ==============================
def share_prompt_to_class(
    db: Session,
    *,
    prompt_id: int,
    class_id: int,
    me: AppUser,
) -> PromptShare:
    """
    강사의 개인 프롬프트를 특정 class 에 공유.
    - 내 프롬프트인지 확인
    - 내가 해당 class 의 강사인지 확인
    - 이미 공유되어 있으면 재사용(비활성 상태였다면 다시 활성화)
    """
    prompt = ensure_my_prompt(db, prompt_id=prompt_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    # 정책 옵션: 비활성 프롬프트는 공유 못 하게
    if not bool(prompt.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성 프롬프트는 공유할 수 없습니다.",
        )

    share_in = PromptShareCreate(
        prompt_id=prompt_id,
        class_id=class_id,
        is_active=None,  # None → CRUD에서 server_default/기본값 처리
    )
    share = prompt_share_crud.get_or_create(
        db,
        obj_in=share_in,
        shared_by_user_id=me.user_id,
    )
    return share


def deactivate_prompt_share(
    db: Session,
    *,
    prompt_id: int,
    class_id: int,
    me: AppUser,
) -> PromptShare:
    """
    특정 class 에 대한 프롬프트 공유 비활성화.
    - 내 프롬프트인지
    - 해당 class 의 강사인지
    - share row 가 실제로 존재하는지
    """
    ensure_my_prompt(db, prompt_id=prompt_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    share = prompt_share_crud.get_by_prompt_and_class(
        db,
        prompt_id=prompt_id,
        class_id=class_id,
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 프롬프트를 찾을 수 없습니다.",
        )

    if not share.is_active:
        return share

    return prompt_share_crud.set_active(db, share=share, is_active=False)


# ==============================
# 강사용 조회(이름 분리해서 혼란 방지)
# ==============================
def list_shared_prompts_for_class_as_teacher(
    db: Session,
    *,
    class_id: int,
    me: Optional[AppUser] = None,
    active_only: bool = True,
) -> List[AIPrompt]:
    """
    특정 class 에 공유된 프롬프트 목록 조회(강사용).
    - me가 있으면 담당 강사인지 검증
    - active_only면 share.is_active + prompt.is_active 모두 True 보장
    - 정렬은 share.created_at desc(= shares 리스트 순서) 유지
    """
    if me is not None:
        ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    shares = prompt_share_crud.list_by_class(
        db,
        class_id=class_id,
        active_only=active_only,
    )
    if not shares:
        return []

    # shares 순서 유지 + 중복 방어
    prompt_ids: List[int] = []
    seen = set()
    for s in shares:
        if s.prompt_id not in seen:
            seen.add(s.prompt_id)
            prompt_ids.append(s.prompt_id)

    stmt = select(AIPrompt).where(AIPrompt.prompt_id.in_(prompt_ids))
    if active_only:
        stmt = stmt.where(AIPrompt.is_active.is_(True))

    prompts = db.execute(stmt).scalars().all()
    prompt_map = {p.prompt_id: p for p in prompts}

    # share 순서대로 리턴
    return [prompt_map[pid] for pid in prompt_ids if pid in prompt_map]


# 기존 이름 유지(호환용). 내부적으로 강사용 함수 호출.
def list_shared_prompts_for_class(
    db: Session,
    *,
    class_id: int,
    me: AppUser | None = None,
    active_only: bool = True,
) -> List[AIPrompt]:
    return list_shared_prompts_for_class_as_teacher(
        db=db,
        class_id=class_id,
        me=me,
        active_only=active_only,
    )
