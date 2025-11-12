# crud/supervisor/settings.py
from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from sqlalchemy import select, func, update, delete, and_, text
from sqlalchemy.orm import Session

from models.supervisor.settings import (
    PlatformSetting, ApiKey, RateLimit, Webhook, LlmProvider, EmailSetting, Integration
)

# 공통: 페이지네이션 유틸
def _paginate(stmt, count_stmt, db: Session, page: int, size: int):
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.offset((page - 1) * size).limit(size)).scalars().all()
    return rows, total


# ==============================
# PlatformSetting
# ==============================
class PlatformSettingCRUD:
    def get(self, db: Session, setting_id: int) -> Optional[PlatformSetting]:
        return db.get(PlatformSetting, setting_id)

    def get_by_category_key(self, db: Session, *, category: str, key: str) -> Optional[PlatformSetting]:
        stmt = select(PlatformSetting).where(
            PlatformSetting.category == category,
            PlatformSetting.key == key
        )
        return db.execute(stmt).scalars().first()

    def list(
        self,
        db: Session,
        *,
        category: Optional[str] = None,
        key: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[PlatformSetting], int]:
        conds = []
        if category:
            conds.append(PlatformSetting.category == category)
        if key:
            conds.append(PlatformSetting.key == key)

        where = and_(*conds) if conds else text("TRUE")
        stmt = (
            select(PlatformSetting)
            .where(where)
            .order_by(PlatformSetting.updated_at.desc())
        )
        count_stmt = select(func.count()).select_from(PlatformSetting).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> PlatformSetting:
        obj = PlatformSetting(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, setting_id: int, data: Dict[str, Any]) -> Optional[PlatformSetting]:
        obj = self.get(db, setting_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, setting_id: int) -> bool:
        obj = self.get(db, setting_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# ApiKey
# ==============================
class ApiKeyCRUD:
    def get(self, db: Session, api_key_id: int) -> Optional[ApiKey]:
        return db.get(ApiKey, api_key_id)

    def get_by_hash(self, db: Session, key_hash: str) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        return db.execute(stmt).scalars().first()

    def list(
        self,
        db: Session,
        *,
        name: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ApiKey], int]:
        conds = []
        if name:
            conds.append(ApiKey.name.ilike(f"%{name}%"))
        if status:
            conds.append(ApiKey.status == status)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(ApiKey).where(where).order_by(ApiKey.created_at.desc())
        count_stmt = select(func.count()).select_from(ApiKey).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> ApiKey:
        obj = ApiKey(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def touch_last_used(self, db: Session, api_key_id: int, at: Optional[datetime] = None) -> bool:
        obj = self.get(db, api_key_id)
        if not obj:
            return False
        obj.last_used_at = at or datetime.utcnow()
        db.commit()
        return True

    def update(self, db: Session, api_key_id: int, data: Dict[str, Any]) -> Optional[ApiKey]:
        obj = self.get(db, api_key_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, api_key_id: int) -> bool:
        obj = self.get(db, api_key_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# RateLimit
# ==============================
class RateLimitCRUD:
    def get(self, db: Session, limit_id: int) -> Optional[RateLimit]:
        return db.get(RateLimit, limit_id)

    def list(
        self,
        db: Session,
        *,
        plan_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        limit_type: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[RateLimit], int]:
        conds = []
        if plan_id is not None:
            conds.append(RateLimit.plan_id == plan_id)
        if organization_id is not None:
            conds.append(RateLimit.organization_id == organization_id)
        if limit_type:
            conds.append(RateLimit.limit_type == limit_type)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(RateLimit).where(where).order_by(RateLimit.updated_at.desc())
        count_stmt = select(func.count()).select_from(RateLimit).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> RateLimit:
        # XOR(plan_id, organization_id)은 DB CheckConstraint로 보장
        obj = RateLimit(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, limit_id: int, data: Dict[str, Any]) -> Optional[RateLimit]:
        obj = self.get(db, limit_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, limit_id: int) -> bool:
        obj = self.get(db, limit_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# Webhook
# ==============================
class WebhookCRUD:
    def get(self, db: Session, webhook_id: int) -> Optional[Webhook]:
        return db.get(Webhook, webhook_id)

    def list(
        self,
        db: Session,
        *,
        organization_id: Optional[int] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[Webhook], int]:
        conds = []
        if organization_id is not None:
            conds.append(Webhook.organization_id == organization_id)
        if event_type:
            conds.append(Webhook.event_type == event_type)
        if status:
            conds.append(Webhook.status == status)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(Webhook).where(where).order_by(Webhook.created_at.desc())
        count_stmt = select(func.count()).select_from(Webhook).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> Webhook:
        obj = Webhook(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, webhook_id: int, data: Dict[str, Any]) -> Optional[Webhook]:
        obj = self.get(db, webhook_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, webhook_id: int) -> bool:
        obj = self.get(db, webhook_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# LlmProvider
# ==============================
class LlmProviderCRUD:
    def get(self, db: Session, provider_id: int) -> Optional[LlmProvider]:
        return db.get(LlmProvider, provider_id)

    def get_by_name(self, db: Session, provider_name: str) -> Optional[LlmProvider]:
        stmt = select(LlmProvider).where(LlmProvider.provider_name == provider_name)
        return db.execute(stmt).scalars().first()

    def list(
        self,
        db: Session,
        *,
        provider_name: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[LlmProvider], int]:
        conds = []
        if provider_name:
            conds.append(LlmProvider.provider_name == provider_name)
        if status:
            conds.append(LlmProvider.status == status)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(LlmProvider).where(where).order_by(LlmProvider.provider_id.desc())
        count_stmt = select(func.count()).select_from(LlmProvider).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> LlmProvider:
        obj = LlmProvider(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, provider_id: int, data: Dict[str, Any]) -> Optional[LlmProvider]:
        obj = self.get(db, provider_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, provider_id: int) -> bool:
        obj = self.get(db, provider_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# EmailSetting
# ==============================
class EmailSettingCRUD:
    def get(self, db: Session, email_setting_id: int) -> Optional[EmailSetting]:
        return db.get(EmailSetting, email_setting_id)

    def list(
        self,
        db: Session,
        *,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[EmailSetting], int]:
        conds = []
        if smtp_host:
            conds.append(EmailSetting.smtp_host == smtp_host)
        if smtp_port is not None:
            conds.append(EmailSetting.smtp_port == smtp_port)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(EmailSetting).where(where).order_by(EmailSetting.email_setting_id.desc())
        count_stmt = select(func.count()).select_from(EmailSetting).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> EmailSetting:
        obj = EmailSetting(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, email_setting_id: int, data: Dict[str, Any]) -> Optional[EmailSetting]:
        obj = self.get(db, email_setting_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, email_setting_id: int) -> bool:
        obj = self.get(db, email_setting_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# ==============================
# Integration
# ==============================
class IntegrationCRUD:
    def get(self, db: Session, integration_id: int) -> Optional[Integration]:
        return db.get(Integration, integration_id)

    def list(
        self,
        db: Session,
        *,
        type_: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[Integration], int]:
        conds = []
        if type_:
            conds.append(Integration.type == type_)
        if status:
            conds.append(Integration.status == status)

        where = and_(*conds) if conds else text("TRUE")
        stmt = select(Integration).where(where).order_by(Integration.created_at.desc())
        count_stmt = select(func.count()).select_from(Integration).where(where)
        return _paginate(stmt, count_stmt, db, page, size)

    def create(self, db: Session, data: Dict[str, Any]) -> Integration:
        obj = Integration(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, integration_id: int, data: Dict[str, Any]) -> Optional[Integration]:
        obj = self.get(db, integration_id)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, integration_id: int) -> bool:
        obj = self.get(db, integration_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


# 인스턴스 (엔드포인트에서 바로 import해 사용)
platform_setting = PlatformSettingCRUD()
api_key = ApiKeyCRUD()
rate_limit = RateLimitCRUD()
webhook = WebhookCRUD()
llm_provider = LlmProviderCRUD()
email_setting = EmailSettingCRUD()
integration = IntegrationCRUD()
