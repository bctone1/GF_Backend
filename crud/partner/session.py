# crud/partner/session.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.session import AiSession, SessionMessage


# ==============================
# AiSession CRUD
# ==============================

def get_session(db: Session, session_id: int) -> Optional[AiSession]:
    """
    단일 세션 조회.
    """
    return db.get(AiSession, session_id)


def list_sessions(
    db: Session,
    *,
    student_id: Optional[int] = None,
    class_id: Optional[int] = None,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[AiSession], int]:
    """
    세션 목록 조회 + total 카운트 (페이지네이션).
    endpoint 쪽에서 AiSessionPage 로 감싸서 리턴하면 됨.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if student_id is not None:
        filters.append(AiSession.student_id == student_id)
    if class_id is not None:
        filters.append(AiSession.class_id == class_id)
    if status is not None:
        filters.append(AiSession.status == status)
    if mode is not None:
        filters.append(AiSession.mode == mode)

    base_stmt: Select[AiSession] = select(AiSession)
    if filters:
        base_stmt = base_stmt.where(*filters)

    # total
    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    # items
    stmt = (
        base_stmt.order_by(AiSession.started_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_session(
    db: Session,
    *,
    data: Dict[str, Any],
) -> AiSession:
    """
    세션 생성.
    - 일반적으로 endpoint 에서 AiSessionCreate.model_dump(exclude_unset=True) 를 넘겨주면 됨.
    """
    obj = AiSession(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_session(
    db: Session,
    *,
    session: AiSession,
    data: Dict[str, Any],
) -> AiSession:
    """
    세션 업데이트.
    - endpoint: AiSessionUpdate.model_dump(exclude_unset=True) 를 data 로 전달.
    """
    for key, value in data.items():
        setattr(session, key, value)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def finalize_session(
    db: Session,
    *,
    session: AiSession,
    status: str,
    ended_at: Optional[Any] = None,
) -> AiSession:
    """
    세션 종료/상태 변경용 헬퍼.
    - status: 'completed' | 'canceled' | 'error' 등
    """
    session.status = status
    if ended_at is not None:
        session.ended_at = ended_at
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(
    db: Session,
    *,
    session: AiSession,
) -> None:
    """
    세션 삭제 (메시지는 cascade 로 함께 삭제).
    """
    db.delete(session)
    db.commit()


# ==============================
# SessionMessage CRUD
# ==============================

def get_message(db: Session, message_id: int) -> Optional[SessionMessage]:
    return db.get(SessionMessage, message_id)


def list_messages(
    db: Session,
    *,
    session_id: int,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[SessionMessage], int]:
    """
    특정 세션의 메시지 목록 (시간순 정렬).
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    base_stmt: Select[SessionMessage] = select(SessionMessage).where(
        SessionMessage.session_id == session_id
    )

    # total
    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    # items
    stmt = (
        base_stmt.order_by(SessionMessage.created_at.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_message(
    db: Session,
    *,
    data: Dict[str, Any],
    update_session_stats: bool = True,
) -> SessionMessage:
    """
    메시지 생성.
    - endpoint: SessionMessageCreate.model_dump(exclude_unset=True) 를 data 로 전달.
    - update_session_stats=True 이면 AiSession.total_messages / total_tokens 업데이트.
    """
    obj = SessionMessage(**data)
    db.add(obj)

    if update_session_stats:
        session = db.get(AiSession, data["session_id"])
        if session is not None:
            # total_messages 증가
            session.total_messages = (session.total_messages or 0) + 1
            # tokens 합산
            tokens = data.get("tokens")
            if tokens is not None:
                session.total_tokens = (session.total_tokens or 0) + int(tokens)
            db.add(session)

    db.commit()
    db.refresh(obj)
    return obj


def update_message(
    db: Session,
    *,
    message: SessionMessage,
    data: Dict[str, Any],
) -> SessionMessage:
    """
    메시지 내용/메타 수정 (토큰/레이턴시 등).
    - 토큰 수정 시 세션 total_tokens 를 같이 보정하고 싶으면
      별도 헬퍼를 추가해서 사용하는 게 안전함 (동시성 이슈 방지).
    """
    for key, value in data.items():
        setattr(message, key, value)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def delete_message(
    db: Session,
    *,
    message: SessionMessage,
) -> None:
    db.delete(message)
    db.commit()
