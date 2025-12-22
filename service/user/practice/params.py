# service/user/practice/params.py
from __future__ import annotations

from typing import Any, Dict

from core import config


# =========================================
# generation params 정규화 (max_completion_tokens 기준)
# - DB/서비스 전반 키 혼용 방지
# =========================================
def normalize_generation_params_dict(v: Any) -> Dict[str, Any]:
    """
    입력 dict에서 max_tokens / max_output_tokens / max_completion_tokens 혼용을 정리한다.
    정책:
      - 내부 표준 키는 max_completion_tokens
      - max_tokens는 호환용으로 max_completion_tokens와 동일 값으로 맞춘다
    """
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
    if (
        isinstance(mct, int)
        and mct > 0
        and isinstance(mt, int)
        and mt > 0
        and mct != mt
    ):
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct

    return out


# =========================================
# 기본 generation params
# =========================================
def get_default_generation_params() -> Dict[str, Any]:
    """
    core.config.PRACTICE_DEFAULT_GENERATION이 dict면 그대로 사용(정규화 포함).
    없으면 안전한 fallback 기본값을 제공.
    """
    base = getattr(config, "PRACTICE_DEFAULT_GENERATION", None)
    if isinstance(base, dict):
        return normalize_generation_params_dict(dict(base))

    return normalize_generation_params_dict(
        {
            "temperature": 0.7,
            "top_p": 0.9,
            "response_length_preset": None,
            "max_completion_tokens": 1024,
        }
    )


# =========================================
# 모델별 출력 토큰 상한 추출
# =========================================
def get_model_max_output_tokens(
    *,
    logical_model_name: str,
    provider: str | None,
    real_model_name: str,
) -> int | None:
    """
    1) runtime config(core.config.PRACTICE_MODELS)에서 모델별 max_output_tokens 우선
    2) 혹시 config 누락돼도 안전하게 provider/model별 하드 가드 적용(최소)
    """
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    conf = practice_models.get(logical_model_name) or {}
    if isinstance(conf, dict):
        mt = conf.get("max_output_tokens") or conf.get("max_completion_tokens") or conf.get("max_tokens")
        if isinstance(mt, int) and mt > 0:
            return int(mt)

    # 최소 하드 가드(필요한 것만)
    if (provider or "").lower() == "anthropic":
        if real_model_name == "claude-3-haiku-20240307":
            return 4096

    return None


# =========================================
# max_completion_tokens 상한 강제
# =========================================
def clamp_generation_params_max_tokens(
    gp: Dict[str, Any],
    *,
    max_out: int | None,
) -> Dict[str, Any]:
    """
    max_out이 있으면 gp["max_completion_tokens"]가 이를 초과하지 않도록 clamp.
    또한 호환을 위해 max_tokens도 동일 값으로 맞춘다.
    """
    if not max_out or max_out <= 0:
        return gp

    out = dict(gp)

    mct = out.get("max_completion_tokens")
    try:
        imct = int(mct) if mct is not None else None
    except Exception:
        imct = None

    if imct is not None and imct > max_out:
        out["max_completion_tokens"] = max_out
        out["max_tokens"] = max_out  # call_llm_chat이 max_tokens로 넘길 수도 있어서 같이 맞춤

    return out
