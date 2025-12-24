# service/user/practice/turn_runner.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from langchain_service.chain.qa_chain import make_qa_chain
from langchain_service.llm.setup import call_llm_chat
from langchain_service.llm.runner import generate_session_title_llm

from crud.user.practice import practice_response_crud, practice_session_crud
from models.user.account import AppUser
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeSessionSetting,
    PracticeSessionSettingFewShot,
    UserFewShotExample,
)

from schemas.user.practice import (
    PracticeResponseCreate,
    PracticeSessionUpdate,
    PracticeTurnModelResult,
    PracticeTurnResponse,
)

from service.user.practice.ids import coerce_int_list
from service.user.practice.models_sync import resolve_runtime_model
from service.user.practice.params import (
    normalize_generation_params_dict,
    get_model_max_output_tokens,
    clamp_generation_params_max_tokens,
)
from service.user.practice.retrieval import make_retrieve_fn_for_practice


CHAIN_VERSION = "qa_chain_20251219"
DEFAULT_MAX_CTX_CHARS = 12000


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
# 멀티 모델 Practice 턴 실행
# =========================================
def run_practice_turn(
    *,
    db: Session,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    models: List[PracticeSessionModel],
    prompt_text: str,
    user: AppUser,
    knowledge_ids: Optional[List[int]] = None,
    generate_title: bool = True,
) -> PracticeTurnResponse:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")

    # ---- settings/agent base generation ----
    session_base_gen = normalize_generation_params_dict(getattr(settings, "generation_params", None) or {})
    agent_snapshot = getattr(settings, "agent_snapshot", None) or {}
    agent_gen = agent_snapshot.get("generation_params") if isinstance(agent_snapshot, dict) else {}
    agent_gen = normalize_generation_params_dict(agent_gen) if isinstance(agent_gen, dict) else {}

    # ---- selected few-shots (setting 선택) ----
    selected_few_shots = _load_selected_few_shots_for_setting(
        db,
        setting_id=settings.setting_id,
        me=user,
    )

    # ---- style preset & retrieve_fn ----
    style_key = getattr(settings, "style_preset", None) or "friendly"
    retrieve_fn = make_retrieve_fn_for_practice(db, user)

    chain = make_qa_chain(
        call_llm_chat=call_llm_chat,
        retrieve_fn=retrieve_fn,
        context_text="",
        policy_flags=None,
        style=style_key,
        max_ctx_chars=DEFAULT_MAX_CTX_CHARS,
        streaming=False,
        chain_version=CHAIN_VERSION,
    )

    kids = coerce_int_list(knowledge_ids)
    results: List[PracticeTurnModelResult] = []

    for m in models:
        if m.session_id != session.session_id:
            raise HTTPException(status_code=400, detail="session_model does not belong to given session")

        provider, real_model, runtime_defaults = resolve_runtime_model(m.model_name)
        runtime_defaults = normalize_generation_params_dict(runtime_defaults or {})
        model_gp = normalize_generation_params_dict(getattr(m, "generation_params", None) or {})

        # 우선순위: settings(base) -> agent_gen -> runtime_defaults -> model_gp
        effective_gp_full: Dict[str, Any] = normalize_generation_params_dict(
            {**session_base_gen, **agent_gen, **runtime_defaults, **model_gp}
        )

        max_out = get_model_max_output_tokens(
            logical_model_name=m.model_name,
            provider=provider,
            real_model_name=real_model,
        )
        effective_gp_full = clamp_generation_params_max_tokens(effective_gp_full, max_out=max_out)
        effective_gp_full = normalize_generation_params_dict(effective_gp_full)

        if isinstance(agent_snapshot, dict):
            for k in ("system_prompt", "few_shot_examples"):
                if k in agent_snapshot and not effective_gp_full.get(k):
                    effective_gp_full[k] = agent_snapshot.get(k)

        if not effective_gp_full.get("few_shot_examples") and selected_few_shots:
            effective_gp_full["few_shot_examples"] = selected_few_shots

        sys_from_fs = _derive_system_prompt_from_few_shots(effective_gp_full.get("few_shot_examples"))
        if sys_from_fs:
            prev = effective_gp_full.get("system_prompt")
            if isinstance(prev, str) and prev.strip():
                effective_gp_full["system_prompt"] = prev.strip() + "\n\n" + sys_from_fs
            else:
                effective_gp_full["system_prompt"] = sys_from_fs

        style_params = dict(getattr(settings, "style_params", None) or {})
        sys_prompt = effective_gp_full.get("system_prompt")
        if isinstance(sys_prompt, str) and sys_prompt.strip():
            style_params["system_prompt"] = sys_prompt.strip()

        few_shots = effective_gp_full.get("few_shot_examples")
        few_shots = few_shots if isinstance(few_shots, list) else []

        gen_params = dict(effective_gp_full)
        gen_params.pop("system_prompt", None)
        gen_params.pop("few_shot_examples", None)

        gen_params = normalize_generation_params_dict(gen_params)
        gen_params = clamp_generation_params_max_tokens(gen_params, max_out=max_out)
        gen_params = normalize_generation_params_dict(gen_params)

        chain_in: Dict[str, Any] = {
            "prompt": prompt_text,
            "history": [],
            "session_id": session.session_id,
            "class_id": session.class_id,
            "knowledge_ids": kids,
            "style_params": style_params,
            "generation_params": gen_params,
            "model_names": [real_model],
            "few_shot_examples": few_shots,
            "trace": {"chain_version": CHAIN_VERSION, "logical_model_name": m.model_name},
        }
        if provider:
            chain_in["provider"] = provider

        out = chain.invoke(chain_in)

        response_text = out["text"]
        latency_ms = out.get("latency_ms")

        raw_usage = out.get("token_usage")
        if isinstance(raw_usage, dict):
            token_usage: Dict[str, Any] = dict(raw_usage)
        else:
            token_usage = {"raw": raw_usage}

        token_usage["_gf"] = {
            "retrieval": out.get("retrieval"),
            "sources": out.get("sources"),
            "runtime_model": out.get("model_name"),
        }

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
                generation_params=effective_gp_full,
            )
        )

    if generate_title and (not session.title) and results:
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

