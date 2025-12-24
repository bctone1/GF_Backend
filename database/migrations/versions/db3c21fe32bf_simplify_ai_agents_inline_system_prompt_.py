"""simplify ai_agents: inline system_prompt, drop agent_prompts

Revision ID: db3c21fe32bf
Revises: ac81cd797f6f
Create Date: 2025-12-17 17:57:54.090779
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "db3c21fe32bf"
down_revision: Union[str, Sequence[str], None] = "ac81cd797f6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ---------------------------------------------------------
    # 0) agent_prompts 테이블 제거 (없어도 안 터지게)
    # ---------------------------------------------------------
    op.execute('DROP TABLE IF EXISTS "user".agent_prompts CASCADE')

    # ---------------------------------------------------------
    # 1) ai_agents: system_prompt / is_active 추가 (없으면 생성)
    #    - 기존 row가 있어도 NOT NULL 추가가 터지지 않게 DEFAULT로 backfill
    # ---------------------------------------------------------
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ADD COLUMN IF NOT EXISTS system_prompt TEXT NOT NULL DEFAULT '';
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
        """
    )

    # 앞으로는 API가 system_prompt를 항상 넣는 정책이니까 DEFAULT 제거
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ALTER COLUMN system_prompt DROP DEFAULT;
        """
    )

    # ---------------------------------------------------------
    # 2) ai_agents: 구 컬럼 제거 (없어도 안 터지게)
    # ---------------------------------------------------------
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        DROP COLUMN IF EXISTS project_id CASCADE;
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        DROP COLUMN IF EXISTS knowledge_id CASCADE;
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        DROP COLUMN IF EXISTS status CASCADE;
        """
    )

    # ---------------------------------------------------------
    # 3) 인덱스 정리
    #    - 예전 인덱스명/존재 여부가 달라도 안 터지게 DROP IF EXISTS
    #    - 새 인덱스는 생성 전에 DROP IF EXISTS로 중복 방지
    # ---------------------------------------------------------
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_owner_status')
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_project')
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_document')

    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_owner_active')
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_owner_created_at')

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_agents_owner_active
        ON "user".ai_agents (owner_id, is_active);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_agents_owner_created_at
        ON "user".ai_agents (owner_id, created_at);
        """
    )


def downgrade():
    # 되돌릴 일이 거의 없을 거라서, downgrade도 "안 터지는" 쪽으로만 구성

    # 1) 새 인덱스 제거
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_owner_created_at')
    op.execute('DROP INDEX IF EXISTS "user".idx_ai_agents_owner_active')

    # 2) 구 컬럼 복구 (없으면 생성)
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ADD COLUMN IF NOT EXISTS project_id BIGINT;
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ADD COLUMN IF NOT EXISTS knowledge_id BIGINT;
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';
        """
    )
    # status DEFAULT는 예전 정책 유지
    # (원하면 DROP DEFAULT는 생략)

    # 3) 새 컬럼 제거
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        DROP COLUMN IF EXISTS is_active CASCADE;
        """
    )
    op.execute(
        """
        ALTER TABLE "user".ai_agents
        DROP COLUMN IF EXISTS system_prompt CASCADE;
        """
    )

    # 4) 예전 인덱스 복구 (있으면 스킵)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_agents_owner_status
        ON "user".ai_agents (owner_id, status);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_agents_project
        ON "user".ai_agents (project_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_agents_document
        ON "user".ai_agents (knowledge_id);
        """
    )

    # 5) agent_prompts 테이블 복구 (간단 버전)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS "user".agent_prompts (
            prompt_id BIGSERIAL PRIMARY KEY,
            agent_id BIGINT NOT NULL REFERENCES "user".ai_agents(agent_id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            system_prompt TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT false,
            CONSTRAINT uq_agent_prompts_agent_version UNIQUE (agent_id, version)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_prompts_agent
        ON "user".agent_prompts (agent_id);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_prompts_active_once
        ON "user".agent_prompts (agent_id)
        WHERE (is_active = true);
        """
    )
