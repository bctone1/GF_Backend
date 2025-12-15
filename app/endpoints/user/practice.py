# app/endpoints/user/practice.py
from __future__ import annotations

from typing import List, Any, Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    Body,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from core import config
from models.user.account import AppUser

from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    practice_session_setting_crud,
)

from schemas.base import Page
from schemas.user.practice import (
    PracticeSessionCreate,
    PracticeSessionUpdate,
    PracticeSessionResponse,
    PracticeSessionModelCreate,
    PracticeSessionModelUpdate,
    PracticeSessionModelResponse,
    PracticeResponseCreate,
    PracticeResponseUpdate,
    PracticeResponseResponse,
    PracticeTurnRequest,
    PracticeTurnResponse,
    PracticeSessionSettingResponse,
    PracticeSessionSettingUpdate,
)

from service.user.practice import (
    ensure_my_session,
    ensure_my_session_model,
    ensure_my_response,
    set_primary_model_for_session,
    run_practice_turn_for_session,
)

router = APIRouter()


# =========================================================
# helpers
# =========================================================
def _get_default_generation_params_dict() -> dict:
    base = getattr(config, "PRACTICE_DEFAULT_GENERATION", None)
    if isinstance(base, dict):
        return dict(base)
    return {}


def _ensure_session_settings_row(db: Session, *, session_id: int):
    """
    세션당 settings 1개 보장.
    """
    default_gen = _get_default_generation_params_dict()
    return practice_session_setting_crud.get_or_create_default(
        db,
        session_id=session_id,
        default_generation_params=default_gen,
    )


def _init_default_models_for_session(
    db: Session,
    *,
    session_id: int,
    base_generation_params: dict,
) -> None:
    """
    세션 생성 직후, 튜닝 UI가 바로 뜰 수 있게 기본 모델들을 미리 생성해둠.
    - model_name은 "논리 모델 이름"(= config 키)을 저장
    """
    existing = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if existing:
        return

    practice_models = getattr(config, "PRACTICE_MODELS", {}) or {}
    enabled = [
        (k, v)
        for k, v in practice_models.items()
        if isinstance(v, dict) and v.get("enabled") is True
    ]

    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="no_enabled_practice_models",
        )

    primary_key = None
    for k, v in enabled:
        if v.get("default") is True:
            primary_key = k
            break
    if primary_key is None:
        primary_key = enabled[0][0]

    base_gen = dict(base_generation_params or {})

    for k, _v in enabled:
        data_in = PracticeSessionModelCreate(
            session_id=session_id,
            model_name=k,     # 논리 모델 이름(= config 키)
            is_primary=(k == primary_key),
            generation_params=dict(base_gen),  # 모델별 copy
        )
        practice_session_model_crud.create(db, data_in)


def _ensure_session_models_ready(db: Session, *, session_id: int, base_gen: dict) -> None:
    """
    레거시 세션 대비: 모델 row가 없으면 기본 모델 생성.
    """
    existing = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not existing:
        _init_default_models_for_session(
            db,
            session_id=session_id,
            base_generation_params=base_gen,
        )


