# langchain_service/embedding/factory.py
from __future__ import annotations

from typing import Optional, Literal, List
import requests

from langchain_core.embeddings import Embeddings

import core.config as config
from langchain_service.embedding.openai_embedder import build_openai_embeddings
from sklearn.metrics.pairwise import cosine_similarity

# LangChain용 Upstage Embeddings 사용
try:
    from langchain_upstage import UpstageEmbeddings  # type: ignore
except ImportError:  # 패키지 없으면 None 처리
    UpstageEmbeddings = None  # type: ignore


# 지원 provider 타입
ProviderType = Literal["openai", "exaone", "upstage", "google"]


# ==============================
# Exaone (기존 코드 유지)
# ==============================
class ExaoneEmbeddings(Embeddings):
    """
    기존 get_vector.py 에 있던 ExaoneEmbeddings 그대로 옮김.
    지금은 안 써도 되지만, 확장성 위해 남겨둠.
    """
    def __init__(self, api_url: str, api_key: str | None = None):
        self.api_url = api_url
        self.api_key = api_key

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            self.api_url,
            headers=headers,
            json={"texts": texts},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


# ==============================
# Google 스텁 클래스
# ==============================
class GoogleEmbeddings(Embeddings):
    """
    Google 임베딩용 스텁.
    - Vertex AI / Generative AI 등 실제 사용하는 서비스에 맞게 구현해서 쓰면 됨.
    """
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Google 임베딩 API 스펙에 맞게 구현(추후_)
        raise NotImplementedError("Google embeddings는 아직 구현되지 않았습니다.")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


# ==============================
# 통합 factory
# ==============================
def get_embeddings(
    provider: ProviderType = "openai",
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Embeddings:
    """
    서비스 전체에서 임베딩 객체를 얻는 통합 엔트리.
    - 기본은 OpenAI 임베딩
    - exaone / upstage / google 은 필요 시 사용
    """

    # ---------- OpenAI ----------
    if provider == "openai":
        # 기본값은 config에서 읽음
        effective_key = api_key or config.EMBEDDING_API or config.OPENAI_API
        effective_model = model or config.EMBEDDING_MODEL

        if not effective_key:
            raise RuntimeError("OpenAI Embedding API key(EMBEDDING_API/OPENAI_API)가 설정되지 않았습니다.")
        if not effective_model:
            raise RuntimeError("OpenAI Embedding 모델(EMBEDDING_MODEL)이 설정되지 않았습니다.")

        return build_openai_embeddings(
            api_key=effective_key,
            model=effective_model,
        )

    # ---------- Exaone ----------
    elif provider == "exaone":
        api_url = config.EXAONE_ENDPOINT or config.EXAONE_URL
        effective_key = api_key or config.FRIENDLI_TOKEN or config.EMBEDDING_API

        if not api_url:
            raise RuntimeError("EXAONE_ENDPOINT 또는 EXAONE_URL 이 설정되지 않았습니다.")

        return ExaoneEmbeddings(api_url=api_url, api_key=effective_key)

    # ---------- Upstage ----------
    elif provider == "upstage":
        if UpstageEmbeddings is None:
            raise RuntimeError("langchain_upstage 패키지가 설치되어 있지 않습니다. `pip install langchain-upstage` 후 사용하세요.")

        effective_key = api_key or config.UPSTAGE_API
        effective_model = model or "embedding-query"

        if not effective_key:
            raise RuntimeError("Upstage API key(UPSTAGE_API)가 설정되지 않았습니다.")

        return UpstageEmbeddings(
            api_key=effective_key,
            model=effective_model,
        )

    # ---------- Google ----------
    elif provider == "google":
        effective_key = api_key or config.GOOGLE_API
        effective_model = model or "gemini-embedding-001"
        if not effective_key:
            raise RuntimeError("Google API key(GOOGLE_API)가 설정되지 않았습니다.")
        if not model:
            raise RuntimeError("Google embedding 모델명을 model 파라미터로 명시해야 합니다.")
        return GoogleEmbeddings(api_key=effective_key, model=model)

    # ---------- 기타 ----------
    else:
        raise ValueError(f"지원하지 않는 embedding provider: {provider}")
