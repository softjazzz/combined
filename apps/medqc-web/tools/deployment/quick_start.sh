#!/bin/bash

echo "🚀 启动病案质控系统..."
echo "================================"

# 切换到项目目录
cd /home/ubuntu/KAG/kag/examples/002medqc/MedQC0817

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，安装依赖..."
    npm install
fi

# 启动前端服务
echo "🌐 启动Vue3前端服务..."
echo "前端地址: http://localhost:3000"
echo "后端API: http://124.220.6.136:8000"
echo "================================"

# 使用nohup在后台启动，避免终端关闭时停止服务
nohup npm run dev > frontend.log 2>&1 &

echo "✅ 前端服务已在后台启动"
echo "📋 查看日志: tail -f frontend.log"
echo "🌐 访问地址: http://localhost:3000"
echo "🛑 停止服务: pkill -f 'vite'"

