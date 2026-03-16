#!/bin/bash
#

pid=$(ps aux | grep stock_analysis | grep -v grep | grep -v '.sh' |  head -1 | awk -F ' ' '{print $2}')

if [ "$pid" != "" ]
then
  echo "killing $pid..."
  ps aux | grep stock_analysis | grep -v grep | awk -F ' ' '{print $2}' | xargs kill -9
else
  echo 'stock_analysis服务已停止.'
fi