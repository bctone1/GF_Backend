# service/user/practice/retrieval.py
from __future__ import annotations

from typing import Any, Callable, Dict, List

from sqlalchemy.orm import Session

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

        cache_key = (tuple(kids), q, max_chunks, float(threshold) if threshold is not None else None)
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

        per_doc_top_k = max(1, max_chunks // len(valid_docs))

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
                    top_k=per_doc_top_k,
                )
            except Exception:
                doc_chunks = []

            if doc_chunks:
                chunks.extend(doc_chunks)

        if not chunks:
            out = {"context": "", "sources": []}
            ret_cache[cache_key] = out
            return out

        chunks = chunks[:max_chunks]

        texts: List[str] = []
        sources: List[Dict[str, Any]] = []
        for c in chunks:
            chunk_text = (
                getattr(c, "chunk_text", None)
                or getattr(c, "text", None)
                or getattr(c, "content", None)
            )

            if chunk_text:
                texts.append(str(chunk_text))

            sources.append(
                {
                    "knowledge_id": getattr(c, "knowledge_id", None),
                    "chunk_id": getattr(c, "chunk_id", None) or getattr(c, "id", None),
                    "score": getattr(c, "score", None) or getattr(c, "similarity", None),
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

        _ = raw
        _ = threshold

        out = {"context": context, "sources": sources}
        ret_cache[cache_key] = out
        return out

    return _retrieve
