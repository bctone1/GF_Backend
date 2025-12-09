# service/user/agent.py
from __future__ import annotations

from typing import Optional, Tuple, List

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.user.account import AppUser
from models.user.agent import AIAgent, AgentPrompt, AgentShare
from schemas.user.agent import (
    AIAgentCreate,
    AIAgentUpdate,
    AgentPromptCreate,
)
from crud.user.agent import ai_agent_crud
from models.partner.student import Student, Enrollment
from models.partner.course import Class


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
            detail="해당 에이전트를 찾을 수 없거나 권한이 없음.",
        )
    return agent


def ensure_enrolled_in_class(
    db: Session,
    *,
    class_id: int,
    user_id: int,
) -> None:
    """
    주어진 user_id 가 해당 class_id 에 'active' 상태로 수강 중인지 검증.
    - 없으면 403 Forbidden.
    """
    enrollment = (
        db.query(Enrollment)
        .join(Student, Enrollment.student_id == Student.id)
        .filter(
            Enrollment.class_id == class_id,
            Student.user_id == user_id,
            Enrollment.status == "active",
        )
        .first()
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 강의에 수강 중인 학생이 아니라서 사용할 수 없음",
        )


def list_shared_agents_for_class(
    db: Session,
    *,
    class_id: int,
    me: AppUser,
    active_only: bool = True,
) -> List[AIAgent]:
    """
    특정 class 에 공유된 에이전트 목록 조회.
    - 현재는 '해당 강의에 수강 중인 학생'만 허용.
      (나중에 강사 권한 허용 로직을 추가해도 됨)
    """
    # 0) 강의 존재 여부 체크
    cls = (
        db.query(Class)
        .filter(Class.id == class_id)
        .first()
    )
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없음.",
        )

    # 1) me 가 이 class 의 수강생인지 검증 (수강생만 조회 가능)
    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    # 2) 공유 에이전트 목록 조회
    q = (
        db.query(AIAgent)
        .join(AgentShare, AgentShare.agent_id == AIAgent.agent_id)
        .filter(AgentShare.class_id == class_id)
    )
    if active_only:
        q = q.filter(AgentShare.is_active.is_(True))

    return q.all()


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


# =========================================
# 공유 에이전트 → 내 에이전트로 포크
# =========================================
def fork_shared_agent_to_my_agent(
    db: Session,
    *,
    agent_id: int,
    class_id: int,
    me: AppUser,
    new_name: Optional[str] = None,
) -> AIAgent:
    """
    특정 class 에 공유된 강사 에이전트를
    현재 로그인 유저(me)의 '내 에이전트'로 복제.
    """
    # 1) 이 agent 가 해당 class 에 공유되어 있는지 + 활성인지 확인
    share: Optional[AgentShare] = (
        db.query(AgentShare)
        .filter(
            AgentShare.agent_id == agent_id,
            AgentShare.class_id == class_id,
            AgentShare.is_active.is_(True),
        )
        .first()
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 에이전트를 찾을 수 없음.",
        )

    # 2) me 가 이 class 의 수강생(enrollment)인지 검증
    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    # 3) 원본 에이전트 조회 (소유자와 무관)
    src_agent: Optional[AIAgent] = (
        db.query(AIAgent)
        .filter(AIAgent.agent_id == agent_id)
        .first()
    )
    if src_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="원본 에이전트를 찾을 수 없어.",
        )

    # 4) 원본 활성 시스템 프롬프트 조회
    src_prompt: Optional[AgentPrompt] = (
        db.query(AgentPrompt)
        .filter(
            AgentPrompt.agent_id == agent_id,
            AgentPrompt.is_active.is_(True),
        )
        .order_by(AgentPrompt.version.desc())
        .first()
    )
    if src_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="원본 에이전트에 활성 시스템 프롬프트가 없음.",
        )

    # 5) 새 에이전트 생성 (owner_id = me.user_id)
    agent_in = AIAgentCreate(
        name=new_name or f"{src_agent.name} - 내 버전",
        role_description=src_agent.role_description,
        status="active",
        template_source="class_shared",  # 원본이 class 공유에서 왔다는 표시
        project_id=None,
        knowledge_id=src_agent.knowledge_id,
    )
    new_agent = ai_agent_crud.create(
        db,
        obj_in=agent_in,
        owner_id=me.user_id,
    )

    # 6) 프롬프트 복제: 내 새 에이전트에 활성 버전으로 하나 생성
    upsert_prompt_for_agent(
        db=db,
        me=me,
        agent_id=new_agent.agent_id,
        data=AgentPromptCreate(
            system_prompt=src_prompt.system_prompt,
        ),
    )

    return new_agent
