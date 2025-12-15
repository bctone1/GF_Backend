# schemas/user/practice.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import ConfigDict, Field

from schemas.base import ORMBase


# =========================================
# 공통: Few-shot 예시
# =========================================
class FewShotExample(ORMBase):
    """
    Few-shot 예시 한 쌍(Q/A)
    - JSONB 배열로 저장됨
    """
    model_config = ConfigDict(from_attributes=False)

    input: str
    output: str


# =========================================
# 공통: generation 옵션
# =========================================
class GenerationParams(ORMBase):
    """
    LLM 생성 옵션
    - DB에서는 JSONB(dict)로 저장
    """
    model_config = ConfigDict(from_attributes=False)

    temperature: Optional[float] = None
    top_p: Optional[float] = None
    response_length_preset: Optional[str] = None  # "short" | "normal" | "long" | "custom"
    max_tokens: Optional[int] = None

    # 모델별 few-shot을 유지하고 싶으면 계속 둬도 됨
    few_shot_examples: Optional[List[FewShotExample]] = None


# =========================================
# user.practice_session_settings
# =========================================
class PracticeSessionSettingCreate(ORMBase):
    """
    보통은 서버가 세션 생성 시 default로 1행 생성하지만,
    필요하면 클라이언트가 초기값을 같이 넣을 수도 있게 Create 제공.
    """
    model_config = ConfigDict(from_attributes=False)

    style_preset: Optional[str] = None
    style_params: Optional[Dict[str, Any]] = None
    generation_params: Optional[GenerationParams] = None
    few_shot_examples: Optional[List[FewShotExample]] = None


class PracticeSessionSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    style_preset: Optional[str] = None
    style_params: Optional[Dict[str, Any]] = None
    generation_params: Optional[GenerationParams] = None
    few_shot_examples: Optional[List[FewShotExample]] = None


class PracticeSessionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    setting_id: int
    session_id: int

    style_preset: Optional[str] = None
    # mutable default 방지
    style_params: Dict[str, Any] = Field(default_factory=dict)

    # DB(JSONB) 그대로 내려주기(프론트가 그대로 쓰기 좋게)
    generation_params: Dict[str, Any] = Field(default_factory=dict)
    few_shot_examples: List[Dict[str, Any]] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


# =========================================
# user.practice_sessions
# =========================================
class PracticeSessionCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None
    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class PracticeSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None
    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class PracticeSessionResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    class_id: Optional[int] = None
    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None

    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None

    # ✅ 세션 공통 settings (GET /sessions/{id}/settings + 세션 상세에서 같이 내려줄 수도 있음)
    settings: Optional[PracticeSessionSettingResponse] = None

    # 편의 필드(카드용)
    prompt_text: Optional[str] = None
    response_text: Optional[str] = None

    # ✅ mutable default 방지
    responses: List["PracticeResponseResponse"] = Field(default_factory=list)


# =========================================
# user.practice_session_models
# =========================================
class PracticeSessionModelCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    model_name: str
    is_primary: Optional[bool] = None
    generation_params: Optional[GenerationParams] = None


class PracticeSessionModelUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    is_primary: Optional[bool] = None
    generation_params: Optional[GenerationParams] = None


class PracticeSessionModelResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    session_id: int
    model_name: str
    is_primary: bool
    generation_params: Optional[Dict[str, Any]] = None  # DB(JSONB) 그대로 내려주기


# =========================================
# user.practice_responses
# =========================================
class PracticeResponseCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    session_model_id: int
    model_name: str
    session_id: int
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
    session_id: int
    model_name: str
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
    user_id: Optional[int] = None
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


# =========================================
# LLM 실행용 /chat 스키마
# =========================================
class PracticeTurnRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    prompt_text: str
    model_names: Optional[list[str]] = Field(
        default=None,
        description="이 세션에서 호출할 논리 모델 이름 목록",
    )
    document_ids: Optional[list[int]] = None
    knowledge_id: Optional[int] = None


class PracticeTurnModelResult(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    model_name: str

    response_id: int
    prompt_text: str
    response_text: str

    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime
    is_primary: Optional[bool] = None

    generation_params: Optional[Dict[str, Any]] = None


class PracticeTurnResponse(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    session_title: Optional[str] = None
    prompt_text: str
    results: List[PracticeTurnModelResult]


# ForwardRef
PracticeSessionResponse.model_rebuild()
