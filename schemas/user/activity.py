# schemas/user/activity.py
from __future__ import annotations
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import ConfigDict
from schemas.base import ORMBase


# =========================================
# user.user_activity_events  (원장)
# =========================================
class UserActivityEventCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    event_type: str
    related_type: Optional[str] = None  # 'project' | 'document' | 'prompt' | ...
    related_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class UserActivityEventUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # 로그는 불변에 가깝게 운용. 수정 허용 범위 최소화.
    metadata: Optional[Dict[str, Any]] = None


class UserActivityEventResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    event_id: int
    user_id: int
    event_type: str
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: datetime


# =========================================
# user.usage_summaries 〈집계 전용: 읽기 전용〉
# =========================================
class UsageSummaryResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    summary_id: int
    user_id: int
    period_start: date
    period_end: date
    metric_type: str
    metric_value: Decimal


# =========================================
# user.model_usage_stats 〈집계 전용: 읽기 전용〉
# =========================================
class ModelUsageStatResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    stat_id: int
    user_id: int
    model_name: str
    usage_count: int
    total_tokens: int
    avg_latency_ms: Optional[int] = None
    satisfaction_score: Optional[Decimal] = None
    last_used_at: Optional[datetime] = None


# =========================================
# user.user_achievements
# =========================================
class UserAchievementCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    user_id: int
    achievement_key: str
    metadata: Optional[Dict[str, Any]] = None


class UserAchievementUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    # 기본적으로 불변. 메타데이터만 갱신 허용.
    metadata: Optional[Dict[str, Any]] = None


class UserAchievementResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    achievement_id: int
    user_id: int
    achievement_key: str
    earned_at: datetime
    metadata: Optional[Dict[str, Any]] = None


# =========================================
# user.practice_feature_stats 〈집계 전용: 읽기 전용〉
# =========================================
class PracticeFeatureStatResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    stat_id: int
    user_id: int
    class_id: Optional[int] = None
    feature_type: str
    usage_count: int
    last_used_at: Optional[datetime] = None
