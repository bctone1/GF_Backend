# main.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.routers import register_routers

import warnings

warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    module="langchain_core._api.deprecation",
)


app = FastAPI(title="GrowFit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 도메인/포트 허용
    allow_credentials=True,
    allow_methods=["*"],      # 모든 메서드 허용 (GET, POST, PUT, DELETE ...)
    allow_headers=["*"],      # 모든 요청 헤더 허용
)

register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
