#!/usr/bin/env python3
"""TerraForge Redis 隔离备份（仅 tf: 前缀，安全不污染 KnowForge）。

在 terraforge 容器内运行（内置 redis-py），连接宿主 Redis
（默认 redis://host.docker.internal:6379/1，即 compose 中 REDIS_URL 的宿主地址）。

导出格式（JSONL，每行一条）：{"key", "type", "ttl", "value"}
- ttl: -1 永久, -2 不存在（正常导出时不会是 -2）
- value 按类型序列化：string->str, hash->dict, list/set->list, zset->[(member,score),...]

用法：
    python backup_redis.py --redis redis://host.docker.internal:6379/1 --out tf_redis.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    import redis
except ImportError:
    sys.exit("需要 redis-py（terraforge 容器已内置；如在宿主运行请先 pip install redis）")


def main() -> None:
    ap = argparse.ArgumentParser(description="TerraForge Redis 隔离备份（tf: 前缀）")
    ap.add_argument("--redis", default="redis://host.docker.internal:6379/1")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="tf:")
    args = ap.parse_args()

    r = redis.from_url(args.redis, decode_responses=True)
    count = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for key in r.scan_iter(match=args.prefix + "*"):
            t = r.type(key)
            ttl = r.ttl(key)
            if t == "string":
                val = r.get(key)
            elif t == "hash":
                val = r.hgetall(key)
            elif t == "list":
                val = r.lrange(key, 0, -1)
            elif t == "set":
                val = list(r.smembers(key))
            elif t == "zset":
                val = r.zrange(key, 0, -1, withscores=True)
            else:
                val = None
            rec = {"key": key, "type": t, "ttl": ttl, "value": val}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    print(f"[backup_redis] 导出 {count} 条 (前缀 {args.prefix}) -> {args.out}")


if __name__ == "__main__":
    main()
