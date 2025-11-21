# crud/common/links.py
# crud/common/links.py
from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.common.links import PartnerOrgLink, OrgUserLink
from schemas.common.links import (
    PartnerOrgLinkCreate,
    PartnerOrgLinkUpdate,
    OrgUserLinkCreate,
    OrgUserLinkUpdate,
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
# PartnerOrgLink CRUD
# ==============================
class PartnerOrgLinkCRUD:
    model = PartnerOrgLink

    def get(self, db: Session, link_id: int) -> Optional[PartnerOrgLink]:
        return db.get(self.model, link_id)

    def get_by_org_partner(
        self,
        db: Session,
        *,
        organization_id: int,
        partner_id: int,
    ) -> Optional[PartnerOrgLink]:
        stmt = select(self.model).where(
            self.model.organization_id == organization_id,
            self.model.partner_id == partner_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        db: Session,
        *,
        organization_id: Optional[int] = None,
        partner_id: Optional[int] = None,
        status: Optional[str] = None,
        is_primary: Optional[bool] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[PartnerOrgLink], int]:
        stmt = select(self.model)
        conds = []
        if organization_id is not None:
            conds.append(self.model.organization_id == organization_id)
        if partner_id is not None:
            conds.append(self.model.partner_id == partner_id)
        if status is not None:
            conds.append(self.model.status == status)
        if is_primary is not None:
            conds.append(self.model.is_primary == is_primary)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(
            self.model.organization_id.asc(),
            self.model.partner_id.asc(),
            self.model.link_id.asc(),
        )
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        data: PartnerOrgLinkCreate,
    ) -> PartnerOrgLink:
        obj = self.model(
            organization_id=data.organization_id,
            partner_id=data.partner_id,
            is_primary=data.is_primary,
            notes=data.notes,
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약: (organization_id, partner_id) 또는 partial index(is_primary)
            raise
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        link_id: int,
        data: PartnerOrgLinkUpdate,
    ) -> Optional[PartnerOrgLink]:
        values: dict = {}
        if data.is_primary is not None:
            values["is_primary"] = data.is_primary
        if data.status is not None:
            values["status"] = data.status
        if data.notes is not None:
            values["notes"] = data.notes

        if not values:
            return self.get(db, link_id)

        stmt = (
            update(self.model)
            .where(self.model.link_id == link_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, link_id)

    def delete(self, db: Session, *, link_id: int) -> None:
        db.execute(delete(self.model).where(self.model.link_id == link_id))
        db.commit()


# ==============================
# OrgUserLink CRUD
# ==============================
class OrgUserLinkCRUD:
    model = OrgUserLink

    def get(self, db: Session, link_id: int) -> Optional[OrgUserLink]:
        return db.get(self.model, link_id)

    def get_by_org_user(
        self,
        db: Session,
        *,
        organization_id: int,
        user_id: int,
    ) -> Optional[OrgUserLink]:
        stmt = select(self.model).where(
            self.model.organization_id == organization_id,
            self.model.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        db: Session,
        *,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[OrgUserLink], int]:
        stmt = select(self.model)
        conds = []
        if organization_id is not None:
            conds.append(self.model.organization_id == organization_id)
        if user_id is not None:
            conds.append(self.model.user_id == user_id)
        if role is not None:
            conds.append(self.model.role == role)
        if status is not None:
            conds.append(self.model.status == status)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(
            self.model.organization_id.asc(),
            self.model.user_id.asc(),
            self.model.link_id.asc(),
        )
        return _paginate(stmt, db, page, size)

    def create(
        self,
        db: Session,
        *,
        data: OrgUserLinkCreate,
    ) -> OrgUserLink:
        obj = self.model(
            organization_id=data.organization_id,
            user_id=data.user_id,
            role=data.role.value if hasattr(data.role, "value") else data.role,
            status=data.status.value if hasattr(data.status, "value") else data.status,
            notes=data.notes,
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 유니크 제약: (organization_id, user_id)
            raise
        db.refresh(obj)
        return obj

    def update(
        self,
        db: Session,
        *,
        link_id: int,
        data: OrgUserLinkUpdate,
    ) -> Optional[OrgUserLink]:
        values: dict = {}
        if data.role is not None:
            values["role"] = data.role.value if hasattr(data.role, "value") else data.role
        if data.status is not None:
            values["status"] = data.status.value if hasattr(data.status, "value") else data.status
        if data.notes is not None:
            values["notes"] = data.notes

        if not values:
            return self.get(db, link_id)

        stmt = (
            update(self.model)
            .where(self.model.link_id == link_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        db.execute(stmt)
        db.commit()
        return self.get(db, link_id)

    def delete(self, db: Session, *, link_id: int) -> None:
        db.execute(delete(self.model).where(self.model.link_id == link_id))
        db.commit()


# 인스턴스
partner_org_link = PartnerOrgLinkCRUD()
org_user_link = OrgUserLinkCRUD()
