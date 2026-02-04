# service/user/activity.py
"""Activity tracking helpers.

Thin wrappers around activity CRUD that swallow exceptions so
tracking failures never break the main business logic.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from crud.user.activity import activity_event_crud, practice_feature_stat_crud
from schemas.user.activity import UserActivityEventCreate

logger = logging.getLogger(__name__)


def track_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a user activity event.

    Args:
        db: Active DB session (caller manages commit).
        user_id: The acting user.
        event_type: e.g. ``session_created``, ``document_uploaded``.
        related_type: Entity kind (``practice_session``, ``document``, ...).
        related_id: PK of the related entity.
        metadata: Optional extra payload stored as JSONB.
    """
    try:
        activity_event_crud.create(
            db,
            data=UserActivityEventCreate(
                user_id=user_id,
                event_type=event_type,
                related_type=related_type,
                related_id=related_id,
                metadata=metadata,
            ),
        )
    except Exception:
        logger.warning(
            "track_event failed: user_id=%s event_type=%s",
            user_id,
            event_type,
            exc_info=True,
        )


def track_feature(
    db: Session,
    *,
    user_id: int,
    class_id: Optional[int],
    feature_type: str,
    increment: int = 1,
) -> None:
    """Increment a practice-feature usage counter.

    Args:
        db: Active DB session (caller manages commit).
        user_id: The acting user.
        class_id: Associated class (nullable for personal practice).
        feature_type: One of ``parameter_tuned``, ``fewshot_used``,
            ``file_attached``, ``kb_connected``.
        increment: How many uses to add (default 1).
    """
    try:
        practice_feature_stat_crud.upsert(
            db,
            user_id=user_id,
            class_id=class_id,
            feature_type=feature_type,
            increment=increment,
        )
    except Exception:
        logger.warning(
            "track_feature failed: user_id=%s feature_type=%s",
            user_id,
            feature_type,
            exc_info=True,
        )

