# crud/user/practice.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Any, Mapping, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func
from fastapi import HTTPException

from models.partner.catalog import ModelCatalog
from models.user.practice import (
    PracticeSession,
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
)


# =========================================================
# PracticeSession CRUD
# =========================================================
class PracticeSessionCRUD:
    def create(self, db: Session, data: PracticeSessionCreate) -> PracticeSession:
        # 엔드포인트에서 me.user_id로 채워진 상태여야 함
        if data.user_id is None:
            raise ValueError("PracticeSessionCreate.user_id must be set before create()")

        obj = PracticeSession(
            user_id=data.user_id,
            class_id=data.class_id,
            title=data.title,
            notes=data.notes,
            # started_at, completed_at 은 DB 기본값/제약에 맡김
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

        total = db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        stmt = (
            stmt.order_by(PracticeSession.started_at.desc())
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
        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
        }
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
# PracticeSessionModel CRUD
# =========================================================
class PracticeSessionModelCRUD:
    def create(
        self,
        db: Session,
        data: PracticeSessionModelCreate,
    ) -> PracticeSessionModel:
        obj = PracticeSessionModel(
            session_id=data.session_id,
            model_name=data.model_name,
            is_primary=data.is_primary if data.is_primary is not None else False,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj


    def get(
        self,
        db: Session,
        session_model_id: int,
    ) -> Optional[PracticeSessionModel]:
        stmt = select(PracticeSessionModel).where(
            PracticeSessionModel.session_model_id == session_model_id
        )
        return db.scalar(stmt)

    def list_by_session(
        self,
        db: Session,
        session_id: int,
    ) -> Sequence[PracticeSessionModel]:
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
        """
        PracticeSessionModel 업데이트.
        - data: Pydantic 스키마든 dict든 둘 다 허용.
        """

        # 1) data를 dict로 정규화
        if hasattr(data, "model_dump"):
            update_data = data.model_dump(exclude_unset=True)
        else:
            update_data = dict(data)

        if not update_data:
            # 변경할 게 없으면 현재 상태만 리턴
            return db.get(PracticeSessionModel, session_model_id)

        # 2) 대상 객체 조회
        obj = db.get(PracticeSessionModel, session_model_id)
        if obj is None:
            return None

        # 3) 필드 적용
        for k, v in update_data.items():
            setattr(obj, k, v)

        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    # NOTE (service/user/practice.py):
    # - 세션 내 primary 모델 변경 시
    #   1) 기존 is_primary=true 모두 false로 초기화
    #   2) 새 모델을 is_primary=true 로 설정
    #   -> 여기 CRUD에는 단순 update만 두고, 위 로직은 service 계층에서 묶어 처리 추천


practice_session_model_crud = PracticeSessionModelCRUD()


# =========================================================
# PracticeResponse CRUD
# =========================================================
class PracticeResponseCRUD:
    def create(
        self,
        db: Session,
        data: PracticeResponseCreate,
    ) -> PracticeResponse:
        obj = PracticeResponse(
            session_model_id=data.session_model_id,
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


    def get(
        self,
        db: Session,
        response_id: int,
    ) -> Optional[PracticeResponse]:
        stmt = select(PracticeResponse).where(
            PracticeResponse.response_id == response_id
        )
        return db.scalar(stmt)

    def list_by_session_model(
        self,
        db: Session,
        session_model_id: int,
    ) -> Sequence[PracticeResponse]:
        stmt = (
            select(PracticeResponse)
            .where(PracticeResponse.session_model_id == session_model_id)
            .order_by(PracticeResponse.created_at.asc())
        )
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        response_id: int,
        data: PracticeResponseUpdate,
    ) -> Optional[PracticeResponse]:
        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
        }
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

    def delete(self, db: Session, response_id: int) -> None:
        stmt = delete(PracticeResponse).where(
            PracticeResponse.response_id == response_id
        )
        db.execute(stmt)
        db.flush()

    # NOTE (service/user/practice.py):
    # - 실제 LLM 호출/응답 로깅 플로우
    #   1) 세션/모델 검증
    #   2) LLM 호출 + token_usage, latency_ms 계산
    #   3) 이 CRUD.create() 로 저장
    #   4) 이후 rating, model_comparison 과 연계


practice_response_crud = PracticeResponseCRUD()


# =========================================================
# PracticeRating CRUD
# =========================================================
class PracticeRatingCRUD:
    def get(self, db: Session, rating_id: int) -> Optional[PracticeRating]:
        stmt = select(PracticeRating).where(
            PracticeRating.rating_id == rating_id
        )
        return db.scalar(stmt)

    def get_by_response_user(
        self,
        db: Session,
        *,
        response_id: int,
        user_id: int,
    ) -> Optional[PracticeRating]:
        stmt = select(PracticeRating).where(
            PracticeRating.response_id == response_id,
            PracticeRating.user_id == user_id,
        )
        return db.scalar(stmt)

    def upsert(
        self,
        db: Session,
        data: PracticeRatingCreate,
    ) -> PracticeRating:
        """
        (response_id, user_id) 단위로 1개만 존재
        이미 있으면 score/feedback 업데이트
        """
        if data.user_id is None:
            raise ValueError("PracticeRatingCreate.user_id must be set before upsert()")

        rating = self.get_by_response_user(
            db,
            response_id=data.response_id,
            user_id=data.user_id,
        )
        if rating is None:
            rating = PracticeRating(
                response_id=data.response_id,
                user_id=data.user_id,
                score=data.score,
                feedback=data.feedback,
                # created_at 은 DB default
            )
            db.add(rating)
            db.flush()
            db.refresh(rating)
            return rating

        # update
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

    def update(
        self,
        db: Session,
        rating_id: int,
        data: PracticeRatingUpdate,
    ) -> Optional[PracticeRating]:
        rating = self.get(db, rating_id)
        if not rating:
            return None

        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
        }
        for k, v in values.items():
            setattr(rating, k, v)
        db.flush()
        db.refresh(rating)
        return rating

    def list_by_response(
        self,
        db: Session,
        response_id: int,
    ) -> Sequence[PracticeRating]:
        stmt = select(PracticeRating).where(
            PracticeRating.response_id == response_id
        )
        return db.scalars(stmt).all()

    def list_by_user(
        self,
        db: Session,
        user_id: int,
    ) -> Sequence[PracticeRating]:
        stmt = select(PracticeRating).where(
            PracticeRating.user_id == user_id
        )
        return db.scalars(stmt).all()

    def delete(self, db: Session, rating_id: int) -> None:
        stmt = delete(PracticeRating).where(
            PracticeRating.rating_id == rating_id
        )
        db.execute(stmt)
        db.flush()


