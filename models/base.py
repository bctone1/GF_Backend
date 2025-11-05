# Base, MetaData(naming_convention)만
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy import MetaData, Column, BigInteger, DateTime, text

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
    "ixu": "ixu_%(table_name)s_%(column_0_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)

class IdPKMixin:
    id = Column(BigInteger, primary_key=True, autoincrement=True)

class TimeStampMixin:
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
