# service/user/practice/models_sync.py
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core import config

from crud.partner import classes as classes_crud
from crud.user.practice import practice_session_model_crud

from models.partner.catalog import ModelCatalog
from models.user.account import AppUser
from models.user.practice import PracticeSession, PracticeSessionModel

from schemas.user.practice import PracticeSessionModelCreate

from service.user.practice.ids import has_any_response
from service.user.practice.params import normalize_generation_params_dict


# =========================================
# runtime config helpers
# =========================================
def is_enabled_runtime_model(model_key: str) -> bool:
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    conf = practice_models.get(model_key)
    if not isinstance(conf, dict):
        return False
    return conf.get("enabled", True) is True


def resolve_runtime_model(model_key: str) -> tuple[str | None, str, dict[str, Any]]:
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    conf = practice_models.get(model_key)

    if not isinstance(conf, dict):
        raise HTTPException(status_code=400, detail=f"model_not_configured_in_runtime_config: {model_key}")

    if conf.get("enabled", True) is False:
        raise HTTPException(status_code=400, detail=f"model_not_enabled_in_runtime_config: {model_key}")

    provider = conf.get("provider")
    real_model = conf.get("model_name", model_key)

    defaults: dict[str, Any] = {}
    if "temperature" in conf:
        defaults["temperature"] = conf.get("temperature")
    if "top_p" in conf:
        defaults["top_p"] = conf.get("top_p")

    mt = conf.get("max_output_tokens") or conf.get("max_completion_tokens") or conf.get("max_tokens")
    if isinstance(mt, int) and mt > 0:
        defaults["max_completion_tokens"] = mt
        defaults["max_tokens"] = mt

    return provider, real_model, defaults


def init_models_for_session_from_class(
    db: Session,
    *,
    me: AppUser,
    session: PracticeSession,
    class_id: int,
    requested_model_names: list[str] | None = None,
    base_generation_params: dict[str, Any] | None = None,
    generation_overrides: dict[str, dict[str, Any]] | None = None,
    sync_existing: bool = True,
) -> list[PracticeSessionModel]:
    class_obj = classes_crud.get_class(db, class_id=class_id)
    if not class_obj or class_obj.status != "active":
        raise HTTPException(status_code=400, detail="유효하지 않은 class_id 입니다.")

    model_catalog_ids: list[int] = []
    if class_obj.primary_model_id:
        model_catalog_ids.append(class_obj.primary_model_id)
    if class_obj.allowed_model_ids:
        for mid in class_obj.allowed_model_ids:
            if mid not in model_catalog_ids:
                model_catalog_ids.append(mid)

    if not model_catalog_ids:
        raise HTTPException(status_code=400, detail="이 class 에 설정된 모델이 없습니다.")

    allowed_names: list[str] = []
    seen: set[str] = set()
    for mc_id in model_catalog_ids:
        catalog = db.get(ModelCatalog, mc_id)
        if not catalog:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 model_catalog id: {mc_id}")
        name = getattr(catalog, "logical_name", None) or catalog.model_name
        if name not in seen:
            seen.add(name)
            allowed_names.append(name)

    for name in allowed_names:
        if not is_enabled_runtime_model(name):
            raise HTTPException(status_code=400, detail=f"model_not_enabled_in_runtime_config: {name}")

    desired_names = allowed_names
    if requested_model_names:
        s = set(requested_model_names)
        desired_names = [n for n in allowed_names if n in s]
        if not desired_names:
            raise HTTPException(status_code=400, detail="requested model_names not configured for this class")

    base_gen = normalize_generation_params_dict(dict(base_generation_params or {}))
    overrides = generation_overrides or {}

    existing = practice_session_model_crud.list_by_session(db, session_id=session.session_id)

    if existing and sync_existing:
        has_resp = has_any_response(db, session_id=session.session_id)
        desired_set = set(desired_names)

        if not has_resp:
            for m in existing:
                if m.model_name not in desired_set:
                    practice_session_model_crud.delete(db, session_model_id=m.session_model_id)

        existing_after = practice_session_model_crud.list_by_session(db, session_id=session.session_id)
        existing_names_after = {m.model_name for m in existing_after}

        for name in desired_names:
            if name in existing_names_after:
                continue

            gp = dict(base_gen)
            ov = overrides.get(name)
            if isinstance(ov, dict):
                gp.update(ov)
            gp = normalize_generation_params_dict(gp)

            practice_session_model_crud.create(
                db,
                PracticeSessionModelCreate(
                    session_id=session.session_id,
                    model_name=name,
                    is_primary=False,
                    generation_params=gp,
                ),
            )

        final_models = practice_session_model_crud.list_by_session(db, session_id=session.session_id)

        primary_name = desired_names[0] if desired_names else None
        for m in final_models:
            m.is_primary = (m.model_name == primary_name)

        db.flush()

        if requested_model_names:
            s = set(requested_model_names)
            picked = [m for m in final_models if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not found in this session")
            return picked

        return final_models

    if existing:
        if requested_model_names:
            s = set(requested_model_names)
            picked = [m for m in existing if m.model_name in s]
            if not picked:
                raise HTTPException(status_code=400, detail="requested model_names not found in this session")
            return picked
        return list(existing)

    created: list[PracticeSessionModel] = []
    for idx, name in enumerate(desired_names):
        gp = dict(base_gen)
        ov = overrides.get(name)
        if isinstance(ov, dict):
            gp.update(ov)
        gp = normalize_generation_params_dict(gp)

        m = practice_session_model_crud.create(
            db,
            PracticeSessionModelCreate(
                session_id=session.session_id,
                model_name=name,
                is_primary=(idx == 0),
                generation_params=gp,
            ),
        )
        created.append(m)

    db.flush()
    return created
