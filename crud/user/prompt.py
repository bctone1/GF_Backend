# crud/user/prompt.py
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from crud.base import CRUDBase
from models.user.prompt import AIPrompt, PromptShare
from schemas.user.prompt import (
    AIPromptCreate,
    AIPromptUpdate,
    PromptShareCreate,
    PromptShareUpdate,
)


# =========================================================
# user.ai_prompts CRUD (prompt)
# =========================================================
class CRUDAIPrompt(CRUDBase[AIPrompt, AIPromptCreate, AIPromptUpdate]):
    """
    내 프롬프트(AIPrompt) 전용 CRUD.
    - 생성 시 owner_id를 항상 서버에서 주입하도록 create 시그니처를 확장.
    """

    def create(
        self,
        db: Session,
        *,
        obj_in: AIPromptCreate,
        owner_id: int,
    ) -> AIPrompt:
        """
        owner_id는 항상 현재 로그인 유저(me.user_id)에서 받아서 넣는다.
        """
        data = obj_in.model_dump(exclude_unset=True)

        # is_active는 Optional이라 None이 들어오면 DB(not null)에서 터질 수 있어서 무시 (server_default 사용)
        if data.get("is_active", "__missing__") is None:
            data.pop("is_active", None)

        db_obj = AIPrompt(owner_id=owner_id, **data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def list_by_owner(
        self,
        db: Session,
        *,
        owner_id: int,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> Tuple[int, List[AIPrompt]]:
        """
        owner_id 기준 프롬프트 목록 + 페이징/검색.
        - q: name / role_description LIKE 검색
        """
        query = db.query(AIPrompt).filter(AIPrompt.owner_id == owner_id)

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    AIPrompt.name.ilike(like),
                    AIPrompt.role_description.ilike(like),
                )
            )

        total = query.order_by(None).count()

        items = (
            query.order_by(AIPrompt.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, items

    def get_for_owner(
        self,
        db: Session,
        *,
        owner_id: int,
        prompt_id: int,
    ) -> Optional[AIPrompt]:
        """
        owner_id 기준으로 내 프롬프트 한 건 조회.
        (없거나 남의 프롬프트면 None)
        """
        return (
            db.query(AIPrompt)
            .filter(
                AIPrompt.prompt_id == prompt_id,
                AIPrompt.owner_id == owner_id,
            )
            .first()
        )

    def update_for_owner(
        self,
        db: Session,
        *,
        owner_id: int,
        prompt_id: int,
        obj_in: AIPromptUpdate,
    ) -> Optional[AIPrompt]:
        """
        owner_id 기준으로만 수정 가능.
        - 없으면 None 리턴 (엔드포인트/서비스에서 404 처리)
        """
        db_obj = self.get_for_owner(db, owner_id=owner_id, prompt_id=prompt_id)
        if db_obj is None:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)

        # not-null 컬럼들에 None이 들어오면 DB에서 터지니 무시
        for key in ("name", "system_prompt", "is_active"):
            if key in update_data and update_data[key] is None:
                update_data.pop(key, None)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, db_obj: AIPrompt) -> None:
        """
        AIPrompt 삭제.
        - commit은 서비스 레이어에서 수행.
        """
        db.delete(db_obj)
        db.flush()


ai_prompt_crud = CRUDAIPrompt(AIPrompt)


# =========================================================
# user.prompt_shares CRUD (prompt)
# =========================================================
class CRUDPromptShare(CRUDBase[PromptShare, PromptShareCreate, PromptShareUpdate]):
    """
    user.prompt_shares 전용 CRUD (prompt).
    - 기본 CRUDBase 기능 + 공유 시나리오용 헬퍼 메서드들.
    """

    def create(
        self,
        db: Session,
        *,
        obj_in: PromptShareCreate,
        shared_by_user_id: int,
    ) -> PromptShare:
        """
        실제 공유를 수행한 유저(shared_by_user_id)는 서비스 레이어에서 me.user_id로 넣어줌.
        """
        data = obj_in.model_dump(exclude_unset=True)

        # is_active Optional None이면 server_default 사용(혹은 True로 강제해도 됨)
        if data.get("is_active", "__missing__") is None:
            data.pop("is_active", None)

        db_obj = PromptShare(
            shared_by_user_id=shared_by_user_id,
            **data,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_prompt_and_class(
        self,
        db: Session,
        *,
        prompt_id: int,
        class_id: int,
    ) -> Optional[PromptShare]:
        return (
            db.query(PromptShare)
            .filter(
                PromptShare.prompt_id == prompt_id,
                PromptShare.class_id == class_id,
            )
            .first()
        )

    def list_by_prompt(
        self,
        db: Session,
        *,
        prompt_id: int,
        active_only: bool = True,
    ) -> List[PromptShare]:
        query = db.query(PromptShare).filter(PromptShare.prompt_id == prompt_id)
        if active_only:
            query = query.filter(PromptShare.is_active.is_(True))
        return query.order_by(PromptShare.created_at.desc()).all()

    def list_by_class(
        self,
        db: Session,
        *,
        class_id: int,
        active_only: bool = True,
    ) -> List[PromptShare]:
        query = db.query(PromptShare).filter(PromptShare.class_id == class_id)
        if active_only:
            query = query.filter(PromptShare.is_active.is_(True))
        return query.order_by(PromptShare.created_at.desc()).all()

    def set_active(
        self,
        db: Session,
        *,
        share: PromptShare,
        is_active: bool,
    ) -> PromptShare:
        share.is_active = is_active
        db.add(share)
        db.commit()
        db.refresh(share)
        return share

    def get_or_create(
        self,
        db: Session,
        *,
        obj_in: PromptShareCreate,
        shared_by_user_id: int,
    ) -> PromptShare:
        """
        같은 prompt_id + class_id 조합이 이미 있으면 재사용하고,
        없으면 새로 생성.

        (주의) 동시성에서 레이스로 유니크 충돌이 날 수 있으니 IntegrityError 방어.
        """
        existing = self.get_by_prompt_and_class(
            db,
            prompt_id=obj_in.prompt_id,
            class_id=obj_in.class_id,
        )
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.add(existing)
                db.commit()
                db.refresh(existing)
            return existing

        try:
            return self.create(db=db, obj_in=obj_in, shared_by_user_id=shared_by_user_id)
        except IntegrityError:
            db.rollback()
            # 누군가가 방금 만들었을 가능성 → 다시 조회해서 리턴
            again = self.get_by_prompt_and_class(
                db,
                prompt_id=obj_in.prompt_id,
                class_id=obj_in.class_id,
            )
            if again is None:
                raise
            if not again.is_active:
                again.is_active = True
                db.add(again)
                db.commit()
                db.refresh(again)
            return again


prompt_share_crud = CRUDPromptShare(PromptShare)
