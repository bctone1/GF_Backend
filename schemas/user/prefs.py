# schemas/user/prefs.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import ConfigDict, Field
from schemas.base import ORMBase


# =========================================================
# user_preferences
# =========================================================
class UserPreferenceCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    preferences: Dict[str, Any] = Field(default_factory=dict)  # JSONB


class UserPreferenceUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    preferences: Optional[Dict[str, Any]] = None


class UserPreferenceResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    preferences: Dict[str, Any]
    updated_at: datetime


# =========================================================
# user_preference_history
# =========================================================
class UserPreferenceHistoryCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    preferences: Dict[str, Any]
    # changed_at is server-filled; allow optional override if needed
    changed_at: Optional[datetime] = None


class UserPreferenceHistoryUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # history는 보통 append-only. 필요 시 최소 필드만 허용.
    preferences: Optional[Dict[str, Any]] = None


class UserPreferenceHistoryResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    history_id: int
    user_id: int
    preferences: Dict[str, Any]
    changed_at: datetime


# =========================================================
# user_notification_preferences
# =========================================================
class UserNotificationPreferenceCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    channel: str           # 'email' | 'sms' | 'push' 등
    event_type: str        # 'system_notice' | 'deadline' | 'api_cost_alert' 등
    is_enabled: Optional[bool] = None  # server default True


class UserNotificationPreferenceUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    is_enabled: Optional[bool] = None


class UserNotificationPreferenceResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    preference_id: int
    user_id: int
    channel: str
    event_type: str
    is_enabled: bool
    updated_at: datetime


# =========================================================
# notification_events
# =========================================================
class NotificationEventCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: Optional[int] = None
    channel: str
    event_type: str
    status: Optional[str] = None       # server may set 'queued'
    payload: Optional[Dict[str, Any]] = None
    delivered_at: Optional[datetime] = None


class NotificationEventUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    delivered_at: Optional[datetime] = None


class NotificationEventResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    event_id: int
    user_id: Optional[int] = None
    channel: str
    event_type: str
    status: str
    payload: Optional[Dict[str, Any]] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
