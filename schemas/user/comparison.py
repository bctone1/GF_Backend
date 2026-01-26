# schemas/user/comparison.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator

from schemas.user.practice import PracticeTurnResponse


ComparisonPanel = Literal["a", "b"]
ComparisonMode = Literal["llm", "doc", "rag"]


# =========================
# PracticeComparisonRun
# =========================
class PracticeComparisonRunBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    panel: ComparisonPanel = Field(..., description="패널 키", examples=["a"])
    prompt_text: str = Field(..., min_length=1, description="질문(프롬프트)")
    model_names: List[str] = Field(..., min_length=1, description="실행할 모델 리스트")
    mode: ComparisonMode = Field(..., description="실행 모드")

    # nullable fields (doc/rag일 때 프론트에서 들어오면 채움)
    knowledge_ids: Optional[List[int]] = Field(default=None, description="지식베이스 ID 리스트")
    top_k: Optional[int] = Field(default=None, ge=1, le=200, description="retrieval top_k")
    chunk_size: Optional[int] = Field(default=None, ge=1, le=20000, description="chunk size")
    threshold: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1"), description="score threshold")

    @model_validator(mode="after")
    def _validate_mode_fields(self):
        # 실행 관점에서 doc/rag면 knowledge_ids는 있어야 안전함
        if self.mode in ("doc", "rag"):
            if not self.knowledge_ids:
                raise ValueError("knowledge_ids_required_for_doc_or_rag")
        return self


class PracticeComparisonRunCreate(PracticeComparisonRunBase):
    """
    create 시 session_id는 path/body가 아니라 CRUD create(db, session_id=..., data=...)로 주입하는 패턴 유지.
    """
    pass


class PracticeComparisonRunUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_text: Optional[str] = Field(default=None, min_length=1)
    model_names: Optional[List[str]] = Field(default=None)
    mode: Optional[ComparisonMode] = None

    knowledge_ids: Optional[List[int]] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=200)
    chunk_size: Optional[int] = Field(default=None, ge=1, le=20000)
    threshold: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1"))

    @model_validator(mode="after")
    def _validate_update(self):
        # mode를 doc/rag로 바꾸는 업데이트라면 knowledge_ids 같이 오게 하는 게 안전
        if self.mode in ("doc", "rag") and self.knowledge_ids is not None and len(self.knowledge_ids) == 0:
            raise ValueError("knowledge_ids_required_for_doc_or_rag")
        return self


class PracticeComparisonRunResponse(PracticeComparisonRunBase):
    id: int
    session_id: int
    created_at: datetime


# =========================
# Turn (single panel run)
# =========================
class PracticeComparisonTurnRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_text: str = Field(..., min_length=1)
    model_names: List[str] = Field(..., min_length=1)

    panel: ComparisonPanel
    mode: ComparisonMode

    knowledge_ids: Optional[List[int]] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=200)
    chunk_size: Optional[int] = Field(default=None, ge=1, le=20000)
    threshold: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("1"))

    @model_validator(mode="after")
    def _validate_turn(self):
        if self.mode in ("doc", "rag") and not self.knowledge_ids:
            raise ValueError("knowledge_ids_required_for_doc_or_rag")
        return self


class PracticeComparisonTurnPanelResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    panel: ComparisonPanel
    mode: ComparisonMode
    turn: PracticeTurnResponse


class PracticeComparisonTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run: PracticeComparisonRunResponse
    panel_result: PracticeComparisonTurnPanelResult


__all__ = [
    "ComparisonPanel",
    "ComparisonMode",
    "PracticeComparisonRunCreate",
    "PracticeComparisonRunUpdate",
    "PracticeComparisonRunResponse",
    "PracticeComparisonTurnRequest",
    "PracticeComparisonTurnPanelResult",
    "PracticeComparisonTurnResponse",
]
