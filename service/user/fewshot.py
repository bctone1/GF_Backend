# service/user/fewshot.py
from __future__ import annotations

from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.fewshot import UserFewShotExample
from crud.user.fewshot import user_few_shot_example_crud


def ensure_my_few_shot_example(db: Session, *, example_id: int, me: AppUser) -> UserFewShotExample:
    obj = user_few_shot_example_crud.get(db, example_id)
    if not obj or obj.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="few_shot_example_not_found")
    return obj


def validate_my_few_shot_example_ids(
    db: Session,
    *,
    me: AppUser,
    example_ids: Sequence[int],
) -> None:
    # 중복 체크(입력 순서 유지/정규화는 schema에서 하고, 여기서는 안전장치)
    if len(example_ids) != len(set(example_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duplicate_few_shot_example_ids",
        )
    if not example_ids:
        return

    stmt = (
        select(func.count(UserFewShotExample.example_id))
        .where(UserFewShotExample.user_id == me.user_id)
        .where(UserFewShotExample.is_active.is_(True))
        .where(UserFewShotExample.example_id.in_(example_ids))
    )
    cnt = db.scalar(stmt) or 0
    if cnt != len(example_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_few_shot_example_ids",
        )