def _extract_generation_patch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    PracticeSessionSettingUpdate payload에서 generation_params만 뽑아내서
    None 값은 제거한 "실제 변경분" dict로 만든다.
    """
    gp = payload.get("generation_params")
    if not isinstance(gp, dict):
        return {}
    return {k: v for k, v in gp.items() if v is not None}


# =========================================================
# Practice Sessions
# =========================================================
@router.get(
    "/sessions",
    response_model=Page[PracticeSessionResponse],
    operation_id="list_my_practice_sessions",
    summary="내 세션 불러오기",
)
def list_my_practice_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rows, total = practice_session_crud.list_by_user(
        db,
        user_id=me.user_id,
        page=page,
        size=size,
    )
    items = [PracticeSessionResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/sessions",
    response_model=PracticeSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_session",
    summary="새 채팅(세션): 세션 생성 + settings 생성 + 기본 모델 미리 생성",
)
def create_practice_session(
    data: PracticeSessionCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    class_id = getattr(data, "class_id", None)
    if not class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="class_id_required",
        )

    session = practice_session_crud.create(
        db=db,
        data=data,
        user_id=me.user_id,
    )

    # settings 보장
    setting = _ensure_session_settings_row(db, session_id=session.session_id)

    # 기본 모델들 생성(튜닝 UI 즉시 가능)
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()
    _init_default_models_for_session(
        db,
        session_id=session.session_id,
        base_generation_params=base_gen,
    )

    db.commit()
    return PracticeSessionResponse.model_validate(session)


@router.get(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="get_practice_session",
    summary="세션 채팅목록",
)
def get_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    session = ensure_my_session(db, session_id, me)

    # settings 같이 내려주면 UX 편해짐
    setting = _ensure_session_settings_row(db, session_id=session.session_id)

    resp_rows = practice_response_crud.list_by_session(db, session_id=session.session_id)
    resp_items = [PracticeResponseResponse.model_validate(r) for r in resp_rows]

    return PracticeSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        class_id=session.class_id,
        project_id=session.project_id,
        knowledge_id=getattr(session, "knowledge_id", None),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        notes=getattr(session, "notes", None),
        settings=PracticeSessionSettingResponse.model_validate(setting) if setting else None,
        responses=resp_items,
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="update_practice_session",
    summary="세션 제목/메타 수정",
)
def update_practice_session(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    updated = practice_session_crud.update(db, session_id=session_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return PracticeSessionResponse.model_validate(updated)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_session",
    summary="세션 삭제",
)
def delete_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    practice_session_crud.delete(db, session_id=session_id)
    db.commit()
    return None


# =========================================================
# Practice Session Settings
# =========================================================
@router.get(
    "/sessions/{session_id}/settings",
    response_model=PracticeSessionSettingResponse,
    operation_id="get_practice_session_settings",
    summary="세션 settings 조회",
)
def get_practice_session_settings(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)

    setting = _ensure_session_settings_row(db, session_id=session_id)

    # settings는 있는데 모델이 없을 수도 있으니 보장
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=session_id, base_gen=base_gen)

    db.commit()  # settings/model이 없어서 생성된 경우 반영
    return PracticeSessionSettingResponse.model_validate(setting)


@router.patch(
    "/sessions/{session_id}/settings",
    response_model=PracticeSessionSettingResponse,
    operation_id="update_practice_session_settings",
    summary="세션 settings",
)
def update_practice_session_settings(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)

    # row 보장
    current = _ensure_session_settings_row(db, session_id=session_id)

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return PracticeSessionSettingResponse.model_validate(current)

    # 이번 PATCH에서 "generation_params 변경분"만 뽑음 (없으면 sync 안 함)
    gen_patch = _extract_generation_patch(payload)

    updated = practice_session_setting_crud.update_by_session_id(
        db,
        session_id=session_id,
        data=data,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="settings not found")

    # 레거시 대비: 모델 없으면 만들어두고
    base_gen = getattr(updated, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=session_id, base_gen=base_gen)

    # generation_params가 바뀐 경우에만 동기화 수행
    if gen_patch:
        practice_session_model_crud.bulk_sync_generation_params_by_session(
            db,
            session_id=session_id,
            generation_params=gen_patch,  # "변경분"만 반영
            merge=True,
        )

    db.commit()
    return PracticeSessionSettingResponse.model_validate(updated)


# =========================================================
# Practice Session Models
# =========================================================
@router.get(
    "/sessions/{session_id}/models",
    response_model=List[PracticeSessionModelResponse],
    operation_id="list_practice_session_models",
    summary="해당 세션에 생성된 모델 목록 확인",
)
def list_practice_session_models(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    return [PracticeSessionModelResponse.model_validate(m) for m in models]


@router.post(
    "/sessions/{session_id}/models",
    response_model=PracticeSessionModelResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_session_model",
    summary="세션에 모델 추가",
)
def create_practice_session_model(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionModelCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)

    # 새 모델을 추가할 때 generation_params를 안 주면 settings 값을 복사해서 넣어준다
    setting = _ensure_session_settings_row(db, session_id=session_id)
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()

    incoming_gp = getattr(data, "generation_params", None)

    if incoming_gp is None:
        data_in = data.model_copy(
            update={"session_id": session_id, "generation_params": dict(base_gen)}
        )
    else:
        # base_gen + incoming override
        if hasattr(incoming_gp, "model_dump"):
            gp_dict = incoming_gp.model_dump(exclude_unset=True)
        elif isinstance(incoming_gp, dict):
            gp_dict = dict(incoming_gp)
        else:
            gp_dict = {}

        merged = dict(base_gen)
        merged.update(gp_dict)
        data_in = data.model_copy(
            update={"session_id": session_id, "generation_params": merged}
        )

    model = practice_session_model_crud.create(db, data_in)
    db.commit()
    return PracticeSessionModelResponse.model_validate(model)


@router.patch(
    "/models/{session_model_id}",
    response_model=PracticeSessionModelResponse,
    operation_id="user_update_practice_session_model",
    summary="모델별 LLM 파라미터 튜닝/primary 변경",
)
def update_practice_session_model(
    session_model_id: int = Path(..., ge=1),
    data: PracticeSessionModelUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    model, _session = ensure_my_session_model(db, session_model_id, me)

    if data.is_primary is True:
        target = set_primary_model_for_session(
            db,
            me=me,
            session_id=model.session_id,
            target_session_model_id=session_model_id,
        )
        db.commit()
        return PracticeSessionModelResponse.model_validate(target)

    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("is_primary", None)

    if update_data:
        model = practice_session_model_crud.update(
            db,
            session_model_id=session_model_id,
            data=update_data,
        )
        db.commit()

    return PracticeSessionModelResponse.model_validate(model)


@router.delete(
    "/models/{session_model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_session_model",
)
def delete_practice_session_model(
    session_model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)
    practice_session_model_crud.delete(db, session_model_id=session_model_id)
    db.commit()
    return None


# =========================================================
# Chat / Turns
# =========================================================
@router.post(
    "/sessions/run",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_new_session",
    summary="QUICK 입력: 새 세션 생성 + 첫 턴 실행",
)
def run_practice_turn_new_session_endpoint(
    class_id: int = Query(..., ge=1, description="이 연습 세션이 속한 Class ID (partner.classes.id)"),
    project_id: int | None = Query(
        None,
        ge=1,
        description="새 세션 생성 시 연결할 Project ID (user.projects.project_id)",
    ),
    body: PracticeTurnRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    turn_result = run_practice_turn_for_session(
        db=db,
        me=me,
        session_id=0,  # 내부적으로만 사용
        class_id=class_id,
        project_id=project_id,
        body=body,
    )

    # 생성된 세션에 settings 보장
    _ensure_session_settings_row(db, session_id=turn_result.session_id)

    db.commit()
    return turn_result


@router.post(
    "/sessions/{session_id}/chat",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_existing_session",
    summary="기존 세션에서 실습 턴 실행",
)
def run_practice_turn_endpoint(
    session_id: int = Path(..., ge=1, description="1 이상: 해당 세션에서 이어서 대화"),
    body: PracticeTurnRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    session = ensure_my_session(db, session_id, me)

    if session.class_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_has_no_class_id",
        )

    # settings + 모델 row 보장(레거시 대비)
    setting = _ensure_session_settings_row(db, session_id=session.session_id)
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=session.session_id, base_gen=base_gen)

    turn_result = run_practice_turn_for_session(
        db=db,
        me=me,
        session_id=session_id,
        class_id=session.class_id,
        project_id=session.project_id,
        body=body,
    )
    db.commit()
    return turn_result


# =========================================================
# Practice Responses
# =========================================================
@router.get(
    "/models/{session_model_id}/responses",
    response_model=List[PracticeResponseResponse],
    operation_id="list_practice_responses_by_model",
)
def list_practice_responses_by_model(
    session_model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)
    responses = practice_response_crud.list_by_session_model(
        db,
        session_model_id=session_model_id,
    )
    return [PracticeResponseResponse.model_validate(r) for r in responses]


@router.post(
    "/models/{session_model_id}/responses",
    response_model=PracticeResponseResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_response",
    summary="실습 응답 생성(수동)",
)
def create_practice_response(
    session_model_id: int = Path(..., ge=1),
    data: PracticeResponseCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)

    data_in = data.model_copy(
        update={
            "session_model_id": session_model_id,
            "session_id": _session.session_id,
            "model_name": _model.model_name,
        }
    )
    resp = practice_response_crud.create(db, data_in)
    db.commit()
    return PracticeResponseResponse.model_validate(resp)


@router.get(
    "/responses/{response_id}",
    response_model=PracticeResponseResponse,
    operation_id="get_practice_response",
)
def get_practice_response(
    response_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    resp, _model, _session = ensure_my_response(db, response_id, me)
    return PracticeResponseResponse.model_validate(resp)


@router.patch(
    "/responses/{response_id}",
    response_model=PracticeResponseResponse,
    operation_id="update_practice_response",
)
def update_practice_response(
    response_id: int = Path(..., ge=1),
    data: PracticeResponseUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _resp, _model, _session = ensure_my_response(db, response_id, me)
    updated = practice_response_crud.update(db, response_id=response_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response not found")
    return PracticeResponseResponse.model_validate(updated)


@router.delete(
    "/responses/{response_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_response",
)
def delete_practice_response(
    response_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _resp, _model, _session = ensure_my_response(db, response_id, me)
    practice_response_crud.delete(db, response_id=response_id)
    db.commit()
    return None
