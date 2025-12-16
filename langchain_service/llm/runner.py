# langchain_service/llm/runner.py
from __future__ import annotations

from typing import Iterable, Optional
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from crud.partner import session as session_crud
from crud.user import document as document_crud
from crud.supervisor.api_usage import api_usage_crud as api_usage  # api 사용량/비용 집계용

from schemas.common.llm import QASource, QAResponse

from core import config
from core.pricing import tokens_for_texts, estimate_llm_cost_usd

from langchain_service.chain.qa_chain import make_qa_chain
from langchain_service.embedding.get_vector import text_to_vector, _to_vector
from langchain_service.llm.setup import get_llm
from langchain_service.prompt.style import build_system_prompt

try:
    from langchain_community.callbacks import get_openai_callback
except Exception:
    try:
        from langchain_community.callbacks.manager import get_openai_callback  # 일부 버전
    except Exception:
        get_openai_callback = None

from langchain_core.messages import SystemMessage, HumanMessage

log = logging.getLogger("api_cost")

MAX_CTX_CHARS = 12000  # qa_chain 기본값과 동일


def _update_last_user_vector(db: Session, session_id: int, vector: Iterable[float]) -> None:
    """
    마지막 user 메시지에 vector_memory 를 저장하는 로직.
    """
    # 마지막 user 메시지 찾기
    message = session_crud.get_last_message_by_role(
        db,
        session_id=session_id,
        role="user",
    )
    if not message:
        return

    # 벡터를 list 로 변환해서 저장
    session_crud.update_message(
        db,
        message=message,
        data={"vector_memory": list(vector)},
    )


def _build_sources(
    db: Session,
    vector: list[float],
    knowledge_id: Optional[int],
    top_k: int,
) -> list[QASource]:
    """
    벡터 검색으로 컨텍스트 청크를 가져와 QASource 리스트로 변환.

    - 현재 프로젝트 기준:
      knowledge_id == knowledge_id 로 해석해서 crud.user.document.search_chunks_by_vector 사용
    """

    chunks = document_crud.search_chunks_by_vector(
        db,
        query_vector=vector,
        knowledge_id=knowledge_id,  # 내부에서 knowledge_id 로 매핑
        top_k=top_k,
    )

    sources: list[QASource] = []

    for chunk in chunks:
        # knowledge_id / page_id / chunk_index 등의 필드명은 모델 정의에 맞춰 사용
        knowledge_id = getattr(chunk, "knowledge_id", None)
        page_id = getattr(chunk, "page_id", None)
        chunk_index = getattr(chunk, "chunk_index", None)

        # 텍스트 컬럼은 프로젝트마다 이름이 다를 수 있어 순서대로 fallback
        text = (
            getattr(chunk, "chunk_text", None)
            or getattr(chunk, "content", None)
            or getattr(chunk, "text", "")
        )

        sources.append(
            QASource(
                chunk_id=chunk.id,
                knowledge_id=knowledge_id,  # QASource 필드명은 그대로 두고 knowledge_id를 넣어줌
                page_id=page_id,
                chunk_index=chunk_index,
                text=text,
            )
        )

    return sources


