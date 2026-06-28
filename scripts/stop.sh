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

warn "停止现有服务 ($APP_ENV)..."

graceful_stop() {
  local name=$1 port=$2
  local pids
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
    warn "已停止: $name (port $port)"
  fi
}

graceful_stop "后端 API" "$BACKEND_PORT"
graceful_stop "LangGraph" "$LANGGRAPH_PORT"
graceful_stop "ChromaDB" "$CHROMA_PORT"
graceful_stop "前端" "$FRONTEND_PORT"

rm -f "$ROOT/tmp/"*.${APP_ENV}.pid

warn "全部服务已停止 ($APP_ENV)"
