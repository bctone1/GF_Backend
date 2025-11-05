# schemas/supervisor/growth.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from schemas.base import ORMBase


# ========== supervisor.growth_channels ==========
class GrowthChannelCreate(ORMBase):
    channel_name: str
    description: Optional[str] = None


class GrowthChannelUpdate(ORMBase):
    channel_name: Optional[str] = None
    description: Optional[str] = None


class GrowthChannelResponse(ORMBase):
    channel_id: int
    channel_name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ========== supervisor.user_acquisition ==========
class UserAcquisitionCreate(ORMBase):
    user_id: int
    channel_id: Optional[int] = None
    acquired_at: Optional[datetime] = None
    campaign_info: Optional[Dict[str, Any]] = None


class UserAcquisitionUpdate(ORMBase):
    channel_id: Optional[int] = None
    acquired_at: Optional[datetime] = None
    campaign_info: Optional[Dict[str, Any]] = None


class UserAcquisitionResponse(ORMBase):
    acquisition_id: int
    user_id: int
    channel_id: Optional[int] = None
    acquired_at: datetime
    campaign_info: Optional[Dict[str, Any]] = None


# ========== supervisor.feedback ==========
class FeedbackCreate(ORMBase):
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    category: Optional[str] = None
    rating: Optional[int] = None  # 1~5
    comment: Optional[str] = None


class FeedbackUpdate(ORMBase):
    category: Optional[str] = None
    rating: Optional[int] = None  # 1~5
    comment: Optional[str] = None


class FeedbackResponse(ORMBase):
    feedback_id: int
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    category: Optional[str] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    submitted_at: datetime
