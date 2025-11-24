# crud/user/account.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from models.user.account import (
    AppUser,
    UserProfile,
    UserSecuritySetting,
    UserLoginSession,
    UserPrivacySetting,
)

# =============================================================================
# AppUser (user.users)
# =============================================================================
def get_by_id(db: Session, user_id: int) -> Optional[AppUser]:
    """기존 코드 호환용: user_crud.get_by_id(...)"""
    return db.get(AppUser, user_id)


def get_user(db: Session, user_id: int) -> Optional[AppUser]:
    """동일 의미 alias."""
    return db.get(AppUser, user_id)


def get_by_email(db: Session, email: str) -> Optional[AppUser]:
    """기존 코드 호환용: user_crud.get_by_email(...)"""
    stmt = select(AppUser).where(AppUser.email == email)
    return db.execute(stmt).scalars().first()


def list_users(
    db: Session,
    *,
    status: Optional[str] = None,
    is_partner: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[AppUser], int]:
    """
    사용자 목록 조회.
    - status 필터(예: active/suspended 등)
    - is_partner 필터(True/False)
    - 페이징 (rows, total) 반환
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if status is not None:
        filters.append(AppUser.status == status)

    # 강사 여부 필터 (한 번 승격되면 is_partner = true 로 유지)
    if is_partner is True:
        filters.append(AppUser.is_partner.is_(True))
    elif is_partner is False:
        filters.append(AppUser.is_partner.is_(False))

    base_stmt: Select[AppUser] = select(AppUser)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(AppUser.created_at.desc(), AppUser.user_id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_user(
    db: Session,
    *,
    data: Dict[str, Any],
) -> AppUser:
    """
    순수 user.users 생성.
    - data 에는 이미 password_hash 가 세팅되어 있어야 함.
    - 평문 password → hash 는 service/endpoint 에서 처리.
    - is_partner 는 기본적으로 false, 승격시 true 로 변경.
    """
    obj = AppUser(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_user(
    db: Session,
    *,
    user: AppUser,
    data: Dict[str, Any],
) -> AppUser:
    for key, value in data.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_user(
    db: Session,
    *,
    user: AppUser,
) -> None:
    db.delete(user)
    db.commit()


def create_with_profile(
    db: Session,
    *,
    user_in: Dict[str, Any],
    profile_in: Optional[Dict[str, Any]] = None,
    ensure_settings: bool = False,
) -> AppUser:
    """
    user_crud.create_with_profile(db, user_in={...}, profile_in={...}, ensure_settings=True)

    - user.users 생성 (user_in 안에 is_partner 포함 가능)
    - user.user_profiles (옵션)
    - user.user_security_settings / user.user_privacy_settings (ensure_settings=True 일 때 기본 생성)
    """
    user = AppUser(**user_in)
    db.add(user)
    db.flush()  # user_id 확보

    if profile_in is not None:
        profile = UserProfile(user_id=user.user_id, **profile_in)
        db.add(profile)

    if ensure_settings:
        # 기본 보안 설정
        if db.get(UserSecuritySetting, user.user_id) is None:
            sec = UserSecuritySetting(user_id=user.user_id)
            db.add(sec)
        # 기본 프라이버시 설정
        if db.get(UserPrivacySetting, user.user_id) is None:
            privacy = UserPrivacySetting(user_id=user.user_id)
            db.add(privacy)

    db.commit()
    db.refresh(user)
    return user


def set_last_login(
    db: Session,
    *,
    user_id: int,
    at: Optional[datetime] = None,
) -> None:
    """
    마지막 로그인 시각 업데이트.
    """
    at = at or datetime.now(timezone.utc)
    stmt = (
        update(AppUser)
        .where(AppUser.user_id == user_id)
        .values(last_login_at=at, updated_at=func.now())
    )
    db.execute(stmt)
    db.commit()



# =============================================================================
# UserProfile (user.user_profiles)
# =============================================================================
def get_profile(db: Session, user_id: int) -> Optional[UserProfile]:
    return db.get(UserProfile, user_id)


def upsert_profile(
    db: Session,
    *,
    user_id: int,
    data: Dict[str, Any],
) -> UserProfile:
    """
    프로필 생성 또는 업데이트.
    """
    obj = db.get(UserProfile, user_id)
    if obj is None:
        obj = UserProfile(user_id=user_id, **data)
        db.add(obj)
    else:
        for key, value in data.items():
            setattr(obj, key, value)
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_profile(
    db: Session,
    *,
    user_id: int,
) -> None:
    obj = db.get(UserProfile, user_id)
    if obj is None:
        return
    db.delete(obj)
    db.commit()


# =============================================================================
# UserSecuritySetting (user.user_security_settings)
# =============================================================================
def get_security_setting(db: Session, user_id: int) -> Optional[UserSecuritySetting]:
    return db.get(UserSecuritySetting, user_id)


def upsert_security_setting(
    db: Session,
    *,
    user_id: int,
    data: Dict[str, Any],
) -> UserSecuritySetting:
    obj = db.get(UserSecuritySetting, user_id)
    if obj is None:
        obj = UserSecuritySetting(user_id=user_id, **data)
        db.add(obj)
    else:
        for key, value in data.items():
            setattr(obj, key, value)
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_security_setting(
    db: Session,
    *,
    user_id: int,
) -> None:
    obj = db.get(UserSecuritySetting, user_id)
    if obj is None:
        return
    db.delete(obj)
    db.commit()


# =============================================================================
# UserLoginSession (user.user_login_sessions)
# =============================================================================
def get_login_session(db: Session, session_id: int) -> Optional[UserLoginSession]:
    return db.get(UserLoginSession, session_id)


def list_login_sessions(
    db: Session,
    *,
    user_id: int,
    only_current: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[UserLoginSession], int]:
    """
    로그인 세션 목록.
    - only_current=True  → is_current = true만
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = [UserLoginSession.user_id == user_id]
    if only_current is True:
        filters.append(UserLoginSession.is_current.is_(True))
    elif only_current is False:
        filters.append(UserLoginSession.is_current.is_(False))

    base_stmt: Select[UserLoginSession] = select(UserLoginSession).where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(UserLoginSession.logged_in_at.desc(), UserLoginSession.session_id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_login_session(
    db: Session,
    *,
    user_id: int,
    data: Dict[str, Any],
) -> UserLoginSession:
    """
    로그인 성공 시 세션 레코드 생성.
    - data: UserLoginSessionCreate.model_dump(exclude_unset=True)
    """
    obj = UserLoginSession(user_id=user_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_login_session(
    db: Session,
    *,
    session: UserLoginSession,
    data: Dict[str, Any],
) -> UserLoginSession:
    for key, value in data.items():
        setattr(session, key, value)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_login_session(
    db: Session,
    *,
    session: UserLoginSession,
    at: Optional[datetime] = None,
) -> UserLoginSession:
    """
    세션 종료 처리 (로그아웃 시).
    """
    at = at or datetime.now(timezone.utc)
    session.logged_out_at = at
    session.is_current = False
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_all_sessions_for_user(
    db: Session,
    *,
    user_id: int,
    at: Optional[datetime] = None,
) -> None:
    """
    2FA 재설정 / 비밀번호 변경 / 강제 로그아웃 등에서
    해당 유저의 현재 세션을 모두 종료할 때 사용.
    """
    at = at or datetime.now(timezone.utc)
    stmt = (
        update(UserLoginSession)
        .where(
            UserLoginSession.user_id == user_id,
            UserLoginSession.is_current.is_(True),
        )
        .values(logged_out_at=at, is_current=False)
    )
    db.execute(stmt)
    db.commit()



# =============================================================================
# UserPrivacySetting (user.user_privacy_settings)
# =============================================================================
def get_privacy_setting(db: Session, user_id: int) -> Optional[UserPrivacySetting]:
    return db.get(UserPrivacySetting, user_id)


def upsert_privacy_setting(
    db: Session,
    *,
    user_id: int,
    data: Dict[str, Any],
) -> UserPrivacySetting:
    obj = db.get(UserPrivacySetting, user_id)
    if obj is None:
        obj = UserPrivacySetting(user_id=user_id, **data)
        db.add(obj)
    else:
        for key, value in data.items():
            setattr(obj, key, value)
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_privacy_setting(
    db: Session,
    *,
    user_id: int,
) -> None:
    obj = db.get(UserPrivacySetting, user_id)
    if obj is None:
        return
    db.delete(obj)
    db.commit()
