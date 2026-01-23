# app/endpoints/user/comparison.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user

from models.user.account import AppUser
from models.user.practice import PracticeSession, PracticeSessionSetting

from crud.user.comparison import practice_comparison_run_crud
from crud.user.practice import practice_response_crud

from schemas.base import Page
from schemas.user.comparison import (
    PracticeComparisonRunCreate,
    PracticeComparisonRunUpdate,
    PracticeComparisonRunResponse,
    PracticeComparisonTurnPanelResult,
    PracticeComparisonTurnRequest,
    PracticeComparisonTurnResponse,
    # PracticeTurnResponse,
)
from schemas.user.practice import (
    PracticeResponseUpdate,
    PracticeTurnRequestNewSession,
    PracticeTurnRequestExistingSession,
    PracticeTurnResponse,
)

from service.user.practice.ownership import ensure_my_session, ensure_my_comparison_run
from service.user.practice.orchestrator import prepare_practice_turn_for_session
from service.user.practice.turn_runner import run_practice_turn

router = APIRouter()


# =========================================================
# Practice Comparison Runs
# =========================================================
def _build_panel_retrieval_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    top_k = payload.get("top_k")
    threshold = payload.get("threshold")
    chunk_size = payload.get("chunk_size")
    if top_k is not None:
        params["top_k"] = top_k
    if threshold is not None:
        params["threshold"] = threshold
    if chunk_size is not None:
        params["chunk_size"] = chunk_size
    return params


def _run_comparison_turn(
    *,
    db: Session,
    me: AppUser,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    models: List[Any],
    body: PracticeComparisonTurnRequest,
    ctx_knowledge_ids: List[int],
    run_obj: Any,
    panel_key: str,
    panel_payload: Dict[str, Any],
) -> PracticeTurnResponse:
    mode = panel_payload.get("mode")
    if mode == "pure_llm":
        panel_knowledge_ids: List[int] = []
        panel_retrieval_params = None
    else:
        if not ctx_knowledge_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="knowledge_ids_required")
        panel_knowledge_ids = ctx_knowledge_ids
        rag_settings = panel_payload.get("rag_settings") or {}
        panel_retrieval_params = (
            _build_panel_retrieval_params(rag_settings) if mode == "rag" else None
        )

    turn = run_practice_turn(
        db=db,
        session=session,
        settings=settings,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        knowledge_ids=panel_knowledge_ids,
        requested_retrieval_params=panel_retrieval_params,
        generate_title=False,
    )
    for result in turn.results:
        practice_response_crud.update(
            db,
            response_id=result.response_id,
            data=PracticeResponseUpdate(
                comparison_run_id=run_obj.id,
                panel_key=panel_key,
            ),
        )
    return turn


@router.get(
    "/sessions/{session_id}/comparison-runs",
    response_model=Page[PracticeComparisonRunResponse],
    operation_id="list_practice_comparison_runs",
)
def list_practice_comparison_runs(
    session_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    ensure_my_session(db, session_id, me)
    rows, total = practice_comparison_run_crud.list_by_session(
        db,
        session_id=session_id,
        page=page,
        size=size,
    )
    items = [PracticeComparisonRunResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/sessions/{session_id}/comparison-runs",
    response_model=PracticeComparisonRunResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_comparison_run",
)
def create_practice_comparison_run(
    session_id: int = Path(..., ge=1),
    payload: PracticeComparisonRunCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    ensure_my_session(db, session_id, me)
    obj = practice_comparison_run_crud.create(db, session_id=session_id, data=payload)
    db.commit()
    return PracticeComparisonRunResponse.model_validate(obj)


@router.post(
    "/sessions/{session_id}/comparison-runs/run",
    response_model=PracticeComparisonTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_comparison_turn",
    summary="비교 학습 실행(패널 A/B)",
)
def run_practice_comparison_turn(
    session_id: int = Path(..., ge=0),
    class_id: Optional[int] = Query(None, ge=1),
    body: PracticeComparisonTurnRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    if session_id == 0:
        if class_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="class_id_required")
        session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
            db=db,
            me=me,
            session_id=0,
            class_id=class_id,
            body=PracticeTurnRequestNewSession(
                prompt_text=body.prompt_text,
                model_names=body.model_names,
                prompt_id=body.prompt_id,
                project_id=body.project_id,
                knowledge_ids=body.knowledge_ids,
            ),
        )
    else:
        session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
            db=db,
            me=me,
            session_id=session_id,
            class_id=None,
            body=PracticeTurnRequestExistingSession(
                prompt_text=body.prompt_text,
                model_names=body.model_names,
            ),
        )

    panel_a_config = body.panel_a.model_dump()
    panel_b_config = body.panel_b.model_dump()
    run_obj = practice_comparison_run_crud.create(
        db,
        session_id=session.session_id,
        data=PracticeComparisonRunCreate(
            prompt_text=body.prompt_text,
            panel_a_config=panel_a_config,
            panel_b_config=panel_b_config,
        ),
    )
    panel_results = [
        PracticeComparisonTurnPanelResult(
            panel_key="a",
            mode=body.panel_a.mode,
            turn=_run_comparison_turn(
                db=db,
                me=me,
                session=session,
                settings=settings,
                models=models,
                body=body,
                ctx_knowledge_ids=ctx_knowledge_ids,
                run_obj=run_obj,
                panel_key="a",
                panel_payload=panel_a_config,
            ),
        ),
        PracticeComparisonTurnPanelResult(
            panel_key="b",
            mode=body.panel_b.mode,
            turn=_run_comparison_turn(
                db=db,
                me=me,
                session=session,
                settings=settings,
                models=models,
                body=body,
                ctx_knowledge_ids=ctx_knowledge_ids,
                run_obj=run_obj,
                panel_key="b",
                panel_payload=panel_b_config,
            ),
        ),
    ]

    db.commit()
    return PracticeComparisonTurnResponse(
        run=PracticeComparisonRunResponse.model_validate(run_obj),
        panel_results=panel_results,
    )


@router.get(
    "/comparison-runs/{run_id}",
    response_model=PracticeComparisonRunResponse,
    operation_id="get_practice_comparison_run",
)
def get_practice_comparison_run(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    run, _session = ensure_my_comparison_run(db, run_id, me)
    return PracticeComparisonRunResponse.model_validate(run)


@router.patch(
    "/comparison-runs/{run_id}",
    response_model=PracticeComparisonRunResponse,
    operation_id="update_practice_comparison_run",
)
def update_practice_comparison_run(
    run_id: int = Path(..., ge=1),
    payload: PracticeComparisonRunUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    run, _session = ensure_my_comparison_run(db, run_id, me)
    updated = practice_comparison_run_crud.update(db, run=run, data=payload)
    db.commit()
    return PracticeComparisonRunResponse.model_validate(updated)


@router.delete(
    "/comparison-runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_comparison_run",
)
def delete_practice_comparison_run(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    run, _session = ensure_my_comparison_run(db, run_id, me)
    practice_comparison_run_crud.delete(db, run=run)
    db.commit()
    return None
