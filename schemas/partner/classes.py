# schemas/partner/classes.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal, List

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from schemas.base import ORMBase, Page
from schemas.enums import ClassStatus


# student 초대코드 전용
InviteTargetRole = Literal["student"]
InviteStatus = Literal["active", "expired", "disabled"]


# ==============================
# classes
# ==============================
class ClassBase(ORMBase):
    """
    Class 공통 필드
    - name, 시간, 정원, 장소 등
    - status / timezone / invite_only 에는 기본값 부여
    """
    name: str
    description: Optional[str] = None

    status: ClassStatus = ClassStatus.planned

    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None

    timezone: str = "UTC"
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: bool = False

    # ==========================
    # LLM 설정 (강의실 단위)
    # ==========================
    # 이 강의실에서 기본으로 사용할 LLM 모델 (partner.model_catalog.id)
    primary_model_id: Optional[int] = None
    # 이 강의실에서 허용되는 모델 목록 (model_catalog.id 리스트)
    allowed_model_ids: List[int] = Field(default_factory=list)


class ClassCreate(ClassBase):
    """
    partner_id, course_id 는 path / 컨텍스트에서 받기 때문에 body 에선 제외.
    """
    # 여기서는 별도 필드 추가 없이 ClassBase 그대로 사용
    pass


class ClassUpdate(ORMBase):
    """
    부분 수정용. 전부 Optional.
    """
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ClassStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    invite_only: Optional[bool] = None

    # 코스 소속 변경 가능 (독립 class ↔ course 소속)
    course_id: Optional[int] = None

    # LLM 설정
    primary_model_id: Optional[int] = None
    allowed_model_ids: Optional[List[int]] = None


# ==============================
# invite_codes
# ==============================
class InviteCodeBase(ORMBase):
    code: str
    # 항상 student 초대코드
    target_role: InviteTargetRole = "student"
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # 없으면 DB default('active') 사용


class InviteCodeCreate(ORMBase):
    """
    partner_id, class_id, created_by 는
    path(`/partner/{partner_id}/classes/{class_id}/invites`) 등에서 결정.
    클라이언트는 code / expires_at / max_uses 정도만 보냄.
    """
    code: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # 없으면 DB default('active') 사용


class InviteCodeUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    status: Optional[InviteStatus] = None  # active | expired | disabled


class InviteCodeResponse(InviteCodeBase):
    id: int
    code: str
    status: str
    expires_at: datetime | None = None
    max_uses: int | None = None
    used_count: int
    partner_id: int
    class_id: int

    model_config = ConfigDict(from_attributes=True)


class ClassResponse(ClassBase):
    """
    DB → 응답용 스키마
    """
    id: int
    partner_id: int
    course_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    invite_codes: List[InviteCodeResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================
# Invite DTOs (endpoint 전용)
# ==============================
class InviteSendRequest(BaseModel):
    """
    이메일로 초대 링크를 보낼 때 사용하는 DTO.
    partner_id / class_id / target_role 은 path 및 서버 로직에서 결정.
    """
    email: EmailStr
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None


class InviteAssignRequest(BaseModel):
    """
    이미 생성된 코드와 이메일을 묶어 관리할 때 사용하는 DTO.
    partner_id / class_id / target_role 은 path 및 서버 로직에서 결정.
    """
    email: EmailStr
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None


class InviteResendRequest(BaseModel):
    email: EmailStr


class InviteSendResponse(BaseModel):
    invite_id: int
    code: str
    invite_url: str
    email: EmailStr
    is_existing_user: bool
    email_sent: bool


# ==============================
# pagination wrappers
# ==============================
class ClassPage(Page[ClassResponse]):
    ...


class InviteCodePage(Page[InviteCodeResponse]):
    ...
