#!/bin/bash

# DRG Backend API 启动脚本

echo "========================================="
echo "🚀 DRG Backend API 启动脚本"
echo "========================================="
echo ""

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python 版本: $python_version"

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "✓ 虚拟环境已存在"
    source venv/bin/activate
else
    echo "⚠️  虚拟环境不存在，正在创建..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ 虚拟环境创建成功"
fi

# 检查依赖
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "⚠️  依赖未安装，正在安装..."
    pip install -r requirements.txt
    echo "✓ 依赖安装完成"
else
    echo "✓ 依赖已安装"
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，从模板复制..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，配置必要的环境变量！"
    echo ""
    echo "必须配置的变量："
    echo "  - SUPABASE_URL"
    echo "  - SUPABASE_KEY (service_role key)"
    echo "  - DEEPSEEK_API_KEY"
    echo ""
    read -p "按 Enter 继续（或 Ctrl+C 退出）..."
else
    echo "✓ .env 文件已存在"
fi

# 创建日志目录
mkdir -p logs
echo "✓ 日志目录已创建"

echo ""
echo "========================================="
echo "✨ 启动 FastAPI 服务..."
echo "========================================="
echo ""
echo "📚 API 文档: http://localhost:8001/docs"
echo "📖 ReDoc: http://localhost:8001/redoc"
echo "🔍 健康检查: http://localhost:8001/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
