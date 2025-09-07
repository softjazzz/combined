#!/bin/bash

# 医生工作站演示启动脚本
# 作者：医疗质控系统开发团队
# 版本：1.0.0

echo "🏥 医疗质控系统 - 医生工作站演示"
echo "=================================="
echo ""

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到Node.js，请先安装Node.js"
    exit 1
fi

# 检查npm环境
if ! command -v npm &> /dev/null; then
    echo "❌ 错误：未找到npm，请先安装npm"
    exit 1
fi

echo "✅ Node.js版本：$(node --version)"
echo "✅ npm版本：$(npm --version)"
echo ""

# 检查项目依赖
if [ ! -d "node_modules" ]; then
    echo "📦 正在安装项目依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查网络连接或npm配置"
        exit 1
    fi
    echo "✅ 依赖安装完成"
    echo ""
fi

# 启动开发服务器
echo "🚀 正在启动开发服务器..."
echo ""
echo "📋 演示访问地址："
echo "   - 主演示页面：http://localhost:5173/demo"
echo "   - 医生工作站：http://localhost:5173/dashboard/doctor-workstation"
echo ""
echo "💡 演示提示："
echo "   1. 选择不同的演示场景体验质控效果"
echo "   2. 在编辑器中修改病历内容观察实时分析"
echo "   3. 查看右侧质控面板的详细分析结果"
echo "   4. 点击改进建议按钮应用智能建议"
echo ""
echo "⌨️  快捷键："
echo "   - Ctrl+C：停止服务器"
echo "   - Ctrl+S：保存病历（在编辑器中）"
echo ""

# 启动服务器
npm run dev
