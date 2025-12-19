# langchain_service/chain/stages.py
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langchain_service.chain.contracts import (
    # key constants (GF_)
    GF_PROMPT,
    GF_HISTORY,
    GF_SESSION_ID,
    GF_CLASS_ID,
    GF_KNOWLEDGE_IDS,
    GF_STYLE_PARAMS,
    GF_GENERATION_PARAMS,
    GF_MODEL_NAMES,
    GF_POLICY_FLAGS,
    GF_TRACE,
    GF_CONTEXT,
    GF_SOURCES,
    GF_RETRIEVAL,
    GF_MESSAGES,
    GF_RAW_TEXT,
    GF_TOKEN_USAGE,
    GF_LATENCY_MS,
    GF_MODEL_NAME,
    GF_TEXT,
    GF_USED,
    GF_RETRIEVED_COUNT,
    GF_TOP_K,
    GF_THRESHOLD,
    # guards/validators
    ContractError,
    ensure_dict,
    validate_stage0,
    validate_stage1,
    validate_stage2,
    validate_stage3,
    validate_stage4,
    validate_final,
)

# (선택) config 있으면 response_length_preset -> max_tokens 매핑에 활용
try:
    from core import config as _config  # type: ignore
except Exception:  # pragma: no cover
    _config = None  # type: ignore


# =========================================================
# helpers
# =========================================================
def _as_dict(x: Any) -> Dict[str, Any]:
    return ensure_dict("input", x) if isinstance(x, dict) else {"_raw": x}


def _normalize_int_id_list(v: Any) -> List[int]:
    """
    knowledge_ids 정리:
    - None/0/음수 제거
    - 중복 제거(입력 순서 유지)
    - str/int 혼용이면 int 캐스팅 시도
    """
    if not v:
        return []
    if not isinstance(v, list):
        v = [v]

    seen: set[int] = set()
    out: List[int] = []
    for x in v:
        if x is None:
            continue
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue
        if ix <= 0:
            continue
        if ix not in seen:
            seen.add(ix)
            out.append(ix)
    return out


def _coerce_generation_params(gen: Any, style_params: Mapping[str, Any]) -> Dict[str, Any]:
    """
    generation_params 키 정규화는 여기서만.
    내부 표준 키: max_completion_tokens (int | None)
    """
    gen = dict(gen or {}) if isinstance(gen, Mapping) else {}

    # 1) max tokens 혼용 -> max_completion_tokens 로 통일
    # 우선순위: max_completion_tokens > max_tokens > max_output_tokens
    mct = gen.get("max_completion_tokens", None)
    if mct is None:
        mct = gen.get("max_tokens", None)
    if mct is None:
        mct = gen.get("max_output_tokens", None)

    # 2) response_length_preset 있으면 (그리고 mct 없으면) preset으로 채움
    # - style_params나 gen에 있을 수 있어서 둘 다 봄
    preset = gen.get("response_length_preset") or style_params.get("response_length_preset")
    if mct is None and preset and _config is not None:
        presets = getattr(_config, "RESPONSE_LENGTH_PRESETS", {}) or {}
        try:
            mct = presets.get(str(preset))
        except Exception:
            mct = None

    # 3) 캐스팅
    if mct is not None:
        try:
            mct = int(mct)
        except (TypeError, ValueError):
            mct = None

    # 4) 표준 키로 저장 + 혼용 키 제거
    gen["max_completion_tokens"] = mct
    gen.pop("max_tokens", None)
    gen.pop("max_output_tokens", None)

    # (선택) temperature/top_p 캐스팅
    if "temperature" in gen and gen["temperature"] is not None:
        try:
            gen["temperature"] = float(gen["temperature"])
        except (TypeError, ValueError):
            pass
    if "top_p" in gen and gen["top_p"] is not None:
        try:
            gen["top_p"] = float(gen["top_p"])
        except (TypeError, ValueError):
            pass

    return gen


def _extract_token_usage(result: Any) -> Optional[Dict[str, Any]]:
    """
    provider/LC 버전마다 token usage 위치가 달라서 최대한 안전하게 뽑음.
    없으면 None.
    """
    # LangChain AIMessage: usage_metadata / response_metadata 등이 있을 수 있음
    usage = None
    try:
        usage = getattr(result, "usage_metadata", None)
        if usage:
            return dict(usage)
    except Exception:
        pass

    try:
        meta = getattr(result, "response_metadata", None) or {}
        if isinstance(meta, dict):
            tu = meta.get("token_usage") or meta.get("usage") or meta.get("usage_metadata")
            if isinstance(tu, dict):
                return tu
    except Exception:
        pass

    return None


