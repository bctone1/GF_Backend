# service/user/document_rag.py
from __future__ import annotations

from typing import Optional, Any, Dict
import logging

from sqlalchemy.orm import Session

from core import config
from crud.user import document as document_crud
from crud.user.document import document_search_setting_crud
from schemas.common.llm import QASource

log = logging.getLogger("api_cost")

_SCORE_TYPE_FIXED = "cosine_similarity"


def get_effective_search_settings(
    db: Session,
    *,
    knowledge_id: Optional[int],
    top_k_fallback: int,
) -> Dict[str, Any]:
    """
    document_search_settings를 기준으로 검색 파라미터 확정.
    - knowledge_id 없으면 config.DEFAULT_SEARCH + fallback top_k
    - score_type은 cosine_similarity로 고정
    - reranker_top_n <= top_k 보정
    """
    defaults = dict(getattr(config, "DEFAULT_SEARCH"))
    defaults["score_type"] = _SCORE_TYPE_FIXED

    if knowledge_id is None:
        defaults["top_k"] = int(top_k_fallback)
        return defaults

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


def retrieve_sources(
    db: Session,
    *,
    question: str,
    vector: list[float],
    knowledge_id: Optional[int],
    search: Dict[str, Any],
) -> list[QASource]:
    """
    벡터검색 + min_score + (옵션) rerank 적용 후 QASource 생성
    """
    chunks = document_crud.search_chunks_by_vector(
        db,
        query_vector=vector,
        knowledge_id=knowledge_id,
        top_k=int(search["top_k"]),
        min_score=float(search["min_score"]),
        score_type=str(search["score_type"]),
    )

    if (
        search.get("reranker_enabled")
        and search.get("reranker_model")
        and len(chunks) > 1
        and int(search.get("reranker_top_n", 1)) >= 1
    ):
        try:
            from service.user.rerank import rerank_chunks  # lazy import
            chunks = rerank_chunks(
                question,
                chunks,
                model_name=str(search["reranker_model"]),
                top_n=int(search["reranker_top_n"]),
            )
        except Exception as e:
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


def build_context_text(sources: list[QASource], *, max_chars: int = 12000) -> str:
    if not sources:
        return ""
    ctx = "\n\n".join((s.text or "") for s in sources)
    return ctx[:max_chars]
