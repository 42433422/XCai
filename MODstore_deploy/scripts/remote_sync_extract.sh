#!/usr/bin/env bash
# Run on server: extract modstore_deploy_sync.tgz, keep .env, pip, npm, mvn, restart
# Usage: export REMOTE_BASE=/root/modstore-git; bash remote_sync_extract.sh
# 可选：export MODSTORE_API_HEALTH_PORTS="9999 8765" 若 FastAPI 监听非默认端口
set -e
# 与 sync-modstore-to-server.ps1 默认一致；须与 modstore、modstore-payment 的 -jar 为同一工作树
BASE="${REMOTE_BASE:-/root/modstore-git}"
TAR="/tmp/modstore_deploy_sync.tgz"
if ! test -f "$TAR"; then
  echo "[err] missing: $TAR" >&2
  exit 1
fi
DP="$BASE/MODstore_deploy"
if ! test -d "$BASE"; then
  echo "[err] not a directory: $BASE" >&2
  exit 1
fi
if test -f "$DP/.env"; then
  echo "[ok] backup $DP/.env"
  cp "$DP/.env" /tmp/modstore.env.sync.bak
fi
cd "$BASE" || exit 1
if ! tar -tzf "$TAR" 2>/dev/null | head -1 | grep -q '^MODstore_deploy/'; then
  echo "[err] tgz top must be MODstore_deploy/" >&2
  exit 1
fi
# 必须整目录覆盖：只 tar 解压会「合并」进现有树，本机已删除/重命名的文件在服务器上仍残留
# 曾导致 Flyway 同版本两套 sql（如旧 V9__sync + 新 V9__orders）同存于 JAR
if [ -d MODstore_deploy ]; then
  echo "[ok] remove old MODstore_deploy/ (no stale from merge-only extract)"
  rm -rf MODstore_deploy
fi
echo "[ok] extracting to $BASE"
tar xzf "$TAR" || { echo "[err] extract failed"; exit 1; }
rm -f "$TAR"
if test -f /tmp/modstore.env.sync.bak; then
  echo "[ok] restore .env"
  cp /tmp/modstore.env.sync.bak "$DP/.env"
  rm -f /tmp/modstore.env.sync.bak
fi
cd "$DP" || exit 1
if test -f scripts/ensure_llm_master_key.py; then
  if test -f .venv/bin/python; then
    .venv/bin/python scripts/ensure_llm_master_key.py .env || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 scripts/ensure_llm_master_key.py .env || true
  fi
fi
if ! test -f .venv/bin/pip; then
  echo "[ok] create venv"
  (command -v python3 >/dev/null 2>&1) && python3 -m venv .venv
fi
if test -f .venv/bin/pip; then
  .venv/bin/pip install -q -U pip
  .venv/bin/pip install -q -e ".[web,knowledge]"
else
  echo "[warn] no venv" >&2
fi
cd market
echo "[ok] npm install (--legacy-peer-deps avoids npm edgesOut bug on some Node 20 + lockfile combos)"
npm install --no-audit --legacy-peer-deps
export VITE_PUBLIC_BASE=/market/
echo "[ok] npm run build"
npm run build
cd "$DP/java_payment_service" || { echo "[err] no java dir"; exit 1; }
if [ -d "/usr/lib/jvm/java-17-openjdk-17.0.17.0.10-1.tl3.x86_64" ]; then
  export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-17.0.17.0.10-1.tl3.x86_64"
  export PATH="$JAVA_HOME/bin:$PATH"
fi
if ! command -v mvn >/dev/null 2>&1; then
  echo "[err] mvn not found" >&2
  exit 1
fi
echo "[ok] mvn clean package"
# 必须 clean：重命名 Flyway 文件后旧版会残留在 target/classes，与新版并存导致「两个 V9」
mvn -B -q -Dmaven.test.skip=true clean package
echo "[ok] restart"
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart modstore || { echo "[err] systemctl restart modstore failed" >&2; exit 1; }
  systemctl restart modstore-payment || { echo "[err] systemctl restart modstore-payment failed" >&2; exit 1; }
else
  echo "[warn] no systemctl; skip service restart" >&2
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active modstore 2>/dev/null || true
  systemctl is-active modstore-payment 2>/dev/null || true
fi
# Spring Boot can take 30-90s to bind :8080 after systemctl restart
echo "[ok] wait payment :8080/actuator/health (up to ~120s)..."
PAY_CODE=000
for _try in $(seq 1 60); do
  pc=$(curl -sS -o /dev/null -m 3 -w "%{http_code}" "http://127.0.0.1:8080/actuator/health" 2>/dev/null || true)
  pc=${pc:-000}
  PAY_CODE=$pc
  if [ "$PAY_CODE" = "200" ]; then
    echo "[ok] payment ready (try ${_try})"
    break
  fi
  sleep 2
done
# FastAPI：单机常见 9999（systemd）或 8765（文档/compose）；重启后需轮询，勿单次 curl
# 可 export MODSTORE_API_HEALTH_PORTS="9999 8765 8000" 覆盖探测顺序
API_PORTS="${MODSTORE_API_HEALTH_PORTS:-9999 8765}"
API_CODE=000
API_READY_PORT=""
echo "[ok] wait modstore /api/health on ports: $API_PORTS (up to ~120s)..."
for _try in $(seq 1 60); do
  for port in $API_PORTS; do
    c=$(curl -sS -o /dev/null -m 3 -w "%{http_code}" "http://127.0.0.1:${port}/api/health" 2>/dev/null || true)
    c=${c:-000}
    if [ "$c" = "200" ]; then
      API_CODE=200
      API_READY_PORT=$port
      echo "[ok] modstore API ready on :${port} (try ${_try})"
      break 2
    fi
  done
  sleep 2
done
printf "api=%s port=%s pay=%s\n" "$API_CODE" "${API_READY_PORT:-none}" "$PAY_CODE"
if [ "$PAY_CODE" != "200" ]; then
  echo "[err] payment service not healthy on 127.0.0.1:8080 (need 200; check modstore-payment / DB / Redis / Rabbit)" >&2
  if command -v systemctl >/dev/null 2>&1; then
    systemctl status modstore-payment --no-pager -l 2>&1 | head -n 40 || true
    echo "--- journal (last 50 lines) ---"
    journalctl -u modstore-payment -n 50 --no-pager 2>&1 || true
  fi
  if command -v ss >/dev/null 2>&1; then
    echo "--- listen :8080 ---"
    ss -lntp 2>/dev/null | grep -E ':8080\b' || echo "(no listener on 8080)"
  fi
  exit 1
fi
if [ "$API_CODE" != "200" ]; then
  echo "[err] modstore /api/health not 200 on any of: $API_PORTS (need 200; check uvicorn 端口与 systemd)" >&2
  if command -v systemctl >/dev/null 2>&1; then
    systemctl status modstore --no-pager -l 2>&1 | head -n 40 || true
    echo "--- journal modstore (last 80 lines) ---"
    journalctl -u modstore -n 80 --no-pager 2>&1 || true
  fi
  if command -v ss >/dev/null 2>&1; then
    echo "--- listen :9999 :8765 :8000 ---"
    ss -lntp 2>/dev/null | grep -E ':(9999|8765|8000)\b' || echo "(no listener on common API ports)"
  fi
  exit 1
fi
echo "[hint] 请确认 systemctl 中 modstore 的 WorkingDirectory/ExecStart 使用本目录: $DP（若仍指向 /root/releases/… 则运行的是旧树，本脚本已不会更新该路径）"
echo "[ok] sync build done"
