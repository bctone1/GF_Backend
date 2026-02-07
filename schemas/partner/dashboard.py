# schemas/partner/dashboard.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from schemas.base import ORMBase


class DashboardWelcome(ORMBase):
    partner_id: int
    partner_name: str
    org_name: str


class DashboardStatCards(ORMBase):
    active_classes: int = 0
    active_students: int = 0
    today_conversations: int = 0
    weekly_cost: Decimal = Decimal("0")


class DashboardActivityEvent(ORMBase):
    id: int
    event_type: str
    title: str
    description: Optional[str] = None
    class_id: Optional[int] = None
    student_id: Optional[int] = None
    meta: Dict[str, Any] = {}
    created_at: datetime


class DashboardTopStudent(ORMBase):
    rank: int
    student_id: int
    student_name: str
    conversation_count: int


class DashboardClassBudget(ORMBase):
    class_id: int
    class_name: str
    budget_used: Decimal = Decimal("0")
    budget_limit: Optional[Decimal] = None
    usage_percent: Decimal = Decimal("0")
    status: Literal["ok", "warning", "alert"] = "ok"


class DashboardResponse(ORMBase):
    welcome: DashboardWelcome
    stat_cards: DashboardStatCards
    recent_activity: List[DashboardActivityEvent] = []
    top_students: List[DashboardTopStudent] = []
    class_budgets: List[DashboardClassBudget] = []
