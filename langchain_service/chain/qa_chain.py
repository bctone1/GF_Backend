# langchain_service/chain/qa_chain.py
from __future__ import annotations

from typing import Optional, Callable, List, Any, Dict

from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from langchain_service.chain.style import build_system_prompt, llm_params, STYLE_MAP
from core import config


def make_qa_chain(
    get_llm: Callable[..., object],
    *,
    context_text: str = "",
    policy_flags: dict | None = None,
    style: str = "friendly",
    max_ctx_chars: int = 12000,
    streaming: bool = False,
    callbacks: Optional[List[Any]] = None,  # 비용 집계용 콜백
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
):
    """
    검색 없는 QA 체인
    - context_text는 외부(document_rag)에서 만들어서 주입
    - 이 파일은 "메시지 구성 + LLM 호출"만 담당
    """
    fast_mode = getattr(config, "FAST_RESPONSE_MODE", False)
    style = style if style in STYLE_MAP else "friendly"
    system_txt = build_system_prompt(style=style, **(policy_flags or {}))
    few_shot_examples = few_shot_examples or []

    rule_txt = (
        "규칙: 제공된 컨텍스트를 우선하여 답하고, 정말 관련이 없을 때만 "
        "짧게 '해당내용은 찾을 수 없음'이라고 답하라."
    )

    def _build_messages(inputs: dict) -> list:
        question = str(inputs.get("question", "") or "")
        ctx = inputs.get("context", None)
        if ctx is None:
            ctx = context_text
        ctx = str(ctx or "")
        if max_ctx_chars and len(ctx) > max_ctx_chars:
            ctx = ctx[:max_ctx_chars]

        msgs: list = [
            SystemMessage(content=system_txt + "\n" + rule_txt),
        ]

        # few-shot 삽입
        for ex in few_shot_examples:
            inp = str(ex.get("input", "") or "").strip()
            out = str(ex.get("output", "") or "").strip()
            if not inp:
                continue
            msgs.append(HumanMessage(content=inp))
            msgs.append(AIMessage(content=out))

        msgs.append(
            HumanMessage(
                content=(
                    "다음 컨텍스트만 근거로 답하세요.\n"
                    "[컨텍스트 시작]\n"
                    f"{ctx}\n"
                    "[컨텍스트 끝]\n\n"
                    f"질문: {question}"
                )
            )
        )
        return msgs

    params = llm_params(fast_mode)

    provider = getattr(config, "LLM_PROVIDER", "openai")
    model_name = getattr(
        config,
        "LLM_MODEL",
        getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini"),
    )

    llm = get_llm(
        provider=provider,
        model=model_name,
        temperature=params.get("temperature", 0.7),
        streaming=streaming,
    )

    if callbacks:
        try:
            llm = llm.with_config(callbacks=callbacks, run_name="qa_llm")
        except Exception:
            pass

    chain = (
        RunnableLambda(_build_messages)
        | llm
        | StrOutputParser()
    )
    return chain
