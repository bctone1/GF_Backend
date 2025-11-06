from sqlalchemy.orm import Session
from crud.user.account import (
    user_crud, user_profile_crud, user_security_crud,
    user_privacy_crud, user_login_session_crud
)
from service.auth import hash_password, verify_password, issue_tokens
from models.user.account import UserLoginSession
from schemas.user.account import (
    UserCreate, UserResponse, UserProfileUpdate, LoginInput, AuthTokens
)
from fastapi import HTTPException, status
from sqlalchemy import select, func

def signup(db: Session, payload: UserCreate) -> UserResponse:
    data = payload.model_dump()
    raw_pw = data.pop("password", None)
    if not raw_pw:
        raise HTTPException(status_code=400, detail="password required")
    data["password_hash"] = hash_password(raw_pw)

    profile_in = None
    if "full_name" in data and data["full_name"]:
        profile_in = {"full_name": data.pop("full_name")}

    try:
        user = user_crud.create_with_profile(
            db, user_in=data, profile_in=profile_in, ensure_settings=True
        )
    except Exception:
        raise HTTPException(status_code=409, detail="email already exists")

    return UserResponse(user_id=user.user_id, email=user.email, default_role=user.default_role)


def login(db: Session, payload: LoginInput, meta: dict[str, str]) -> AuthTokens:
    user = user_crud.get_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    # 세션
    user_login_session_crud.open_session(
        db, user_id=user.user_id, obj_in={
            "device_name": meta.get("device_name"),
            "ip_address": meta.get("ip_address"),
            "location": meta.get("location"),
            "user_agent": meta.get("user_agent"),
        },
        single_current=True,
    )
    user_crud.set_last_login(db, user_id=user.user_id)
    return issue_tokens(user_id=user.user_id)
