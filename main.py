from fastapi import FastAPI


app = FastAPI(title="GrowFit API")

try:
    from app.routers import api as api_router  # 권장: app/routers.py에서 APIRouter 집계
    app.include_router(api_router)
except Exception:
    pass



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)