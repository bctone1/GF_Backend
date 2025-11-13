# app/routers.py
from fastapi import FastAPI

# supervisor
from app.endpoints.supervisor.core import router as super_core
from app.endpoints.supervisor.auth import router as super_auth

# partner
from app.endpoints.partner.partner_core import router as partner_core
from app.endpoints.partner.course import router as partner_course
from app.endpoints.partner.student import router as partner_student
from app.endpoints.partner.catalog import router as partner_catalog
from app.endpoints.partner.session import router as partner_session
from app.endpoints.partner.usage import router as partner_usage
from app.endpoints.partner.notify import router as partner_notify
from app.endpoints.partner.billing import router as partner_billing
from app.endpoints.partner.prompt import router as partner_prompt
from app.endpoints.partner.analytics import router as partner_analytics  # ← 추가

# user
from app.endpoints.user.account import router as my_account

def register_routers(app: FastAPI) -> None:
    # ==============================
    # Supervisor
    # ==============================
    app.include_router(super_auth, prefix="/supervisor", tags=["super/auth"])
    app.include_router(super_core, prefix="/supervisor/core", tags=["super/core"])

    # ==============================
    # Partner
    # ==============================
    app.include_router(partner_core,    prefix="/partners",                        tags=["partner/core"])
    app.include_router(partner_course,  prefix="/partners/{partner_id}/course",    tags=["partner/course"])
    app.include_router(partner_student, prefix="/partners/{partner_id}/students",  tags=["partner/students"])
    app.include_router(partner_catalog, prefix="/partners/{partner_id}/catalog",   tags=["partner/catalog"])
    app.include_router(partner_session, prefix="/partners/{partner_id}/sessions",  tags=["partner/sessions"])
    app.include_router(partner_usage,   prefix="/partners/{partner_id}/usage",     tags=["partner/usage"])
    app.include_router(partner_notify,  prefix="/partners/{partner_id}/notify",    tags=["partner/notify"])
    app.include_router(partner_billing, prefix="/partners/{partner_id}/billing",   tags=["partner/billing"])
    app.include_router(partner_prompt,  prefix="/partners/{partner_id}/prompt",    tags=["partner/prompt"])
    app.include_router(partner_analytics, prefix="/partners/{partner_id}/analytics", tags=["partner/analytics"])  # ← 추가

    # ==============================
    # User
    # ==============================
    app.include_router(my_account, tags=["my_account"])
