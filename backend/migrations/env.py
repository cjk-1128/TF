"""Alembic 运行环境：绑定 TerraForge 的 SQLAlchemy Base 与数据库配置。

支持：
- SQLite / MySQL / PostgreSQL 一套迁移通吃（URL 来自 app.core.config）
- SQLite 的 ALTER 支持（render_as_batch=True，未来改列/删列可安全迁移）
- 类型比对（compare_type=True，避免字段类型漂移）
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.session import Base

# 触发所有模型注册到 Base.metadata（必须 import，否则迁移检测不到表）
import app.models  # noqa: F401

config = context.config

# 用 settings 覆盖 sqlalchemy.url，避免明文写在 ini 里
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    """统一配置：SQLite 启用 batch 模式以支持 ALTER。"""
    opts = {
        "target_metadata": target_metadata,
        "render_as_batch": settings.DATABASE_URL.startswith("sqlite"),
        "compare_type": True,
        "compare_server_default": True,
    }
    opts.update(kwargs)
    return opts


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(url=url, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, **_configure())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_configure())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
