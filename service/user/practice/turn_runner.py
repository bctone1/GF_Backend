# service/user/practice/turn_runner.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import time
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import config as core_config
from database.session import SessionLocal
from langchain_service.chain.qa_chain import lc_messages_to_role_dicts, make_qa_chain
from langchain_service.chain.stages import build_messages, normalize_input, retrieve_context
from langchain_service.chain.style import build_system_prompt as build_style_system_prompt
from langchain_service.llm.setup import call_llm_chat, iter_llm_chat_stream
from langchain_service.llm.runner import generate_session_title_llm

from crud.user.practice import practice_response_crud, practice_session_crud
from models.user.account import AppUser
from models.user.prompt import AIPrompt, PromptShare
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeSessionSetting,
    UserFewShotExample,
)

from schemas.user.practice import (
    PracticeResponseCreate,
    PracticeSessionUpdate,
    PracticeTurnModelResult,
    PracticeTurnResponse,
)

from service.user.practice.ids import coerce_int_list, get_session_prompt_ids
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


def _normalize_example_ids(v: Any) -> list[int]:
    if v is None:
        return []
    if not isinstance(v, list):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for x in v:
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue
        if ix <= 0:
            continue
        if ix in seen:
            continue
        seen.add(ix)
        out.append(ix)
    return out


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


def _load_prompt_system_prompts_for_practice(
    db: Session,
    *,
    prompt_ids: list[int],
    me: AppUser,
    class_id: Optional[int],
    strict: bool,
) -> list[str]:
    out: list[str] = []
    for prompt_id in coerce_int_list(prompt_ids):
        sp = _load_prompt_system_prompt_for_practice(
            db,
            prompt_id=int(prompt_id),
            me=me,
            class_id=class_id,
            strict=strict,
        )
        if sp:
            out.append(sp)
    return out


# =========================================
# settings에 선택된 few-shot 예시 로드 (A안: JSONB list)
# - 우선순위: few_shot_example_ids(JSONB) -> (레거시) few_shot_example_id
# =========================================
def _load_selected_few_shots_for_setting(
    db: Session,
    *,
    setting: PracticeSessionSetting,
    me: AppUser,
) -> List[Dict[str, Any]]:
    # A안: JSONB list
    ids = _normalize_example_ids(getattr(setting, "few_shot_example_ids", None))
    if ids:
        stmt = (
            select(
                UserFewShotExample.example_id,
                UserFewShotExample.input_text,
                UserFewShotExample.output_text,
                UserFewShotExample.meta,
            )
            .where(UserFewShotExample.user_id == me.user_id)
            .where(UserFewShotExample.is_active.is_(True))
            .where(UserFewShotExample.example_id.in_(ids))
        )
        rows = db.execute(stmt).all()

        by_id: dict[int, tuple[str, str, Any]] = {}
        for eid, input_text, output_text, meta in rows:
            by_id[int(eid)] = (input_text or "", output_text or "", meta or {})

        out: List[Dict[str, Any]] = []
        for eid in ids:  # 입력 순서 유지
            row = by_id.get(int(eid))
            if not row:
                continue
            it, ot, meta = row
            it = (it or "").strip()
            ot = (ot or "").strip()
            if it and ot:
                out.append({"input": it, "output": ot, "meta": meta or {}})
        return out

    # (레거시) 단일 선택 유지하고 있으면 호환
    example_id = getattr(setting, "few_shot_example_id", None)
    if example_id:
        stmt = (
            select(
                UserFewShotExample.input_text,
                UserFewShotExample.output_text,
                UserFewShotExample.meta,
            )
            .where(UserFewShotExample.example_id == example_id)
            .where(UserFewShotExample.user_id == me.user_id)
            .where(UserFewShotExample.is_active.is_(True))
        )
        row = db.execute(stmt).one_or_none()
        if row:
            input_text, output_text, meta = row
            it = (input_text or "").strip()
            ot = (output_text or "").strip()
            if it and ot:
                return [{"input": it, "output": ot, "meta": meta or {}}]
    return []


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


