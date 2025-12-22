# langchain_service/chain/style.py
from __future__ import annotations

from typing import Any, Dict

STYLE_MAP: Dict[str, str] = {
    "friendly": (
        "친절하고 쉽게, 핵심만. 모르면 모른다고 말해."
    ),
    "concise": (
        "짧게, 핵심만. 목록으로."
    ),
    "tutor": (
        "쉽게 설명+짧은 예시+힌트."
    ),
}


def build_system_prompt(style: str = "friendly", **policy_flags: Any) -> str:
    """
    스타일 프리셋 + 선택적 정책 플래그를 합쳐 system 프롬프트 텍스트 생성
    policy_flags 는 향후 확장용(지금은 거의 무시해도 됨)
    """
    base = STYLE_MAP.get(style, STYLE_MAP["friendly"])

    # 확장용 플래그 예시 (필요 없으면 그냥 두면 됨)
    extra_rules: list[str] = []

    # 예: 추가 규칙 문자열을 직접 넣고 싶을 때
    extra = policy_flags.get("extra_instructions")
    if isinstance(extra, str) and extra.strip():
        extra_rules.append(extra.strip())

    # 예: 코드 출력 제한 플래그 (실제로 쓰려면 호출할 때 이 키를 넘기면 됨)
    if policy_flags.get("no_code_examples"):
        extra_rules.append("- 코드 예시는 제공하지 않는다.")

    if extra_rules:
        base += "\n\n추가 규칙:\n" + "\n".join(extra_rules)

    return base


def llm_params(fast_mode: bool) -> Dict[str, Any]:
    """
    fast_mode 여부에 따라 LLM 기본 파라미터를 정리해서 반환
    - qa_chain 에서는 temperature 만 사용하지만, 나중에 max_tokens 등도 같이 쓸 수 있게 구조 유지
    """
    if fast_mode:
        # 빠른 응답 모드: 약간 높은 temperature, 짧은 max_tokens
        return {
            "temperature": 0.7,
            "max_tokens": 512,
            "top_p": 0.9,
        }
    else:
        # 정밀 모드: 낮은 temperature, 조금 더 긴 max_tokens
        return {
            "temperature": 0.3,
            "max_tokens": 1024,
            "top_p": 0.9,
        }
