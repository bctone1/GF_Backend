# langchain_service/llm/setup.py
import os
import time
import threading
import inspect
from dataclasses import dataclass
from typing import Any, Optional, Dict, List, Iterable, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

import core.config as config
from pydantic import SecretStr  # 아직은 안씀 추후 사용

# 선택적으로 Anthropic / Google 지원 (LangChain용)
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # 라이브러리 없으면 None으로 두고 런타임에 에러 안내
    ChatAnthropic = None  # type: ignore

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore

# OpenAI 공식 클라이언트 (token_usage, latency 계산용 + GPT-5 Responses)
try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None  # type: ignore



# =========================================================
# globals: defaults / caches
# =========================================================
_DEFAULT_TIMEOUT_S: float = float(getattr(config, "LLM_TIMEOUT_S", 60))
_DEFAULT_MAX_RETRIES: int = int(getattr(config, "LLM_MAX_RETRIES", 1))

_OPENAI_CLIENT_CACHE: Dict[Tuple[str, Optional[str], float, int], Any] = {}
_OPENAI_CLIENT_LOCK = threading.Lock()
_OPENAI_CLIENT_CACHE_MAX = 32

_LLM_CACHE: Dict[Tuple[Any, ...], Any] = {}
_LLM_CACHE_LOCK = threading.Lock()
_LLM_CACHE_MAX = 64


@dataclass
class LLMCallResult:
    """
    LLM 한 번 호출 결과를 통일된 형태로 반환하기 위한 DTO.
    - text: 최종 응답 텍스트
    - token_usage: provider별 token 사용량 dict (없으면 None)
    - latency_ms: 요청~응답까지 걸린 시간(ms)
    - raw: provider별 원본 응답 객체
    """
    text: str
    token_usage: Optional[Dict[str, Any]]
    latency_ms: int
    raw: Any


def _pick_key(*candidates: Optional[str]) -> Optional[str]:
    for key in candidates:
        if key:
            return key
    return None


