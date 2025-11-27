# app/endpoints/supervisor/core.py
from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from core.deps import get_db, require_supervisor_admin
from crud.supervisor import core as super_crud

from schemas.supervisor.core import (
    PlanCreate, PlanUpdate, PlanResponse, OrganizationCreate,
    OrganizationUpdate, OrganizationResponse, SupervisorUserCreate,
    SupervisorUserResponse,
    UserRoleCreate,
    UserRoleResponse,
    UserRoleAssignmentResponse,
    PartnerPromotionRequestResponse,
)
from service.supervisor import promotion as promotion_service

router = APIRouter()


# ==============================
# Partner Promotion Requests (승격 요청 승인/거절)
# ==============================
class PromotionDecision(BaseModel):
    """
    target_role 이 'partner' 이면 강사, 'assistant' 이면 조교 등으로 승격.
    """
    target_role: Optional[str] = None


@router.get(
    "/promotions/partner-requests",
    response_model=List[PartnerPromotionRequestResponse],
)
def list_partner_promotion_requests(
    status_: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """
    승격 요청 목록 조회
    - status 쿼리로 pending/approved/rejected/cancelled 필터
    """
    rows = promotion_service.list_promotion_requests(db, status=status_)
    return rows


@router.get(
    "/promotions/partner-requests/{request_id}",
    response_model=PartnerPromotionRequestResponse,
)
def get_partner_promotion_request(
    request_id: int,
    db: Session = Depends(get_db),
    # _ = Depends(require_supervisor_admin),
):
    """
    단일 승격 요청 상세 조회
    """
    req = promotion_service.get_promotion_request(db, request_id=request_id)
    return req


@router.post(
    "/promotions/partner-requests/{request_id}/approve",
    response_model=PartnerPromotionRequestResponse,
    summary="강사 요청 승인",
)
def approve_partner_promotion_request(
    request_id: int,
    body: PromotionDecision,
    db: Session = Depends(get_db),
    # me = Depends(require_supervisor_admin),
):
    """
    승격 요청 승인

    - Org 결정/생성
    - partner.partners 에 Partner 엔터티 생성
    - user.users.partner_id 에 Partner.id 세팅
    - user.default_role 을 target_role 기준으로 업데이트
    - 요청 status = approved 로 변경
    """
    req = promotion_service.approve_partner_request(
        db=db,
        request_id=request_id,
        target_role=body.target_role,
    )
    return req


@router.post(
    "/promotions/partner-requests/{request_id}/reject",
    response_model=PartnerPromotionRequestResponse,
    summary="강사 요청 거절",
)
def reject_partner_promotion_request(
    request_id: int,
    db: Session = Depends(get_db),
    # me = Depends(require_supervisor_admin),
):
    """
    승격 요청 거절, pending 상태만 거절 가능
    """
    req = promotion_service.reject_partner_request(
        db=db,
        request_id=request_id,
    )
    return req


# ==============================
# Supervisor Users
# ==============================
@router.post(
    "/users",
    response_model=SupervisorUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="슈바 생성(필요없을듯)",
)
def create_supervisor_user(
    data: SupervisorUserCreate,
    db: Session = Depends(get_db),
):
    """
    새 supervisor user 생성
    기본값:
    - role : supervisor_admin
    - status : active
    """
    return super_crud.create_supervisor_user(
        db,
        org_id=data.organization_id,
        email=data.email,
        name=data.name,
        role=data.role or "supervisor_admin",
        status=data.status or "active",
    )


@router.get("/users/by-email", response_model=SupervisorUserResponse)
def get_supervisor_user_by_email(
    email: str = Query(...),
    db: Session = Depends(get_db),
    # _ = Depends(require_supervisor_admin),
):
    sup = super_crud.get_supervisor_user_by_email(db, email=email)
    if not sup:
        raise HTTPException(status_code=404, detail="supervisor user not found")
    return sup


# ==============================
# Roles
# ==============================
@router.post(
    "/roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="역할 생성",
)
def create_role(
    data: UserRoleCreate,
    db: Session = Depends(get_db),
):
    role = super_crud.get_or_create_role(
        db,
        role_name=data.role_name,
        permissions=data.permissions_json or {},
    )
    return role


@router.post(
    "/roles/bootstrap",
    response_model=List[UserRoleResponse],
    summary="기본 역할 초기화",
)
def bootstrap_roles(
    db: Session = Depends(get_db),
    # _ = Depends(require_supervisor_admin),
):
    return list(super_crud.bootstrap_default_roles(db))


@router.post(
    "/users/{user_id}/roles/{role_name}",
    response_model=UserRoleAssignmentResponse,
    summary="추후 기관 당",
)
def assign_role_to_user(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db),
):
    ura = super_crud.assign_role(
        db,
        user_id=user_id,
        role_name=role_name,
        assigned_by=getattr("user_id", None),
    )
    return ura
