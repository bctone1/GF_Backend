from __future__ import annotations

from typing import Optional, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from models.partner.billing import PartnerProjectFinanceMonthly

def upsert_project_finance_monthly(
    db: Session,
    *,
    project_id: int,
    month: date,
    contract_amount: Decimal = Decimal("0"),
    api_cost: Decimal = Decimal("0"),
    platform_fee: Decimal = Decimal("0"),
    payout_amount: Decimal = Decimal("0"),
) -> PartnerProjectFinanceMonthly:
    tbl = PartnerProjectFinanceMonthly.__table__
    stmt = (
        insert(tbl)
        .values(
            project_id=project_id,
            month=month,
            contract_amount=contract_amount,
            api_cost=api_cost,
            platform_fee=platform_fee,
            payout_amount=payout_amount,
        )
        .on_conflict_do_update(
            index_elements=["project_id", "month"],
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
    obj = db.get(PartnerProjectFinanceMonthly, row["id"])
    return obj

def get_project_finance_monthly(db: Session, *, id: int) -> Optional[PartnerProjectFinanceMonthly]:
    return db.get(PartnerProjectFinanceMonthly, id)

def list_project_finance_monthly(
    db: Session,
    *,
    project_id: int,
    month_from: Optional[date] = None,
    month_to: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[PartnerProjectFinanceMonthly]:
    stmt = select(PartnerProjectFinanceMonthly).where(PartnerProjectFinanceMonthly.project_id == project_id)
    if month_from:
        stmt = stmt.where(PartnerProjectFinanceMonthly.month >= month_from)
    if month_to:
        stmt = stmt.where(PartnerProjectFinanceMonthly.month <= month_to)
    stmt = stmt.order_by(PartnerProjectFinanceMonthly.month.desc()).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()
