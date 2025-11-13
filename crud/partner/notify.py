# crud/partner/notify.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.notify import (
    NotificationPreference,
    EmailSubscription,
    MfaSetting,
    LoginActivity,
)


# =============================================================================
# NotificationPreference (1:1 by partner_user_id)
# =============================================================================

def get_notification_pref(db: Session, pref_id: int) -> Optional[NotificationPreference]:
    """
    ID 기준 단건 조회.
    """
    return db.get(NotificationPreference, pref_id)


def get_notification_pref_by_user(
    db: Session,
    *,
    partner_user_id: int,
) -> Optional[NotificationPreference]:
    """
    partner_user_id 기준 단건 조회.
    """
    stmt: Select[NotificationPreference] = select(NotificationPreference).where(
        NotificationPreference.partner_user_id == partner_user_id
    )
    return db.execute(stmt).scalar_one_or_none()


def list_notification_prefs(
    db: Session,
    *,
    partner_user_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[NotificationPreference], int]:
    """
    알림 기본 설정 목록(관리자용).
    일반적으로는 my 페이지에서 get_by_user 만 쓰고,
    목록은 파트너 관리 화면에서만 사용.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if partner_user_id is not None:
        filters.append(NotificationPreference.partner_user_id == partner_user_id)

    base_stmt: Select[NotificationPreference] = select(NotificationPreference)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(NotificationPreference.partner_user_id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_notification_pref(
    db: Session,
    *,
    data: Dict[str, Any],
) -> NotificationPreference:
    """
    알림 기본 설정 생성.
    - NotificationPreferenceCreate.model_dump(exclude_unset=True) 사용.
    - partner_user_id 당 1개만 허용되므로, 이미 존재하면 에러가 날 수 있다.
    """
    obj = NotificationPreference(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def upsert_notification_pref_for_user(
    db: Session,
    *,
    partner_user_id: int,
    data: Dict[str, Any],
) -> NotificationPreference:
    """
    partner_user_id 기준으로 존재하면 업데이트, 없으면 생성.
    - service 레이어에서 my 설정 화면에서 주로 사용할 패턴.
    """
    pref = get_notification_pref_by_user(db, partner_user_id=partner_user_id)
    if pref is None:
        # ensure partner_user_id
        data = {**data, "partner_user_id": partner_user_id}
        return create_notification_pref(db, data=data)

    for key, value in data.items():
        setattr(pref, key, value)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def update_notification_pref(
    db: Session,
    *,
    pref: NotificationPreference,
    data: Dict[str, Any],
) -> NotificationPreference:
    """
    알림 기본 설정 수정.
    """
    for key, value in data.items():
        setattr(pref, key, value)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def delete_notification_pref(
    db: Session,
    *,
    pref: NotificationPreference,
) -> None:
    """
    알림 기본 설정 삭제.
    """
    db.delete(pref)
    db.commit()


# =============================================================================
# EmailSubscription (unique by partner_user_id + subscription_type)
# =============================================================================

def get_email_subscription(db: Session, sub_id: int) -> Optional[EmailSubscription]:
    return db.get(EmailSubscription, sub_id)


def get_email_subscription_by_user_type(
    db: Session,
    *,
    partner_user_id: int,
    subscription_type: str,
) -> Optional[EmailSubscription]:
    stmt: Select[EmailSubscription] = select(EmailSubscription).where(
        EmailSubscription.partner_user_id == partner_user_id,
        EmailSubscription.subscription_type == subscription_type,
    )
    return db.execute(stmt).scalar_one_or_none()


def list_email_subscriptions(
    db: Session,
    *,
    partner_user_id: Optional[int] = None,
    subscription_type: Optional[str] = None,
    is_subscribed: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[EmailSubscription], int]:
    """
    이메일 구독 목록.
    - 파트너 사용자별 혹은 구독 타입별로 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if partner_user_id is not None:
        filters.append(EmailSubscription.partner_user_id == partner_user_id)
    if subscription_type is not None:
        filters.append(EmailSubscription.subscription_type == subscription_type)
    if is_subscribed is not None:
        filters.append(EmailSubscription.is_subscribed == is_subscribed)

    base_stmt: Select[EmailSubscription] = select(EmailSubscription)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(
            EmailSubscription.partner_user_id.asc(),
            EmailSubscription.subscription_type.asc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_email_subscription(
    db: Session,
    *,
    data: Dict[str, Any],
) -> EmailSubscription:
    """
    이메일 구독 생성.
    - EmailSubscriptionCreate.model_dump(exclude_unset=True) 사용.
    """
    obj = EmailSubscription(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def upsert_email_subscription_for_user(
    db: Session,
    *,
    partner_user_id: int,
    subscription_type: str,
    data: Dict[str, Any],
) -> EmailSubscription:
    """
    partner_user_id + subscription_type 조합 기준으로 upsert.
    """
    sub = get_email_subscription_by_user_type(
        db,
        partner_user_id=partner_user_id,
        subscription_type=subscription_type,
    )
    if sub is None:
        payload = {
            **data,
            "partner_user_id": partner_user_id,
            "subscription_type": subscription_type,
        }
        return create_email_subscription(db, data=payload)

    for key, value in data.items():
        setattr(sub, key, value)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def update_email_subscription(
    db: Session,
    *,
    sub: EmailSubscription,
    data: Dict[str, Any],
) -> EmailSubscription:
    """
    이메일 구독 수정.
    """
    for key, value in data.items():
        setattr(sub, key, value)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def delete_email_subscription(
    db: Session,
    *,
    sub: EmailSubscription,
) -> None:
    """
    이메일 구독 삭제.
    """
    db.delete(sub)
    db.commit()


# =============================================================================
# MfaSetting (PK = partner_user_id)
# =============================================================================

def get_mfa_setting(
    db: Session,
    *,
    partner_user_id: int,
) -> Optional[MfaSetting]:
    """
    MFA 설정 단건 조회.
    """
    return db.get(MfaSetting, partner_user_id)


def list_mfa_settings(
    db: Session,
    *,
    is_enabled: Optional[bool] = None,
    method: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[MfaSetting], int]:
    """
    MFA 설정 목록 (보안/운영용).
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if is_enabled is not None:
        filters.append(MfaSetting.is_enabled == is_enabled)
    if method is not None:
        filters.append(MfaSetting.method == method)

    base_stmt: Select[MfaSetting] = select(MfaSetting)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(MfaSetting.partner_user_id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_mfa_setting(
    db: Session,
    *,
    data: Dict[str, Any],
) -> MfaSetting:
    """
    MFA 설정 생성.
    - MfaSettingCreate.model_dump(exclude_unset=True) 사용.
    """
    obj = MfaSetting(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def upsert_mfa_setting_for_user(
    db: Session,
    *,
    partner_user_id: int,
    data: Dict[str, Any],
) -> MfaSetting:
    """
    partner_user_id 기준으로 존재하면 업데이트, 없으면 생성.
    """
    setting = get_mfa_setting(db, partner_user_id=partner_user_id)
    if setting is None:
        payload = {**data, "partner_user_id": partner_user_id}
        return create_mfa_setting(db, data=payload)

    for key, value in data.items():
        setattr(setting, key, value)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def update_mfa_setting(
    db: Session,
    *,
    setting: MfaSetting,
    data: Dict[str, Any],
) -> MfaSetting:
    """
    MFA 설정 수정.
    - is_enabled, method, secret_encrypted, last_enabled_at 조정에 사용.
    """
    for key, value in data.items():
        setattr(setting, key, value)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def delete_mfa_setting(
    db: Session,
    *,
    setting: MfaSetting,
) -> None:
    """
    MFA 설정 삭제.
    """
    db.delete(setting)
    db.commit()


def enable_mfa(
    db: Session,
    *,
    partner_user_id: int,
    method: str,
    secret_encrypted: Optional[str] = None,
    enabled_at: Optional[datetime] = None,
) -> MfaSetting:
    """
    MFA 활성화 헬퍼.
    - service 레이어에서 MFA 등록 완료 시 호출하기 좋은 형태.
    """
    data: Dict[str, Any] = {
        "is_enabled": True,
        "method": method,
        "secret_encrypted": secret_encrypted,
        "last_enabled_at": enabled_at or datetime.utcnow(),
    }
    return upsert_mfa_setting_for_user(
        db,
        partner_user_id=partner_user_id,
        data=data,
    )


def disable_mfa(
    db: Session,
    *,
    partner_user_id: int,
) -> MfaSetting:
    """
    MFA 비활성화 헬퍼.
    """
    setting = get_mfa_setting(db, partner_user_id=partner_user_id)
    if setting is None:
        # 없으면 새로 만들지 않고 그대로 예외로 두는 것도 한 방법이지만,
        # 여기서는 기본 레코드를 생성해 두는 방식을 택할 수 있다.
        setting = create_mfa_setting(
            db,
            data={
                "partner_user_id": partner_user_id,
                "is_enabled": False,
                "method": None,
                "secret_encrypted": None,
            },
        )
        return setting

    setting.is_enabled = False
    setting.method = None
    setting.secret_encrypted = None
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


# -----------------------------------------------------------------------------
# NOTE (service/partner/auth.py 등에서 사용할만한 예시 인터페이스)
#
# def ensure_default_notification_settings(db: Session, partner_user_id: int) -> None:
#     """
#     파트너 유저가 처음 생성될 때 기본 알림/구독/MFA 설정을 초기화하는 용도.
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# LoginActivity (append-only)
# =============================================================================

def get_login_activity(db: Session, login_at: datetime, activity_id: int) -> Optional[LoginActivity]:
    """
    파티셔닝 PK(login_at, id) 기준 단건 조회.
    """
    # login_at + id 를 PK로 사용하므로, get() 대신 select 로 처리.
    stmt: Select[LoginActivity] = select(LoginActivity).where(
        LoginActivity.login_at == login_at,
        LoginActivity.id == activity_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def list_login_activities(
    db: Session,
    *,
    partner_user_id: Optional[int] = None,
    status: Optional[str] = None,
    ip_address: Optional[str] = None,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[LoginActivity], int]:
    """
    로그인 활동 로그 조회.
    - 파티셔닝 테이블이지만, 일반 SELECT 사용 가능.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if partner_user_id is not None:
        filters.append(LoginActivity.partner_user_id == partner_user_id)
    if status is not None:
        filters.append(LoginActivity.status == status)
    if ip_address is not None:
        filters.append(LoginActivity.ip_address == ip_address)
    if from_at is not None:
        filters.append(LoginActivity.login_at >= from_at)
    if to_at is not None:
        filters.append(LoginActivity.login_at <= to_at)

    base_stmt: Select[LoginActivity] = select(LoginActivity)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(LoginActivity.login_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_login_activity(
    db: Session,
    *,
    data: Dict[str, Any],
) -> LoginActivity:
    """
    로그인 활동 기록 (append-only).
    - LoginActivityCreate.model_dump(exclude_unset=True) 사용.
    - 파티셔닝은 DB 레벨에서 처리되므로, 여기서는 단순 INSERT.
    """
    obj = LoginActivity(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# 일반적으로 로그인 로그는 수정/삭제하지 않으므로 update/delete 제공 안 함.
# 필요하다면 운영용으로 별도의 정리 쿼리나 배치에서 삭제 처리.


# -----------------------------------------------------------------------------
# NOTE (service/partner/auth.py 에서 쓸 수 있는 헬퍼 예시)
#
# def record_partner_login(
#     db: Session,
#     *,
#     partner_user_id: Optional[int],
#     ip_address: Optional[str],
#     user_agent: Optional[str],
#     success: bool,
# ) -> None:
#     status = "success" if success else "failed"
#     data = {
#         "partner_user_id": partner_user_id,
#         "ip_address": ip_address,
#         "user_agent": user_agent,
#         "status": status,
#     }
#     create_login_activity(db, data=data)
# -----------------------------------------------------------------------------
