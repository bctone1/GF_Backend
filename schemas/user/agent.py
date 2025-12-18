# schemas/user/agent.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict

from schemas.base import ORMBase


# =========================================================
# user.ai_agents
#   - system_prompt는 ai_agents에 직접 저장
#   - is_active는 Boolean (default true)
# =========================================================
class AIAgentCreate(ORMBase):
    """
    에이전트 생성용 입력 스키마.
    - owner_id는 서버에서 me.user_id로 채운다.
    - is_active는 지정 안 하면 DB server_default(true) 사용.
    """
    model_config = ConfigDict(from_attributes=False)

    name: str
    role_description: Optional[str] = None
    system_prompt: str
    template_source: Optional[str] = None
    is_active: Optional[bool] = None  # server default true


class AIAgentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    role_description: Optional[str] = None
    system_prompt: Optional[str] = None
    template_source: Optional[str] = None
    is_active: Optional[bool] = None


class AIAgentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    agent_id: int
    owner_id: int
    name: str
    role_description: Optional[str] = None
    system_prompt: str
    template_source: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =========================================================
# user.agent_examples
# =========================================================
class AgentExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    agent_id: int
    example_type: Optional[str] = None  # server default 'few_shot'
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
    avg_rating: Optional[Decimal] = None  # 0~5
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
    is_active: Optional[bool] = None  # server default true


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


# =========================================================
# 공유 에이전트 → 내 에이전트 포크(복붙) 요청
# =========================================================
class AgentForkRequest(ORMBase):
    """
    공유된 강사 에이전트를 '내 에이전트'로 복제할 때 사용하는 입력 스키마.
    - class_id: 이 에이전트가 공유된 강의 ID
    - name: 내 에이전트로 복제할 때 사용할 이름 (없으면 서버에서 기본값 생성)
    """
    model_config = ConfigDict(from_attributes=False)

    class_id: int
    name: Optional[str] = None
