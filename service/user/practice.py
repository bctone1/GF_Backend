# service/user/practice.py
from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from core import config
from langchain_service.embedding.get_vector import texts_to_vectors
from langchain_service.llm.runner import generate_session_title_llm
from langchain_service.llm.setup import call_llm_chat
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from crud.user.document import document_crud, document_chunk_crud
from crud.user.practice import (
    practice_session_crud,
    practice_session_setting_crud,
    practice_session_model_crud,
    practice_response_crud,
)
from crud.partner import classes as classes_crud

from models.user.account import AppUser
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeSessionSetting,
    PracticeSessionSettingFewShot,
    UserFewShotExample,
    PracticeResponse,
)
from models.partner.catalog import ModelCatalog

from schemas.user.practice import (
    PracticeResponseCreate,
    PracticeSessionCreate,
    PracticeSessionModelCreate,
    PracticeSessionUpdate,
    PracticeTurnModelResult,
    PracticeTurnRequestNewSession,
    PracticeTurnRequestExistingSession,
    PracticeTurnResponse,
)


# =========================================
# helpers
# =========================================
def _coerce_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for x in value:
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue
        if ix > 0:
            out.append(ix)
    # 중복 제거(입력 순서 유지)
    seen: set[int] = set()
    uniq: list[int] = []
    for ix in out:
        if ix not in seen:
            seen.add(ix)
            uniq.append(ix)
    return uniq


def _get_session_knowledge_ids(session: PracticeSession) -> list[int]:
    """
    ORM이 아직 knowledge_id(단일)일 수도, knowledge_ids(리스트)일 수도 있어서 안전하게 흡수.
    """
    kids = getattr(session, "knowledge_ids", None)
    if isinstance(kids, list):
        return _coerce_int_list(kids)

    kid = getattr(session, "knowledge_id", None)
    if kid is None:
        return []
    try:
        ik = int(kid)
    except (TypeError, ValueError):
        return []
    return [ik] if ik > 0 else []


# =========================================
# generation params 정규화 (max_completion_tokens 기준)
# - DB/서비스 전반 키 혼용 방지
# =========================================
def _normalize_generation_params_dict(v: Any) -> Dict[str, Any]:
    if not isinstance(v, dict):
        return {}

    out = dict(v)
    mct = out.get("max_completion_tokens")
    mt = out.get("max_tokens")
    mot = out.get("max_output_tokens")

    # max_output_tokens 들어오면 승격
    if mct is None and isinstance(mot, int) and mot > 0:
        out["max_completion_tokens"] = mot
        out["max_tokens"] = mot
        return out

    # max_tokens만 들어오면 승격
    if mct is None and isinstance(mt, int) and mt > 0:
        out["max_completion_tokens"] = mt
        out["max_tokens"] = mt
        return out

    # max_completion_tokens만 있으면 max_tokens도 채움
    if mt is None and isinstance(mct, int) and mct > 0:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct
        return out

    # 둘 다 있고 다르면 max_completion_tokens 우선
    if isinstance(mct, int) and mct > 0 and isinstance(mt, int) and mt > 0 and mct != mt:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct

    return out


# =========================================
# 세션 settings 보장(세션당 1개)
# =========================================
def ensure_session_settings(db: Session, *, session_id: int) -> PracticeSessionSetting:
    default_gen = _get_default_generation_params()
    return practice_session_setting_crud.get_or_create_default(
        db,
        session_id=session_id,
        default_generation_params=default_gen,
    )


# =========================================
# 기본 generation params 헬퍼
# =========================================
def _get_default_generation_params() -> Dict[str, Any]:
    base = getattr(config, "PRACTICE_DEFAULT_GENERATION", None)
    if isinstance(base, dict):
        return _normalize_generation_params_dict(dict(base))

    return _normalize_generation_params_dict(
        {
            "temperature": 0.7,
            "top_p": 0.9,
            "response_length_preset": None,
            "max_completion_tokens": 1024,
        }
    )


def _is_enabled_runtime_model(model_key: str) -> bool:
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    conf = practice_models.get(model_key)
    return isinstance(conf, dict) and conf.get("enabled") is True


def _has_any_response(db: Session, *, session_id: int) -> bool:
    stmt = select(func.count(PracticeResponse.response_id)).where(PracticeResponse.session_id == session_id)
    return (db.scalar(stmt) or 0) > 0


