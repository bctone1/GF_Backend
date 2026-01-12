# service/user/prompt.py
from __future__ import annotations

from typing import Optional, Tuple, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.prompt import AIPrompt, PromptShare
from schemas.user.prompt import (
    AIPromptCreate,
    AIPromptUpdate,
)
from crud.user.prompt import ai_prompt_crud
from models.partner.student import Student, Enrollment
from models.partner.course import Class


# =========================================
# helpers
# =========================================
def ensure_my_prompt(db: Session, prompt_id: int, me: AppUser) -> AIPrompt:
    """
    현재 로그인 유저(me)가 소유한 프롬프트인지 검증 후 반환.
    없거나 남의 프롬프트면 404.
    """
    prompt = ai_prompt_crud.get_for_owner(
        db,
        owner_id=me.user_id,
        prompt_id=prompt_id,
    )
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 프롬프트를 찾을 수 없거나 권한이 없음.",
        )
    return prompt


def ensure_enrolled_in_class(
    db: Session,
    *,
    class_id: int,
    user_id: int,
) -> None:
    """
    주어진 user_id 가 해당 class_id 에 'active' 상태로 수강 중인지 검증.
    - 없으면 403 Forbidden.
    """
    enrollment = (
        db.query(Enrollment)
        .join(Student, Enrollment.student_id == Student.id)
        .filter(
            Enrollment.class_id == class_id,
            Student.user_id == user_id,
            Enrollment.status == "active",
        )
        .first()
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 강의에 수강 중인 학생이 아니라서 사용할 수 없음",
        )


def list_shared_prompts_for_class(
    db: Session,
    *,
    class_id: int,
    me: AppUser,
    active_only: bool = True,
) -> List[AIPrompt]:
    """
    특정 class 에 공유된 프롬프트 목록 조회.
    - 현재는 '해당 강의에 수강 중인 학생'만 허용.
      (강사 허용 로직은 prompt_share 서비스에서 확장 가능)
    """
    # 0) 강의 존재 여부 체크
    cls = db.query(Class).filter(Class.id == class_id).first()
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없음.",
        )

    # 1) me 가 이 class 의 수강생인지 검증 (수강생만 조회 가능)
    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    # 2) 공유 프롬프트 목록 조회
    q = (
        db.query(AIPrompt)
        .join(PromptShare, PromptShare.prompt_id == AIPrompt.prompt_id)
        .filter(PromptShare.class_id == class_id)
    )

    if active_only:
        q = q.filter(
            PromptShare.is_active.is_(True),
            AIPrompt.is_active.is_(True),
        )

    return q.all()


# =========================================
# AIPrompt CRUD
# =========================================
def create_prompt(
    db: Session,
    *,
    me: AppUser,
    data: AIPromptCreate,
) -> AIPrompt:
    """
    새 프롬프트 생성.
    - owner_id는 항상 me.user_id 로 강제.
    - system_prompt는 ai_agents.system_prompt에 저장(버전 없음).
    """
    prompt = ai_prompt_crud.create(
        db,
        obj_in=data,
        owner_id=me.user_id,
    )
    return prompt


def list_my_prompts(
    db: Session,
    *,
    me: AppUser,
    limit: int,
    offset: int,
    q: Optional[str] = None,
) -> Tuple[int, List[AIPrompt]]:
    """
    owner_id = me.user_id 기준 프롬프트 목록 조회.
    """
    total, items = ai_prompt_crud.list_by_owner(
        db,
        owner_id=me.user_id,
        limit=limit,
        offset=offset,
        q=q,
    )
    return total, items


def get_my_prompt(
    db: Session,
    *,
    me: AppUser,
    prompt_id: int,
) -> AIPrompt:
    """
    단일 프롬프트 조회 (소유자 검증 포함).
    """
    return ensure_my_prompt(db, prompt_id, me)


def update_my_prompt(
    db: Session,
    *,
    me: AppUser,
    prompt_id: int,
    data: AIPromptUpdate,
) -> AIPrompt:
    """
    내 프롬프트 수정.
    - system_prompt 업데이트는 여기서 직접 반영됨(공유 템플릿 즉시 반영 정책).
    """
    prompt = ai_prompt_crud.update_for_owner(
        db,
        owner_id=me.user_id,
        prompt_id=prompt_id,
        obj_in=data,
    )
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 프롬프트를 찾을 수 없거나 권한이 없어.",
        )
    return prompt


# =========================================
# 공유 프롬프트 → 내 프롬프트로 포크
# =========================================
def fork_shared_prompt_to_my_prompt(
    db: Session,
    *,
    prompt_id: int,
    class_id: int,
    me: AppUser,
    new_name: Optional[str] = None,
) -> AIPrompt:
    """
    특정 class 에 공유된 강사 프롬프트를
    현재 로그인 유저(me)의 '내 프롬프트'로 복제.
    """
    # 1) 이 prompt 가 해당 class 에 공유되어 있는지 + 활성인지 확인
    share: Optional[PromptShare] = (
        db.query(PromptShare)
        .filter(
            PromptShare.prompt_id == prompt_id,
            PromptShare.class_id == class_id,
            PromptShare.is_active.is_(True),
        )
        .first()
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 프롬프트를 찾을 수 없음.",
        )

    # 2) me 가 이 class 의 수강생(enrollment)인지 검증
    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    # 3) 원본 프롬프트 조회 (소유자와 무관)
    src_prompt: Optional[AIPrompt] = (
        db.query(AIPrompt)
        .filter(AIPrompt.prompt_id == prompt_id)
        .first()
    )
    if src_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="원본 프롬프트를 찾을 수 없어.",
        )

    # 4) 원본 프롬프트 존재 확인(모델상 not-null이지만, 레거시 데이터 방어)
    if not (src_prompt.system_prompt or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="원본 프롬프트에 system_prompt가 비어있어.",
        )

    # 5) 새 프롬프트 생성 (owner_id = me.user_id)
    prompt_in = AIPromptCreate(
        name=new_name or f"{src_prompt.name} - 내 버전",
        role_description=src_prompt.role_description,
        system_prompt=src_prompt.system_prompt,
        template_source="class_shared",
        is_active=True,
    )
    new_prompt = ai_prompt_crud.create(
        db,
        obj_in=prompt_in,
        owner_id=me.user_id,
    )

    return new_prompt
