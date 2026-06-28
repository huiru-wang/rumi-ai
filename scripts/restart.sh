#!/usr/bin/env bash
# restart.sh — 重启 RumiAI 全部服务
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
ENV_NAME="${1:-dev}"

"$SCRIPTS/stop.sh" "$ENV_NAME"
sleep 1
"$SCRIPTS/start.sh" "$ENV_NAME"
