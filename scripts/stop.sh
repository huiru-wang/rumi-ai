#!/usr/bin/env bash
# stop.sh — 停止 RumiAI 全部服务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_NAME="${1:-dev}"
CONFIG_FILE="$ROOT/scripts/config/${ENV_NAME}.env"

# Colors
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

warn() { echo -e "${YELLOW}[stop]${NC} $1"; }
fail() { echo -e "${RED}[stop]${NC} $1"; exit 1; }

usage() {
  echo "Usage: $0 [dev|prod]"
}

if [ "$ENV_NAME" = "-h" ] || [ "$ENV_NAME" = "--help" ]; then
  usage
  exit 0
fi

if [ ! -f "$CONFIG_FILE" ]; then
  usage
  fail "未知环境: $ENV_NAME"
fi

set -a
# shellcheck source=/dev/null
source "$CONFIG_FILE"
set +a

APP_ENV="${APP_ENV:-$ENV_NAME}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
LANGGRAPH_PORT="${LANGGRAPH_PORT:-2024}"
CHROMA_PORT="${CHROMA_PORT:-8001}"
TMP="$ROOT/tmp"

warn "停止现有服务 ($APP_ENV)..."

is_running() {
  local pid=$1
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

descendant_pids() {
  local pid=$1
  local children child

  children=$(pgrep -P "$pid" 2>/dev/null || true)
  for child in $children; do
    echo "$child"
    descendant_pids "$child"
  done
}

stop_pids() {
  local name=$1
  local pids=$2

  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    echo "$pids" | while read -r pid; do
      if is_running "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
    warn "已停止: $name"
  fi
}

graceful_stop() {
  local name=$1 port=$2 pid_file=$3
  local root_pid pids

  if [ -f "$pid_file" ]; then
    root_pid=$(cat "$pid_file" 2>/dev/null || true)
    if is_running "$root_pid"; then
      pids=$(
        {
          echo "$root_pid"
          descendant_pids "$root_pid"
        } | awk 'NF && !seen[$0]++'
      )
      stop_pids "$name (pid $root_pid)" "$pids"
    fi
  fi

  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    stop_pids "$name (port $port)" "$pids"
  fi
}

graceful_stop "后端 API" "$BACKEND_PORT" "$TMP/backend.${APP_ENV}.pid"
graceful_stop "LangGraph" "$LANGGRAPH_PORT" "$TMP/langgraph.${APP_ENV}.pid"
graceful_stop "ChromaDB" "$CHROMA_PORT" "$TMP/chromadb.${APP_ENV}.pid"
graceful_stop "前端" "$FRONTEND_PORT" "$TMP/frontend.${APP_ENV}.pid"

rm -f "$TMP/"*.${APP_ENV}.pid

warn "全部服务已停止 ($APP_ENV)"
