# app/endpoints/partner/partner_core.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from crud.partner import partner_core as partner_crud

from schemas.partner.partner_core import (
    OrgResponse, OrgUpdate,
    PartnerUserCreate, PartnerUserUpdate, PartnerUserResponse,
)

router = APIRouter()


# ==============================
# Org (조회/수정)
# ==============================
@router.get("", response_model=OrgResponse)
def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),  # 멤버 이상 접근 허용
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
    _ = Depends(get_current_partner_user),  # 관리자만 수정 (권한 체크는 추후 service 레벨에서)
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
# Org 내 Partner Users (강사/어시스턴트)
# ==============================
@router.get("/users", response_model=List[PartnerUserResponse])
def list_partner_users(
    org_id: int,
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),  # 멤버 이상 조회 가능
):
    return partner_crud.list_partner_users(
        db,
        org_id=org_id,
        role=role,
        is_active=is_active,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("/users", response_model=PartnerUserResponse, status_code=status.HTTP_201_CREATED)
def add_partner_user(
    org_id: int,
    data: PartnerUserCreate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),  # 관리자만 추가 (권한 체크는 추후)
):
    try:
        return partner_crud.add_partner_user(
            db,
            org_id=org_id,
            email=data.email,
            full_name=data.full_name,
            role=data.role or "partner",
            phone=data.phone,
            is_active=True if data.is_active is None else data.is_active,
            user_id=data.user_id,  # optional
        )
    except partner_crud.PartnerUserConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/users/{partner_user_id}", response_model=PartnerUserResponse)
def get_partner_user(
    org_id: int,  # 경로 정합성 체크용 (실제 FK는 PartnerUser.partner_id)
    partner_user_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),
):
    obj = partner_crud.get_partner_user(db, partner_user_id)
    if not obj or obj.partner_id != org_id:
        raise HTTPException(status_code=404, detail="partner_user not found")
    return obj


@router.patch("/users/{partner_user_id}", response_model=PartnerUserResponse)
def update_partner_user(
    org_id: int,
    partner_user_id: int,
    data: PartnerUserUpdate,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),
):
    try:
        updated = partner_crud.update_partner_user(
            db,
            partner_user_id,
            **data.model_dump(exclude_unset=True),
        )
    except partner_crud.PartnerUserConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not updated or updated.partner_id != org_id:
        raise HTTPException(status_code=404, detail="partner_user not found")
    return updated


@router.post("/users/{partner_user_id}/deactivate", response_model=PartnerUserResponse)
def deactivate_partner_user(
    org_id: int,
    partner_user_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),
):
    updated = partner_crud.deactivate_partner_user(db, partner_user_id)
    if not updated or updated.partner_id != org_id:
        raise HTTPException(status_code=404, detail="partner_user not found")
    return updated


@router.post("/users/{partner_user_id}/role", response_model=PartnerUserResponse)
def change_partner_user_role(
    org_id: int,
    partner_user_id: int,
    role: str = Query(..., pattern="^(partner|assistant)$"),
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),
):
    updated = partner_crud.change_partner_user_role(db, partner_user_id, role=role)
    if not updated or updated.partner_id != org_id:
        raise HTTPException(status_code=404, detail="partner_user not found")
    return updated


@router.delete("/users/{partner_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_partner_user(
    org_id: int,
    partner_user_id: int,
    db: Session = Depends(get_db),
    _ = Depends(get_current_partner_user),
):
    # 존재 및 소속 Org 확인
    obj = partner_crud.get_partner_user(db, partner_user_id)
    if not obj or obj.partner_id != org_id:
        raise HTTPException(status_code=404, detail="partner_user not found")

    ok = partner_crud.remove_partner_user(db, partner_user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="partner_user not found")
    return None
