from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core import config
from langchain_service.embedding.get_vector import texts_to_vectors
from langchain_service.llm.runner import generate_session_title_llm, _run_qa
from langchain_service.llm.setup import call_llm_chat

from crud.user.document import document_crud, document_chunk_crud
from crud.user.practice import (
    practice_session_crud,
    practice_session_setting_crud,
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
# 세션 settings 보장(세션당 1개)
# =========================================
def ensure_session_settings(db: Session, *, session_id: int):
    return practice_session_setting_crud.get_or_create_default(db, session_id=session_id)


# =========================================
# 기본 generation params 헬퍼
# =========================================
def _get_default_generation_params() -> Dict[str, Any]:
    base = getattr(config, "PRACTICE_DEFAULT_GENERATION", None)
    if isinstance(base, dict):
        return dict(base)

    return {
        "temperature": 0.7,
        "top_p": 0.9,
        "response_length_preset": "normal",
        "max_tokens": 512,
    }


# =========================================
# 질문 → 벡터 임베딩
# =========================================
def _embed_question_to_vector(question: str) -> list[float]:
    cleaned = (question or "").strip()
    if not cleaned:
        return []

    try:
        vectors = texts_to_vectors([cleaned])
    except Exception:
        return []

    if not vectors:
        return []

    v0 = vectors[0]
    if not isinstance(v0, (list, tuple)):
        return []
    return list(v0)


# =========================================
# 지식베이스 컨텍스트 빌더 (벡터 top-k 기반)
# - document_ids가 "Document PK(id)"든 "knowledge_id"든 둘 다 방어
# =========================================
def _build_context_from_documents(
    db: Session,
    user: AppUser,
    document_ids: List[int],
    question: str,
    max_chunks: int = 10,
) -> str:
    if not document_ids:
        return ""

    query_vector = _embed_question_to_vector(question)
    if not query_vector:
        return ""

    valid_docs: list[Any] = []

    for raw_id in document_ids:
        if raw_id is None:
            continue

        doc = None

        # 1) 우선: knowledge_id로 조회 시도(기존 너 코드 호환)
        try:
            doc = document_crud.get(db, knowledge_id=raw_id)
        except TypeError:
            doc = None
        except Exception:
            doc = None

        # 2) 실패하면: id로 조회 시도(= document PK)
        if doc is None:
            try:
                doc = document_crud.get(db, id=raw_id)
            except TypeError:
                doc = None
            except Exception:
                doc = None

        if not doc:
            continue

        # 소유권 체크(필드명이 프로젝트마다 달라서 안전하게)
        owner_id = (
            getattr(doc, "owner_id", None)
            or getattr(doc, "user_id", None)
            or getattr(doc, "owner_user_id", None)
        )
        if owner_id is not None and owner_id != user.user_id:
            continue

        # 벡터검색 키(보통 knowledge_id)
        kid = getattr(doc, "knowledge_id", None)
        if kid is None:
            # 그래도 없으면 doc 자체를 top-k에 쓰기 어려우니 스킵
            continue

        valid_docs.append(doc)

    if not valid_docs:
        return ""

    per_doc_top_k = max(1, max_chunks // len(valid_docs))

    chunks: list[Any] = []
    for doc in valid_docs:
        kid = getattr(doc, "knowledge_id", None)
        if kid is None:
            continue

        try:
            doc_chunks = document_chunk_crud.search_by_vector(
                db,
                query_vector=query_vector,
                knowledge_id=kid,
                top_k=per_doc_top_k,
            )
        except TypeError:
            # search_by_vector 시그니처가 다를 수도 있어서 최소 방어
            try:
                doc_chunks = document_chunk_crud.search_by_vector(db, query_vector, kid, per_doc_top_k)
            except Exception:
                doc_chunks = []
        except Exception:
            doc_chunks = []

        if doc_chunks:
            chunks.extend(doc_chunks)

    if not chunks:
        return ""

    chunks = chunks[:max_chunks]

    texts: List[str] = []
    for c in chunks:
        chunk_text = (
            getattr(c, "chunk_text", None)
            or getattr(c, "text", None)
            or getattr(c, "content", None)
        )
        if chunk_text:
            texts.append(str(chunk_text))

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


# =========================================
# 세션 내 primary 모델 변경
# =========================================
def set_primary_model_for_session(
    db: Session,
    *,
    me: AppUser | None,
    session_id: int,
    target_session_model_id: int,
) -> PracticeSessionModel:
    session = practice_session_crud.get(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    if me is not None and session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not models:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no models for this session")

    target: PracticeSessionModel | None = None
    for m in models:
        if m.session_model_id == target_session_model_id:
            target = m
            m.is_primary = True
        else:
            m.is_primary = False

    if target is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target model does not belong to this session")

    db.flush()
    return target


def init_models_for_session_from_class(
    db: Session,
    *,
    me: AppUser,
    session: PracticeSession,
    class_id: int,
    requested_model_names: list[str] | None = None,
    generation_overrides: dict[str, dict[str, Any]] | None = None,
) -> list[PracticeSessionModel]:
    existing = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
    if existing:
        if requested_model_names:
            s = set(requested_model_names)
            picked = [m for m in existing if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not found in this session")
            return picked
        return existing

    class_obj = classes_crud.get_class(db, class_id=class_id)
    if not class_obj or class_obj.status != "active":
        raise HTTPException(status_code=400, detail="유효하지 않은 class_id 입니다.")

    model_catalog_ids: list[int] = []
    if class_obj.primary_model_id:
        model_catalog_ids.append(class_obj.primary_model_id)
    if class_obj.allowed_model_ids:
        for mid in class_obj.allowed_model_ids:
            if mid not in model_catalog_ids:
                model_catalog_ids.append(mid)

    if not model_catalog_ids:
        raise HTTPException(status_code=400, detail="이 class 에 설정된 모델이 없습니다.")

    allowed_names: list[str] = []
    for mc_id in model_catalog_ids:
        catalog = db.get(ModelCatalog, mc_id)
        if not catalog:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 model_catalog id: {mc_id}")
        name = getattr(catalog, "logical_name", None) or catalog.model_name
        allowed_names.append(name)

    final_names = allowed_names
    if requested_model_names:
        s = set(requested_model_names)
        final_names = [n for n in allowed_names if n in s]
        if not final_names:
            raise HTTPException(status_code=400, detail="requested model_names not configured for this class")

    overrides = generation_overrides or {}

    created: list[PracticeSessionModel] = []
    for idx, name in enumerate(final_names):
        gp = overrides.get(name) or _get_default_generation_params()
        m = practice_session_model_crud.create(
            db,
            PracticeSessionModelCreate(
                session_id=session.session_id,
                model_name=name,
                is_primary=(idx == 0),
                generation_params=gp,
            ),
        )
        created.append(m)

    db.flush()
    return created


def _call_llm_for_model(
    model_name: str,
    prompt_text: str,
    generation_params: Dict[str, Any] | None = None,
) -> tuple[str, Dict[str, Any] | None, int | None]:
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    model_conf = practice_models.get(model_name) or {}

    provider: str | None = None
    real_model_name: str = model_name

    temperature: float | None = 0.7
    top_p: float | None = 1.0
    max_tokens: int | None = None
    response_length_preset: str | None = None

    if isinstance(model_conf, dict):
        if not model_conf.get("enabled", True):
            raise ValueError(f"unsupported or disabled model_name: {model_name}")

        provider = model_conf.get("provider")
        real_model_name = model_conf.get("model_name", model_name)

        if "temperature" in model_conf:
            temperature = model_conf.get("temperature")
        if "top_p" in model_conf:
            top_p = model_conf.get("top_p")
        mt = model_conf.get("max_output_tokens") or model_conf.get("max_tokens")
        if mt is not None:
            max_tokens = mt

    default_gen = getattr(config, "PRACTICE_DEFAULT_GENERATION", {}) or {}
    response_length_preset = default_gen.get("response_length_preset", "normal")

    base_params: Dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "response_length_preset": response_length_preset,
    }
    for k, v in default_gen.items():
        if v is not None:
            base_params[k] = v

    gp: Dict[str, Any] = generation_params if isinstance(generation_params, dict) else {}
    effective: Dict[str, Any] = {**base_params, **gp}

    length_presets: Dict[str, int] = getattr(config, "RESPONSE_LENGTH_PRESETS", {}) or {}
    preset = effective.get("response_length_preset")

    if preset in length_presets and preset != "custom":
        effective["max_tokens"] = length_presets[preset]
    elif preset == "custom":
        if effective.get("max_tokens") is None:
            if "max_tokens" in default_gen and default_gen["max_tokens"] is not None:
                effective["max_tokens"] = default_gen["max_tokens"]
    else:
        if effective.get("max_tokens") is not None:
            effective["response_length_preset"] = "custom"

    final_temperature = effective.get("temperature", 0.7)
    final_top_p = effective.get("top_p", 1.0)
    final_max_tokens = effective.get("max_tokens")

    messages: list[dict[str, str]] = []

    few_shot_raw = gp.get("few_shot_examples") if isinstance(gp, dict) else None
    if isinstance(few_shot_raw, list):
        for ex in few_shot_raw:
            if isinstance(ex, dict):
                input_text = (ex.get("input") or "").strip()
                output_text = (ex.get("output") or "").strip()
            else:
                input_text = (getattr(ex, "input", "") or "").strip()
                output_text = (getattr(ex, "output", "") or "").strip()

            if input_text:
                messages.append({"role": "user", "content": input_text})
            if output_text:
                messages.append({"role": "assistant", "content": output_text})

    messages.append({"role": "user", "content": prompt_text})

    llm_result = call_llm_chat(
        messages=messages,
        provider=provider,
        model=real_model_name,
        temperature=final_temperature,
        max_tokens=final_max_tokens,
        top_p=final_top_p,
    )

    return llm_result.text, llm_result.token_usage, llm_result.latency_ms


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
    document_ids: Optional[List[int]] = None,
) -> PracticeTurnResponse:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="session not owned by user")

    settings = ensure_session_settings(db, session_id=session.session_id)
    session_base_gen = getattr(settings, "generation_params", None) or {}
    session_few_shots = getattr(settings, "few_shot_examples", None) or []

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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_model does not belong to given session")

        full_prompt = f"{context_text}\n\n질문: {prompt_text}" if context_text else prompt_text

        model_gp = getattr(m, "generation_params", None) or {}
        effective_gp: Dict[str, Any] = {**session_base_gen, **model_gp}

        if not effective_gp.get("few_shot_examples") and session_few_shots:
            effective_gp["few_shot_examples"] = session_few_shots

        response_text, token_usage, latency_ms = _call_llm_for_model(
            model_name=m.model_name,
            prompt_text=full_prompt,
            generation_params=effective_gp,
        )

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
                generation_params=effective_gp,
            )
        )

    if not session.title and results:
        primary = next((r for r in results if r.is_primary), results[0])
        title = generate_session_title_llm(
            question=prompt_text,
            answer=primary.response_text,
            max_chars=30,
        )
        practice_session_crud.update(db, session_id=session.session_id, data=PracticeSessionUpdate(title=title))
        session.title = title

    return PracticeTurnResponse(
        session_id=session.session_id,
        session_title=session.title,
        prompt_text=prompt_text,
        results=results,
    )


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
    session = practice_session_crud.create(
        db,
        data=PracticeSessionCreate(
            class_id=None,
            project_id=None,
            title=None,
            notes=None,
        ),
        user_id=user.user_id,
    )

    ensure_session_settings(db, session_id=session.session_id)

    session_model = practice_session_model_crud.create(
        db,
        PracticeSessionModelCreate(
            session_id=session.session_id,
            model_name=model_name,
            is_primary=True,
            generation_params=_get_default_generation_params(),
        ),
    )

    qa = _run_qa(
        db,
        question=prompt_text,
        knowledge_id=knowledge_id,
        top_k=3,
        session_id=None,
    )

    response = practice_response_crud.create(
        db,
        PracticeResponseCreate(
            session_model_id=session_model.session_model_id,
            session_id=session.session_id,
            model_name=model_name,
            prompt_text=prompt_text,
            response_text=qa.answer,
            token_usage=None,
            latency_ms=None,
        ),
    )

    title = generate_session_title_llm(prompt_text, qa.answer)
    session = practice_session_crud.update(
        db,
        session_id=session.session_id,
        data=PracticeSessionUpdate(title=title),
    )

    return session, response


