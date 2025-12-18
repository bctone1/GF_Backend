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
    init_models_for_session_from_class,
)

router = APIRouter()


# =========================================================
# helpers
# =========================================================
def _normalize_generation_params_dict(v: Any) -> dict[str, Any]:
    """
    max_completion_tokens 기준으로 키 혼용을 정규화.
    (서비스 레이어와 동일한 정규화 규칙을 엔드포인트에서도 적용)
    """
    if not isinstance(v, dict):
        return {}

    out = dict(v)
    mct = out.get("max_completion_tokens")
    mt = out.get("max_tokens")
    mot = out.get("max_output_tokens")

    if mct is None and isinstance(mot, int) and mot > 0:
        out["max_completion_tokens"] = mot
        out["max_tokens"] = mot
        return out

    if mct is None and isinstance(mt, int) and mt > 0:
        out["max_completion_tokens"] = mt
        out["max_tokens"] = mt
        return out

    if mt is None and isinstance(mct, int) and mct > 0:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct
        return out

    if isinstance(mct, int) and mct > 0 and isinstance(mt, int) and mt > 0 and mct != mt:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct

    return out


def _coerce_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_unset=True)
    return dict(value) if isinstance(value, dict) else {}


def _get_default_generation_params_dict() -> dict:
    base = getattr(config, "PRACTICE_DEFAULT_GENERATION", None)
    if isinstance(base, dict):
        return _normalize_generation_params_dict(dict(base))
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


def _sync_session_models_with_class(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
) -> None:
    """
    모델 소스를 class/ModelCatalog로 단일화.
    - 기존 config 기반 세션도 정리(sync_existing=True)
    - 기존 primary 선택이 유효하면 유지(동기화가 primary를 덮어쓰지 않도록)
    """
    session = ensure_my_session(db, session_id, me)

    if session.class_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_has_no_class_id")

    # 동기화 전 primary 기억(이름 기준)
    before = list(practice_session_model_crud.list_by_session(db, session_id=session.session_id))
    prev_primary_name = next((m.model_name for m in before if getattr(m, "is_primary", False)), None)

    setting = _ensure_session_settings_row(db, session_id=session.session_id)
    base_gen = _normalize_generation_params_dict(getattr(setting, "generation_params", None) or _get_default_generation_params_dict())

    init_models_for_session_from_class(
        db,
        me=me,
        session=session,
        class_id=session.class_id,
        requested_model_names=None,
        base_generation_params=base_gen,
        generation_overrides=None,
        sync_existing=True,
    )

    # 동기화 후에도 이전 primary가 남아있으면 복구
    if prev_primary_name:
        after = list(practice_session_model_crud.list_by_session(db, session_id=session.session_id))
        names = [m.model_name for m in after]
        if prev_primary_name in names:
            for m in after:
                m.is_primary = (m.model_name == prev_primary_name)
            db.flush()


def _extract_generation_patch(payload: Dict[str, Any]) -> Dict[str, Any]:
    gp = payload.get("generation_params")
    if not isinstance(gp, dict):
        return {}
    return _normalize_generation_params_dict({k: v for k, v in gp.items() if v is not None})


def _validate_my_few_shot_example_ids(
    db: Session,
    *,
    me: AppUser,
    example_ids: list[int],
) -> None:
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
    summary="새 채팅(세션): 세션 생성 + settings 생성 + class 기준 모델 생성",
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

    _ = _ensure_session_settings_row(db, session_id=session.session_id)
    _sync_session_models_with_class(db, me=me, session_id=session.session_id)

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

    # 구 세션 정리 목적(필요 없으면 제거 가능)
    if session.class_id is not None:
        _sync_session_models_with_class(db, me=me, session_id=session.session_id)

    setting = _get_settings_with_links(db, session_id=session.session_id)

    resp_rows = practice_response_crud.list_by_session(db, session_id=session.session_id)
    resp_items = [PracticeResponseResponse.model_validate(r) for r in resp_rows]

    db.commit()
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

    _sync_session_models_with_class(db, me=me, session_id=session_id)
    setting = _get_settings_with_links(db, session_id=session_id)

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
    _ = ensure_my_session(db, session_id, me)
    _ = _ensure_session_settings_row(db, session_id=session_id)

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        _sync_session_models_with_class(db, me=me, session_id=session_id)
        setting = _get_settings_with_links(db, session_id=session_id)
        db.commit()
        return PracticeSessionSettingResponse.model_validate(setting)

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

    _sync_session_models_with_class(db, me=me, session_id=session_id)

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
    session = ensure_my_session(db, session_id, me)
    if session.class_id is not None:
        _sync_session_models_with_class(db, me=me, session_id=session_id)

    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    db.commit()
    return [PracticeSessionModelResponse.model_validate(m) for m in models]


@router.post(
    "/sessions/{session_id}/models",
    response_model=PracticeSessionModelResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_session_model",
    summary="세션에 모델 추가(실제 소스는 class 기준; 허용 모델만 보장 + 옵션 적용)",
)
def create_practice_session_model(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionModelCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    class/ModelCatalog 기준으로만 모델이 존재하도록 유지.
    - 요청한 model_name이 class 허용 모델이면: 세션에 존재하도록 보장(sync) 후 해당 row 반환
    - 요청에 generation_params가 있으면: 해당 모델에 merge 적용
    - is_primary=True면 primary 변경
    """
    session = ensure_my_session(db, session_id, me)
    if session.class_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_has_no_class_id")

    _ensure_session_settings_row(db, session_id=session_id)

    # class 기준으로 모델 목록을 먼저 정리/보장
    _sync_session_models_with_class(db, me=me, session_id=session_id)

    models = list(practice_session_model_crud.list_by_session(db, session_id=session_id))
    target = next((m for m in models if m.model_name == data.model_name), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="model_not_allowed_for_class")

    # generation_params: merge
    incoming_gp = _normalize_generation_params_dict(_coerce_dict(getattr(data, "generation_params", None)))
    if incoming_gp:
        current_gp = _normalize_generation_params_dict(getattr(target, "generation_params", None) or {})
        merged = dict(current_gp)
        merged.update(incoming_gp)
        practice_session_model_crud.update(
            db,
            session_model_id=target.session_model_id,
            data={"generation_params": merged},
        )

    # primary 변경
    if getattr(data, "is_primary", None) is True:
        target = set_primary_model_for_session(
            db,
            me=me,
            session_id=session_id,
            target_session_model_id=target.session_model_id,
        )

    db.commit()
    # 최신 row 재조회(merge/primary 반영)
    refreshed = practice_session_model_crud.get(db, target.session_model_id)
    return PracticeSessionModelResponse.model_validate(refreshed or target)


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

    # generation_params는 merge로 처리(덮어쓰기 방지)
    if "generation_params" in update_data:
        patch = _normalize_generation_params_dict(_coerce_dict(update_data.get("generation_params")))
        current = _normalize_generation_params_dict(getattr(model, "generation_params", None) or {})
        merged = dict(current)
        merged.update(patch)
        update_data["generation_params"] = merged

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
