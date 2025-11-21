# app/endpoints/common/links.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.deps import get_db, get_current_supervisor  # 권한: supervisor 전용 가정

from crud.common.links import (
    partner_org_link,
    org_user_link,
)
from schemas.common.links import (
    PartnerOrgLinkCreate,
    PartnerOrgLinkUpdate,
    PartnerOrgLinkResponse,
    OrgUserLinkCreate,
    OrgUserLinkUpdate,
    OrgUserLinkResponse,
)
from schemas.base import Page


router = APIRouter()


# ==============================
# PartnerOrgLink
# ==============================
@router.get(
    "/partner-org-links",
    response_model=Page[PartnerOrgLinkResponse],
)
def list_partner_org_links(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    organization_id: Optional[int] = Query(None, ge=1),
    partner_id: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None, description="active|inactive|suspended|draft"),
    is_primary: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    rows, total = partner_org_link.list(
        db,
        organization_id=organization_id,
        partner_id=partner_id,
        status=status,
        is_primary=is_primary,
        page=page,
        size=size,
    )
    items = [PartnerOrgLinkResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/partner-org-links",
    response_model=PartnerOrgLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_partner_org_link(
    data: PartnerOrgLinkCreate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    try:
        obj = partner_org_link.create(db, data=data)
    except IntegrityError:
        # (organization_id, partner_id) 중복 또는 primary unique 위반
        raise HTTPException(
            status_code=409,
            detail="link for this organization and partner already exists or primary link already set",
        )
    return PartnerOrgLinkResponse.model_validate(obj)


@router.patch(
    "/partner-org-links/{link_id}",
    response_model=PartnerOrgLinkResponse,
)
def update_partner_org_link(
    link_id: int = Path(..., ge=1),
    data: PartnerOrgLinkUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    obj = partner_org_link.get(db, link_id)
    if not obj:
        raise HTTPException(status_code=404, detail="partner-org link not found")

    try:
        obj = partner_org_link.update(db, link_id=link_id, data=data)
    except IntegrityError:
        # primary 플래그 충돌 등
        raise HTTPException(
            status_code=409,
            detail="conflict while updating link (maybe primary already exists for this organization)",
        )

    return PartnerOrgLinkResponse.model_validate(obj)


@router.delete(
    "/partner-org-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_partner_org_link(
    link_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    obj = partner_org_link.get(db, link_id)
    if not obj:
        raise HTTPException(status_code=404, detail="partner-org link not found")

    partner_org_link.delete(db, link_id=link_id)
    return


# ==============================
# OrgUserLink
# ==============================
@router.get(
    "/org-user-links",
    response_model=Page[OrgUserLinkResponse],
)
def list_org_user_links(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    organization_id: Optional[int] = Query(None, ge=1),
    user_id: Optional[int] = Query(None, ge=1),
    role: Optional[str] = Query(None, description="owner|admin|manager|member"),
    status: Optional[str] = Query(None, description="active|inactive|suspended|draft"),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    rows, total = org_user_link.list(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        status=status,
        page=page,
        size=size,
    )
    items = [OrgUserLinkResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/org-user-links",
    response_model=OrgUserLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_org_user_link(
    data: OrgUserLinkCreate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    try:
        obj = org_user_link.create(db, data=data)
    except IntegrityError:
        # (organization_id, user_id) 중복
        raise HTTPException(
            status_code=409,
            detail="link for this organization and user already exists",
        )
    return OrgUserLinkResponse.model_validate(obj)


@router.patch(
    "/org-user-links/{link_id}",
    response_model=OrgUserLinkResponse,
)
def update_org_user_link(
    link_id: int = Path(..., ge=1),
    data: OrgUserLinkUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    obj = org_user_link.get(db, link_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org-user link not found")

    obj = org_user_link.update(db, link_id=link_id, data=data)
    return OrgUserLinkResponse.model_validate(obj)


@router.delete(
    "/org-user-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_org_user_link(
    link_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_supervisor),
):
    obj = org_user_link.get(db, link_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org-user link not found")

    org_user_link.delete(db, link_id=link_id)
    return
