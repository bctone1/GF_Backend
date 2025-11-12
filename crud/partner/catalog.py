# crud/partner/catalog.py
from __future__ import annotations
from typing import Optional, Tuple, List
from datetime import datetime

from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.partner.catalog import (
    ProviderCredential,
    ModelCatalog,
    OrgLlmSetting,
)


# ==============================
# 공통: 페이지네이션 유틸
# ==============================
def _paginate(stmt, db: Session, page: int, size: int):
    page = max(page or 1, 1)
    size = min(max(size or 50, 1), 200)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.limit(size).offset((page - 1) * size)).scalars().all()
    return rows, total


# ==============================
# ProviderCredential CRUD
# ==============================
class ProviderCredentialCRUD:
    model = ProviderCredential

    def get(self, db: Session, id: int) -> Optional[ProviderCredential]:
        return db.get(self.model, id)

    def get_by_partner_provider(
        self, db: Session, *, partner_id: int, provider: str
    ) -> Optional[ProviderCredential]:
        stmt = select(self.model).where(
            self.model.partner_id == partner_id,
            self.model.provider == provider,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        db: Session,
        *,
        partner_id: Optional[int] = None,
        provider: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ProviderCredential], int]:
        stmt = select(self.model)
        conds = []
        if partner_id is not None:
            conds.append(self.model.partner_id == partner_id)
        if provider is not None:
            conds.append(self.model.provider == provider)
        if is_active is not None:
            conds.append(self.model.is_active == is_active)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(self.model.partner_id.asc(), self.model.provider.asc(), self.model.id.asc())
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        partner_id: int,
        provider: str,
        api_key_encrypted: str,
        credential_label: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> ProviderCredential:
        obj = self.model(
            partner_id=partner_id,
            provider=provider,
            credential_label=credential_label,
            api_key_encrypted=api_key_encrypted,
        )
        if is_active is not None:
            obj.is_active = is_active
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약 충돌 가능: (partner_id, provider)
            raise
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        id: int,
        credential_label: Optional[str] = None,
        api_key_encrypted: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ProviderCredential]:
        values = {}
        if credential_label is not None:
            values["credential_label"] = credential_label
        if api_key_encrypted is not None:
            values["api_key_encrypted"] = api_key_encrypted
        if is_active is not None:
            values["is_active"] = is_active
        if not values:
            return self.get(db, id)

        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, id)

    def mark_validated(self, db: Session, *, id: int, at: Optional[datetime] = None) -> None:
        at = at or func.now()
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(last_validated_at=at)
        )
        db.execute(stmt)
        db.commit()

    def delete(self, db: Session, *, id: int) -> None:
        db.execute(delete(self.model).where(self.model.id == id))
        db.commit()


# ==============================
# ModelCatalog CRUD
# ==============================
class ModelCatalogCRUD:
    model = ModelCatalog

    def get(self, db: Session, id: int) -> Optional[ModelCatalog]:
        return db.get(self.model, id)

    def get_by_provider_model(
        self, db: Session, *, provider: str, model_name: str
    ) -> Optional[ModelCatalog]:
        stmt = select(self.model).where(
            self.model.provider == provider,
            self.model.model_name == model_name,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        db: Session,
        *,
        provider: Optional[str] = None,
        modality: Optional[str] = None,
        is_active: Optional[bool] = None,
        q: Optional[str] = None,  # model_name like
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ModelCatalog], int]:
        stmt = select(self.model)
        conds = []
        if provider is not None:
            conds.append(self.model.provider == provider)
        if modality is not None:
            conds.append(self.model.modality == modality)
        if is_active is not None:
            conds.append(self.model.is_active == is_active)
        if q:
            conds.append(self.model.model_name.ilike(f"%{q}%"))
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(self.model.provider.asc(), self.model.model_name.asc())
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        provider: str,
        model_name: str,
        modality: Optional[str] = None,
        supports_parallel: Optional[bool] = None,
        default_pricing: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> ModelCatalog:
        obj = self.model(
            provider=provider,
            model_name=model_name,
        )
        if modality is not None:
            obj.modality = modality
        if supports_parallel is not None:
            obj.supports_parallel = supports_parallel
        if default_pricing is not None:
            obj.default_pricing = default_pricing
        if is_active is not None:
            obj.is_active = is_active
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약 충돌: (provider, model_name)
            raise
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        id: int,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        modality: Optional[str] = None,
        supports_parallel: Optional[bool] = None,
        default_pricing: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ModelCatalog]:
        values = {}
        if provider is not None:
            values["provider"] = provider
        if model_name is not None:
            values["model_name"] = model_name
        if modality is not None:
            values["modality"] = modality
        if supports_parallel is not None:
            values["supports_parallel"] = supports_parallel
        if default_pricing is not None:
            values["default_pricing"] = default_pricing
        if is_active is not None:
            values["is_active"] = is_active
        if not values:
            return self.get(db, id)

        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, id)

    def delete(self, db: Session, *, id: int) -> None:
        db.execute(delete(self.model).where(self.model.id == id))
        db.commit()

    # 파트너가 실제 선택 가능(키 보유 + 모델 활성)한 모델 목록
    def list_available_for_partner(
        self,
        db: Session,
        *,
        partner_id: int,
        modality: Optional[str] = "chat",
        only_active: bool = True,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ModelCatalog], int]:
        mc = self.model
        pc = ProviderCredential
        stmt = (
            select(mc)
            .join(pc, pc.provider == mc.provider)
            .where(pc.partner_id == partner_id)
        )
        if modality:
            stmt = stmt.where(mc.modality == modality)
        if only_active:
            stmt = stmt.where(mc.is_active.is_(True), pc.is_active.is_(True))
        stmt = stmt.order_by(mc.provider.asc(), mc.model_name.asc(), mc.id.asc())
        return _paginate(stmt, db, page, size)


