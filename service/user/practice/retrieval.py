# service/user/practice/retrieval.py
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Mapping

from sqlalchemy.orm import Session

from core import config
from models.user.account import AppUser

from langchain_service.embedding.get_vector import texts_to_vectors

from crud.user.document import document_crud, document_chunk_crud

from service.user.practice.ids import coerce_int_list


def embed_question_to_vector(question: str) -> list[float]:
    cleaned = (question or "").strip()
    if not cleaned:
        return []

    try:
        vectors = texts_to_vectors([cleaned])
    except Exception:
        return []

    if not vectors:
        return []

    v0 = vectors[0]
    if not isinstance(v0, (list, tuple)):
        return []

    return list(v0)


def make_retrieve_fn_for_practice(db_outer: Session, me: AppUser) -> Callable[..., Any]:
    vec_cache: dict[str, list[float]] = {}
    ret_cache: dict[tuple, Dict[str, Any]] = {}

    def _coerce_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_search_params(raw_payload: dict | None) -> Mapping[str, Any]:
        if not isinstance(raw_payload, Mapping):
            return {}
        params = raw_payload.get("search_params") or raw_payload.get("retrieval_params") or {}
        return params if isinstance(params, Mapping) else {}

    def _default_threshold() -> float:
        return float(getattr(config, "DEFAULT_SEARCH", {}).get("min_score", 0.2))

    def _normalize_threshold(value: float | None) -> float:
        if value is None:
            value = _default_threshold()
        else:
            try:
                if not math.isfinite(float(value)):
                    value = _default_threshold()
            except (TypeError, ValueError):
                value = _default_threshold()
        return float(min(max(float(value), 0.0), 1.0))

    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float | None:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return None
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            dot += a * b
            norm_a += a * a
            norm_b += b * b
        if norm_a <= 0.0 or norm_b <= 0.0:
            return None
        return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))

    def _chunk_score(chunk: Any, query_vector: list[float]) -> float | None:
        existing = getattr(chunk, "score", None)
        if existing is None:
            existing = getattr(chunk, "similarity", None)
        if existing is not None:
            return _coerce_float(existing)
        vec = getattr(chunk, "vector_memory", None)
        if vec is None:
            return None
        try:
            vector = list(vec)
        except TypeError:
            return None
        return _cosine_similarity(query_vector, vector)

    def _retrieve(
        *,
        knowledge_ids: List[int] | None = None,
        query: str | None = None,
        top_k: int | None = None,
        threshold: float | None = None,
        raw: dict | None = None,
        **_: Any,
    ) -> Dict[str, Any]:
        kids = coerce_int_list(knowledge_ids or [])
        q = (query or "").strip()
        if not kids or not q:
            return {"context": "", "sources": []}

        max_chunks = int(top_k) if isinstance(top_k, int) and top_k > 0 else 10
        search_params = _get_search_params(raw)

        effective_threshold = _normalize_threshold(threshold)

        candidate_top_k = _coerce_int(
            search_params.get("candidate_top_k")
            or search_params.get("vector_top_k")
            or search_params.get("initial_top_k")
        )
        if candidate_top_k is None or candidate_top_k < 1:
            candidate_top_k = max(max_chunks * 5, max_chunks)
        candidate_top_k = max(candidate_top_k, max_chunks)

        reranker_model = search_params.get("reranker_model")
        reranker_enabled = search_params.get("reranker_enabled")
        if reranker_enabled is None:
            reranker_enabled = True

        rerank_top_n = _coerce_int(
            search_params.get("reranker_top_n")
            or search_params.get("rerank_top_n")
            or search_params.get("rerank_top_k")
        )
        if rerank_top_n is None and reranker_model:
            rerank_top_n = max(max_chunks * 2, max_chunks)
        if rerank_top_n is not None:
            rerank_top_n = max(1, min(rerank_top_n, candidate_top_k))

        cache_key = (
            tuple(kids),
            q,
            max_chunks,
            effective_threshold,
            candidate_top_k,
            reranker_model,
            reranker_enabled,
            rerank_top_n,
        )
        cached = ret_cache.get(cache_key)
        if cached is not None:
            return cached

        if q in vec_cache:
            query_vector = vec_cache[q]
        else:
            query_vector = embed_question_to_vector(q)
            vec_cache[q] = query_vector

        if not query_vector:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        valid_docs: list[Any] = []
        for kid in kids:
            try:
                doc = document_crud.get(db_outer, knowledge_id=kid)
            except Exception:
                doc = None

            if not doc:
                continue

            owner_id = (
                getattr(doc, "owner_id", None)
                or getattr(doc, "user_id", None)
                or getattr(doc, "owner_user_id", None)
            )
            if owner_id is not None and owner_id != me.user_id:
                continue

            real_kid = getattr(doc, "knowledge_id", None)
            if real_kid is None:
                continue

            valid_docs.append(doc)

        if not valid_docs:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        chunks: list[Any] = []
        for doc in valid_docs:
            kid = getattr(doc, "knowledge_id", None)
            if kid is None:
                continue
            try:
                doc_chunks = document_chunk_crud.search_by_vector(
                    db_outer,
                    query_vector=query_vector,
                    knowledge_id=kid,
                    top_k=candidate_top_k,
                    min_score=effective_threshold,
                )
            except Exception:
                doc_chunks = []

            if doc_chunks:
                chunks.extend(doc_chunks)

        if not chunks:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        scored_chunks: list[tuple[float, Any]] = []
        for chunk in chunks:
            score = _chunk_score(chunk, query_vector)
            score = score if score is not None else 0.0
            if score < effective_threshold:
                continue
            scored_chunks.append((score, chunk))

        if not scored_chunks:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        scored_chunks = scored_chunks[:candidate_top_k]

        chunk_score_map = {id(chunk): score for score, chunk in scored_chunks}

        if reranker_model and rerank_top_n and reranker_enabled and len(scored_chunks) > 1:
            try:
                from service.user.rerank import rerank_chunks  # lazy import

                top_candidates = [chunk for _, chunk in scored_chunks[:rerank_top_n]]
                reranked = rerank_chunks(
                    q,
                    top_candidates,
                    model_name=str(reranker_model),
                    top_n=int(rerank_top_n),
                )
                final_chunks = reranked[:max_chunks]
            except Exception:
                final_chunks = [chunk for _, chunk in scored_chunks[:max_chunks]]
        else:
            final_chunks = [chunk for _, chunk in scored_chunks[:max_chunks]]

        texts: List[str] = []
        sources: List[Dict[str, Any]] = []
        for c in final_chunks:
            chunk_text = (
                getattr(c, "chunk_text", None)
                or getattr(c, "text", None)
                or getattr(c, "content", None)
            )

            if chunk_text:
                texts.append(str(chunk_text))

            score = chunk_score_map.get(id(c))
            sources.append(
                {
                    "knowledge_id": getattr(c, "knowledge_id", None),
                    "chunk_id": getattr(c, "chunk_id", None) or getattr(c, "id", None),
                    "score": score,
                    "preview": (str(chunk_text)[:200] if chunk_text else ""),
                }
            )

        if not texts:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        context_body = "\n\n".join(texts)
        context = (
            "다음은 사용자가 업로드한 참고 문서 중에서, "
            "질문과 가장 관련도가 높은 일부 발췌 내용입니다.\n\n"
            f"{context_body}\n\n"
            "위 내용을 참고해서 아래 질문에 답변해 주세요."
        )

        out = {
            "context": context,
            "sources": sources,
            "retrieval": {
                "retrieved_count": len(sources),
                "top_k": max_chunks,
                "threshold": effective_threshold,
            },
        }
        ret_cache[cache_key] = out
        return out

    return _retrieve