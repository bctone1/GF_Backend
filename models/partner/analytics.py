from __future__ import annotations

from sqlalchemy import Column, BigInteger, Date, Text, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from MODELS.base import Base

class PartnerAnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("partner_id", "snapshot_date", "metric_type", name="uq_partner_snapshot_date_metric"),
        {"schema": "partner"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    partner_id = Column(BigInteger, ForeignKey("partner.partners.id", ondelete="CASCADE"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    metric_type = Column(Text, nullable=False)
    metric_value = Column(Numeric(18, 4), nullable=False)
    metadata = Column(JSONB)

    partner = relationship("Partner", lazy="selectin")