def _select_models_for_existing_session(
    db: Session,
    *,
    session: PracticeSession,
    body: PracticeTurnRequest,
    me: AppUser,
    class_id: int | None = None,
) -> List[PracticeSessionModel]:
    if session.class_id is None:
        raise HTTPException(status_code=400, detail="session has no class_id")

    if class_id is not None and session.class_id != class_id:
        raise HTTPException(status_code=400, detail="class_id does not match this session")

    all_models = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
    if not all_models:
        raise HTTPException(status_code=400, detail="no models configured for this session")

    if body.model_names:
        s = set(body.model_names)
        picked = [m for m in all_models if m.model_name in s]
        if not picked:
            raise HTTPException(status_code=400, detail="requested model_names not found in this session")
        return picked

    return all_models


def run_practice_turn_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    class_id: int | None,
    body: PracticeTurnRequest,
    project_id: Optional[int] = None,
) -> PracticeTurnResponse:
    if session_id == 0:
        if class_id is None:
            raise HTTPException(status_code=400, detail="class_id_required")

        session = practice_session_crud.create(
            db,
            data=PracticeSessionCreate(
                class_id=class_id,
                project_id=project_id,
                title=None,
                notes=None,
            ),
            user_id=me.user_id,
        )

        ensure_session_settings(db, session_id=session.session_id)

        created_models = init_models_for_session_from_class(
            db,
            me=me,
            session=session,
            class_id=class_id,
            requested_model_names=None,
            generation_overrides=None,
        )

        models = created_models
        if body.model_names:
            s = set(body.model_names)
            models = [m for m in created_models if m.model_name in s]
            if not models:
                raise HTTPException(status_code=400, detail="requested model_names not configured for this class")

    else:
        session = ensure_my_session(db, session_id, me)
        ensure_session_settings(db, session_id=session.session_id)

        models = _select_models_for_existing_session(
            db,
            session=session,
            body=body,
            me=me,
            class_id=class_id,
        )

        if project_id is not None and session.project_id is not None and session.project_id != project_id:
            raise HTTPException(status_code=400, detail="요청한 project_id와 세션의 project_id가 일치하지 않습니다.")

    return run_practice_turn(
        db=db,
        session=session,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        document_ids=body.document_ids,
    )