practice_rating_crud = PracticeRatingCRUD()


# =========================================================
# ModelComparison CRUD
# =========================================================
class ModelComparisonCRUD:
    def create(
        self,
        db: Session,
        data: ModelComparisonCreate,
    ) -> ModelComparison:
        obj = ModelComparison(
            session_id=data.session_id,
            model_a=data.model_a,
            model_b=data.model_b,
            winner_model=data.winner_model,
            latency_diff_ms=data.latency_diff_ms,
            token_diff=data.token_diff,
            user_feedback=data.user_feedback,
            # created_at 은 DB default
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(
        self,
        db: Session,
        comparison_id: int,
    ) -> Optional[ModelComparison]:
        stmt = select(ModelComparison).where(
            ModelComparison.comparison_id == comparison_id
        )
        return db.scalar(stmt)

    def list_by_session(
        self,
        db: Session,
        session_id: int,
    ) -> Sequence[ModelComparison]:
        stmt = (
            select(ModelComparison)
            .where(ModelComparison.session_id == session_id)
            .order_by(ModelComparison.created_at.asc())
        )
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        comparison_id: int,
        data: ModelComparisonUpdate,
    ) -> Optional[ModelComparison]:
        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
        }
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

    def delete(self, db: Session, comparison_id: int) -> None:
        stmt = delete(ModelComparison).where(
            ModelComparison.comparison_id == comparison_id
        )
        db.execute(stmt)
        db.flush()

    # NOTE (service/user/practice.py):
    # - 두 모델 응답/토큰/레이턴시 데이터 받아서
    #   1) ModelComparisonCreate 구성
    #   2) 이 CRUD.create() 호출
    #   3) 필요 시 PracticeRating 과 함께 묶어서 비교 실습 플로우 구성


model_comparison_crud = ModelComparisonCRUD()
