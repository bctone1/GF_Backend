# langchain_service/embedding/setup.py
from __future__ import annotations

from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
import core.config as config


def get_default_embeddings() -> Embeddings:
    """
    시스템 전역 기본 Embeddings 객체.
    - 간단한 테스트용 / 레거시 코드용
    - 실제 서비스 로직에서는 factory.get_embeddings() 사용 권장
    """
    return OpenAIEmbeddings(
        api_key=config.EMBEDDING_API,
        model=config.EMBEDDING_MODEL,
    )



# from langchain_openai import OpenAIEmbeddings
# import core.config as config
#
#
# def get_embeddings():
#     return OpenAIEmbeddings(
#         api_key = config.EMBEDDING_API,
#         model=config.EMBEDDING_MODEL
#      #    UPSTAGE 임베딩
#      #    api_key = config.UPSTAGE_API,
#      #    model = "embedding-query"
#     )