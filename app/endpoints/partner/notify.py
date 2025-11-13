# app/endpoints/partner/notify.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_admin
from crud.partner import notify as notify_crud
from schemas.partner.notify import (
    NotificationPreferenceCreate,
    NotificationPreferenceUpdate,
    NotificationPreferenceResponse,
    NotificationPreferencePage,
    EmailSubscriptionCreate,
    EmailSubscriptionUpdate,
    EmailSubscriptionResponse,
    EmailSubscriptionPage,
    MfaSettingCreate,
    MfaSettingUpdate,
    MfaSettingResponse,
    MfaSettingPage,
    LoginActivityCreate,
    LoginActivityResponse,
    LoginActivityPage,
)

router = APIRouter()


# ==============================
# notification_preferences
# ==============================

@router.get(
    "/preferences",
    response_model=NotificationPreferencePage,
)
def list_notification_preferences(
    partner_id: int = Path(..., ge=1),
    partner_user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = notify_crud.list_notification_prefs(
        db,
        partner_user_id=partner_user_id,
        page=page,
        size=size,
    )
    items = [NotificationPreferenceResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/preferences/{pref_id}",
    response_model=NotificationPreferenceResponse,
)
def get_notification_preference(
    partner_id: int = Path(..., ge=1),
    pref_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_notification_pref(db, pref_id=pref_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification_preference not found")
    return NotificationPreferenceResponse.model_validate(obj)


@router.post(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification_preference(
    partner_id: int = Path(..., ge=1),
    payload: NotificationPreferenceCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.create_notification_pref(db, data=data)
    return NotificationPreferenceResponse.model_validate(obj)


@router.patch(
    "/preferences/{pref_id}",
    response_model=NotificationPreferenceResponse,
)
def update_notification_preference(
    partner_id: int = Path(..., ge=1),
    pref_id: int = Path(..., ge=1),
    payload: NotificationPreferenceUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_notification_pref(db, pref_id=pref_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification_preference not found")

    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.update_notification_pref(db, pref=obj, data=data)
    return NotificationPreferenceResponse.model_validate(obj)


@router.delete(
    "/preferences/{pref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notification_preference(
    partner_id: int = Path(..., ge=1),
    pref_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_notification_pref(db, pref_id=pref_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification_preference not found")

    notify_crud.delete_notification_pref(db, pref=obj)
    return None


# ==============================
# email_subscriptions
# ==============================

@router.get(
    "/subscriptions",
    response_model=EmailSubscriptionPage,
)
def list_email_subscriptions(
    partner_id: int = Path(..., ge=1),
    partner_user_id: Optional[int] = Query(None),
    subscription_type: Optional[str] = Query(None),
    is_subscribed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = notify_crud.list_email_subscriptions(
        db,
        partner_user_id=partner_user_id,
        subscription_type=subscription_type,
        is_subscribed=is_subscribed,
        page=page,
        size=size,
    )
    items = [EmailSubscriptionResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/subscriptions/{sub_id}",
    response_model=EmailSubscriptionResponse,
)
def get_email_subscription(
    partner_id: int = Path(..., ge=1),
    sub_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_email_subscription(db, sub_id=sub_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="email_subscription not found")
    return EmailSubscriptionResponse.model_validate(obj)


@router.post(
    "/subscriptions",
    response_model=EmailSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_email_subscription(
    partner_id: int = Path(..., ge=1),
    payload: EmailSubscriptionCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.create_email_subscription(db, data=data)
    return EmailSubscriptionResponse.model_validate(obj)


@router.patch(
    "/subscriptions/{sub_id}",
    response_model=EmailSubscriptionResponse,
)
def update_email_subscription(
    partner_id: int = Path(..., ge=1),
    sub_id: int = Path(..., ge=1),
    payload: EmailSubscriptionUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_email_subscription(db, sub_id=sub_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="email_subscription not found")

    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.update_email_subscription(db, sub=obj, data=data)
    return EmailSubscriptionResponse.model_validate(obj)


@router.delete(
    "/subscriptions/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_email_subscription(
    partner_id: int = Path(..., ge=1),
    sub_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_email_subscription(db, sub_id=sub_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="email_subscription not found")

    notify_crud.delete_email_subscription(db, sub=obj)
    return None


# ==============================
# mfa_settings
# ==============================

@router.get(
    "/mfa",
    response_model=MfaSettingPage,
)
def list_mfa_settings(
    partner_id: int = Path(..., ge=1),
    is_enabled: Optional[bool] = Query(None),
    method: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = notify_crud.list_mfa_settings(
        db,
        is_enabled=is_enabled,
        method=method,
        page=page,
        size=size,
    )
    items = [MfaSettingResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/mfa/{partner_user_id}",
    response_model=MfaSettingResponse,
)
def get_mfa_setting(
    partner_id: int = Path(..., ge=1),
    partner_user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_mfa_setting(db, partner_user_id=partner_user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mfa_setting not found")
    return MfaSettingResponse.model_validate(obj)


@router.post(
    "/mfa",
    response_model=MfaSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mfa_setting(
    partner_id: int = Path(..., ge=1),
    payload: MfaSettingCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.create_mfa_setting(db, data=data)
    return MfaSettingResponse.model_validate(obj)


@router.patch(
    "/mfa/{partner_user_id}",
    response_model=MfaSettingResponse,
)
def update_mfa_setting(
    partner_id: int = Path(..., ge=1),
    partner_user_id: int = Path(..., ge=1),
    payload: MfaSettingUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = notify_crud.get_mfa_setting(db, partner_user_id=partner_user_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mfa_setting not found")

    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.update_mfa_setting(db, setting=obj, data=data)
    return MfaSettingResponse.model_validate(obj)


# ==============================
# login_activity (append-only)
# ==============================

@router.get(
    "/logins",
    response_model=LoginActivityPage,
)
def list_login_activities(
    partner_id: int = Path(..., ge=1),
    partner_user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    from_at: Optional[datetime] = Query(None),
    to_at: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = notify_crud.list_login_activities(
        db,
        partner_user_id=partner_user_id,
        status=status,
        ip_address=ip_address,
        from_at=from_at,
        to_at=to_at,
        page=page,
        size=size,
    )
    items = [LoginActivityResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/logins",
    response_model=LoginActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_login_activity(
    partner_id: int = Path(..., ge=1),
    payload: LoginActivityCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    """
    일반적으로는 service/partner/auth 에서 사용.
    운영에서 수동으로 넣을 일은 거의 없음.
    """
    data = payload.model_dump(exclude_unset=True)
    obj = notify_crud.create_login_activity(db, data=data)
    return LoginActivityResponse.model_validate(obj)
