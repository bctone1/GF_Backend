# crud/user/agent.py
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

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
        project_id: Optional[int] = None,
        q: Optional[str] = None,
    ) -> Tuple[int, List[AIAgent]]:
        """
        owner_id 기준 에이전트 목록 + 페이징/검색.
        - project_id: 특정 프로젝트에 속한 것만 필터
        - q: name / role_description LIKE 검색
        """
        stmt = select(AIAgent).where(AIAgent.owner_id == owner_id)

        if project_id is not None:
            stmt = stmt.where(AIAgent.project_id == project_id)

        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    AIAgent.name.ilike(like),
                    AIAgent.role_description.ilike(like),
                )
            )

        # total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(count_stmt).scalar_one()

        # page items
        items_stmt = (
            stmt.order_by(AIAgent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = db.execute(items_stmt).scalars().all()

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
        stmt = select(AIAgent).where(
            AIAgent.agent_id == agent_id,
            AIAgent.owner_id == owner_id,
        )
        return db.execute(stmt).scalar_one_or_none()

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
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


ai_agent_crud = CRUDAIAgent(AIAgent)


# =========================================================
# user.agent_shares 전용 CRUD (기존 코드)
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
        stmt = (
            select(AgentShare)
            .where(
                AgentShare.agent_id == agent_id,
                AgentShare.class_id == class_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_by_agent(
        self,
        db: Session,
        *,
        agent_id: int,
        active_only: bool = True,
    ) -> List[AgentShare]:
        stmt = select(AgentShare).where(AgentShare.agent_id == agent_id)
        if active_only:
            stmt = stmt.where(AgentShare.is_active.is_(True))
        stmt = stmt.order_by(AgentShare.created_at.desc())
        return db.execute(stmt).scalars().all()

    def list_by_class(
        self,
        db: Session,
        *,
        class_id: int,
        active_only: bool = True,
    ) -> List[AgentShare]:
        stmt = select(AgentShare).where(AgentShare.class_id == class_id)
        if active_only:
            stmt = stmt.where(AgentShare.is_active.is_(True))
        stmt = stmt.order_by(AgentShare.created_at.desc())
        return db.execute(stmt).scalars().all()

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
            # 이미 존재하는데 비활성 상태였다면 다시 활성화만 해줌
            if not existing.is_active:
                existing.is_active = True
                db.add(existing)
                db.commit()
                db.refresh(existing)
            return existing

        return self.create(db=db, obj_in=obj_in, shared_by_user_id=shared_by_user_id)


agent_share_crud = CRUDAgentShare(AgentShare)