@dataclass(frozen=True)
class PracticeTurnContext:
    session_base_gen: Dict[str, Any]
    prompt_snapshot: Dict[str, Any]
    selected_few_shots: List[Dict[str, Any]]
    style_key: Optional[str]
    style_is_none: bool
    prompt_system_prompt: Optional[str]
    base_style_params: Dict[str, Any]
    kids: List[int]
    style_key_for_chain: str


def _build_turn_context(
    *,
    db: Session,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    user: AppUser,
    knowledge_ids: Optional[List[int]],
    requested_prompt_ids: Optional[List[int]],
    requested_style_preset: Optional[str],
    requested_style_params: Optional[Dict[str, Any]],
) -> PracticeTurnContext:
    session_base_gen = normalize_generation_params_dict(getattr(settings, "generation_params", None) or {})
    prompt_snapshot = getattr(settings, "prompt_snapshot", None) or {}

    selected_few_shots = _load_selected_few_shots_for_setting(
        db,
        setting=settings,
        me=user,
    )

    style_key = requested_style_preset if requested_style_preset is not None else getattr(settings, "style_preset", None)
    style_is_none = _is_none_style(style_key)

    effective_prompt_ids = (
        coerce_int_list(requested_prompt_ids)
        if requested_prompt_ids is not None
        else get_session_prompt_ids(session)
    )
    prompt_system_prompt: Optional[str] = None
    if effective_prompt_ids:
        strict = requested_prompt_ids is not None
        prompt_parts = _load_prompt_system_prompts_for_practice(
            db,
            prompt_ids=effective_prompt_ids,
            me=user,
            class_id=getattr(session, "class_id", None),
            strict=strict,
        )
        prompt_system_prompt = _compose_system_prompt(*prompt_parts)

    base_style_params = dict(getattr(settings, "style_params", None) or {})
    if isinstance(requested_style_params, dict) and requested_style_params:
        base_style_params.update(requested_style_params)

    kids = coerce_int_list(knowledge_ids)

    return PracticeTurnContext(
        session_base_gen=session_base_gen,
        prompt_snapshot=prompt_snapshot if isinstance(prompt_snapshot, dict) else {},
        selected_few_shots=selected_few_shots,
        style_key=style_key,
        style_is_none=style_is_none,
        prompt_system_prompt=prompt_system_prompt,
        base_style_params=base_style_params,
        kids=kids,
        style_key_for_chain="friendly",
    )


