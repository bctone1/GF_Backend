# crud/user/account.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, func

from crud.base import CRUDBase
from models.user.account import (
    AppUser as UserModel,
    UserProfile,
    UserSecuritySetting,
    UserLoginSession,
    UserPrivacySetting,
)

# ---- Pydantic 스키마 ----
try:
    from schemas.user.account import (
        UserCreate, UserUpdate,
        UserProfileUpdate,
        UserSecuritySettingUpdate,
        UserPrivacySettingUpdate,
        UserLoginSessionCreate, UserLoginSessionUpdate,
    )
except Exception:
    from pydantic import BaseModel
    UserCreate = UserUpdate = UserProfileUpdate = (
        UserSecuritySettingUpdate
    ) = UserPrivacySettingUpdate = UserLoginSessionCreate = UserLoginSessionUpdate = BaseModel  # type: ignore


# User
# =========================
class CRUDUser:
    def __init__(self, model: type[UserModel]):
        self.model = model

    # ---- 기본 조회 ----
    def get_by_email(self, db: Session, email: str) -> Optional[UserModel]:
        return db.query(self.model).filter(self.model.email == email).first()

    # ---- 생성 + 프로필 ----
    def create_with_profile(
        self,
        db: Session,
        *,
        user_in: UserCreate | dict[str, Any],
        profile_in: Optional[UserProfileUpdate | dict[str, Any]] = None,
        ensure_settings: bool = True,
    ) -> UserModel:
        data = self._to_data(user_in)
        db_obj = self.model(**data)
        db.add(db_obj)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise
        db.refresh(db_obj)

        # 프로필 생성/업데이트
        if profile_in is not None:
            pdata = self._to_data(profile_in)
            self._upsert_profile(db, user_id=db_obj.user_id, data=pdata)

        if ensure_settings:
            self._ensure_security_row(db, db_obj.user_id)
            self._ensure_privacy_row(db, db_obj.user_id)

        return db_obj

    # ---- 로그인 시각 업데이트 ----
    def set_last_login(self, db: Session, *, user_id: int, at: Optional[datetime] = None) -> None:
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(last_login_at=(at or func.now()), updated_at=func.now())
        )
        db.execute(stmt)
        db.commit()

    # ---- 내부 유틸 ----
    def _to_data(self, obj: Any) -> dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump(exclude_unset=True)
        return vars(obj)

    def _upsert_profile(self, db: Session, *, user_id: int, data: dict[str, Any]) -> UserProfile:
        prof = db.get(UserProfile, user_id)
        if prof is None:
            prof = UserProfile(user_id=user_id, **data)
            db.add(prof)
        else:
            for k, v in data.items():
                if hasattr(prof, k):
                    setattr(prof, k, v)
        db.commit()
        db.refresh(prof)
        return prof

    def _ensure_security_row(self, db: Session, user_id: int) -> UserSecuritySetting:
        row = db.get(UserSecuritySetting, user_id)
        if row is None:
            row = UserSecuritySetting(user_id=user_id)
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    def _ensure_privacy_row(self, db: Session, user_id: int) -> UserPrivacySetting:
        row = db.get(UserPrivacySetting, user_id)
        if row is None:
            row = UserPrivacySetting(user_id=user_id)
            db.add(row)
            db.commit()
            db.refresh(row)
        return row


# =========================
# UserProfile
# =========================
class CRUDUserProfile(CRUDBase[UserProfile, UserProfileUpdate, UserProfileUpdate]):
    def upsert(self, db: Session, *, user_id: int, obj_in: UserProfileUpdate | dict[str, Any]) -> UserProfile:
        data = self._to_data(obj_in)
        row = db.get(UserProfile, user_id)
        if row is None:
            row = UserProfile(user_id=user_id, **data)
            db.add(row)
        else:
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return row


# =========================
# UserSecuritySetting
# =========================
class CRUDUserSecurity(CRUDBase[UserSecuritySetting, UserSecuritySettingUpdate, UserSecuritySettingUpdate]):
    def upsert(self, db: Session, *, user_id: int, obj_in: UserSecuritySettingUpdate | dict[str, Any]) -> UserSecuritySetting:
        data = self._to_data(obj_in)
        row = db.get(UserSecuritySetting, user_id)
        if row is None:
            row = UserSecuritySetting(user_id=user_id, **data)
            db.add(row)
        else:
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return row


# =========================
# UserPrivacySetting
# =========================
class CRUDUserPrivacy(CRUDBase[UserPrivacySetting, UserPrivacySettingUpdate, UserPrivacySettingUpdate]):
    def upsert(self, db: Session, *, user_id: int, obj_in: UserPrivacySettingUpdate | dict[str, Any]) -> UserPrivacySetting:
        data = self._to_data(obj_in)
        row = db.get(UserPrivacySetting, user_id)
        if row is None:
            row = UserPrivacySetting(user_id=user_id, **data)
            db.add(row)
        else:
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return row


# =========================
# UserLoginSession
# =========================
class CRUDUserLoginSession(CRUDBase[UserLoginSession, UserLoginSessionCreate, UserLoginSessionUpdate]):
    def open_session(
        self,
        db: Session,
        *,
        user_id: int,
        obj_in: UserLoginSessionCreate | dict[str, Any],
        single_current: bool = True,
    ) -> UserLoginSession:
        """로그인 세션 오픈. single_current=True면 기존 current 세션들을 종료."""
        if single_current:
            db.execute(
                update(UserLoginSession)
                .where(
                    UserLoginSession.user_id == user_id,
                    UserLoginSession.is_current.is_(True),
                    UserLoginSession.logged_out_at.is_(None),
                )
                .values(is_current=False, logged_out_at=func.now())
            )

        data = self._to_data(obj_in)
        row = UserLoginSession(user_id=user_id, **data)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def close_session(self, db: Session, *, session_id: int) -> None:
        db.execute(
            update(UserLoginSession)
            .where(UserLoginSession.session_id == session_id)
            .values(is_current=False, logged_out_at=func.now())
        )
        db.commit()

    def close_all_for_user(self, db: Session, *, user_id: int) -> int:
        res = db.execute(
            update(UserLoginSession)
            .where(
                UserLoginSession.user_id == user_id,
                UserLoginSession.is_current.is_(True),
                UserLoginSession.logged_out_at.is_(None),
            )
            .values(is_current=False, logged_out_at=func.now())
        )
        db.commit()
        return res.rowcount or 0


# =========================
# CRUD 인스턴스
# =========================
user_crud = CRUDUser(UserModel)
user_profile_crud = CRUDUserProfile(UserProfile)
user_security_crud = CRUDUserSecurity(UserSecuritySetting)
user_privacy_crud = CRUDUserPrivacy(UserPrivacySetting)
user_login_session_crud = CRUDUserLoginSession(UserLoginSession)
