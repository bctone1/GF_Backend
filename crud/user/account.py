# crud/user/account.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud.base import CRUDBase
from models.user.account import (
    User,
    UserProfile,
    UserSecuritySetting,
    UserLoginSession,
    UserPrivacySetting,
)

# ---- Pydantic 스키마 타입 힌트(프로젝트 스키마 네이밍에 맞춰 사용) ----
# 존재하지 않는 경우 dict로도 동작하도록 BaseModel | dict 허용
try:
    from schemas.user.account import (
        UserCreate, UserUpdate,
        UserProfileUpdate,
        UserSecuritySettingUpdate,
        UserPrivacySettingUpdate,
        UserLoginSessionCreate, UserLoginSessionUpdate,
    )
except Exception:
    UserCreate = UserUpdate = UserProfileUpdate = UserSecuritySettingUpdate = UserPrivacySettingUpdate = UserLoginSessionCreate = UserLoginSessionUpdate = BaseModel  # type: ignore


# =========================
# User
# =========================
class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        stmt = select(self.model).where(self.model.email == email)
        return db.execute(stmt).scalars().first()

    def create_with_profile(
        self,
        db: Session,
        *,
        user_in: UserCreate | dict[str, Any],
        profile_in: Optional[UserProfileUpdate | dict[str, Any]] = None,
        ensure_settings: bool = True,
    ) -> User:
        data = self._to_data(user_in)
        # 이메일 소문자 정규화는 서비스 계층에서 수행 권장(CITEXT 여도 일관성 위해)
        db_obj = self.model(**data)  # type: ignore
        db.add(db_obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # email unique 위반 등
            raise
        db.refresh(db_obj)

        # 프로필 생성(있으면 업데이트)
        if profile_in is not None:
            pdata = self._to_data(profile_in)
            self._upsert_profile(db, user_id=db_obj.user_id, data=pdata)

        if ensure_settings:
            # 보안/프라이버시 기본 레코드 확보
            self._ensure_security_row(db, db_obj.user_id)
            self._ensure_privacy_row(db, db_obj.user_id)

        return db_obj


    def set_last_login(self, db: Session, *, user_id: int, at: Optional[datetime] = None) -> None:
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(last_login_at=(at if at is not None else func.now()),
                    updated_at=func.now()))
        db.execute(stmt)
        db.commit()

    # ---- 내부 유틸 ----
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
# 모델별 CRUD 동작을 재사용 가능케하려고 캡슐화한 실행 인스턴스(싱글톤)
# =========================
user_crud = CRUDUser(User)
user_profile_crud = CRUDUserProfile(UserProfile)
user_security_crud = CRUDUserSecurity(UserSecuritySetting)
user_privacy_crud = CRUDUserPrivacy(UserPrivacySetting)
user_login_session_crud = CRUDUserLoginSession(UserLoginSession)
