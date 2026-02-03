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
    """현재 사용자의 few-shot 예제를 조회하고 소유권을 검증한다.

    Args:
        db: SQLAlchemy 세션.
        example_id: 조회할 few-shot 예제 PK.
        me: 현재 인증된 사용자.

    Returns:
        소유권이 확인된 ``UserFewShotExample`` 인스턴스.

    Raises:
        HTTPException: 예제가 존재하지 않거나 본인 소유가 아닌 경우 404.
    """
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
    """주어진 few-shot ID 목록이 현재 사용자 소유이며 활성 상태인지 검증한다.

    Args:
        db: SQLAlchemy 세션.
        me: 현재 인증된 사용자.
        example_ids: 검증할 few-shot 예제 ID 시퀀스.

    Raises:
        HTTPException: 중복 ID(400) 또는 유효하지 않은 ID(403).
    """
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