# =========================================
# settings에 선택된 few-shot 예시 로드
# =========================================
def _load_selected_few_shots_for_setting(
    db: Session,
    *,
    setting_id: int,
    me: AppUser,
) -> List[Dict[str, Any]]:
    stmt = (
        select(
            UserFewShotExample.input_text,
            UserFewShotExample.output_text,
            UserFewShotExample.meta,
        )
        .join(
            PracticeSessionSettingFewShot,
            PracticeSessionSettingFewShot.example_id == UserFewShotExample.example_id,
        )
        .where(PracticeSessionSettingFewShot.setting_id == setting_id)
        .where(UserFewShotExample.user_id == me.user_id)
        .where(UserFewShotExample.is_active.is_(True))
        .order_by(PracticeSessionSettingFewShot.sort_order.asc())
    )
    rows = db.execute(stmt).all()

    out: List[Dict[str, Any]] = []
    for input_text, output_text, meta in rows:
        it = (input_text or "").strip()
        ot = (output_text or "").strip()
        if it and ot:
            out.append({"input": it, "output": ot, "meta": meta or {}})
    return out


# =========================================
# few-shot meta에서 rule -> system_prompt 생성
# =========================================
def _derive_system_prompt_from_few_shots(few_shots: Any) -> Optional[str]:
    if not isinstance(few_shots, list) or not few_shots:
        return None

    first = few_shots[0]
    if not isinstance(first, dict):
        return None

    meta = first.get("meta")
    if not isinstance(meta, dict):
        return None

    ap = meta.get("additionalProp1")
    if not isinstance(ap, dict):
        return None

    rule = ap.get("rule")
    if not isinstance(rule, str) or not rule.strip():
        return None

    r = rule.strip()
    return (
        "아래 규칙을 반드시 지켜라.\n"
        f"- {r}\n"
        "규칙 외의 불필요한 설명은 하지 마라."
    )


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
# 지식베이스(knowledge_ids) 컨텍스트 빌더
# =========================================
def _build_context_from_knowledges(
    db: Session,
    user: AppUser,
    knowledge_ids: List[int],
    question: str,
    max_chunks: int = 10,
) -> str:
    knowledge_ids = _coerce_int_list(knowledge_ids)
    if not knowledge_ids:
        return ""

    query_vector = _embed_question_to_vector(question)
    if not query_vector:
        return ""

    valid_docs: list[Any] = []

    for kid in knowledge_ids:
        try:
            doc = document_crud.get(db, knowledge_id=kid)
        except Exception:
            doc = None

        if not doc:
            continue

        owner_id = (
            getattr(doc, "owner_id", None)
            or getattr(doc, "user_id", None)
            or getattr(doc, "owner_user_id", None)
        )
        if owner_id is not None and owner_id != user.user_id:
            continue

        real_kid = getattr(doc, "knowledge_id", None)
        if real_kid is None:
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
        raise HTTPException(status_code=404, detail="session not found")
    return session


def ensure_my_session_model(
    db: Session,
    session_model_id: int,
    me: AppUser,
) -> Tuple[PracticeSessionModel, PracticeSession]:
    model = practice_session_model_crud.get(db, session_model_id)
    if not model:
        raise HTTPException(status_code=404, detail="model not found")

    session = practice_session_crud.get(db, model.session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=404, detail="model not found")

    return model, session


def ensure_my_response(db: Session, response_id: int, me: AppUser):
    resp = practice_response_crud.get(db, response_id)
    if not resp:
        raise HTTPException(status_code=404, detail="response not found")
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
        raise HTTPException(status_code=404, detail="session not found")

    if me is not None and session.user_id != me.user_id:
        raise HTTPException(status_code=404, detail="session not found")

    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not models:
        raise HTTPException(status_code=400, detail="no models for this session")

    target: PracticeSessionModel | None = None
    for m in models:
        if m.session_model_id == target_session_model_id:
            target = m
            m.is_primary = True
        else:
            m.is_primary = False

    if target is None:
        raise HTTPException(status_code=400, detail="target model does not belong to this session")

    db.flush()
    return target


