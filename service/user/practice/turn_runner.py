# service/user/practice/turn_runner.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.session import SessionLocal
from langchain_service.chain.qa_chain import make_qa_chain
from langchain_service.chain.style import build_system_prompt as build_style_system_prompt
from langchain_service.llm.setup import call_llm_chat
from langchain_service.llm.runner import generate_session_title_llm

from crud.user.practice import practice_response_crud, practice_session_crud
from models.user.account import AppUser
from models.user.prompt import AIPrompt, PromptShare
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
# prompt helpers
# =========================================
def _merge_prompt(prev: Any, extra: Any) -> Optional[str]:
    p = (prev or "").strip() if isinstance(prev, str) else ""
    e = (extra or "").strip() if isinstance(extra, str) else ""
    if not e:
        return p or None
    if not p:
        return e
    if e in p:
        return p
    return p + "\n\n" + e


def _compose_system_prompt(*parts: Any) -> Optional[str]:
    out: List[str] = []
    for x in parts:
        if isinstance(x, str) and x.strip():
            s = x.strip()
            if s not in out:
                out.append(s)
    if not out:
        return None
    return "\n\n".join(out).strip()


def _is_none_style(style_key: Any) -> bool:
    if style_key is None:
        return True
    if isinstance(style_key, str) and style_key.strip().lower() in ("none", "null", ""):
        return True
    return False


