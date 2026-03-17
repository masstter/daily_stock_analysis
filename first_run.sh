#!/bin/bash
#

# 安装markdown-to-file工具，支持将markdown文件转换为图片
if [ "$(npm ls -g | grep markdown-to-file)" == "" ];then
  npm i -g markdown-to-file
fi

# 安装python依赖
pip install -r requirements.txt

#安装web依赖并构建
cd ./apps/dsa-web
npm install && npm run build
cd ../..