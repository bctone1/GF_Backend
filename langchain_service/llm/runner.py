# langchain_service/llm/runner.py
from __future__ import annotations

from typing import Iterable, Optional
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from crud.partner import session as session_crud
from crud.supervisor.api_usage import api_usage_crud as api_usage

from schemas.common.llm import QAResponse

from core import config
from core.pricing import tokens_for_texts, estimate_llm_cost_usd

from service.user.document_rag import (
    get_effective_search_settings,
    retrieve_sources,
    build_context_text,
)

from langchain_service.embedding.get_vector import _to_vector
from langchain_service.llm.setup import get_llm, call_llm_chat
from langchain_service.chain.qa_chain import make_qa_chain

from langchain_core.messages import SystemMessage, HumanMessage

log = logging.getLogger("api_cost")

MAX_CTX_CHARS = 12000


def _update_last_user_vector(db: Session, session_id: int, vector: Iterable[float]) -> None:
    message = session_crud.get_last_message_by_role(db, session_id=session_id, role="user")
    if not message:
        return
    session_crud.update_message(db, message=message, data={"vector_memory": list(vector)})


def _render_prompt_for_estimate(
    *,
    question: str,
    context_text: str,
    style: Optional[str],
    policy_flags: Optional[dict],
    few_shot_examples: Optional[list[dict]] = None,
) -> list[str]:

    from langchain_service.prompt.style import build_system_prompt  # runner에서만 필요

    system_txt = build_system_prompt(style=(style or "friendly"), **(policy_flags or {}))
    rule_txt = (
        "규칙: 제공된 컨텍스트를 우선하여 답하고, 정말 관련이 없을 때만 "
        "짧게 '해당내용은 찾을 수 없음'이라고 답하라."
    )
    parts: list[str] = [system_txt, rule_txt]

    for ex in (few_shot_examples or []):
        inp = str(ex.get("input", "") or "")
        out = str(ex.get("output", "") or "")
        if inp:
            parts.append("예시 질문: " + inp)
        if out:
            parts.append("예시 답변: " + out)

    parts += [
        "다음 컨텍스트만 근거로 답하세요.\n[컨텍스트 시작]",
        context_text or "",
        "[컨텍스트 끝]",
        "질문: " + question,
    ]
    return parts


def _run_qa(
    db: Session,
    *,
    question: str,
    knowledge_id: Optional[int],
    top_k: int,
    session_id: Optional[int] = None,
    policy_flags: Optional[dict] = None,
    style: Optional[str] = None,
    few_shot_examples: Optional[list[dict]] = None,
) -> QAResponse:
    vector = _to_vector(question)

    if session_id is not None:
        _update_last_user_vector(db, session_id, vector)

    # 검색/리랭크는 document_rag에서 1번만
    search = get_effective_search_settings(db, knowledge_id=knowledge_id, top_k_fallback=top_k)
    sources = retrieve_sources(
        db,
        question=question,
        vector=vector,
        knowledge_id=knowledge_id,
        search=search,
    )
    context_text = build_context_text(sources, max_chars=MAX_CTX_CHARS)

    provider = getattr(config, "LLM_PROVIDER", "openai").lower()
    model = getattr(config, "LLM_MODEL", getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini"))

    try:
        chain = make_qa_chain(
            call_llm_chat=call_llm_chat,
            provider=provider,
            model=model,
            temperature=getattr(config, "LLM_TEMPERATURE", 0.7),
            top_p=getattr(config, "LLM_TOP_P", None),
            max_tokens=None,
            streaming=False,
            context_text=context_text,
            policy_flags=policy_flags,
            style=style or "friendly",
            max_ctx_chars=MAX_CTX_CHARS,
            few_shot_examples=few_shot_examples,
        )

        out = chain.invoke({"question": question})
        resp_text = str(out.get("text", "") or "")
        token_usage = out.get("token_usage")

        # token/cost: 가능하면 실제 token_usage 우선, 없으면 estimate
        total_tokens: int | None = None
        if isinstance(token_usage, dict):
            t = token_usage.get("total_tokens")
            if isinstance(t, int):
                total_tokens = t

        if total_tokens is None:
            prompt_parts = _render_prompt_for_estimate(
                question=question,
                context_text=context_text,
                style=style,
                policy_flags=policy_flags,
                few_shot_examples=few_shot_examples,
            )
            total_tokens = tokens_for_texts(model, prompt_parts + [resp_text])

        usd = estimate_llm_cost_usd(model=model, total_tokens=total_tokens)

        try:
            api_usage.add_event(
                db,
                ts_utc=datetime.now(timezone.utc),
                product="llm",
                model=model,
                llm_tokens=total_tokens,
                embedding_tokens=0,
                audio_seconds=0,
                cost_usd=Decimal(str(usd)),
            )
        except Exception as e:
            log.exception("api-usage llm record failed: %s", e)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 호출에 실패했습니다.",
        ) from exc

    return QAResponse(
        answer=resp_text,
        question=question,
        session_id=session_id,
        sources=sources,
        documents=sources,
    )


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
