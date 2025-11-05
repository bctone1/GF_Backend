# schemas/supervisor/env.py
from __future__ import annotations
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from schemas.base import ORMBase


# ========== supervisor.env_variables ==========
class EnvVariableCreate(ORMBase):
    key: str
    value: Optional[str] = None
    scope: str                       # global | org | user
    encrypted: bool = False
    updated_by: Optional[int] = None


class EnvVariableUpdate(ORMBase):
    key: Optional[str] = None
    value: Optional[str] = None
    scope: Optional[str] = None
    encrypted: Optional[bool] = None
    updated_by: Optional[int] = None


class EnvVariableResponse(ORMBase):
    env_id: int
    key: str
    value: Optional[str] = None
    scope: str
    encrypted: bool
    updated_at: datetime
    updated_by: Optional[int] = None


# ========== supervisor.danger_zone_logs ==========
class DangerZoneLogCreate(ORMBase):
    action_type: str                 # purge_data | rotate_keys | ...
    performed_by: Optional[int] = None
    performed_at: Optional[datetime] = None
    notes: Optional[str] = None


class DangerZoneLogUpdate(ORMBase):
    notes: Optional[str] = None


class DangerZoneLogResponse(ORMBase):
    action_id: int
    action_type: str
    performed_by: Optional[int] = None
    performed_at: datetime
    notes: Optional[str] = None


# ========== supervisor.feature_toggles ==========
class FeatureToggleCreate(ORMBase):
    feature_name: str
    is_enabled: bool = False
    scope: Optional[str] = None          # global | org | user
    target_id: Optional[int] = None
    rollout_pct: Optional[int] = None    # 0..100
    description: Optional[str] = None
    updated_by: Optional[int] = None


class FeatureToggleUpdate(ORMBase):
    feature_name: Optional[str] = None
    is_enabled: Optional[bool] = None
    scope: Optional[str] = None
    target_id: Optional[int] = None
    rollout_pct: Optional[int] = None
    description: Optional[str] = None
    updated_by: Optional[int] = None


class FeatureToggleResponse(ORMBase):
    toggle_id: int
    feature_name: str
    is_enabled: bool
    scope: Optional[str] = None
    target_id: Optional[int] = None
    rollout_pct: Optional[int] = None
    description: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[int] = None


# ========== supervisor.usage_features ==========
class UsageFeatureCreate(ORMBase):
    organization_id: int
    feature_name: str
    usage_count: int = 0
    period: date


class UsageFeatureUpdate(ORMBase):
    feature_name: Optional[str] = None
    usage_count: Optional[int] = None
    period: Optional[date] = None


class UsageFeatureResponse(ORMBase):
    record_id: int
    organization_id: int
    feature_name: str
    usage_count: int
    period: date
    updated_at: datetime


# ========== supervisor.ai_insights ==========
class AiInsightCreate(ORMBase):
    category: str
    title: str
    description: Optional[str] = None
    data_points_json: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None


class AiInsightUpdate(ORMBase):
    category: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    data_points_json: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None


class AiInsightResponse(ORMBase):
    insight_id: int
    category: str
    title: str
    description: Optional[str] = None
    data_points_json: Optional[Dict[str, Any]] = None
    generated_at: datetime


# ========== supervisor.forecasts ==========
class ForecastCreate(ORMBase):
    metric_type: str                  # mrr | dau | tokens ...
    period: date
    value: Decimal
    model_info: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None
    confidence_interval_json: Optional[Dict[str, Any]] = None


class ForecastUpdate(ORMBase):
    metric_type: Optional[str] = None
    period: Optional[date] = None
    value: Optional[Decimal] = None
    model_info: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None
    confidence_interval_json: Optional[Dict[str, Any]] = None


class ForecastResponse(ORMBase):
    forecast_id: int
    metric_type: str
    period: date
    value: Decimal
    model_info: Optional[Dict[str, Any]] = None
    generated_at: datetime
    confidence_interval_json: Optional[Dict[str, Any]] = None
