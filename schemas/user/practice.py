# schemas/user/practice.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import ConfigDict, Field

from schemas.base import ORMBase
from schemas.enums import StylePreset, ResponseLengthPreset


# =========================================
# generation 옵션 (JSONB로 저장되는 옵션 묶음)
# =========================================
class GenerationParams(ORMBase):
    # JSONB 확장 키(예: presence_penalty 등) 허용
    model_config = ConfigDict(from_attributes=False, extra="allow")

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    response_length_preset: Optional[ResponseLengthPreset] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)


# =========================================
# user.few_shot_examples (개인 라이브러리)
# =========================================
class UserFewShotExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: str
    output_text: str
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    example_id: int
    user_id: int
    title: Optional[str] = None
    input_text: str
    output_text: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =========================================
# user.practice_session_setting_few_shots (매핑)
# =========================================
class PracticeSessionSettingFewShotResponse(ORMBase):
    """
    settings.few_shot_links 로 내려오는 매핑 row
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    setting_id: int
    example_id: int
    sort_order: int
    created_at: datetime

    # relationship: PracticeSessionSettingFewShot.example
    example: Optional[UserFewShotExampleResponse] = None


# =========================================
# user.practice_session_settings
# =========================================
class PracticeSessionSettingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    style_preset: Optional[StylePreset] = None
    style_params: Optional[Dict[str, Any]] = None
    generation_params: Optional[GenerationParams] = None

    # JSON 배열 대신 "선택한 예시 ID들"만 받음 (순서는 리스트 순서로 해석 or 서비스에서 sort_order 처리)
    few_shot_example_ids: Optional[List[int]] = None


class PracticeSessionSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    style_preset: Optional[StylePreset] = None
    style_params: Optional[Dict[str, Any]] = None
    generation_params: Optional[GenerationParams] = None
    few_shot_example_ids: Optional[List[int]] = None


class PracticeSessionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    setting_id: int
    session_id: int

    style_preset: Optional[StylePreset] = None
    style_params: Dict[str, Any] = Field(default_factory=dict)

    # DB(JSONB) 그대로 내려줌
    generation_params: Dict[str, Any] = Field(default_factory=dict)

    # 매핑 테이블 기반
    few_shot_links: List[PracticeSessionSettingFewShotResponse] = Field(default_factory=list)

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

    settings: Optional[PracticeSessionSettingResponse] = None

    prompt_text: Optional[str] = None
    response_text: Optional[str] = None

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
    generation_params: Optional[Dict[str, Any]] = None


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
