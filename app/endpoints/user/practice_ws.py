# app/endpoints/user/practice_ws.py
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.deps import get_current_user_ws, get_db
from database.session import SessionLocal
from crud.user.document import document_crud
from models.user.account import AppUser
from schemas.user.practice import (
    PracticeTurnRequestExistingSession,
    PracticeTurnRequestNewSession,
)
from service.user.practice.orchestrator import prepare_practice_turn_for_session
from service.user.practice.turn_runner import iter_practice_model_stream_events

from service.user.fewshot import validate_my_few_shot_example_ids


router = APIRouter()

WS_SEND_MAX_RETRIES = 2
WS_SEND_RETRY_BACKOFF_S = 0.2

DOC_POLL_INTERVAL_S = 1.5
DOC_POLL_TIMEOUT_S = 120.0


def _get_unready_knowledge_ids(db: Session, knowledge_ids: list[int]) -> list[int]:
    """Return subset of *knowledge_ids* whose status is not 'ready'."""
    if not knowledge_ids:
        return []
    unready: list[int] = []
    for kid in knowledge_ids:
        doc = document_crud.get(db, kid)
        if doc is not None and doc.status != "ready":
            unready.append(kid)
    return unready


async def _await_documents_ready(
    websocket: WebSocket,
    knowledge_ids: list[int],
    session_id: int,
    timeout_s: float = DOC_POLL_TIMEOUT_S,
    poll_interval_s: float = DOC_POLL_INTERVAL_S,
) -> None:
    """Poll document status until all *knowledge_ids* are ready.

    Sends ``doc_status`` events to the client on every poll.
    Uses a separate DB session so background-task commits are visible.

    Raises:
        HTTPException: on not-found / failed / timeout.
        WebSocketDisconnect: if the client disconnects while waiting.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    pending = set(knowledge_ids)

    poll_db = SessionLocal()
    try:
        while pending:
            if loop.time() >= deadline:
                for kid in pending:
                    await _send_json(websocket, {
                        "event": "doc_status",
                        "session_id": session_id,
                        "knowledge_id": kid,
                        "status": "timeout",
                        "progress": 0,
                        "error": "document processing timed out",
                    })
                raise HTTPException(status_code=408, detail="document_processing_timeout")

            poll_db.expire_all()
            done_this_round: list[int] = []

            for kid in pending:
                doc = document_crud.get(poll_db, kid)

                if doc is None:
                    await _send_json(websocket, {
                        "event": "doc_status",
                        "session_id": session_id,
                        "knowledge_id": kid,
                        "status": "not_found",
                        "progress": 0,
                        "error": "document not found",
                    })
                    raise HTTPException(status_code=404, detail="document_not_found")

                await _send_json(websocket, {
                    "event": "doc_status",
                    "session_id": session_id,
                    "knowledge_id": kid,
                    "status": doc.status,
                    "progress": doc.progress or 0,
                })

                if doc.status == "ready":
                    done_this_round.append(kid)
                elif doc.status == "failed":
                    await _send_json(websocket, {
                        "event": "doc_status",
                        "session_id": session_id,
                        "knowledge_id": kid,
                        "status": "failed",
                        "progress": doc.progress or 0,
                        "error": doc.error_message or "document processing failed",
                    })
                    raise HTTPException(status_code=422, detail="document_processing_failed")

            for kid in done_this_round:
                pending.discard(kid)

            if pending:
                await asyncio.sleep(poll_interval_s)
    finally:
        poll_db.close()


async def _send_json(websocket: WebSocket, payload: Dict[str, Any]) -> None:
    for attempt in range(WS_SEND_MAX_RETRIES + 1):
        try:
            await websocket.send_json(jsonable_encoder(payload))
            return
        except WebSocketDisconnect:
            if attempt >= WS_SEND_MAX_RETRIES:
                raise
            await asyncio.sleep(WS_SEND_RETRY_BACKOFF_S * (2**attempt))
        except RuntimeError:
            if attempt >= WS_SEND_MAX_RETRIES:
                raise
            await asyncio.sleep(WS_SEND_RETRY_BACKOFF_S * (2**attempt))


async def _send_http_exception(websocket: WebSocket, exc: HTTPException) -> None:
    detail = exc.detail if exc.detail is not None else "error"
    await _send_json(
        websocket,
        {
            "event": "error",
            "detail": detail,
            "status_code": exc.status_code,
        },
    )


async def _run_practice_turn(
    *,
    websocket: WebSocket,
    session,
    settings,
    models,
    prompt_text: str,
    user: AppUser,
    knowledge_ids: list[int],
    generate_title: bool,
    requested_prompt_ids: list[int] | None,
    requested_generation_params: Dict[str, Any] | None,
    requested_style_preset: str | None,
    requested_style_params: Dict[str, Any] | None,
) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    executor = ThreadPoolExecutor(max_workers=len(models))

    def _run_model_stream(model) -> None:
        try:
            for event in iter_practice_model_stream_events(
                session=session,
                settings=settings,
                model=model,
                prompt_text=prompt_text,
                user=user,
                knowledge_ids=knowledge_ids,
                generate_title=generate_title,
                requested_prompt_ids=requested_prompt_ids,
                requested_generation_params=requested_generation_params,
                requested_style_preset=requested_style_preset,
                requested_style_params=requested_style_params,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "event": "error",
                    "session_id": session.session_id,
                    "model_name": getattr(model, "model_name", None),
                    "detail": str(exc),
                },
            )

    futures = [loop.run_in_executor(executor, _run_model_stream, model) for model in models]

    done_count = 0
    session_title: str | None = None
    try:
        while done_count < len(models):
            msg = await queue.get()
            if msg.get("event") == "done" and "session_title" in msg:
                session_title = msg.get("session_title")
            await _send_json(websocket, msg)
            if msg.get("event") in {"done", "error"}:
                done_count += 1
    except WebSocketDisconnect:
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=False)

    await _send_json(
        websocket,
        {"event": "done", "session_id": session.session_id, "session_title": session_title},
    )


@router.websocket("/ws/sessions/run")
async def ws_run_practice_turn_new_session(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user_ws),
) -> None:
    await websocket.accept()

    while True:
        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except Exception as exc:
            await _send_json(websocket, {"event": "error", "detail": f"invalid_payload: {exc}"})
            continue

        session_id = payload.get("session_id")
        if not isinstance(session_id, int):
            await _send_json(websocket, {"event": "error", "detail": "session_id_required"})
            continue

        if session_id == 0:
            class_id = payload.get("class_id")
            if not isinstance(class_id, int) or class_id < 1:
                await _send_json(websocket, {"event": "error", "detail": "class_id_required"})
                continue

            payload_body = dict(payload)
            payload_body.pop("class_id", None)
            payload_body.pop("session_id", None)
            try:
                body = PracticeTurnRequestNewSession.model_validate(payload_body)
            except ValidationError as exc:
                await _send_json(
                    websocket,
                    {"event": "error", "detail": "invalid_payload", "errors": exc.errors()},
                )
                continue

            if body.model_names and len(body.model_names) > 3:
                await _send_json(websocket, {"event": "error", "detail": "max_3_models_per_session"})
                continue

            if body.few_shot_example_ids:
                try:
                    validate_my_few_shot_example_ids(
                        db,
                        me=me,
                        example_ids=[int(x) for x in body.few_shot_example_ids],
                    )
                except HTTPException as exc:
                    await _send_http_exception(websocket, exc)
                    continue

            try:
                session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
                    db=db,
                    me=me,
                    session_id=0,
                    class_id=class_id,
                    body=body,
                )
            except HTTPException as exc:
                await _send_http_exception(websocket, exc)
                continue
            generate_title = True
            requested_prompt_ids = body.prompt_ids
            requested_generation_params = (
                body.generation_params.model_dump(exclude_unset=True)
                if body.generation_params is not None
                else None
            )
            requested_style_preset = body.style_preset
            requested_style_params = body.style_params
            prompt_text = body.prompt_text
        elif session_id > 0:
            payload_body = {
                "prompt_text": payload.get("prompt_text"),
                "model_names": payload.get("model_names"),
                "prompt_ids": payload.get("prompt_ids"),
                "knowledge_ids": payload.get("knowledge_ids"),
                "style_preset": payload.get("style_preset"),
                "style_params": payload.get("style_params"),
                "generation_params": payload.get("generation_params"),
                "few_shot_example_ids": payload.get("few_shot_example_ids"),
            }
            try:
                body = PracticeTurnRequestExistingSession.model_validate(payload_body)
            except ValidationError as exc:
                await _send_json(
                    websocket,
                    {"event": "error", "detail": "invalid_payload", "errors": exc.errors()},
                )
                continue

            try:
                session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
                    db=db,
                    me=me,
                    session_id=session_id,
                    class_id=None,
                    body=body,
                )
            except HTTPException as exc:
                await _send_http_exception(websocket, exc)
                continue
            generate_title = False
            requested_prompt_ids = body.prompt_ids
            requested_generation_params = (
                body.generation_params.model_dump(exclude_unset=True)
                if body.generation_params is not None
                else None
            )
            requested_style_preset = body.style_preset
            requested_style_params = body.style_params
            prompt_text = body.prompt_text
        else:
            await _send_json(websocket, {"event": "error", "detail": "session_id_required"})
            continue

        if not models:
            await _send_json(websocket, {"event": "error", "detail": "no_models_available"})
            continue
        if len(models) > 3:
            await _send_json(websocket, {"event": "error", "detail": "max_3_models_per_session"})
            continue

        # -- Document readiness gate --
        unready_ids = _get_unready_knowledge_ids(db, ctx_knowledge_ids)
        if unready_ids:
            try:
                await _await_documents_ready(
                    websocket=websocket,
                    knowledge_ids=unready_ids,
                    session_id=session.session_id,
                )
            except HTTPException as exc:
                await _send_http_exception(websocket, exc)
                continue
            except WebSocketDisconnect:
                return

        try:
            await _run_practice_turn(
                websocket=websocket,
                session=session,
                settings=settings,
                models=models,
                prompt_text=prompt_text,
                user=me,
                knowledge_ids=ctx_knowledge_ids,
                generate_title=generate_title,
                requested_prompt_ids=requested_prompt_ids,
                requested_generation_params=requested_generation_params,
                requested_style_preset=requested_style_preset,
                requested_style_params=requested_style_params,
            )
        except WebSocketDisconnect:
            return
