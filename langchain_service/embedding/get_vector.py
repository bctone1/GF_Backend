# langchain_service/embedding/get_vector.py
from __future__ import annotations

from typing import List, Optional, Literal

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_service.embedding.factory import get_embeddings, ProviderType


def text_to_vector(
    text: str,
    *,
    provider: ProviderType = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> np.ndarray | None:
    """
    단일 텍스트를 임베딩 벡터(np.ndarray)로 변환.
    - 기본 provider는 'openai'
    - 필요 시 model, api_key 오버라이드 가능
    """
    embeddings: Embeddings = get_embeddings(
        provider=provider,
        api_key=api_key,
        model=model,
    )
    try:
        vector = embeddings.embed_query(text)
        return np.array(vector, dtype=float)
    except Exception as e:
        # logger 연동되면 print 대신 logger.error 사용(추후 작업)
        print(f"Error during embedding: {e}")
        return None


def _to_vector(
    question: str,
    *,
    provider: ProviderType = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[float]:
    """
    임베딩 생성 + 변환 + 검증 래퍼 (APP/llm 및 runner에서 공통 사용).
    기존 _to_vector(question) 시그니처와 호환되게 유지.
    """
    vector = text_to_vector(
        question,
        provider=provider,
        model=model,
        api_key=api_key,
    )
    if vector is None:
        raise RuntimeError("임베딩 생성에 실패했습니다.")

    vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    if not vector_list:
        raise RuntimeError("임베딩 생성에 실패했습니다.")

    # 안전하게 float 변환
    return [float(v) for v in vector_list]


def texts_to_vectors(
    texts: list[str],
    *,
    provider: ProviderType = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[list[float]]:
    """
    여러 텍스트를 한꺼번에 임베딩하는 유틸.
    - DocumentIngestService 등에서 bulk 임베딩할 때 사용 가능.
    """
    embeddings: Embeddings = get_embeddings(
        provider=provider,
        api_key=api_key,
        model=model,
    )
    vectors = embeddings.embed_documents(texts)
    # float 리스트 2차원 배열로 정규화
    return [[float(v) for v in vec] for vec in vectors]
