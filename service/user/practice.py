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
from crud.user.document import (
    document_crud,
    document_chunk_crud,
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
from langchain_service.embedding.get_vector import texts_to_vectors
import time


# =========================================
# 질문 → 벡터 임베딩 헬퍼
# =========================================
def _embed_question_to_vector(question: str) -> list[float]:
    """
    질문 텍스트를 pgvector용 벡터(list[float])로 변환.
    인제스트 때와 동일한 임베딩 모델(texts_to_vectors) 사용.
    """
    cleaned = (question or "").strip()
    if not cleaned:
        return []

    vectors = texts_to_vectors([cleaned])  # 인제스트 때랑 동일한 함수
    if not vectors:
        return []

    return vectors[0]


# =========================================
# 지식베이스 컨텍스트 빌더 (벡터 top-k 기반)
# =========================================
def _build_context_from_documents(
    db: Session,
    user: AppUser,
    document_ids: List[int],
    question: str,
    max_chunks: int = 10,
) -> str:
    """
    선택한 document_ids 기준으로:
    - 내 소유 문서인지 검증
    - 질문을 임베딩해서 pgvector 코사인 거리 기반 top-k 청크 검색
    - 상위 청크들을 하나의 컨텍스트 텍스트로 합침
    """
    if not document_ids:
        return ""

    # 1) 문서 소유권 체크
    valid_docs = []
    for doc_id in document_ids:
        doc = document_crud.get(db, knowledge_id=doc_id)
        if not doc or doc.owner_id != user.user_id:
            # 내 문서가 아니면 스킵 (원하면 여기서 HTTPException으로 바꿀 수도 있음)
            continue
        valid_docs.append(doc)

    if not valid_docs:
        return ""

    # 2) 질문을 벡터로 임베딩
    query_vector = _embed_question_to_vector(question)

    # 3) 각 문서별로 벡터 검색(top-k) 실행
    chunks: List = []
    # 문서 수에 따라 per-doc top_k 분배 (최소 1개는 보장)
    per_doc_top_k = max(1, max_chunks // len(valid_docs))

    for doc in valid_docs:
        doc_chunks = document_chunk_crud.search_by_vector(
            db,
            query_vector=query_vector,
            knowledge_id=doc.knowledge_id,
            top_k=per_doc_top_k,
        )
        chunks.extend(doc_chunks)

    # 혹시 너무 많이 모이면 max_chunks까지만 사용
    chunks = chunks[:max_chunks]

    # 4) 컨텐츠 텍스트 합치기
    texts: List[str] = []
    for c in chunks:
        # DocumentChunk 모델의 텍스트 필드명에 맞게 사용 (여기는 chunk_text)
        chunk_text = getattr(c, "chunk_text", None)
        if chunk_text:
            texts.append(chunk_text)

    if not texts:
        return ""

    context_body = "\n\n".join(texts)

    # 최종 컨텍스트 프롬프트
    return (
        "다음은 사용자가 업로드한 참고 문서 중에서, "
        "질문과 가장 관련도가 높은 일부 발췌 내용입니다.\n\n"
        f"{context_body}\n\n"
        "위 내용을 참고해서 아래 질문에 답변해 주세요."
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
# 첫 턴에서 세션 생성 + 자동 타이틀 (단일 모델 + knowledge_id 기반 RAG)
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
    models: List[PracticeSessionModel],
    prompt_text: str,
    user: AppUser,
    document_ids: Optional[List[int]] = None,
) -> PracticeTurnResponse:
    """
    - 선택된 지식베이스의 벡터 top-k 청크를 컨텍스트로 붙여서
      각 모델에 LLM 호출
    - PracticeResponse 레코드 생성
    - 세션에 title 없으면 자동 생성하여 업데이트
    """
    if session.user_id != user.user_id:
        raise PermissionError("session not owned by user")

    # 0) 지식베이스 컨텍스트 구성
    context_text = ""
    if document_ids:
        context_text = _build_context_from_documents(
            db=db,
            user=user,
            document_ids=document_ids,
            question=prompt_text,
        )

    results: List[PracticeTurnModelResult] = []

    for m in models:
        if m.session_id != session.session_id:
            raise ValueError("session_model does not belong to given session")

        # 1) 실제 LLM에 보낼 프롬프트 만들기
        if context_text:
            full_prompt = (
                f"{context_text}\n\n"
                f"질문: {prompt_text}"
            )
        else:
            full_prompt = prompt_text

        # 2) LLM 호출
        response_text, token_usage, latency_ms = _call_llm_for_model(
            model_name=m.model_name,
            prompt_text=full_prompt,
        )

        # 3) 응답 저장 (DB에는 원래 질문만 저장)
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

        # 4) 응답 DTO 생성
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

    # 5) 세션 제목이 아직 없으면 → 첫 턴 기준으로 자동 생성
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

    # 6) 클라이언트로 돌려줄 DTO
    return PracticeTurnResponse(
        session_id=session.session_id,
        session_title=session.title,
        prompt_text=prompt_text,
        results=results,
    )
