# crud/partner/billing.py
from __future__ import annotations

from typing import Optional, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from models.partner.billing import ClassFinanceMonthly  # 신규 모델로 교체


def upsert_enrollment_finance_monthly(
    db: Session,
    *,
    enrollment_id: int,
    month: date,
    contract_amount: Decimal = Decimal("0"),
    api_cost: Decimal = Decimal("0"),
    platform_fee: Decimal = Decimal("0"),
    payout_amount: Decimal = Decimal("0"),
) -> ClassFinanceMonthly:
    """
    partner.enrollment_finance_monthly에 (enrollment_id, month) 단위로 upsert.
    """
    tbl = ClassFinanceMonthly.__table__
    stmt = (
        insert(tbl)
        .values(
            enrollment_id=enrollment_id,
            month=month,
            contract_amount=contract_amount,
            api_cost=api_cost,
            platform_fee=platform_fee,
            payout_amount=payout_amount,
        )
        .on_conflict_do_update(
            index_elements=["enrollment_id", "month"],
            set_={
                "contract_amount": contract_amount,
                "api_cost": api_cost,
                "platform_fee": platform_fee,
                "payout_amount": payout_amount,
            },
        )
        .returning(tbl)
    )
    row = db.execute(stmt).mappings().one()
    return db.get(ClassFinanceMonthly, row["id"])


def get_enrollment_finance_monthly(
    db: Session, *, id: int
) -> Optional[ClassFinanceMonthly]:
    return db.get(ClassFinanceMonthly, id)


def list_enrollment_finance_monthly(
    db: Session,
    *,
    enrollment_id: int,
    month_from: Optional[date] = None,
    month_to: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[ClassFinanceMonthly]:
    """
    특정 수강(enrollment) 단위 월별 정산 내역 조회.
    """
    stmt = select(ClassFinanceMonthly).where(
        ClassFinanceMonthly.enrollment_id == enrollment_id
    )
    if month_from:
        stmt = stmt.where(ClassFinanceMonthly.month >= month_from)
    if month_to:
        stmt = stmt.where(ClassFinanceMonthly.month <= month_to)
    stmt = stmt.order_by(ClassFinanceMonthly.month.desc()).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()
