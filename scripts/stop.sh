#!/usr/bin/env bash
# stop.sh — 停止 RumiAI 全部服务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Colors
YELLOW='\033[1;33m'
NC='\033[0m'

warn() { echo -e "${YELLOW}[stop]${NC} $1"; }

warn "停止现有服务..."

# Graceful stop: SIGTERM first, wait for flush, then force kill
graceful_stop() {
  local name=$1 port=$2
  local pids
  pids=$(lsof -ti:$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    # Force kill any remaining
    pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
    warn "已停止: $name (port $port)"
  fi
}

graceful_stop "后端 API" 8000
graceful_stop "LangGraph" 2024
graceful_stop "ChromaDB" 8001
graceful_stop "前端" 3000

# Clean pid files
rm -f "$ROOT/tmp/"*.pid

warn "全部服务已停止"