# =========================================
# prompt system_prompt 로드 (내 소유 or class 공유)
# =========================================
def _load_prompt_system_prompt_for_practice(
    db: Session,
    *,
    prompt_id: int,
    me: AppUser,
    class_id: Optional[int],
    strict: bool,
) -> Optional[str]:
    # 1) 내 소유 프롬프트
    stmt = select(AIPrompt).where(AIPrompt.prompt_id == prompt_id)
    if hasattr(AIPrompt, "is_active"):
        stmt = stmt.where(AIPrompt.is_active.is_(True))
    prompt = db.execute(stmt).scalar_one_or_none()

    if prompt is not None and getattr(prompt, "owner_id", None) == me.user_id:
        sp = (getattr(prompt, "system_prompt", "") or "").strip()
        return sp or None

    # 2) class 공유 프롬프트
    if class_id:
        conds = [
            PromptShare.prompt_id == prompt_id,
            PromptShare.class_id == class_id,
        ]
        if hasattr(PromptShare, "is_active"):
            conds.append(PromptShare.is_active.is_(True))
        if hasattr(AIPrompt, "is_active"):
            conds.append(AIPrompt.is_active.is_(True))

        stmt2 = (
            select(AIPrompt)
            .join(PromptShare, PromptShare.prompt_id == AIPrompt.prompt_id)
            .where(*conds)
        )
        prompt2 = db.execute(stmt2).scalar_one_or_none()
        if prompt2 is not None:
            sp = (getattr(prompt2, "system_prompt", "") or "").strip()
            return sp or None

    if strict:
        raise HTTPException(status_code=404, detail="prompt not found or not accessible")
    return None


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
    # --- per-turn overrides (orchestrator에서 넘겨주도록) ---
    requested_prompt_id: Optional[int] = None,
    requested_generation_params: Optional[Dict[str, Any]] = None,
    requested_style_preset: Optional[str] = None,
    requested_style_params: Optional[Dict[str, Any]] = None,
) -> PracticeTurnResponse:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")

    # ---- settings/prompt base generation ----
    session_base_gen = normalize_generation_params_dict(getattr(settings, "generation_params", None) or {})
    prompt_snapshot = getattr(settings, "prompt_snapshot", None) or {}
    prompt_gen = prompt_snapshot.get("generation_params") if isinstance(prompt_snapshot, dict) else {}
    prompt_gen = normalize_generation_params_dict(prompt_gen) if isinstance(prompt_gen, dict) else {}

    # ---- selected few-shots (setting 선택) ----
    selected_few_shots = _load_selected_few_shots_for_setting(
        db,
        setting_id=settings.setting_id,
        me=user,
    )

    # ---- style preset (요청 > settings) ----
    style_key = requested_style_preset if requested_style_preset is not None else getattr(settings, "style_preset", None)
    style_is_none = _is_none_style(style_key)

    # ---- prompt system_prompt (요청 > 세션 저장값) ----
    effective_prompt_id = requested_prompt_id if requested_prompt_id is not None else getattr(session, "prompt_id", None)
    prompt_system_prompt: Optional[str] = None
    if effective_prompt_id:
        # 요청으로 들어온 prompt_id면 strict, 세션에 박힌 값이면 soft(깨진 세션을 살리기)
        strict = requested_prompt_id is not None
        prompt_system_prompt = _load_prompt_system_prompt_for_practice(
            db,
            prompt_id=int(effective_prompt_id),
            me=user,
            class_id=getattr(session, "class_id", None),
            strict=strict,
        )

    # ---- style params (settings + per-turn override) ----
    base_style_params = dict(getattr(settings, "style_params", None) or {})
    if isinstance(requested_style_params, dict) and requested_style_params:
        base_style_params.update(requested_style_params)

    # ---- retrieve_fn & chain ----
    # chain 쪽 style 인자는 내부 fallback/기본 프롬프트 때문에 "friendly"로 안정화하되,
    # 실제 SystemMessage는 style_params["system_prompt"]로 제어한다.
    style_key_for_chain = "friendly"

    kids = coerce_int_list(knowledge_ids)
    def run_model_turn(model: PracticeSessionModel) -> Dict[str, Any]:
        if model.session_id != session.session_id:
            raise HTTPException(status_code=400, detail="session_model does not belong to given session")

        db_task = SessionLocal()
        try:
            provider, real_model, runtime_defaults = resolve_runtime_model(model.model_name)
            runtime_defaults = normalize_generation_params_dict(runtime_defaults or {})
            model_gp = normalize_generation_params_dict(getattr(model, "generation_params", None) or {})
            req_gp = (
                normalize_generation_params_dict(requested_generation_params or {})
                if isinstance(requested_generation_params, dict)
                else {}
            )

            # 우선순위:
            # settings(base) -> prompt_gen -> runtime_defaults -> model_gp -> request(turn override)
            effective_gp_full: Dict[str, Any] = normalize_generation_params_dict(
                {**session_base_gen, **prompt_gen, **runtime_defaults, **model_gp, **req_gp}
            )

            max_out = get_model_max_output_tokens(
                logical_model_name=model.model_name,
                provider=provider,
                real_model_name=real_model,
            )
            effective_gp_full = clamp_generation_params_max_tokens(effective_gp_full, max_out=max_out)
            effective_gp_full = normalize_generation_params_dict(effective_gp_full)

            # ---- prompt_snapshot fallback (settings에 저장된 스냅샷) ----
            if isinstance(prompt_snapshot, dict):
                for k in ("system_prompt", "few_shot_examples"):
                    if k in prompt_snapshot and not effective_gp_full.get(k):
                        effective_gp_full[k] = prompt_snapshot.get(k)

            # ---- 최신 prompt system_prompt 합치기 (스냅샷보다 우선 반영) ----
            if prompt_system_prompt:
                effective_gp_full["system_prompt"] = _merge_prompt(
                    effective_gp_full.get("system_prompt"),
                    prompt_system_prompt,
                )

            # ---- few-shots: request/prompt_snapshot 없으면 setting 선택 값 사용 ----
            if not effective_gp_full.get("few_shot_examples") and selected_few_shots:
                effective_gp_full["few_shot_examples"] = selected_few_shots

            # ---- few-shot meta rule을 system_prompt 뒤에 붙임 ----
            sys_from_fs = _derive_system_prompt_from_few_shots(effective_gp_full.get("few_shot_examples"))
            if sys_from_fs:
                effective_gp_full["system_prompt"] = _merge_prompt(
                    effective_gp_full.get("system_prompt"),
                    sys_from_fs,
                )

            # ---- 최종 system_prompt 구성 (style + user_override + prompt/derived) ----
            style_params = dict(base_style_params)
            user_override_sys = (
                style_params.get("system_prompt")
                if isinstance(style_params.get("system_prompt"), str)
                else None
            )

            base_style_prompt: Optional[str] = None
            if (not style_is_none) and isinstance(style_key, str) and style_key.strip():
                # policy_flags는 필요 시 추후 주입
                base_style_prompt = build_style_system_prompt(style=style_key.strip())

            final_system_prompt = _compose_system_prompt(
                base_style_prompt,
                user_override_sys,
                effective_gp_full.get("system_prompt"),
            )

            if final_system_prompt is not None:
                style_params["system_prompt"] = final_system_prompt
            else:
                # style_preset을 none/null로 두는 경우 기본 system 프롬프트 삽입을 막기 위해 빈 문자열로 박아둠
                if style_is_none and "system_prompt" not in style_params:
                    style_params["system_prompt"] = ""

            # ---- few_shot_examples / gen_params 분리 ----
            few_shots = effective_gp_full.get("few_shot_examples")
            few_shots = few_shots if isinstance(few_shots, list) else []

            gen_params = dict(effective_gp_full)
            gen_params.pop("system_prompt", None)
            gen_params.pop("few_shot_examples", None)

            gen_params = normalize_generation_params_dict(gen_params)
            gen_params = clamp_generation_params_max_tokens(gen_params, max_out=max_out)
            gen_params = normalize_generation_params_dict(gen_params)

            retrieve_fn_task = make_retrieve_fn_for_practice(db_task, user)
            chain_task = make_qa_chain(
                call_llm_chat=call_llm_chat,
                retrieve_fn=retrieve_fn_task,
                context_text="",
                policy_flags=None,
                style=style_key_for_chain,
                max_ctx_chars=DEFAULT_MAX_CTX_CHARS,
                streaming=False,
                chain_version=CHAIN_VERSION,
            )

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
                "trace": {"chain_version": CHAIN_VERSION, "logical_model_name": model.model_name},
            }
            if provider:
                chain_in["provider"] = provider

            out = chain_task.invoke(chain_in)

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

            return {
                "session_model_id": model.session_model_id,
                "model_name": model.model_name,
                "prompt_text": prompt_text,
                "response_text": response_text,
                "token_usage": token_usage,
                "latency_ms": latency_ms,
                "generation_params": effective_gp_full,
                "is_primary": model.is_primary,
            }
        except Exception:
            db_task.rollback()
            raise
        finally:
            db_task.close()

    results: List[PracticeTurnModelResult] = []
    responses: List[Dict[str, Any]] = []
    if models:
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = [executor.submit(run_model_turn, m) for m in models]
            for future in futures:
                responses.append(future.result())

    if responses:
        try:
            for response in responses:
                resp = practice_response_crud.create(
                    db,
                    PracticeResponseCreate(
                        session_model_id=response["session_model_id"],
                        session_id=session.session_id,
                        model_name=response["model_name"],
                        prompt_text=response["prompt_text"],
                        response_text=response["response_text"],
                        token_usage=response["token_usage"],
                        latency_ms=response["latency_ms"],
                    ),
                )
                results.append(
                    PracticeTurnModelResult(
                        session_model_id=resp.session_model_id,
                        model_name=response["model_name"],
                        response_id=resp.response_id,
                        prompt_text=resp.prompt_text,
                        response_text=resp.response_text,
                        token_usage=resp.token_usage,
                        latency_ms=resp.latency_ms,
                        created_at=resp.created_at,
                        is_primary=response["is_primary"],
                        generation_params=response["generation_params"],
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            raise

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
