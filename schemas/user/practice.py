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
    Few-shot 예시 한 쌍(Q/A).
    - generation_params JSONB 안에 배열로 들어감.
    """
    # from_attributes 필요 없으니까 False 로 둬도 되고,
    model_config = ConfigDict(from_attributes=False)

    input: str   # 예시 질문
    output: str  # 예시 답변

# =========================================
# 공통: 세션-모델 generation 옵션
# =========================================
class GenerationParams(ORMBase):
    """
    세션 모델별 LLM 생성 옵션.
    - DB에서는 JSONB로 저장되고, API에서는 이 구조로 주고받음.
    """
    model_config = ConfigDict(from_attributes=False)

    temperature: Optional[float] = None
    top_p: Optional[float] = None
    response_length_preset: Optional[str] = None  # "short" | "normal" | "long" | "custom"
    max_tokens: Optional[int] = None

    few_shot_examples: Optional[List[FewShotExample]] = None


# =========================================
# user.practice_sessions
# =========================================
class PracticeSessionCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None          # 어떤 class 에서 시작된 실습인지 연결용
    project_id: Optional[int] = None        # 어떤 프로젝트(폴더)에 속한 세션인지
    title: Optional[str] = None
    notes: Optional[str] = None


class PracticeSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: Optional[int] = None
    project_id: Optional[int] = None        # 프로젝트 이동/해제할 때 사용 가능
    title: Optional[str] = None
    notes: Optional[str] = None


class PracticeSessionResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    class_id: Optional[int] = None
    project_id: Optional[int] = None

    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None

    # 편의를 위해 마지막 프롬프트/응답 한 쌍을 세션 레벨에서 보여줄 때 사용
    prompt_text: Optional[str] = None
    response_text: Optional[str] = None

    # 자세한 턴 목록
    responses: List["PracticeResponseResponse"] = []


# =========================================
# user.practice_session_models
# =========================================
class PracticeSessionModelCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    model_name: str
    is_primary: Optional[bool] = None  # server default false
    # ★ 추가: 생성 옵션(없으면 서버에서 default 채움)
    generation_params: Optional[GenerationParams] = None


class PracticeSessionModelUpdate(ORMBase):
    """
    세션 모델 설정 업데이트.

    - 모델 자체는 바꾸지 않고(is_primary만 수정)
    - generation_params 는 옵션 변경용(PATCH /options 에서 사용 가능)
    """
    model_config = ConfigDict(from_attributes=False)

    is_primary: Optional[bool] = None
    generation_params: Optional[GenerationParams] = None


class PracticeSessionModelResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    session_id: int
    model_name: str
    is_primary: bool
    # ★ 추가: 현재 세션-모델에 설정된 LLM 생성 옵션
    generation_params: Optional[GenerationParams] = None


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
    # model_name 은 보통 수정 안 해도 되니까 굳이 안 넣어도 됨


class PracticeResponseResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    response_id: int
    session_model_id: int
    session_id: int          # NEW: FK 붙인 컬럼까지 응답에 포함
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
    # 요청 바디에서는 user_id를 받지 않고, 엔드포인트에서 me.user_id로 채움
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
    # 지금은 문자열 기준으로 비교 저장 (예: "gpt-4o-mini" vs "upstage-...").
    # 나중에 필요하면 session_model_id / model_catalog_id 기준으로 확장 가능.
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
    """
    /sessions/{session_id}/chat 요청 바디

    - prompt_text: 사용자가 입력한 프롬프트
    - model_names:
        * 새 세션 시작 시, 특정 모델들만 선택해서 돌리고 싶을 때
    - document_ids:
        * 선택한 문서들 (RAG 컨텍스트로 사용할 문서 id 리스트)
    """
    model_config = ConfigDict(from_attributes=False)

    prompt_text: str
    model_names: Optional[list[str]] = Field(
        None,
        description="이 세션에서 호출할 논리 모델 이름 목록 (예: ['gpt-4o-mini', 'gpt-5-nano'])",
    )
    document_ids: Optional[list[int]] = None  # 내가 선택한 문서들


class PracticeTurnModelResult(ORMBase):
    """
    한 모델에 대해 한 번 실행한 결과
    """
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    model_name: str

    response_id: int
    prompt_text: str
    response_text: str

    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime
    is_primary: Optional[bool] = None  # 필요 없으면 제거 가능

    # 프론트에서 받게 이 턴에서 사용된 LLM 생성 파라미터 쏴주기
    generation_params: Optional[GenerationParams] = None


class PracticeTurnResponse(ORMBase):
    """
    한 프롬프트에 대해 여러 모델을 실행한 결과 묶음
    """
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    session_title: Optional[str] = None  # 자동 요약 타이틀
    prompt_text: str
    results: List[PracticeTurnModelResult]


# ForwardRef 해결
PracticeSessionResponse.model_rebuild()
