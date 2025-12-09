# schemas/base.py
from __future__ import annotations
from typing import Any, Generic, TypeVar
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, model_validator  # ← model_validator 추가

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyBase(ORMBase):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: format(v, "f")},
    )


class Page(ORMBase, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int

    # 기존 응답이 {"total", "items", "limit", "offset"} 인 경우도 받아서
    # page/size로 자동 매핑
    @model_validator(mode="before")
    @classmethod
    def from_limit_offset(cls, data: Any):
        # FastAPI가 dict 형태로 넘겨줄 때만 처리
        if isinstance(data, dict):
            # 이미 page/size 있으면 건드리지 않음
            if "page" not in data and "size" not in data:
                limit = data.get("limit")
                offset = data.get("offset", 0)
                if limit is not None:
                    # 원본 건드리지 않으려고 복사
                    data = dict(data)
                    data["size"] = int(limit)
                    data["page"] = int(offset) // int(limit) + 1
        return data
