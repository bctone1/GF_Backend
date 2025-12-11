# langchain_service/llm/setup.py
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Dict, List

from langchain_openai import ChatOpenAI
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

# OpenAI 공식 클라이언트 (token_usage, latency 계산용)
try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None  # type: ignore


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

        # 1) 문자열
        if isinstance(obj, str):
            s = obj.strip()
            if s:
                buf.append(s)
            return

        # 2) 리스트/튜플
        if isinstance(obj, (list, tuple)):
            for item in obj:
                _collect_text(item, buf, depth + 1, max_depth)
            return

        # 3) dict → 의미 있는 키들만 우선적으로 탐색
        if isinstance(obj, dict):
            for key in ("text", "content", "output_text", "value"):
                if key in obj:
                    _collect_text(obj[key], buf, depth + 1, max_depth)
            return

        # 4) SDK 객체류: text / content / output_text / value 속성만 추적
        for attr in ("text", "content", "output_text", "value"):
            if hasattr(obj, attr):
                try:
                    val = getattr(obj, attr)
                except Exception:
                    continue
                _collect_text(val, buf, depth + 1, max_depth)

    # ---------- 여기서부터 실제 추출 ----------
    if not getattr(resp, "choices", None):
        return ""

    choice = resp.choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        return ""

    collected: List[str] = []

    # 1차: message.content 에서 추출
    try:
        content = getattr(message, "content", None)
    except Exception:
        content = None
    _collect_text(content, collected)

    # 2차: 비어 있으면 message.model_dump() 결과에서 추출
    if not collected:
        msg_dict = None
        try:
            msg_dict = message.model_dump(exclude_none=True)
        except Exception:
            if isinstance(message, dict):
                msg_dict = message
        if isinstance(msg_dict, dict):
            _collect_text(msg_dict, collected)

    # 3차: 그래도 없으면 resp.model_dump() 전체에서 추출
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
    Responses API 응답(Response 객체)에서 텍스트만 추출.
    - resp.output[*].content[*].text.value 형태를 최대한 따라가서 수집
    """

    def _collect_text(obj: Any, buf: List[str], depth: int = 0, max_depth: int = 8) -> None:
        if obj is None or depth > max_depth:
            return

        # 문자열
        if isinstance(obj, str):
            s = obj.strip()
            if s:
                buf.append(s)
            return

        # list/tuple
        if isinstance(obj, (list, tuple)):
            for item in obj:
                _collect_text(item, buf, depth + 1, max_depth)
            return

        # dict
        if isinstance(obj, dict):
            # Responses 구조에서 자주 나오는 키들 우선
            for key in ("text", "value", "content", "output_text"):
                if key in obj:
                    _collect_text(obj[key], buf, depth + 1, max_depth)
            # 그 외 나머지도 한 번 쭉 훑기
            for v in obj.values():
                _collect_text(v, buf, depth + 1, max_depth)
            return

        # SDK 객체류: text / value / content / output_text 속성 재귀 탐색
        for attr in ("text", "value", "content", "output_text"):
            if hasattr(obj, attr):
                try:
                    val = getattr(obj, attr)
                except Exception:
                    continue
                _collect_text(val, buf, depth + 1, max_depth)

    collected: List[str] = []

    # 보통 resp.output 이 리스트
    outputs = getattr(resp, "output", None)
    if outputs is None:
        outputs = getattr(resp, "outputs", None)

    if outputs is not None:
        _collect_text(outputs, collected)
    else:
        # 그래도 없으면 resp 전체에서 한 번 시도
        _collect_text(resp, collected)

    return "\n".join(collected).strip()


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
    **kwargs: Any,
) -> LLMCallResult:
    """
    실습 세션에서 사용할 공통 LLM 호출기.

    - input: OpenAI 스타일 messages 리스트
      예) [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    - output: LLMCallResult(text, token_usage, latency_ms, raw)
    """
    provider, resolved_model = _resolve_provider_and_model(provider, model)

    # ------------------------- OpenAI / Friendli(EXAONE) : OpenAI 호환 -------------------------
    if provider in ("openai", "friendli", "lg", "lgai", "exaone"):
        if OpenAIClient is None:
            raise RuntimeError(
                "openai 패키지가 설치되어 있지 않습니다. 'pip install openai' 후 다시 시도하세요."
            )

        if provider == "openai":
            key = _pick_key(
                api_key,
                getattr(config, "OPENAI_API", None),
                os.getenv("OPENAI_API"),
                os.getenv("OPENAI_API_KEY"),
            )
            base_url = None
            provider_name = "openai"
        else:
            key = _pick_key(
                api_key,
                getattr(config, "FRIENDLI_API", None),
                getattr(config, "FRIENDLI_TOKEN", None),
                os.getenv("FRIENDLI_API"),
                os.getenv("FRIENDLI_TOKEN"),
            )
            base_url = getattr(config, "FRIENDLI_BASE_URL", None) or getattr(
                config, "EXAONE_URL", None
            )
            provider_name = "friendli"

        if not key:
            if provider_name == "openai":
                raise RuntimeError("OPENAI_API/OPENAI_API_KEY가 설정되지 않았습니다.")
            else:
                raise RuntimeError(
                    "Friendli/EXAONE API 키가 설정되지 않았습니다. "
                    "FRIENDLI_API 또는 FRIENDLI_TOKEN을 설정하세요."
                )

        client = OpenAIClient(api_key=key, base_url=base_url)

        # --- 파라미터 매핑 ---
        base_kwargs: Dict[str, Any] = dict(kwargs)

        lm = resolved_model.lower()
        # GPT-5 계열: temperature/top_p/penalty 옵션 미지원 → 제거
        is_gpt5_family = provider_name == "openai" and lm.startswith("gpt-5")

        if is_gpt5_family:
            for k in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
                base_kwargs.pop(k, None)
        else:
            if "temperature" not in base_kwargs and temperature is not None:
                base_kwargs["temperature"] = temperature

        # max_tokens 매핑 (OpenAI vs Friendli, GPT-5 Responses 고려)
        if max_tokens is not None:
            if provider_name == "openai":
                if is_gpt5_family:
                    # Responses API용
                    base_kwargs["max_output_tokens"] = max_tokens
                else:
                    # chat.completions용
                    base_kwargs["max_completion_tokens"] = max_tokens
            else:
                # Friendli(OpenAI 호환)는 여전히 max_tokens 사용
                base_kwargs["max_tokens"] = max_tokens

        # ===== GPT-5 계열: Responses API 사용 =====
        if is_gpt5_family:
            # messages → Responses API input 포맷으로 그대로 전달 (SDK가 변환해줌)
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
                    "provider": provider_name,
                    "model": resolved_model,
                    "prompt_tokens": getattr(usage_obj, "input_tokens", None),
                    "completion_tokens": getattr(usage_obj, "output_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }

            return LLMCallResult(
                text=text,
                token_usage=token_usage,
                latency_ms=latency_ms,
                raw=resp,
            )

        # ===== 나머지 모델: 기존처럼 chat.completions 사용 =====
        start = time.perf_counter()
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
            prompt_tokens = getattr(usage_obj, "prompt_tokens", None) or getattr(
                usage_obj, "input_tokens", None
            )
            completion_tokens = getattr(
                usage_obj, "completion_tokens", None
            ) or getattr(usage_obj, "output_tokens", None)
            total_tokens = getattr(usage_obj, "total_tokens", None)
            token_usage = {
                "provider": provider_name,
                "model": resolved_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

        return LLMCallResult(
            text=text,
            token_usage=token_usage,
            latency_ms=latency_ms,
            raw=resp,
        )

    # ------------------------- 기타(provider별 세부 usage 미지원) -------------------------
    start = time.perf_counter()
    llm = get_llm(
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        temperature=temperature,
        **kwargs,
    )

    # messages → 하나의 프롬프트 문자열로 단순 변환
    if len(messages) == 1 and messages[0].get("role") == "user":
        prompt = messages[0]["content"]
    else:
        prompt = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
        )

    res = llm.invoke(prompt)
    latency_ms = int((time.perf_counter() - start) * 1000)

    text = getattr(res, "content", None) or str(res)

    return LLMCallResult(
        text=text,
        token_usage=None,
        latency_ms=latency_ms,
        raw=res,
    )


# =========================================================
# 기존: LangChain LLM 인스턴스 생성기
# =========================================================
def get_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    **kwargs: Any,
):
    """
    LLM 인스턴스 생성기. streaming=True 전달 시 스트리밍 가능.

    지원 provider 예시:
      - "openai"        : gpt-4o-mini 등
      - "friendli" / "lg" / "exaone" : exaone-4.0 (Friendli OpenAI 호환)
      - "anthropic"     : claude-3-* 계열
      - "google"        : gemini-* 계열
    """
    provider, resolved_model = _resolve_provider_and_model(provider, model)

    # ------------------------- OpenAI -------------------------
    if provider == "openai":
        key = _pick_key(
            api_key,
            getattr(config, "OPENAI_API", None),
            os.getenv("OPENAI_API"),
            os.getenv("OPENAI_API"),
        )
        if not key:
            raise RuntimeError("OPENAI_API/OPENAI_API_KEY가 설정되지 않았습니다.")
        return ChatOpenAI(
            model=resolved_model,
            api_key=key,
            temperature=temperature,
            **kwargs,
        )

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
            raise RuntimeError(
                "Friendli/EXAONE API 키가 설정되지 않았습니다. "
                "FRIENDLI_API 또는 FRIENDLI_TOKEN을 설정하세요."
            )

        base_url = getattr(config, "FRIENDLI_BASE_URL", None) or getattr(
            config, "EXAONE_URL", None
        )

        return ChatOpenAI(
            model=resolved_model,
            api_key=key,
            base_url=base_url,
            temperature=temperature,
            **kwargs,
        )

    # ------------------------- Anthropic (Claude) -------------------------
    elif provider in ("anthropic", "claude"):
        if ChatAnthropic is None:
            raise RuntimeError(
                "Anthropic 사용을 위해서는 'langchain-anthropic' 패키지가 필요합니다."
            )

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

        return ChatAnthropic(
            model=use_model,
            api_key=key,
            temperature=temperature,
            **kwargs,
        )

    # ------------------------- Google (Gemini) -------------------------
    elif provider in ("google", "gemini"):
        if ChatGoogleGenerativeAI is None:
            raise RuntimeError(
                "Google Gemini 사용을 위해서는 'langchain-google-genai' 패키지가 필요합니다."
            )

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

        return ChatGoogleGenerativeAI(
            model=use_model,
            api_key=key,
            temperature=temperature,
            **kwargs,
        )

    # ------------------------- 기타 미지원 -------------------------
    else:
        raise ValueError(f"지원되지 않는 제공자: {provider}")


def get_backend_agent(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
):
    """
    백엔드용 Agent LLM.
    - 기본적으로 get_llm()을 감싸되, 키 우선순위를 조금 다르게 가져갈 수 있음.
    """
    provider = (provider or getattr(config, "LLM_PROVIDER", "openai")).lower()

    # 기본 backend 모델: 없으면 LLM_MODEL → DEFAULT_CHAT_MODEL 순서
    default_chat_model = getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini")
    default_llm_model = getattr(config, "LLM_MODEL", default_chat_model)
    use_model = model or default_llm_model

    # OpenAI: EMBEDDING_API > OPENAI_API 순으로 키 선택
    if provider == "openai":
        key = _pick_key(
            getattr(config, "EMBEDDING_API", None),
            getattr(config, "OPENAI_API", None),
            os.getenv("OPENAI_API"),
            os.getenv("OPENAI_API"),
        )
        if not key:
            raise RuntimeError("EMBEDDING_API/OPENAI_API 키가 설정되지 않았습니다.")

        return get_llm(
            provider="openai",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    # Friendli / LG / EXAONE
    elif provider in ("friendli", "lg", "lgai", "exaone"):
        key = _pick_key(
            getattr(config, "FRIENDLI_API", None),
            getattr(config, "FRIENDLI_TOKEN", None),
            os.getenv("FRIENDLI_API"),
            os.getenv("FRIENDLI_TOKEN"),
        )
        if not key:
            raise RuntimeError("FRIENDLI_API/FRIENDLI_TOKEN 키가 설정되지 않았습니다.")

        return get_llm(
            provider="friendli",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    # Anthropic
    elif provider in ("anthropic", "claude"):
        key = _pick_key(
            getattr(config, "CLAUDE_API", None),
            os.getenv("CLAUDE_API"),
        )
        if not key:
            raise RuntimeError("CLAUDE_API(Anthropic) 키가 설정되지 않았습니다.")

        return get_llm(
            provider="anthropic",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    # Google (Gemini)
    elif provider in ("google", "gemini"):
        key = _pick_key(
            getattr(config, "GOOGLE_API", None),
            os.getenv("GOOGLE_API"),
        )
        if not key:
            raise RuntimeError("GOOGLE_API(Gemini) 키가 설정되지 않았습니다.")

        return get_llm(
            provider="google",
            model=use_model,
            api_key=key,
            **kwargs,
        )

    else:
        raise ValueError(f"지원되지 않는 제공자: {provider}")
