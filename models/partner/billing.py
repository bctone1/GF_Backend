from __future__ import annotations

from decimal import Decimal
from sqlalchemy import Column, BigInteger, Date, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from MODELS.base import Base

class PartnerProjectFinanceMonthly(Base):
    __tablename__ = "project_finance_monthly"
    __table_args__ = (
        UniqueConstraint("project_id", "month", name="uq_project_month"),
        {"schema": "partner"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("partner.projects.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date, nullable=False)
    contract_amount = Column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    api_cost = Column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    platform_fee = Column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    payout_amount = Column(Numeric(14, 2), nullable=False, default=Decimal("0"))

    project = relationship("PartnerProject", lazy="selectin")
