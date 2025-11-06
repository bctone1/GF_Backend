# app/routers.py
from fastapi import FastAPI

# ----- common -----
# from app.endpoints.common.auth import router as auth
# from app.endpoints.common.health import router as health
# from app.endpoints.common.files import router as files
# from app.endpoints.common.webhooks import router as webhooks

# ----- supervisor (전역 스코프) -----
# 별칭: super_*
# from app.endpoints.supervisor.dashboard import router as super_dashboard
# from app.endpoints.supervisor.organizations import router as super_organizations
# from app.endpoints.supervisor.users import router as super_users
# from app.endpoints.supervisor.billing import router as super_billing
# from app.endpoints.supervisor.analytics import router as super_analytics
# from app.endpoints.supervisor.reports import router as super_reports
# from app.endpoints.supervisor.system import router as super_system
# from app.endpoints.supervisor.settings import router as super_settings

# ----- partner (조직 스코프) -----
# from app.endpoints.partner.partners import router as partner_self
# from app.endpoints.partner.users import router as partner_users
# from app.endpoints.partner.projects import router as partner_projects
# from app.endpoints.partner.students import router as partner_students
# from app.endpoints.partner.sessions import router as partner_sessions
# from app.endpoints.partner.catalog import router as partner_catalog
# from app.endpoints.partner.prompts import router as partner_prompts
# from app.endpoints.partner.usage import router as partner_usage
# from app.endpoints.partner.analytics import router as partner_analytics
# from app.endpoints.partner.billing import router as partner_billing

# ----- user (개인 스코프: /my) -----
from app.endpoints.user.account import router as my_account
# from app.endpoints.user.projects import router as my_projects
# from app.endpoints.user.documents import router as my_documents
# from app.endpoints.user.agents import router as my_agents
# from app.endpoints.user.practice import router as my_practice
# from app.endpoints.user.sessions import router as my_sessions
# from app.endpoints.user.feedback import router as my_feedback


def register_routers(app: FastAPI) -> None:
    # common
    # app.include_router(auth,     prefix="/auth",      tags=["auth"])
    # app.include_router(health,   prefix="/_health",   tags=["system"])
    # app.include_router(files,    prefix="/files",     tags=["files"])
    # app.include_router(webhooks, prefix="/webhooks",  tags=["webhooks"])

    # supervisor (URL path는 유지: /supervisor/*)
    # app.include_router(super_dashboard,   prefix="/supervisor/dashboard",     tags=["super.dashboard"])
    # app.include_router(super_organizations, prefix="/supervisor/organizations", tags=["super.organizations"])
    # app.include_router(super_users,       prefix="/supervisor/users",         tags=["super.users"])
    # app.include_router(super_billing,     prefix="/supervisor/billing",       tags=["super.billing"])
    # app.include_router(super_analytics,   prefix="/supervisor/analytics",     tags=["super.analytics"])
    # app.include_router(super_reports,     prefix="/supervisor/reports",       tags=["super.reports"])
    # app.include_router(super_system,      prefix="/supervisor/system",        tags=["super.system"])
    # app.include_router(super_settings,    prefix="/supervisor/settings",      tags=["super.settings"])

    # partner (조직별 경로 변수 고정)
    # app.include_router(partner_self,      prefix="/partners/{partner_id}",            tags=["partner.self"])
    # app.include_router(partner_users,     prefix="/partners/{partner_id}/users",      tags=["partner.users"])
    # app.include_router(partner_projects,  prefix="/partners/{partner_id}/projects",   tags=["partner.projects"])
    # app.include_router(partner_students,  prefix="/partners/{partner_id}/students",   tags=["partner.students"])
    # app.include_router(partner_sessions,  prefix="/partners/{partner_id}/sessions",   tags=["partner.sessions"])
    # app.include_router(partner_catalog,   prefix="/partners/{partner_id}/catalog",    tags=["partner.catalog"])
    # app.include_router(partner_prompts,   prefix="/partners/{partner_id}/prompts",    tags=["partner.prompts"])
    # app.include_router(partner_usage,     prefix="/partners/{partner_id}/usage",      tags=["partner.usage"])
    # app.include_router(partner_analytics, prefix="/partners/{partner_id}/analytics",  tags=["partner.analytics"])
    # app.include_router(partner_billing,   prefix="/partners/{partner_id}/billing",    tags=["partner.billing"])

    # user (/my/* 라우트를 내부에서 직접 선언했음을 가정. 추가 prefix 없음)
    app.include_router(my_account, tags=["my_account"])
    # app.include_router(my_projects,  tags=["my_projects"])
    # app.include_router(my_documents, tags=["my_documents"])
    # app.include_router(my_agents,    tags=["my_agents"])
    # app.include_router(my_practice,  tags=["my_practice"])
    # app.include_router(my_sessions,  tags=["my_sessions"])
    # app.include_router(my_feedback,  tags=["my_feedback"])
