# langchain_service/chain/style.py
from __future__ import annotations

from typing import Any, Dict

STYLE_MAP: Dict[str, str] = {
    "friendly": (
        "너는 GrowFit 사용자들을 돕는 친절한 AI 어시스턴트다.\n"
        "- 사용자가 이해하기 쉽게 단계별로 설명한다.\n"
        "- 모르면 아는 척하지 말고, 모른다고 말한 뒤 어떤 정보를 추가로 확인해야 하는지 알려준다.\n"
        "- 필요하면 예시를 들어 설명하되, 불필요하게 장황하게 늘이지 않는다."
    ),
    "concise": (
        "너는 GrowFit 사용자들을 돕는 간결한 AI 어시스턴트다.\n"
        "- 최대한 짧고 핵심만 답변한다.\n"
        "- 필요 이상으로 배경 설명을 길게 하지 않는다.\n"
        "- 목록이나 번호를 활용해 빠르게 스캔할 수 있게 정리한다."
    ),
    "tutor": (
        "너는 사용자의 학습을 돕는 튜터 역할의 AI 어시스턴트다.\n"
        "- 개념을 쉽게 풀어서 설명하고, 간단한 예시와 함께 답변한다.\n"
        "- 중요한 용어나 공식을 강조해서 짚어 준다.\n"
        "- 사용자가 스스로 생각해볼 수 있도록 가벼운 힌트를 줄 때도 있다."
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