def _extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, AIMessage):
        return result.content if isinstance(result.content, str) else str(result.content)
    # 어떤 모델은 dict 반환할 수도 있어서 방어
    if isinstance(result, dict):
        for k in ("text", "content", "output", "raw_text"):
            if k in result:
                return str(result[k])
    return str(result)


def _pick_model_name(d: Mapping[str, Any]) -> Optional[str]:
    # 우선순위: 이미 지정된 model_name > model_names[0]
    mn = d.get(GF_MODEL_NAME)
    if isinstance(mn, str) and mn:
        return mn
    mns = d.get(GF_MODEL_NAMES)
    if isinstance(mns, list) and mns:
        x = mns[0]
        return x if isinstance(x, str) else str(x)
    return None


# =========================================================
# (0) normalize_input
# =========================================================
def normalize_input(inp: Any) -> Dict[str, Any]:
    """
    입력이 뭐가 오든 stage0 계약 dict로 정리.
    - knowledge_ids 정리
    - generation_params 키 정규화(여기서만!)
    """
    # str이 들어오면 prompt로 간주
    if isinstance(inp, str):
        d: Dict[str, Any] = {GF_PROMPT: inp}
    else:
        d = dict(inp) if isinstance(inp, Mapping) else {}

    # prompt
    prompt = d.get(GF_PROMPT)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ContractError("[stage0] prompt is required (non-empty str)")

    # history (없으면 빈 리스트)
    history = d.get(GF_HISTORY)
    if history is None:
        history = []
    if not isinstance(history, list):
        # dict/tuple 들어오면 list로 감싸는 정도만
        history = [history]
    d[GF_HISTORY] = history

    # ids / params
    d[GF_KNOWLEDGE_IDS] = _normalize_int_id_list(d.get(GF_KNOWLEDGE_IDS))

    style_params = d.get(GF_STYLE_PARAMS) or {}
    if not isinstance(style_params, Mapping):
        style_params = {}
    d[GF_STYLE_PARAMS] = dict(style_params)

    gen_params = _coerce_generation_params(d.get(GF_GENERATION_PARAMS), d[GF_STYLE_PARAMS])
    d[GF_GENERATION_PARAMS] = gen_params

    # session_id/class_id (없어도 키는 유지)
    for k in (GF_SESSION_ID, GF_CLASS_ID):
        if k not in d:
            d[k] = None

    # model_names/policy_flags 키 유지
    if GF_MODEL_NAMES not in d:
        d[GF_MODEL_NAMES] = None
    if GF_POLICY_FLAGS not in d:
        d[GF_POLICY_FLAGS] = None

    # trace (optional 키지만, 디버깅 편하면 기본 {}로 둬도 됨)
    if GF_TRACE not in d or d[GF_TRACE] is None:
        d[GF_TRACE] = {}

    validate_stage0(d)
    return d


