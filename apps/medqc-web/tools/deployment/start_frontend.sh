#!/bin/bash

echo "🚀 启动医疗质控系统前端..."
echo "================================"

# 切换到项目目录
cd /home/ubuntu/KAG/kag/examples/002medqc/MedQC0817

# 检查Node.js版本
echo "📋 检查Node.js环境..."
node --version
npm --version

# 检查是否有node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖包..."
    npm install
else
    echo "✅ 依赖包已存在"
fi

# 启动开发服务器
echo "🌐 启动Vue3开发服务器..."
echo "前端地址: http://localhost:5173"
echo "后端API: http://124.220.6.136:8000"
echo "================================"

npm run dev

