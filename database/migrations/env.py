import os, sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if sys.path[0] != BASE_DIR:
    sys.path.insert(0, BASE_DIR)

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import importlib, inspect

importlib.invalidate_caches()
import models  # 디버그용: 어떤 models가 로드되는지 확인
print(">>> models loaded from:", inspect.getfile(models))

from models.base import Base
target_metadata = Base.metadata
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)



import models.supervisor.core
import models.supervisor.core
import models.supervisor.settings
import models.supervisor.ops
import models.supervisor.metrics
import models.supervisor.billing
import models.supervisor.reports
import models.supervisor.growth
import models.supervisor.env
import models.supervisor.api_usage
import models.partner.partner_core

import models.partner.student
import models.partner.session
import models.partner.catalog
import models.partner.course
import models.partner.prompt
import models.partner.compare
import models.partner.usage
import models.partner.billing
import models.partner.notify
import models.partner.analytics
import models.user.account
import models.user.prefs
import models.user.project
import models.user.document
import models.user.agent
import models.user.practice
import models.user.activity
import models.user.account_delete
import models.links.links

import models, inspect
print(">>> models file loaded from:", inspect.getfile(models))




def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


