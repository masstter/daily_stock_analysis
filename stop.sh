#!/bin/bash
#

pid=$(ps aux | grep stock_analysis_service | grep -v grep | grep -v '.sh' |  head -1 | awk -F ' ' '{print $2}')

if [ "$pid" != "" ]
then
  echo "killing stock_analysis $pid..."
  kill -9 "$pid"
else
  echo 'stock_analysis服务已停止.'
fi