# service/user/practice/orchestrator.py
from __future__ import annotations

from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.practice import PracticeSession, PracticeSessionSetting, PracticeSessionModel

from schemas.user.practice import (
    PracticeSessionCreate,
    PracticeTurnRequestNewSession,
    PracticeTurnRequestExistingSession,
    PracticeTurnResponse,
)

from crud.user.practice import (
    practice_session_crud,
    practice_session_setting_crud,
    practice_session_model_crud,
)

from service.user.practice.ownership import ensure_my_session
from service.user.practice.params import get_default_generation_params, normalize_generation_params_dict
from service.user.practice.ids import coerce_int_list, get_session_knowledge_ids
from service.user.practice.models_sync import init_models_for_session_from_class
from service.user.practice.turn_runner import run_practice_turn


# =========================================
# 세션 settings 보장(세션당 1개)
# - A안(JSONB): default_few_shot_example_ids는 settings.few_shot_example_ids(JSONB)에 들어가는 값
# =========================================
def ensure_session_settings(
    db: Session,
    *,
    session_id: int,
    default_few_shot_example_ids: Optional[list[int]] = None,
) -> PracticeSessionSetting:
    """
    - practice_session_settings는 세션당 1개(uselist=False) 전제
    - 없으면 default_generation_params로 생성
    """
    default_gen = get_default_generation_params()
    fs_ids = coerce_int_list(default_few_shot_example_ids)
    return practice_session_setting_crud.get_or_create_default(
        db,
        session_id=session_id,
        default_generation_params=default_gen,
        default_few_shot_example_ids=fs_ids if fs_ids else None,
    )


# =========================================
# existing session에서 실행할 모델 선택
# =========================================
def _select_models_for_existing_session(
    db: Session,
    *,
    session: PracticeSession,
    body: PracticeTurnRequestExistingSession,
    class_id: int | None = None,
) -> List[PracticeSessionModel]:
    """
    - body.model_names가 있으면 해당 모델만 선택
    - 없으면 세션에 붙어있는 전체 모델 사용
    """
    if session.class_id is None:
        raise HTTPException(status_code=400, detail="session has no class_id")

    if class_id is not None and session.class_id != class_id:
        raise HTTPException(status_code=400, detail="class_id does not match this session")

    all_models = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
    if not all_models:
        raise HTTPException(status_code=400, detail="no models configured for this session")

    if body.model_names:
        s = set(body.model_names)
        picked = [m for m in all_models if m.model_name in s]
        if not picked:
            raise HTTPException(status_code=400, detail="requested model_names not found in this session")
        return picked

    return list(all_models)


# =========================================
# 엔드포인트용 진입점: new/existing 분기 + 준비
# =========================================
def prepare_practice_turn_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    class_id: int | None,
    body: PracticeTurnRequestNewSession | PracticeTurnRequestExistingSession,
) -> tuple[PracticeSession, PracticeSessionSetting, List[PracticeSessionModel], List[int]]:
    if session_id == 0:
        if class_id is None:
            raise HTTPException(status_code=400, detail="class_id_required")

        if not isinstance(body, PracticeTurnRequestNewSession):
            raise HTTPException(status_code=400, detail="invalid_body_for_new_session")

        requested_project_id = body.project_id
        requested_knowledge_ids = coerce_int_list(body.knowledge_ids)

        session = practice_session_crud.create(
            db,
            data=PracticeSessionCreate(
                class_id=class_id,
                project_id=requested_project_id,
                knowledge_ids=requested_knowledge_ids,
                prompt_ids=coerce_int_list(getattr(body, "prompt_ids", None)),
                title=None,
                notes=None,
            ),
            user_id=me.user_id,
        )

        # A안(JSONB): 세션 생성 시 선택된 few-shot ids를 settings 기본값으로 주입
        requested_few_shot_example_ids = coerce_int_list(getattr(body, "few_shot_example_ids", None))
        settings = ensure_session_settings(
            db,
            session_id=session.session_id,
            default_few_shot_example_ids=requested_few_shot_example_ids if requested_few_shot_example_ids else None,
        )

        base_gen = normalize_generation_params_dict(
            getattr(settings, "generation_params", None) or get_default_generation_params()
        )

        models = init_models_for_session_from_class(
            db,
            me=me,
            session=session,
            class_id=class_id,
            requested_model_names=None,
            base_generation_params=base_gen,
            generation_overrides=None,
            sync_existing=True,
        )

        db.flush()
        db.commit()

        if body.model_names:
            s = set(body.model_names)
            picked = [m for m in models if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not configured for this class")
            models = picked
            if not any(m.is_primary for m in models):
                models[0].is_primary = True

        ctx_knowledge_ids = get_session_knowledge_ids(session)

    else:
        if not isinstance(body, PracticeTurnRequestExistingSession):
            raise HTTPException(status_code=400, detail="invalid_body_for_existing_session")

        session = ensure_my_session(db, session_id, me)
        settings = ensure_session_settings(db, session_id=session.session_id)

        if session.class_id is None:
            raise HTTPException(status_code=400, detail="session has no class_id")

        base_gen = normalize_generation_params_dict(
            getattr(settings, "generation_params", None) or get_default_generation_params()
        )

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

        db.flush()
        db.commit()

        models = _select_models_for_existing_session(
            db,
            session=session,
            body=body,
            class_id=class_id,
        )

        ctx_knowledge_ids = get_session_knowledge_ids(session)

    return session, settings, models, ctx_knowledge_ids


def run_practice_turn_for_session(
    db: Session,
    *,
    me: AppUser,
    session_id: int,
    class_id: int | None,
    body: PracticeTurnRequestNewSession | PracticeTurnRequestExistingSession,
    project_id: Optional[int] = None,
    generate_title: bool = True,
) -> PracticeTurnResponse:
    """
    - session_id == 0  : 새 세션 생성 + 첫 턴
    - session_id > 0   : 기존 세션 턴

    공통:
    - body의 per-turn override 값들(prompt/style/generation)은 run_practice_turn에 그대로 전달(세션 저장값은 유지).
    """
    # ---------------------------------
    # per-turn overrides (body에 있으면 전달)
    # ---------------------------------
    requested_prompt_ids: Optional[List[int]] = getattr(body, "prompt_ids", None)
    requested_style_preset: Optional[str] = getattr(body, "style_preset", None)
    requested_style_params: Optional[Dict[str, Any]] = getattr(body, "style_params", None)

    # GenerationParams(피딕틱 모델) -> dict로 통일
    rgp = getattr(body, "generation_params", None)
    if rgp is not None and hasattr(rgp, "model_dump"):
        requested_generation_params: Optional[Dict[str, Any]] = rgp.model_dump(exclude_unset=True)
    elif isinstance(rgp, dict):
        requested_generation_params = rgp
    else:
        requested_generation_params = None

    session, settings, models, ctx_knowledge_ids = prepare_practice_turn_for_session(
        db=db,
        me=me,
        session_id=session_id,
        class_id=class_id,
        body=body,
    )

    if project_id is not None and session.project_id is not None and session.project_id != project_id:
        raise HTTPException(status_code=400, detail="요청한 project_id와 세션의 project_id가 일치하지 않습니다.")

    # -----------------------------
    # 공통: 턴 실행 (per-turn override 전달)
    # -----------------------------
    return run_practice_turn(
        db=db,
        session=session,
        settings=settings,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
        knowledge_ids=ctx_knowledge_ids,
        generate_title=generate_title,
        requested_prompt_ids=requested_prompt_ids,
        requested_generation_params=requested_generation_params,
        requested_style_preset=requested_style_preset,
        requested_style_params=requested_style_params,
    )
