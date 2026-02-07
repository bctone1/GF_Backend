# langchain_service/llm/runner.py
from __future__ import annotations

from langchain_service.llm.setup import get_llm
from langchain_core.messages import SystemMessage, HumanMessage


def generate_session_title_llm(
    question: str,
    answer: str,
    *,
    max_chars: int = 20,
) -> str:
    llm = get_llm(temperature=0.2, streaming=False)

    system = (
        "너는 사용자의 대화 세션 제목을 지어주는 도우미야. "
        f"대화 내용을 보고 핵심 주제를 {max_chars}자 이내 한국어로 한 줄 제목으로 만들어라. "
        "따옴표나 불필요한 기호 없이 제목만 출력해라."
    )
    content = f"사용자 질문: {question}\n모델 답변: {answer}"

    res = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=content),
    ])

    title = (res.content or "").strip().splitlines()[0]
    if len(title) > max_chars:
        title = title[:max_chars]
    return title
