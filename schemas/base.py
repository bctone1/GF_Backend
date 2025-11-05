# schemas/base.py
from __future__ import annotations
from typing import Any, Generic, TypeVar
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class MoneyBase(ORMBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: format(v, "f")},
    )

class Page(Generic[T], ORMBase):
    items: list[T]
    total: int
    page: int
    size: int
