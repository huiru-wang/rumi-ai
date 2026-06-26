#!/usr/bin/env bash
# init.sh — RumiAI 项目从零初始化：检查/安装系统工具，安装依赖，准备环境
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

export TZ=Asia/Shanghai

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
fail() { echo -e "${RED}[fail]${NC} $1"; }
info() { echo -e "${GREEN}[init]${NC} $1"; }

ERRORS=0

# ─────────────────────────────────────────────────────────────
# 1. 检查 Python >= 3.12
# ─────────────────────────────────────────────────────────────
echo ""
info "== 1/6 检查 Python =="

if command -v python3 >/dev/null 2>&1; then
  PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
  PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
  if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 12 ]; then
    ok "Python $PY_VER"
  else
    fail "Python $PY_VER < 3.12"
    echo "  安装方式: pyenv install 3.12 / brew install python@3.12 / apt install python3.12"
    ERRORS=1
  fi
else
  fail "python3 not found"
  echo "  安装方式: pyenv install 3.12 / brew install python@3.12 / apt install python3.12"
  ERRORS=1
fi

# ─────────────────────────────────────────────────────────────
# 2. 检查 Node.js >= 22
# ─────────────────────────────────────────────────────────────
info "== 2/6 检查 Node.js =="

if command -v node >/dev/null 2>&1; then
  NODE_VER="$(node --version)"
  NODE_MAJOR="$(node --version | sed 's/^v//' | cut -d. -f1)"
  if [ "$NODE_MAJOR" -ge 22 ]; then
    ok "Node.js $NODE_VER"
  else
    fail "Node.js $NODE_VER < v22（pnpm 10+ 要求 Node >= 22）"
    echo "  安装方式: nvm install 22 / brew install node@22"
    ERRORS=1
  fi
else
  fail "node not found"
  echo "  安装方式: nvm install 22 / brew install node@22"
  ERRORS=1
fi

# ─────────────────────────────────────────────────────────────
# 3. 检查并安装 uv
# ─────────────────────────────────────────────────────────────
info "== 3/6 检查 uv =="

if command -v uv >/dev/null 2>&1; then
  ok "uv: $(uv --version)"
else
  warn "uv not found，正在安装..."
  if curl -LsSf https://astral.sh/uv/install.sh | sh; then
    # uv 安装到 ~/.local/bin 或 ~/.cargo/bin，加入 PATH
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if command -v uv >/dev/null 2>&1; then
      ok "uv 安装成功: $(uv --version)"
    else
      fail "uv 安装完成但未在 PATH 中，请手动添加 ~/.local/bin 到 PATH"
      ERRORS=1
    fi
  else
    fail "uv 安装失败，请手动安装: https://docs.astral.sh/uv/getting-started/installation/"
    ERRORS=1
  fi
fi

# ─────────────────────────────────────────────────────────────
# 4. 检查 pnpm / npm
# ─────────────────────────────────────────────────────────────
info "== 4/6 检查前端包管理器 =="

FRONTEND_RUNNER=""
if command -v pnpm >/dev/null 2>&1; then
  ok "pnpm: $(pnpm --version)"
  FRONTEND_RUNNER="pnpm"
elif command -v npm >/dev/null 2>&1; then
  warn "pnpm not found，尝试安装 pnpm..."
  if npm install -g pnpm 2>/dev/null; then
    ok "pnpm 安装成功: $(pnpm --version)"
    FRONTEND_RUNNER="pnpm"
  else
    warn "pnpm 安装失败，使用 npm 作为兜底"
    FRONTEND_RUNNER="npm"
  fi
else
  fail "neither pnpm nor npm found"
  echo "  安装方式: npm install -g pnpm / brew install node（自带 npm）"
  ERRORS=1
fi

# ─────────────────────────────────────────────────────────────
# 5. 检查 perl / lsof
# ─────────────────────────────────────────────────────────────
info "== 5/6 检查辅助工具 =="

if command -v perl >/dev/null 2>&1; then
  ok "perl: $(perl -e 'print $^V')"
else
  warn "perl not found（日志时间戳转换需要）"
  echo "  macOS 自带 perl；Linux: apt install perl / yum install perl"
fi

if command -v lsof >/dev/null 2>&1; then
  ok "lsof: $(command -v lsof)"
else
  warn "lsof not found（端口检测需要）"
  echo "  macOS 自带 lsof；Linux: apt install lsof / yum install lsof"
fi

# ─────────────────────────────────────────────────────────────
# 如果关键工具缺失，提前退出
# ─────────────────────────────────────────────────────────────
if [ "$ERRORS" -ne 0 ]; then
  echo ""
  fail "关键工具缺失，请先按上述提示安装后重新运行 init.sh"
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# 6. 准备环境配置
# ─────────────────────────────────────────────────────────────
echo ""
info "== 6/6 准备项目环境 =="

# 复制 .env 模板
if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  ok "已创建 backend/.env（请编辑填入 API Key）"
else
  ok "backend/.env 已存在"
fi

# 创建数据目录
DATA_DIR="${DATA_DIR:-$BACKEND/data}"
mkdir -p "$DATA_DIR/chroma" "$DATA_DIR/files"
ok "数据目录已就绪: $DATA_DIR/{chroma,files}"

# 安装 Python 依赖
info "安装 Python 依赖（uv sync）..."
cd "$BACKEND"
if uv sync --quiet 2>/dev/null || uv sync; then
  ok "Python 依赖安装完成"
else
  fail "Python 依赖安装失败，请检查 pyproject.toml 和网络连接"
  exit 1
fi

# 安装前端依赖
info "安装前端依赖（${FRONTEND_RUNNER} install）..."
cd "$FRONTEND"
if "$FRONTEND_RUNNER" install; then
  ok "前端依赖安装完成"
else
  fail "前端依赖安装失败，请检查 package.json 和网络连接"
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# 结果摘要
# ─────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
ok "RumiAI 初始化完成！"
echo "============================================================"
echo ""
echo "  下一步："
echo "  1. 编辑 backend/.env，填入必要的 API Key："
echo "       OPENAI_API_KEY      — Agent LLM 推理（必须）"
echo "       EMBEDDING_API_KEY     — 向量 Embedding（必须）"
echo "       TTS_API_KEY           — TTS 语音合成（可选）"
echo "       VISION_API_KEY        — 视觉模型（可选）"
echo "       LANGSMITH_API_KEY     — 链路追踪（可选）"
echo ""
echo "  2. 启动所有服务："
echo "       ./scripts/start.sh"
echo ""
echo "  3. 访问 http://localhost:3000"
echo ""