# ==============================
# OrgLlmSetting CRUD
# ==============================
class OrgLlmSettingCRUD:
    model = OrgLlmSetting

    def get(self, db: Session, id: int) -> Optional[OrgLlmSetting]:
        return db.get(self.model, id)

    def get_by_partner(self, db: Session, *, partner_id: int) -> Optional[OrgLlmSetting]:
        stmt = select(self.model).where(self.model.partner_id == partner_id)
        return db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        db: Session,
        *,
        partner_id: int,
        default_chat_model: str,
        enable_parallel_mode: Optional[bool] = None,
        daily_message_limit: Optional[int] = None,
        token_alert_threshold: Optional[int] = None,
        provider_credential_id: Optional[int] = None,
        updated_by: Optional[int] = None,
    ) -> OrgLlmSetting:
        obj = self.model(
            partner_id=partner_id,
            default_chat_model=default_chat_model,
            provider_credential_id=provider_credential_id,
            updated_by=updated_by,
        )
        if enable_parallel_mode is not None:
            obj.enable_parallel_mode = enable_parallel_mode
        if daily_message_limit is not None:
            obj.daily_message_limit = daily_message_limit
        if token_alert_threshold is not None:
            obj.token_alert_threshold = token_alert_threshold

        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약: partner_id 당 1행
            raise
        db.refresh(obj)
        return obj

    def upsert_by_partner(
        self,
        db: Session,
        *,
        partner_id: int,
        default_chat_model: Optional[str] = None,
        enable_parallel_mode: Optional[bool] = None,
        daily_message_limit: Optional[int] = None,
        token_alert_threshold: Optional[int] = None,
        provider_credential_id: Optional[int] = None,
        updated_by: Optional[int] = None,
    ) -> OrgLlmSetting:
        cur = self.get_by_partner(db, partner_id=partner_id)
        if cur is None:
            return self.create(
                db,
                partner_id=partner_id,
                default_chat_model=default_chat_model or "gpt-4o-mini",
                enable_parallel_mode=enable_parallel_mode,
                daily_message_limit=daily_message_limit,
                token_alert_threshold=token_alert_threshold,
                provider_credential_id=provider_credential_id,
                updated_by=updated_by,
            )

        # update path
        values = {}
        if default_chat_model is not None:
            values["default_chat_model"] = default_chat_model
        if enable_parallel_mode is not None:
            values["enable_parallel_mode"] = enable_parallel_mode
        if daily_message_limit is not None:
            values["daily_message_limit"] = daily_message_limit
        if token_alert_threshold is not None:
            values["token_alert_threshold"] = token_alert_threshold
        if provider_credential_id is not None:
            values["provider_credential_id"] = provider_credential_id
        if updated_by is not None:
            values["updated_by"] = updated_by
        if not values:
            return cur

        stmt = (
            update(self.model)
            .where(self.model.id == cur.id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, cur.id)

    def update(
        self,
        db: Session,
        *,
        id: int,
        default_chat_model: Optional[str] = None,
        enable_parallel_mode: Optional[bool] = None,
        daily_message_limit: Optional[int] = None,
        token_alert_threshold: Optional[int] = None,
        provider_credential_id: Optional[int] = None,
        updated_by: Optional[int] = None,
    ) -> Optional[OrgLlmSetting]:
        values = {}
        if default_chat_model is not None:
            values["default_chat_model"] = default_chat_model
        if enable_parallel_mode is not None:
            values["enable_parallel_mode"] = enable_parallel_mode
        if daily_message_limit is not None:
            values["daily_message_limit"] = daily_message_limit
        if token_alert_threshold is not None:
            values["token_alert_threshold"] = token_alert_threshold
        if provider_credential_id is not None:
            values["provider_credential_id"] = provider_credential_id
        if updated_by is not None:
            values["updated_by"] = updated_by
        if not values:
            return self.get(db, id)

        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, id)

    def delete(self, db: Session, *, id: int) -> None:
        db.execute(delete(self.model).where(self.model.id == id))
        db.commit()


# 인스턴스
provider_credential = ProviderCredentialCRUD()
model_catalog = ModelCatalogCRUD()
org_llm_setting = OrgLlmSettingCRUD()
