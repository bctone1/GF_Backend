# app/endpoints/user/agent.py
from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
    Body,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.agent import (
    AIAgentResponse,
    AIAgentCreate,
    AIAgentUpdate,
    AgentShareResponse,
    AgentForkRequest,
)
from service.user.agent_share import (
    share_agent_to_class,
    deactivate_agent_share,
)
from service.user.agent import (
    create_agent,
    list_my_agents,
    get_my_agent,
    update_my_agent,
    fork_shared_agent_to_my_agent,
    list_shared_agents_for_class,
)

router = APIRouter()


# =========================================
# (학생용) class 기준 공유 에이전트 목록
# =========================================
@router.get(
    "/agents/shared",
    response_model=List[AIAgentResponse],
    summary="class 에 공유된 에이전트 목록 조회",
    operation_id="list_shared_agents_for_class",
)
def list_shared_agents_for_class_endpoint(
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 에이전트를 조회할 강의실 ID (partner.classes.id)",
    ),
    active_only: bool = Query(
        True,
        description="true 이면 활성 공유(is_active=true)만 조회",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 class 에 공유된 에이전트 목록을 조회한다.

    현재 서비스 로직:
    - me가 해당 class에 'active' 상태로 등록된 수강생(enrollment)인 경우에만 조회 가능.
    """
    agents = list_shared_agents_for_class(
        db=db,
        class_id=class_id,
        me=me,
        active_only=active_only,
    )
    return agents


# =========================================
# 공유 에이전트 → 내 에이전트로 포크
# =========================================
@router.post(
    "/agents/{agent_id}/fork",
    response_model=AIAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공유 에이전트를 내 에이전트로 복제(수강생 전용)",
    operation_id="fork_shared_agent_to_my_agent",
)
def fork_shared_agent_to_my_agent_endpoint(
    agent_id: int = Path(..., ge=1),
    payload: AgentForkRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - agent_id: 강사가 만든 원본 에이전트 ID
    - payload.class_id: 이 에이전트가 공유된 class_id

    서비스 로직:
    - agent_id가 class_id에 공유(is_active=true) 되어 있어야 하고
    - me가 그 class에 'active' 상태로 등록된 수강생이어야 포크 가능
    """
    new_agent = fork_shared_agent_to_my_agent(
        db=db,
        agent_id=agent_id,
        class_id=payload.class_id,
        me=me,
        new_name=payload.name,
    )
    return new_agent


# =========================================
# 내 에이전트 카드 CRUD
# =========================================
@router.post(
    "/agents",
    response_model=AIAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="새 에이전트 생성",
    operation_id="create_my_agent",
)
def create_my_agent_endpoint(
    body: AIAgentCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    에이전트 생성.
    - owner_id는 서버에서 me.user_id로 채움
    - system_prompt는 생성 시 함께 저장
    """
    agent = create_agent(db=db, me=me, data=body)
    return agent


@router.get(
    "/agents",
    response_model=Page[AIAgentResponse],
    summary="내 에이전트 목록 조회",
    operation_id="list_my_agents",
)
def list_my_agents_endpoint(
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(
        None, description="에이전트 이름/역할 설명 검색 키워드"
    ),
):
    """
    내(owner_id=me.user_id) 에이전트 목록을 페이징 조회.
    - q로 name / role_description LIKE 검색 가능
    """
    total, agents = list_my_agents(
        db=db,
        me=me,
        limit=limit,
        offset=offset,
        q=q,
    )
    return {
        "total": total,
        "items": agents,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/agents/{agent_id}",
    response_model=AIAgentResponse,
    summary="내 에이전트 상세 조회",
    operation_id="get_my_agent",
)
def get_my_agent_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="조회할 내 에이전트 ID (user.ai_agents.agent_id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    단일 에이전트 상세 조회.
    - owner_id != me.user_id 이면 404 처리 (서비스 레이어에서 검증)
    """
    agent = get_my_agent(db=db, me=me, agent_id=agent_id)
    return agent


@router.patch(
    "/agents/{agent_id}",
    response_model=AIAgentResponse,
    summary="내 에이전트 수정",
    operation_id="update_my_agent",
)
def update_my_agent_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="수정할 내 에이전트 ID (user.ai_agents.agent_id)",
    ),
    body: AIAgentUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    에이전트 수정.
    - name / role_description / system_prompt / template_source / is_active
    """
    agent = update_my_agent(db=db, me=me, agent_id=agent_id, data=body)
    return agent


# =========================================
# 강사용: 내 에이전트를 특정 class 에 공유
# =========================================
@router.post(
    "/agents/{agent_id}/share",
    response_model=AgentShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="내 에이전트를 내 class 에 공유",
    operation_id="share_agent_to_class",
)
def share_agent_to_class_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="공유할 내 에이전트 ID (user.ai_agents.agent_id)",
    ),
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 대상 강의실 ID (partner.classes.id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    강사의 개인 에이전트를 특정 class 에 공유한다.

    검증:
    - agent_id 존재 여부
    - 해당 에이전트 owner_id == me.user_id
    - class_id 존재 + 내가 그 class 담당 강사인지
    """
    share = share_agent_to_class(
        db=db,
        agent_id=agent_id,
        class_id=class_id,
        me=me,
    )
    return share


@router.delete(
    "/agents/{agent_id}/share",
    response_model=AgentShareResponse,
    summary="특정 class 에 대한 에이전트 공유 비활성화",
    operation_id="deactivate_agent_share",
)
def deactivate_agent_share_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="공유 해제할 내 에이전트 ID (user.ai_agents.agent_id)",
    ),
    class_id: int = Query(
        ...,
        ge=1,
        description="공유 해제 대상 강의실 ID (partner.classes.id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 class 에 대한 내 에이전트 공유를 비활성화한다.
    """
    share = deactivate_agent_share(
        db=db,
        agent_id=agent_id,
        class_id=class_id,
        me=me,
    )
    return share