# =========================================
# class 설정 기반 모델 생성/동기화
# =========================================
def init_models_for_session_from_class(
    db: Session,
    *,
    me: AppUser,
    session: PracticeSession,
    class_id: int,
    requested_model_names: list[str] | None = None,
    base_generation_params: dict[str, Any] | None = None,
    generation_overrides: dict[str, dict[str, Any]] | None = None,
    sync_existing: bool = True,
) -> list[PracticeSessionModel]:
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
    seen: set[str] = set()
    for mc_id in model_catalog_ids:
        catalog = db.get(ModelCatalog, mc_id)
        if not catalog:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 model_catalog id: {mc_id}")
        name = getattr(catalog, "logical_name", None) or catalog.model_name
        if name not in seen:
            seen.add(name)
            allowed_names.append(name)

    for name in allowed_names:
        if not _is_enabled_runtime_model(name):
            raise HTTPException(status_code=400, detail=f"model_not_enabled_in_runtime_config: {name}")

    desired_names = allowed_names
    if requested_model_names:
        s = set(requested_model_names)
        desired_names = [n for n in allowed_names if n in s]
        if not desired_names:
            raise HTTPException(status_code=400, detail="requested model_names not configured for this class")

    base_gen = _normalize_generation_params_dict(dict(base_generation_params or _get_default_generation_params()))
    overrides = generation_overrides or {}

    existing = practice_session_model_crud.list_by_session(db, session_id=session.session_id)

    if existing and sync_existing:
        has_resp = _has_any_response(db, session_id=session.session_id)
        desired_set = set(desired_names)

        if not has_resp:
            for m in existing:
                if m.model_name not in desired_set:
                    practice_session_model_crud.delete(db, session_model_id=m.session_model_id)

        existing_after = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
        existing_names_after = {m.model_name for m in existing_after}

        for name in desired_names:
            if name in existing_names_after:
                continue

            gp = dict(base_gen)
            ov = overrides.get(name)
            if isinstance(ov, dict):
                gp.update(ov)
            gp = _normalize_generation_params_dict(gp)

            practice_session_model_crud.create(
                db,
                PracticeSessionModelCreate(
                    session_id=session.session_id,
                    model_name=name,
                    is_primary=False,
                    generation_params=gp,
                ),
            )

        final_models = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
        primary_name = desired_names[0] if desired_names else None
        for m in final_models:
            m.is_primary = (m.model_name == primary_name)

        db.flush()

        if requested_model_names:
            s = set(requested_model_names)
            picked = [m for m in final_models if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not found in this session")
            return picked

        return final_models

    if existing:
        if requested_model_names:
            s = set(requested_model_names)
            picked = [m for m in existing if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not found in this session")
            return picked
        return list(existing)

    created: list[PracticeSessionModel] = []
    for idx, name in enumerate(desired_names):
        gp = dict(base_gen)
        ov = overrides.get(name)
        if isinstance(ov, dict):
            gp.update(ov)
        gp = _normalize_generation_params_dict(gp)

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
    conf_max_tokens: int | None = None

    if isinstance(model_conf, dict):
        if not model_conf.get("enabled", True):
            raise ValueError(f"unsupported or disabled model_name: {model_name}")

        provider = model_conf.get("provider")
        real_model_name = model_conf.get("model_name", model_name)

        if "temperature" in model_conf:
            temperature = model_conf.get("temperature")
        if "top_p" in model_conf:
            top_p = model_conf.get("top_p")

        mt = model_conf.get("max_output_tokens") or model_conf.get("max_completion_tokens") or model_conf.get("max_tokens")
        if isinstance(mt, int) and mt > 0:
            conf_max_tokens = mt

    default_gen = _normalize_generation_params_dict(getattr(config, "PRACTICE_DEFAULT_GENERATION", {}) or {})
    length_presets: Dict[str, int] = getattr(config, "RESPONSE_LENGTH_PRESETS", {}) or {}

    base_params: Dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "response_length_preset": default_gen.get("response_length_preset", None),
    }
    for k, v in default_gen.items():
        if v is not None:
            base_params[k] = v

    if conf_max_tokens is not None:
        base_params["max_completion_tokens"] = conf_max_tokens
        base_params["max_tokens"] = conf_max_tokens

    gp: Dict[str, Any] = generation_params if isinstance(generation_params, dict) else {}
    effective: Dict[str, Any] = _normalize_generation_params_dict({**base_params, **gp})

    preset = effective.get("response_length_preset")
    if preset in length_presets and preset != "custom":
        mt2 = int(length_presets[preset])
        effective["max_completion_tokens"] = mt2
        effective["max_tokens"] = mt2
    elif preset == "custom":
        effective = _normalize_generation_params_dict(effective)
    else:
        if effective.get("max_completion_tokens") is not None:
            effective["response_length_preset"] = "custom"

    final_temperature = effective.get("temperature", 0.7)
    final_top_p = effective.get("top_p", 1.0)
    final_max_tokens = effective.get("max_completion_tokens") or effective.get("max_tokens")

    # ---- 여기부터 Runnable로 구성 ----
    sys_prompt = effective.get("system_prompt")
    sys_prompt = sys_prompt.strip() if isinstance(sys_prompt, str) and sys_prompt.strip() else ""

    # few-shot 정규화(list[dict])로 통일
    fs_list: list[dict[str, str]] = []
    few_shot_raw = effective.get("few_shot_examples")
    if isinstance(few_shot_raw, list):
        for ex in few_shot_raw:
            if isinstance(ex, dict):
                it = (ex.get("input") or "").strip()
                ot = (ex.get("output") or "").strip()
            else:
                it = (getattr(ex, "input", "") or "").strip()
                ot = (getattr(ex, "output", "") or "").strip()
            fs_list.append({"input": it, "output": ot})

    def _build_messages(x: dict) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if sys_prompt:
            msgs.append({"role": "system", "content": sys_prompt})

        for ex in fs_list:
            it = (ex.get("input") or "").strip()
            ot = (ex.get("output") or "").strip()
            if it:
                msgs.append({"role": "user", "content": it})
            if ot:
                msgs.append({"role": "assistant", "content": ot})

        msgs.append({"role": "user", "content": str(x.get("prompt_text", "") or "")})
        return msgs

    def _call(messages: list[dict[str, str]]):
        return call_llm_chat(
            messages=messages,
            provider=provider,
            model=real_model_name,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            top_p=final_top_p,
        )

    def _normalize(res) -> tuple[str, Dict[str, Any] | None, int | None]:
        return (
            str(getattr(res, "text", "") or ""),
            getattr(res, "token_usage", None),
            getattr(res, "latency_ms", None),
        )

    chain = (
        RunnablePassthrough.assign(prompt_text=lambda x: x.get("prompt_text"))
        | RunnableLambda(_build_messages)
        | RunnableLambda(_call)
        | RunnableLambda(_normalize)
    )

    response_text, token_usage, latency_ms = chain.invoke({"prompt_text": prompt_text})
    return response_text, token_usage, latency_ms



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
    knowledge_ids: Optional[List[int]] = None,
) -> PracticeTurnResponse:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")

    settings = ensure_session_settings(db, session_id=session.session_id)
    session_base_gen = _normalize_generation_params_dict(getattr(settings, "generation_params", None) or {})

    agent_snapshot = getattr(settings, "agent_snapshot", None) or {}
    agent_gen = agent_snapshot.get("generation_params") if isinstance(agent_snapshot, dict) else {}
    agent_gen = _normalize_generation_params_dict(agent_gen) if isinstance(agent_gen, dict) else {}

    selected_few_shots = _load_selected_few_shots_for_setting(
        db,
        setting_id=settings.setting_id,
        me=user,
    )

    context_text = ""
    kids = _coerce_int_list(knowledge_ids)
    if kids:
        context_text = _build_context_from_knowledges(
            db=db,
            user=user,
            knowledge_ids=kids,
            question=prompt_text,
        )

    results: List[PracticeTurnModelResult] = []

    for m in models:
        if m.session_id != session.session_id:
            raise HTTPException(status_code=400, detail="session_model does not belong to given session")

        full_prompt = f"{context_text}\n\n질문: {prompt_text}" if context_text else prompt_text

        model_gp = _normalize_generation_params_dict(getattr(m, "generation_params", None) or {})

        # 우선순위: settings(base) -> agent_snapshot(gen) -> model(gen)
        effective_gp: Dict[str, Any] = _normalize_generation_params_dict({**session_base_gen, **agent_gen, **model_gp})

        # agent_snapshot의 system_prompt/few_shot_examples는 "없을 때만" 주입
        if isinstance(agent_snapshot, dict):
            for k in ("system_prompt", "few_shot_examples"):
                if k in agent_snapshot and not effective_gp.get(k):
                    effective_gp[k] = agent_snapshot.get(k)

        # 모델이 직접 few_shot_examples를 안 갖고 있으면 settings 선택분 주입
        if not effective_gp.get("few_shot_examples") and selected_few_shots:
            effective_gp["few_shot_examples"] = selected_few_shots

        # few-shot meta(rule) -> system_prompt로 강제
        sys_from_fs = _derive_system_prompt_from_few_shots(effective_gp.get("few_shot_examples"))
        if sys_from_fs:
            prev = effective_gp.get("system_prompt")
            if isinstance(prev, str) and prev.strip():
                effective_gp["system_prompt"] = prev.strip() + "\n\n" + sys_from_fs
            else:
                effective_gp["system_prompt"] = sys_from_fs

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
        practice_session_crud.update(
            db,
            session_id=session.session_id,
            data=PracticeSessionUpdate(title=title),
        )
        session.title = title

    return PracticeTurnResponse(
        session_id=session.session_id,
        session_title=session.title,
        prompt_text=prompt_text,
        results=results,
    )


