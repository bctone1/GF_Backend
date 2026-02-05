# app/endpoints/user/prompt.py
from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
    Body,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.prompt import (
    AIPromptResponse,
    AIPromptCreate,
    AIPromptUpdate,
    PromptShareResponse,
    PromptForkRequest,
)
from service.user.prompt_share import (
    share_prompt_to_class,
    deactivate_prompt_share,
)
from service.user.prompt import (
    create_prompt,
    list_my_prompts,
    get_my_prompt,
    update_my_prompt,
    delete_my_prompt,
    fork_shared_prompt_to_my_prompt,
    list_shared_prompts_for_class,
)
from service.user.activity import track_event

router = APIRouter()


# =========================================
# (학생용) class 기준 공유 프롬프트 목록
# =========================================
@router.get(
    "/prompts/shared",
    response_model=List[AIPromptResponse],
    summary="공유프롬프트",
    operation_id="list_shared_prompts_for_class",
)
def list_shared_prompts_for_class_endpoint(
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 프롬프트를 조회할 강의실 ID (partner.classes.id)",
    ),
    active_only: bool = Query(
        True,
        description="true 이면 활성 공유(is_active=true)만 조회",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 class 에 공유된 프롬프트 목록을 조회한다.

    현재 서비스 로직:
    - me가 해당 class에 'active' 상태로 등록된 수강생(enrollment)인 경우에만 조회 가능.
    """
    prompts = list_shared_prompts_for_class(
        db=db,
        class_id=class_id,
        me=me,
        active_only=active_only,
    )
    return prompts


# =========================================
# 공유 프롬프트 → 내 프롬프트로 포크
# =========================================
@router.post(
    "/prompts/{prompt_id}/fork",
    response_model=AIPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="프롬프트복제",
    operation_id="fork_shared_prompt_to_my_prompt",
)
def fork_shared_prompt_to_my_prompt_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="원본 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    payload: PromptForkRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - prompt_id: 강사가 만든 원본 프롬프트 ID
    - payload.class_id: 이 프롬프트가 공유된 class_id

    서비스 로직:
    - prompt_id가 class_id에 공유(is_active=true) 되어 있어야 하고
    - me가 그 class에 'active' 상태로 등록된 수강생이어야 포크 가능
    """
    new_prompt = fork_shared_prompt_to_my_prompt(
        db=db,
        prompt_id=prompt_id,
        class_id=payload.class_id,
        me=me,
        new_name=payload.name,
    )
    db.commit()
    return new_prompt


# =========================================
# 내 프롬프트 카드 CRUD
# =========================================
@router.post(
    "/prompts",
    response_model=AIPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="프롬프트생성",
    operation_id="create_my_prompt",
)
def create_my_prompt_endpoint(
    body: AIPromptCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    프롬프트 생성.
    - owner_id는 서버에서 me.user_id로 채움
    - system_prompt는 생성 시 함께 저장
    """
    prompt = create_prompt(db=db, me=me, data=body)

    track_event(
        db, user_id=me.user_id, event_type="prompt_created",
        related_type="ai_prompt", related_id=prompt.prompt_id,
    )
    db.commit()

    return prompt


@router.get(
    "/prompts",
    response_model=Page[AIPromptResponse],
    summary="프롬프트목록",
    operation_id="list_my_prompts",
)
def list_my_prompts_endpoint(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(
        None, description="프롬프트 이름/역할 설명 검색 키워드"
    ),
):
    """
    내(owner_id=me.user_id) 프롬프트 목록을 페이징 조회.
    - q로 name / role_description LIKE 검색 가능
    """
    total, prompts = list_my_prompts(
        db=db,
        me=me,
        limit=limit,
        offset=offset,
        q=q,
    )
    return {
        "total": total,
        "items": prompts,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/prompts/{prompt_id}",
    response_model=AIPromptResponse,
    summary="프롬프트조회",
    operation_id="get_my_prompt",
)
def get_my_prompt_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="조회할 내 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    단일 프롬프트 상세 조회.
    - owner_id != me.user_id 이면 404 처리 (서비스 레이어에서 검증)
    """
    prompt = get_my_prompt(db=db, me=me, prompt_id=prompt_id)
    return prompt


@router.patch(
    "/prompts/{prompt_id}",
    response_model=AIPromptResponse,
    summary="프롬프트수정",
    operation_id="update_my_prompt",
)
def update_my_prompt_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="수정할 내 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    body: AIPromptUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    프롬프트 수정.
    - name / role_description / system_prompt / template_source / is_active
    """
    prompt = update_my_prompt(db=db, me=me, prompt_id=prompt_id, data=body)
    db.commit()
    return prompt


@router.delete(
    "/prompts/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="프롬프트삭제",
    operation_id="delete_my_prompt",
)
def delete_my_prompt_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="삭제할 내 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    내 프롬프트 삭제.
    - owner_id != me.user_id 이면 404 처리 (서비스 레이어에서 검증)
    """
    delete_my_prompt(db=db, me=me, prompt_id=prompt_id)
    db.commit()
    return None


# =========================================
# 강사용: 내 프롬프트를 특정 class 에 공유
# =========================================
@router.post(
    "/prompts/{prompt_id}/share",
    response_model=PromptShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="프롬프트공유",
    operation_id="share_prompt_to_class",
)
def share_prompt_to_class_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="공유할 내 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 대상 강의실 ID (partner.classes.id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    강사의 개인 프롬프트를 특정 class 에 공유한다.

    검증:
    - prompt_id 존재 여부
    - 해당 프롬프트 owner_id == me.user_id
    - class_id 존재 + 내가 그 class 담당 강사인지
    """
    share = share_prompt_to_class(
        db=db,
        prompt_id=prompt_id,
        class_id=class_id,
        me=me,
    )
    db.commit()
    return share


@router.delete(
    "/prompts/{prompt_id}/share",
    response_model=PromptShareResponse,
    summary="공유해제",
    operation_id="deactivate_prompt_share",
)
def deactivate_prompt_share_endpoint(
    prompt_id: int = Path(
        ...,
        ge=1,
        description="공유 해제할 내 프롬프트 ID (user.ai_prompts.prompt_id)",
    ),
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 해제 대상 강의실 ID (partner.classes.id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 class 에 대한 내 프롬프트 공유를 비활성화한다.
    """
    share = deactivate_prompt_share(
        db=db,
        prompt_id=prompt_id,
        class_id=class_id,
        me=me,
    )
    db.commit()
    return share
