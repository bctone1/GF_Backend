# schemas/user/account.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import EmailStr, ConfigDict, BaseModel
from schemas.base import ORMBase

# ==============================
# 이메일 인증: 요청/응답 스키마 (엔드포인트 전용)
# ==============================
class EmailCodeSendRequest(BaseModel):
    email: str


class EmailCodeSendResponse(BaseModel):
    email: str
    verification_token: str   # email + code + exp 를 서명한 토큰


class EmailCodeVerifyRequest(BaseModel):
    email: str
    code: str
    verification_token: str   # send-code 때 받은 토큰


class EmailCodeVerifyResponse(BaseModel):
    email: str
    email_verified_token: str  # 최종 회원가입에서 검증할 토큰


# =========================
# Auth I/O
# =========================
class LoginInput(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    email: EmailStr
    password: str

class AuthTokens(ORMBase):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# =========================
# users
# =========================
class UserCreate(ORMBase):
    # 엔드포인트 입력용: 평문 password 수신
    model_config = ConfigDict(from_attributes=False)
    email: EmailStr
    password: str
    full_name: Optional[str] = None          # 프로필 초기값에 사용 가능
    status: Optional[str] = None             # 서버 기본값 'active' 사용 가능
    default_role: Optional[str] = None       # 서버 기본값 'member' 사용 가능
    email_verified_token: Optional[str] = None

class UserUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    status: Optional[str] = None
    default_role: Optional[str] = None

class UserResponse(ORMBase):
    user_id: int
    email: EmailStr
    status: str
    default_role: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# =========================
# user_profiles
# =========================
class UserProfileCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_initials: Optional[str] = None

class UserProfileUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_initials: Optional[str] = None

class UserProfileResponse(ORMBase):
    user_id: int
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_initials: Optional[str] = None
    updated_at: datetime


# =========================
# user_security_settings
# =========================
class UserSecuritySettingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    two_factor_enabled: Optional[bool] = None
    two_factor_method: Optional[str] = None   # 'totp' | 'sms' | 'email'
    backup_codes: Optional[List[str]] = None
    recovery_email: Optional[EmailStr] = None

class UserSecuritySettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    two_factor_enabled: Optional[bool] = None
    two_factor_method: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    recovery_email: Optional[EmailStr] = None

class UserSecuritySettingResponse(ORMBase):
    user_id: int
    two_factor_enabled: bool
    two_factor_method: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    last_password_change_at: Optional[datetime] = None
    recovery_email: Optional[EmailStr] = None
    updated_at: datetime


# =========================
# user_login_sessions
# =========================
class UserLoginSessionCreate(ORMBase):
    # 엔드포인트 입력용: user_id, is_current는 서버가 설정
    model_config = ConfigDict(from_attributes=False)
    device_name: Optional[str] = None
    ip_address: Optional[str] = None   # INET -> str, 서버 검증
    location: Optional[str] = None
    user_agent: Optional[str] = None

class UserLoginSessionUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    logged_out_at: Optional[datetime] = None
    is_current: Optional[bool] = None

class UserLoginSessionResponse(ORMBase):
    session_id: int
    user_id: int
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    user_agent: Optional[str] = None
    logged_in_at: datetime
    logged_out_at: Optional[datetime] = None
    is_current: bool


# =========================
# user_privacy_settings
# =========================
class UserPrivacySettingCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    save_conversation_history: Optional[bool] = None
    allow_data_collection: Optional[bool] = None
    allow_personalized_ai: Optional[bool] = None

class UserPrivacySettingUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    save_conversation_history: Optional[bool] = None
    allow_data_collection: Optional[bool] = None
    allow_personalized_ai: Optional[bool] = None

class UserPrivacySettingResponse(ORMBase):
    user_id: int
    save_conversation_history: bool
    allow_data_collection: bool
    allow_personalized_ai: bool
    updated_at: datetime
