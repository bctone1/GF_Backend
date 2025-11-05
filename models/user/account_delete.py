# models/user/account_delete.py
from sqlalchemy import (
    Column, BigInteger, Text, DateTime,
    ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.sql import func
from models.base import Base


# ========== user.account_deletion_requests ==========
class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_requests"

    request_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(Text, nullable=False, server_default=text("'pending'"))  # pending|processing|completed|rejected
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "processed_at IS NULL OR processed_at >= requested_at",
            name="chk_account_deletion_requests_time",
        ),
        Index("idx_account_deletion_requests_user", "user_id"),
        Index("idx_account_deletion_requests_status_time", "status", "requested_at"),
        {"schema": "user"},
    )
