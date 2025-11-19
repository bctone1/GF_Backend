# main.py
from fastapi import FastAPI
from app.routers import register_routers

import warnings

warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    module="langchain_core._api.deprecation",
)


app = FastAPI(title="GrowFit API")
register_routers(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
