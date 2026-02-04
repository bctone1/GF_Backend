# service/user/activity.py
"""Activity tracking helpers.

Thin wrappers around activity CRUD that swallow exceptions so
tracking failures never break the main business logic.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from sqlalchemy import select, func, exists

from crud.user.activity import activity_event_crud, practice_feature_stat_crud
from models.user.activity import UserActivityEvent
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeResponse,
)
from models.user.comparison import PracticeComparisonRun
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


def backfill_session_metadata(
    db: Session,
    *,
    user_id: int,
    class_id: Optional[int] = None,
) -> int:
    """기존 practice_session 이벤트의 meta를 세션 현재 데이터로 보강.

    Args:
        db: Active DB session (caller manages commit).
        user_id: 대상 사용자.
        class_id: 특정 강의로 범위 제한 (optional).

    Returns:
        갱신된 이벤트 건수.
    """
    # 1) 해당 유저의 practice_session 관련 이벤트 조회
    filters = [
        UserActivityEvent.user_id == user_id,
        UserActivityEvent.related_type == "practice_session",
        UserActivityEvent.related_id.is_not(None),
    ]
    events = db.scalars(
        select(UserActivityEvent).where(*filters)
    ).all()

    if not events:
        return 0

    # 2) session_id 목록 수집 (중복 제거)
    session_ids = list({e.related_id for e in events if e.related_id is not None})

    # 3) 세션 데이터 배치 조회
    sessions = db.scalars(
        select(PracticeSession).where(PracticeSession.session_id.in_(session_ids))
    ).all()

    # class_id 필터가 있으면 해당 class의 세션만 보강
    if class_id is not None:
        sessions = [s for s in sessions if s.class_id == class_id]

    session_map: dict[int, PracticeSession] = {s.session_id: s for s in sessions}

    if not session_map:
        return 0

    # 4) 세션별 부가 정보 조회: primary_model, model_names, turn_count, is_compare
    s_ids = list(session_map.keys())

    # model names per session
    model_rows = db.execute(
        select(
            PracticeSessionModel.session_id,
            PracticeSessionModel.model_name,
            PracticeSessionModel.is_primary,
        ).where(PracticeSessionModel.session_id.in_(s_ids))
    ).all()

    session_models: dict[int, list[str]] = {}
    session_primary: dict[int, Optional[str]] = {}
    for row in model_rows:
        sid = row.session_id
        session_models.setdefault(sid, []).append(row.model_name)
        if row.is_primary:
            session_primary[sid] = row.model_name

    # turn count per session
    turn_rows = db.execute(
        select(
            PracticeResponse.session_id,
            func.count(PracticeResponse.response_id).label("cnt"),
        )
        .where(PracticeResponse.session_id.in_(s_ids))
        .group_by(PracticeResponse.session_id)
    ).all()
    turn_counts: dict[int, int] = {r.session_id: r.cnt for r in turn_rows}

    # is_compare per session
    compare_rows = db.execute(
        select(PracticeComparisonRun.session_id)
        .where(PracticeComparisonRun.session_id.in_(s_ids))
        .distinct()
    ).all()
    compare_set: set[int] = {r.session_id for r in compare_rows}

    # 5) 이벤트별 meta merge
    updates: list[tuple[int, dict[str, Any]]] = []
    for event in events:
        sid = event.related_id
        if sid is None or sid not in session_map:
            continue

        sess = session_map[sid]
        k_ids = getattr(sess, "knowledge_ids", None) or []

        new_meta: dict[str, Any] = {
            "session_title": sess.title,
            "primary_model_name": session_primary.get(sid),
            "model_names": session_models.get(sid, []),
            "is_compare_mode": sid in compare_set,
            "has_knowledge_base": bool(k_ids),
            "turn_count": turn_counts.get(sid, 0),
        }
        updates.append((event.event_id, new_meta))

    # 6) bulk update
    count = activity_event_crud.bulk_update_meta(db, updates)
    return count
