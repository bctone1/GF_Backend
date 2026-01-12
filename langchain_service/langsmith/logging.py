from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os

from langsmith import Client as LangSmithClient

from core import config

_client: Optional[LangSmithClient] = None


def _is_tracing_enabled() -> bool:
    value = str(getattr(config, "LANGSMITH_TRACING", "")).strip().lower()
    return value in {"true", "1", "yes", "on"}


def _apply_env() -> None:
    if config.LANGSMITH_ENDPOINT:
        os.environ.setdefault("LANGCHAIN_ENDPOINT", config.LANGSMITH_ENDPOINT)
        os.environ.setdefault("LANGSMITH_ENDPOINT", config.LANGSMITH_ENDPOINT)
    if config.LANGSMITH_API_KEY:
        os.environ.setdefault("LANGCHAIN_API_KEY", config.LANGSMITH_API_KEY)
        os.environ.setdefault("LANGSMITH_API_KEY", config.LANGSMITH_API_KEY)
    if config.LANGSMITH_PROJECT:
        os.environ.setdefault("LANGCHAIN_PROJECT", config.LANGSMITH_PROJECT)
        os.environ.setdefault("LANGSMITH_PROJECT", config.LANGSMITH_PROJECT)


def _get_client() -> Optional[LangSmithClient]:
    global _client
    if not _is_tracing_enabled():
        return None
    if _client is None:
        _apply_env()
        _client = LangSmithClient()
    return _client


def start_run(name: str, inputs: Dict[str, Any], run_type: str = "chain") -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    project_name = config.LANGSMITH_PROJECT or os.getenv("LANGCHAIN_PROJECT")
    return client.create_run(
        name=name,
        inputs=inputs,
        run_type=run_type,
        start_time=datetime.now(timezone.utc),
        project_name=project_name,
    )


def _get_run_id(run: Any) -> Optional[str]:
    if run is None:
        return None
    if isinstance(run, dict):
        return run.get("id") or run.get("run_id")
    return getattr(run, "id", None) or getattr(run, "run_id", None)


def end_run(
    run: Any,
    outputs: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    client = _get_client()
    run_id = _get_run_id(run)
    if client is None or not run_id:
        return
    client.update_run(
        run_id,
        outputs=outputs,
        error=error,
        end_time=datetime.now(timezone.utc),
    )
