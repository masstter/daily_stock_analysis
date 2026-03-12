#!/bin/bash
#

ps aux | grep stock_analysis | grep -v grep | awk -F ' ' '{print $2}' | xargs kill -9