def _select_models_for_existing_session(
    db: Session,
    *,
    session: PracticeSession,
    body: PracticeTurnRequestExistingSession,
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

    return list(all_models)


def run_practice_turn_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    class_id: int | None,
    body: PracticeTurnRequestNewSession | PracticeTurnRequestExistingSession,
    project_id: Optional[int] = None,
) -> PracticeTurnResponse:
    """
    - session_id == 0  : 새 세션 생성 + 첫 턴 (body에 agent/project/knowledge 허용)
    - session_id > 0   : 기존 세션 턴 (body는 prompt/model_names만, 컨텍스트는 세션 저장값 사용)
    """
    if session_id == 0:
        if class_id is None:
            raise HTTPException(status_code=400, detail="class_id_required")

        if not isinstance(body, PracticeTurnRequestNewSession):
            # 방어: 라우팅/타이핑 실수 방지
            raise HTTPException(status_code=400, detail="invalid_body_for_new_session")

        requested_project_id = project_id if project_id is not None else body.project_id
        requested_knowledge_ids = _coerce_int_list(body.knowledge_ids)
        requested_agent_id = body.agent_id

        session = practice_session_crud.create(
            db,
            data=PracticeSessionCreate(
                class_id=class_id,
                project_id=requested_project_id,
                knowledge_ids=requested_knowledge_ids,
                agent_id=requested_agent_id,
                title=None,
                notes=None,
            ),
            user_id=me.user_id,
        )

        settings = ensure_session_settings(db, session_id=session.session_id)
        base_gen = _normalize_generation_params_dict(
            getattr(settings, "generation_params", None) or _get_default_generation_params()
        )

        models = init_models_for_session_from_class(
            db,
            me=me,
            session=session,
            class_id=class_id,
            requested_model_names=None,
            base_generation_params=base_gen,
            generation_overrides=None,
            sync_existing=True,
        )

        if body.model_names:
            s = set(body.model_names)
            picked = [m for m in models if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not configured for this class")
            models = picked

        ctx_knowledge_ids = _get_session_knowledge_ids(session)

    else:
        if not isinstance(body, PracticeTurnRequestExistingSession):
            # 방어: 라우팅/타이핑 실수 방지
            raise HTTPException(status_code=400, detail="invalid_body_for_existing_session")

        session = ensure_my_session(db, session_id, me)
        settings = ensure_session_settings(db, session_id=session.session_id)

        if session.class_id is None:
            raise HTTPException(status_code=400, detail="session has no class_id")

        base_gen = _normalize_generation_params_dict(
            getattr(settings, "generation_params", None) or _get_default_generation_params()
        )

        init_models_for_session_from_class(
            db,
            me=me,
            session=session,
            class_id=session.class_id,
            requested_model_names=None,
            base_generation_params=base_gen,
            generation_overrides=None,
            sync_existing=True,
        )

        models = _select_models_for_existing_session(
            db,
            session=session,
            body=body,
            class_id=class_id,
        )

        # project_id는 "요청 파라미터"로만 검증
        if project_id is not None and session.project_id is not None and session.project_id != project_id:
            raise HTTPException(status_code=400, detail="요청한 project_id와 세션의 project_id가 일치하지 않습니다.")

        ctx_knowledge_ids = _get_session_knowledge_ids(session)

    return run_practice_turn(
        db=db,
        session=session,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        knowledge_ids=ctx_knowledge_ids,
    )
