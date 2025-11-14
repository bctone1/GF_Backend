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

# 두 모델 비교
def run_practice_turn(
    db: Session,
    *,
    me: AppUser,
    session_model_id: int,
    prompt_text: str,
    llm_callable,  # langchain Runnable 이나 get_llm()이 반환한 객체
    llm_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, PracticeResponseCreate]:
    """
    연습 한 턴 실행:
    - 세션/모델 소유자 검증
    - LLM 호출
    - latency 측정 및 (임시) token_usage 구성
    - PracticeResponseCreate 스키마 리턴 (또는 바로 CRUD 호출까지)
    """
    model = practice_session_model_crud.get(db, session_model_id)
    if not model:
        raise ValueError("session model not found")

    session = practice_session_crud.get(db, model.session_id)
    if not session or session.user_id != me.user_id:
        raise PermissionError("session not found or not owned by user")

    # 실제 LLM 호출 (여기 부분은 프로젝트에 맞게 바꿔 쓰면 됨)
    t0 = perf_counter()

    # 예시: LangChain Runnable 이라고 가정
    # result = llm_callable.invoke({"question": prompt_text})
    result = llm_callable(prompt_text)  # NOTE : 실제 시그니처에 맞게 수정
    latency_ms = int((perf_counter() - t0) * 1000)

    # NOTE : 토큰 집계 시스템 붙이면 여기에서 token_usage 채우기
    token_usage: Dict[str, Any] = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "meta": llm_meta or {},
    }

    resp_in = PracticeResponseCreate(
        session_model_id=session_model_id,
        prompt_text=prompt_text,
        response_text=str(result),
        token_usage=token_usage,
        latency_ms=latency_ms,
    )

    # 여기서 바로 저장까지 할지, 호출하는 쪽에서 CRUD 호출할지는 선택
    response_row = practice_response_crud.create(db, resp_in)
    # 트랜잭션은 바깥에서 commit
    return result, response_row



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
    # commit 역시 바깥에서
    return comp_row
