# schemas/base.py
from __future__ import annotations
from typing import Annotated, Any, Generic, TypeVar
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, PlainSerializer, model_serializer, model_validator

T = TypeVar("T")

# Decimal → str 직렬화 (json_encoders 대체, Pydantic v2 권장)
DecimalStr = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str)]


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyBase(ORMBase):
    """Decimal 필드를 고정소수점 문자열로 직렬화하는 베이스 클래스."""
    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_decimals(self, handler):  # type: ignore[override]
        d = handler(self)
        return {
            k: format(v, "f") if isinstance(v, Decimal) else v
            for k, v in d.items()
        }


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
