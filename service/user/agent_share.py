# service/user/agent_share.py
from __future__ import annotations

from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.agent import AIAgent, AgentShare
from models.partner.course import Class
from models.partner.partner_core import Partner
from crud.user.agent import agent_share_crud


# ==============================
# 내부 헬퍼: 소유/권한 검증
# ==============================
def ensure_my_agent(db: Session, *, agent_id: int, me: AppUser) -> AIAgent:
    """
    현재 로그인 유저(me)가 소유한 에이전트인지 검증.
    - 못 찾으면 404
    - 내 소유가 아니면 403
    """
    stmt = select(AIAgent).where(AIAgent.agent_id == agent_id)
    agent = db.execute(stmt).scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="에이전트를 찾을 수 없습니다.",
        )
    if agent.owner_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 에이전트에 대한 권한이 없습니다.",
        )
    return agent


def ensure_my_class_as_teacher(db: Session, *, class_id: int, me: AppUser) -> Class:
    """
    현재 로그인 유저(me)가 이 Class 의 담당 강사(Partner)인지 검증.
    - partner.partners.user_id == me.user_id
    - 그 Partner 가 가진 Class.id 인지 확인
    """
    stmt = (
        select(Class)
        .join(
            Partner,
            Class.partner_id == Partner.id,
        )
        .where(
            Class.id == class_id,
            Partner.user_id == me.user_id,
            Partner.is_active.is_(True),
        )
    )
    classroom = db.execute(stmt).scalar_one_or_none()
    if classroom is None:
        # 존재하지 않거나, 내가 강사가 아닌 경우 둘 다 여기로
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 강의에 대한 권한이 없습니다.",
        )
    return classroom


# ==============================
# 공유 서비스
# ==============================
def share_agent_to_class(
    db: Session,
    *,
    agent_id: int,
    class_id: int,
    me: AppUser,
) -> AgentShare:
    """
    강사의 개인 에이전트를 특정 class 에 공유.
    - 내 에이전트인지 확인
    - 내가 해당 class 의 강사인지 확인
    - 이미 공유되어 있으면 재사용(비활성 상태였다면 다시 활성화)
    """
    # 권한/유효성 검증
    ensure_my_agent(db, agent_id=agent_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    from schemas.user.agent import AgentShareCreate

    share_in = AgentShareCreate(
        agent_id=agent_id,
        class_id=class_id,
        is_active=None,  # None → CRUD 에서 default True 처리
    )
    share = agent_share_crud.get_or_create(
        db,
        obj_in=share_in,
        shared_by_user_id=me.user_id,
    )
    return share


def deactivate_agent_share(
    db: Session,
    *,
    agent_id: int,
    class_id: int,
    me: AppUser,
) -> AgentShare:
    """
    특정 class 에 대한 에이전트 공유 비활성화.
    - 내 에이전트인지
    - 해당 class 의 강사인지
    - share row 가 실제로 존재하는지
    """
    ensure_my_agent(db, agent_id=agent_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    share = agent_share_crud.get_by_agent_and_class(
        db,
        agent_id=agent_id,
        class_id=class_id,
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 에이전트를 찾을 수 없습니다.",
        )

    if not share.is_active:
        # 이미 비활성인데 또 비활성 요청이면 그냥 그대로 반환
        return share

    return agent_share_crud.set_active(db, share=share, is_active=False)


def list_shared_agents_for_class(
    db: Session,
    *,
    class_id: int,
    me: AppUser | None = None,
    active_only: bool = True,
) -> List[AIAgent]:
    """
    특정 class 에 공유된 에이전트 목록 조회.
    - 지금은 강사 기준 권한만 예시로 체크
    - 나중에 학생 수강 여부(enrollments) 검증 추가 가능
    """
    if me is not None:
        # 최소한 담당 강사는 조회 가능
        ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    shares = agent_share_crud.list_by_class(
        db,
        class_id=class_id,
        active_only=active_only,
    )
    if not shares:
        return []

    agent_ids = [s.agent_id for s in shares]

    stmt = (
        select(AIAgent)
        .where(AIAgent.agent_id.in_(agent_ids))
        .order_by(AIAgent.created_at.desc())
    )
    agents = db.execute(stmt).scalars().all()
    return agents
