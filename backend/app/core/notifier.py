"""治理任务/告警通知（可选）。

若配置了 NOTIFIER_WEBHOOK_URL，则在治理任务自动创建后通过 HTTP POST 推送一条
JSON 消息（可用于对接企业微信/钉钉/Slack/自定义告警总线）。未配置时为 no-op，
不影响主流程（包括推送失败也仅记日志，不抛异常）。
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def notify_task_created(task, source: str = "") -> None:
    """治理任务创建后通知负责人/告警总线。未配置 webhook 时静默返回。"""
    url = (settings.NOTIFIER_WEBHOOK_URL or "").strip()
    if not url:
        return
    payload = {
        "event": "governance_task_created",
        "task_id": getattr(task, "id", ""),
        "task_type": getattr(task, "task_type", ""),
        "title": getattr(task, "title", ""),
        "kb_id": getattr(task, "kb_id", ""),
        "priority": getattr(task, "priority", ""),
        "assignee": getattr(task, "assignee", ""),
        "status": getattr(task, "status", ""),
        "source": source,
    }
    try:
        httpx.post(url, json=payload, timeout=5)
        logger.info("治理任务通知已发送 | task=%s", payload["task_id"])
    except Exception as exc:  # 通知失败绝不影响主流程
        logger.warning("治理任务通知发送失败（已忽略）: %s", exc)
