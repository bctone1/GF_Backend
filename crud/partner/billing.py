# crud/partner/billing.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.billing import (
    Invoice,
    InvoiceItem,
    Payout,
    PayoutItem,
    FeeRate,
    PayoutAccount,
    BusinessProfile,
    ClassFinanceMonthly,
)


# =============================================================================
# Invoices
# =============================================================================
def get_invoice(db: Session, invoice_id: int) -> Optional[Invoice]:
    return db.get(Invoice, invoice_id)


def list_invoices(
    db: Session,
    *,
    partner_id: int,
    status: Optional[str] = None,  # InvoiceStatus.value 사용 권장
    period_start_from: Optional[date] = None,
    period_start_to: Optional[date] = None,
    period_end_from: Optional[date] = None,
    period_end_to: Optional[date] = None,
    invoice_number: Optional[str] = None,  # 부분 검색용
    page: int = 1,
    size: int = 50,
) -> Tuple[List[Invoice], int]:
    """
    파트너별 인보이스 목록 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [Invoice.partner_id == partner_id]

    if status is not None:
        filters.append(Invoice.status == status)
    if period_start_from is not None:
        filters.append(Invoice.billing_period_start >= period_start_from)
    if period_start_to is not None:
        filters.append(Invoice.billing_period_start <= period_start_to)
    if period_end_from is not None:
        filters.append(Invoice.billing_period_end >= period_end_from)
    if period_end_to is not None:
        filters.append(Invoice.billing_period_end <= period_end_to)
    if invoice_number:
        filters.append(Invoice.invoice_number.ilike(f"%{invoice_number}%"))

    base_stmt: Select[Invoice] = select(Invoice).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(Invoice.billing_period_start.desc(), Invoice.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_invoice(
    db: Session,
    *,
    data: Dict[str, Any],
) -> Invoice:
    """
    인보이스 생성.
    - InvoiceCreate.model_dump(exclude_unset=True) 사용.
    """
    obj = Invoice(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_invoice(
    db: Session,
    *,
    invoice: Invoice,
    data: Dict[str, Any],
) -> Invoice:
    """
    인보이스 수정.
    - 상태 전환(draft→issued→paid 등)에 사용.
    """
    for key, value in data.items():
        setattr(invoice, key, value)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(
    db: Session,
    *,
    invoice: Invoice,
) -> None:
    """
    인보이스 삭제.
    - invoice_items 는 CASCADE 로 함께 삭제됨.
    """
    db.delete(invoice)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/billing.py 에서 사용할만한 예시)
#
# def recalc_invoice_total(db: Session, invoice: Invoice) -> Invoice:
#     """
#     invoice_items 를 다시 합산해서 invoice.total_amount를 재계산하는 헬퍼.
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# InvoiceItems
# =============================================================================
def get_invoice_item(db: Session, item_id: int) -> Optional[InvoiceItem]:
    return db.get(InvoiceItem, item_id)


def list_invoice_items(
    db: Session,
    *,
    invoice_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[InvoiceItem], int]:
    """
    인보이스 아이템 목록 조회.
    - 보통 invoice_id 기준으로 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if invoice_id is not None:
        filters.append(InvoiceItem.invoice_id == invoice_id)
    if enrollment_id is not None:
        filters.append(InvoiceItem.enrollment_id == enrollment_id)
    if student_id is not None:
        filters.append(InvoiceItem.student_id == student_id)

    base_stmt: Select[InvoiceItem] = select(InvoiceItem)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(InvoiceItem.invoice_id.asc(), InvoiceItem.sort_order.asc(), InvoiceItem.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_invoice_item(
    db: Session,
    *,
    data: Dict[str, Any],
) -> InvoiceItem:
    """
    인보이스 아이템 생성.
    - InvoiceItemCreate.model_dump(exclude_unset=True) 사용.
    - DB 제약: amount = quantity * unit_price (서비스 레벨에서 맞춰주는 게 좋다).
    """
    obj = InvoiceItem(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_invoice_item(
    db: Session,
    *,
    item: InvoiceItem,
    data: Dict[str, Any],
) -> InvoiceItem:
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_invoice_item(
    db: Session,
    *,
    item: InvoiceItem,
) -> None:
    db.delete(item)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/billing.py 예시)
#
# def add_line_to_invoice(
#     db: Session,
#     invoice: Invoice,
#     description: str,
#     quantity: int,
#     unit_price: Decimal,
#     enrollment_id: Optional[int] = None,
#     student_id: Optional[int] = None,
# ) -> Invoice:
#     """
#     1) amount 계산
#     2) InvoiceItem 생성
#     3) invoice.total_amount 재계산
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# Payouts
# =============================================================================

def get_payout(db: Session, payout_id: int) -> Optional[Payout]:
    return db.get(Payout, payout_id)


