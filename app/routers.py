# app/routers.py
from fastapi import FastAPI

from app.endpoints.supervisor.core import router as super_core
from app.endpoints.supervisor.auth import router as super_auth

from app.endpoints.partner.partner_core import router as partner_core
from app.endpoints.partner.course import router as partner_course
from app.endpoints.partner.student import router as partner_student

from app.endpoints.user.account import router as my_account

def register_routers(app: FastAPI) -> None:
    # common.auth 제거 (중복 방지)

    # supervisor
    app.include_router(super_auth, prefix="/supervisor", tags=["super/auth"])   # /supervisor/signup, /supervisor/login
    app.include_router(super_core, prefix="/supervisor/core", tags=["super/core"])

    # partner
    app.include_router(partner_core,    prefix="/partners",                      tags=["partner/core"])
    app.include_router(partner_course,  prefix="/partners/{partner_id}/course",  tags=["partner/course"])
    app.include_router(partner_student, prefix="/partners/{partner_id}/students", tags=["partner/students"])

    # user
    app.include_router(my_account, tags=["my_account"])
