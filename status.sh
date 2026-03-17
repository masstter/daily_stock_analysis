#!/bin/bash
#

ps aux | grep stock_analysis_service | grep -v grep | grep -v '.sh' |  head -1 |  awk -F ' ' '{print "stock_analysis服务正在运行, 进程号: "$2}'