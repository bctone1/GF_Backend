# app/endpoints/user/fewshot.py
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.fewshot import (
    UserFewShotExampleCreate,
    UserFewShotExampleUpdate,
    UserFewShotExampleResponse,
    FewShotShareResponse,
    FewShotForkRequest,
)
from crud.user.fewshot import user_few_shot_example_crud
from service.user.fewshot import ensure_my_few_shot_example
from service.user.activity import track_event
from service.user.fewshot_share import (
    share_few_shot_example_to_class,
    deactivate_few_shot_share,
    list_shared_few_shot_examples_for_class,
    fork_shared_few_shot_example,
    attach_class_ids_to_examples,
)


router = APIRouter()


# =========================================================
# Few-shot Example Library (개인)
# =========================================================
@router.get(
    "/few-shot-examples",
    response_model=Page[UserFewShotExampleResponse],
    operation_id="list_my_few_shot_examples",
    summary="few-shot목록",
)
def list_my_few_shot_examples(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    내 few-shot 목록 조회.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    rows, total = user_few_shot_example_crud.list_by_user(
        db,
        user_id=me.user_id,
        page=page,
        size=size,
        is_active=is_active,
    )
    attach_class_ids_to_examples(db, examples=rows, active_only=True)
    items = [UserFewShotExampleResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/few-shot-examples",
    response_model=UserFewShotExampleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_my_few_shot_example",
    summary="few-shot생성",
)
def create_my_few_shot_example(
    data: UserFewShotExampleCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    내 few-shot 생성.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    obj = user_few_shot_example_crud.create(db, user_id=me.user_id, data=data)

    track_event(
        db, user_id=me.user_id, event_type="fewshot_created",
        related_type="fewshot_example", related_id=obj.example_id,
    )

    db.commit()
    attach_class_ids_to_examples(db, examples=[obj], active_only=True)
    return UserFewShotExampleResponse.model_validate(obj)


# =========================================================
# (학생용) class 기준 공유 few-shot 목록
# — /{example_id} 보다 위에 위치해야 "shared"가 path param으로 먹히지 않음
# =========================================================
@router.get(
    "/few-shot-examples/shared",
    response_model=List[UserFewShotExampleResponse],
    summary="공유퓨샷",
    operation_id="list_shared_few_shot_examples_for_class",
)
def list_shared_few_shot_examples_for_class_endpoint(
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 few-shot을 조회할 강의실 ID (partner.classes.id)",
    ),
    active_only: bool = Query(
        True,
        description="true 이면 활성 공유(is_active=true)만 조회",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    강의실 기준 공유 few-shot 조회.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    examples = list_shared_few_shot_examples_for_class(
        db=db,
        class_id=class_id,
        me=me,
        active_only=active_only,
    )
    return [UserFewShotExampleResponse.model_validate(example) for example in examples]


@router.get(
    "/few-shot-examples/{example_id}",
    response_model=UserFewShotExampleResponse,
    operation_id="get_my_few_shot_example",
    summary="few-shot조회",
)
def get_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    내 few-shot 단건 조회.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    obj = ensure_my_few_shot_example(db, example_id=example_id, me=me)
    attach_class_ids_to_examples(db, examples=[obj], active_only=True)
    return UserFewShotExampleResponse.model_validate(obj)


@router.patch(
    "/few-shot-examples/{example_id}",
    response_model=UserFewShotExampleResponse,
    operation_id="update_my_few_shot_example",
    summary="few-shot수정",
)
def update_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    data: UserFewShotExampleUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    내 few-shot 수정.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    _ = ensure_my_few_shot_example(db, example_id=example_id, me=me)
    obj = user_few_shot_example_crud.update(db, example_id=example_id, data=data)
    db.commit()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="few_shot_example_not_found")
    attach_class_ids_to_examples(db, examples=[obj], active_only=True)
    return UserFewShotExampleResponse.model_validate(obj)


@router.delete(
    "/few-shot-examples/{example_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_my_few_shot_example",
    summary="few-shot삭제",
)
def delete_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_few_shot_example(db, example_id=example_id, me=me)
    user_few_shot_example_crud.delete(db, example_id=example_id)
    db.commit()
    return None


# =========================================================
# 공유 few-shot → 내 few-shot으로 복제
# =========================================================
@router.post(
    "/few-shot-examples/{example_id}/fork",
    response_model=UserFewShotExampleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="퓨샷복제",
    operation_id="fork_shared_few_shot_example",
)
def fork_shared_few_shot_example_endpoint(
    example_id: int = Path(
        ...,
        ge=1,
        description="원본 few-shot ID (user.few_shot_examples.example_id)",
    ),
    payload: FewShotForkRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    공유 few-shot을 내 few-shot으로 복제.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    new_example = fork_shared_few_shot_example(
        db=db,
        example_id=example_id,
        class_id=payload.class_id,
        name=payload.name,
        me=me,
    )
    db.commit()
    attach_class_ids_to_examples(db, examples=[new_example], active_only=True)
    return UserFewShotExampleResponse.model_validate(new_example)


# =========================================================
# 강사용: 내 few-shot을 특정 class에 공유
# =========================================================
@router.post(
    "/few-shot-examples/{example_id}/share",
    response_model=FewShotShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="퓨샷공유",
    operation_id="share_few_shot_example_to_class",
)
def share_few_shot_example_to_class_endpoint(
    example_id: int = Path(
        ...,
        ge=1,
        description="공유할 내 few-shot ID (user.few_shot_examples.example_id)",
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
    강사용: 내 few-shot을 특정 class에 공유.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    share = share_few_shot_example_to_class(
        db=db,
        example_id=example_id,
        class_id=class_id,
        me=me,
    )
    db.commit()
    return FewShotShareResponse.model_validate(share)


@router.delete(
    "/few-shot-examples/{example_id}/share",
    response_model=FewShotShareResponse,
    summary="퓨샷해제",
    operation_id="deactivate_few_shot_share",
)
def deactivate_few_shot_share_endpoint(
    example_id: int = Path(
        ...,
        ge=1,
        description="공유 해제할 내 few-shot ID (user.few_shot_examples.example_id)",
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
    공유 few-shot 해제.
    - fewshot_source: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)
    """
    share = deactivate_few_shot_share(
        db=db,
        example_id=example_id,
        class_id=class_id,
        me=me,
    )
    db.commit()
    return FewShotShareResponse.model_validate(share)
