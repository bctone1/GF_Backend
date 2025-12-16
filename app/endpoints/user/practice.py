# app/endpoints/user/practice.py
from __future__ import annotations

from typing import List, Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    Body,
)
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from core.deps import get_db, get_current_user
from core import config
from models.user.account import AppUser
from models.user.practice import (
    PracticeSessionSetting,
    PracticeSessionSettingFewShot,
    UserFewShotExample,
)

from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    practice_session_setting_crud,
    user_few_shot_example_crud,
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
    UserFewShotExampleCreate,
    UserFewShotExampleUpdate,
    UserFewShotExampleResponse,
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


def _ensure_session_settings_row(db: Session, *, session_id: int) -> PracticeSessionSetting:
    default_gen = _get_default_generation_params_dict()
    return practice_session_setting_crud.get_or_create_default(
        db,
        session_id=session_id,
        default_generation_params=default_gen,
    )


def _get_settings_with_links(db: Session, *, session_id: int) -> PracticeSessionSetting:
    """
    settings + few_shot_links(+example)까지 같이 로드해서 N+1 완화
    """
    stmt = (
        select(PracticeSessionSetting)
        .where(PracticeSessionSetting.session_id == session_id)
        .options(
            selectinload(PracticeSessionSetting.few_shot_links).selectinload(
                PracticeSessionSettingFewShot.example
            )
        )
    )
    row = db.scalar(stmt)
    if row:
        return row
    return _ensure_session_settings_row(db, session_id=session_id)


def _init_default_models_for_session(
    db: Session,
    *,
    session_id: int,
    base_generation_params: dict,
) -> None:
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
            model_name=k,
            is_primary=(k == primary_key),
            generation_params=dict(base_gen),
        )
        practice_session_model_crud.create(db, data_in)


def _ensure_session_models_ready(db: Session, *, session_id: int, base_gen: dict) -> None:
    existing = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if not existing:
        _init_default_models_for_session(
            db,
            session_id=session_id,
            base_generation_params=base_gen,
        )


def _extract_generation_patch(payload: Dict[str, Any]) -> Dict[str, Any]:
    gp = payload.get("generation_params")
    if not isinstance(gp, dict):
        return {}
    return {k: v for k, v in gp.items() if v is not None}


def _validate_my_few_shot_example_ids(
    db: Session,
    *,
    me: AppUser,
    example_ids: list[int],
) -> None:
    # 중복 방지(UniqueConstraint 걸려있어서 DB에서 터지기 전에 400으로)
    if len(example_ids) != len(set(example_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duplicate_few_shot_example_ids",
        )
    if not example_ids:
        return

    stmt = (
        select(func.count(UserFewShotExample.example_id))
        .where(UserFewShotExample.user_id == me.user_id)
        .where(UserFewShotExample.is_active.is_(True))
        .where(UserFewShotExample.example_id.in_(example_ids))
    )
    cnt = db.scalar(stmt) or 0
    if cnt != len(example_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_few_shot_example_ids",
        )


def _ensure_my_few_shot_example(db: Session, *, example_id: int, me: AppUser) -> UserFewShotExample:
    obj = user_few_shot_example_crud.get(db, example_id)
    if not obj or obj.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="few_shot_example_not_found")
    return obj


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

    setting = _ensure_session_settings_row(db, session_id=session.session_id)

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

    setting = _get_settings_with_links(db, session_id=session.session_id)

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

    setting = _get_settings_with_links(db, session_id=session_id)

    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=session_id, base_gen=base_gen)

    db.commit()
    return PracticeSessionSettingResponse.model_validate(setting)


