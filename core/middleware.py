# core/middleware.py
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start
        # 헤더로 내려주기
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        return response
