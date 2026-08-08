#!/usr/bin/env python3
"""TerraForge Redis 隔离恢复（仅 tf: 前缀）。

在 terraforge 容器内运行（内置 redis-py）。依据 backup_redis.py 生成的 JSONL 恢复。
默认不清空现有数据（幂等覆盖同名键）；加 --flush-prefix 可先清空 tf: 前缀再恢复。

用法：
    python restore_redis.py --redis redis://host.docker.internal:6379/1 --in tf_redis.jsonl [--flush-prefix]
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
    ap = argparse.ArgumentParser(description="TerraForge Redis 隔离恢复（tf: 前缀）")
    ap.add_argument("--redis", default="redis://host.docker.internal:6379/1")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--flush-prefix", action="store_true",
                    help="恢复前先清空现有 tf: 前缀（谨慎：会删除本平台所有 Redis 缓存）")
    ap.add_argument("--prefix", default="tf:")
    args = ap.parse_args()

    r = redis.from_url(args.redis, decode_responses=True)
    if args.flush_prefix:
        for k in r.scan_iter(match=args.prefix + "*"):
            r.delete(k)
        print("[restore_redis] 已清空现有 tf: 前缀")

    n = 0
    with open(args.inp, encoding="utf-8") as f:
        pipe = r.pipeline(transaction=False)
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key, t, val, ttl = rec["key"], rec["type"], rec["value"], rec.get("ttl", -1)
            if t == "string":
                pipe.set(key, val)
            elif t == "hash":
                pipe.delete(key)
                pipe.hset(key, mapping=val)
            elif t == "list":
                pipe.delete(key)
                pipe.rpush(key, *val)
            elif t == "set":
                pipe.delete(key)
                pipe.sadd(key, *val)
            elif t == "zset":
                pipe.delete(key)
                pipe.zadd(key, {m: s for m, s in val})
            else:
                continue
            if ttl and ttl > 0:
                pipe.expire(key, ttl)
            n += 1
            if n % 500 == 0:
                pipe.execute()
        pipe.execute()
    print(f"[restore_redis] 恢复 {n} 条")


if __name__ == "__main__":
    main()