# =========================================================
# (1) retrieve_context
# =========================================================
def retrieve_context(d: Mapping[str, Any]) -> Dict[str, Any]:
    """
    RAG branch:
    - knowledge_ids 비면 무조건 used=False, context="", sources=[]
    - 있으면 retrieve_fn 호출해서 context/sources 채움
    """
    dd = dict(d)
    validate_stage0(dd)

    knowledge_ids = dd.get(GF_KNOWLEDGE_IDS) or []
    knowledge_ids = knowledge_ids if isinstance(knowledge_ids, list) else []
    top_k = None
    threshold = None

    # 선택: 검색 파라미터를 dict로 넣어두면 여기서 읽어도 됨 (계약 외 키라서 자유)
    search_params = dd.get("search_params") or dd.get("retrieval_params") or {}
    if isinstance(search_params, Mapping):
        top_k = search_params.get("top_k")
        threshold = search_params.get("threshold")
        try:
            top_k = int(top_k) if top_k is not None else None
        except (TypeError, ValueError):
            top_k = None
        try:
            threshold = float(threshold) if threshold is not None else None
        except (TypeError, ValueError):
            threshold = None

    # 기본 산출(무조건 세팅)
    dd[GF_CONTEXT] = ""
    dd[GF_SOURCES] = []
    dd[GF_RETRIEVAL] = {
        GF_USED: False,
        GF_RETRIEVED_COUNT: 0,
        GF_TOP_K: top_k,
        GF_THRESHOLD: threshold,
        GF_KNOWLEDGE_IDS: list(knowledge_ids),
    }

    if not knowledge_ids:
        validate_stage1(dd)
        return dd

    # retrieve 함수는 체인 조립 시 주입하는 걸 권장
    # - 키 예시: "retrieve_fn" 또는 "_retrieve"
    retrieve_fn = dd.get("retrieve_fn") or dd.get("_retrieve")
    if not callable(retrieve_fn):
        # RAG ON(knowledge_ids 있음)인데 retrieve_fn 없으면 바로 알려주는 게 맞음
        raise ContractError("[stage1] knowledge_ids provided but no retrieve_fn/_retrieve callable found")

    # 호출 (최대한 유연하게)
    context = ""
    sources: List[Dict[str, Any]] = []
    retrieved_count = 0

    try:
        res = retrieve_fn(
            db=dd.get("db"),
            user=dd.get("me") or dd.get("user"),
            knowledge_ids=list(knowledge_ids),
            query=dd.get(GF_PROMPT),
            top_k=top_k,
            threshold=threshold,
            raw=dd,
        )
    except TypeError:
        # 시그니처 다르면 dict 통째로 넘김
        res = retrieve_fn(dd)

    # 결과 파싱 (dict/tuple/str 허용)
    if isinstance(res, Mapping):
        context = str(res.get("context") or "")
        sources = list(res.get("sources") or [])
        r = res.get("retrieval") or {}
        if isinstance(r, Mapping):
            retrieved_count = int(r.get("retrieved_count") or len(sources) or 0)
            top_k = r.get("top_k", top_k)
            threshold = r.get("threshold", threshold)
        else:
            retrieved_count = len(sources) if sources else 0

    elif isinstance(res, tuple) or isinstance(res, list):
        # (context, sources) or (context, sources, meta)
        context = str(res[0] or "") if len(res) >= 1 else ""
        sources = list(res[1] or []) if len(res) >= 2 else []
        meta = res[2] if len(res) >= 3 else {}
        if isinstance(meta, Mapping):
            retrieved_count = int(meta.get("retrieved_count") or len(sources) or 0)
            top_k = meta.get("top_k", top_k)
            threshold = meta.get("threshold", threshold)
        else:
            retrieved_count = len(sources) if sources else 0

    else:
        context = str(res or "")
        sources = []
        retrieved_count = 0

    dd[GF_CONTEXT] = context
    dd[GF_SOURCES] = sources
    dd[GF_RETRIEVAL] = {
        GF_USED: True,
        GF_RETRIEVED_COUNT: int(retrieved_count),
        GF_TOP_K: top_k,
        GF_THRESHOLD: threshold,
        GF_KNOWLEDGE_IDS: list(knowledge_ids),
    }

    validate_stage1(dd)
    return dd


# =========================================================
# (2) build_messages
# =========================================================
def build_messages(d: Mapping[str, Any]) -> Dict[str, Any]:
    """
    반드시 messages 키를 추가해서 반환.
    (주의: {'messages': ...}만 반환하면 이전 키들이 날아가니까, 여기서는 dict merge로 반환)
    """
    dd = dict(d)
    validate_stage1(dd)

    prompt: str = dd[GF_PROMPT]
    history: List[Any] = dd.get(GF_HISTORY) or []
    style_params: Dict[str, Any] = dd.get(GF_STYLE_PARAMS) or {}
    context: str = dd.get(GF_CONTEXT) or ""

    # system prompt (최소)
    system_prompt = (
        style_params.get("system_prompt")
        or style_params.get("system")
        or "You are a helpful assistant."
    )

    messages: List[Any] = [SystemMessage(content=str(system_prompt))]

    # few-shot (선택) : [{"input": "...", "output": "..."}]
    few_shot = dd.get("few_shot_examples") or []
    if isinstance(few_shot, list):
        for ex in few_shot:
            if not isinstance(ex, Mapping):
                continue
            inp = ex.get("input")
            out = ex.get("output")
            if isinstance(inp, str) and isinstance(out, str):
                messages.append(HumanMessage(content=inp))
                messages.append(AIMessage(content=out))

    # history는 LC BaseMessage면 그대로 붙임
    if isinstance(history, list) and history:
        messages.extend(history)

    # context 주입 (최소 형태)
    if context:
        user_text = f"{prompt}\n\n[Context]\n{context}"
    else:
        user_text = prompt

    messages.append(HumanMessage(content=user_text))

    dd[GF_MESSAGES] = messages
    validate_stage2(dd)
    return dd


