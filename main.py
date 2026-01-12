# main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config
from core.middleware import ProcessTimeMiddleware
from app.routers import register_routers


def _configure_langsmith_tracing() -> None:
    if config.LANGSMITH_TRACING and config.LANGSMITH_TRACING.lower() == "true":
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if config.LANGSMITH_API_KEY:
            os.environ["LANGCHAIN_API_KEY"] = config.LANGSMITH_API_KEY
        if config.LANGSMITH_PROJECT:
            os.environ["LANGCHAIN_PROJECT"] = config.LANGSMITH_PROJECT


_configure_langsmith_tracing()

app = FastAPI(
    title="GrowFit API",
    version="0.1.0",
    description="GrowFit LLM practice platform API",
)

app.add_middleware(ProcessTimeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