def _filter_kwargs_for(cls: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    provider별 LangChain 클래스가 받지 못하는 kwargs 때문에 터지는 걸 막기 위해
    __init__ 시그니처 기준으로 필터링.
    """
    try:
        params = inspect.signature(cls.__init__).parameters
        allowed = set(params.keys())
        allowed.discard("self")
        return {k: v for k, v in kwargs.items() if k in allowed}
    except Exception:
        return kwargs


def _to_lc_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role in ("assistant", "ai"):
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _resolve_provider_and_model(
    provider: Optional[str],
    model: Optional[str],
) -> tuple[str, str]:
    """
    provider/model 자동 추론 로직을 get_llm, call_llm_chat에서 공통 사용.
    """
    # 1) 기본 모델
    default_chat_model = getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini")
    default_llm_model = getattr(config, "LLM_MODEL", default_chat_model)
    resolved_model = model or default_llm_model

    # 2) provider 자동 추론
    if not provider:
        practice_models = getattr(config, "PRACTICE_MODELS", {}) or {}
        conf = practice_models.get(resolved_model)
        if isinstance(conf, dict) and conf.get("provider"):
            provider = str(conf["provider"]).lower()
        else:
            lm = resolved_model.lower()
            if lm.startswith("claude"):
                provider = "anthropic"
            elif lm.startswith("gemini"):
                provider = "google"
            elif "exaone" in lm or "friendli" in lm or lm.startswith("lg"):
                provider = "friendli"
            else:
                provider = getattr(config, "LLM_PROVIDER", "openai")

    return provider.lower(), resolved_model


def _extract_text_from_openai_chat(resp: Any, model_name: str) -> str:
    """
    OpenAI chat.completions 응답에서 사람이 읽을 텍스트를 최대한 뽑아낸다.
    - content 가 str / list / dict / SDK 객체일 때 모두 처리
    - text / content / output_text / value 필드 위주로 재귀적으로 탐색
    """

    def _collect_text(obj: Any, buf: List[str], depth: int = 0, max_depth: int = 8) -> None:
        if obj is None or depth > max_depth:
            return

        if isinstance(obj, str):
            s = obj.strip()
            if s:
                buf.append(s)
            return

        if isinstance(obj, (list, tuple)):
            for item in obj:
                _collect_text(item, buf, depth + 1, max_depth)
            return

        if isinstance(obj, dict):
            for key in ("text", "content", "output_text", "value"):
                if key in obj:
                    _collect_text(obj[key], buf, depth + 1, max_depth)
            return

        for attr in ("text", "content", "output_text", "value"):
            if hasattr(obj, attr):
                try:
                    val = getattr(obj, attr)
                except Exception:
                    continue
                _collect_text(val, buf, depth + 1, max_depth)

    if not getattr(resp, "choices", None):
        return ""

    choice = resp.choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        return ""

    collected: List[str] = []

    try:
        content = getattr(message, "content", None)
    except Exception:
        content = None
    _collect_text(content, collected)

    if not collected:
        msg_dict = None
        try:
            msg_dict = message.model_dump(exclude_none=True)
        except Exception:
            if isinstance(message, dict):
                msg_dict = message
        if isinstance(msg_dict, dict):
            _collect_text(msg_dict, collected)

    if not collected:
        resp_dict = None
        try:
            resp_dict = resp.model_dump(exclude_none=True)  # type: ignore[attr-defined]
        except Exception:
            if isinstance(resp, dict):
                resp_dict = resp
        if isinstance(resp_dict, dict):
            _collect_text(resp_dict, collected)

    text = "\n".join(collected).strip()
    return text


def _extract_text_from_response(resp: Any) -> str:
    """
    OpenAI Responses API 응답에서 텍스트만 깔끔하게 추출.
    """
    parts: List[str] = []

    outputs = getattr(resp, "output", None)
    if outputs is None:
        outputs = getattr(resp, "outputs", None)
    if outputs is None:
        return ""

    if not isinstance(outputs, (list, tuple)):
        outputs = [outputs]

    for out in outputs:
        if isinstance(out, dict):
            content_list = out.get("content") or []
        else:
            content_list = getattr(out, "content", None) or []

        for c in content_list:
            if isinstance(c, dict):
                c_type = c.get("type")
                if c_type == "reasoning":
                    continue

                text_block = c.get("text")
                val: Any = None

                if isinstance(text_block, dict):
                    val = text_block.get("value") or text_block.get("text")
                elif isinstance(text_block, str):
                    val = text_block
                else:
                    val = text_block

                if isinstance(val, str):
                    s = val.strip()
                    if s:
                        parts.append(s)
                elif isinstance(val, dict):
                    inner_val = val.get("value") or val.get("text")
                    if isinstance(inner_val, str):
                        s = inner_val.strip()
                        if s:
                            parts.append(s)
                continue

            text_obj = getattr(c, "text", None)
            if text_obj is None:
                continue

            val: Any = None
            if isinstance(text_obj, dict):
                val = text_obj.get("value") or text_obj.get("text")
            else:
                v = getattr(text_obj, "value", None)
                if isinstance(v, str):
                    val = v
                else:
                    try:
                        val = str(text_obj)
                    except Exception:
                        val = None

            if isinstance(val, str):
                s = val.strip()
                if s and not s.startswith("rs_"):
                    parts.append(s)

    text = "\n\n".join(parts).strip()
    if text:
        return text

    # fallback (최소)
    try:
        resp_dict = resp.model_dump(exclude_none=True)  # type: ignore[attr-defined]
    except Exception:
        resp_dict = resp if isinstance(resp, dict) else None
    if not isinstance(resp_dict, dict):
        return ""

    def _collect_all_strings(o: Any, buf: List[str], depth: int = 0, max_depth: int = 6):
        if o is None or depth > max_depth:
            return
        if isinstance(o, str):
            s = o.strip()
            if not s:
                return
            if s.startswith("rs_") and len(s) > 10:
                return
            if s in {"reasoning", "output_text"}:
                return
            buf.append(s)
            return
        if isinstance(o, (list, tuple)):
            for item in o:
                _collect_all_strings(item, buf, depth + 1, max_depth)
            return
        if isinstance(o, dict):
            for k in ("output", "outputs", "content", "text", "value"):
                if k in o:
                    _collect_all_strings(o[k], buf, depth + 1, max_depth)
            return

    buf: List[str] = []
    _collect_all_strings(resp_dict.get("output") or resp_dict.get("outputs"), buf)
    return "\n\n".join(buf).strip()


def _get_openai_client_cached(
    *,
    api_key: str,
    base_url: Optional[str] = None,
    timeout_s: float,
    max_retries: int,
) -> Any:
    """
    OpenAI 공식 SDK 클라이언트를 재사용(keep-alive)해서 꼬리 지연을 줄이기.
    - key에는 api_key 자체를 쓰긴 하는데, 외부로 노출만 안 하면 됨(메모리 내부).
    """
    if OpenAIClient is None:
        raise RuntimeError("openai 패키지가 설치되어 있지 않습니다. 'pip install openai' 후 다시 시도하세요.")

    cache_key = (api_key, base_url, float(timeout_s), int(max_retries))
    with _OPENAI_CLIENT_LOCK:
        cached = _OPENAI_CLIENT_CACHE.get(cache_key)
        if cached is not None:
            return cached

        client = OpenAIClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_s,
            max_retries=max_retries,
        )

        _OPENAI_CLIENT_CACHE[cache_key] = client
        if len(_OPENAI_CLIENT_CACHE) > _OPENAI_CLIENT_CACHE_MAX:
            _OPENAI_CLIENT_CACHE.pop(next(iter(_OPENAI_CLIENT_CACHE)))
        return client


# =========================================================
# Streaming: TTFT 개선용 (FastAPI StreamingResponse/SSE에서 사용)
# =========================================================
def iter_llm_chat_stream(
    messages: List[Dict[str, str]],
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout_s: Optional[float] = None,
    max_retries: Optional[int] = None,
    **kwargs: Any,
) -> Iterable[str]:
    """
    토큰(또는 chunk) 스트리밍 제너레이터.
    - 실제 HTTP 스트리밍은 엔드포인트에서 StreamingResponse로 감싸야 함.
    - usage/latency는 스트리밍 중간에는 안정적으로 못 얻는 provider가 많아서,
      여기서는 "TTFT 개선" 목적에 집중.
    """
    provider, resolved_model = _resolve_provider_and_model(provider, model)

    # GPT-5 Responses API는 여기선 스트리밍 구현을 강제하지 않고(버전/SDK 차이 큼),
    # 최소한으로 "한 번에" 반환하도록 fallback.
    if provider == "openai" and resolved_model.lower().startswith("gpt-5"):
        r = call_llm_chat(
            messages=messages,
            provider=provider,
            model=resolved_model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            max_retries=max_retries,
            **kwargs,
        )
        if r.text:
            yield r.text
        return

    lc_kwargs: Dict[str, Any] = dict(kwargs)
    lc_kwargs["streaming"] = True
    if max_tokens is not None and "max_tokens" not in lc_kwargs:
        lc_kwargs["max_tokens"] = max_tokens

    llm = get_llm(
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        temperature=temperature,
        timeout_s=timeout_s,
        max_retries=max_retries,
        **lc_kwargs,
    )

    lc_messages = _to_lc_messages(messages)

    collected_parts: List[str] = []
    try:
        for chunk in llm.stream(lc_messages):
            part = getattr(chunk, "content", None)
            if part:
                collected_parts.append(part)
                yield part
    except Exception as e:
        raise


# =========================================================
# 실습용: 1회 LLM 호출 + token_usage/latency 계산 헬퍼
# =========================================================
def call_llm_chat(
    messages: List[Dict[str, str]],
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout_s: Optional[float] = None,
    max_retries: Optional[int] = None,
    **kwargs: Any,
) -> LLMCallResult:
    """
    실습 세션에서 사용할 공통 LLM 호출기.
    """
    provider, resolved_model = _resolve_provider_and_model(provider, model)
    lm = resolved_model.lower()

    # defaults (명시 없으면 config 기반)
    timeout_s = float(timeout_s if timeout_s is not None else kwargs.pop("timeout_s", _DEFAULT_TIMEOUT_S))
    if "timeout" in kwargs and timeout_s == _DEFAULT_TIMEOUT_S:
        # 호출자가 timeout= 를 넣었으면 그걸 우선
        try:
            timeout_s = float(kwargs.pop("timeout"))
        except Exception:
            kwargs.pop("timeout", None)

    max_retries = int(max_retries if max_retries is not None else kwargs.pop("max_retries", _DEFAULT_MAX_RETRIES))

    # ------------------------- OpenAI GPT-5: Responses API -------------------------
    if provider == "openai" and lm.startswith("gpt-5"):
        key = _pick_key(
            api_key,
            getattr(config, "OPENAI_API", None),
            getattr(config, "OPENAI_API_KEY", None),
            os.getenv("OPENAI_API"),
            os.getenv("OPENAI_API_KEY"),
        )
        if not key:
            raise RuntimeError("OPENAI_API/OPENAI_API_KEY가 설정되지 않았습니다.")

        client = _get_openai_client_cached(
            api_key=key,
            base_url=None,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )

        base_kwargs: Dict[str, Any] = dict(kwargs)
        for k in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
            base_kwargs.pop(k, None)

        if max_tokens is not None:
            base_kwargs["max_output_tokens"] = max_tokens

        try:
            start = time.perf_counter()
            resp = client.responses.create(
                model=resolved_model,
                input=messages,
                **base_kwargs,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            text = _extract_text_from_response(resp)
            usage_obj = getattr(resp, "usage", None)

            token_usage: Optional[Dict[str, Any]] = None
            if usage_obj is not None:
                token_usage = {
                    "provider": "openai",
                    "model": resolved_model,
                    "prompt_tokens": getattr(usage_obj, "input_tokens", None),
                    "completion_tokens": getattr(usage_obj, "output_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }

            return LLMCallResult(text=text, token_usage=token_usage, latency_ms=latency_ms, raw=resp)

        except Exception as e:
            raise

    # ------------------------- Friendli / EXAONE: OpenAI 호환 엔드포인트 -------------------------
    if provider in ("friendli", "lg", "lgai", "exaone"):
        key = _pick_key(
            api_key,
            getattr(config, "FRIENDLI_API", None),
            getattr(config, "FRIENDLI_TOKEN", None),
            os.getenv("FRIENDLI_API"),
            os.getenv("FRIENDLI_TOKEN"),
        )
        if not key:
            raise RuntimeError("Friendli/EXAONE API 키가 설정되지 않았습니다. FRIENDLI_API 또는 FRIENDLI_TOKEN을 설정하세요.")

        base_url = getattr(config, "FRIENDLI_BASE_URL", None) or getattr(config, "EXAONE_URL", None)

        client = _get_openai_client_cached(
            api_key=key,
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )

        base_kwargs: Dict[str, Any] = dict(kwargs)
        if "temperature" not in base_kwargs and temperature is not None:
            base_kwargs["temperature"] = temperature
        if max_tokens is not None:
            base_kwargs["max_tokens"] = max_tokens

        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=resolved_model,
                messages=messages,
                **base_kwargs,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            usage_obj = getattr(resp, "usage", None)
            text = _extract_text_from_openai_chat(resp, resolved_model)

            token_usage: Optional[Dict[str, Any]] = None
            if usage_obj is not None:
                prompt_tokens = getattr(usage_obj, "prompt_tokens", None) or getattr(usage_obj, "input_tokens", None)
                completion_tokens = getattr(usage_obj, "completion_tokens", None) or getattr(usage_obj, "output_tokens", None)
                total_tokens = getattr(usage_obj, "total_tokens", None)
                token_usage = {
                    "provider": "friendli",
                    "model": resolved_model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }

            return LLMCallResult(text=text, token_usage=token_usage, latency_ms=latency_ms, raw=resp)
        except Exception as e:
            raise

    # ------------------------- 나머지: LangChain LLM 사용 -------------------------
    start = time.perf_counter()

    lc_kwargs: Dict[str, Any] = dict(kwargs)
    if max_tokens is not None and "max_tokens" not in lc_kwargs:
        lc_kwargs["max_tokens"] = max_tokens

    llm = get_llm(
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        temperature=temperature,
        timeout_s=timeout_s,
        max_retries=max_retries,
        **lc_kwargs,
    )

    # ✅ messages를 문자열로 뭉개지 말고 chat 메시지로 호출(정확도/일관성 + 스트리밍 호환)
    lc_messages = _to_lc_messages(messages)

    try:
        res = llm.invoke(lc_messages)
        latency_ms = int((time.perf_counter() - start) * 1000)

        text = getattr(res, "content", None) or str(res)

        token_usage: Optional[Dict[str, Any]] = None
        meta: Any = getattr(res, "usage_metadata", None)

        if not meta:
            meta = getattr(res, "response_metadata", None)
            if isinstance(meta, dict) and "token_usage" in meta and isinstance(meta["token_usage"], dict):
                meta = meta["token_usage"]

        if isinstance(meta, dict):
            prompt_tokens = meta.get("input_tokens") or meta.get("prompt_tokens")
            completion_tokens = meta.get("output_tokens") or meta.get("completion_tokens")
            total_tokens = meta.get("total_tokens")

            if any(v is not None for v in (prompt_tokens, completion_tokens, total_tokens)):
                token_usage = {
                    "provider": provider,
                    "model": resolved_model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }

        return LLMCallResult(text=text, token_usage=token_usage, latency_ms=latency_ms, raw=res)
    except Exception as e:
        raise


# =========================================================
# LangChain LLM 인스턴스 생성기 (+ retry/timeout 기본 적용 + 캐시)
# =========================================================
def get_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    timeout_s: Optional[float] = None,
    max_retries: Optional[int] = None,
    **kwargs: Any,
):
    """
    LLM 인스턴스 생성기. streaming=True 전달 시 스트리밍 가능.
    + 기본 timeout/max_retries 적용
    + 인스턴스 캐시로 커넥션 재사용(keep-alive)
    """
    provider, resolved_model = _resolve_provider_and_model(provider, model)

    timeout_s = float(timeout_s if timeout_s is not None else kwargs.pop("timeout_s", _DEFAULT_TIMEOUT_S))
    if "timeout" in kwargs and timeout_s == _DEFAULT_TIMEOUT_S:
        try:
            timeout_s = float(kwargs.pop("timeout"))
        except Exception:
            kwargs.pop("timeout", None)
    max_retries = int(max_retries if max_retries is not None else kwargs.pop("max_retries", _DEFAULT_MAX_RETRIES))

    # timeout/retry 기본 주입(이미 있으면 유지)
    kwargs.setdefault("timeout", timeout_s)
    kwargs.setdefault("max_retries", max_retries)

    streaming = bool(kwargs.get("streaming", False))
    base_url: Optional[str] = None

    # ------------------------- OpenAI -------------------------
    if provider == "openai":
        key = _pick_key(
            api_key,
            getattr(config, "OPENAI_API", None),
            getattr(config, "OPENAI_API_KEY", None),
            os.getenv("OPENAI_API"),
            os.getenv("OPENAI_API_KEY"),
        )
        if not key:
            raise RuntimeError("OPENAI_API/OPENAI_API_KEY가 설정되지 않았습니다.")

        filtered = _filter_kwargs_for(ChatOpenAI, dict(kwargs))
        cache_key = ("openai", resolved_model, key, float(temperature), streaming, tuple(sorted(filtered.items())))

        with _LLM_CACHE_LOCK:
            cached = _LLM_CACHE.get(cache_key)
            if cached is not None:
                return cached

        llm = ChatOpenAI(
            model=resolved_model,
            api_key=key,
            temperature=temperature,
            **filtered,
        )

        with _LLM_CACHE_LOCK:
            _LLM_CACHE[cache_key] = llm
            if len(_LLM_CACHE) > _LLM_CACHE_MAX:
                _LLM_CACHE.pop(next(iter(_LLM_CACHE)))
        return llm

    # ------------------------- Friendli / EXAONE -------------------------
    elif provider in ("friendli", "lg", "lgai", "exaone"):
        key = _pick_key(
            api_key,
            getattr(config, "FRIENDLI_API", None),
            getattr(config, "FRIENDLI_TOKEN", None),
            os.getenv("FRIENDLI_API"),
            os.getenv("FRIENDLI_TOKEN"),
        )
        if not key:
            raise RuntimeError("Friendli/EXAONE API 키가 설정되지 않았습니다. FRIENDLI_API 또는 FRIENDLI_TOKEN을 설정하세요.")

        base_url = getattr(config, "FRIENDLI_BASE_URL", None) or getattr(config, "EXAONE_URL", None)

        filtered = _filter_kwargs_for(ChatOpenAI, dict(kwargs))
        cache_key = ("friendli", resolved_model, key, base_url, float(temperature), streaming, tuple(sorted(filtered.items())))

        with _LLM_CACHE_LOCK:
            cached = _LLM_CACHE.get(cache_key)
            if cached is not None:
                return cached

        llm = ChatOpenAI(
            model=resolved_model,
            api_key=key,
            base_url=base_url,
            temperature=temperature,
            **filtered,
        )

        with _LLM_CACHE_LOCK:
            _LLM_CACHE[cache_key] = llm
            if len(_LLM_CACHE) > _LLM_CACHE_MAX:
                _LLM_CACHE.pop(next(iter(_LLM_CACHE)))
        return llm

    # ------------------------- Anthropic (Claude) -------------------------
    elif provider in ("anthropic", "claude"):
        if ChatAnthropic is None:
            raise RuntimeError("Anthropic 사용을 위해서는 'langchain-anthropic' 패키지가 필요합니다.")

        key = _pick_key(
            api_key,
            getattr(config, "CLAUDE_API", None),
            os.getenv("CLAUDE_API"),
        )
        if not key:
            raise RuntimeError("CLAUDE_API(Anthropic) 키가 설정되지 않았습니다.")

        anthropic_models = getattr(config, "ANTHROPIC_MODELS", "") or ""
        default_anthropic_model = (
            anthropic_models.split(",")[0].strip()
            if anthropic_models
            else "claude-3-5-sonnet-latest"
        )
        use_model = resolved_model or default_anthropic_model

        filtered = _filter_kwargs_for(ChatAnthropic, dict(kwargs))
        cache_key = ("anthropic", use_model, key, float(temperature), streaming, tuple(sorted(filtered.items())))

        with _LLM_CACHE_LOCK:
            cached = _LLM_CACHE.get(cache_key)
            if cached is not None:
                return cached

        llm = ChatAnthropic(
            model=use_model,
            api_key=key,
            temperature=temperature,
            **filtered,
        )

        with _LLM_CACHE_LOCK:
            _LLM_CACHE[cache_key] = llm
            if len(_LLM_CACHE) > _LLM_CACHE_MAX:
                _LLM_CACHE.pop(next(iter(_LLM_CACHE)))
        return llm

    # ------------------------- Google (Gemini) -------------------------
    elif provider in ("google", "gemini"):
        if ChatGoogleGenerativeAI is None:
            raise RuntimeError("Google Gemini 사용을 위해서는 'langchain-google-genai' 패키지가 필요합니다.")

        key = _pick_key(
            api_key,
            getattr(config, "GOOGLE_API", None),
            os.getenv("GOOGLE_API"),
        )
        if not key:
            raise RuntimeError("GOOGLE_API(Gemini) 키가 설정되지 않았습니다.")

        google_models = getattr(config, "GOOGLE_MODELS", "") or ""
        default_google_model = (
            google_models.split(",")[0].strip()
            if google_models
            else "gemini-2.5-flash"
        )
        use_model = resolved_model or default_google_model

        filtered = _filter_kwargs_for(ChatGoogleGenerativeAI, dict(kwargs))
        cache_key = ("google", use_model, key, float(temperature), streaming, tuple(sorted(filtered.items())))

        with _LLM_CACHE_LOCK:
            cached = _LLM_CACHE.get(cache_key)
            if cached is not None:
                return cached

        llm = ChatGoogleGenerativeAI(
            model=use_model,
            api_key=key,
            temperature=temperature,
            **filtered,
        )

        with _LLM_CACHE_LOCK:
            _LLM_CACHE[cache_key] = llm
            if len(_LLM_CACHE) > _LLM_CACHE_MAX:
                _LLM_CACHE.pop(next(iter(_LLM_CACHE)))
        return llm

    else:
        raise ValueError(f"지원되지 않는 제공자: {provider}")


def get_backend_prompt(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
):
    """
    백엔드용 Prompt LLM.
    - 기본적으로 get_llm()을 감싸되, 키 우선순위를 조금 다르게 가져갈 수 있음.
    """
    provider = (provider or getattr(config, "LLM_PROVIDER", "openai")).lower()

    default_chat_model = getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini")
    default_llm_model = getattr(config, "LLM_MODEL", default_chat_model)
    use_model = model or default_llm_model

    # OpenAI: EMBEDDING_API > OPENAI_API/OPENAI_API_KEY 순
    if provider == "openai":
        key = _pick_key(
            getattr(config, "EMBEDDING_API", None),
            getattr(config, "OPENAI_API", None),
            getattr(config, "OPENAI_API_KEY", None),
            os.getenv("OPENAI_API"),
            os.getenv("OPENAI_API_KEY"),
        )
        if not key:
            raise RuntimeError("EMBEDDING_API/OPENAI_API 키가 설정되어 있지 않습니다.")

        return get_llm(
            provider="openai",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    elif provider in ("friendli", "lg", "lgai", "exaone"):
        key = _pick_key(
            getattr(config, "FRIENDLI_API", None),
            getattr(config, "FRIENDLI_TOKEN", None),
            os.getenv("FRIENDLI_API"),
            os.getenv("FRIENDLI_TOKEN"),
        )
        if not key:
            raise RuntimeError("FRIENDLI_API/FRIENDLI_TOKEN 키가 설정되어 있지 않습니다.")

        return get_llm(
            provider="friendli",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    elif provider in ("anthropic", "claude"):
        key = _pick_key(
            getattr(config, "CLAUDE_API", None),
            os.getenv("CLAUDE_API"),
        )
        if not key:
            raise RuntimeError("CLAUDE_API(Anthropic) 키가 설정되어 있지 않습니다.")

        return get_llm(
            provider="anthropic",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    elif provider in ("google", "gemini"):
        key = _pick_key(
            getattr(config, "GOOGLE_API", None),
            os.getenv("GOOGLE_API"),
        )
        if not key:
            raise RuntimeError("GOOGLE_API(Gemini) 키가 설정되어 있지 않습니다.")

        return get_llm(
            provider="google",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    else:
        raise ValueError(f"지원되지 않는 제공자: {provider}")
