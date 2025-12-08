# service/user/agent.py
from __future__ import annotations

from typing import Optional, Tuple, List

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.agent import AIAgent, AgentPrompt
from schemas.user.agent import (
    AIAgentCreate,
    AIAgentUpdate,
    AgentPromptCreate,
)
from crud.user.agent import ai_agent_crud


# =========================================
# helpers
# =========================================
def ensure_my_agent(db: Session, agent_id: int, me: AppUser) -> AIAgent:
    """
    현재 로그인 유저(me)가 소유한 에이전트인지 검증 후 반환.
    없거나 남의 에이전트면 404.
    """
    agent = ai_agent_crud.get_for_owner(
        db,
        owner_id=me.user_id,
        agent_id=agent_id,
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 에이전트를 찾을 수 없거나 권한이 없어.",
        )
    return agent


# =========================================
# AIAgent 메타 CRUD
# =========================================
def create_agent(
    db: Session,
    *,
    me: AppUser,
    data: AIAgentCreate,
) -> AIAgent:
    """
    새 에이전트 생성.
    - owner_id는 항상 me.user_id 로 강제.
    """
    agent = ai_agent_crud.create(
        db,
        obj_in=data,
        owner_id=me.user_id,
    )
    return agent


def list_my_agents(
    db: Session,
    *,
    me: AppUser,
    limit: int,
    offset: int,
    project_id: Optional[int] = None,
    q: Optional[str] = None,
) -> Tuple[int, List[AIAgent]]:
    """
    owner_id = me.user_id 기준 에이전트 목록 조회.
    """
    total, items = ai_agent_crud.list_by_owner(
        db,
        owner_id=me.user_id,
        limit=limit,
        offset=offset,
        project_id=project_id,
        q=q,
    )
    return total, items


def get_my_agent(
    db: Session,
    *,
    me: AppUser,
    agent_id: int,
) -> AIAgent:
    """
    단일 에이전트 조회 (소유자 검증 포함).
    """
    return ensure_my_agent(db, agent_id, me)


def update_my_agent(
    db: Session,
    *,
    me: AppUser,
    agent_id: int,
    data: AIAgentUpdate,
) -> AIAgent:
    """
    내 에이전트 메타데이터 수정.
    """
    agent = ai_agent_crud.update_for_owner(
        db,
        owner_id=me.user_id,
        agent_id=agent_id,
        obj_in=data,
    )
    if agent is None:
        # 소유자가 아니거나 존재하지 않는 경우
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 에이전트를 찾을 수 없거나 권한이 없어.",
        )
    return agent


# =========================================
# AgentPrompt (버전 관리)
# =========================================
def get_active_prompt_for_agent(
    db: Session,
    *,
    me: AppUser,
    agent_id: int,
) -> Optional[AgentPrompt]:
    """
    해당 에이전트의 활성 프롬프트 한 개 반환.
    - 없으면 None
    """
    # 권한 체크
    ensure_my_agent(db, agent_id, me)

    prompt: Optional[AgentPrompt] = (
        db.query(AgentPrompt)
        .filter(
            AgentPrompt.agent_id == agent_id,
            AgentPrompt.is_active.is_(True),
        )
        .order_by(AgentPrompt.version.desc())
        .first()
    )
    return prompt


def upsert_prompt_for_agent(
    db: Session,
    *,
    me: AppUser,
    agent_id: int,
    data: AgentPromptCreate,
) -> AgentPrompt:
    """
    새로운 프롬프트 버전을 생성하고 활성화한다.
    - 기존 활성 프롬프트들은 is_active=False 로 비활성화.
    - version = (agent_id 기준 max(version) + 1)
    """
    # 권한 체크
    ensure_my_agent(db, agent_id, me)

    # 다음 버전 번호 계산
    max_version: Optional[int] = (
        db.query(func.max(AgentPrompt.version))
        .filter(AgentPrompt.agent_id == agent_id)
        .scalar()
    )
    next_version = (max_version or 0) + 1

    # 기존 활성 프롬프트 비활성화
    (
        db.query(AgentPrompt)
        .filter(
            AgentPrompt.agent_id == agent_id,
            AgentPrompt.is_active.is_(True),
        )
        .update(
            {"is_active": False},
            synchronize_session=False,
        )
    )

    # 새 버전 생성
    prompt = AgentPrompt(
        agent_id=agent_id,
        version=next_version,
        system_prompt=data.system_prompt,
        is_active=True,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt
