# schemas/user/agent.py
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
    model_config = ConfigDict(from_attributes=False)
    owner_id: int
    project_id: Optional[int] = None
    document_id: Optional[int] = None
    name: str
    role_description: Optional[str] = None
    status: Optional[str] = None          # server default 'draft'
    icon: Optional[str] = None
    template_source: Optional[str] = None


class AIAgentUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    project_id: Optional[int] = None
    document_id: Optional[int] = None
    name: Optional[str] = None
    role_description: Optional[str] = None
    status: Optional[str] = None
    icon: Optional[str] = None
    template_source: Optional[str] = None


class AIAgentResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    agent_id: int
    owner_id: int
    project_id: Optional[int] = None
    document_id: Optional[int] = None
    name: str
    role_description: Optional[str] = None
    status: str
    icon: Optional[str] = None
    template_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =========================================================
# user.agent_prompts
# =========================================================
class AgentPromptCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    agent_id: int
    version: int
    system_prompt: str
    is_active: Optional[bool] = None       # server default false


class AgentPromptUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    version: Optional[int] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


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
# user.agent_usage_stats
# =========================================================
class AgentUsageStatCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    agent_id: int
    usage_count: Optional[int] = None      # server default 0
    last_used_at: Optional[datetime] = None
    avg_rating: Optional[Decimal] = None   # 0~5
    total_tokens: Optional[int] = None     # server default 0


class AgentUsageStatUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)
    usage_count: Optional[int] = None
    last_used_at: Optional[datetime] = None
    avg_rating: Optional[Decimal] = None
    total_tokens: Optional[int] = None


class AgentUsageStatResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)
    usage_stat_id: int
    agent_id: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    avg_rating: Optional[Decimal] = None
    total_tokens: int
