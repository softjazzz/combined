#!/bin/bash

# 智慧医保质控系统后端启动脚本

echo "🚀 启动智慧医保质控系统后端服务..."

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装，请先安装 Python 3.8+"
    exit 1
fi

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  建议在虚拟环境中运行"
    echo "创建虚拟环境: python3 -m venv venv"
    echo "激活虚拟环境: source venv/bin/activate"
fi

# 安装依赖
echo "📦 安装依赖包..."
pip install -r requirements.txt

# 检查环境变量
if [ ! -f "../.env" ]; then
    echo "⚠️  未找到 .env 文件，将使用默认配置"
    echo "请复制 .env.example 为 .env 并配置相应参数"
fi

# 启动服务
echo "🌟 启动服务..."
python main.py
