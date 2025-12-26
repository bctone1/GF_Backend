# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.middleware import ProcessTimeMiddleware
from app.routers import register_routers

OPENAPI_TAGS = [
    {"name": "User", "description": "학생/일반 사용자 기능 (Practice, Documents, Agents 등)"},
    {"name": "Partner", "description": "강사/클래스 운영 기능"},
    {"name": "Supervisor", "description": "플랫폼 관리자 설정/정책/사용량"},
]

app = FastAPI(
    title="GrowFit API",
    version="0.1.0",
    description="GrowFit LLM practice platform API",
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(ProcessTimeMiddleware)

# ⚠️ 주의:
# allow_origins=["*"] + allow_credentials=True 조합은 보안적으로 위험하고,
# 환경/브라우저에 따라 CORS가 꼬일 수 있어. 가능하면 명시적으로 origins를 적는 걸 추천.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # docs dev (mint dev)
        "http://localhost:5173",  # (있다면) 프론트 dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
