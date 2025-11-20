# # app/endpoints/supervisor/auth.py
# from fastapi import APIRouter, HTTPException, status
# from pydantic import BaseModel
#
# router = APIRouter()
#
# ADMIN_ID = "admin"        # 로컬용 하드코딩
# ADMIN_PASSWORD = "1234"   # 로컬용 하드코딩
# DEV_TOKEN = "dev-supervisor"  # 고정 토큰
#
# class LoginIn(BaseModel):
#     id: str
#     password: str
#
# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#
# @router.post("/login", response_model=TokenOut, operation_id="supervisor_login")
# def supervisor_login(data: LoginIn):
#     if data.id != ADMIN_ID or data.password != ADMIN_PASSWORD:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
#     return TokenOut(access_token=DEV_TOKEN)
