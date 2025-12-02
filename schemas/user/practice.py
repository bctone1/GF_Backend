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
    # 요청 바디에서는 user_id를 받지 않고, 엔드포인트에서 me.user_id로 채움
    user_id: Optional[int] = None
    class_id: Optional[int] = None  # 어떤 class 에서 시작된 실습인지 연결용
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
    class_id: Optional[int] = None
    title: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


# =========================================
# user.practice_session_models
# =========================================
class PracticeSessionModelCreate(ORMBase):
    """
    한 세션에서 사용할 단일 모델 추가용.

    - model_catalog_id: partner.model_catalog.id (반드시 카탈로그에 존재해야 함)
    - model_name: 요청에서는 생략 가능, 서버에서 ModelCatalog 를 보고 채우는 용도
    """
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    model_catalog_id: int  # 카탈로그 기준으로 필수
    model_name: Optional[str] = None
    is_primary: Optional[bool] = None  # server default false


class PracticeSessionModelUpdate(ORMBase):
    """
    세션 모델 설정 업데이트.

    - 모델 자체는 바꾸지 않고(is_primary만 수정)
    """
    model_config = ConfigDict(from_attributes=False)

    is_primary: Optional[bool] = None


class PracticeSessionModelResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    model_catalog_id: Optional[int] = None
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
    - model_catalog_id:
        * session_id == 0 인 새 세션 시작 시,
          카탈로그 기준으로 특정 모델 한 개만 골라서 시작하고 싶을 때 사용
        * 기존 세션(session_id > 0)에서는 보통 사용하지 않음
    - session_model_ids:
        * 이미 세션에 등록된 모델들 중 일부만 대상으로 돌리고 싶을 때 사용
        * None 이면 세션에 등록된 모든 모델 대상
    - document_ids:
        * 선택한 문서들 (RAG 컨텍스트로 사용할 문서 id 리스트)
    """
    model_config = ConfigDict(from_attributes=False)

    prompt_text: str
    model_catalog_id: Optional[int] = None
    session_model_ids: Optional[list[int]] = None
    document_ids: Optional[list[int]] = None  # 내가 선택한 문서들


class PracticeTurnModelResult(ORMBase):
    """
    한 모델에 대해 한 번 실행한 결과
    """
    # DB에서 바로 model_validate 할 수도 있으니 from_attributes=True 로
    model_config = ConfigDict(from_attributes=True)

    session_model_id: int
    model_catalog_id: Optional[int] = None
    model_name: str

    response_id: int
    prompt_text: str
    response_text: str

    token_usage: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    created_at: datetime
    is_primary: Optional[bool] = None  # 필요 없으면 제거 가능


class PracticeTurnResponse(ORMBase):
    """
    한 프롬프트에 대해 여러 모델을 실행한 결과 묶음
    """
    model_config = ConfigDict(from_attributes=False)

    session_id: int
    session_title: Optional[str] = None  # 자동 요약 타이틀
    prompt_text: str
    results: list[PracticeTurnModelResult]
