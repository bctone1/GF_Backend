# models/user/fewshot.py

from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

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

    template_source = Column(Text, nullable=True)

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

    shares = relationship("FewShotShare", back_populates="example", passive_deletes=True)

    __table_args__ = (
        Index("idx_few_shot_examples_user", "user_id"),
        {"schema": "user"},
    )


# ========== user.few_shot_shares ==========
class FewShotShare(Base):
    """
    강사의 개인 few-shot 예제를 특정 class에 공유하는 매핑 테이블.
    - 하나의 example을 여러 class에 공유 가능
    - 같은 example_id + class_id는 한 번만(유니크)
    """

    __tablename__ = "few_shot_shares"

    share_id = Column(BigInteger, primary_key=True, autoincrement=True)

    example_id = Column(
        BigInteger,
        ForeignKey("user.few_shot_examples.example_id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id = Column(
        BigInteger,
        ForeignKey("partner.classes.id", ondelete="CASCADE"),
        nullable=False,
    )

    shared_by_user_id = Column(
        BigInteger,
        ForeignKey("user.users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    example = relationship("UserFewShotExample", back_populates="shares", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("example_id", "class_id", name="uq_few_shot_shares_example_class"),
        Index("idx_few_shot_shares_example", "example_id"),
        Index("idx_few_shot_shares_class", "class_id"),
        {"schema": "user"},
    )
