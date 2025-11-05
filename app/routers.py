# # app/routers.py
# 예시
# from fastapi import FastAPI
#
# # ----- common -----
# from app.routers.common.auth import router as auth
# from app.routers.common.health import router as health
# from app.routers.common.files import router as files
# from app.routers.common.webhooks import router as webhooks
#
# # ----- superviser (전역 스코프) -----
# from app.routers.superviser.dashboard import router as sv_dash
# from app.routers.superviser.organizations import router as sv_orgs
# from app.routers.superviser.users import router as sv_users
# from app.routers.superviser.billing import router as sv_billing
# from app.routers.superviser.analytics import router as sv_analytics
# from app.routers.superviser.reports import router as sv_reports
# from app.routers.superviser.system import router as sv_system
# from app.routers.superviser.settings import router as sv_settings
#
# # ----- partner (조직 스코프) -----
# from app.routers.partner.partners import router as pt_self
# from app.routers.partner.users import router as pt_users
# from app.routers.partner.projects import router as pt_projects
# from app.routers.partner.students import router as pt_students
# from app.routers.partner.sessions import router as pt_sessions
# from app.routers.partner.catalog import router as pt_catalog
# from app.routers.partner.prompts import router as pt_prompts
# from app.routers.partner.usage import router as pt_usage
# from app.routers.partner.analytics import router as pt_analytics
# from app.routers.partner.billing import router as pt_billing
#
# # ----- user (개인 스코프) -----
# from app.routers.user.account import router as me_account
# from app.routers.user.projects import router as me_projects
# from app.routers.user.documents import router as me_documents
# from app.routers.user.agents import router as me_agents
# from app.routers.user.practice import router as me_practice
# from app.routers.user.sessions import router as me_sessions
# from app.routers.user.feedback import router as me_feedback
#
#
# def register_routers(app: FastAPI) -> None:
#     # common
#     app.include_router(auth,     prefix="/auth",      tags=["auth"])
#     app.include_router(health,   prefix="/_health",   tags=["system"])
#     app.include_router(files,    prefix="/files",     tags=["files"])
#     app.include_router(webhooks, prefix="/webhooks",  tags=["webhooks"])
#
#     # superviser
#     app.include_router(sv_dash,      prefix="/superviser/dashboard",     tags=["superviser.dashboard"])
#     app.include_router(sv_orgs,      prefix="/superviser/organizations", tags=["superviser.organizations"])
#     app.include_router(sv_users,     prefix="/superviser/users",         tags=["superviser.users"])
#     app.include_router(sv_billing,   prefix="/superviser/billing",       tags=["superviser.billing"])
#     app.include_router(sv_analytics, prefix="/superviser/analytics",     tags=["superviser.analytics"])
#     app.include_router(sv_reports,   prefix="/superviser/reports",       tags=["superviser.reports"])
#     app.include_router(sv_system,    prefix="/superviser/system",        tags=["superviser.system"])
#     app.include_router(sv_settings,  prefix="/superviser/settings",      tags=["superviser.settings"])
#
#     # partner (조직별 경로 변수 고정)
#     app.include_router(pt_self,     prefix="/partners/{partner_id}",                tags=["partner.self"])
#     app.include_router(pt_users,    prefix="/partners/{partner_id}/users",         tags=["partner.users"])
#     app.include_router(pt_projects, prefix="/partners/{partner_id}/projects",      tags=["partner.projects"])
#     app.include_router(pt_students, prefix="/partners/{partner_id}/students",      tags=["partner.students"])
#     app.include_router(pt_sessions, prefix="/partners/{partner_id}/sessions",      tags=["partner.sessions"])
#     app.include_router(pt_catalog,  prefix="/partners/{partner_id}/catalog",       tags=["partner.catalog"])
#     app.include_router(pt_prompts,  prefix="/partners/{partner_id}/prompts",       tags=["partner.prompts"])
#     app.include_router(pt_usage,    prefix="/partners/{partner_id}/usage",         tags=["partner.usage"])        # READ-ONLY
#     app.include_router(pt_analytics,prefix="/partners/{partner_id}/analytics",     tags=["partner.analytics"])    # READ-ONLY
#     app.include_router(pt_billing,  prefix="/partners/{partner_id}/billing",       tags=["partner.billing"])
#
#     # user (개인 스코프는 /me 권장)
#     app.include_router(me_account,   prefix="/me",             tags=["user.account"])
#     app.include_router(me_projects,  prefix="/me/projects",    tags=["user.projects"])
#     app.include_router(me_documents, prefix="/me/documents",   tags=["user.documents"])
#     app.include_router(me_agents,    prefix="/me/agents",      tags=["user.agents"])
#     app.include_router(me_practice,  prefix="/me/practice",    tags=["user.practice"])
#     app.include_router(me_sessions,  prefix="/me/sessions",    tags=["user.sessions"])
#     app.include_router(me_feedback,  prefix="/me/feedback",    tags=["user.feedback"])
