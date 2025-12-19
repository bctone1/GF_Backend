# langchain_service/chain/contracts.py
from __future__ import annotations

"""
Chain internal contracts (stage 0~5).

목표:
- stage별 "고정 키"를 한 곳에서 정의해서, 리팩터/디버깅 시 계약이 흔들리지 않게 하기
- stage 함수들이 dict를 반환하는지 / 필수 키가 있는지 빠르게 실패(fail-fast)하게 하기
- (선택) TypedDict로 IDE 리팩터 안정화

주의:
- 여기서 타입을 과하게 엄격하게 잡으면 provider/확장 시 발목 잡힘.
  => 핵심 키만 고정하고 값 타입은 Dict[str, Any] 등으로 느슨하게 둠.
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, TypedDict

try:
    from typing import NotRequired
except ImportError:  # pragma: no cover
    from typing_extensions import NotRequired  # type: ignore


# =========================
# Common aliases
# =========================
JSONDict = Dict[str, Any]
TokenUsage = Dict[str, Any]
MessageList = List[Any]  # langchain_core.messages.BaseMessage list (loosely typed)


# =========================
# Stage keys (constants)
# =========================
# NOTE: "GF_" prefix = GrowFit key constants

# ---- Stage 0: normalize_input output keys ----
GF_PROMPT = "prompt"
GF_HISTORY = "history"
GF_SESSION_ID = "session_id"
GF_CLASS_ID = "class_id"
GF_KNOWLEDGE_IDS = "knowledge_ids"
GF_STYLE_PARAMS = "style_params"
GF_GENERATION_PARAMS = "generation_params"
GF_MODEL_NAMES = "model_names"
GF_POLICY_FLAGS = "policy_flags"
GF_TRACE = "trace"

STAGE0_KEYS: Tuple[str, ...] = (
    GF_PROMPT,
    GF_HISTORY,
    GF_SESSION_ID,
    GF_CLASS_ID,
    GF_KNOWLEDGE_IDS,
    GF_STYLE_PARAMS,
    GF_GENERATION_PARAMS,
    GF_MODEL_NAMES,
    GF_POLICY_FLAGS,
    # trace는 optional이지만 "고정 키"로 두고 싶으면 stage0에서 {}로 채워 넣어도 됨
    GF_TRACE,
)

# stage0에서 "반드시 있어야 하는 키" (trace는 optional로 두는 편이 안전)
STAGE0_REQUIRED_KEYS: Tuple[str, ...] = (
    GF_PROMPT,
    GF_HISTORY,
    GF_SESSION_ID,
    GF_CLASS_ID,
    GF_KNOWLEDGE_IDS,
    GF_STYLE_PARAMS,
    GF_GENERATION_PARAMS,
    GF_MODEL_NAMES,
    GF_POLICY_FLAGS,
)

# ---- Stage 1: enrich_context adds ----
GF_CONTEXT = "context"
GF_SOURCES = "sources"
GF_RETRIEVAL = "retrieval"

STAGE1_ADD_KEYS: Tuple[str, ...] = (GF_CONTEXT, GF_SOURCES, GF_RETRIEVAL)
STAGE1_REQUIRED_KEYS: Tuple[str, ...] = STAGE0_REQUIRED_KEYS + STAGE1_ADD_KEYS

# retrieval inner keys
GF_USED = "used"
GF_RETRIEVED_COUNT = "retrieved_count"
GF_TOP_K = "top_k"
GF_THRESHOLD = "threshold"

RETRIEVAL_KEYS: Tuple[str, ...] = (
    GF_USED,
    GF_RETRIEVED_COUNT,
    GF_TOP_K,
    GF_THRESHOLD,
    GF_KNOWLEDGE_IDS,
)

# ---- Stage 2: build_messages adds ----
GF_MESSAGES = "messages"
STAGE2_ADD_KEYS: Tuple[str, ...] = (GF_MESSAGES,)
STAGE2_REQUIRED_KEYS: Tuple[str, ...] = STAGE1_REQUIRED_KEYS + STAGE2_ADD_KEYS

# ---- Stage 3: call_llm adds ----
GF_RAW_TEXT = "raw_text"
GF_TOKEN_USAGE = "token_usage"
GF_LATENCY_MS = "latency_ms"
GF_MODEL_NAME = "model_name"

STAGE3_ADD_KEYS: Tuple[str, ...] = (GF_RAW_TEXT, GF_TOKEN_USAGE, GF_LATENCY_MS, GF_MODEL_NAME)
STAGE3_REQUIRED_KEYS: Tuple[str, ...] = STAGE2_REQUIRED_KEYS + STAGE3_ADD_KEYS

# ---- Stage 4: parse_output adds ----
GF_TEXT = "text"
STAGE4_ADD_KEYS: Tuple[str, ...] = (GF_TEXT,)
STAGE4_REQUIRED_KEYS: Tuple[str, ...] = STAGE3_REQUIRED_KEYS + STAGE4_ADD_KEYS

# ---- Stage 5: normalize_response output keys (최종 응답 계약) ----
FINAL_REQUIRED_KEYS: Tuple[str, ...] = (
    GF_TEXT,
    GF_SOURCES,
    GF_RETRIEVAL,
    GF_TOKEN_USAGE,
    GF_LATENCY_MS,
    GF_MODEL_NAME,
)


# =========================
# TypedDict (optional but recommended)
# =========================

class TraceDict(TypedDict, total=False):
    run_id: str
    chain_version: str


class RetrievalDict(TypedDict):
    used: bool
    retrieved_count: int
    top_k: Optional[int]
    threshold: Optional[float]
    knowledge_ids: List[int]


class Stage0Out(TypedDict):
    prompt: str
    history: MessageList
    session_id: Optional[int]
    class_id: Optional[int]
    knowledge_ids: List[int]
    style_params: JSONDict
    generation_params: JSONDict
    model_names: Optional[List[str]]
    policy_flags: Optional[JSONDict]


class Stage1Out(Stage0Out):
    context: str
    sources: List[JSONDict]
    retrieval: RetrievalDict


class Stage2Out(Stage1Out):
    messages: MessageList


class Stage3Out(Stage2Out):
    raw_text: str
    token_usage: Optional[TokenUsage]
    latency_ms: Optional[int]
    model_name: str


class Stage4Out(Stage3Out):
    text: str


class FinalOut(TypedDict):
    text: str
    sources: List[JSONDict]
    retrieval: RetrievalDict
    token_usage: Optional[TokenUsage]
    latency_ms: Optional[int]
    model_name: str


# =========================
# Fail-fast guards
# =========================

class ContractError(RuntimeError):
    """Raised when chain stage contract is violated."""


def ensure_dict(stage: str, v: Any) -> Dict[str, Any]:
    """
    stage 함수 반환값이 dict인지 강제.
    RunnableLambda 단계에서 이거로 감싸면 "list/string 반환" 같은 실수를 즉시 잡음.
    """
    if not isinstance(v, dict):
        raise ContractError(f"[{stage}] must return dict, got: {type(v).__name__}")
    return v


def require_keys(stage: str, d: Mapping[str, Any], keys: Iterable[str]) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ContractError(f"[{stage}] missing keys: {missing}")


def require_retrieval_keys(stage: str, d: Mapping[str, Any]) -> None:
    """
    retrieval dict 내부 키 강제.
    stage1/5에서 retrieval이 항상 디버깅 가능한 형태인지 보장.
    """
    if GF_RETRIEVAL not in d or not isinstance(d.get(GF_RETRIEVAL), dict):
        raise ContractError(f"[{stage}] '{GF_RETRIEVAL}' must be a dict")
    require_keys(f"{stage}.retrieval", d[GF_RETRIEVAL], RETRIEVAL_KEYS)  # type: ignore[arg-type]


def validate_stage0(d: Mapping[str, Any]) -> None:
    require_keys("stage0", d, STAGE0_REQUIRED_KEYS)


def validate_stage1(d: Mapping[str, Any]) -> None:
    require_keys("stage1", d, STAGE1_REQUIRED_KEYS)
    require_retrieval_keys("stage1", d)


def validate_stage2(d: Mapping[str, Any]) -> None:
    require_keys("stage2", d, STAGE2_REQUIRED_KEYS)


def validate_stage3(d: Mapping[str, Any]) -> None:
    require_keys("stage3", d, STAGE3_REQUIRED_KEYS)


def validate_stage4(d: Mapping[str, Any]) -> None:
    require_keys("stage4", d, STAGE4_REQUIRED_KEYS)


def validate_final(d: Mapping[str, Any]) -> None:
    require_keys("final", d, FINAL_REQUIRED_KEYS)
    require_retrieval_keys("final", d)
