# app/endpoints/partner/partner_core.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner
from crud.partner import partner_core as partner_crud

from schemas.partner.partner_core import (
    OrgResponse,
    OrgUpdate,
    PartnerCreate,
    PartnerUpdate,
    PartnerResponse,
)

router = APIRouter()


# ==============================
# Org (조회/수정)
# ==============================
@router.get("", response_model=OrgResponse)
def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),  # 파트너(강사) 이상 접근 허용
):
    obj = partner_crud.get_org(db, org_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org not found")
    return obj


@router.patch("", response_model=OrgResponse)
def update_org(
    org_id: int,
    data: OrgUpdate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),  # 추후에 Org 관리자 권한 체크는 service 레벨에서
):
    try:
        updated = partner_crud.update_org(
            db,
            org_id,
            **data.model_dump(exclude_unset=True),
        )
    except partner_crud.OrgConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="org not found")
    return updated


# ==============================
# Org 내 Partners (강사/어시스턴트)
# ==============================
@router.get("/partners", response_model=List[PartnerResponse])
def list_partners(
    org_id: int,
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),  # 파트너 멤버 이상 조회 가능
):
    return partner_crud.list_partners(
        db,
        org_id=org_id,
        role=role,
        is_active=is_active,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/partners",
    response_model=PartnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="파트너 생성",
)
def add_partner(
    org_id: int,
    data: PartnerCreate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),  # 관리자 권한 체크는 추후
):
    try:
        return partner_crud.add_partner(
            db,
            org_id=org_id,
            email=data.email,
            full_name=data.full_name,
            role=data.role or "partner",
            phone=data.phone,
            is_active=True if data.is_active is None else data.is_active,
            user_id=data.user_id,  # optional
        )
    except partner_crud.PartnerConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/partners/{partner_id}", response_model=PartnerResponse)
def get_partner(
    org_id: int,      # 경로 정합성 체크용 (실제 FK는 Partner.org_id)
    partner_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),
):
    obj = partner_crud.get_partner(db, partner_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="partner not found")
    return obj


@router.patch("/partners/{partner_id}", response_model=PartnerResponse)
def update_partner(
    org_id: int,
    partner_id: int,
    data: PartnerUpdate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),
):
    try:
        updated = partner_crud.update_partner(
            db,
            partner_id,
            **data.model_dump(exclude_unset=True),
        )
    except partner_crud.PartnerConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not updated or updated.org_id != org_id:
        raise HTTPException(status_code=404, detail="partner not found")
    return updated


@router.post(
    "/partners/{partner_id}/deactivate",
    response_model=PartnerResponse,
    summary="파트너 비활성화",
)
def deactivate_partner(
    org_id: int,
    partner_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),
):
    updated = partner_crud.deactivate_partner(db, partner_id)
    if not updated or updated.org_id != org_id:
        raise HTTPException(status_code=404, detail="partner not found")
    return updated


@router.post(
    "/partners/{partner_id}/role",
    response_model=PartnerResponse,
    summary="파트너 역할 변경",
)
def change_partner_role(
    org_id: int,
    partner_id: int,
    role: str = Query(..., pattern="^(partner|assistant)$"),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),
):
    updated = partner_crud.change_partner_role(db, partner_id, role=role)
    if not updated or updated.org_id != org_id:
        raise HTTPException(status_code=404, detail="partner not found")
    return updated


@router.delete("/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_partner(
    org_id: int,
    partner_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner),
):
    # 존재 및 소속 Org 확인
    obj = partner_crud.get_partner(db, partner_id)
    if not obj or obj.org_id != org_id:
        raise HTTPException(status_code=404, detail="partner not found")

    ok = partner_crud.remove_partner(db, partner_id)
    if not ok:
        raise HTTPException(status_code=404, detail="partner not found")
    return None
