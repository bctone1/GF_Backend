# schemas/user/fewshot.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import ConfigDict, Field

from schemas.base import ORMBase


class UserFewShotExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: str
    output_text: str
    template_source: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    title: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    template_source: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    example_id: int
    user_id: int
    class_ids: List[int] = []
    title: Optional[str] = None
    input_text: str
    output_text: str
    template_source: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FewShotShareCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    example_id: int
    class_id: int
    is_active: Optional[bool] = None


class FewShotShareUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    is_active: Optional[bool] = None


class FewShotShareResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    share_id: int
    example_id: int
    class_id: int
    shared_by_user_id: int
    is_active: bool
    created_at: datetime


class FewShotForkRequest(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    class_id: int