def _prepare_model_payload(
    *,
    db_task: Session,
    ctx: PracticeTurnContext,
    model: PracticeSessionModel,
    prompt_text: str,
    session: PracticeSession,
    user: AppUser,
    requested_generation_params: Optional[Dict[str, Any]],
    requested_retrieval_params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    provider, real_model, runtime_defaults = resolve_runtime_model(model.model_name)
    runtime_defaults = normalize_generation_params_dict(runtime_defaults or {})
    model_gp = normalize_generation_params_dict(getattr(model, "generation_params", None) or {})
    req_gp = (
        normalize_generation_params_dict(requested_generation_params or {})
        if isinstance(requested_generation_params, dict)
        else {}
    )

    prompt_gen = ctx.prompt_snapshot.get("generation_params") if isinstance(ctx.prompt_snapshot, dict) else {}
    prompt_gen = normalize_generation_params_dict(prompt_gen) if isinstance(prompt_gen, dict) else {}

    effective_gp_full: Dict[str, Any] = normalize_generation_params_dict(
        {**ctx.session_base_gen, **prompt_gen, **runtime_defaults, **model_gp, **req_gp}
    )

    max_out = get_model_max_output_tokens(
        logical_model_name=model.model_name,
        provider=provider,
        real_model_name=real_model,
    )
    effective_gp_full = clamp_generation_params_max_tokens(effective_gp_full, max_out=max_out)
    effective_gp_full = normalize_generation_params_dict(effective_gp_full)

    if isinstance(ctx.prompt_snapshot, dict):
        for k in ("system_prompt", "few_shot_examples"):
            if k in ctx.prompt_snapshot and not effective_gp_full.get(k):
                effective_gp_full[k] = ctx.prompt_snapshot.get(k)

    if ctx.prompt_system_prompt:
        effective_gp_full["system_prompt"] = _merge_prompt(
            effective_gp_full.get("system_prompt"),
            ctx.prompt_system_prompt,
        )

    if not effective_gp_full.get("few_shot_examples") and ctx.selected_few_shots:
        effective_gp_full["few_shot_examples"] = ctx.selected_few_shots

    sys_from_fs = _derive_system_prompt_from_few_shots(effective_gp_full.get("few_shot_examples"))
    if sys_from_fs:
        effective_gp_full["system_prompt"] = _merge_prompt(
            effective_gp_full.get("system_prompt"),
            sys_from_fs,
        )

    style_params = dict(ctx.base_style_params)
    user_override_sys = (
        style_params.get("system_prompt")
        if isinstance(style_params.get("system_prompt"), str)
        else None
    )

    base_style_prompt: Optional[str] = None
    if (not ctx.style_is_none) and isinstance(ctx.style_key, str) and ctx.style_key.strip():
        base_style_prompt = build_style_system_prompt(style=ctx.style_key.strip())

    final_system_prompt = _compose_system_prompt(
        base_style_prompt,
        user_override_sys,
        effective_gp_full.get("system_prompt"),
    )

    if final_system_prompt is not None:
        style_params["system_prompt"] = final_system_prompt
    else:
        if ctx.style_is_none and "system_prompt" not in style_params:
            style_params["system_prompt"] = ""

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
        "knowledge_ids": ctx.kids,
        "style_params": style_params,
        "generation_params": gen_params,
        "model_names": [real_model],
        "few_shot_examples": few_shots,
        "trace": {"chain_version": CHAIN_VERSION, "logical_model_name": model.model_name},
    }
    if isinstance(requested_retrieval_params, dict) and requested_retrieval_params:
        chain_in["retrieval_params"] = dict(requested_retrieval_params)
    if provider:
        chain_in["provider"] = provider

    retrieve_fn_task = make_retrieve_fn_for_practice(db_task, user)

    return {
        "provider": provider,
        "real_model": real_model,
        "effective_gp_full": effective_gp_full,
        "gen_params": gen_params,
        "style_params": style_params,
        "few_shots": few_shots,
        "chain_in": chain_in,
        "retrieve_fn": retrieve_fn_task,
    }


