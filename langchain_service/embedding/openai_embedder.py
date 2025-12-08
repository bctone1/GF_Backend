# langchain_service/embedding/openai_embedder.py
from __future__ import annotations

from typing import Optional, Dict, Tuple
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

# (api_key, model) 조합별 임베딩 객체 캐시
_embeddings_cache: Dict[Tuple[Optional[str], str], Embeddings] = {}


def get_openai_embeddings(
    api_key: Optional[str],
    model: str,
) -> Embeddings:
    """
    OpenAI 임베딩 객체 싱글톤 getter.
    - 동일 (api_key, model) 조합에 대해 프로세스 전체에서 하나의 인스턴스만 재사용.
    """
    cache_key = (api_key, model)

    emb = _embeddings_cache.get(cache_key)
    if emb is None:
        emb = OpenAIEmbeddings(
            api_key=api_key,
            model=model,
        )
        _embeddings_cache[cache_key] = emb

    return emb


def build_openai_embeddings(
    api_key: Optional[str],
    model: str,
) -> Embeddings:
    """
    기존 코드 호환용 래퍼.
    내부적으로는 get_openai_embeddings 를 호출해서 싱글톤을 반환.
    """
    return get_openai_embeddings(api_key=api_key, model=model)
