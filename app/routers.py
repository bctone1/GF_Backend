# app/routers.py
from fastapi import FastAPI

# common
# from app.endpoints.common.links import router as links
from app.endpoints.common.course_public import router as common_course
from app.endpoints.common.model import router as model
# supervisor
from app.endpoints.supervisor.core import router as super_core
# from app.endpoints.supervisor.auth import router as super_auth

# partner
from app.endpoints.partner.partner_core import router as partner_core
from app.endpoints.partner.course import router as partner_course
from app.endpoints.partner.student import router as partner_student
# from app.endpoints.partner.catalog import router as partner_catalog
from app.endpoints.partner.classes import router as partner_classes
from app.endpoints.partner.session import router as partner_session
# from app.endpoints.partner.usage import router as partner_usage
# from app.endpoints.partner.notify import router as partner_notify
# from app.endpoints.partner.billing import router as partner_billing
# from app.endpoints.partner.prompt import router as partner_prompt
# from app.endpoints.partner.analytics import router as partner_analytics


# user
from app.endpoints.user.account import router as account
from app.endpoints.user.document import router as user_document
from app.endpoints.user.practice import router as practice
from app.endpoints.user.agent import router as agent
from app.endpoints.user.project import router as project

def register_routers(app: FastAPI) -> None:
    app.include_router(common_course,  prefix="/course", tags=["유틸"])
    app.include_router(model,  prefix="/models", tags=["유틸"])
    # app.include_router(links, prefix="/links", tags=["links"])

    # ==============================
    # Supervisor
    # ==============================
    # app.include_router(super_auth,        prefix="/supervisor",                     tags=["super/auth"])
    app.include_router(super_core,        prefix="/supervisor/core",                tags=["super/core"])

    # ==============================
    # Partner
    # ==============================
    app.include_router(partner_classes, prefix="/partner/{partner_id}/classes", tags=["partner/classes"])
    # app.include_router(partner_analytics, prefix="/partner/{partner_id}/analytics", tags=["partner/analytics"])
    # app.include_router(partner_billing,   prefix="/partner/{partner_id}/billing",   tags=["partner/billing"])
    # app.include_router(partner_catalog,   prefix="/partner/{partner_id}/catalog",   tags=["partner/catalog:모델등록"])
    app.include_router(partner_course,    prefix="/partner/{partner_id}/course",    tags=["partner/course"])
    # app.include_router(partner_notify,    prefix="/partner/{partner_id}/notify",    tags=["partner/notify"])
    app.include_router(partner_core,      prefix="/partner",                        tags=["partner/core"])
    # app.include_router(partner_prompt,    prefix="/partner/{partner_id}/prompt",    tags=["partner/prompt"])
    app.include_router(partner_session,   prefix="/partner/{partner_id}/session",   tags=["partner/session"])
    app.include_router(partner_student,   prefix="/partner/{partner_id}/student",   tags=["partner/student"])
    # app.include_router(partner_usage,     prefix="/partner/{partner_id}/usage",     tags=["partner/usage"])


    # ==============================
    # User
    # ==============================
    app.include_router(account,           prefix="/user",                 tags=["user/account"])
    app.include_router(user_document,     prefix="/user",                 tags=["user/document"])
    app.include_router(practice,          prefix="/user/practice",        tags=["user/practice"])
    app.include_router(agent,             prefix="",                      tags=["user/agent"])
    app.include_router((project),         prefix="",                      tags=["user/project"])