def stream_practice_turn(
    *,
    db: Session,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    models: List[PracticeSessionModel],
    prompt_text: str,
    user: AppUser,
    knowledge_ids: Optional[List[int]] = None,
    generate_title: bool = True,
    requested_prompt_ids: Optional[List[int]] = None,
    requested_generation_params: Optional[Dict[str, Any]] = None,
    requested_retrieval_params: Optional[Dict[str, Any]] = None,
    requested_style_preset: Optional[str] = None,
    requested_style_params: Optional[Dict[str, Any]] = None,
) -> Iterable[str]:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")
    if len(models) != 1:
        raise HTTPException(status_code=400, detail="streaming supports single model only")

    ctx = _build_turn_context(
        db=db,
        session=session,
        settings=settings,
        user=user,
        knowledge_ids=knowledge_ids,
        requested_prompt_ids=requested_prompt_ids,
        requested_style_preset=requested_style_preset,
        requested_style_params=requested_style_params,
    )

    model = models[0]

    def _event(event: str, payload: Dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _generator() -> Iterable[str]:
        db_task = SessionLocal()
        try:
            prepared = _prepare_model_payload(
                db_task=db_task,
                ctx=ctx,
                model=model,
                prompt_text=prompt_text,
                session=session,
                user=user,
                requested_generation_params=requested_generation_params,
                requested_retrieval_params=requested_retrieval_params,
            )

            chain_in = prepared["chain_in"]
            stage0 = normalize_input(chain_in)
            stage1 = retrieve_context({**stage0, "retrieve_fn": prepared["retrieve_fn"]})
            stage2 = build_messages(stage1)
            messages = stage2.get("messages")
            if not isinstance(messages, list) or not messages:
                raise HTTPException(status_code=500, detail="empty_messages_for_streaming")

            msg_dicts = lc_messages_to_role_dicts(messages)
            gen_params = prepared["gen_params"]

            temperature = gen_params.get("temperature")
            if temperature is None:
                temperature = getattr(core_config, "LLM_TEMPERATURE", 0.7)
            top_p = gen_params.get("top_p")
            if top_p is None:
                top_p = getattr(core_config, "LLM_TOP_P", None)
            max_tokens = gen_params.get("max_completion_tokens")
            stream_kwargs = dict(gen_params)
            stream_kwargs.pop("max_completion_tokens", None)
            stream_kwargs.pop("max_tokens", None)
            stream_kwargs.pop("temperature", None)
            stream_kwargs.pop("top_p", None)

            started = time.perf_counter()
            parts: List[str] = []
            for chunk in iter_llm_chat_stream(
                messages=msg_dicts,
                provider=prepared["provider"],
                model=prepared["real_model"],
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=max_tokens,
                top_p=top_p,
                **stream_kwargs,
            ):
                parts.append(chunk)
                yield _event("chunk", {"text": chunk})

            response_text = "".join(parts)
            latency_ms = int((time.perf_counter() - started) * 1000)

            resp = practice_response_crud.create(
                db_task,
                PracticeResponseCreate(
                    session_model_id=model.session_model_id,
                    session_id=session.session_id,
                    model_name=model.model_name,
                    prompt_text=prompt_text,
                    response_text=response_text,
                    token_usage=None,
                    latency_ms=latency_ms,
                ),
            )
            db_task.commit()

            session_title = session.title
            if generate_title and not session_title:
                session_title = generate_session_title_llm(
                    question=prompt_text,
                    answer=response_text,
                    max_chars=30,
                )
                practice_session_crud.update(
                    db_task,
                    session_id=session.session_id,
                    data=PracticeSessionUpdate(title=session_title),
                )
                db_task.commit()

            result = PracticeTurnModelResult(
                session_model_id=resp.session_model_id,
                model_name=resp.model_name,
                response_id=resp.response_id,
                prompt_text=resp.prompt_text,
                response_text=resp.response_text,
                token_usage=resp.token_usage,
                latency_ms=resp.latency_ms,
                created_at=resp.created_at,
                is_primary=model.is_primary,
                generation_params=prepared["effective_gp_full"],
            )
            final_payload = PracticeTurnResponse(
                session_id=session.session_id,
                session_title=session_title,
                prompt_text=prompt_text,
                results=[result],
            )
            yield _event("done", final_payload.model_dump())
        except Exception as exc:
            db_task.rollback()
            yield _event("error", {"detail": str(exc)})
        finally:
            db_task.close()

    return _generator()


# =========================================
# 멀티 모델 WS 스트리밍용 이벤트 생성
# =========================================
def iter_practice_model_stream_events(
    *,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    model: PracticeSessionModel,
    prompt_text: str,
    user: AppUser,
    knowledge_ids: Optional[List[int]] = None,
    generate_title: bool = True,
    requested_prompt_ids: Optional[List[int]] = None,
    requested_generation_params: Optional[Dict[str, Any]] = None,
    requested_retrieval_params: Optional[Dict[str, Any]] = None,
    requested_style_preset: Optional[str] = None,
    requested_style_params: Optional[Dict[str, Any]] = None,
) -> Iterable[Dict[str, Any]]:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")
    if model.session_id != session.session_id:
        raise HTTPException(status_code=400, detail="session_model does not belong to given session")

    db_task = SessionLocal()
    try:
        ctx = _build_turn_context(
            db=db_task,
            session=session,
            settings=settings,
            user=user,
            knowledge_ids=knowledge_ids,
            requested_prompt_ids=requested_prompt_ids,
            requested_style_preset=requested_style_preset,
            requested_style_params=requested_style_params,
        )
        prepared = _prepare_model_payload(
            db_task=db_task,
            ctx=ctx,
            model=model,
            prompt_text=prompt_text,
            session=session,
            user=user,
            requested_generation_params=requested_generation_params,
            requested_retrieval_params=requested_retrieval_params,
        )

        chain_in = prepared["chain_in"]
        stage0 = normalize_input(chain_in)
        stage1 = retrieve_context({**stage0, "retrieve_fn": prepared["retrieve_fn"]})
        stage2 = build_messages(stage1)
        messages = stage2.get("messages")
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=500, detail="empty_messages_for_streaming")

        msg_dicts = lc_messages_to_role_dicts(messages)
        gen_params = prepared["gen_params"]

        temperature = gen_params.get("temperature")
        if temperature is None:
            temperature = getattr(core_config, "LLM_TEMPERATURE", 0.7)
        top_p = gen_params.get("top_p")
        if top_p is None:
            top_p = getattr(core_config, "LLM_TOP_P", None)
        max_tokens = gen_params.get("max_completion_tokens")
        stream_kwargs = dict(gen_params)
        stream_kwargs.pop("max_completion_tokens", None)
        stream_kwargs.pop("max_tokens", None)
        stream_kwargs.pop("temperature", None)
        stream_kwargs.pop("top_p", None)

        started = time.perf_counter()
        parts: List[str] = []
        for chunk in iter_llm_chat_stream(
            messages=msg_dicts,
            provider=prepared["provider"],
            model=prepared["real_model"],
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens,
            top_p=top_p,
            **stream_kwargs,
        ):
            parts.append(chunk)
            yield {
                "event": "chunk",
                "session_id": session.session_id,
                "model_name": model.model_name,
                "text": chunk,
            }

        response_text = "".join(parts)
        latency_ms = int((time.perf_counter() - started) * 1000)

        resp = practice_response_crud.create(
            db_task,
            PracticeResponseCreate(
                session_model_id=model.session_model_id,
                session_id=session.session_id,
                model_name=model.model_name,
                prompt_text=prompt_text,
                response_text=response_text,
                token_usage=None,
                latency_ms=latency_ms,
            ),
        )
        db_task.commit()

        session_title = session.title
        if generate_title and not session_title and model.is_primary:
            session_title = generate_session_title_llm(
                question=prompt_text,
                answer=response_text,
                max_chars=30,
            )
            practice_session_crud.update(
                db_task,
                session_id=session.session_id,
                data=PracticeSessionUpdate(title=session_title),
            )
            db_task.commit()

        result = PracticeTurnModelResult(
            session_model_id=resp.session_model_id,
            model_name=resp.model_name,
            response_id=resp.response_id,
            prompt_text=resp.prompt_text,
            response_text=resp.response_text,
            token_usage=resp.token_usage,
            latency_ms=resp.latency_ms,
            created_at=resp.created_at,
            is_primary=model.is_primary,
            generation_params=prepared["effective_gp_full"],
        )
        yield {
            "event": "done",
            "session_id": session.session_id,
            "session_title": session_title,
            "model_name": model.model_name,
            "result": result.model_dump(),
        }
    except Exception as exc:
        db_task.rollback()
        yield {
            "event": "error",
            "session_id": session.session_id,
            "model_name": model.model_name,
            "detail": str(exc),
        }
    finally:
        db_task.close()


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
    requested_prompt_ids: Optional[List[int]] = None,
    requested_generation_params: Optional[Dict[str, Any]] = None,
    requested_retrieval_params: Optional[Dict[str, Any]] = None,
    requested_style_preset: Optional[str] = None,
    requested_style_params: Optional[Dict[str, Any]] = None,
) -> PracticeTurnResponse:
    if session.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="session not owned by user")

    ctx = _build_turn_context(
        db=db,
        session=session,
        settings=settings,
        user=user,
        knowledge_ids=knowledge_ids,
        requested_prompt_ids=requested_prompt_ids,
        requested_style_preset=requested_style_preset,
        requested_style_params=requested_style_params,
    )

    def run_model_turn(model: PracticeSessionModel) -> Dict[str, Any]:
        if model.session_id != session.session_id:
            raise HTTPException(status_code=400, detail="session_model does not belong to given session")

        db_task = SessionLocal()
        try:
            prepared = _prepare_model_payload(
                db_task=db_task,
                ctx=ctx,
                model=model,
                prompt_text=prompt_text,
                session=session,
                user=user,
                requested_generation_params=requested_generation_params,
                requested_retrieval_params=requested_retrieval_params,
            )
            chain_task = make_qa_chain(
                call_llm_chat=call_llm_chat,
                retrieve_fn=prepared["retrieve_fn"],
                context_text="",
                policy_flags=None,
                style=ctx.style_key_for_chain,
                max_ctx_chars=DEFAULT_MAX_CTX_CHARS,
                streaming=False,
                chain_version=CHAIN_VERSION,
            )
            out = chain_task.invoke(prepared["chain_in"])

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
                "generation_params": prepared["effective_gp_full"],
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
