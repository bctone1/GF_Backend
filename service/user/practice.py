# service/user/practice.py
from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
import time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import config
from langchain_service.embedding.get_vector import texts_to_vectors
from langchain_service.llm.runner import generate_session_title_llm, _run_qa
from langchain_service.llm.setup import get_llm

from crud.user.document import document_crud, document_chunk_crud
from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    practice_rating_crud,
    model_comparison_crud,
)
from crud.partner import classes as classes_crud

from models.user.account import AppUser
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeResponse,
)
from models.partner.course import Class as PartnerClass
from models.partner.catalog import ModelCatalog

from schemas.user.practice import (
    PracticeResponseCreate,
    ModelComparisonCreate,
    PracticeSessionCreate,
    PracticeSessionModelCreate,
    PracticeSessionUpdate,
    PracticeTurnModelResult,
    PracticeTurnRequest,
    PracticeTurnResponse,
)


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

    vectors = texts_to_vectors([cleaned])
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
        chunk_text = getattr(c, "chunk_text", None)
        if chunk_text:
            texts.append(chunk_text)

    if not texts:
        return ""

    context_body = "\n\n".join(texts)

    return (
        "다음은 사용자가 업로드한 참고 문서 중에서, "
        "질문과 가장 관련도가 높은 일부 발췌 내용입니다.\n\n"
        f"{context_body}\n\n"
        "위 내용을 참고해서 아래 질문에 답변해 주세요."
    )