def list_payouts(
    db: Session,
    *,
    partner_id: int,
    status: Optional[str] = None,  # PayoutStatus.value 사용 권장
    period_start_from: Optional[date] = None,
    period_start_to: Optional[date] = None,
    period_end_from: Optional[date] = None,
    period_end_to: Optional[date] = None,
    payout_number: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[Payout], int]:
    """
    파트너별 정산(payout) 목록 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [Payout.partner_id == partner_id]

    if status is not None:
        filters.append(Payout.status == status)
    if period_start_from is not None:
        filters.append(Payout.period_start >= period_start_from)
    if period_start_to is not None:
        filters.append(Payout.period_start <= period_start_to)
    if period_end_from is not None:
        filters.append(Payout.period_end >= period_end_from)
    if period_end_to is not None:
        filters.append(Payout.period_end <= period_end_to)
    if payout_number:
        filters.append(Payout.payout_number.ilike(f"%{payout_number}%"))

    base_stmt: Select[Payout] = select(Payout).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(Payout.period_start.desc(), Payout.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_payout(
    db: Session,
    *,
    data: Dict[str, Any],
) -> Payout:
    obj = Payout(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_payout(
    db: Session,
    *,
    payout: Payout,
    data: Dict[str, Any],
) -> Payout:
    for key, value in data.items():
        setattr(payout, key, value)
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


def delete_payout(
    db: Session,
    *,
    payout: Payout,
) -> None:
    db.delete(payout)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/billing.py 예시)
#
# def sync_payout_totals_from_items(db: Session, payout: Payout) -> Payout:
#     """
#     payout_items 를 합산해서 payout.total_amount를 재계산하는 헬퍼.
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# PayoutItems
# =============================================================================

def get_payout_item(db: Session, item_id: int) -> Optional[PayoutItem]:
    return db.get(PayoutItem, item_id)


