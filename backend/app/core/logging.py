"""统一日志：控制台 + 按天滚动文件，带 trace_id 上下文。"""
from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")

_FMT = "%(asctime)s | %(levelname)-7s | %(trace_id)s | %(name)s:%(lineno)d | %(message)s"


def new_trace_id() -> str:
    tid = uuid.uuid4().hex[:12]
    _trace_id.set(tid)
    return tid


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid)


def get_trace_id() -> str:
    return _trace_id.get()


class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()
        return True


_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())
    root.handlers.clear()

    fmt = logging.Formatter(_FMT)
    flt = _TraceFilter()

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.addFilter(flt)
    root.addHandler(ch)

    fh = TimedRotatingFileHandler(
        Path(settings.LOG_DIR) / "terraforge.log",
        when="midnight", backupCount=settings.LOG_RETENTION_DAYS, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.addFilter(flt)
    root.addHandler(fh)

    for noisy in ("httpx", "urllib3", "pymilvus", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
