#!/usr/bin/env bash
# =====================================================================
#  TerraForge 生产数据备份（Phase 6）
#  备份内容：
#    1) MySQL `terraforge` 库（经同机 KnowForge MySQL 容器，自动探测 13307）
#    2) docker_vector/ (BM25 索引) 与 docker_data/ (bind 挂载数据)
#    3) Redis `tf:` 前缀隔离导出（仅本平台缓存，绝不碰 KnowForge 数据）
#  留存：默认保留近 7 天每日备份，自动清理更早的。
#
#  用法：bash tools/backup.sh
#  可调环境变量：TF_ROOT / TF_MYSQL_CONTAINER / TF_MYSQL_ROOT_PASSWORD /
#                TF_REDIS_HOST / TF_REDIS_PORT / TF_REDIS_DB / TF_BACKUP_RETENTION_DAYS
# =====================================================================
set -euo pipefail

TF_ROOT="${TF_ROOT:-/root/terraforge}"
BACKUP_ROOT="${BACKUP_ROOT:-$TF_ROOT/backups}"
MYSQL_CONTAINER="${TF_MYSQL_CONTAINER:-$(docker ps --filter 'publish=13307/tcp' --format '{{.Names}}' | head -1)}"
MYSQL_PASSWORD="${TF_MYSQL_ROOT_PASSWORD:-root123}"
REDIS_HOST="${TF_REDIS_HOST:-host.docker.internal}"
REDIS_PORT="${TF_REDIS_PORT:-6379}"
REDIS_DB="${TF_REDIS_DB:-1}"
RETENTION_DAYS="${TF_BACKUP_RETENTION_DAYS:-7}"

TS="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$TS"
mkdir -p "$DEST"

log() { echo "[backup][$(date '+%F %T')] $*"; }

log "备份目录: $DEST"
log "MySQL 容器: ${MYSQL_CONTAINER:-<未探测到, 跳过>}"
log "Redis: $REDIS_HOST:$REDIS_PORT db$REDIS_DB (前缀 tf:)"

# 1) MySQL
if [[ -n "$MYSQL_CONTAINER" ]]; then
  log "导出 MySQL terraforge 库 ..."
  if docker exec "$MYSQL_CONTAINER" mysqldump -uroot -p"$MYSQL_PASSWORD" \
        --single-transaction --routines --triggers --no-create-db \
        terraforge 2>/dev/null | gzip > "$DEST/terraforge.sql.gz"; then
    log "MySQL 导出完成: $(du -h "$DEST/terraforge.sql.gz" | cut -f1)"
  else
    log "MySQL 导出失败，请检查容器名/密码（TF_MYSQL_CONTAINER / TF_MYSQL_ROOT_PASSWORD）"
  fi
else
  log "未探测到 MySQL 容器，跳过 MySQL 备份"
fi

# 2) 本地向量 / 数据
if [[ -d "$TF_ROOT/docker_vector" ]]; then
  tar -czf "$DEST/vectorstore.tar.gz" -C "$TF_ROOT" docker_vector
  log "vectorstore 打包完成"
fi
if [[ -d "$TF_ROOT/docker_data" ]]; then
  tar -czf "$DEST/data.tar.gz" -C "$TF_ROOT" docker_data
  log "docker_data 打包完成"
fi

# 3) Redis tf: 前缀隔离导出（复用 terraforge 容器内的 redis-py）
if docker ps --format '{{.Names}}' | grep -qx terraforge; then
  log "导出 Redis tf: 前缀 ..."
  docker cp "$TF_ROOT/tools/backup_redis.py" terraforge:/tmp/backup_redis.py
  docker exec terraforge python /tmp/backup_redis.py \
    --redis "redis://$REDIS_HOST:$REDIS_PORT/$REDIS_DB" \
    --out /tmp/tf_redis.jsonl
  docker cp terraforge:/tmp/tf_redis.jsonl "$DEST/tf_redis.jsonl"
  log "Redis 导出完成: $(wc -l < "$DEST/tf_redis.jsonl") 条"
else
  log "terraforge 容器未运行，跳过 Redis 备份"
fi

# 4) 留存清理
log "清理 ${RETENTION_DAYS} 天前的备份 ..."
find "$BACKUP_ROOT" -maxdepth 1 -type d -name '20*' -mtime +"$RETENTION_DAYS" -print -exec rm -rf {} \; 2>/dev/null || true

log "备份完成: $DEST"
