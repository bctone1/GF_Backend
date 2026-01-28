# service/user/practice/ids.py
from __future__ import annotations

from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.user.practice import PracticeSession, PracticeResponse


def coerce_int_list(value: Any) -> list[int]:
    """
    - None -> []
    - list 아니면 []
    - 원소를 int로 캐스팅 시도, 1 이상만 유지
    - 중복 제거(입력 순서 유지)
    """
    if value is None or not isinstance(value, list):
        return []

    out: list[int] = []
    for x in value:
        if x is None:
            continue
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue
        if ix > 0:
            out.append(ix)

    seen: set[int] = set()
    uniq: list[int] = []
    for ix in out:
        if ix not in seen:
            seen.add(ix)
            uniq.append(ix)

    return uniq


def get_session_knowledge_ids(session: PracticeSession) -> list[int]:
    """
    ORM이 knowledge_id(단일)일 수도, knowledge_ids(리스트)일 수도 있어서 안전하게 흡수.
    """
    kids = getattr(session, "knowledge_ids", None)
    if isinstance(kids, list):
        return coerce_int_list(kids)

    kid = getattr(session, "knowledge_id", None)
    if kid is None:
        return []
    try:
        ik = int(kid)
    except (TypeError, ValueError):
        return []
    return [ik] if ik > 0 else []


def get_session_prompt_ids(session: PracticeSession) -> list[int]:
    """
    ORM에서 prompt_ids(JSONB list)를 안전하게 흡수.
    """
    pids = getattr(session, "prompt_ids", None)
    if isinstance(pids, list):
        return coerce_int_list(pids)
    return []


def has_any_response(db: Session, *, session_id: int) -> bool:
    stmt = select(func.count(PracticeResponse.response_id)).where(PracticeResponse.session_id == session_id)
    return (db.scalar(stmt) or 0) > 0
