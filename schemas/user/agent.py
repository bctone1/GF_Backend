from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict

from schemas.base import ORMBase


# =========================================================
# user.ai_agents
# =========================================================
class AIAgentCreate(ORMBase):
    """
    에이전트 생성용 입력 스키마.
    - owner_id는 서버에서 me.user_id로 채운다.
    - status는 지정 안 하면 DB server_default('draft') 사용.
    """
    model_config = ConfigDict(from_attributes=False)

    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    name: str
    role_description: Optional[str] = None
    status: Optional[str] = None          # 'draft' | 'active' 등 (옵션)
    template_source: Optional[str] = None


class AIAgentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    name: Optional[str] = None
    role_description: Optional[str] = None
    status: Optional[str] = None
    template_source: Optional[str] = None


class AIAgentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    agent_id: int
    owner_id: int
    project_id: Optional[int] = None
    knowledge_id: Optional[int] = None
    name: str
    role_description: Optional[str] = None
    status: str
    template_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =========================================================
# user.agent_prompts
#   - 프론트는 system_prompt만 보내고,
#   - version / is_active / agent_id는 서버가 관리
# =========================================================
class AgentPromptCreate(ORMBase):
    """
    /agents/{agent_id}/prompt 저장용 입력 스키마.
    - agent_id, version, is_active는 서버에서 처리.
    """
    model_config = ConfigDict(from_attributes=False)

    system_prompt: str


class AgentPromptUpdate(ORMBase):
    """
    필요 시 부분 수정용이나,
    /agents/{agent_id}/prompt 는 보통 새 버전 생성(Upsert)로 사용.
    """
    model_config = ConfigDict(from_attributes=False)

    system_prompt: Optional[str] = None


class AgentPromptResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    prompt_id: int
    agent_id: int
    version: int
    system_prompt: str
    created_at: datetime
    is_active: bool


# =========================================================
# user.agent_examples
# =========================================================
class AgentExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    agent_id: int
    example_type: Optional[str] = None     # server default 'few_shot'
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None


class AgentExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    example_type: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None


class AgentExampleResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    example_id: int
    agent_id: int
    example_type: str
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None
    created_at: datetime


# =========================================================
# user.agent_usage_stats  (집계/통계: READ-ONLY)
# =========================================================
class AgentUsageStatResponse(ORMBase):
    """
    집계/통계용 테이블이므로 Create/Update는 두지 않고
    조회용 Response만 둔다.
    """
    model_config = ConfigDict(from_attributes=True)

    usage_stat_id: int
    agent_id: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    avg_rating: Optional[Decimal] = None   # 0~5
    total_tokens: int


# =========================================================
# user.agent_shares
# =========================================================
class AgentShareCreate(ORMBase):
    """
    강사가 자신의 에이전트를 특정 class에 공유할 때 쓰는 입력 스키마.
    - shared_by_user_id는 서버에서 me.user_id로 채우는 구조를 권장.
    - is_active는 지정 안 하면 server_default true.
    """
    model_config = ConfigDict(from_attributes=False)

    agent_id: int
    class_id: int
    is_active: Optional[bool] = None   # server default true


class AgentShareUpdate(ORMBase):
    """
    주로 is_active 토글용 (비활성화 등).
    """
    model_config = ConfigDict(from_attributes=False)

    is_active: Optional[bool] = None


class AgentShareResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    share_id: int
    agent_id: int
    class_id: int
    shared_by_user_id: int
    is_active: bool
    created_at: datetime
