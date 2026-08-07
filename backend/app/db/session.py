"""数据库会话管理：SQLAlchemy 2.0 同步引擎（MySQL / SQLite 双兼容）。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

Base = declarative_base()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.DB_ECHO, "pool_pre_ping": True, "future": True}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=3600,
    )

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                            expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """脚本/后台任务用。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库：优先走 Alembic 迁移（版本化管理，支持改/删字段），
    失败则回退到 create_all（仅新增表，向后兼容旧环境）。"""
    from app import models  # noqa: F401  触发模型注册
    try:
        from app.db.migrate import run_migrations
        run_migrations()
        logger.info("数据库迁移完成 | %s", settings.DATABASE_URL.split("@")[-1])
    except Exception as exc:  # pragma: no cover - 兜底，保证服务可启动
        logger.warning("Alembic 迁移失败，回退 create_all: %s", exc)
        Base.metadata.create_all(bind=engine)
        logger.info("数据库初始化完成(create_all) | %s", settings.DATABASE_URL.split("@")[-1])
    _seed_default_user()


def _seed_default_user() -> None:
    """首次启动若 tf_user 为空，创建默认管理员（api_key 取自 BOOTSTRAP_API_KEY）。"""
    from app.models.identity import ROLE_ADMIN, User
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(
                username="admin", display_name="默认管理员",
                api_key=settings.BOOTSTRAP_API_KEY, role=ROLE_ADMIN,
                tenant_id=settings.DEFAULT_TENANT_ID))
            db.commit()
            logger.info("已创建默认管理员 | username=admin | api_key=%s",
                        settings.BOOTSTRAP_API_KEY)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("默认管理员 seed 失败（可忽略）: %s", exc)
    finally:
        db.close()
