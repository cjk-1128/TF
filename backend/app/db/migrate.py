"""TerraForge 数据库迁移执行辅助。

用于让应用启动（init_db）自动执行 `alembic upgrade head`，
使数据库 schema 始终与代码模型保持版本一致——替代原先
`Base.metadata.create_all` 只能"新增"不能"修改/删除"的缺陷。
"""
from __future__ import annotations

import os

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_config() -> Config:
    ini_path = os.path.join(_BACKEND_ROOT, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(_BACKEND_ROOT, "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    cfg.attributes["configure_logger"] = False
    return cfg


def run_migrations() -> None:
    """执行迁移到最新版本（head）。"""
    cfg = _make_config()
    command.upgrade(cfg, "head")
    logger.info("数据库迁移已同步至最新版本 | %s", settings.DATABASE_URL.split("@")[-1])


def stamp_head() -> None:
    """把当前数据库标记为已是最新版本（不执行建表，用于已有库接管）。"""
    cfg = _make_config()
    command.stamp(cfg, "head")
    logger.info("已将现有数据库标记为最新版本（stamp head）")
