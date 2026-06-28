#!/usr/bin/env bash
# start.sh — 启动 RumiAI 全部服务（后端API + LangGraph + 前端）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOGS="$ROOT/logs"
TMP="$ROOT/tmp"

ENV_NAME="${1:-dev}"
CONFIG_FILE="$ROOT/scripts/config/${ENV_NAME}.env"

export TZ=Asia/Shanghai
export UV_CACHE_DIR="${UV_CACHE_DIR:-$BACKEND/.uv-cache}"
mkdir -p "$LOGS" "$TMP"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[start]${NC} $1"; }
warn() { echo -e "${YELLOW}[start]${NC} $1"; }
fail() { echo -e "${RED}[start]${NC} $1"; exit 1; }

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

require_cmd() {
  local name=$1
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    echo "Run ./scripts/doctor.sh $ENV_NAME for setup details." >&2
    exit 1
  fi
}

frontend_runner() {
  if command -v pnpm >/dev/null 2>&1; then
    echo "pnpm"
  elif command -v npm >/dev/null 2>&1; then
    echo "npm"
  else
    echo ""
  fi
}

load_env_file() {
  local file=$1
  if [ -f "$file" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$file"
    set +a
  fi
}

load_env_file "$CONFIG_FILE"

if [ "$ENV_NAME" = "prod" ]; then
  if [ ! -f "$BACKEND/.env.production" ]; then
    fail "缺少 backend/.env.production；请复制 backend/.env.production.example 并填入生产配置"
  fi
  load_env_file "$BACKEND/.env.production"
else
  if [ ! -f "$BACKEND/.env" ]; then
    log "复制 backend/.env.example → backend/.env（请编辑填入 API Key）"
    cp "$BACKEND/.env.example" "$BACKEND/.env"
  fi
  load_env_file "$BACKEND/.env"
fi

APP_ENV="${APP_ENV:-$ENV_NAME}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
LANGGRAPH_HOST="${LANGGRAPH_HOST:-0.0.0.0}"
LANGGRAPH_PORT="${LANGGRAPH_PORT:-2024}"
CHROMA_BIND_HOST="${CHROMA_BIND_HOST:-0.0.0.0}"
CHROMA_HOST="${CHROMA_HOST:-localhost}"
CHROMA_PORT="${CHROMA_PORT:-8001}"
DATA_DIR="${DATA_DIR:-./data}"

require_cmd uv
require_cmd node

FRONTEND_RUNNER="$(frontend_runner)"
if [ -z "$FRONTEND_RUNNER" ]; then
  fail "Missing frontend package manager: install pnpm or npm."
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  log "安装前端依赖..."
  cd "$FRONTEND"
  "$FRONTEND_RUNNER" install
  cd "$ROOT"
fi

if [ ! -d "$BACKEND/.venv" ]; then
  log "安装 Python 依赖（uv sync）..."
  cd "$BACKEND"
  uv sync
  cd "$ROOT"
fi

if [ "$ENV_NAME" = "prod" ]; then
  log "执行前端生产构建..."
  cd "$FRONTEND"
  "$FRONTEND_RUNNER" run build
  cd "$ROOT"
fi

# --- Start ChromaDB HTTP Server ---
log "启动 ChromaDB ($CHROMA_BIND_HOST:$CHROMA_PORT, env: $APP_ENV)..."
cd "$BACKEND"
CHROMA_PATH="$DATA_DIR/chroma"
DATA_FILES_PATH="$DATA_DIR/files"
mkdir -p "$CHROMA_PATH" "$DATA_FILES_PATH"
nohup uv run chroma run --path "$CHROMA_PATH" --host "$CHROMA_BIND_HOST" --port "$CHROMA_PORT" \
  > "$LOGS/chromadb.${APP_ENV}.log" 2>&1 &
echo $! > "$TMP/chromadb.${APP_ENV}.pid"
sleep 2

# --- Start Backend API ---
log "启动后端 API ($BACKEND_HOST:$BACKEND_PORT, env: $APP_ENV)..."
cd "$BACKEND"
if [ "$ENV_NAME" = "prod" ]; then
  nohup uv run uvicorn src.api.routes:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
    > "$LOGS/backend.${APP_ENV}.log" 2>&1 &
else
  nohup uv run uvicorn src.api.routes:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
    --reload \
    --reload-exclude '.venv' \
    --reload-exclude 'data' \
    --reload-exclude '.langgraph_api' \
    --reload-exclude '__pycache__' \
    > "$LOGS/backend.${APP_ENV}.log" 2>&1 &
fi
echo $! > "$TMP/backend.${APP_ENV}.pid"

# --- Start LangGraph ---
log "启动 LangGraph ($LANGGRAPH_HOST:$LANGGRAPH_PORT, env: $APP_ENV)..."
cd "$BACKEND"
nohup env FORCE_COLOR=0 NO_COLOR=1 UV_TERM=0 uv run langgraph dev \
  --host "$LANGGRAPH_HOST" --port "$LANGGRAPH_PORT" --no-browser --no-reload \
  2>&1 | sed $'s/\x1b\\[[0-9;]*[a-zA-Z]//g' | perl "$ROOT/scripts/utc2local.pl" > "$LOGS/langgraph.${APP_ENV}.log" &
echo $! > "$TMP/langgraph.${APP_ENV}.pid"

# --- Start Frontend ---
log "启动前端 ($FRONTEND_HOST:$FRONTEND_PORT, runner: $FRONTEND_RUNNER, env: $APP_ENV)..."
cd "$FRONTEND"
if [ -f "$HOME/.nvm/nvm.sh" ]; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh" --no-use
  if nvm ls v22 >/dev/null 2>&1; then
    nvm use v22 >/dev/null 2>&1 || true
    log "已切换至 Node.js $(node --version) 以兼容 pnpm"
  fi
fi

if [ "$ENV_NAME" = "prod" ]; then
  nohup "$FRONTEND_RUNNER" run start -- -H "$FRONTEND_HOST" -p "$FRONTEND_PORT" \
    > "$LOGS/frontend.${APP_ENV}.log" 2>&1 &
else
  nohup "$FRONTEND_RUNNER" run dev -- -H "$FRONTEND_HOST" -p "$FRONTEND_PORT" \
    > "$LOGS/frontend.${APP_ENV}.log" 2>&1 &
fi
echo $! > "$TMP/frontend.${APP_ENV}.pid"

sleep 2

# --- Verify ---
echo ""
log "========== 服务状态 ($APP_ENV) =========="
FAILED=0

check_port() {
  local name=$1 port=$2 pid_file=$3 log_file=$4
  if lsof -ti:"$port" > /dev/null 2>&1; then
    log "运行中: $name (port $port)"
  else
    local pid=""
    if [ -f "$pid_file" ]; then
      pid="$(cat "$pid_file")"
    fi

    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      log "启动中: $name (port $port)，请稍候..."
    else
      warn "启动失败: $name (port $port)"
      if [ -f "$log_file" ]; then
        warn "最近日志: $log_file"
        tail -n 40 "$log_file"
      fi
      FAILED=1
    fi
  fi
}

check_port "后端 API" "$BACKEND_PORT" "$TMP/backend.${APP_ENV}.pid" "$LOGS/backend.${APP_ENV}.log"
check_port "LangGraph" "$LANGGRAPH_PORT" "$TMP/langgraph.${APP_ENV}.pid" "$LOGS/langgraph.${APP_ENV}.log"
check_port "ChromaDB" "$CHROMA_PORT" "$TMP/chromadb.${APP_ENV}.pid" "$LOGS/chromadb.${APP_ENV}.log"
check_port "前端" "$FRONTEND_PORT" "$TMP/frontend.${APP_ENV}.pid" "$LOGS/frontend.${APP_ENV}.log"

echo ""
log "日志文件:"
log "  后端:      tail -f $LOGS/backend.${APP_ENV}.log"
log "  LangGraph: tail -f $LOGS/langgraph.${APP_ENV}.log"
log "  ChromaDB:  tail -f $LOGS/chromadb.${APP_ENV}.log"
log "  前端:      tail -f $LOGS/frontend.${APP_ENV}.log"
echo ""
if [ "$ENV_NAME" = "prod" ]; then
  log "访问: https://rumi.robinverse.me"
else
  log "访问: http://localhost:$FRONTEND_PORT"
fi

if [ "$FAILED" -ne 0 ]; then
  exit 1
fi
