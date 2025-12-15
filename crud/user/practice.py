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
    PracticeRating,
    ModelComparison,
)

from schemas.user.practice import (
    PracticeSessionCreate,
    PracticeSessionUpdate,
    PracticeSessionModelCreate,
    PracticeSessionModelUpdate,
    PracticeResponseCreate,
    PracticeResponseUpdate,
    PracticeRatingCreate,
    PracticeRatingUpdate,
    ModelComparisonCreate,
    ModelComparisonUpdate,
    # ✅ NEW (스키마 단계에서 만들 예정)
    PracticeSessionSettingUpdate,
)


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
        stmt = select(PracticeSession).where(PracticeSession.user_id == user_id)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        stmt = (
            stmt.order_by(PracticeSession.created_at.desc())
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
    def get_by_session(
        self,
        db: Session,
        *,
        session_id: int,
    ) -> Optional[PracticeSessionSetting]:
        stmt = select(PracticeSessionSetting).where(
            PracticeSessionSetting.session_id == session_id
        )
        return db.scalar(stmt)

    def get_or_create_default(
        self,
        db: Session,
        *,
        session_id: int,
        default_generation_params: Optional[dict[str, Any]] = None,
        default_style_params: Optional[dict[str, Any]] = None,
        default_few_shot_examples: Optional[list[Any]] = None,
        style_preset: Optional[str] = None,
    ) -> PracticeSessionSetting:
        row = self.get_by_session(db, session_id=session_id)
        if row:
            return row

        gen = default_generation_params
        if not isinstance(gen, dict):
            gen = getattr(config, "PRACTICE_DEFAULT_GENERATION", {}) or {}
        gen = dict(gen)

        style = default_style_params if isinstance(default_style_params, dict) else {}
        few = default_few_shot_examples if isinstance(default_few_shot_examples, list) else []

        try:
            with db.begin_nested():
                obj = PracticeSessionSetting(
                    session_id=session_id,
                    style_preset=style_preset,
                    style_params=style,
                    generation_params=gen,
                    few_shot_examples=few,
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

    # ✅ NEW: endpoints에서 필요
    def update_by_session_id(
        self,
        db: Session,
        *,
        session_id: int,
        data: Union[PracticeSessionSettingUpdate, Mapping[str, Any]],
    ) -> Optional[PracticeSessionSetting]:
        """
        session_id 기준으로 settings PATCH.
        - 없으면 None (endpoint에서 ensure_default 후 호출하는 패턴 권장)
        - data: Pydantic 스키마 또는 dict 허용
        """
        row = self.get_by_session(db, session_id=session_id)
        if not row:
            return None

        if hasattr(data, "model_dump"):
            values = data.model_dump(exclude_unset=True)
        else:
            values = dict(data)

        if not values:
            return row

        # 명시적 set (ORM update)
        for k, v in values.items():
            setattr(row, k, v)

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
        if data.generation_params is not None:
            gen_params: dict[str, Any] = data.generation_params.model_dump(exclude_unset=True)
        else:
            gen_params = {}

        obj = PracticeSessionModel(
            session_id=data.session_id,
            model_name=data.model_name,
            is_primary=data.is_primary if data.is_primary is not None else False,
            generation_params=gen_params,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, session_model_id: int) -> Optional[PracticeSessionModel]:
        stmt = select(PracticeSessionModel).where(
            PracticeSessionModel.session_model_id == session_model_id
        )
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
        if hasattr(data, "model_dump"):
            update_data = data.model_dump(exclude_unset=True)
        else:
            update_data = dict(data)

        if not update_data:
            return db.get(PracticeSessionModel, session_model_id)

        obj = db.get(PracticeSessionModel, session_model_id)
        if obj is None:
            return None

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
            .order_by(
                PracticeResponse.created_at.asc(),
                PracticeResponse.response_id.asc(),
            )
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


# =========================================================
# PracticeRating CRUD
# =========================================================
class PracticeRatingCRUD:
    def get(self, db: Session, rating_id: int) -> Optional[PracticeRating]:
        stmt = select(PracticeRating).where(PracticeRating.rating_id == rating_id)
        return db.scalar(stmt)

    def get_by_response_user(self, db: Session, *, response_id: int, user_id: int) -> Optional[PracticeRating]:
        stmt = select(PracticeRating).where(
            PracticeRating.response_id == response_id,
            PracticeRating.user_id == user_id,
        )
        return db.scalar(stmt)

    def upsert(self, db: Session, data: PracticeRatingCreate) -> PracticeRating:
        if data.user_id is None:
            raise ValueError("PracticeRatingCreate.user_id must be set before upsert()")

        rating = self.get_by_response_user(db, response_id=data.response_id, user_id=data.user_id)
        if rating is None:
            rating = PracticeRating(
                response_id=data.response_id,
                user_id=data.user_id,
                score=data.score,
                feedback=data.feedback,
            )
            db.add(rating)
            db.flush()
            db.refresh(rating)
            return rating

        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
            if k in {"score", "feedback"}
        }
        for k, v in values.items():
            setattr(rating, k, v)
        db.flush()
        db.refresh(rating)
        return rating

    def update(self, db: Session, rating_id: int, data: PracticeRatingUpdate) -> Optional[PracticeRating]:
        rating = self.get(db, rating_id)
        if not rating:
            return None

        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        for k, v in values.items():
            setattr(rating, k, v)
        db.flush()
        db.refresh(rating)
        return rating

    def list_by_response(self, db: Session, response_id: int) -> Sequence[PracticeRating]:
        stmt = select(PracticeRating).where(PracticeRating.response_id == response_id)
        return db.scalars(stmt).all()

    def list_by_user(self, db: Session, user_id: int) -> Sequence[PracticeRating]:
        stmt = select(PracticeRating).where(PracticeRating.user_id == user_id)
        return db.scalars(stmt).all()

    def delete(self, db: Session, *, rating_id: int) -> None:
        stmt = delete(PracticeRating).where(PracticeRating.rating_id == rating_id)
        db.execute(stmt)
        db.flush()


practice_rating_crud = PracticeRatingCRUD()


# =========================================================
# ModelComparison CRUD
# =========================================================
class ModelComparisonCRUD:
    def create(self, db: Session, data: ModelComparisonCreate) -> ModelComparison:
        obj = ModelComparison(
            session_id=data.session_id,
            model_a=data.model_a,
            model_b=data.model_b,
            winner_model=data.winner_model,
            latency_diff_ms=data.latency_diff_ms,
            token_diff=data.token_diff,
            user_feedback=data.user_feedback,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, comparison_id: int) -> Optional[ModelComparison]:
        stmt = select(ModelComparison).where(ModelComparison.comparison_id == comparison_id)
        return db.scalar(stmt)

    def list_by_session(self, db: Session, session_id: int) -> Sequence[ModelComparison]:
        stmt = (
            select(ModelComparison)
            .where(ModelComparison.session_id == session_id)
            .order_by(ModelComparison.created_at.asc())
        )
        return db.scalars(stmt).all()

    def update(self, db: Session, comparison_id: int, data: ModelComparisonUpdate) -> Optional[ModelComparison]:
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        if not values:
            return self.get(db, comparison_id)

        stmt = (
            update(ModelComparison)
            .where(ModelComparison.comparison_id == comparison_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        return self.get(db, comparison_id)

    def delete(self, db: Session, *, comparison_id: int) -> None:
        stmt = delete(ModelComparison).where(ModelComparison.comparison_id == comparison_id)
        db.execute(stmt)
        db.flush()


model_comparison_crud = ModelComparisonCRUD()
