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
    PracticeSessionSettingFewShot,
    UserFewShotExample,
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
    UserFewShotExampleCreate,
    UserFewShotExampleUpdate,
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


def _normalize_generation_params_dict(v: dict[str, Any]) -> dict[str, Any]:
    """
    DB에는 max_completion_tokens 기준으로 맞추되,
    기존 코드 호환을 위해 max_tokens도 함께 동일 값으로 유지.
    """
    if not isinstance(v, dict):
        return {}

    # dict(v)로 복사해서 side-effect 최소화
    out = dict(v)

    mct = out.get("max_completion_tokens")
    mt = out.get("max_tokens")

    # max_tokens만 들어오면 max_completion_tokens로 승격
    if mct is None and mt is not None:
        out["max_completion_tokens"] = mt
        out["max_tokens"] = mt
        return out

    # max_completion_tokens만 들어오면 max_tokens도 채움
    if mt is None and mct is not None:
        out["max_tokens"] = mct
        out["max_completion_tokens"] = mct
        return out

    # 둘 다 있으면 max_completion_tokens 우선으로 동기화
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
        obj = PracticeSession(
            user_id=user_id,
            class_id=data.class_id,
            project_id=data.project_id,
            knowledge_id=data.knowledge_id,
            agent_id=getattr(data, "agent_id", None),  # ✅ 추가
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
        session_id: int,
        data: PracticeSessionUpdate,
    ) -> Optional[PracticeSession]:
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        if not values:
            return self.get(db, session_id)

        stmt = (
            update(PracticeSession)
            .where(PracticeSession.session_id == session_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        return self.get(db, session_id)

    def delete(self, db: Session, session_id: int) -> None:
        stmt = delete(PracticeSession).where(PracticeSession.session_id == session_id)
        db.execute(stmt)
        db.flush()


practice_session_crud = PracticeSessionCRUD()


# =========================================================
# PracticeSessionSetting CRUD
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
        default_agent_snapshot: Optional[dict[str, Any]] = None,
    ) -> PracticeSessionSetting:
        """
        세션당 settings 1개 보장.
        - 없으면 생성
        - UNIQUE(session_id) 레이스컨디션은 SAVEPOINT로 안전 처리
        """
        row = self.get_by_session(db, session_id=session_id)
        if row:
            return row

        gen = default_generation_params
        if not isinstance(gen, dict):
            gen = getattr(config, "PRACTICE_DEFAULT_GENERATION", {}) or {}
        gen = _normalize_generation_params_dict(dict(gen))

        style = default_style_params if isinstance(default_style_params, dict) else {}
        agent_snapshot = dict(default_agent_snapshot) if isinstance(default_agent_snapshot, dict) else {}

        try:
            with db.begin_nested():
                obj = PracticeSessionSetting(
                    session_id=session_id,
                    style_preset=style_preset,
                    style_params=dict(style),
                    generation_params=gen,
                    agent_snapshot=agent_snapshot,  # ✅ 추가
                )
                db.add(obj)
                db.flush()

                # (선택) 기본 few-shot 링크 세팅
                if default_few_shot_example_ids:
                    for i, eid in enumerate(default_few_shot_example_ids):
                        db.add(
                            PracticeSessionSettingFewShot(
                                setting_id=obj.setting_id,
                                example_id=eid,
                                sort_order=i,
                            )
                        )
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

    def _replace_few_shot_links(
        self,
        db: Session,
        *,
        setting_id: int,
        example_ids: list[int],
    ) -> None:
        db.execute(
            delete(PracticeSessionSettingFewShot).where(
                PracticeSessionSettingFewShot.setting_id == setting_id
            )
        )
        for i, eid in enumerate(example_ids):
            db.add(
                PracticeSessionSettingFewShot(
                    setting_id=setting_id,
                    example_id=eid,
                    sort_order=i,
                )
            )
        db.flush()

    def update_by_session_id(
        self,
        db: Session,
        *,
        session_id: int,
        data: Union[PracticeSessionSettingUpdate, Mapping[str, Any]],
    ) -> Optional[PracticeSessionSetting]:
        """
        session_id 기준 settings PATCH.
        - style_params/generation_params/agent_snapshot: merge
        - few_shot_example_ids: replace(매핑 테이블)
        """
        row = self.get_by_session(db, session_id=session_id)
        if not row:
            return None

        values = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        if not values:
            return row

        # style_preset: replace
        if "style_preset" in values:
            row.style_preset = values.get("style_preset")

        # style_params: merge
        if "style_params" in values:
            incoming_style = _coerce_dict(values.get("style_params"))
            base_style = dict(getattr(row, "style_params", None) or {})
            base_style.update(incoming_style)
            row.style_params = base_style

        # generation_params: merge (token key normalize 포함)
        if "generation_params" in values:
            incoming_gen = _normalize_generation_params_dict(_coerce_dict(values.get("generation_params")))
            base_gen = _normalize_generation_params_dict(dict(getattr(row, "generation_params", None) or {}))
            base_gen.update(incoming_gen)
            row.generation_params = _normalize_generation_params_dict(base_gen)

        # agent_snapshot: merge
        if "agent_snapshot" in values:
            incoming_snap = _coerce_dict(values.get("agent_snapshot"))
            base_snap = dict(getattr(row, "agent_snapshot", None) or {})
            base_snap.update(incoming_snap)
            row.agent_snapshot = base_snap

        # few_shot_example_ids: replace
        if "few_shot_example_ids" in values:
            ids = values.get("few_shot_example_ids") or []
            if not isinstance(ids, list):
                ids = []
            self._replace_few_shot_links(db, setting_id=row.setting_id, example_ids=list(ids))

        db.add(row)
        db.flush()
        db.refresh(row)
        return row


practice_session_setting_crud = PracticeSessionSettingCRUD()


# =========================================================
# UserFewShotExample CRUD (개인 라이브러리)
# =========================================================
class UserFewShotExampleCRUD:
    def create(self, db: Session, *, user_id: int, data: UserFewShotExampleCreate) -> UserFewShotExample:
        obj = UserFewShotExample(
            user_id=user_id,
            title=data.title,
            input_text=data.input_text,
            output_text=data.output_text,
            meta=_coerce_dict(data.meta),
            is_active=data.is_active if data.is_active is not None else True,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, example_id: int) -> Optional[UserFewShotExample]:
        stmt = select(UserFewShotExample).where(UserFewShotExample.example_id == example_id)
        return db.scalar(stmt)

    def list_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        page: int = 1,
        size: int = 50,
        is_active: Optional[bool] = None,
    ) -> Tuple[Sequence[UserFewShotExample], int]:
        stmt = select(UserFewShotExample).where(UserFewShotExample.user_id == user_id)
        if is_active is not None:
            stmt = stmt.where(UserFewShotExample.is_active == is_active)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        stmt = (
            stmt.order_by(UserFewShotExample.created_at.desc(), UserFewShotExample.example_id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = db.scalars(stmt).all()
        return rows, total

    def update(
        self,
        db: Session,
        *,
        example_id: int,
        data: Union[UserFewShotExampleUpdate, Mapping[str, Any]],
    ) -> Optional[UserFewShotExample]:
        obj = db.get(UserFewShotExample, example_id)
        if obj is None:
            return None

        values = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        if not values:
            return obj

        if "meta" in values:
            values["meta"] = _coerce_dict(values.get("meta"))

        for k, v in values.items():
            setattr(obj, k, v)

        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, *, example_id: int) -> None:
        obj = db.get(UserFewShotExample, example_id)
        if obj:
            db.delete(obj)
            db.flush()


user_few_shot_example_crud = UserFewShotExampleCRUD()


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
