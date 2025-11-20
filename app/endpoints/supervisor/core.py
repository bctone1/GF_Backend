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

router = APIRouter()


# ==============================
# Partner Promotion Requests (승격 요청 승인/거절)
# ==============================
class PromotionDecision(BaseModel):
    # 승인 시에만 사용, 거절 시에는 무시(현재는 저장 안 함)
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
    rows = super_crud.list_promotion_requests(db, status=status_)
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
    req = super_crud.get_promotion_request(db, request_id=request_id)
    if not req:
        raise HTTPException(status_code=404, detail="promotion request not found")
    return req


@router.post(
    "/promotions/partner-requests/{request_id}/approve",
    response_model=PartnerPromotionRequestResponse,
)
def approve_partner_promotion_request(
    request_id: int,
    body: PromotionDecision,
    db: Session = Depends(get_db),
):
    """
    승격 요청 승인
    - partner/partner_user 생성(또는 재사용)
    - 요청 status = approved 로 변경
    """
    try:
        req = super_crud.approve_promotion_request(
            db,
            request_id=request_id,
            target_role=body.target_role,
        )
        return req
    except super_crud.PromotionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except super_crud.PromotionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/promotions/partner-requests/{request_id}/reject",
    response_model=PartnerPromotionRequestResponse,
)
def reject_partner_promotion_request(
    request_id: int,
    db: Session = Depends(get_db),
    # _ = Depends(require_supervisor_admin),
):
    """
    승격 요청 거절, pending 상태만 거절 가능
    """
    try:
        req = super_crud.reject_promotion_request(
            db,
            request_id=request_id,
        )
        return req
    except super_crud.PromotionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except super_crud.PromotionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


# ==============================
# Supervisor Users
# ==============================
@router.post("/users", response_model=SupervisorUserResponse, status_code=status.HTTP_201_CREATED)
def create_supervisor_user(
    data: SupervisorUserCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new supervisor user
    role : supervisor_admin
    status : active
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
@router.post("/roles", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
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

@router.post("/roles/bootstrap", response_model=List[UserRoleResponse])
def bootstrap_roles(
    db: Session = Depends(get_db),
    # _ = Depends(require_supervisor_admin),
):
    return list(super_crud.bootstrap_default_roles(db))

@router.post("/users/{user_id}/roles/{role_name}", response_model=UserRoleAssignmentResponse)
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



# # ==============================
# # Organizations
# # ==============================
# @router.get("/organizations", response_model=List[OrganizationResponse])
# def list_organizations(
#     status_: Optional[str] = Query(None, alias="status"),
#     q: Optional[str] = Query(None),
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     return super_crud.list_orgs(db, status=status_, q=q)
#
# @router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
# def create_organization(
#     data: OrganizationCreate,
#     db: Session = Depends(get_db),
#     me=Depends(require_supervisor_admin),
# ):
#     return super_crud.create_org(
#         db,
#         name=data.name,
#         plan_id=data.plan_id,
#         industry=data.industry,
#         company_size=data.company_size,
#         status=data.status or "active",
#         created_by=getattr(me, "user_id", None),
#         notes=data.notes,
#     )
#
# @router.get("/organizations/{org_id}", response_model=OrganizationResponse)
# def get_organization(
#     org_id: int,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     org = super_crud.get_org(db, org_id)
#     if not org:
#         raise HTTPException(status_code=404, detail="organization not found")
#     return org
#
# @router.patch("/organizations/{org_id}", response_model=OrganizationResponse)
# def update_organization(
#     org_id: int,
#     data: OrganizationUpdate,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     updated = super_crud.update_org(
#         db,
#         org_id,
#         **data.model_dump(exclude_unset=True),
#     )
#     if not updated:
#         raise HTTPException(status_code=404, detail="organization not found")
#     return updated
#
# @router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_organization(
#     org_id: int,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     ok = super_crud.delete_org(db, org_id)
#     if not ok:
#         raise HTTPException(status_code=404, detail="organization not found")
#     return None

# # ==============================
# # Plans
# # ==============================
# @router.get("/plans", response_model=List[PlanResponse])
# def list_plans(
#     q: Optional[str] = Query(None),
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     return super_crud.list_plans(db, q=q)
#
# @router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
# def create_plan(
#     data: PlanCreate,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     try:
#         return super_crud.create_plan(
#             db,
#             name=data.plan_name,
#             billing_cycle=data.billing_cycle or "monthly",
#             price_mrr=float(data.price_mrr or 0),
#             price_arr=float(data.price_arr or 0),
#             features_json=data.features_json,
#             max_users=data.max_users,
#             is_active=True if data.is_active is None else data.is_active,
#         )
#     except IntegrityError:
#         raise HTTPException(status_code=409, detail="plan name already exists")
#
# @router.get("/plans/{plan_id}", response_model=PlanResponse)
# def get_plan(
#     plan_id: int,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     plan = super_crud.get_plan(db, plan_id)
#     if not plan:
#         raise HTTPException(status_code=404, detail="plan not found")
#     return plan
#
# @router.patch("/plans/{plan_id}", response_model=PlanResponse)
# def update_plan(
#     plan_id: int,
#     data: PlanUpdate,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     updated = super_crud.update_plan(
#         db,
#         plan_id,
#         **data.model_dump(exclude_unset=True),
#     )
#     if not updated:
#         raise HTTPException(status_code=404, detail="plan not found")
#     return updated
#
# @router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_plan(
#     plan_id: int,
#     db: Session = Depends(get_db),
#     _ = Depends(require_supervisor_admin),
# ):
#     ok = super_crud.delete_plan(db, plan_id)
#     if not ok:
#         raise HTTPException(status_code=404, detail="plan not found")
#     return None
