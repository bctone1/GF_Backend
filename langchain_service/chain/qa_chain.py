# langchain_service/chain/qa_chain.py
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from core import config
from langchain_service.chain.style import build_system_prompt, STYLE_MAP
from langchain_service.chain.stages import (
    normalize_input,          # (0)
    build_messages,           # (2)
    parse_output,             # (4)
    normalize_response,       # (5)
    retrieve_context as stage_retrieve_context,  # (1)에서 실제 retrieve 실행용(선택)
)
from langchain_service.chain.contracts import (
    # keys
    GF_PROMPT,
    GF_STYLE_PARAMS,
    GF_GENERATION_PARAMS,
    GF_MODEL_NAMES,
    GF_POLICY_FLAGS,
    GF_TRACE,
    GF_KNOWLEDGE_IDS,
    GF_CONTEXT,
    GF_SOURCES,
    GF_RETRIEVAL,
    GF_MESSAGES,
    GF_RAW_TEXT,
    GF_TOKEN_USAGE,
    GF_LATENCY_MS,
    GF_MODEL_NAME,
    GF_USED,
    GF_RETRIEVED_COUNT,
    GF_TOP_K,
    GF_THRESHOLD,

    # validators / errors
    ContractError,
    validate_stage1,
    validate_stage3,
)


