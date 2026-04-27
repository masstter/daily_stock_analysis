#!/bin/bash

pid=""
if command -v pgrep >/dev/null 2>&1; then
  pid=$(pgrep -f "stock_analysis_service" | head -1)
fi

if [ -z "$pid" ]; then
  pid=$(ps aux | grep stock_analysis_service | grep -v grep | grep -v '.sh' | head -1 | awk '{print $2}')
fi

if [ "$pid" != "" ]
then
  echo "killing stock_analysis $pid..."
  kill -9 "$pid"
else
  echo 'stock_analysis服务已停止.'
fi