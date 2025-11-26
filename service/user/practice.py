# service/user/practice.py
from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeResponse,
)
from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    model_comparison_crud,
)
from schemas.user.practice import (
    PracticeResponseCreate,
    ModelComparisonCreate,
)
from core import config
from langchain_service.llm.setup import get_llm

import time


# =========================================
# 세션 내 primary 모델 변경
# =========================================
def set_primary_model_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    target_session_model_id: int,
) -> PracticeSessionModel:
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

    target: PracticeSessionModel | None = None
    for m in models:
        if m.session_model_id == target_session_model_id:
            target = m
            m.is_primary = True
        else:
            m.is_primary = False

    if target is None:
        raise ValueError("target model does not belong to this session")

    db.flush()
    return target


# =========================================
# 메트릭 기반 모델 비교 레코드 생성
# =========================================
def create_model_comparison_from_metrics(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    model_a: str,
    model_b: str,
    latency_a_ms: Optional[int],
    latency_b_ms: Optional[int],
    tokens_a: Optional[int],
    tokens_b: Optional[int],
    winner_model: Optional[str] = None,
    user_feedback: Optional[str] = None,
):
    """
    이미 수집된 두 모델의 latency/token 메트릭을 기반으로 model_comparisons 레코드 생성
    """
    session = practice_session_crud.get(db, session_id)
    if not session or session.user_id != me.user_id:
        raise PermissionError("session not found or not owned by user")

    latency_diff_ms: Optional[int] = None
    if latency_a_ms is not None and latency_b_ms is not None:
        latency_diff_ms = abs(latency_a_ms - latency_b_ms)

    token_diff: Optional[int] = None
    if tokens_a is not None and tokens_b is not None:
        token_diff = abs(tokens_a - tokens_b)

    comp_in = ModelComparisonCreate(
        session_id=session_id,
        model_a=model_a,
        model_b=model_b,
        winner_model=winner_model,
        latency_diff_ms=latency_diff_ms,
        token_diff=token_diff,
        user_feedback=user_feedback,
    )

    comp_row = model_comparison_crud.create(db, comp_in)
    # commit 은 바깥에서 처리
    return comp_row


# =========================================
# LLM 호출 헬퍼 (provider/API는 하나, 모델만 변경)
# =========================================
def _call_llm_for_model(
    model_name: str,
    prompt_text: str,
) -> tuple[str, Dict[str, Any] | None, int | None]:
    """
    하나의 모델에 대해 LLM 호출을 수행.
    - 프로바이더/모델 정보는 config.PRACTICE_MODELS 에서 가져옴.
    """
    model_conf = config.PRACTICE_MODELS.get(model_name)
    if model_conf is None or not model_conf.get("enabled", True):
        raise ValueError(f"unsupported or disabled model_name: {model_name}")

    provider = model_conf["provider"]
    real_model_name = model_conf["model_name"]

    # get_llm provider 여부에 따라 선택 (없으면 모델만 받아도됨)
    # 1) provider 지원 버전
    # llm = get_llm(
    #     provider=provider,
    #     model=real_model_name,
    #     streaming=False,
    #     callbacks=None,
    # )

    # 2) 아직 provider 인자 없이 model만 받는 버전:
    llm = get_llm(
        model=real_model_name,
        streaming=False,
        callbacks=None,
    )

    start = time.perf_counter()
    result = llm.invoke(prompt_text)
    end = time.perf_counter()

    latency_ms = int((end - start) * 1000)

    token_usage: Dict[str, Any] | None = None
    usage = getattr(result, "usage_metadata", None)
    if usage:
        token_usage = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    content = getattr(result, "content", None) or str(result)

    return content, token_usage, latency_ms


# =========================================
# 멀티 모델 Practice 턴 실행
# =========================================
def run_practice_turn(
    *,
    db: Session,
    session: PracticeSession,
    models: List[PracticeSessionModel],
    prompt_text: str,
    user: AppUser,
) -> Dict[str, Any]:
    """
    하나의 prompt_text 를 받아 주어진 여러 PracticeSessionModel 에 순차 호출하고
    PracticeResponse 를 생성한 뒤, /chat 응답 스키마(PracticeTurnResponse)에 맞는 dict 를 리턴.

    NOTE (crud.user.practice.PracticeResponseCRUD):
    - 세션/모델 검증은 엔드포인트 + 상위 로직에서 수행
    - 여기서는 LLM 호출 + token_usage/latency 계산
    - practice_response_crud.create() 를 통해 영구 저장
    """
    if session.user_id != user.user_id:
        raise PermissionError("session not owned by user")

    results: List[Dict[str, Any]] = []

    for m in models:
        # 안전 검증: 모델이 해당 세션에 속하는지 확인
        if m.session_id != session.session_id:
            raise ValueError("session_model does not belong to given session")

        response_text, token_usage, latency_ms = _call_llm_for_model(
            model_name=m.model_name,
            prompt_text=prompt_text,
        )

        # DB에 PracticeResponse 생성 (CRUD NOTE 반영)
        resp_in = PracticeResponseCreate(
            session_model_id=m.session_model_id,
            prompt_text=prompt_text,
            response_text=response_text,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )
        resp: PracticeResponse = practice_response_crud.create(db, resp_in)

        results.append(
            {
                "session_model_id": m.session_model_id,
                "model_name": m.model_name,
                "response_id": resp.response_id,
                "prompt_text": resp.prompt_text,
                "response_text": resp.response_text,
                "latency_ms": resp.latency_ms,
                "token_usage": resp.token_usage,
                "created_at": resp.created_at,
            }
        )

    return {
        "session_id": session.session_id,
        "prompt_text": prompt_text,
        "results": results,
    }
