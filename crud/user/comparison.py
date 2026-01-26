# crud/user/comparison.py
from __future__ import annotations

from typing import Tuple, List, Optional, Any, Dict

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from models.user.comparison import PracticeComparisonRun
from schemas.user.comparison import PracticeComparisonRunCreate, PracticeComparisonRunUpdate


class PracticeComparisonRunCRUD:
    def get(self, db: Session, *, run_id: int) -> Optional[PracticeComparisonRun]:
        stmt = select(PracticeComparisonRun).where(PracticeComparisonRun.id == run_id)
        return db.execute(stmt).scalars().first()

    def list_by_session(
        self,
        db: Session,
        *,
        session_id: int,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[PracticeComparisonRun], int]:
        offset = (page - 1) * size

        base = select(PracticeComparisonRun).where(PracticeComparisonRun.session_id == session_id)

        total_stmt = select(func.count()).select_from(base.subquery())
        total = int(db.execute(total_stmt).scalar() or 0)

        rows_stmt = (
            base.order_by(desc(PracticeComparisonRun.created_at))
            .offset(offset)
            .limit(size)
        )
        rows = db.execute(rows_stmt).scalars().all()
        return rows, total

    def create(
        self,
        db: Session,
        *,
        session_id: int,
        data: PracticeComparisonRunCreate,
    ) -> PracticeComparisonRun:
        payload: Dict[str, Any] = data.model_dump(exclude_unset=True)

        obj = PracticeComparisonRun(
            session_id=session_id,
            **payload,
        )
        db.add(obj)
        db.flush()  # id 확보
        return obj

    def update(
        self,
        db: Session,
        *,
        run: PracticeComparisonRun,
        data: PracticeComparisonRunUpdate,
    ) -> PracticeComparisonRun:
        patch: Dict[str, Any] = data.model_dump(exclude_unset=True)

        for k, v in patch.items():
            setattr(run, k, v)

        db.add(run)
        db.flush()
        return run

    def delete(self, db: Session, *, run: PracticeComparisonRun) -> None:
        db.delete(run)
        db.flush()


practice_comparison_run_crud = PracticeComparisonRunCRUD()

__all__ = [
    "PracticeComparisonRunCRUD",
    "practice_comparison_run_crud",
]
