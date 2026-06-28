#!/usr/bin/env bash
# doctor.sh - check prerequisites for a RumiAI environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
ENV_NAME="${1:-dev}"
CONFIG_FILE="$ROOT/scripts/config/${ENV_NAME}.env"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok() { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
fail() { echo -e "${RED}[fail]${NC} $1"; }

usage() {
  echo "Usage: $0 [dev|prod]"
}

if [ "$ENV_NAME" = "-h" ] || [ "$ENV_NAME" = "--help" ]; then
  usage
  exit 0
fi

missing=0

if [ ! -f "$CONFIG_FILE" ]; then
  usage
  fail "unknown environment: $ENV_NAME"
  exit 1
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

check_cmd() {
  local name=$1
  if command -v "$name" >/dev/null 2>&1; then
    ok "$name: $(command -v "$name")"
  else
    fail "$name not found"
    missing=1
  fi
}

echo "== Environment =="
ok "env: $APP_ENV"
ok "config: ${CONFIG_FILE#$ROOT/}"

echo ""
echo "== Toolchain =="
check_cmd uv
check_cmd node

if command -v pnpm >/dev/null 2>&1; then
  ok "pnpm: $(command -v pnpm)"
elif command -v npm >/dev/null 2>&1; then
  warn "pnpm not found; npm is available and scripts will fall back to it"
else
  fail "neither pnpm nor npm found"
  missing=1
fi

echo ""
echo "== Project Files =="
for path in "$BACKEND/pyproject.toml" "$BACKEND/langgraph.json" "$FRONTEND/package.json"; do
  if [ -f "$path" ]; then
    ok "${path#$ROOT/}"
  else
    fail "missing ${path#$ROOT/}"
    missing=1
  fi
done

echo ""
echo "== App Environment Files =="
if [ "$ENV_NAME" = "prod" ]; then
  if [ -f "$BACKEND/.env.production" ]; then
    ok "backend/.env.production"
  else
    fail "backend/.env.production missing; copy backend/.env.production.example and fill production values"
    missing=1
  fi

  if [ -f "$FRONTEND/.env.production.example" ]; then
    ok "frontend/.env.production.example"
  else
    fail "frontend/.env.production.example missing"
    missing=1
  fi
else
  if [ -f "$BACKEND/.env" ]; then
    ok "backend/.env"
  else
    warn "backend/.env missing; scripts/start.sh dev will copy backend/.env.example"
  fi

  if [ -f "$FRONTEND/.env.development.example" ]; then
    ok "frontend/.env.development.example"
  else
    warn "frontend/.env.development.example missing; scripts/config/dev.env still injects dev values"
  fi
fi

echo ""
echo "== Frontend Dependencies =="
if [ -d "$FRONTEND/node_modules" ]; then
  ok "frontend/node_modules"
else
  warn "frontend/node_modules missing; run pnpm install or npm install in frontend/"
fi

if [ "$ENV_NAME" = "prod" ]; then
  if [ -d "$FRONTEND/.next" ]; then
    ok "frontend/.next"
  else
    warn "frontend/.next missing; scripts/start.sh prod will run a production build"
  fi
fi

echo ""
echo "== Ports =="
for port in "$BACKEND_PORT" "$CHROMA_PORT" "$LANGGRAPH_PORT" "$FRONTEND_PORT"; do
  if lsof -ti:"$port" >/dev/null 2>&1; then
    warn "port $port is in use"
  else
    ok "port $port is free"
  fi
done

echo ""
if [ "$missing" -eq 0 ]; then
  ok "doctor check completed for $APP_ENV"
else
  fail "doctor check found missing required tools or files for $APP_ENV"
  exit 1
fi
