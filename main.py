# main.py
import os

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from fastapi.responses import HTMLResponse
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
    docs_url=None,
    redoc_url=None,
    servers=[
        {"url": "https://growfit.onecloud.kr:3004/", "description": "Production"},
        {"url": "http://127.0.0.1:9000", "description": "Local"},
    ],
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


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html() -> HTMLResponse:
    method_order = ["get", "post", "patch", "put", "delete", "head", "options", "trace"]
    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html>
  <head>
    <link
      rel="stylesheet"
      type="text/css"
      href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
    />
    <title>{app.title} - Swagger UI</title>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      const methodOrder = {method_order};
      window.ui = SwaggerUIBundle({{
        url: "{app.openapi_url}",
        dom_id: "#swagger-ui",
        operationsSorter: (a, b) => {{
          const aIndex = methodOrder.indexOf(a.get("method"));
          const bIndex = methodOrder.indexOf(b.get("method"));
          const normalizedA = aIndex === -1 ? methodOrder.length : aIndex;
          const normalizedB = bIndex === -1 ? methodOrder.length : bIndex;
          return normalizedA - normalizedB;
        }},
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset,
        ],
        layout: "BaseLayout",
      }});
    </script>
  </body>
</html>
"""
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def swagger_ui_redirect() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)