# schemas/supervisor/ops.py
from __future__ import annotations
from typing import Any, Optional, Dict
from decimal import Decimal
from datetime import datetime
from schemas.base import ORMBase


# ========== supervisor.system_metrics ==========
class SystemMetricCreate(ORMBase):
    metric_type: str                 # cpu_usage, mem_used_mb, qps 등
    resource: str                    # 호스트명, 서비스명, 노드ID 등
    value: Decimal
    unit: Optional[str] = None
    recorded_at: Optional[datetime] = None
    tags_json: Optional[Dict[str, Any]] = None


class SystemMetricUpdate(ORMBase):
    metric_type: Optional[str] = None
    resource: Optional[str] = None
    value: Optional[Decimal] = None
    unit: Optional[str] = None
    recorded_at: Optional[datetime] = None
    tags_json: Optional[Dict[str, Any]] = None


class SystemMetricResponse(ORMBase):
    metric_id: int
    metric_type: str
    resource: str
    value: Decimal
    unit: Optional[str] = None
    recorded_at: datetime
    tags_json: Optional[Dict[str, Any]] = None


# ========== supervisor.service_status ==========
class ServiceStatusCreate(ORMBase):
    service_name: str
    status: str = "ok"               # ok | degraded | down | maintenance
    message: Optional[str] = None
    checked_at: Optional[datetime] = None


class ServiceStatusUpdate(ORMBase):
    status: Optional[str] = None
    message: Optional[str] = None
    checked_at: Optional[datetime] = None


class ServiceStatusResponse(ORMBase):
    status_id: int
    service_name: str
    status: str
    message: Optional[str] = None
    checked_at: datetime


# ========== supervisor.alerts ==========
class AlertCreate(ORMBase):
    category: str                    # billing | ops | security ...
    severity: str                    # low | medium | high | critical
    title: str
    description: Optional[str] = None
    status: str = "open"             # open | acknowledged | resolved
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None


class AlertUpdate(ORMBase):
    category: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None


class AlertResponse(ORMBase):
    alert_id: int
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None


# ========== supervisor.events ==========
class EventCreate(ORMBase):
    source: str                      # 'billing.invoice', 'user.signup' 등
    level: str                       # debug | info | warning | error | critical
    message: str
    metadata_json: Optional[Dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class EventUpdate(ORMBase):
    # 일반적으로 이벤트는 불변이지만, 필요시 메시지/메타데이터 수정 허용
    message: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class EventResponse(ORMBase):
    event_id: int
    source: str
    level: str
    message: str
    metadata_json: Optional[Dict[str, Any]] = None
    occurred_at: datetime


# ========== supervisor.logs ==========
class LogCreate(ORMBase):
    service_name: str
    level: str                       # debug | info | warning | error | critical
    message: str
    context_json: Optional[Dict[str, Any]] = None
    logged_at: Optional[datetime] = None


class LogUpdate(ORMBase):
    message: Optional[str] = None
    context_json: Optional[Dict[str, Any]] = None


class LogResponse(ORMBase):
    log_id: int
    service_name: str
    level: str
    message: str
    context_json: Optional[Dict[str, Any]] = None
    logged_at: datetime
