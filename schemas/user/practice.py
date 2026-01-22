# schemas/user/practice.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import ConfigDict, Field, model_validator, field_validator

from schemas.base import ORMBase
from schemas.enums import StylePreset, ResponseLengthPreset


# =========================================
# helpers
# =========================================
def _normalize_int_id_list(v: Optional[List[int]]) -> Optional[List[int]]:
    """
    - None 그대로 유지 (PATCH에서 '미변경' 의미)
    - 중복 제거(입력 순서 유지)
    - None/0/음수 제거
    - str/int 혼용 들어와도 int 캐스팅 시도
    """
    if v is None:
        return None

    seen: set[int] = set()
    out: List[int] = []

    for x in v:
        if x is None:
            continue
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue

        if ix <= 0:
            continue

        if ix not in seen:
            seen.add(ix)
            out.append(ix)

    return out


# =========================================
# generation 옵션 (JSONB로 저장되는 옵션 묶음)
# =========================================
class GenerationParams(ORMBase):
    # JSONB 확장 키(예: presence_penalty 등) 허용
    model_config = ConfigDict(from_attributes=False, extra="allow")

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    response_length_preset: Optional[ResponseLengthPreset] = None

    # 내부 표준은 max_completion_tokens
    max_completion_tokens: Optional[int] = Field(default=None, ge=1)
    # 호환용
    max_tokens: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _sync_token_fields(self) -> "GenerationParams":
        if self.max_completion_tokens is None and self.max_tokens is not None:
            self.max_completion_tokens = self.max_tokens
        if self.max_tokens is None and self.max_completion_tokens is not None:
            self.max_tokens = self.max_completion_tokens
        return self


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

    # JSON 배열 대신 "선택한 예시 ID들"만 받음
    few_shot_example_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def _normalize(self) -> "PracticeSessionSettingCreate":
        self.few_shot_example_ids = _normalize_int_id_list(self.few_shot_example_ids)
        return self


class PracticeSessionSettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    style_preset: Optional[StylePreset] = None
    style_params: Optional[Dict[str, Any]] = None
    generation_params: Optional[GenerationParams] = None
    few_shot_example_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def _normalize(self) -> "PracticeSessionSettingUpdate":
        self.few_shot_example_ids = _normalize_int_id_list(self.few_shot_example_ids)
        return self


class PracticeSessionSettingResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    setting_id: int
    session_id: int

    style_preset: Optional[StylePreset] = None
    style_params: Dict[str, Any] = Field(default_factory=dict)

    # DB(JSONB) 그대로 내려줌
    generation_params: Dict[str, Any] = Field(default_factory=dict)

    # prompt 템플릿 스냅샷(세션 생성 시점 재현성)
    prompt_snapshot: Dict[str, Any] = Field(default_factory=dict)

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
    knowledge_ids: Optional[List[int]] = None

    prompt_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _normalize(self) -> "PracticeSessionCreate":
        self.knowledge_ids = _normalize_int_id_list(self.knowledge_ids)
        return self


class PracticeSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None
    project_id: Optional[int] = None
    knowledge_ids: Optional[List[int]] = None

    prompt_id: Optional[int] = None
    title: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _normalize(self) -> "PracticeSessionUpdate":
        self.knowledge_ids = _normalize_int_id_list(self.knowledge_ids)
        return self


class PracticeSessionResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    class_id: Optional[int] = None
    project_id: Optional[int] = None

    # 항상 list로 내려주기(ORM에서 None 들어와도 안전)
    knowledge_ids: List[int] = Field(default_factory=list)

    prompt_id: Optional[int] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None

    settings: Optional[PracticeSessionSettingResponse] = None
    responses: List["PracticeResponseResponse"] = Field(default_factory=list)

    @field_validator("knowledge_ids", mode="before")
    @classmethod
    def _normalize_knowledge_ids(cls, v: Any) -> List[int]:
        if v is None:
            return []
        if isinstance(v, list):
            normalized = _normalize_int_id_list(v) or []
            return normalized
        # 혹시 단일 int로 들어오는 경우 방어
        try:
            ix = int(v)
        except (TypeError, ValueError):
            return []
        return [ix] if ix > 0 else []


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
    comparison_run_id: Optional[int] = Field(default=None, ge=1)
    panel_key: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


class PracticeResponseUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    prompt_text: Optional[str] = None
    response_text: Optional[str] = None
    comparison_run_id: Optional[int] = Field(default=None, ge=1)
    panel_key: Optional[str] = None
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
    comparison_run_id: Optional[int] = None
    panel_key: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime


# =========================================
# user.practice_comparison_runs
# =========================================
class PracticeComparisonRunCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    prompt_text: str
    panel_a_config: Optional[Dict[str, Any]] = None
    panel_b_config: Optional[Dict[str, Any]] = None


class PracticeComparisonRunUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    prompt_text: Optional[str] = None
    panel_a_config: Optional[Dict[str, Any]] = None
    panel_b_config: Optional[Dict[str, Any]] = None


class PracticeComparisonRunResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    prompt_text: str
    panel_a_config: Dict[str, Any] = Field(default_factory=dict)
    panel_b_config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# =========================================
# LLM 실행용 /chat 스키마 (분리)
# =========================================
class _PracticeTurnBase(ORMBase):
    model_config = ConfigDict(from_attributes=False, extra="forbid")

    prompt_text: str
    model_names: Optional[list[str]] = Field(
        default=None,
        description="이 세션에서 호출할 논리 모델 이름 목록",
    )



class PracticeTurnRequestNewSession(_PracticeTurnBase):
    """
    POST /sessions/run
    - 새 세션 생성 + 첫 턴
    - prompt_id / project_id / knowledge_ids + (settings 튜닝 값들)까지 받는다.
    """
    prompt_id: Optional[int] = Field(default=None, ge=1, json_schema_extra={"example": None})
    project_id: Optional[int] = Field(default=None, ge=1, json_schema_extra={"example": None})

    knowledge_ids: Optional[List[int]] = Field(
        default=None,
        json_schema_extra={"example": None},
        description="새 세션에서만 설정되는 지식베이스 ID 목록",
    )

    style_preset: Optional[StylePreset] = Field(
        default=None,
        description="스타일 프리셋(accurate/balanced/creative/custom 등)",
    )
    style_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="스타일 상세 옵션(형식/persona/힌트모드/self-check 등)",
    )

    generation_params: Optional[GenerationParams] = Field(
        default=None,
        description="LLM 생성 파라미터(temperature/top_p/max_completion_tokens 등)",
    )

    few_shot_example_ids: Optional[List[int]] = Field(
        default=None,
        description="유저 few-shot 라이브러리(example_id)에서 선택한 ID 목록",
    )

    @model_validator(mode="after")
    def _normalize(self) -> "PracticeTurnRequestNewSession":
        self.knowledge_ids = _normalize_int_id_list(self.knowledge_ids)
        self.few_shot_example_ids = _normalize_int_id_list(self.few_shot_example_ids)
        return self



class PracticeTurnRequestExistingSession(_PracticeTurnBase):
    """
    POST /sessions/{session_id}/chat
    - 기존 세션 턴
    - prompt_text / model_names만 받는다. (컨텍스트는 세션 저장값 사용)
    """
    pass


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
