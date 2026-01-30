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
# helpers
# =========================================================
def _build_retrieval_params_from_body(body: PracticeComparisonTurnRequest) -> Optional[Dict[str, Any]]:
    if body.mode != "rag":
        return None

    params: Dict[str, Any] = {}
    if body.top_k is not None:
        params["top_k"] = body.top_k
    if body.chunk_size is not None:
        params["chunk_size"] = body.chunk_size
    if body.threshold is not None:
        params["threshold"] = float(body.threshold)
    return params or None


def _run_single_panel_turn(
    *,
    db: Session,
    me: AppUser,
    session: PracticeSession,
    settings: PracticeSessionSetting,
    models: List[Any],
    body: PracticeComparisonTurnRequest,
    run_obj: Any,
    knowledge_ids: List[int],
    retrieval_params: Optional[Dict[str, Any]],
) -> PracticeTurnResponse:
    turn = run_practice_turn(
        db=db,
        session=session,
        settings=settings,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        knowledge_ids=knowledge_ids,
        requested_retrieval_params=retrieval_params,
        generate_title=False,
    )

    # practice_responses에 comparison_run_id + panel 태깅
    for result in turn.results:
        practice_response_crud.update(
            db,
            response_id=result.response_id,
            data=PracticeResponseUpdate(
                comparison_run_id=run_obj.id,
                panel_key=body.panel,  # 기존 컬럼 유지 가정
            ),
        )

    return turn


# =========================================================
# Practice Comparison Runs
# =========================================================
@router.get(
    "/sessions/{session_id}/comparison-runs",
    response_model=Page[PracticeComparisonRunResponse],
    operation_id="list_practice_comparison_runs",
    summary="비교런목록",
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
    summary="비교런생성",
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
    summary="비교학습실행",
)
def run_practice_comparison_turn(
    session_id: int = Path(..., ge=0),
    class_id: Optional[int] = Query(None, ge=1),
    body: PracticeComparisonTurnRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    # 1) 세션 준비 (새 세션 or 기존 세션)
    if session_id == 0:
        if class_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="class_id_required")

        session, settings, models, _ctx_knowledge_ids = prepare_practice_turn_for_session(
            db=db,
            me=me,
            session_id=0,
            class_id=class_id,
            body=PracticeTurnRequestNewSession(
                prompt_text=body.prompt_text,
                model_names=body.model_names,
                # 비교 실행에서는 prompt_id/project_id를 안 쓰는 구조라면 None으로
                # prompt_id=None,
                project_id=None,
                knowledge_ids=body.knowledge_ids or [],
            ),
        )
    else:
        ensure_my_session(db, session_id, me)
        session, settings, models, _ctx_knowledge_ids = prepare_practice_turn_for_session(
            db=db,
            me=me,
            session_id=session_id,
            class_id=None,
            body=PracticeTurnRequestExistingSession(
                prompt_text=body.prompt_text,
                model_names=body.model_names,
            ),
        )

    # 2) comparison run row 생성 (패널 1개)
    if body.mode == "llm":
        effective_knowledge_ids: List[int] = []
        retrieval_params = None
    else:
        effective_knowledge_ids = body.knowledge_ids or _ctx_knowledge_ids
        if not effective_knowledge_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="knowledge_ids_required")
        retrieval_params = _build_retrieval_params_from_body(body)

    run_obj = practice_comparison_run_crud.create(
        db,
        session_id=session.session_id,  # PracticeSession PK가 session_id인 구조 가정
        data=PracticeComparisonRunCreate(
            panel=body.panel,
            prompt_text=body.prompt_text,
            model_names=body.model_names,
            mode=body.mode,
            knowledge_ids=effective_knowledge_ids,
            top_k=body.top_k,
            chunk_size=body.chunk_size,
            threshold=body.threshold,
        ),
    )

    # 3) 실행
    turn = _run_single_panel_turn(
        db=db,
        me=me,
        session=session,
        settings=settings,
        models=models,
        body=body,
        run_obj=run_obj,
        knowledge_ids=effective_knowledge_ids,
        retrieval_params=retrieval_params,
    )

    db.commit()

    return PracticeComparisonTurnResponse(
        run=PracticeComparisonRunResponse.model_validate(run_obj),
        panel_result=PracticeComparisonTurnPanelResult(
            panel=body.panel,
            mode=body.mode,
            turn=turn,
        ),
    )


@router.get(
    "/comparison-runs/{run_id}",
    response_model=PracticeComparisonRunResponse,
    operation_id="get_practice_comparison_run",
    summary="비교런조회",
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
    summary="비교런수정",
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
    summary="비교런삭제",
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
