#!/usr/bin/env bash
# doctor.sh - check local prerequisites for RumiAI development.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok() { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
fail() { echo -e "${RED}[fail]${NC} $1"; }

missing=0

check_cmd() {
  local name=$1
  if command -v "$name" >/dev/null 2>&1; then
    ok "$name: $(command -v "$name")"
  else
    fail "$name not found"
    missing=1
  fi
}

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
echo "== Environment =="
if [ -f "$ROOT/.env" ]; then
  ok ".env"
else
  warn ".env missing; copy .env.example if you want root-level env defaults"
fi

if [ -f "$BACKEND/.env" ]; then
  ok "backend/.env"
else
  warn "backend/.env missing; copy backend/.env.example before real LLM/RAG runs"
fi

if [ "${DASHSCOPE_API_KEY:-}" = "" ]; then
  warn "DASHSCOPE_API_KEY is not exported in this shell; backend/.env may still provide it"
else
  ok "DASHSCOPE_API_KEY is set in this shell"
fi

echo ""
echo "== Frontend Dependencies =="
if [ -d "$FRONTEND/node_modules" ]; then
  ok "frontend/node_modules"
else
  warn "frontend/node_modules missing; run pnpm install or npm install in frontend/"
fi

echo ""
echo "== Ports =="
for port in 8000 8001 2024 3000; do
  if lsof -ti:"$port" >/dev/null 2>&1; then
    warn "port $port is in use"
  else
    ok "port $port is free"
  fi
done

echo ""
if [ "$missing" -eq 0 ]; then
  ok "doctor check completed"
else
  fail "doctor check found missing required tools or files"
  exit 1
fi
