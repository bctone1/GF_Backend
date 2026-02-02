# models/user/fewshot.py

from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


# ========== user.few_shot_examples (개인 라이브러리) ==========
class UserFewShotExample(Base):
    __tablename__ = "few_shot_examples"

    example_id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    title = Column(Text, nullable=True)

    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)

    meta = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_few_shot_examples_user", "user_id"),
        {"schema": "user"},
    )
