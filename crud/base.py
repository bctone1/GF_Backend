# crud/base.py
from __future__ import annotations

from typing import Any, Generic, Mapping, Sequence, TypeVar, Optional, Iterable
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect as sa_inspect

from models.base import Base  # declarative_base()

# ---- 제네릭 타입 ----
ModelT = TypeVar("ModelT", bound=Base)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class CRUDBase(Generic[ModelT, CreateT, UpdateT]):
    """
    공통 CRUD 베이스.
    - get, get_multi, create, update, delete
    - PK 이름 고정 가정 없음 (모델의 첫 번째 PK 컬럼을 자동 사용)
    """

    def __init__(self, model: type[ModelT]):
        self.model = model

    # ---------- 내부 유틸 ----------
    @property
    def _pk_col(self):
        return sa_inspect(self.model).primary_key[0]

    def _to_data(self, obj: CreateT | UpdateT | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(obj, BaseModel):
            # Pydantic v2
            return obj.model_dump(exclude_unset=True)
        # dict-like
        return dict(obj)

    def _apply_filters(self, query, filters: Optional[Mapping[str, Any]]):
        if not filters:
            return query
        for k, v in filters.items():
            col = getattr(self.model, k, None)
            if col is None:
                continue
            if v is None:
                query = query.where(col.is_(None))
            elif isinstance(v, (list, tuple, set)):
                if len(v) == 0:
                    # 빈 IN 조건이면 결과 없음
                    query = query.where(False)
                else:
                    query = query.where(col.in_(list(v)))
            else:
                query = query.where(col == v)
        return query

    def _apply_order_by(self, query, order_by: Optional[Iterable[str]]):
        if not order_by:
            return query
        clauses = []
        for field in order_by:
            desc = False
            name = field
            if field.startswith("-"):
                desc = True
                name = field[1:]
            col = getattr(self.model, name, None)
            if col is None:
                continue
            clauses.append(col.desc() if desc else col.asc())
        if clauses:
            query = query.order_by(*clauses)
        return query

    # ---------- CRUD ----------
    def get(self, db: Session, id: Any) -> Optional[ModelT]:
        stmt = select(self.model).where(self._pk_col == id)
        return db.execute(stmt).scalars().first()

    def get_multi(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 100,
        filters: Optional[Mapping[str, Any]] = None,
        order_by: Optional[Iterable[str]] = None,
    ) -> list[ModelT]:
        stmt = select(self.model)
        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_order_by(stmt, order_by)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, *, obj_in: CreateT | Mapping[str, Any]) -> ModelT:
        data = self._to_data(obj_in)
        db_obj: ModelT = self.model(**data)  # type: ignore[arg-type]
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelT,
        obj_in: UpdateT | Mapping[str, Any],
        exclude_none: bool = False,
    ) -> ModelT:
        data = self._to_data(obj_in)
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        for field, value in data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: Any | None = None, db_obj: ModelT | None = None) -> None:
        if db_obj is None:
            if id is None:
                raise ValueError("delete() requires either id or db_obj.")
            db_obj = self.get(db, id)
            if db_obj is None:
                return
        db.delete(db_obj)
        db.commit()
