# crud/user/fewshot.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Any, Mapping, Union

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from sqlalchemy.exc import IntegrityError

from crud.base import coerce_dict
from models.user.fewshot import UserFewShotExample, FewShotShare
from schemas.user.fewshot import (
    UserFewShotExampleCreate,
    UserFewShotExampleUpdate,
    FewShotShareCreate,
)


class UserFewShotExampleCRUD:
    def create(self, db: Session, *, user_id: int, data: UserFewShotExampleCreate) -> UserFewShotExample:
        obj = UserFewShotExample(
            user_id=user_id,
            title=data.title,
            input_text=data.input_text,
            output_text=data.output_text,
            fewshot_source=data.fewshot_source,
            meta=coerce_dict(data.meta),
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
            values["meta"] = coerce_dict(values.get("meta"))

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


class FewShotShareCRUD:
    def create(
        self,
        db: Session,
        *,
        obj_in: FewShotShareCreate,
        shared_by_user_id: int,
    ) -> FewShotShare:
        data = obj_in.model_dump(exclude_unset=True)
        if data.get("is_active", "__missing__") is None:
            data.pop("is_active", None)

        db_obj = FewShotShare(shared_by_user_id=shared_by_user_id, **data)
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def get_by_example_and_class(
        self,
        db: Session,
        *,
        example_id: int,
        class_id: int,
    ) -> Optional[FewShotShare]:
        return (
            db.query(FewShotShare)
            .filter(
                FewShotShare.example_id == example_id,
                FewShotShare.class_id == class_id,
            )
            .first()
        )

    def list_by_example(
        self,
        db: Session,
        *,
        example_id: int,
        active_only: bool = True,
    ) -> Sequence[FewShotShare]:
        query = db.query(FewShotShare).filter(FewShotShare.example_id == example_id)
        if active_only:
            query = query.filter(FewShotShare.is_active.is_(True))
        return query.order_by(FewShotShare.created_at.desc()).all()

    def list_by_class(
        self,
        db: Session,
        *,
        class_id: int,
        active_only: bool = True,
    ) -> Sequence[FewShotShare]:
        query = db.query(FewShotShare).filter(FewShotShare.class_id == class_id)
        if active_only:
            query = query.filter(FewShotShare.is_active.is_(True))
        return query.order_by(FewShotShare.created_at.desc()).all()

    def set_active(
        self,
        db: Session,
        *,
        share: FewShotShare,
        is_active: bool,
    ) -> FewShotShare:
        share.is_active = is_active
        db.add(share)
        db.flush()
        db.refresh(share)
        return share

    def get_or_create(
        self,
        db: Session,
        *,
        obj_in: FewShotShareCreate,
        shared_by_user_id: int,
    ) -> FewShotShare:
        existing = self.get_by_example_and_class(
            db,
            example_id=obj_in.example_id,
            class_id=obj_in.class_id,
        )
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.add(existing)
                db.flush()
                db.refresh(existing)
            return existing

        try:
            with db.begin_nested():
                obj = self.create(db=db, obj_in=obj_in, shared_by_user_id=shared_by_user_id)
            return obj
        except IntegrityError:
            again = self.get_by_example_and_class(
                db,
                example_id=obj_in.example_id,
                class_id=obj_in.class_id,
            )
            if again is None:
                raise
            if not again.is_active:
                again.is_active = True
                db.add(again)
                db.flush()
                db.refresh(again)
            return again


few_shot_share_crud = FewShotShareCRUD()
