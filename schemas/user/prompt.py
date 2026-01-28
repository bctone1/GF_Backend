# schemas/user/prompt.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict

from schemas.base import ORMBase


# =========================================================
# user.ai_prompts
#   - system_prompt는 ai_prompts에 직접 저장
#   - is_active는 Boolean (default true)
# =========================================================
class AIPromptCreate(ORMBase):
    """
    프롬프트 생성용 입력 스키마.
    - owner_id는 서버에서 me.user_id로 채운다.
    - is_active는 지정 안 하면 DB server_default(true) 사용.
    """
    model_config = ConfigDict(from_attributes=False)

    name: str
    role_description: Optional[str] = None
    system_prompt: str
    template_source: Optional[str] = None
    is_active: Optional[bool] = None  # server default true


class AIPromptUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    name: Optional[str] = None
    role_description: Optional[str] = None
    system_prompt: Optional[str] = None
    template_source: Optional[str] = None
    is_active: Optional[bool] = None


class AIPromptResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    prompt_id: int
    owner_id: int
    name: str
    role_description: Optional[str] = None
    system_prompt: str
    template_source: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =========================================================
# user.prompt_examples
# =========================================================
class PromptExampleCreate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    prompt_id: int
    example_type: Optional[str] = None  # server default 'few_shot'
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None


class PromptExampleUpdate(ORMBase):
    model_config = ConfigDict(from_attributes=False)

    example_type: Optional[str] = None
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None


class PromptExampleResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    example_id: int
    prompt_id: int
    example_type: str
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    position: Optional[int] = None
    created_at: datetime


# =========================================================
# user.prompt_usage_stats (집계/통계: READ-ONLY)
# =========================================================
class PromptUsageStatResponse(ORMBase):
    """
    집계/통계용 테이블이므로 Create/Update는 두지 않고
    조회용 Response만 둔다.
    """
    model_config = ConfigDict(from_attributes=True)

    usage_stat_id: int
    prompt_id: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    avg_rating: Optional[Decimal] = None  # 0~5
    total_tokens: int


# =========================================================
# user.prompt_shares
# =========================================================
class PromptShareCreate(ORMBase):
    """
    강사가 자신의 프롬프트를 특정 class에 공유할 때 쓰는 입력 스키마.
    - shared_by_user_id는 서버에서 me.user_id로 채우는 구조를 권장.
    - is_active는 지정 안 하면 server_default true.
    """
    model_config = ConfigDict(from_attributes=False)

    prompt_id: int
    class_id: int
    is_active: Optional[bool] = None  # server default true


class PromptShareUpdate(ORMBase):
    """
    주로 is_active 토글용 (비활성화 등).
    """
    model_config = ConfigDict(from_attributes=False)

    is_active: Optional[bool] = None


class PromptShareResponse(ORMBase):
    model_config = ConfigDict(from_attributes=True)

    share_id: int
    prompt_id: int
    class_id: int
    shared_by_user_id: int
    is_active: bool
    created_at: datetime


# =========================================================
# 공유 프롬프트 → 내 프롬프트 포크(복붙) 요청
# =========================================================
class PromptForkRequest(ORMBase):
    """
    공유된 강사 프롬프트를 '내 프롬프트'로 복제할 때 사용하는 입력 스키마.
    - class_id: 이 프롬프트가 공유된 강의 ID
    - name: 내 프롬프트로 복제할 때 사용할 이름 (없으면 서버에서 기본값 생성)
    """
    model_config = ConfigDict(from_attributes=False)

    class_id: int
    name: Optional[str] = None
