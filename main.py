# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.middleware import ProcessTimeMiddleware
from app.routers import register_routers


app = FastAPI(
    title="GrowFit API",
    version="0.1.0",
    description="GrowFit LLM practice platform API",
)

app.add_middleware(ProcessTimeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
