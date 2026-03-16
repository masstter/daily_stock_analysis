#!/bin/bash
#

ps aux | grep stock_analysis | grep -v grep | grep -v status.sh | awk -F ' ' '{print "服务正在运行, 进程号: "$2}'