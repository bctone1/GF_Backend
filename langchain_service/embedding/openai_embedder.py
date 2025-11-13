# langchain_service/embedding/openai_embedder.py
from __future__ import annotations

from typing import Optional
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings


def build_openai_embeddings(
    api_key: str,
    model: str,
) -> Embeddings:
    """
    OpenAI 임베딩 객체 생성기.
    - factory / service 에서 공통으로 사용.
    """
    return OpenAIEmbeddings(
        api_key=api_key,
        model=model,
    )
