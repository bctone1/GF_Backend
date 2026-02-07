# crud/partner/activity.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc, and_
from sqlalchemy.orm import Session

from models.partner.activity import ActivityEvent


def create_activity_event(
    db: Session,
    *,
    partner_id: int,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> ActivityEvent:
    """활동 이벤트 생성. flush만 수행하므로 commit은 호출자가 담당."""
    obj = ActivityEvent(
        partner_id=partner_id,
        event_type=event_type,
        title=title,
        description=description,
        class_id=class_id,
        student_id=student_id,
        meta=meta or {},
    )
    db.add(obj)
    db.flush()
    return obj


def list_activity_events(
    db: Session,
    *,
    partner_id: int,
    event_type: Optional[str] = None,
    class_id: Optional[int] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[ActivityEvent]:
    """활동 이벤트 목록 조회 (newest-first)."""
    conds = [ActivityEvent.partner_id == partner_id]
    if event_type is not None:
        conds.append(ActivityEvent.event_type == event_type)
    if class_id is not None:
        conds.append(ActivityEvent.class_id == class_id)

    stmt = (
        select(ActivityEvent)
        .where(and_(*conds))
        .order_by(desc(ActivityEvent.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())
