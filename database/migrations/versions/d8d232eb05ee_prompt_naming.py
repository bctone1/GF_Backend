"""prompt_naming

Revision ID: d8d232eb05ee
Revises: b328f6ef1f1f
Create Date: 2026-01-28 16:54:00.714011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8d232eb05ee'
down_revision: Union[str, Sequence[str], None] = 'b328f6ef1f1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) parent table
    op.rename_table("ai_agents", "ai_prompts", schema="user")
    op.alter_column("ai_prompts", "agent_id", new_column_name="prompt_id", schema="user")

    # 2) children
    op.rename_table("agent_examples", "prompt_examples", schema="user")
    op.alter_column("prompt_examples", "agent_id", new_column_name="prompt_id", schema="user")

    op.rename_table("agent_usage_stats", "prompt_usage_stats", schema="user")
    op.alter_column("prompt_usage_stats", "agent_id", new_column_name="prompt_id", schema="user")

    op.rename_table("agent_shares", "prompt_shares", schema="user")
    op.alter_column("prompt_shares", "agent_id", new_column_name="prompt_id", schema="user")

    # (권장) 인덱스 rename: 실패 위험 줄이려고 IF EXISTS 사용
    op.execute('ALTER INDEX IF EXISTS "user".idx_ai_agents_owner_active RENAME TO idx_ai_prompts_owner_active')
    op.execute('ALTER INDEX IF EXISTS "user".idx_ai_agents_owner_created_at RENAME TO idx_ai_prompts_owner_created_at')
    op.execute('ALTER INDEX IF EXISTS "user".idx_agent_examples_agent_pos RENAME TO idx_prompt_examples_prompt_pos')
    op.execute('ALTER INDEX IF EXISTS "user".idx_agent_usage_stats_last_used RENAME TO idx_prompt_usage_stats_last_used')
    op.execute('ALTER INDEX IF EXISTS "user".idx_agent_shares_agent RENAME TO idx_prompt_shares_prompt')
    op.execute('ALTER INDEX IF EXISTS "user".idx_agent_shares_class RENAME TO idx_prompt_shares_class')

    # (선택) 시퀀스 rename (환경마다 이름이 다를 수 있어 선택 처리 권장)
    # op.execute('ALTER SEQUENCE IF EXISTS "user".ai_agents_agent_id_seq RENAME TO ai_prompts_prompt_id_seq')


def downgrade():
    # reverse order
    op.alter_column("prompt_shares", "prompt_id", new_column_name="agent_id", schema="user")
    op.rename_table("prompt_shares", "agent_shares", schema="user")

    op.alter_column("prompt_usage_stats", "prompt_id", new_column_name="agent_id", schema="user")
    op.rename_table("prompt_usage_stats", "agent_usage_stats", schema="user")

    op.alter_column("prompt_examples", "prompt_id", new_column_name="agent_id", schema="user")
    op.rename_table("prompt_examples", "agent_examples", schema="user")

    op.alter_column("ai_prompts", "prompt_id", new_column_name="agent_id", schema="user")
    op.rename_table("ai_prompts", "ai_agents", schema="user")

    op.execute('ALTER INDEX IF EXISTS "user".idx_ai_prompts_owner_active RENAME TO idx_ai_agents_owner_active')
    op.execute('ALTER INDEX IF EXISTS "user".idx_ai_prompts_owner_created_at RENAME TO idx_ai_agents_owner_created_at')
    op.execute('ALTER INDEX IF EXISTS "user".idx_prompt_examples_prompt_pos RENAME TO idx_agent_examples_agent_pos')
    op.execute('ALTER INDEX IF EXISTS "user".idx_prompt_usage_stats_last_used RENAME TO idx_agent_usage_stats_last_used')
    op.execute('ALTER INDEX IF EXISTS "user".idx_prompt_shares_prompt RENAME TO idx_agent_shares_agent')
    op.execute('ALTER INDEX IF EXISTS "user".idx_prompt_shares_class RENAME TO idx_agent_shares_class')
