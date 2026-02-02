# crud/user/practice.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Any, Mapping, Union

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError

from core import config
from models.user.practice import (
    PracticeSession,
    PracticeSessionSetting,
    PracticeSessionModel,
    PracticeResponse,
)

from schemas.user.practice import (
    PracticeSessionCreate,
    PracticeSessionUpdate,
    PracticeSessionSettingUpdate,
    PracticeSessionModelCreate,
    PracticeSessionModelUpdate,
    PracticeResponseCreate,
    PracticeResponseUpdate,
)


# =========================================================
# internal helpers
# =========================================================
def _dump_pydantic(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_unset=True)
    return value


def _coerce_dict(value: Any) -> dict[str, Any]:
    v = _dump_pydantic(value)
    return dict(v) if isinstance(v, dict) else {}


def _coerce_int_list(value: Any) -> list[int]:
    """
    JSONB(list[int]) 방어용
    - None/비정상 타입이면 []
    - int 캐스팅 실패는 스킵
    - 0/음수 제거
    - (주의) 중복 제거는 여기서 하지 않음: 호출부(스키마 normalize)에서 제거하는 전제
    """
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for x in value:
        try:
            ix = int(x)
        except (TypeError, ValueError):
            continue
        if ix > 0:
            out.append(ix)
    return out


def _normalize_generation_params_dict(v: dict[str, Any]) -> dict[str, Any]:
    """
    DB에는 max_completion_tokens 기준으로 맞추되,
    기존 코드 호환을 위해 max_tokens도 함께 동일 값으로 유지.
    """
    if not isinstance(v, dict):
        return {}

    out = dict(v)

    mct = out.get("max_completion_tokens")
    mt = out.get("max_tokens")

    if mct is None and mt is not None:
        out["max_completion_tokens"] = mt
        out["max_tokens"] = mt
        return out

    if mt is None and mct is not None:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct
        return out

    if mct is not None and mt is not None and mct != mt:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct

    return out


