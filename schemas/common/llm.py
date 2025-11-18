# schemas/common/llm.py
from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class QASource(BaseModel):
    """
    RAG에서 가져온 컨텍스트 청크 한 덩어리
    """
    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    knowledge_id: Optional[int] = None  # 필요 없으면 나중에 제거 가능
    page_id: Optional[int] = None
    chunk_index: Optional[int] = None
    text: str


class QAResponse(BaseModel):
    """
    QA 실행 결과 DTO
    """
    model_config = ConfigDict(from_attributes=True)

    answer: str
    question: str
    session_id: Optional[int] = None

    # sources / documents 둘 다 QASource 리스트로 유지 (호환성용)
    sources: List[QASource] = Field(default_factory=list)
    documents: List[QASource] = Field(default_factory=list)
