#!/bin/bash

# Distiller LINE Bot Service
# Runs persistently via launchd (KeepAlive = true)
# Configuration: com.distiller.bot.plist

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

# 載入環境變數（LINE_CHANNEL_ID, LINE_CHANNEL_SECRET 等）
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

cd "$PROJECT_DIR"
exec uv run python bot.py