# =========================================================
# PracticeSession CRUD
# =========================================================
class PracticeSessionCRUD:
    def create(
        self,
        db: Session,
        *,
        data: PracticeSessionCreate,
        user_id: int,
    ) -> PracticeSession:
        knowledge_ids = _coerce_int_list(getattr(data, "knowledge_ids", None))
        prompt_ids = _coerce_int_list(getattr(data, "prompt_ids", None))

        obj = PracticeSession(
            user_id=user_id,
            class_id=data.class_id,
            project_id=data.project_id,
            knowledge_ids=knowledge_ids,
            prompt_ids=prompt_ids,
            title=data.title,
            notes=data.notes,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, session_id: int) -> Optional[PracticeSession]:
        stmt = select(PracticeSession).where(PracticeSession.session_id == session_id)
        return db.scalar(stmt)

    def list_by_user(
        self,
        db: Session,
        user_id: int,
        *,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[Sequence[PracticeSession], int]:
        base = select(PracticeSession).where(PracticeSession.user_id == user_id)
        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

        stmt = (
            base.order_by(PracticeSession.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = db.scalars(stmt).all()
        return rows, total

    def update(
        self,
        db: Session,
        *,
        session_id: int,
        data: PracticeSessionUpdate,
    ) -> Optional[PracticeSession]:
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        if not values:
            return self.get(db, session_id)

        if "knowledge_ids" in values:
            values["knowledge_ids"] = _coerce_int_list(values.get("knowledge_ids"))
        if "prompt_ids" in values:
            values["prompt_ids"] = _coerce_int_list(values.get("prompt_ids"))

        stmt = (
            update(PracticeSession)
            .where(PracticeSession.session_id == session_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        return self.get(db, session_id)

    def delete(self, db: Session, *, session_id: int) -> None:
        stmt = delete(PracticeSession).where(PracticeSession.session_id == session_id)
        db.execute(stmt)
        db.flush()


practice_session_crud = PracticeSessionCRUD()


# =========================================================
# PracticeSessionSetting CRUD
#   - 매핑 테이블 제거
#   - few_shot_example_ids(JSONB array)로 단일화
# =========================================================
class PracticeSessionSettingCRUD:
    def get_by_session(self, db: Session, *, session_id: int) -> Optional[PracticeSessionSetting]:
        stmt = select(PracticeSessionSetting).where(PracticeSessionSetting.session_id == session_id)
        return db.scalar(stmt)

    def get_or_create_default(
        self,
        db: Session,
        *,
        session_id: int,
        default_generation_params: Optional[dict[str, Any]] = None,
        default_style_params: Optional[dict[str, Any]] = None,
        style_preset: Optional[str] = None,
        default_few_shot_example_ids: Optional[list[int]] = None,
        default_prompt_snapshot: Optional[dict[str, Any]] = None,
    ) -> PracticeSessionSetting:
        row = self.get_by_session(db, session_id=session_id)
        if row:
            return row

        gen = default_generation_params
        if not isinstance(gen, dict):
            gen = getattr(config, "PRACTICE_DEFAULT_GENERATION", {}) or {}
        gen = _normalize_generation_params_dict(dict(gen))

        style = default_style_params if isinstance(default_style_params, dict) else {}
        prompt_snapshot = dict(default_prompt_snapshot) if isinstance(default_prompt_snapshot, dict) else {}

        few_ids = _coerce_int_list(default_few_shot_example_ids)

        try:
            with db.begin_nested():
                obj = PracticeSessionSetting(
                    session_id=session_id,
                    style_preset=style_preset,
                    style_params=dict(style),
                    generation_params=gen,
                    few_shot_example_ids=few_ids,  # ✅ JSONB array
                    prompt_snapshot=prompt_snapshot,
                )
                db.add(obj)
                db.flush()

            db.refresh(obj)
            return obj
        except IntegrityError:
            row = self.get_by_session(db, session_id=session_id)
            if row:
                return row
            raise

    def ensure_default(self, db: Session, *, session_id: int) -> PracticeSessionSetting:
        return self.get_or_create_default(db, session_id=session_id)

    def update_by_session_id(
        self,
        db: Session,
        *,
        session_id: int,
        data: Union[PracticeSessionSettingUpdate, Mapping[str, Any]],
    ) -> Optional[PracticeSessionSetting]:
        row = self.get_by_session(db, session_id=session_id)
        if not row:
            return None

        values = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        if not values:
            return row

        if "style_preset" in values:
            row.style_preset = values.get("style_preset")

        if "style_params" in values:
            incoming_style = _coerce_dict(values.get("style_params"))
            base_style = dict(getattr(row, "style_params", None) or {})
            base_style.update(incoming_style)
            row.style_params = base_style

        if "generation_params" in values:
            incoming_gen = _normalize_generation_params_dict(_coerce_dict(values.get("generation_params")))
            base_gen = _normalize_generation_params_dict(dict(getattr(row, "generation_params", None) or {}))
            base_gen.update(incoming_gen)
            row.generation_params = _normalize_generation_params_dict(base_gen)

        if "few_shot_example_ids" in values:
            # ✅ JSONB array로 그대로 저장
            row.few_shot_example_ids = _coerce_int_list(values.get("few_shot_example_ids"))

        if "prompt_snapshot" in values:
            incoming_snap = _coerce_dict(values.get("prompt_snapshot"))
            base_snap = dict(getattr(row, "prompt_snapshot", None) or {})
            base_snap.update(incoming_snap)
            row.prompt_snapshot = base_snap

        db.add(row)
        db.flush()
        db.refresh(row)
        return row


practice_session_setting_crud = PracticeSessionSettingCRUD()


# =========================================================
# PracticeSessionModel CRUD
# =========================================================
class PracticeSessionModelCRUD:
    def create(self, db: Session, data: PracticeSessionModelCreate) -> PracticeSessionModel:
        raw_gp = getattr(data, "generation_params", None)
        gp = _normalize_generation_params_dict(_coerce_dict(raw_gp)) if raw_gp is not None else {}

        obj = PracticeSessionModel(
            session_id=data.session_id,
            model_name=data.model_name,
            is_primary=data.is_primary if data.is_primary is not None else False,
            generation_params=gp,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, session_model_id: int) -> Optional[PracticeSessionModel]:
        stmt = select(PracticeSessionModel).where(PracticeSessionModel.session_model_id == session_model_id)
        return db.scalar(stmt)

    def list_by_session(self, db: Session, session_id: int) -> Sequence[PracticeSessionModel]:
        stmt = (
            select(PracticeSessionModel)
            .where(PracticeSessionModel.session_id == session_id)
            .order_by(
                PracticeSessionModel.is_primary.desc(),
                PracticeSessionModel.session_model_id.asc(),
            )
        )
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        *,
        session_model_id: int,
        data: Union[PracticeSessionModelUpdate, Mapping[str, Any]],
    ) -> PracticeSessionModel | None:
        obj = db.get(PracticeSessionModel, session_model_id)
        if obj is None:
            return None

        update_data = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        if not update_data:
            return obj

        if "generation_params" in update_data:
            update_data["generation_params"] = _normalize_generation_params_dict(
                _coerce_dict(update_data.get("generation_params"))
            )

        for k, v in update_data.items():
            setattr(obj, k, v)

        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, *, session_model_id: int) -> None:
        obj = db.get(PracticeSessionModel, session_model_id)
        if obj:
            db.delete(obj)
            db.flush()

    def bulk_sync_generation_params_by_session(
        self,
        db: Session,
        *,
        session_id: int,
        generation_params: Mapping[str, Any] | Any,
        merge: bool = True,
        overwrite_keys: Optional[list[str]] = None,
    ) -> list[PracticeSessionModel]:
        gp = _normalize_generation_params_dict(_coerce_dict(generation_params))
        if not gp:
            return list(self.list_by_session(db, session_id=session_id))

        models = list(self.list_by_session(db, session_id=session_id))
        keys = overwrite_keys[:] if overwrite_keys else None

        for m in models:
            current = _normalize_generation_params_dict(dict(getattr(m, "generation_params", None) or {}))
            next_gp = dict(current) if merge else {}

            if keys is None:
                next_gp.update(gp)
            else:
                for k in keys:
                    if k in gp:
                        next_gp[k] = gp[k]

            m.generation_params = _normalize_generation_params_dict(next_gp)
            db.add(m)

        db.flush()
        return models


practice_session_model_crud = PracticeSessionModelCRUD()


# =========================================================
# PracticeResponse CRUD
# =========================================================
class PracticeResponseCRUD:
    def create(self, db: Session, data: PracticeResponseCreate) -> PracticeResponse:
        obj = PracticeResponse(
            session_model_id=data.session_model_id,
            session_id=data.session_id,
            model_name=data.model_name,
            prompt_text=data.prompt_text,
            response_text=data.response_text,
            comparison_run_id=data.comparison_run_id,
            panel_key=data.panel_key,
            token_usage=data.token_usage,
            latency_ms=data.latency_ms,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, response_id: int) -> Optional[PracticeResponse]:
        stmt = select(PracticeResponse).where(PracticeResponse.response_id == response_id)
        return db.scalar(stmt)

    def list_by_session_model(self, db: Session, session_model_id: int) -> Sequence[PracticeResponse]:
        stmt = (
            select(PracticeResponse)
            .where(PracticeResponse.session_model_id == session_model_id)
            .order_by(PracticeResponse.created_at.asc())
        )
        return db.scalars(stmt).all()

    def list_by_session(self, db: Session, session_id: int) -> Sequence[PracticeResponse]:
        stmt = (
            select(PracticeResponse)
            .where(PracticeResponse.session_id == session_id)
            .order_by(PracticeResponse.created_at.asc(), PracticeResponse.response_id.asc())
        )
        return db.scalars(stmt).all()

    def update(self, db: Session, response_id: int, data: PracticeResponseUpdate) -> Optional[PracticeResponse]:
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        if not values:
            return self.get(db, response_id)

        stmt = (
            update(PracticeResponse)
            .where(PracticeResponse.response_id == response_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        return self.get(db, response_id)

    def delete(self, db: Session, *, response_id: int) -> None:
        stmt = delete(PracticeResponse).where(PracticeResponse.response_id == response_id)
        db.execute(stmt)
        db.flush()


practice_response_crud = PracticeResponseCRUD()