def list_payout_items(
    db: Session,
    *,
    payout_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[PayoutItem], int]:
    """
    정산 항목 목록 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if payout_id is not None:
        filters.append(PayoutItem.payout_id == payout_id)
    if invoice_id is not None:
        filters.append(PayoutItem.invoice_id == invoice_id)

    base_stmt: Select[PayoutItem] = select(PayoutItem)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(PayoutItem.payout_id.asc(), PayoutItem.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_payout_item(
    db: Session,
    *,
    data: Dict[str, Any],
) -> PayoutItem:
    """
    - DB 제약: net_amount = amount - fee_amount
    """
    obj = PayoutItem(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_payout_item(
    db: Session,
    *,
    item: PayoutItem,
    data: Dict[str, Any],
) -> PayoutItem:
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_payout_item(
    db: Session,
    *,
    item: PayoutItem,
) -> None:
    db.delete(item)
    db.commit()


# =============================================================================
# FeeRates
# =============================================================================

def get_fee_rate(db: Session, fee_rate_id: int) -> Optional[FeeRate]:
    return db.get(FeeRate, fee_rate_id)


def list_fee_rates(
    db: Session,
    *,
    partner_id: int,
    fee_type: Optional[str] = None,
    effective_from: Optional[date] = None,
    effective_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[FeeRate], int]:
    """
    수수료(FeeRate) 목록 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [FeeRate.partner_id == partner_id]

    if fee_type is not None:
        filters.append(FeeRate.fee_type == fee_type)
    if effective_from is not None:
        filters.append(FeeRate.effective_from >= effective_from)
    if effective_to is not None:
        filters.append(FeeRate.effective_from <= effective_to)

    base_stmt: Select[FeeRate] = select(FeeRate).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(FeeRate.effective_from.desc(), FeeRate.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_fee_rate(
    db: Session,
    *,
    data: Dict[str, Any],
) -> FeeRate:
    obj = FeeRate(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_fee_rate(
    db: Session,
    *,
    fee_rate: FeeRate,
    data: Dict[str, Any],
) -> FeeRate:
    for key, value in data.items():
        setattr(fee_rate, key, value)
    db.add(fee_rate)
    db.commit()
    db.refresh(fee_rate)
    return fee_rate


def delete_fee_rate(
    db: Session,
    *,
    fee_rate: FeeRate,
) -> None:
    db.delete(fee_rate)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/billing.py 예시)
#
# def get_effective_fee_rate(
#     db: Session,
#     *,
#     partner_id: int,
#     fee_type: str,
#     at: date,
# ) -> Optional[FeeRate]:
#     """
#     특정 일자(at)에 유효한 수수료 레코드 하나를 가져오는 헬퍼.
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# PayoutAccounts
# =============================================================================

def get_payout_account(db: Session, account_id: int) -> Optional[PayoutAccount]:
    return db.get(PayoutAccount, account_id)


def list_payout_accounts(
    db: Session,
    *,
    partner_id: int,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[PayoutAccount], int]:
    """
    파트너의 정산 계좌 목록.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [PayoutAccount.partner_id == partner_id]

    base_stmt: Select[PayoutAccount] = select(PayoutAccount).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(PayoutAccount.is_primary.desc(), PayoutAccount.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_payout_account(
    db: Session,
    *,
    data: Dict[str, Any],
) -> PayoutAccount:
    """
    파트너 정산 계좌 생성.
    - is_primary=True 가 여러 개 생기지 않도록, set_primary_payout_account 헬퍼와 함께 사용하는 것을 권장.
    """
    obj = PayoutAccount(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_payout_account(
    db: Session,
    *,
    account: PayoutAccount,
    data: Dict[str, Any],
) -> PayoutAccount:
    for key, value in data.items():
        setattr(account, key, value)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def delete_payout_account(
    db: Session,
    *,
    account: PayoutAccount,
) -> None:
    db.delete(account)
    db.commit()


def set_primary_payout_account(
    db: Session,
    *,
    account: PayoutAccount,
) -> PayoutAccount:
    """
    파트너당 primary 계좌를 하나로 맞춰주는 헬퍼.
    - 다른 계좌의 is_primary 를 False 로 만들고, 이 계좌를 True로 설정.
    """
    stmt: Select[PayoutAccount] = select(PayoutAccount).where(
        PayoutAccount.partner_id == account.partner_id,
        PayoutAccount.id != account.id,
    )
    others = db.execute(stmt).scalars().all()

    for other in others:
        if other.is_primary:
            other.is_primary = False
            db.add(other)

    account.is_primary = True
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


# =============================================================================
# BusinessProfile
# =============================================================================

def get_business_profile(
    db: Session,
    *,
    partner_id: int,
) -> Optional[BusinessProfile]:
    """
    비즈니스 프로필 단건 조회.
    - PK = partner_id
    """
    return db.get(BusinessProfile, partner_id)


def create_business_profile(
    db: Session,
    *,
    data: Dict[str, Any],
) -> BusinessProfile:
    obj = BusinessProfile(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_business_profile(
    db: Session,
    *,
    profile: BusinessProfile,
    data: Dict[str, Any],
) -> BusinessProfile:
    for key, value in data.items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def upsert_business_profile(
    db: Session,
    *,
    partner_id: int,
    data: Dict[str, Any],
) -> BusinessProfile:
    """
    partner_id 기준으로 없으면 생성, 있으면 업데이트.
    """
    profile = get_business_profile(db, partner_id=partner_id)
    if profile is None:
        payload = {**data, "partner_id": partner_id}
        return create_business_profile(db, data=payload)

    for key, value in data.items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def delete_business_profile(
    db: Session,
    *,
    profile: BusinessProfile,
) -> None:
    db.delete(profile)
    db.commit()


# =============================================================================
# ClassFinanceMonthly
# =============================================================================

def get_class_finance_monthly(
    db: Session,
    cfm_id: int,
) -> Optional[ClassFinanceMonthly]:
    return db.get(ClassFinanceMonthly, cfm_id)


def list_class_finance_monthly(
    db: Session,
    *,
    class_id: Optional[int] = None,
    month_from: Optional[date] = None,
    month_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[ClassFinanceMonthly], int]:
    """
    분반별 월간 재무 집계(ClassFinanceMonthly) 목록.
    - ETL 집계 결과를 읽기 전용으로 사용하는 것을 권장.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if class_id is not None:
        filters.append(ClassFinanceMonthly.class_id == class_id)
    if month_from is not None:
        filters.append(ClassFinanceMonthly.month >= month_from)
    if month_to is not None:
        filters.append(ClassFinanceMonthly.month <= month_to)

    base_stmt: Select[ClassFinanceMonthly] = select(ClassFinanceMonthly)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(ClassFinanceMonthly.class_id.asc(), ClassFinanceMonthly.month.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_class_finance_monthly(
    db: Session,
    *,
    data: Dict[str, Any],
) -> ClassFinanceMonthly:
    """
    ETL/집계 작업에서 사용하는 생성 함수.
    - 일반 애플리케이션 코드에서는 직접 호출하지 않는 것을 권장.
    """
    obj = ClassFinanceMonthly(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_class_finance_monthly(
    db: Session,
    *,
    cfm: ClassFinanceMonthly,
    data: Dict[str, Any],
) -> ClassFinanceMonthly:
    for key, value in data.items():
        setattr(cfm, key, value)
    db.add(cfm)
    db.commit()
    db.refresh(cfm)
    return cfm


def delete_class_finance_monthly(
    db: Session,
    *,
    cfm: ClassFinanceMonthly,
) -> None:
    db.delete(cfm)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/billing.py 예시)
#
# def aggregate_class_finance_monthly(
#     db: Session,
#     *,
#     class_id: int,
#     month: date,
# ) -> ClassFinanceMonthly:
#     """
#     usage_daily / api_cost_daily / invoice_items 등을 기반으로
#     class_finance_monthly 를 재계산하는 ETL 헬퍼.
#     """
#     ...
# -----------------------------------------------------------------------------
