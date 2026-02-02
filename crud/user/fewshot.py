# crud/user/fewshot.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Any, Mapping, Union

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from models.user.fewshot import UserFewShotExample
from schemas.user.fewshot import UserFewShotExampleCreate, UserFewShotExampleUpdate


def _coerce_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_unset=True)
    return dict(value) if isinstance(value, dict) else {}


class UserFewShotExampleCRUD:
    def create(self, db: Session, *, user_id: int, data: UserFewShotExampleCreate) -> UserFewShotExample:
        obj = UserFewShotExample(
            user_id=user_id,
            title=data.title,
            input_text=data.input_text,
            output_text=data.output_text,
            meta=_coerce_dict(data.meta),
            is_active=data.is_active if data.is_active is not None else True,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, example_id: int) -> Optional[UserFewShotExample]:
        stmt = select(UserFewShotExample).where(UserFewShotExample.example_id == example_id)
        return db.scalar(stmt)

    def list_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        page: int = 1,
        size: int = 50,
        is_active: Optional[bool] = None,
    ) -> Tuple[Sequence[UserFewShotExample], int]:
        stmt = select(UserFewShotExample).where(UserFewShotExample.user_id == user_id)
        if is_active is not None:
            stmt = stmt.where(UserFewShotExample.is_active == is_active)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        stmt = (
            stmt.order_by(UserFewShotExample.created_at.desc(), UserFewShotExample.example_id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = db.scalars(stmt).all()
        return rows, total

    def update(
        self,
        db: Session,
        *,
        example_id: int,
        data: Union[UserFewShotExampleUpdate, Mapping[str, Any]],
    ) -> Optional[UserFewShotExample]:
        obj = db.get(UserFewShotExample, example_id)
        if obj is None:
            return None

        values = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        if not values:
            return obj

        if "meta" in values:
            values["meta"] = _coerce_dict(values.get("meta"))

        for k, v in values.items():
            setattr(obj, k, v)

        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, *, example_id: int) -> None:
        obj = db.get(UserFewShotExample, example_id)
        if obj:
            db.delete(obj)
            db.flush()


user_few_shot_example_crud = UserFewShotExampleCRUD()