def _render_prompt_for_estimate(
    *,
    question: str,
    context_text: str,
    style: Optional[str],
    policy_flags: Optional[dict],
    few_shot_examples: Optional[list[dict]] = None,
) -> list[str]:
    system_txt = build_system_prompt(style=(style or "friendly"), **(policy_flags or {}))
    rule_txt = (
        "규칙: 제공된 컨텍스트를 우선하여 답하고, 정말 관련이 없을 때만 "
        "짧게 '해당내용은 찾을 수 없음'이라고 답하라."
    )
    context_hdr = "다음 컨텍스트만 근거로 답하세요.\n[컨텍스트 시작]"
    context_ftr = "[컨텍스트 끝]"
    question_lbl = "질문: "

    parts: list[str] = [
        system_txt,
        rule_txt,
    ]

    for ex in (few_shot_examples or []):
        inp = str(ex.get("input", "") or "")
        out = str(ex.get("output", "") or "")
        if inp:
            parts.append("예시 질문: " + inp)
        if out:
            parts.append("예시 답변: " + out)

    parts += [
        context_hdr,
        context_text,
        context_ftr,
        question_lbl + question,
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

    sources = _build_sources(db, vector, knowledge_id, top_k)
    context_text = ("\n\n".join(s.text for s in sources))[:MAX_CTX_CHARS] if sources else ""

    provider = getattr(config, "LLM_PROVIDER", "openai").lower()
    model = getattr(config, "LLM_MODEL", getattr(config, "DEFAULT_CHAT_MODEL", "gpt-4o-mini"))

    raw = ""
    few = few_shot_examples or []

    try:
        if provider == "openai" and get_openai_callback is not None:
            with get_openai_callback() as cb:
                chain = make_qa_chain(
                    db,
                    get_llm,
                    text_to_vector,
                    knowledge_id=knowledge_id,
                    top_k=top_k,
                    policy_flags=policy_flags or {},
                    style=style or "friendly",
                    streaming=True,
                    few_shot_examples=few,
                    callbacks=[cb],
                )

                raw = "".join(
                    chain.stream(
                        {"question": question},
                        config={"callbacks": [cb]},
                    )
                )
                resp_text = str(raw or "")

                prompt_parts = _render_prompt_for_estimate(
                    question=question,
                    context_text=context_text,
                    style=style,
                    policy_flags=policy_flags,
                    few_shot_examples=few,
                )
                est_tokens = tokens_for_texts(model, prompt_parts + [resp_text])

                cb_total = int(getattr(cb, "total_tokens", 0) or 0)
                total_tokens = max(cb_total, est_tokens)

                usd_cb = Decimal(str(getattr(cb, "total_cost", 0.0) or 0.0))
                usd_est = estimate_llm_cost_usd(model=model, total_tokens=total_tokens)
                usd = max(usd_cb, usd_est)

                log.info(
                    "api-usage(openai): cb_total=%d est=%d used=%d usd=%s model=%s few_shots=%d",
                    cb_total,
                    est_tokens,
                    total_tokens,
                    usd,
                    model,
                    len(few),
                )

                try:
                    api_usage.add_event(
                        db,
                        ts_utc=datetime.now(timezone.utc),
                        product="llm",
                        model=model,
                        llm_tokens=total_tokens,
                        embedding_tokens=0,
                        audio_seconds=0,
                        cost_usd=usd,
                    )
                except Exception as e:
                    log.exception("api-usage llm record failed: %s", e)

        else:
            chain = make_qa_chain(
                db,
                get_llm,
                text_to_vector,
                knowledge_id=knowledge_id,
                top_k=top_k,
                policy_flags=policy_flags or {},
                style=style or "friendly",
                streaming=True,
                few_shot_examples=few,
            )

            raw = "".join(chain.stream({"question": question}))
            resp_text = str(raw or "")

            prompt_parts = _render_prompt_for_estimate(
                question=question,
                context_text=context_text,
                style=style,
                policy_flags=policy_flags,
                few_shot_examples=few,
            )
            total_tokens = tokens_for_texts(model, prompt_parts + [resp_text])
            usd = estimate_llm_cost_usd(model=model, total_tokens=total_tokens)

            log.info(
                "api-usage(fallback): tokens=%d usd=%s model=%s few_shots=%d",
                total_tokens,
                usd,
                model,
                len(few),
            )

            try:
                api_usage.add_event(
                    db,
                    ts_utc=datetime.now(timezone.utc),
                    product="llm",
                    model=model,
                    llm_tokens=total_tokens,
                    embedding_tokens=0,
                    audio_seconds=0,
                    cost_usd=usd,
                )
            except Exception as e:
                log.exception("api-usage llm record failed: %s", e)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 호출에 실패했습니다.",
        ) from exc

    return QAResponse(
        answer=str(raw or ""),
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
    """
    질문/응답 한 턴을 보고 세션 제목을 한 줄로 만들어주는 LLM 헬퍼.
    - 도메인 객체(DB)는 전혀 모르게 두고, 텍스트만 다룸.
    """
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