@router.patch(
    "/sessions/{session_id}/settings",
    response_model=PracticeSessionSettingResponse,
    operation_id="update_practice_session_settings",
    summary="세션 settings 수정(style/generation/few-shot 선택)",
)
def update_practice_session_settings(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
     style : `accurate` | `balanced` | `creative` |`custom`
     Length : `short` | `normal` | `long`| `custom`
    """
    _ = ensure_my_session(db, session_id, me)

    current = _ensure_session_settings_row(db, session_id=session_id)

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        setting = _get_settings_with_links(db, session_id=session_id)
        return PracticeSessionSettingResponse.model_validate(setting)

    # few-shot 선택 ids 검증(내 것 + 활성)
    if "few_shot_example_ids" in payload:
        ids = payload.get("few_shot_example_ids") or []
        if not isinstance(ids, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="few_shot_example_ids_must_be_list")
        _validate_my_few_shot_example_ids(db, me=me, example_ids=[int(x) for x in ids])

    gen_patch = _extract_generation_patch(payload)

    updated = practice_session_setting_crud.update_by_session_id(
        db,
        session_id=session_id,
        data=data,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="settings not found")

    base_gen = getattr(updated, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=session_id, base_gen=base_gen)

    if gen_patch:
        practice_session_model_crud.bulk_sync_generation_params_by_session(
            db,
            session_id=session_id,
            generation_params=gen_patch,
            merge=True,
        )

    db.commit()
    setting = _get_settings_with_links(db, session_id=session_id)
    return PracticeSessionSettingResponse.model_validate(setting)


# =========================================================
# Few-shot Example Library (개인)
# =========================================================
@router.get(
    "/few-shot-examples",
    response_model=Page[UserFewShotExampleResponse],
    operation_id="list_my_few_shot_examples",
    summary="내 few-shot 예시 목록",
)
def list_my_few_shot_examples(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rows, total = user_few_shot_example_crud.list_by_user(
        db,
        user_id=me.user_id,
        page=page,
        size=size,
        is_active=is_active,
    )
    items = [UserFewShotExampleResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/few-shot-examples",
    response_model=UserFewShotExampleResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_my_few_shot_example",
    summary="내 few-shot 예시 생성",
)
def create_my_few_shot_example(
    data: UserFewShotExampleCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    obj = user_few_shot_example_crud.create(db, user_id=me.user_id, data=data)
    db.commit()
    return UserFewShotExampleResponse.model_validate(obj)


@router.get(
    "/few-shot-examples/{example_id}",
    response_model=UserFewShotExampleResponse,
    operation_id="get_my_few_shot_example",
    summary="내 few-shot 예시 단건",
)
def get_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    obj = _ensure_my_few_shot_example(db, example_id=example_id, me=me)
    return UserFewShotExampleResponse.model_validate(obj)


@router.patch(
    "/few-shot-examples/{example_id}",
    response_model=UserFewShotExampleResponse,
    operation_id="update_my_few_shot_example",
    summary="내 few-shot 예시 수정",
)
def update_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    data: UserFewShotExampleUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_few_shot_example(db, example_id=example_id, me=me)
    obj = user_few_shot_example_crud.update(db, example_id=example_id, data=data)
    db.commit()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="few_shot_example_not_found")
    return UserFewShotExampleResponse.model_validate(obj)


@router.delete(
    "/few-shot-examples/{example_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_my_few_shot_example",
    summary="내 few-shot 예시 삭제",
)
def delete_my_few_shot_example(
    example_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_few_shot_example(db, example_id=example_id, me=me)
    user_few_shot_example_crud.delete(db, example_id=example_id)
    db.commit()
    return None


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

    setting = _ensure_session_settings_row(db, session_id=session_id)
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()

    incoming_gp = getattr(data, "generation_params", None)

    if incoming_gp is None:
        data_in = data.model_copy(update={"session_id": session_id, "generation_params": dict(base_gen)})
    else:
        if hasattr(incoming_gp, "model_dump"):
            gp_dict = incoming_gp.model_dump(exclude_unset=True)
        elif isinstance(incoming_gp, dict):
            gp_dict = dict(incoming_gp)
        else:
            gp_dict = {}

        merged = dict(base_gen)
        merged.update(gp_dict)
        data_in = data.model_copy(update={"session_id": session_id, "generation_params": merged})

    model = practice_session_model_crud.create(db, data_in)
    db.commit()
    return PracticeSessionModelResponse.model_validate(model)


@router.patch(
    "/models/{session_model_id}",
    response_model=PracticeSessionModelResponse,
    operation_id="user_update_practice_session_model",
    summary="LLM 파라미터 튜닝/primary 변경",
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
    project_id: int | None = Query(None, ge=1, description="새 세션 생성 시 연결할 Project ID (user.projects.project_id)"),
    body: PracticeTurnRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    turn_result = run_practice_turn_for_session(
        db=db,
        me=me,
        session_id=0,
        class_id=class_id,
        project_id=project_id,
        body=body,
    )

    setting = _ensure_session_settings_row(db, session_id=turn_result.session_id)
    base_gen = getattr(setting, "generation_params", None) or _get_default_generation_params_dict()
    _ensure_session_models_ready(db, session_id=turn_result.session_id, base_gen=base_gen)

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
    responses = practice_response_crud.list_by_session_model(db, session_model_id=session_model_id)
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
