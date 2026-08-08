"""Sprint7-T2 质量巡检后台定时调度器。

轻量级 asyncio 循环（单进程内，无需外部依赖），周期触发
`run_scheduled_inspection`：运行巡检快照 + 阈值告警评估。
调度参数全部来自 Settings（环境变量可覆盖）。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_task: Optional[asyncio.Task] = None


async def _tick_once() -> None:
    """执行一次调度巡检（独立会话，异常隔离，不拖垮循环）。"""
    from app.db.session import SessionLocal
    from app.services.alert_service import run_scheduled_inspection

    db = SessionLocal()
    try:
        report, alerts, _tasks = await run_scheduled_inspection(
            db, tenant_id=settings.DEFAULT_TENANT_ID,
            score_threshold=settings.QUALITY_ALERT_SCORE_THRESHOLD,
            new_high_threshold=settings.QUALITY_ALERT_NEW_HIGH_THRESHOLD,
        )
        logger.info("定时巡检完成 | score=%.1f | 触发告警 %d",
                    float(report.get("score", 0)), len(alerts))
    except Exception as exc:  # noqa: BLE001
        logger.warning("定时巡检失败（已跳过本轮）: %s", exc)
    finally:
        db.close()


async def _loop() -> None:
    interval = max(30, settings.QUALITY_INSPECT_INTERVAL_SECONDS)
    logger.info("质量巡检调度器启动 | 间隔 %ds | 阈值分 %.1f | 新高危阈值 %d",
                interval, settings.QUALITY_ALERT_SCORE_THRESHOLD,
                settings.QUALITY_ALERT_NEW_HIGH_THRESHOLD)
    while True:
        try:
            await _tick_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度循环异常: %s", exc)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break


def start_quality_scheduler() -> None:
    """在应用 lifespan 中调用：启动后台调度任务。"""
    global _task
    if not settings.QUALITY_INSPECT_ENABLED:
        logger.info("质量巡检调度器未启用（QUALITY_INSPECT_ENABLED=false）")
        return
    if _task is not None and not _task.done():
        logger.info("质量巡检调度器已在运行")
        return
    _task = asyncio.create_task(_loop())


def stop_quality_scheduler() -> None:
    """在应用 shutdown 时调用：取消调度任务。"""
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        logger.info("质量巡检调度器已停止")
    _task = None
