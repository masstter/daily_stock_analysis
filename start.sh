#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pid=""
if command -v pgrep >/dev/null 2>&1; then
  pid=$(pgrep -f "stock_analysis_service" | head -1)
fi

if [ -z "$pid" ]; then
  pid=$(ps aux | grep stock_analysis_service | grep -v grep | grep -v '.sh' | head -1 | awk '{print $2}')
fi

if [ -n "$pid" ]; then
  echo "stock_analysis服务已在运行, 进程号: $pid"
  exit 0
fi

cd "$SCRIPT_DIR" || exit 1
python main.py --webui --name stock_analysis_service > /dev/null 2>&1 &

sh "$SCRIPT_DIR/status.sh"
