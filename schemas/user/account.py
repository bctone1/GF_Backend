# schemas/user/account.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import EmailStr, ConfigDict
from schemas.base import ORMBase


# =========================================================
# users
# =========================================================
class UserCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)  # payload, not ORM
    email: EmailStr
    password_hash: str
    status: Optional[str] = None          # server may default to 'active'
    default_role: Optional[str] = None    # server may default to 'member'


class UserUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = None
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


# =========================================================
# user_profiles
# =========================================================
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


# =========================================================
# user_security_settings
# =========================================================
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


# =========================================================
# user_login_sessions
# =========================================================
class UserLoginSessionCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    device_name: Optional[str] = None
    ip_address: Optional[str] = None   # INET -> str, server-side validation
    location: Optional[str] = None
    user_agent: Optional[str] = None
    is_current: Optional[bool] = None  # server may set True by default


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


# =========================================================
# user_privacy_settings
# =========================================================
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
