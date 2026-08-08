"""统一日志：控制台 + 按天滚动文件，带 trace_id / tenant 上下文。

格式由 settings.LOG_FORMAT 控制：
- "text"（默认）：管道分隔单行，便于人读；
- "json"：结构化 JSON，便于日志采集/检索（Phase 4 可观测性）。
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_tenant: ContextVar[str] = ContextVar("tenant", default="-")

_FMT = "%(asctime)s | %(levelname)-7s | %(trace_id)s | %(name)s:%(lineno)d | %(message)s"


def new_trace_id() -> str:
    tid = uuid.uuid4().hex[:12]
    _trace_id.set(tid)
    return tid


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid)


def get_trace_id() -> str:
    return _trace_id.get()


def set_tenant_id(tid: str) -> None:
    _tenant.set(tid or "-")


def get_tenant_id() -> str:
    return _tenant.get()


class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()
        record.tenant = _tenant.get()
        return True


class JsonFormatter(logging.Formatter):
    """结构化 JSON 输出：ts/level/trace_id/tenant/logger/line/msg(+exc)。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "trace_id": getattr(record, "trace_id", "-"),
            "tenant": getattr(record, "tenant", "-"),
            "logger": record.name,
            "line": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())
    root.handlers.clear()

    use_json = (settings.LOG_FORMAT or "text").lower() == "json"
    fmt: logging.Formatter = JsonFormatter() if use_json else logging.Formatter(_FMT)
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
