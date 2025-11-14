# service/user/practice.py
from __future__ import annotations

from time import perf_counter
from typing import Optional, Any, Dict, Tuple

from sqlalchemy.orm import Session

from models.user.account import AppUser
from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    model_comparison_crud,
)
from schemas.user.practice import (
    PracticeSessionModelUpdate,
    PracticeResponseCreate,
    ModelComparisonCreate,
)


# =========================================
# 세션 내 primary 모델 변경
# =========================================
def set_primary_model_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    target_session_model_id: int,
):
    """
    1) 세션이 내 것인지 검증
    2) 해당 세션의 모든 모델 is_primary = false
    3) target만 is_primary = true
    """
    session = practice_session_crud.get(db, session_id)
    if not session or session.user_id != me.user_id:
        raise PermissionError("session not found or not owned by user")

    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not models:
        raise ValueError("no models for this session")

    target = None
    for m in models:
        if m.session_model_id == target_session_model_id:
            target = m
            m.is_primary = True
        else:
            m.is_primary = False

    if target is None:
        raise ValueError("target model does not belong to this session")

    db.flush()
    # 필요하면 여기서 db.refresh(target) 해서 반환해도 됨
    return target
