# schemas/user/fewshot.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List, Literal

from pydantic import ConfigDict, Field

from schemas.base import ORMBase

FewShotSource = Literal["user_fewshot", "class_shared", "partner_fewshot"]


class UserFewShotExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False, populate_by_name=True)

    title: Optional[str] = None
    input_text: str
    output_text: str
    fewshot_source: Optional[FewShotSource] = Field(
        default=None,
        # alias="template_source",
        description="퓨샷 출처: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)",
    )
    meta: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserFewShotExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False, populate_by_name=True)

    title: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    fewshot_source: Optional[FewShotSource] = Field(
        default=None,
        # alias="template_source",
        description="퓨샷 출처: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)",
    )
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
    fewshot_source: Optional[FewShotSource] = Field(
        default=None,
        description="퓨샷 출처: user_fewshot(내가 만든 것), class_shared(공유), partner_fewshot(강사 제공)",
    )
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FewShotShareCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    example_id: int
    class_id: int
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
    name: Optional[str] = None