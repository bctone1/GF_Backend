# langchain_service/chain/qa_chain.py
from operator import itemgetter
from typing import Optional, Callable, List, Any, Dict

from sqlalchemy.orm import Session

from langchain_core.runnables import RunnableLambda, RunnableMap
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from crud.user.document import search_chunks_by_vector
from langchain_service.chain.style import build_system_prompt, llm_params, STYLE_MAP
from core import config


def make_qa_chain(
    db: Session,
    get_llm: Callable[..., object],
    text_to_vector: Callable[[str], list[float]],
    *,
    knowledge_id: Optional[int] = None,
    top_k: int = 8,
    policy_flags: dict | None = None,
    style: str = "friendly",
    max_ctx_chars: int = 12000,
    restrict_to_kb: bool = True,  # (현재 미사용) 필요하면 search_chunks_by_vector 쪽에서 사용
    streaming: bool = False,
    callbacks: Optional[List[Any]] = None,  # 비용 집계용 콜백
    few_shot_examples: Optional[List[Dict[str, str]]] = None,  # ✅ 추가
):
    fast_mode = getattr(config, "FAST_RESPONSE_MODE", False)
    style = style if style in STYLE_MAP else "friendly"
    system_txt = build_system_prompt(style=style, **(policy_flags or {}))
    few_shot_examples = few_shot_examples or []

    rule_txt = (
        "규칙: 제공된 컨텍스트를 우선하여 답하고, 정말 관련이 없을 때만 "
        "짧게 '해당내용은 찾을 수 없음'이라고 답하라."
    )

    def _retrieve(question: str) -> str:
        vec = text_to_vector(question)
        chunks = search_chunks_by_vector(
            db=db,
            query_vector=vec,
            knowledge_id=knowledge_id,
            top_k=top_k,
        )
        return "\n\n".join(getattr(c, "chunk_text", "") for c in chunks)[:max_ctx_chars]

    retriever = RunnableLambda(_retrieve)

    def _build_messages(inputs: dict) -> list:
        question: str = inputs["question"]
        context: str = inputs.get("context", "") or ""

        msgs: list = [
            SystemMessage(content=system_txt + "\n" + rule_txt),
        ]

        # ✅ few-shot 삽입 (템플릿 안 쓰고 메시지 직접 구성 → JSON {}도 안전)
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
                    f"{context}\n"
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
        RunnableMap(
            {
                "question": itemgetter("question"),
                "context": itemgetter("question") | retriever,
            }
        )
        | RunnableLambda(_build_messages)
        | llm
        | StrOutputParser()
    )

    return chain
