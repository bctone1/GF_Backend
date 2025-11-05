# schemas/user/practice.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import ConfigDict
from schemas.base import ORMBase


# =========================================
# user.practice_sessions
# =========================================
class PracticeSessionCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    title: Optional[str] = None
    notes: Optional[str] = None


class PracticeSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    title: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class PracticeSessionResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    session_id: int
    user_id: int
    title: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


# =========================================
# user.practice_session_models
# =========================================
class PracticeSessionModelCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    session_id: int
    model_name: str
    is_primary: Optional[bool] = None  # server default false


class PracticeSessionModelUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    model_name: Optional[str] = None
    is_primary: Optional[bool] = None


class PracticeSessionModelResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    session_model_id: int
    session_id: int
    model_name: str
    is_primary: bool


# =========================================
# user.practice_responses
# =========================================
class PracticeResponseCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    session_model_id: int
    prompt_text: str
    response_text: str
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


class PracticeResponseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    prompt_text: Optional[str] = None
    response_text: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


class PracticeResponseResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    response_id: int
    session_model_id: int
    prompt_text: str
    response_text: str
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime


# =========================================
# user.practice_ratings
# =========================================
class PracticeRatingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    response_id: int
    user_id: int
    score: int
    feedback: Optional[str] = None


class PracticeRatingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    score: Optional[int] = None
    feedback: Optional[str] = None


class PracticeRatingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    rating_id: int
    response_id: int
    user_id: int
    score: int
    feedback: Optional[str] = None
    created_at: datetime


# =========================================
# user.model_comparisons
# =========================================
class ModelComparisonCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    session_id: int
    model_a: str
    model_b: str
    winner_model: Optional[str] = None
    latency_diff_ms: Optional[int] = None
    token_diff: Optional[int] = None
    user_feedback: Optional[str] = None


class ModelComparisonUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    winner_model: Optional[str] = None
    latency_diff_ms: Optional[int] = None
    token_diff: Optional[int] = None
    user_feedback: Optional[str] = None


class ModelComparisonResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    comparison_id: int
    session_id: int
    model_a: str
    model_b: str
    winner_model: Optional[str] = None
    latency_diff_ms: Optional[int] = None
    token_diff: Optional[int] = None
    user_feedback: Optional[str] = None
    created_at: datetime
