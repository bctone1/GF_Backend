# app/endpoints/user/fewshot.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.fewshot import (
    UserFewShotExampleCreate,
    UserFewShotExampleUpdate,
    UserFewShotExampleResponse,
)
from crud.user.fewshot import user_few_shot_example_crud
from service.user.fewshot import ensure_my_few_shot_example


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
    rows, total = user_few_shot_example_crud.list_by_user(
        db,
        user_id=me.user_id,
        page=page,
        size=size,
        is_active=is_active,
    )
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
    obj = user_few_shot_example_crud.create(db, user_id=me.user_id, data=data)
    db.commit()
    return UserFewShotExampleResponse.model_validate(obj)


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
    obj = ensure_my_few_shot_example(db, example_id=example_id, me=me)
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
    _ = ensure_my_few_shot_example(db, example_id=example_id, me=me)
    obj = user_few_shot_example_crud.update(db, example_id=example_id, data=data)
    db.commit()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="few_shot_example_not_found")
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
