# app/endpoints/user/practice_ws.py
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.deps import get_current_user_ws, get_db
from models.user.account import AppUser
from schemas.user.practice import PracticeTurnRequestNewSession
from service.user.practice.orchestrator import prepare_practice_turn_for_session
from service.user.practice.turn_runner import iter_practice_model_stream_events

from app.endpoints.user.practice import _validate_my_few_shot_example_ids


router = APIRouter()


@router.websocket("/ws/sessions/run")
async def ws_run_practice_turn_new_session(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user_ws),
) -> None:
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
    except Exception as exc:
        await websocket.send_json({"event": "error", "detail": f"invalid_payload: {exc}"})
        return

    class_id = payload.get("class_id")
    if not isinstance(class_id, int) or class_id < 1:
        await websocket.send_json({"event": "error", "detail": "class_id_required"})
        return

    payload_body = dict(payload)
    payload_body.pop("class_id", None)
    try:
        body = PracticeTurnRequestNewSession.model_validate(payload_body)
    except ValidationError as exc:
        await websocket.send_json(
            {"event": "error", "detail": "invalid_payload", "errors": exc.errors()}
        )
        return

    if body.model_names and len(body.model_names) > 3:
        await websocket.send_json({"event": "error", "detail": "max_3_models_per_session"})
        return

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

    if not models:
        await websocket.send_json({"event": "error", "detail": "no_models_available"})
        return
    if len(models) > 3:
        await websocket.send_json({"event": "error", "detail": "max_3_models_per_session"})
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    executor = ThreadPoolExecutor(max_workers=len(models))

    def _run_model_stream(model) -> None:
        try:
            for event in iter_practice_model_stream_events(
                session=session,
                settings=settings,
                model=model,
                prompt_text=body.prompt_text,
                user=me,
                knowledge_ids=ctx_knowledge_ids,
                generate_title=True,
                requested_prompt_ids=body.prompt_ids,
                requested_generation_params=(
                    body.generation_params.model_dump(exclude_unset=True)
                    if body.generation_params is not None
                    else None
                ),
                requested_style_preset=body.style_preset,
                requested_style_params=body.style_params,
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
    try:
        while done_count < len(models):
            msg = await queue.get()
            await websocket.send_json(msg)
            if msg.get("event") in {"done", "error"}:
                done_count += 1
    except WebSocketDisconnect:
        for future in futures:
            future.cancel()
        return
    finally:
        executor.shutdown(wait=False)

    await websocket.send_json({"event": "all_done", "session_id": session.session_id})
