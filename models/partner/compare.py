# models/partner/compare.py
from sqlalchemy import (
    Column, BigInteger, Text, Integer, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


# ========== partner.comparison_runs ==========
class ComparisonRun(Base):
    __tablename__ = "comparison_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    project_id = Column(
        BigInteger,
        ForeignKey("partner.projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = Column(
        BigInteger,
        ForeignKey("partner.students.id", ondelete="SET NULL"),
        nullable=True,
    )
    initiated_by = Column(
        BigInteger,
        ForeignKey("partner.partner_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(Text, nullable=False, server_default=text("'running'"))  # running|completed|failed|canceled
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)

    items = relationship("ComparisonRunItem", back_populates="run", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed','canceled')",
            name="chk_comparison_runs_status",
        ),
        CheckConstraint(
            "(completed_at IS NULL) OR (completed_at >= started_at)",
            name="chk_comparison_runs_time",
        ),
        Index("idx_comparison_runs_project_time", "project_id", "started_at"),
        Index("idx_comparison_runs_status_time", "status", "started_at"),
        {"schema": "partner"},
    )


# ========== partner.comparison_run_items ==========
class ComparisonRunItem(Base):
    __tablename__ = "comparison_run_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    run_id = Column(
        BigInteger,
        ForeignKey("partner.comparison_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    model_name = Column(Text, nullable=False)
    prompt_template_version_id = Column(
        BigInteger,
        ForeignKey("partner.prompt_template_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(Text, nullable=False, server_default=text("'pending'"))  # pending|running|success|error
    total_tokens = Column(Integer, nullable=True)
    average_latency_ms = Column(Integer, nullable=True)
    total_cost = Column(Numeric(14, 4), nullable=True)

    run = relationship("ComparisonRun", back_populates="items", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("run_id", "model_name", name="uq_comparison_run_items_run_model"),
        CheckConstraint(
            "status IN ('pending','running','success','error')",
            name="chk_comparison_run_items_status",
        ),
        CheckConstraint("total_tokens IS NULL OR total_tokens >= 0", name="chk_comparison_run_items_tokens_nonneg"),
        CheckConstraint("average_latency_ms IS NULL OR average_latency_ms >= 0", name="chk_comparison_run_items_latency_nonneg"),
        CheckConstraint("total_cost IS NULL OR total_cost >= 0", name="chk_comparison_run_items_cost_nonneg"),
        Index("idx_comparison_run_items_run", "run_id"),
        Index("idx_comparison_run_items_status", "status"),
        {"schema": "partner"},
    )
