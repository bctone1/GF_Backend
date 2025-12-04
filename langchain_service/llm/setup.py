# langchain_service/llm/setup.py
import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI
import core.config as config
from pydantic import SecretStr  # 아직은 안씀 추후 사용

# 선택적으로 Anthropic / Google 지원
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # 라이브러리 없으면 None으로 두고 런타임에 에러 안내
    ChatAnthropic = None  # type: ignore

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore



def _pick_key(*candidates: Optional[str]) -> Optional[str]:
    for key in candidates:
        if key:
            return key
    return None


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
    # 1) 기본 모델 결정
    default_chat_model = getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini")
    default_llm_model = getattr(config, "LLM_MODEL", default_chat_model)
    resolved_model = model or default_llm_model

    # 2) provider 자동 추론 (명시 안 한 경우)
    if not provider:
        # 2-1) PRACTICE_MODELS 에 설정된 provider 우선
        practice_models = getattr(config, "PRACTICE_MODELS", {}) or {}
        conf = practice_models.get(resolved_model)
        if isinstance(conf, dict) and conf.get("provider"):
            provider = str(conf["provider"]).lower()
        else:
            # 2-2) 모델 이름으로 휴리스틱
            lm = resolved_model.lower()
            if lm.startswith("claude"):
                provider = "anthropic"
            elif lm.startswith("gemini"):
                provider = "google"
            elif "exaone" in lm or "friendli" in lm or lm.startswith("lg"):
                provider = "friendli"
            else:
                provider = getattr(config, "LLM_PROVIDER", "openai")

    provider = provider.lower()

    # 3) provider별 분기
    # ------------------------- OpenAI -------------------------
    if provider is None or provider.lower() in ("openai"):
        key = _pick_key(api_key, getattr(config, "OPENAI_API", None), os.getenv("OPENAI_API_KEY"))
        if not key:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            api_key=key,
            temperature=temperature,
            **kwargs,
        )

    # ------------------------- Friendli / EXAONE -------------------------
    elif provider in ("friendli", "lg", "lgai", "exaone", "EXAONE"):
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
        # model 인자를 직접 넘기면 그걸 우선 사용
        use_model = model or default_anthropic_model

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
        use_model = model or default_google_model

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
    elif provider in ("friendli", "lg", "lgai", "exaone", "EXAONE"):
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