# =========================================================
# (3) call_llm
# =========================================================
def call_llm(d: Mapping[str, Any]) -> Dict[str, Any]:
    """
    LLM 호출:
    - llm_instance 또는 get_llm callable을 dict에서 받아서 호출
    - 출력 키 고정: raw_text, token_usage, latency_ms, model_name
    """
    dd = dict(d)
    validate_stage2(dd)

    messages = dd.get(GF_MESSAGES)
    if not isinstance(messages, list) or not messages:
        raise ContractError("[stage3] messages must be a non-empty list")

    gen = dd.get(GF_GENERATION_PARAMS) or {}
    if not isinstance(gen, Mapping):
        gen = {}

    selected_model = _pick_model_name(dd)

    llm = dd.get("llm_instance") or dd.get("llm")
    get_llm = dd.get("get_llm") or dd.get("_get_llm")

    # llm 준비
    if llm is None:
        if not callable(get_llm):
            raise ContractError("[stage3] need llm_instance/llm or get_llm callable")
        # get_llm 시그니처가 제각각일 수 있어서 유연하게 시도
        try:
            llm = get_llm(model_name=selected_model, raw=dd)
        except TypeError:
            try:
                llm = get_llm(selected_model)
            except TypeError:
                llm = get_llm()

    # per-call params 바인딩 (가능한 경우에만)
    # 내부 표준 max_completion_tokens -> provider용 max_tokens 로 매핑
    llm_kwargs: Dict[str, Any] = {}
    for k in ("temperature", "top_p", "stop", "presence_penalty", "frequency_penalty"):
        if k in gen and gen[k] is not None:
            llm_kwargs[k] = gen[k]
    mct = gen.get("max_completion_tokens")
    if mct is not None:
        llm_kwargs["max_tokens"] = mct

    if llm_kwargs and hasattr(llm, "bind"):
        try:
            llm = llm.bind(**llm_kwargs)
        except Exception:
            # bind 실패하면 그냥 원본 llm로 진행
            pass

    # 호출 + 메타 수집
    t0 = time.perf_counter()
    try:
        result = llm.invoke(messages)  # type: ignore[attr-defined]
    except Exception as e:
        raise ContractError(f"[stage3] llm.invoke failed: {e}") from e
    t1 = time.perf_counter()

    raw_text = _extract_text(result)
    token_usage = _extract_token_usage(result)
    latency_ms = int((t1 - t0) * 1000)

    model_name = selected_model or "unknown"

    dd[GF_RAW_TEXT] = raw_text
    dd[GF_TOKEN_USAGE] = token_usage
    dd[GF_LATENCY_MS] = latency_ms
    dd[GF_MODEL_NAME] = model_name

    validate_stage3(dd)
    return dd


# =========================================================
# (4) parse_output
# =========================================================
def parse_output(d: Mapping[str, Any]) -> Dict[str, Any]:
    """
    raw_text -> text 통일.
    이미 text면 그대로.
    """
    dd = dict(d)
    validate_stage3(dd)

    raw_text = dd.get(GF_RAW_TEXT, "")
    if dd.get(GF_TEXT) is None:
        dd[GF_TEXT] = str(raw_text or "")

    validate_stage4(dd)
    return dd


# =========================================================
# (5) normalize_response
# =========================================================
def normalize_response(d: Mapping[str, Any]) -> Dict[str, Any]:
    """
    최종 응답 계약으로 축약.
    최종: {text, sources, retrieval, token_usage, latency_ms, model_name}
    """
    dd = dict(d)
    validate_stage4(dd)

    out = {
        GF_TEXT: str(dd.get(GF_TEXT) or ""),
        GF_SOURCES: list(dd.get(GF_SOURCES) or []),
        GF_RETRIEVAL: dd.get(GF_RETRIEVAL) or {
            GF_USED: False,
            GF_RETRIEVED_COUNT: 0,
            GF_TOP_K: None,
            GF_THRESHOLD: None,
            GF_KNOWLEDGE_IDS: list(dd.get(GF_KNOWLEDGE_IDS) or []),
        },
        GF_TOKEN_USAGE: dd.get(GF_TOKEN_USAGE),
        GF_LATENCY_MS: dd.get(GF_LATENCY_MS),
        GF_MODEL_NAME: dd.get(GF_MODEL_NAME) or _pick_model_name(dd) or "unknown",
    }

    validate_final(out)
    return out


# =========================================================
# (선택) factory helpers (체인 조립 시 주입 편하게)
# =========================================================
def make_retrieve_context_stage(retrieve_fn: Callable[..., Any]) -> Callable[[Mapping[str, Any]], Dict[str, Any]]:
    """
    qa_chain 조립할 때 RunnableLambda(make_retrieve_context_stage(fn)) 형태로 쓰면
    retrieve_fn 주입을 dict 키로 안 넣어도 돼.
    """
    def _stage(d: Mapping[str, Any]) -> Dict[str, Any]:
        dd = dict(d)
        dd["retrieve_fn"] = retrieve_fn
        return retrieve_context(dd)
    return _stage


def make_call_llm_stage(get_llm: Callable[..., Any]) -> Callable[[Mapping[str, Any]], Dict[str, Any]]:
    """
    qa_chain 조립할 때 RunnableLambda(make_call_llm_stage(get_llm)) 형태로 쓰면
    get_llm 주입을 dict 키로 안 넣어도 돼.
    """
    def _stage(d: Mapping[str, Any]) -> Dict[str, Any]:
        dd = dict(d)
        dd["get_llm"] = get_llm
        return call_llm(dd)
    return _stage
