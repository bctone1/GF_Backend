# app/endpoints/user/agent.py
from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
    HTTPException,
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
    AgentPromptCreate,
    AgentPromptResponse,
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
    get_active_prompt_for_agent,
    upsert_prompt_for_agent,
    fork_shared_agent_to_my_agent,
    list_shared_agents_for_class,
)


router = APIRouter()


# =========================================
# (강사용/학생용) class 기준 공유 에이전트 목록
# =========================================
@router.get(
    "/agents/shared",
    response_model=List[AIAgentResponse],
    summary="class 에 공유된 에이전트 목록 조회(강사/수강생)",
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

    서비스 레이어 로직 기준:
    - me 가 해당 class 의 담당 강사이거나,
    - 해당 class 에 'active' 상태로 등록된 수강생(enrollment)인 경우에만 조회 가능.

    실제 권한 검사는 service.user.agent_share.list_shared_agents_for_class 에서 처리한다.
    """
    agents = list_shared_agents_for_class(
        db=db,
        class_id=class_id,
        me=me,
        active_only=active_only,
    )
    # AIAgentResponse.from_orm 으로 자동 변환 (from_attributes=True)
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
    - me: 현재 로그인한 학생/사용자

    서비스 레이어 로직 기준:
    - 해당 agent_id 가 payload.class_id 에 공유(is_active=true) 되어 있어야 하고,
    - me 가 그 class 에 'active' 상태로 등록된 수강생(enrollment)이어야 포크 가능.
      (service.user.agent.ensure_enrolled_in_class 에서 검증)
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
# NEW: 내 에이전트 카드 CRUD
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
    my-agents.html 왼쪽 카드에서 사용하는 **에이전트 생성** API.
    - owner_id 는 항상 현재 로그인 유저(me.user_id)로 서버에서 채운다.
    """
    agent = create_agent(db=db, me=me, data=body)
    return agent


@router.put(
    "/agents/{agent_id}/prompt",
    response_model=AgentPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="에이전트 프롬프트 저장(새 버전 생성)",
    operation_id="upsert_prompt_for_agent",
)
def upsert_prompt_for_agent_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="프롬프트를 저장할 에이전트 ID (user.ai_agents.agent_id)",
    ),
    body: AgentPromptCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - 항상 **새 버전**을 생성한다.
    - 기존 is_active=True 프롬프트들은 모두 is_active=False 로 비활성화.
    - 프론트는 system_prompt 문자열만 보내면 된다.
    """
    prompt = upsert_prompt_for_agent(
        db=db,
        me=me,
        agent_id=agent_id,
        data=body,
    )
    return prompt


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
    project_id: Optional[int] = Query(
        None, description="특정 프로젝트에 속한 에이전트만 필터링"
    ),
    q: Optional[str] = Query(
        None, description="에이전트 이름/역할 설명 검색 키워드"
    ),
):
    """
    내(owner_id=me.user_id) 에이전트 목록을 페이징 조회.
    - project_id 로 필터 가능
    - q 로 name / role_description LIKE 검색 가능
    """
    total, agents = list_my_agents(
        db=db,
        me=me,
        limit=limit,
        offset=offset,
        project_id=project_id,
        q=q,
    )
    # Page 스키마 구조(page/size vs limit/offset)에 맞게 이 부분은
    # 정의한 Page에 맞춰서만 한번 더 점검하면 됨.
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
    summary="내 에이전트 메타데이터 수정",
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
    에이전트 카드 메타데이터 수정.
    - project_id / knowledge_id / name / role_description / status / template_source
    """
    agent = update_my_agent(db=db, me=me, agent_id=agent_id, data=body)
    return agent


# =========================================
# NEW: 프롬프트(AgentPrompt) 조회
# =========================================
@router.get(
    "/agents/{agent_id}/prompt",
    response_model=AgentPromptResponse,
    summary="해당 에이전트의 활성 프롬프트 조회",
    operation_id="get_active_prompt_for_agent",
)
def get_active_prompt_for_agent_endpoint(
    agent_id: int = Path(
        ...,
        ge=1,
        description="프롬프트를 조회할 에이전트 ID (user.ai_agents.agent_id)",
    ),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    에이전트의 현재 활성(system_prompt) 버전 1개만 조회.
    - 없으면 404 반환 → 프론트는 에디터를 빈 상태로 열면 됨.
    """
    prompt = get_active_prompt_for_agent(db=db, me=me, agent_id=agent_id)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성화된 프롬프트가 아직 없어.",
        )
    return prompt


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
    - agent_id 가 실제 존재하는지
    - 해당 에이전트의 owner_id == me.user_id 인지 (내 에이전트인지)
    - class_id 가 존재하고, 내가 그 class 의 담당 강사인지
    """
    share = share_agent_to_class(
        db=db,
        agent_id=agent_id,
        class_id=class_id,
        me=me,
    )
    return share


# =========================================
# 강사용: 특정 class 에 대한 에이전트 공유 비활성화
# =========================================
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

    검증:
    - agent_id 가 실제 존재하는지
    - 해당 에이전트의 owner_id == me.user_id 인지
    - class_id 가 존재하고, 내가 그 class 의 담당 강사인지
    - 해당 조합(agent_id + class_id)의 share row 존재 여부
    """
    share = deactivate_agent_share(
        db=db,
        agent_id=agent_id,
        class_id=class_id,
        me=me,
    )
    return share