def make_qa_chain(
    *,
    call_llm_chat: Callable[..., Any],
    retrieve_fn: Optional[Callable[..., Any]] = None,
    # (레거시/호환) 외부에서 만든 context_text가 있으면 stage1 fallback으로 사용
    context_text: str = "",
    policy_flags: dict | None = None,
    style: str = "friendly",
    max_ctx_chars: int = 10000,
    streaming: bool = False,  # call_llm_chat가 streaming 지원하면 추후 연결
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    # 배포 추적용
    chain_version: str = "qa_chain_20251219",
):
    """
    (0) RunnableLambda(normalize_input)
    (1) RunnableAssign(RunnableParallel(...retrieve...)) 형태로 enrich_context를 "보이게"
    (2) RunnableLambda(build_messages)
    (3) RunnableLambda(call_llm)
    (4) RunnableLambda(parse_output)
    (5) RunnableLambda(normalize_response)
    """

    def _is_none_style(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v.strip().lower() in ("none", "null", ""):
            return True
        return False

    # -------------------------
    # defaults (factory level)
    # -------------------------
    _rule_txt = (
        "규칙: 제공된 컨텍스트를 우선하여 답하고, 정말 관련이 없을 때만 "
        "짧게 '해당내용은 찾을 수 없음'이라고 답하라."
    )

    if _is_none_style(style):
        _style = "none"
        _system_txt = ""  # style none이면 기본 스타일 프롬프트는 비움
    else:
        _style = style if style in STYLE_MAP else "friendly"
        _system_txt = build_system_prompt(style=_style, **(policy_flags or {}))

    _default_few_shot = few_shot_examples or []

    _provider_default = (provider or getattr(config, "LLM_PROVIDER", "openai")).lower()
    _model_default = model or getattr(
        config, "LLM_MODEL", getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini")
    )
    _temperature_default = temperature if temperature is not None else getattr(config, "LLM_TEMPERATURE", 0.7)
    _top_p_default = top_p if top_p is not None else getattr(config, "LLM_TOP_P", None)
    _max_tokens_default = max_tokens  # None이면 모델 기본값 사용

    # =========================================================
    # (0) normalize_input (wrapper: defaults + legacy 키 흡수)
    # =========================================================
    def _stage0(inp: Any) -> Dict[str, Any]:
        d: Dict[str, Any]
        if isinstance(inp, str):
            d = {GF_PROMPT: inp}
        elif isinstance(inp, dict):
            d = dict(inp)
        else:
            d = {}

        # legacy prompt keys -> GF_PROMPT
        if GF_PROMPT not in d:
            for k in ("question", "prompt_text", "input", "query"):
                v = d.get(k)
                if isinstance(v, str) and v.strip():
                    d[GF_PROMPT] = v.strip()
                    break

        # style_params 기본 + system_prompt 처리(덮어쓰기 금지)
        sp = d.get(GF_STYLE_PARAMS) or {}
        if not isinstance(sp, dict):
            sp = {}

        # 기본 규칙 자동 부착 여부(옵션): 기본 True
        use_default_rule = sp.get("use_default_rule")
        if use_default_rule is None:
            use_default_rule = True
        use_default_rule = bool(use_default_rule)

        existing = sp.get("system_prompt")
        if "system_prompt" not in sp:
            # system_prompt 키 자체가 없을 때만 기본값을 채움
            base_parts: List[str] = []
            if isinstance(_system_txt, str) and _system_txt.strip():
                base_parts.append(_system_txt.strip())
            if use_default_rule and isinstance(_rule_txt, str) and _rule_txt.strip():
                base_parts.append(_rule_txt.strip())
            sp["system_prompt"] = "\n".join(base_parts).strip()
        else:
            # system_prompt가 있으면 덮지 않고, 기본 rule만 필요 시 append
            if use_default_rule and isinstance(existing, str):
                cur = existing
                if _rule_txt.strip() and (_rule_txt.strip() not in cur):
                    # 비어있는 system_prompt("" 포함)여도 rule은 붙임(원치 않으면 use_default_rule=false)
                    sep = "\n\n" if cur.strip() else ""
                    sp["system_prompt"] = (cur + sep + _rule_txt).strip()
            # non-str이면 그대로 둠(후속 stage에서 str 캐스팅)

        d[GF_STYLE_PARAMS] = sp

        # policy_flags 기본값
        d.setdefault(GF_POLICY_FLAGS, policy_flags)

        # few-shot 기본값 (계약 외 키)
        d.setdefault("few_shot_examples", _default_few_shot)

        # trace (배포 추적)
        tr = d.get(GF_TRACE) or {}
        if not isinstance(tr, dict):
            tr = {}
        tr.setdefault("chain_version", chain_version)
        d[GF_TRACE] = tr

        return normalize_input(d)

    # =========================================================
    # (1) enrich_context: retrieve를 "보이게" 만들기 위한 assign + merge
    # =========================================================
    def _context_pack(stage0_out: Dict[str, Any]) -> Dict[str, Any]:
        """
        반환은 {context, sources, retrieval}만.
        retrieve_fn 있으면 stage_retrieve_context를 통해 실제 검색 수행.
        """
        knowledge_ids = stage0_out.get(GF_KNOWLEDGE_IDS) or []
        if not isinstance(knowledge_ids, list):
            knowledge_ids = []

        # search params (계약 외 키)
        top_k = None
        threshold = None
        sp2 = stage0_out.get("search_params") or stage0_out.get("retrieval_params") or {}
        if isinstance(sp2, dict):
            try:
                top_k = int(sp2.get("top_k")) if sp2.get("top_k") is not None else None
            except Exception:
                top_k = None
            try:
                threshold = float(sp2.get("threshold")) if sp2.get("threshold") is not None else None
            except Exception:
                threshold = None

        # 1) retrieve_fn 주입 시: stages.retrieve_context 사용
        if retrieve_fn is not None:
            dd = dict(stage0_out)
            dd["retrieve_fn"] = retrieve_fn
            out = stage_retrieve_context(dd)  # full dict(stage1)
            ctx = str(out.get(GF_CONTEXT) or "")
            if max_ctx_chars and len(ctx) > max_ctx_chars:
                ctx = ctx[:max_ctx_chars]
            return {
                GF_CONTEXT: ctx,
                GF_SOURCES: list(out.get(GF_SOURCES) or []),
                GF_RETRIEVAL: dict(out.get(GF_RETRIEVAL) or {}),
            }

        # 2) fallback: context_text(외부 RAG) 사용
        ctx = stage0_out.get(GF_CONTEXT)
        if ctx is None:
            ctx = context_text
        ctx = str(ctx or "")
        if max_ctx_chars and len(ctx) > max_ctx_chars:
            ctx = ctx[:max_ctx_chars]

        sources: List[Dict[str, Any]] = list(stage0_out.get(GF_SOURCES) or [])
        used = bool(knowledge_ids) or bool(ctx)

        return {
            GF_CONTEXT: ctx,
            GF_SOURCES: sources,
            GF_RETRIEVAL: {
                GF_USED: used,
                GF_RETRIEVED_COUNT: int(len(sources) or 0),
                GF_TOP_K: top_k,
                GF_THRESHOLD: threshold,
                GF_KNOWLEDGE_IDS: list(knowledge_ids),
            },
        }

    def _stage1_merge(x: Dict[str, Any]) -> Dict[str, Any]:
        base = x.get("passthrough_input")
        pack = x.get("context_pack")
        if not isinstance(base, dict):
            raise ContractError("[stage1] passthrough_input must be dict")
        if not isinstance(pack, dict):
            raise ContractError("[stage1] context_pack must be dict")

        out = dict(base)
        out.update(pack)

        validate_stage1(out)
        return out

    # =========================================================
    # (3) call_llm (call_llm_chat 기반, stage3 계약 dict로 맞춤)
    # =========================================================
    def _lc_messages_to_role_dicts(messages: List[Any]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for m in messages:
            role = "user"
            content = ""

            try:
                from langchain_core.messages import SystemMessage, HumanMessage, AIMessage  # local import
                if isinstance(m, SystemMessage):
                    role = "system"
                elif isinstance(m, HumanMessage):
                    role = "user"
                elif isinstance(m, AIMessage):
                    role = "assistant"
            except Exception:
                pass

            if hasattr(m, "content"):
                content = m.content if isinstance(m.content, str) else str(m.content)
            elif isinstance(m, dict):
                role = str(m.get("role") or role)
                content = str(m.get("content") or "")
            else:
                content = str(m)

            out.append({"role": role, "content": content})
        return out

    def _stage3_call_llm(d: Dict[str, Any]) -> Dict[str, Any]:
        messages = d.get(GF_MESSAGES)
        if not isinstance(messages, list) or not messages:
            raise ContractError("[stage3] messages must be a non-empty list")

        gen = d.get(GF_GENERATION_PARAMS) or {}
        if not isinstance(gen, dict):
            gen = {}

        # model: model_names[0] > factory default
        model_names = d.get(GF_MODEL_NAMES)
        chosen_model = None
        if isinstance(model_names, list) and model_names and isinstance(model_names[0], str) and model_names[0]:
            chosen_model = model_names[0]
        chosen_model = chosen_model or _model_default

        # provider
        chosen_provider = d.get("provider") or _provider_default

        # params
        chosen_temp = gen.get("temperature", None)
        if chosen_temp is None:
            chosen_temp = _temperature_default

        chosen_top_p = gen.get("top_p", None)
        if chosen_top_p is None:
            chosen_top_p = _top_p_default

        # stage0에서 통일한 키: max_completion_tokens (없으면 factory max_tokens_default)
        mct = gen.get("max_completion_tokens", None)
        if mct is None:
            mct = _max_tokens_default

        _ = streaming
        msg_dicts = _lc_messages_to_role_dicts(messages)

        t0 = time.perf_counter()
        res = call_llm_chat(
            messages=msg_dicts,
            provider=str(chosen_provider),
            model=str(chosen_model),
            temperature=chosen_temp,
            max_tokens=mct,
            top_p=chosen_top_p,
        )
        t1 = time.perf_counter()

        raw_text = str(getattr(res, "text", "") or "")
        token_usage = getattr(res, "token_usage", None)
        latency_ms = int((t1 - t0) * 1000)

        out = dict(d)
        out[GF_RAW_TEXT] = raw_text
        out[GF_TOKEN_USAGE] = token_usage
        out[GF_LATENCY_MS] = latency_ms
        out[GF_MODEL_NAME] = str(chosen_model)

        validate_stage3(out)
        return out

    # =========================================================
    # Runnable graph (0~5) : 고정
    # =========================================================
    stage0 = RunnableLambda(_stage0).with_config(run_name="stage0_normalize_input")

    stage1_assign = RunnablePassthrough.assign(
        passthrough_input=RunnablePassthrough().with_config(run_name="stage1_passthrough_input"),
        context_pack=RunnableLambda(_context_pack).with_config(run_name="stage1_retrieve_context"),
    ).with_config(run_name="stage1_enrich_assign")

    stage1_merge = RunnableLambda(_stage1_merge).with_config(run_name="stage1_enrich_merge")

    stage2 = RunnableLambda(build_messages).with_config(run_name="stage2_build_messages")
    stage3 = RunnableLambda(_stage3_call_llm).with_config(run_name="stage3_call_llm")
    stage4 = RunnableLambda(parse_output).with_config(run_name="stage4_parse_output")
    stage5 = RunnableLambda(normalize_response).with_config(run_name="stage5_normalize_response")

    return stage0 | stage1_assign | stage1_merge | stage2 | stage3 | stage4 | stage5
