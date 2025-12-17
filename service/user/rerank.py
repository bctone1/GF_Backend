# service/user/rerank.py
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Sequence, TypeVar, List, Tuple

T = TypeVar("T")

_MODEL_CACHE: dict[str, Any] = {}
_LOCK = threading.Lock()


def _get_cross_encoder(model_name: str):
    """
    로컬 리랭커: sentence-transformers CrossEncoder 기반
    """
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "reranker를 쓰려면 sentence-transformers가 필요해. "
            "pip install sentence-transformers"
        ) from e

    with _LOCK:
        m = _MODEL_CACHE.get(model_name)
        if m is None:
            device = os.getenv("RERANK_DEVICE")  # 예: "cpu" / "cuda"
            if device:
                m = CrossEncoder(model_name, device=device)
            else:
                m = CrossEncoder(model_name)
            _MODEL_CACHE[model_name] = m
    return m


def rerank_pairs(
    query: str,
    passages: Sequence[str],
    *,
    model_name: str,
    top_n: int,
) -> List[Tuple[int, float]]:
    """
    반환: [(원본 index, score)] score 내림차순 top_n
    """
    if not passages:
        return []

    top_n = max(1, min(int(top_n), len(passages)))
    model = _get_cross_encoder(model_name)

    pairs = [(query, (p or "")) for p in passages]
    scores = model.predict(pairs)  # list/np.array

    scored = [(i, float(scores[i])) for i in range(len(passages))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def rerank_items(
    query: str,
    items: Sequence[T],
    *,
    get_text: Callable[[T], str],
    model_name: str,
    top_n: int,
) -> List[T]:
    if not items:
        return []

    texts = [(get_text(it) or "") for it in items]
    ranked = rerank_pairs(query, texts, model_name=model_name, top_n=top_n)
    return [items[i] for i, _ in ranked]


def rerank_chunks(
    query: str,
    chunks: Sequence[Any],
    *,
    model_name: str,
    top_n: int,
) -> List[Any]:
    """
    DocumentChunk 리스트를 rerank.
    """
    return rerank_items(
        query,
        list(chunks),
        get_text=lambda c: (
            getattr(c, "chunk_text", None)
            or getattr(c, "text", None)
            or getattr(c, "content", None)
            or ""
        ),
        model_name=model_name,
        top_n=top_n,
    )
