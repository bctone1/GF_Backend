# crud/user/activity.py
"""CRUD for user_activity_events & practice_feature_stats."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Tuple

from sqlalchemy import select, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.user.activity import UserActivityEvent, PracticeFeatureStat
from schemas.user.activity import UserActivityEventCreate


class UserActivityEventCRUD:
    """user.user_activity_events CRUD (쓰기는 내부 서비스 전용)."""

    def create(self, db: Session, *, data: UserActivityEventCreate) -> UserActivityEvent:
        """내부 서비스용 이벤트 생성."""
        obj = UserActivityEvent(
            user_id=data.user_id,
            event_type=data.event_type,
            related_type=data.related_type,
            related_id=data.related_id,
            meta=data.metadata,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, event_id: int) -> Optional[UserActivityEvent]:
        """단건 조회."""
        stmt = select(UserActivityEvent).where(
            UserActivityEvent.event_id == event_id,
        )
        return db.scalar(stmt)

    def list_by_user(
        self,
        db: Session,
        user_id: int,
        *,
        event_type: Optional[str] = None,
        related_type: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[Sequence[UserActivityEvent], int]:
        """사용자별 이벤트 목록 (페이지네이션)."""
        filters = [UserActivityEvent.user_id == user_id]
        if event_type is not None:
            filters.append(UserActivityEvent.event_type == event_type)
        if related_type is not None:
            filters.append(UserActivityEvent.related_type == related_type)

        base = select(UserActivityEvent).where(*filters)
        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

        stmt = (
            base
            .order_by(UserActivityEvent.occurred_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = db.scalars(stmt).all()
        return rows, total

    def bulk_update_meta(
        self,
        db: Session,
        updates: list[tuple[int, dict[str, Any]]],
    ) -> int:
        """여러 이벤트의 meta를 병합 갱신. returns 갱신 건수.

        Args:
            db: Active DB session (caller manages commit).
            updates: List of (event_id, new_meta) pairs.
        """
        if not updates:
            return 0

        count = 0
        for event_id, new_meta in updates:
            row = db.get(UserActivityEvent, event_id)
            if row is None:
                continue
            existing = row.meta or {}
            merged = {**existing, **new_meta}
            row.meta = merged
            count += 1

        if count:
            db.flush()
        return count


class PracticeFeatureStatCRUD:
    """user.practice_feature_stats CRUD (쓰기는 내부 서비스 전용)."""

    def upsert(
        self,
        db: Session,
        *,
        user_id: int,
        class_id: Optional[int],
        feature_type: str,
        increment: int = 1,
    ) -> PracticeFeatureStat:
        """ON CONFLICT increment usage_count (내부 서비스용)."""
        now = datetime.now(timezone.utc)
        insert_stmt = pg_insert(PracticeFeatureStat).values(
            user_id=user_id,
            class_id=class_id,
            feature_type=feature_type,
            usage_count=increment,
            last_used_at=now,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_practice_feature_stats_user_class_feature",
            set_={
                "usage_count": PracticeFeatureStat.usage_count + increment,
                "last_used_at": now,
            },
        )
        db.execute(upsert_stmt)
        db.flush()

        # 방금 upsert 된 행 조회
        class_filter = (
            PracticeFeatureStat.class_id == class_id
            if class_id is not None
            else PracticeFeatureStat.class_id.is_(None)
        )
        stmt = select(PracticeFeatureStat).where(
            PracticeFeatureStat.user_id == user_id,
            class_filter,
            PracticeFeatureStat.feature_type == feature_type,
        )
        row = db.scalar(stmt)
        assert row is not None
        return row

    def get(self, db: Session, stat_id: int) -> Optional[PracticeFeatureStat]:
        """단건 조회."""
        stmt = select(PracticeFeatureStat).where(
            PracticeFeatureStat.stat_id == stat_id,
        )
        return db.scalar(stmt)

    def list_by_user(
        self,
        db: Session,
        user_id: int,
        *,
        class_id: Optional[int] = None,
    ) -> Sequence[PracticeFeatureStat]:
        """사용자별 기능 통계 목록."""
        filters = [PracticeFeatureStat.user_id == user_id]
        if class_id is not None:
            filters.append(PracticeFeatureStat.class_id == class_id)

        stmt = (
            select(PracticeFeatureStat)
            .where(*filters)
            .order_by(PracticeFeatureStat.feature_type)
        )
        return db.scalars(stmt).all()


activity_event_crud = UserActivityEventCRUD()
practice_feature_stat_crud = PracticeFeatureStatCRUD()
