#!/bin/bash
#
python main.py --webui --name stock_analysis_service > /dev/null 2>&1 &

sh ./status.sh