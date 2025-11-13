# app/endpoints/partner/billing.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_admin
from crud.partner import billing as billing_crud
from schemas.partner.billing import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoicePage,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoiceItemResponse,
    InvoiceItemPage,
    PayoutCreate,
    PayoutUpdate,
    PayoutResponse,
    PayoutPage,
    PayoutItemCreate,
    PayoutItemUpdate,
    PayoutItemResponse,
    PayoutItemPage,
    FeeRateCreate,
    FeeRateUpdate,
    FeeRateResponse,
    FeeRatePage,
    PayoutAccountCreate,
    PayoutAccountUpdate,
    PayoutAccountResponse,
    PayoutAccountPage,
    BusinessProfileCreate,
    BusinessProfileUpdate,
    BusinessProfileResponse,
    ClassFinanceMonthlyResponse,
    ClassFinanceMonthlyPage,
)
from schemas.enums import InvoiceStatus, PayoutStatus

router = APIRouter()  # prefix는 routers.py에서 설정


# ==============================
# Invoices
# ==============================

@router.get("/invoices", response_model=InvoicePage)
def list_invoices(
    partner_id: int = Path(..., ge=1),
    status: Optional[InvoiceStatus] = Query(None),
    period_start_from: Optional[date] = Query(None),
    period_start_to: Optional[date] = Query(None),
    period_end_from: Optional[date] = Query(None),
    period_end_to: Optional[date] = Query(None),
    invoice_number: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = billing_crud.list_invoices(
        db,
        partner_id=partner_id,
        status=status.value if status else None,
        period_start_from=period_start_from,
        period_start_to=period_start_to,
        period_end_from=period_end_from,
        period_end_to=period_end_to,
        invoice_number=invoice_number,
        page=page,
        size=size,
    )
    items = [InvoiceResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    partner_id: int = Path(..., ge=1),
    invoice_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_invoice(db, invoice_id=invoice_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")
    return InvoiceResponse.model_validate(obj)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    partner_id: int = Path(..., ge=1),
    payload: InvoiceCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    # path 의 partner_id 강제 적용
    data["partner_id"] = partner_id
    obj = billing_crud.create_invoice(db, data=data)
    return InvoiceResponse.model_validate(obj)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    partner_id: int = Path(..., ge=1),
    invoice_id: int = Path(..., ge=1),
    payload: InvoiceUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_invoice(db, invoice_id=invoice_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")

    data = payload.model_dump(exclude_unset=True)
    obj = billing_crud.update_invoice(db, invoice=obj, data=data)
    return InvoiceResponse.model_validate(obj)


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    partner_id: int = Path(..., ge=1),
    invoice_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_invoice(db, invoice_id=invoice_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")

    billing_crud.delete_invoice(db, invoice=obj)
    return None


# ==============================
# InvoiceItems (per invoice)
# ==============================

@router.get("/invoices/{invoice_id}/items", response_model=InvoiceItemPage)
def list_invoice_items(
    partner_id: int = Path(..., ge=1),
    invoice_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    invoice = billing_crud.get_invoice(db, invoice_id=invoice_id)
    if not invoice or invoice.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")

    rows, total = billing_crud.list_invoice_items(
        db,
        invoice_id=invoice_id,
        page=page,
        size=size,
    )
    items = [InvoiceItemResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/invoices/{invoice_id}/items",
    response_model=InvoiceItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice_item(
    partner_id: int = Path(..., ge=1),
    invoice_id: int = Path(..., ge=1),
    payload: InvoiceItemCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    invoice = billing_crud.get_invoice(db, invoice_id=invoice_id)
    if not invoice or invoice.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice not found")

    data = payload.model_dump(exclude_unset=True)
    data["invoice_id"] = invoice_id  # path 기준으로 강제
    obj = billing_crud.create_invoice_item(db, data=data)
    return InvoiceItemResponse.model_validate(obj)


@router.get("/invoice-items/{item_id}", response_model=InvoiceItemResponse)
def get_invoice_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_invoice_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    invoice = billing_crud.get_invoice(db, invoice_id=item.invoice_id)
    if not invoice or invoice.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    return InvoiceItemResponse.model_validate(item)


@router.patch("/invoice-items/{item_id}", response_model=InvoiceItemResponse)
def update_invoice_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    payload: InvoiceItemUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_invoice_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    invoice = billing_crud.get_invoice(db, invoice_id=item.invoice_id)
    if not invoice or invoice.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    data = payload.model_dump(exclude_unset=True)
    item = billing_crud.update_invoice_item(db, item=item, data=data)
    return InvoiceItemResponse.model_validate(item)


@router.delete("/invoice-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_invoice_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    invoice = billing_crud.get_invoice(db, invoice_id=item.invoice_id)
    if not invoice or invoice.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_item not found")

    billing_crud.delete_invoice_item(db, item=item)
    return None


# ==============================
# Payouts
# ==============================

@router.get("/payouts", response_model=PayoutPage)
def list_payouts(
    partner_id: int = Path(..., ge=1),
    status: Optional[PayoutStatus] = Query(None),
    period_start_from: Optional[date] = Query(None),
    period_start_to: Optional[date] = Query(None),
    period_end_from: Optional[date] = Query(None),
    period_end_to: Optional[date] = Query(None),
    payout_number: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = billing_crud.list_payouts(
        db,
        partner_id=partner_id,
        status=status.value if status else None,
        period_start_from=period_start_from,
        period_start_to=period_start_to,
        period_end_from=period_end_from,
        period_end_to=period_end_to,
        payout_number=payout_number,
        page=page,
        size=size,
    )
    items = [PayoutResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/payouts/{payout_id}", response_model=PayoutResponse)
def get_payout(
    partner_id: int = Path(..., ge=1),
    payout_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout(db, payout_id=payout_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout not found")
    return PayoutResponse.model_validate(obj)


@router.post("/payouts", response_model=PayoutResponse, status_code=status.HTTP_201_CREATED)
def create_payout(
    partner_id: int = Path(..., ge=1),
    payload: PayoutCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    data["partner_id"] = partner_id
    obj = billing_crud.create_payout(db, data=data)
    return PayoutResponse.model_validate(obj)


@router.patch("/payouts/{payout_id}", response_model=PayoutResponse)
def update_payout(
    partner_id: int = Path(..., ge=1),
    payout_id: int = Path(..., ge=1),
    payload: PayoutUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout(db, payout_id=payout_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout not found")

    data = payload.model_dump(exclude_unset=True)
    obj = billing_crud.update_payout(db, payout=obj, data=data)
    return PayoutResponse.model_validate(obj)


@router.delete("/payouts/{payout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payout(
    partner_id: int = Path(..., ge=1),
    payout_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout(db, payout_id=payout_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout not found")

    billing_crud.delete_payout(db, payout=obj)
    return None


# ==============================
# PayoutItems
# ==============================

@router.get("/payouts/{payout_id}/items", response_model=PayoutItemPage)
def list_payout_items(
    partner_id: int = Path(..., ge=1),
    payout_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    payout = billing_crud.get_payout(db, payout_id=payout_id)
    if not payout or payout.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout not found")

    rows, total = billing_crud.list_payout_items(
        db,
        payout_id=payout_id,
        page=page,
        size=size,
    )
    items = [PayoutItemResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/payouts/{payout_id}/items",
    response_model=PayoutItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payout_item(
    partner_id: int = Path(..., ge=1),
    payout_id: int = Path(..., ge=1),
    payload: PayoutItemCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    payout = billing_crud.get_payout(db, payout_id=payout_id)
    if not payout or payout.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout not found")

    data = payload.model_dump(exclude_unset=True)
    data["payout_id"] = payout_id
    obj = billing_crud.create_payout_item(db, data=data)
    return PayoutItemResponse.model_validate(obj)


@router.get("/payout-items/{item_id}", response_model=PayoutItemResponse)
def get_payout_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_payout_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    payout = billing_crud.get_payout(db, payout_id=item.payout_id)
    if not payout or payout.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    return PayoutItemResponse.model_validate(item)


@router.patch("/payout-items/{item_id}", response_model=PayoutItemResponse)
def update_payout_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    payload: PayoutItemUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_payout_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    payout = billing_crud.get_payout(db, payout_id=item.payout_id)
    if not payout or payout.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    data = payload.model_dump(exclude_unset=True)
    item = billing_crud.update_payout_item(db, item=item, data=data)
    return PayoutItemResponse.model_validate(item)


@router.delete("/payout-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payout_item(
    partner_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = billing_crud.get_payout_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    payout = billing_crud.get_payout(db, payout_id=item.payout_id)
    if not payout or payout.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_item not found")

    billing_crud.delete_payout_item(db, item=item)
    return None


# ==============================
# FeeRates
# ==============================

@router.get("/fee-rates", response_model=FeeRatePage)
def list_fee_rates(
    partner_id: int = Path(..., ge=1),
    fee_type: Optional[str] = Query(None),
    effective_from: Optional[date] = Query(None),
    effective_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = billing_crud.list_fee_rates(
        db,
        partner_id=partner_id,
        fee_type=fee_type,
        effective_from=effective_from,
        effective_to=effective_to,
        page=page,
        size=size,
    )
    items = [FeeRateResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/fee-rates/{fee_rate_id}", response_model=FeeRateResponse)
def get_fee_rate(
    partner_id: int = Path(..., ge=1),
    fee_rate_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_fee_rate(db, fee_rate_id=fee_rate_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fee_rate not found")
    return FeeRateResponse.model_validate(obj)


@router.post("/fee-rates", response_model=FeeRateResponse, status_code=status.HTTP_201_CREATED)
def create_fee_rate(
    partner_id: int = Path(..., ge=1),
    payload: FeeRateCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    data["partner_id"] = partner_id
    obj = billing_crud.create_fee_rate(db, data=data)
    return FeeRateResponse.model_validate(obj)


@router.patch("/fee-rates/{fee_rate_id}", response_model=FeeRateResponse)
def update_fee_rate(
    partner_id: int = Path(..., ge=1),
    fee_rate_id: int = Path(..., ge=1),
    payload: FeeRateUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_fee_rate(db, fee_rate_id=fee_rate_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fee_rate not found")

    data = payload.model_dump(exclude_unset=True)
    obj = billing_crud.update_fee_rate(db, fee_rate=obj, data=data)
    return FeeRateResponse.model_validate(obj)


@router.delete("/fee-rates/{fee_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fee_rate(
    partner_id: int = Path(..., ge=1),
    fee_rate_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_fee_rate(db, fee_rate_id=fee_rate_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fee_rate not found")

    billing_crud.delete_fee_rate(db, fee_rate=obj)
    return None


# ==============================
# PayoutAccounts
# ==============================

@router.get("/payout-accounts", response_model=PayoutAccountPage)
def list_payout_accounts(
    partner_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = billing_crud.list_payout_accounts(
        db,
        partner_id=partner_id,
        page=page,
        size=size,
    )
    items = [PayoutAccountResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/payout-accounts/{account_id}", response_model=PayoutAccountResponse)
def get_payout_account(
    partner_id: int = Path(..., ge=1),
    account_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout_account(db, account_id=account_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_account not found")
    return PayoutAccountResponse.model_validate(obj)


@router.post("/payout-accounts", response_model=PayoutAccountResponse, status_code=status.HTTP_201_CREATED)
def create_payout_account(
    partner_id: int = Path(..., ge=1),
    payload: PayoutAccountCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    data["partner_id"] = partner_id
    obj = billing_crud.create_payout_account(db, data=data)
    return PayoutAccountResponse.model_validate(obj)


@router.patch("/payout-accounts/{account_id}", response_model=PayoutAccountResponse)
def update_payout_account(
    partner_id: int = Path(..., ge=1),
    account_id: int = Path(..., ge=1),
    payload: PayoutAccountUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout_account(db, account_id=account_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_account not found")

    data = payload.model_dump(exclude_unset=True)
    obj = billing_crud.update_payout_account(db, account=obj, data=data)
    return PayoutAccountResponse.model_validate(obj)


@router.delete("/payout-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payout_account(
    partner_id: int = Path(..., ge=1),
    account_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_payout_account(db, account_id=account_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_account not found")

    billing_crud.delete_payout_account(db, account=obj)
    return None


@router.post(
    "/payout-accounts/{account_id}/primary",
    response_model=PayoutAccountResponse,
)
def set_primary_payout_account(
    partner_id: int = Path(..., ge=1),
    account_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    파트너의 primary 정산 계좌 설정.
    """
    obj = billing_crud.get_payout_account(db, account_id=account_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payout_account not found")

    obj = billing_crud.set_primary_payout_account(db, account=obj)
    return PayoutAccountResponse.model_validate(obj)


# ==============================
# BusinessProfile
# ==============================

@router.get("/business-profile", response_model=BusinessProfileResponse)
def get_business_profile(
    partner_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_business_profile(db, partner_id=partner_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="business_profile not found")
    return BusinessProfileResponse.model_validate(obj)


@router.post("/business-profile", response_model=BusinessProfileResponse, status_code=status.HTTP_201_CREATED)
def upsert_business_profile(
    partner_id: int = Path(..., ge=1),
    payload: BusinessProfileCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    비즈니스 프로필 upsert.
    - 존재하면 업데이트, 없으면 생성.
    """
    data = payload.model_dump(exclude_unset=True)
    # path 기준으로 partner_id 강제
    data["partner_id"] = partner_id
    obj = billing_crud.upsert_business_profile(db, partner_id=partner_id, data=data)
    return BusinessProfileResponse.model_validate(obj)


# ==============================
# ClassFinanceMonthly (집계: 주로 조회용)
# ==============================

@router.get("/class-finance", response_model=ClassFinanceMonthlyPage)
def list_class_finance_monthly(
    partner_id: int = Path(..., ge=1),
    class_id: Optional[int] = Query(None),
    month_from: Optional[date] = Query(None),
    month_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    분반별 월간 재무 집계 목록 조회.
    - ETL 집계 결과를 조회하는 용도로 사용.
    """
    rows, total = billing_crud.list_class_finance_monthly(
        db,
        class_id=class_id,
        month_from=month_from,
        month_to=month_to,
        page=page,
        size=size,
    )
    items = [ClassFinanceMonthlyResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/class-finance/{cfm_id}", response_model=ClassFinanceMonthlyResponse)
def get_class_finance_monthly(
    partner_id: int = Path(..., ge=1),
    cfm_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = billing_crud.get_class_finance_monthly(db, cfm_id=cfm_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="class_finance_monthly not found")
    return ClassFinanceMonthlyResponse.model_validate(obj)