# =========================================
# 공통 ensure_* 헬퍼 (소유권 검증)
# =========================================
def ensure_my_session(db: Session, session_id: int, me: AppUser) -> PracticeSession:
    session = practice_session_crud.get(db, session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


def ensure_my_session_model(
    db: Session,
    session_model_id: int,
    me: AppUser,
) -> Tuple[PracticeSessionModel, PracticeSession]:
    model = practice_session_model_crud.get(db, session_model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")

    session = practice_session_crud.get(db, model.session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")

    return model, session


def ensure_my_response(db: Session, response_id: int, me: AppUser):
    resp = practice_response_crud.get(db, response_id)
    if not resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response not found")
    model, session = ensure_my_session_model(db, resp.session_model_id, me)
    return resp, model, session


def ensure_my_rating(db: Session, rating_id: int, me: AppUser):
    rating = practice_rating_crud.get(db, rating_id)
    if not rating or rating.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rating not found")
    return rating


def ensure_my_comparison(db: Session, comparison_id: int, me: AppUser):
    comp = model_comparison_crud.get(db, comparison_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison not found")
    session = practice_session_crud.get(db, comp.session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison not found")
    return comp, session


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models for this session",
        )

    target: PracticeSessionModel | None = None
    for m in models:
        if m.session_model_id == target_session_model_id:
            target = m
            m.is_primary = True
        else:
            m.is_primary = False

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target model does not belong to this session",
        )

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

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
# LLM 연결/모델 해석 유틸
# =========================================
def resolve_models_for_class(
    db: Session,
    class_id: int,
) -> tuple[PartnerClass, list[ModelCatalog]]:
    clazz = (
        db.execute(select(PartnerClass).where(PartnerClass.id == class_id))
        .scalar_one_or_none()
    )
    if not clazz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="class not found")

    allowed_ids: list[int] = clazz.allowed_model_ids or []
    if not allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 강의에 설정된 모델이 없습니다.",
        )

    rows = (
        db.execute(
            select(ModelCatalog).where(
                ModelCatalog.id.in_(allowed_ids),
                ModelCatalog.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효한 모델이 없습니다.",
        )

    return clazz, rows


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

    provider = model_conf.get("provider", "openai")
    real_model_name = model_conf["model_name"]

    llm = get_llm(
        provider=provider,
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
# 세션 + 첫 턴 생성 (단일 모델/RAG)
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
        session_id=None,
    )

    # 4) 응답 저장
    response = practice_response_crud.create(
        db,
        PracticeResponseCreate(
            session_model_id=session_model.session_model_id,
            session_id=session.session_id,
            model_name=model_name,
            prompt_text=prompt_text,
            response_text=qa.answer,
            token_usage=None,  # runner에서 토큰정보 넘겨받으면 채우기
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
# 멀티 모델 Practice 턴 실행 (저수준, 세션/모델 확정 이후)
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="session not owned by user",
        )

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_model does not belong to given session",
            )

        # 1) 실제 LLM에 보낼 프롬프트 만들기
        if context_text:
            full_prompt = f"{context_text}\n\n질문: {prompt_text}"
        else:
            full_prompt = prompt_text

        # 2) LLM 호출
        response_text, token_usage, latency_ms = _call_llm_for_model(
            model_name=m.model_name,
            prompt_text=full_prompt,
        )

        # 3) 응답 저장
        resp = practice_response_crud.create(
            db,
            PracticeResponseCreate(
                session_model_id=m.session_model_id,
                session_id=session.session_id,
                model_name=m.model_name,
                prompt_text=prompt_text,
                response_text=response_text,
                token_usage=token_usage,
                latency_ms=latency_ms,
            ),
        )

        # 4) 클라이언트 응답용 DTO
        results.append(
            PracticeTurnModelResult(
                session_model_id=resp.session_model_id,
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
        session.title = title

    # 6) 최종 응답
    return PracticeTurnResponse(
        session_id=session.session_id,
        session_title=session.title,
        prompt_text=prompt_text,
        results=results,
    )


# =========================================
# /sessions/{session_id}/chat 유즈케이스
# =========================================
def _init_session_and_models_from_class(
    db: Session,
    *,
    me: AppUser,
    class_id: int,
    body: PracticeTurnRequest,
) -> tuple[PracticeSession, List[PracticeSessionModel]]:
    """
    session_id == 0 인 경우:
    - 새 practice_session 생성
    - class LLM 설정 기반으로 practice_session_models 생성
    - 이번 턴에 쓸 모델 리스트 리턴
    """
    # 새 practice_session 생성
    session = practice_session_crud.create(
        db,
        PracticeSessionCreate(
            user_id=me.user_id,
            class_id=class_id,
            title=None,
            notes=None,
        ),
    )

    # class 설정에서 사용할 모델 목록 가져오기
    class_obj = classes_crud.get_class(db, class_id=class_id)
    if not class_obj or class_obj.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 class_id 입니다.",
        )

    # class 에 설정된 model_catalog id 목록 수집
    model_catalog_ids: list[int] = []
    if class_obj.primary_model_id:
        model_catalog_ids.append(class_obj.primary_model_id)

    if class_obj.allowed_model_ids:
        for mid in class_obj.allowed_model_ids:
            if mid not in model_catalog_ids:
                model_catalog_ids.append(mid)

    if not model_catalog_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 class 에 설정된 모델이 없습니다. 강의 설정에서 모델을 추가하세요.",
        )

    # catalog → logical_name/model_name 매핑
    all_model_names: list[str] = []
    for mc_id in model_catalog_ids:
        catalog = db.get(ModelCatalog, mc_id)
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 model_catalog id: {mc_id}",
            )

        logical_name = getattr(catalog, "logical_name", None)
        name = logical_name or catalog.model_name
        all_model_names.append(name)

    # 세션-모델 레코드 생성 (첫 번째만 is_primary=True)
    created_models: list[PracticeSessionModel] = []
    for idx, name in enumerate(all_model_names):
        m = practice_session_model_crud.create(
            db,
            PracticeSessionModelCreate(
                session_id=session.session_id,
                model_name=name,
                is_primary=(idx == 0),
            ),
        )
        created_models.append(m)

    # 이번 턴에 실제로 호출할 모델 선택
    if body.model_names:
        requested_names = set(body.model_names)
        models = [m for m in created_models if m.model_name in requested_names]
        if not models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="requested model_names not configured for this class",
            )
    else:
        models = created_models

    return session, models


def _select_models_for_existing_session(
    db: Session,
    *,
    session: PracticeSession,
    class_id: int,
    body: PracticeTurnRequest,
    me: AppUser,
) -> List[PracticeSessionModel]:
    """
    session_id > 0 인 경우:
    - 세션 ↔ class 바인딩 검증
    - 세션에 등록된 모델 중에서 model_names / session_model_ids 로 필터링
    """
    # 세션 ↔ class_id 바인딩 검증
    if session.class_id is None:
        session.class_id = class_id
        db.add(session)
        db.commit()
    elif session.class_id != class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="class_id does not match this session",
        )

    # 이 세션에 등록된 모든 모델 먼저 가져오기
    all_models: list[PracticeSessionModel] = practice_session_model_crud.list_by_session(
        db,
        session_id=session.session_id,
    )
    if not all_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models configured for this session",
        )

    # 1순위: model_names
    if body.model_names:
        requested_names = set(body.model_names)
        models = [m for m in all_models if m.model_name in requested_names]

        if not models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="requested model_names not found in this session",
            )

    # 2순위: session_model_ids
    elif body.session_model_ids:
        requested_ids = {
            sm_id
            for sm_id in body.session_model_ids or []
            if isinstance(sm_id, int) and sm_id > 0
        }

        if requested_ids:
            id_to_model = {m.session_model_id: m for m in all_models}
            models = [
                id_to_model[sm_id]
                for sm_id in requested_ids
                if sm_id in id_to_model
            ]
            if not models:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="requested session_model_ids not found in this session",
                )
        else:
            models = all_models

    # 3순위: 아무 것도 안 보냈으면 전체
    else:
        models = all_models

    return models


def run_practice_turn_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    class_id: int,
    body: PracticeTurnRequest,
) -> PracticeTurnResponse:
    """
    엔드포인트에서 바로 호출할 유즈케이스 함수.
    - session_id == 0 → 새 세션 + class 기반 모델 구성
    - session_id > 0 → 기존 세션 + 모델 선택
    - 마지막에 run_practice_turn 호출
    """
    if session_id == 0:
        session, models = _init_session_and_models_from_class(
            db,
            me=me,
            class_id=class_id,
            body=body,
        )
    else:
        session = ensure_my_session(db, session_id, me)
        models = _select_models_for_existing_session(
            db,
            session=session,
            class_id=class_id,
            body=body,
            me=me,
        )

    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models configured for this session",
        )

    return run_practice_turn(
        db=db,
        session=session,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        document_ids=body.document_ids,
    )
