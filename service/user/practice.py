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
    PracticeSessionCreate,
    PracticeSessionModelCreate,
    PracticeSessionUpdate,
    PracticeTurnModelResult,
    PracticeTurnResponse,
)
from core import config
from langchain_service.llm.setup import get_llm
from langchain_service.llm.runner import generate_session_title_llm, _run_qa
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

    # provider 인자가 필요한 버전이면 provider도 넘겨주면 됨
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
# 첫 턴에서 세션 생성 + 자동 타이틀
# =========================================
def create_session_with_first_turn(
    db: Session,
    *,
    user: AppUser,
    model_name: str,
    prompt_text: str,
    knowledge_id: int | None = None,
) -> tuple[PracticeSession, PracticeResponse]:
    # 1) 세션 생성
    session = practice_session_crud.create(
        db,
        PracticeSessionCreate(
            user_id=user.user_id,
            title=None,
            notes=None,
        ),
    )

    # 2) 세션-모델 연결
    session_model = practice_session_model_crud.create(
        db,
        PracticeSessionModelCreate(
            session_id=session.session_id,
            model_name=model_name,
            is_primary=True,
        ),
    )

    # 3) LLM 호출 (RAG or 일반 QA)
    qa = _run_qa(
        db,
        question=prompt_text,
        knowledge_id=knowledge_id,
        top_k=3,
        session_id=None,  # 필요하면 세션 연동
    )

    # 4) 응답 저장
    response = practice_response_crud.create(
        db,
        PracticeResponseCreate(
            session_model_id=session_model.session_model_id,
            prompt_text=prompt_text,
            response_text=qa.answer,
            token_usage=None,   # 나중에 runner에서 토큰정보 넘겨받으면 채우기
            latency_ms=None,
        ),
    )

    # 5) 제목 자동 생성 + 업데이트
    title = generate_session_title_llm(prompt_text, qa.answer)
    session = practice_session_crud.update(
        db,
        session_id=session.session_id,
        data=PracticeSessionUpdate(title=title),
    )

    return session, response


# =========================================
# 멀티 모델 Practice 턴 실행 (/sessions/{session_id}/chat)
# =========================================
def run_practice_turn(
    *,
    db: Session,
    session: PracticeSession,
    models: list[PracticeSessionModel],
    prompt_text: str,
    user: AppUser,
) -> PracticeTurnResponse:
    """
    - 각 모델에 LLM 호출
    - PracticeResponse 레코드 생성
    - 세션에 title 없으면 자동 생성하여 업데이트
    """
    if session.user_id != user.user_id:
        raise PermissionError("session not owned by user")

    results: list[PracticeTurnModelResult] = []

    for m in models:
        if m.session_id != session.session_id:
            raise ValueError("session_model does not belong to given session")

        # 1) LLM 호출
        response_text, token_usage, latency_ms = _call_llm_for_model(
            model_name=m.model_name,
            prompt_text=prompt_text,
        )

        # 2) 응답 저장
        resp = practice_response_crud.create(
            db,
            PracticeResponseCreate(
                session_model_id=m.session_model_id,
                prompt_text=prompt_text,
                response_text=response_text,
                token_usage=token_usage,
                latency_ms=latency_ms,
            ),
        )

        # 3) 응답 DTO 생성
        results.append(
            PracticeTurnModelResult(
                session_model_id=m.session_model_id,
                model_name=m.model_name,
                response_id=resp.response_id,
                prompt_text=resp.prompt_text,
                response_text=resp.response_text,
                token_usage=resp.token_usage,
                latency_ms=resp.latency_ms,
                created_at=resp.created_at,
                is_primary=m.is_primary,
            )
        )

    # 4) 세션 제목이 아직 없으면 → 첫 턴 기준으로 자동 생성
    if not session.title and results:
        primary = next((r for r in results if r.is_primary), results[0])
        title = generate_session_title_llm(
            question=prompt_text,
            answer=primary.response_text,
            max_chars=30,
        )

        practice_session_crud.update(
            db,
            session_id=session.session_id,
            data=PracticeSessionUpdate(title=title),
        )
        session.title = title  # in-memory 도 같이 반영

    # 5) 클라이언트로 돌려줄 DTO
    return PracticeTurnResponse(
        session_id=session.session_id,
        session_title=session.title,
        prompt_text=prompt_text,
        results=results,
    )
