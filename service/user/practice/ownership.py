# service/user/practice/ownership.py
from __future__ import annotations

from typing import Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.practice import PracticeSession, PracticeSessionModel, PracticeResponse

from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
)


# =========================================
# ownership helpers
# =========================================
def ensure_my_session(db: Session, session_id: int, me: AppUser) -> PracticeSession:
    """
    세션이 존재하고, me가 소유자인지 검증.
    """
    session = practice_session_crud.get(db, session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def ensure_my_session_model(
    db: Session,
    session_model_id: int,
    me: AppUser,
) -> Tuple[PracticeSessionModel, PracticeSession]:
    """
    세션 모델이 존재하고, 그 모델이 속한 세션이 me 소유인지 검증.
    """
    model = practice_session_model_crud.get(db, session_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="model not found")

    session = practice_session_crud.get(db, model.session_id)
    if not session or session.user_id != me.user_id:
        # 소유권이 아니면 모델 자체가 없는 것처럼 처리
        raise HTTPException(status_code=404, detail="model not found")

    return model, session


def ensure_my_response(
    db: Session,
    response_id: int,
    me: AppUser,
) -> Tuple[PracticeResponse, PracticeSessionModel, PracticeSession]:
    """
    응답이 존재하고, 응답 → 세션모델 → 세션이 모두 me 소유인지 검증.
    """
    resp = practice_response_crud.get(db, response_id)
    if not resp:
        raise HTTPException(status_code=404, detail="response not found")

    model, session = ensure_my_session_model(db, resp.session_model_id, me)
    return resp, model, session
