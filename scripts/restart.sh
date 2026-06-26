#!/usr/bin/env bash
# restart.sh — 重启 RumiAI 全部服务
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPTS/stop.sh"
sleep 1
"$SCRIPTS/start.sh"
