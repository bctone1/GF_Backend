# langchain_service/llm/runner.py
from __future__ import annotations

from typing import Iterable, Optional, Any, Dict
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from crud.partner import session as session_crud
from crud.user import document as document_crud
from crud.user.document import document_search_setting_crud
from crud.supervisor.api_usage import api_usage_crud as api_usage

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
        from langchain_community.callbacks.manager import get_openai_callback
    except Exception:
        get_openai_callback = None

from langchain_core.messages import SystemMessage, HumanMessage

log = logging.getLogger("api_cost")

MAX_CTX_CHARS = 12000  # qa_chain 기본값과 동일
_SCORE_TYPE_FIXED = "cosine_similarity"


def _update_last_user_vector(db: Session, session_id: int, vector: Iterable[float]) -> None:
    message = session_crud.get_last_message_by_role(db, session_id=session_id, role="user")
    if not message:
        return
    session_crud.update_message(db, message=message, data={"vector_memory": list(vector)})


def _get_effective_search_settings(
    db: Session,
    *,
    knowledge_id: Optional[int],
    top_k_fallback: int,
) -> Dict[str, Any]:
    """
     document_search_settings를 기준으로 검색 파라미터를 확정.
    - knowledge_id 없으면 config.DEFAULT_SEARCH + fallback top_k로 처리
    - score_type은 cosine_similarity로 고정
    """
    defaults = dict(getattr(config, "DEFAULT_SEARCH"))
    defaults["score_type"] = _SCORE_TYPE_FIXED

    if knowledge_id is None:
        defaults["top_k"] = int(top_k_fallback)
        return defaults

    # row가 없으면 생성(레거시 문서 대비). MVP 원칙: row는 항상 존재
    setting = document_search_setting_crud.ensure_default(
        db,
        knowledge_id=knowledge_id,
        defaults=defaults,
    )

    top_k = int(getattr(setting, "top_k", defaults["top_k"]))
    min_score = float(getattr(setting, "min_score", defaults["min_score"]))
    score_type = str(getattr(setting, "score_type", defaults["score_type"]))

    reranker_enabled = bool(getattr(setting, "reranker_enabled", defaults["reranker_enabled"]))
    reranker_model = getattr(setting, "reranker_model", defaults.get("reranker_model"))
    reranker_top_n = int(getattr(setting, "reranker_top_n", defaults["reranker_top_n"]))

    # 기본 정합성
    if score_type != _SCORE_TYPE_FIXED:
        score_type = _SCORE_TYPE_FIXED
    if reranker_top_n > top_k:
        reranker_top_n = top_k

    return {
        "top_k": top_k,
        "min_score": min_score,
        "score_type": score_type,
        "reranker_enabled": reranker_enabled,
        "reranker_model": reranker_model,
        "reranker_top_n": reranker_top_n,
    }


def _build_sources(
    db: Session,
    *,
    question: str,
    vector: list[float],
    knowledge_id: Optional[int],
    search: Dict[str, Any],
) -> list[QASource]:
    """
    벡터검색 + min_score 적용 + (옵션) rerank 적용 후 QASource 생성
    """
    chunks = document_crud.search_chunks_by_vector(
        db,
        query_vector=vector,
        knowledge_id=knowledge_id,
        top_k=int(search["top_k"]),
        min_score=float(search["min_score"]),
        score_type=str(search["score_type"]),
    )

    # rerank (로컬 모델)
    if (
        search.get("reranker_enabled")
        and search.get("reranker_model")
        and len(chunks) > 1
        and int(search.get("reranker_top_n", 1)) >= 1
    ):
        try:
            from service.user.rerank import rerank_chunks  # 지연 import
            chunks = rerank_chunks(
                question,
                chunks,
                model_name=str(search["reranker_model"]),
                top_n=int(search["reranker_top_n"]),
            )
        except Exception as e:
            # reranker 실패해도 검색은 계속 진행(운영 안정성)
            log.exception("rerank failed (fallback to vector order): %s", e)

    sources: list[QASource] = []
    for chunk in chunks:
        kid = getattr(chunk, "knowledge_id", None)
        page_id = getattr(chunk, "page_id", None)
        chunk_index = getattr(chunk, "chunk_index", None)

        text = (
            getattr(chunk, "chunk_text", None)
            or getattr(chunk, "content", None)
            or getattr(chunk, "text", "")
        )

        chunk_id = (
            getattr(chunk, "chunk_id", None)
            or getattr(chunk, "id", None)
        )

        sources.append(
            QASource(
                chunk_id=chunk_id,
                knowledge_id=kid,
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

    parts: list[str] = [system_txt, rule_txt]

    for ex in (few_shot_examples or []):
        inp = str(ex.get("input", "") or "")
        out = str(ex.get("output", "") or "")
        if inp:
            parts.append("예시 질문: " + inp)
        if out:
            parts.append("예시 답변: " + out)

    parts += [context_hdr, context_text, context_ftr, question_lbl + question]
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

    # 검색 설정 확정(문서 설정 우선)
    search = _get_effective_search_settings(db, knowledge_id=knowledge_id, top_k_fallback=top_k)
    effective_top_k = int(search["top_k"])

    sources = _build_sources(
        db,
        question=question,
        vector=vector,
        knowledge_id=knowledge_id,
        search=search,
    )
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
                    top_k=effective_top_k,
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
                top_k=effective_top_k,     # 설정 반영
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
