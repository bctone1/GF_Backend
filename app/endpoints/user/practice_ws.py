# app/endpoints/user/practice_ws.py
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.deps import get_current_user_ws, get_db
from models.user.account import AppUser
from schemas.user.practice import PracticeTurnRequestExistingSession, PracticeTurnRequestNewSession
from service.user.practice.orchestrator import prepare_practice_turn_for_session
from service.user.practice.turn_runner import iter_practice_model_stream_events

from app.endpoints.user.practice import _validate_my_few_shot_example_ids


router = APIRouter()

WS_SEND_MAX_RETRIES = 2
WS_SEND_RETRY_BACKOFF_S = 0.2


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
                _validate_my_few_shot_example_ids(
                    db,
                    me=me,
                    example_ids=[int(x) for x in body.few_shot_example_ids],
                )

            session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
                db=db,
                me=me,
                session_id=0,
                class_id=class_id,
                body=body,
            )
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
            }
            try:
                body = PracticeTurnRequestExistingSession.model_validate(payload_body)
            except ValidationError as exc:
                await _send_json(
                    websocket,
                    {"event": "error", "detail": "invalid_payload", "errors": exc.errors()},
                )
                continue

            session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
                db=db,
                me=me,
                session_id=session_id,
                class_id=None,
                body=body,
            )
            generate_title = False
            requested_prompt_ids = None
            requested_generation_params = None
            requested_style_preset = None
            requested_style_params = None
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
