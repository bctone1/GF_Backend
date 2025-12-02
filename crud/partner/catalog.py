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

from schemas.partner.catalog import (
    ProviderCredentialCreate,
    ProviderCredentialUpdate,
    ModelCatalogCreate,
    ModelCatalogUpdate,
    OrgLlmSettingCreate,
    OrgLlmSettingUpdate,
)


# ==============================
# 공통: 페이지네이션 유틸
# ==============================
def _paginate(stmt, db: Session, page: int, size: int):
    page = max(page or 1, 1)
    size = min(max(size or 50, 1), 200)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.limit(size).offset((page - 1) * size)
    ).scalars().all()
    return rows, total


# ==============================
# ProviderCredential CRUD
# ==============================
class ProviderCredentialCRUD:
    model = ProviderCredential

    def get(self, db: Session, id: int) -> Optional[ProviderCredential]:
        return db.get(self.model, id)

    def get_by_org_provider(
        self,
        db: Session,
        *,
        org_id: int,
        provider: str,
    ) -> Optional[ProviderCredential]:
        stmt = select(self.model).where(
            self.model.org_id == org_id,
            self.model.provider == provider,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        db: Session,
        *,
        org_id: Optional[int] = None,
        provider: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ProviderCredential], int]:
        stmt = select(self.model)
        conds = []
        if org_id is not None:
            conds.append(self.model.org_id == org_id)
        if provider is not None:
            conds.append(self.model.provider == provider)
        if is_active is not None:
            conds.append(self.model.is_active == is_active)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(
            self.model.org_id.asc(),
            self.model.provider.asc(),
            self.model.id.asc(),
        )
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        data: ProviderCredentialCreate,
    ) -> ProviderCredential:
        obj = self.model(
            org_id=data.org_id,
            provider=data.provider,
            credential_label=data.credential_label,
            api_key_encrypted=data.api_key_encrypted,
        )
        if data.is_active is not None:
            obj.is_active = data.is_active

        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약 충돌 가능: (org_id, provider)
            raise
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        id: int,
        data: ProviderCredentialUpdate,
    ) -> Optional[ProviderCredential]:
        values: dict = {}
        if data.credential_label is not None:
            values["credential_label"] = data.credential_label
        if data.api_key_encrypted is not None:
            values["api_key_encrypted"] = data.api_key_encrypted
        if data.is_active is not None:
            values["is_active"] = data.is_active
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

    def mark_validated(
        self,
        db: Session,
        *,
        id: int,
        at: Optional[datetime] = None,
    ) -> None:
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
        self,
        db: Session,
        *,
        provider: str,
        model_name: str,
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
        stmt = stmt.order_by(
            self.model.provider.asc(),
            self.model.model_name.asc(),
        )
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        data: ModelCatalogCreate,
    ) -> ModelCatalog:
        obj = self.model(
            provider=data.provider,
            model_name=data.model_name,
        )
        if data.modality is not None:
            obj.modality = data.modality
        if data.supports_parallel is not None:
            obj.supports_parallel = data.supports_parallel
        if data.default_pricing is not None:
            obj.default_pricing = data.default_pricing
        if data.is_active is not None:
            obj.is_active = data.is_active

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
        data: ModelCatalogUpdate,
    ) -> Optional[ModelCatalog]:
        values: dict = {}
        if data.provider is not None:
            values["provider"] = data.provider
        if data.model_name is not None:
            values["model_name"] = data.model_name
        if data.modality is not None:
            values["modality"] = data.modality
        if data.supports_parallel is not None:
            values["supports_parallel"] = data.supports_parallel
        if data.default_pricing is not None:
            values["default_pricing"] = data.default_pricing
        if data.is_active is not None:
            values["is_active"] = data.is_active
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

    # Org가 실제 선택 가능(키 보유 + 모델 활성)한 모델 목록
    def list_available_for_org(
        self,
        db: Session,
        *,
        org_id: int,
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
            .where(pc.org_id == org_id)
        )
        if modality:
            stmt = stmt.where(mc.modality == modality)
        if only_active:
            stmt = stmt.where(
                mc.is_active.is_(True),
                pc.is_active.is_(True),
            )
        stmt = stmt.order_by(
            mc.provider.asc(),
            mc.model_name.asc(),
            mc.id.asc(),
        )
        return _paginate(stmt, db, page, size)


# ==============================
# OrgLlmSetting CRUD
# ==============================
class OrgLlmSettingCRUD:
    model = OrgLlmSetting

    def get(self, db: Session, id: int) -> Optional[OrgLlmSetting]:
        return db.get(self.model, id)

    def get_by_org(
        self,
        db: Session,
        *,
        org_id: int,
    ) -> Optional[OrgLlmSetting]:
        stmt = select(self.model).where(self.model.org_id == org_id)
        return db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        db: Session,
        *,
        data: OrgLlmSettingCreate,
    ) -> OrgLlmSetting:
        obj = self.model(
            org_id=data.org_id,
            default_chat_model=data.default_chat_model,
            provider_credential_id=data.provider_credential_id,
            updated_by=data.updated_by,
        )
        if data.enable_parallel_mode is not None:
            obj.enable_parallel_mode = data.enable_parallel_mode
        if data.daily_message_limit is not None:
            obj.daily_message_limit = data.daily_message_limit
        if data.token_alert_threshold is not None:
            obj.token_alert_threshold = data.token_alert_threshold

        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약: org_id 당 1행
            raise
        db.refresh(obj)
        return obj

    def upsert_by_org(
        self,
        db: Session,
        *,
        org_id: int,
        data: OrgLlmSettingUpdate,
    ) -> OrgLlmSetting:
        cur = self.get_by_org(db, org_id=org_id)
        if cur is None:
            # 기본값이 없으면 gpt-4o-mini 로 세팅
            default_chat_model = data.default_chat_model or "gpt-4o-mini"
            create_data = OrgLlmSettingCreate(
                org_id=org_id,
                default_chat_model=default_chat_model,
                enable_parallel_mode=data.enable_parallel_mode,
                daily_message_limit=data.daily_message_limit,
                token_alert_threshold=data.token_alert_threshold,
                provider_credential_id=data.provider_credential_id,
                updated_by=data.updated_by,
            )
            return self.create(db, data=create_data)

        # update path
        values: dict = {}
        if data.default_chat_model is not None:
            values["default_chat_model"] = data.default_chat_model
        if data.enable_parallel_mode is not None:
            values["enable_parallel_mode"] = data.enable_parallel_mode
        if data.daily_message_limit is not None:
            values["daily_message_limit"] = data.daily_message_limit
        if data.token_alert_threshold is not None:
            values["token_alert_threshold"] = data.token_alert_threshold
        if data.provider_credential_id is not None:
            values["provider_credential_id"] = data.provider_credential_id
        if data.updated_by is not None:
            values["updated_by"] = data.updated_by
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
        data: OrgLlmSettingUpdate,
    ) -> Optional[OrgLlmSetting]:
        values: dict = {}
        if data.default_chat_model is not None:
            values["default_chat_model"] = data.default_chat_model
        if data.enable_parallel_mode is not None:
            values["enable_parallel_mode"] = data.enable_parallel_mode
        if data.daily_message_limit is not None:
            values["daily_message_limit"] = data.daily_message_limit
        if data.token_alert_threshold is not None:
            values["token_alert_threshold"] = data.token_alert_threshold
        if data.provider_credential_id is not None:
            values["provider_credential_id"] = data.provider_credential_id
        if data.updated_by is not None:
            values["updated_by"] = data.updated_by
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
