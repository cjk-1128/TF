"""TerraForge 多级缓存层（L1 内存 + L2 Redis + L3 回源）。

层级：
  L1  进程内内存   —— 始终生效，带 TTL（最快）
  L2  Redis        —— REDIS_ENABLED=True 且可达时生效（跨进程/跨请求共享）
  L3  由调用方 loader 提供 —— 缓存未命中时回源（Embedding 推理 / 检索 / 问答）

设计目标：减少重复 Embedding 计算与重复检索/问答，提升响应速度。
Redis 不可用时自动降级为仅 L1，不影响主流程；redis 未安装也不报错。
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryCache:
    """进程内 TTL 缓存（线程安全）。"""

    def __init__(self, default_ttl: int = 3600) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expire_at, value = item
            if expire_at and expire_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            ttl = ttl if ttl is not None else self.default_ttl
            expire_at = time.time() + ttl if ttl else 0
            self._store[key] = (expire_at, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class RedisCache:
    """L2 Redis 缓存（不可用时自动关闭，不抛异常）。"""

    def __init__(self, url: str, default_ttl: int = 3600) -> None:
        self.ttl = default_ttl
        self._ok = False
        self._r = None
        try:
            import redis  # 懒导入：未安装也不影响 L1
            self._r = redis.from_url(
                url,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
                decode_responses=False,
            )
            self._r.ping()
            self._ok = True
            logger.info("Redis L2 缓存已启用: %s", url)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 不可用，L2 缓存关闭（仅用 L1）：%s", e)

    def get(self, key: str) -> Optional[Any]:
        if not self._ok or self._r is None:
            return None
        try:
            raw = self._r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 读取失败：%s", e)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not self._ok or self._r is None:
            return
        try:
            self._r.set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=(ttl if ttl is not None else self.ttl),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis 写入失败：%s", e)


class Cache:
    """多级缓存门面：合并 L1 + L2。"""

    def __init__(self) -> None:
        self.l1 = MemoryCache(settings.CACHE_TTL_SECONDS)
        self.l2: Optional[RedisCache] = None
        if settings.REDIS_ENABLED:
            self.l2 = RedisCache(settings.REDIS_URL, settings.CACHE_TTL_SECONDS)
        # 线程安全统计（可观测）：命中/未命中计数与耗时累计
        self._stats_lock = threading.RLock()
        self._stats: dict = {"l1_hit": 0, "l2_hit": 0, "miss": 0,
                             "load_ms": 0.0, "total_ms": 0.0}

    def _record(self, kind: str, value: float = 1.0) -> None:
        with self._stats_lock:
            self._stats[kind] = self._stats.get(kind, 0) + value

    def stats(self) -> dict:
        """返回统计快照（含计算出的总查询数与命中率）。"""
        with self._stats_lock:
            s = dict(self._stats)
        total = s.get("l1_hit", 0) + s.get("l2_hit", 0) + s.get("miss", 0)
        s["total_lookups"] = total
        s["hit_rate"] = round((s.get("l1_hit", 0) + s.get("l2_hit", 0)) / total, 4) \
            if total else 0.0
        return s

    def get(self, key: str) -> Optional[Any]:
        v = self.l1.get(key)
        if v is not None:
            self._record("l1_hit")
            return v
        if self.l2 is not None:
            v = self.l2.get(key)
            if v is not None:
                self.l1.set(key, v)  # 回填 L1，减少 Redis 往返
                self._record("l2_hit")
                return v
        self._record("miss")
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.l1.set(key, value, ttl)
        if self.l2 is not None:
            self.l2.set(key, value, ttl)

    def get_or_load(self, key: str, loader: Callable[[], Any],
                    ttl: Optional[int] = None) -> Any:
        """先查缓存，未命中则调用 loader 回源并写回，并记录耗时。"""
        t0 = time.perf_counter()
        v = self.get(key)
        if v is not None:
            self._record("total_ms", (time.perf_counter() - t0) * 1000)
            return v
        lt0 = time.perf_counter()
        v = loader()
        self._record("load_ms", (time.perf_counter() - lt0) * 1000)
        self._record("total_ms", (time.perf_counter() - t0) * 1000)
        self.set(key, v, ttl)
        return v


# ----------------- 缓存键助手 -----------------
def embedding_cache_key(provider: str, model: str, text: str) -> str:
    """Embedding 缓存键：provider|model|text 的 SHA256。"""
    h = hashlib.sha256(f"{provider}|{model}|{text}".encode("utf-8")).hexdigest()
    return f"tf:emb:{h}"


def query_cache_key(query: str, **ctx: Any) -> str:
    """查询缓存键：query + 上下文参数 的 SHA256。"""
    payload = query + "|" + json.dumps(ctx, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tf:q:{h}"


# 进程级单例（与 uvicorn worker 生命周期一致）
default_cache: Cache = Cache()


def cache_stats() -> dict:
    """模块级统计快照，供 /health 等探测端点调用。"""
    return default_cache.stats()


def answer_cache_key(query: str, **ctx: Any) -> str:
    """答案（管线结果）缓存键：query + 上下文参数 的 SHA256，前缀 tf:ans:。"""
    payload = "ANS|" + query + "|" + json.dumps(ctx, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tf:ans:{h}"
