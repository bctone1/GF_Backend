# crud/user/agent.py
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from crud.base import CRUDBase
from models.user.agent import AIAgent, AgentShare
from schemas.user.agent import (
    AIAgentCreate,
    AIAgentUpdate,
    AgentShareCreate,
    AgentShareUpdate,
)


# =========================================================
# user.ai_agents 전용 CRUD
# =========================================================
class CRUDAIAgent(CRUDBase[AIAgent, AIAgentCreate, AIAgentUpdate]):
    """
    내 에이전트(AIAgent) 전용 CRUD.
    - 생성 시 owner_id를 항상 서버에서 주입하도록 create 시그니처를 확장.
    """

    def create(
        self,
        db: Session,
        *,
        obj_in: AIAgentCreate,
        owner_id: int,
    ) -> AIAgent:
        """
        owner_id는 항상 현재 로그인 유저(me.user_id)에서 받아서 넣는다.
        """
        data = obj_in.model_dump(exclude_unset=True)

        # is_active는 Optional이라 None이 들어오면 DB(not null)에서 터질 수 있어서 무시
        if data.get("is_active", "__missing__") is None:
            data.pop("is_active", None)

        db_obj = AIAgent(
            owner_id=owner_id,
            **data,
        )
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
    ) -> Tuple[int, List[AIAgent]]:
        """
        owner_id 기준 에이전트 목록 + 페이징/검색.
        - q: name / role_description LIKE 검색
        """
        query = db.query(AIAgent).filter(AIAgent.owner_id == owner_id)

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    AIAgent.name.ilike(like),
                    AIAgent.role_description.ilike(like),
                )
            )

        # total count (정렬 제거하고 count)
        total = query.order_by(None).count()

        items = (
            query.order_by(AIAgent.created_at.desc())
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
        agent_id: int,
    ) -> Optional[AIAgent]:
        """
        owner_id 기준으로 내 에이전트 한 건 조회.
        (없거나 남의 에이전트면 None)
        """
        return (
            db.query(AIAgent)
            .filter(
                AIAgent.agent_id == agent_id,
                AIAgent.owner_id == owner_id,
            )
            .first()
        )

    def update_for_owner(
        self,
        db: Session,
        *,
        owner_id: int,
        agent_id: int,
        obj_in: AIAgentUpdate,
    ) -> Optional[AIAgent]:
        """
        owner_id 기준으로만 수정 가능.
        - 없으면 None 리턴 (엔드포인트/서비스에서 404 처리)
        """
        db_obj = self.get_for_owner(db, owner_id=owner_id, agent_id=agent_id)
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


ai_agent_crud = CRUDAIAgent(AIAgent)


# =========================================================
# user.agent_shares 전용 CRUD
# =========================================================
class CRUDAgentShare(CRUDBase[AgentShare, AgentShareCreate, AgentShareUpdate]):
    """
    user.agent_shares 전용 CRUD.
    - 기본 CRUDBase 기능 + 공유 시나리오용 헬퍼 메서드들.
    """

    def create(
        self,
        db: Session,
        *,
        obj_in: AgentShareCreate,
        shared_by_user_id: int,
    ) -> AgentShare:
        """
        실제 공유를 수행한 유저(shared_by_user_id)는 서비스 레이어에서 me.user_id로 넣어줌.
        """
        db_obj = AgentShare(
            agent_id=obj_in.agent_id,
            class_id=obj_in.class_id,
            shared_by_user_id=shared_by_user_id,
            is_active=obj_in.is_active if obj_in.is_active is not None else True,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_agent_and_class(
        self,
        db: Session,
        *,
        agent_id: int,
        class_id: int,
    ) -> Optional[AgentShare]:
        return (
            db.query(AgentShare)
            .filter(
                AgentShare.agent_id == agent_id,
                AgentShare.class_id == class_id,
            )
            .first()
        )

    def list_by_agent(
        self,
        db: Session,
        *,
        agent_id: int,
        active_only: bool = True,
    ) -> List[AgentShare]:
        query = db.query(AgentShare).filter(AgentShare.agent_id == agent_id)
        if active_only:
            query = query.filter(AgentShare.is_active.is_(True))
        return query.order_by(AgentShare.created_at.desc()).all()

    def list_by_class(
        self,
        db: Session,
        *,
        class_id: int,
        active_only: bool = True,
    ) -> List[AgentShare]:
        query = db.query(AgentShare).filter(AgentShare.class_id == class_id)
        if active_only:
            query = query.filter(AgentShare.is_active.is_(True))
        return query.order_by(AgentShare.created_at.desc()).all()

    def set_active(
        self,
        db: Session,
        *,
        share: AgentShare,
        is_active: bool,
    ) -> AgentShare:
        share.is_active = is_active
        db.add(share)
        db.commit()
        db.refresh(share)
        return share

    def get_or_create(
        self,
        db: Session,
        *,
        obj_in: AgentShareCreate,
        shared_by_user_id: int,
    ) -> AgentShare:
        """
        같은 agent_id + class_id 조합이 이미 있으면 재사용하고,
        없으면 새로 생성.
        """
        existing = self.get_by_agent_and_class(
            db,
            agent_id=obj_in.agent_id,
            class_id=obj_in.class_id,
        )
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.add(existing)
                db.commit()
                db.refresh(existing)
            return existing

        return self.create(db=db, obj_in=obj_in, shared_by_user_id=shared_by_user_id)


agent_share_crud = CRUDAgentShare(AgentShare)
