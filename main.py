# main.py
import warnings
from fastapi import FastAPI
from app.routers import register_routers

# 파이썬 3.14라서 langchain 내부 pydantic v1 쓰고 있는데 이게 아직은 보장못함
## 일단은 경고 코드임 무시 추후 langchain 3.14 공식 지원하면 사라짐
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="langchain_core._api.deprecation",
)



app = FastAPI(title="GrowFit API")
register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
