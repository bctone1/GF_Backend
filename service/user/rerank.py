# service/user/rerank.py
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Sequence, TypeVar, List, Tuple

T = TypeVar("T")

_MODEL_CACHE: dict[str, Any] = {}
_LOCK = threading.Lock()

# env
_RERANK_DEVICE = os.getenv("RERANK_DEVICE")  # "cpu" / "cuda"
_RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "16"))
_RERANK_FP16 = os.getenv("RERANK_FP16", "").lower() in ("1", "true", "yes", "y")


def _is_bge_reranker(model_name: str) -> bool:
    mn = (model_name or "").lower()
    return ("bge-reranker" in mn) or (model_name == "BAAI/bge-reranker-v2-m3")


# ----------------------------
# Backend: CrossEncoder
# ----------------------------
def _get_cross_encoder(model_name: str):
    """
    로컬 리랭커: sentence-transformers CrossEncoder 기반
    """
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "CrossEncoder reranker를 쓰려면 sentence-transformers가 필요해. "
            "pip install sentence-transformers"
        ) from e

    with _LOCK:
        m = _MODEL_CACHE.get(f"cross:{model_name}")
        if m is None:
            if _RERANK_DEVICE:
                m = CrossEncoder(model_name, device=_RERANK_DEVICE)
            else:
                m = CrossEncoder(model_name)
            _MODEL_CACHE[f"cross:{model_name}"] = m
    return m


def _cross_scores(model_name: str, pairs: list[tuple[str, str]]) -> list[float]:
    model = _get_cross_encoder(model_name)
    scores = model.predict(pairs)  # list/np.array
    return [float(scores[i]) for i in range(len(pairs))]


# ----------------------------
# Backend: BGE Reranker (FlagEmbedding preferred)
# ----------------------------
def _get_flag_reranker(model_name: str):
    """
    BGE reranker: FlagEmbedding FlagReranker 우선 사용
    """
    try:
        from FlagEmbedding import FlagReranker  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "BGE reranker를 쓰려면 FlagEmbedding이 필요해. "
            "pip install FlagEmbedding"
        ) from e

    # FlagReranker는 내부에서 device/fp16 옵션을 받음
    use_fp16 = _RERANK_FP16 or ((_RERANK_DEVICE or "").lower() == "cuda")

    with _LOCK:
        m = _MODEL_CACHE.get(f"flag:{model_name}")
        if m is None:
            kwargs: dict[str, Any] = {"use_fp16": use_fp16}
            # FlagEmbedding 버전에 따라 device 인자가 다를 수 있어서 안전하게 처리
            # (없으면 내부 자동)
            if _RERANK_DEVICE:
                kwargs["device"] = _RERANK_DEVICE
            try:
                m = FlagReranker(model_name, **kwargs)
            except TypeError:
                # 일부 버전은 device 파라미터가 없을 수 있음
                kwargs.pop("device", None)
                m = FlagReranker(model_name, **kwargs)

            _MODEL_CACHE[f"flag:{model_name}"] = m
    return m


def _flag_scores(model_name: str, pairs: list[tuple[str, str]]) -> list[float]:
    reranker = _get_flag_reranker(model_name)

    # FlagReranker.compute_score 입력 형태: [[q, p], [q, p], ...]
    qp = [[q, p] for (q, p) in pairs]

    # 배치 처리(큰 top_k에서 메모리/지연 보호)
    bs = max(1, int(_RERANK_BATCH_SIZE))
    out: list[float] = []
    for i in range(0, len(qp), bs):
        batch = qp[i : i + bs]
        scores = reranker.compute_score(batch)
        # scores가 float 하나 or list 형태 모두 대응
        if isinstance(scores, (float, int)):
            out.append(float(scores))
        else:
            out.extend([float(s) for s in scores])
    return out


# ----------------------------
# Public API
# ----------------------------
def rerank_pairs(
    query: str,
    passages: Sequence[str],
    *,
    model_name: str,
    top_n: int,
) -> List[Tuple[int, float]]:
    """
    반환: [(원본 index, score)] score 내림차순 top_n

    model_name 규칙(자동 선택):
    - "BAAI/bge-reranker-v2-m3" 또는 "bge-reranker" 포함 -> BGE(FlagEmbedding)
    - 그 외 -> CrossEncoder(sentence-transformers)
    """
    if not passages:
        return []

    model_name = str(model_name or "").strip()
    if not model_name:
        raise RuntimeError("reranker_model(model_name)이 비어있음")

    top_n = max(1, min(int(top_n), len(passages)))
    pairs = [(query, (p or "")) for p in passages]

    if _is_bge_reranker(model_name):
        scores = _flag_scores(model_name, pairs)
    else:
        scores = _cross_scores(model_name, pairs)

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
    DocumentChunk 리스트 rerank.
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
