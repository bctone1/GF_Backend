# schemas/user/fewshot.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import ConfigDict, Field

from schemas.base import ORMBase


class UserFewShotExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: str
    output_text: str
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    example_id: int
    user_id: int
    title: Optional[str] = None
    input_text: str
    output_text: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime
