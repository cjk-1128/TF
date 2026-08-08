#!/usr/bin/env bash
# =====================================================================
#  TerraForge 自签名证书生成（Phase 6）
#  用途：为内网 VM（192.168.88.100）生成自签名 TLS 证书，供 nginx SSL 终止使用。
#  已有证书则跳过（幂等）。生产环境请用 CA 签发证书替换 nginx/ssl/ 下同名文件。
#  用法：bash tools/gen_ssl.sh
# =====================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 仓库根 / nginx/ssl
SSL_DIR="$HERE/../nginx/ssl"
mkdir -p "$SSL_DIR"
CRT="$SSL_DIR/terraforge.crt"
KEY="$SSL_DIR/terraforge.key"

if [[ -f "$CRT" && -f "$KEY" ]]; then
  echo "[gen_ssl] 证书已存在，跳过生成: $CRT"
  exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "[gen_ssl] 未找到 openssl，请先安装（apt-get install -y openssl）" >&2
  exit 1
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$KEY" -out "$CRT" \
  -subj "/C=CN/ST=Local/L=Local/O=TerraForge/CN=192.168.88.100" \
  -addext "subjectAltName=IP:192.168.88.100,DNS:localhost"

echo "[gen_ssl] 自签名证书已生成:"
echo "  CRT: $CRT"
echo "  KEY: $KEY"
echo "[gen_ssl] 注意：浏览器会提示证书不受信任（自签名属预期）。生产请替换为 CA 签发证书。"
