from __future__ import annotations

from datetime import date
from typing import Optional, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select

from models.partner.analytics import AnalyticsSnapshot

def create_snapshot(db: Session, *, partner_id: int, snapshot_date: date, metric_type: str, metric_value, metadata=None) -> AnalyticsSnapshot:
    obj = AnalyticsSnapshot(
        partner_id=partner_id,
        snapshot_date=snapshot_date,
        metric_type=metric_type,
        metric_value=metric_value,
        metadata=metadata,
    )
    db.add(obj)
    db.flush()
    return obj

def get_snapshot(db: Session, *, snapshot_id: int) -> Optional[AnalyticsSnapshot]:
    return db.get(AnalyticsSnapshot, snapshot_id)

def list_snapshots(
    db: Session,
    *,
    partner_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    metric_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[AnalyticsSnapshot]:
    stmt = select(AnalyticsSnapshot).where(AnalyticsSnapshot.partner_id == partner_id)
    if metric_type:
        stmt = stmt.where(AnalyticsSnapshot.metric_type == metric_type)
    if date_from:
        stmt = stmt.where(AnalyticsSnapshot.snapshot_date >= date_from)
    if date_to:
        stmt = stmt.where(AnalyticsSnapshot.snapshot_date <= date_to)
    stmt = stmt.order_by(AnalyticsSnapshot.snapshot_date.desc()).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()
