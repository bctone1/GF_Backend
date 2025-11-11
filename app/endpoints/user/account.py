# app/endpoints/user/account.py
from __future__ import annotations

from typing import Optional, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.deps import get_db, get_current_user, get_current_session_id

from service.auth import verify_password, hash_password, issue_tokens

from crud.user.account import (
    user_crud,
    user_profile_crud,
    user_security_crud,
    user_privacy_crud,
    user_login_session_crud,
)
from models.user.account import AppUser, UserLoginSession

from schemas.user.account import (
    UserCreate, UserResponse,
    UserProfileUpdate, UserProfileResponse,
    UserSecuritySettingUpdate, UserSecuritySettingResponse,
    UserPrivacySettingUpdate, UserPrivacySettingResponse,
    UserLoginSessionCreate, UserLoginSessionResponse,
    LoginInput, AuthTokens,
)

router = APIRouter()


# ---------- 유틸 ----------
def _client_meta(req: Request) -> dict[str, Any]:
    ip = (req.client.host if req.client else None) or req.headers.get("x-forwarded-for") or None
    ua = req.headers.get("user-agent")
    return {"ip_address": ip, "user_agent": ua}


# ---------- Auth ----------
@router.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
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

    return user  # ORM -> UserResponse(from_attributes)


@router.post("/auth/login", response_model=AuthTokens)
def login(req: Request, payload: LoginInput, db: Session = Depends(get_db)) -> AuthTokens:
    user = user_crud.get_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    meta = _client_meta(req)
    sess_in = UserLoginSessionCreate(
        device_name=meta.get("device_name"),
        ip_address=meta.get("ip_address"),
        location=meta.get("location"),
        user_agent=meta.get("user_agent"),
    )
    user_login_session_crud.open_session(db, user_id=user.user_id, obj_in=sess_in, single_current=True)
    user_crud.set_last_login(db, user_id=user.user_id)

    return issue_tokens(user_id=user.user_id)  # dict 또는 dataclass OK(ORMBase)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_id: Optional[int] = Depends(get_current_session_id),
):
    if session_id:
        user_login_session_crud.close_session(db, session_id=session_id)
    else:
        user_login_session_crud.close_all_for_user(db, user_id=user.user_id)
    return


# ---------- My ----------
@router.get("/my", response_model=UserResponse)
def my(user: User = Depends(get_current_user)) -> UserResponse:
    return user  # ORM -> UserResponse(from_attributes)


@router.patch("/my/profile", response_model=UserProfileResponse)
def update_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserProfileResponse:
    row = user_profile_crud.upsert(db, user_id=user.user_id, obj_in=payload)
    return row


@router.patch("/my/security", response_model=UserSecuritySettingResponse)
def update_security(
    payload: UserSecuritySettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSecuritySettingResponse:
    row = user_security_crud.upsert(db, user_id=user.user_id, obj_in=payload)
    return row


@router.patch("/my/privacy", response_model=UserPrivacySettingResponse)
def update_privacy(
    payload: UserPrivacySettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPrivacySettingResponse:
    row = user_privacy_crud.upsert(db, user_id=user.user_id, obj_in=payload)
    return row


# ---------- My Sessions ----------
@router.get("/my/sessions", response_model=List[UserLoginSessionResponse])
def list_my_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[UserLoginSessionResponse]:
    stmt = (
        select(UserLoginSession)
        .where(UserLoginSession.user_id == user.user_id)
        .order_by(UserLoginSession.logged_in_at.desc())
    )
    rows = list(db.execute(stmt).scalars().all())
    # ip_address(INET) 안전 직렬화
    out: List[UserLoginSessionResponse] = []
    for r in rows:
        out.append(UserLoginSessionResponse(
            session_id=r.session_id,
            user_id=r.user_id,
            device_name=r.device_name,
            ip_address=str(r.ip_address) if r.ip_address is not None else None,
            location=r.location,
            user_agent=r.user_agent,
            logged_in_at=r.logged_in_at,
            logged_out_at=r.logged_out_at,
            is_current=r.is_current,
        ))
    return out


@router.post("/my/sessions/terminate", status_code=status.HTTP_204_NO_CONTENT)
def terminate_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(UserLoginSession).where(
        UserLoginSession.session_id == session_id,
        UserLoginSession.user_id == user.user_id,
    )
    row = db.execute(stmt).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="session not found")

    user_login_session_crud.close_session(db, session_id=session_id)
    return


@router.post("/my/sessions/terminate-all", status_code=status.HTTP_204_NO_CONTENT)
def terminate_all_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user_login_session_crud.close_all_for_user(db, user_id=user.user_id)
    return
