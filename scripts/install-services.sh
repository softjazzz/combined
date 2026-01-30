#!/bin/bash
# 安装 MedQC 前后端为 systemd 服务，实现持久化运行

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 停止现有进程..."
pkill -f "uvicorn.*8001" 2>/dev/null || true
pkill -f "vite.*3000" 2>/dev/null || true
sleep 2

echo "📋 复制服务文件到 systemd..."
sudo cp "${SCRIPT_DIR}/medqc-backend.service" /etc/systemd/system/
sudo cp "${SCRIPT_DIR}/medqc-frontend.service" /etc/systemd/system/

echo "🔄 重新加载 systemd 配置..."
sudo systemctl daemon-reload

echo "🚀 启用并启动后端服务..."
sudo systemctl enable medqc-backend.service
sudo systemctl start medqc-backend.service

echo "🚀 启用并启动前端服务..."
sudo systemctl enable medqc-frontend.service
sudo systemctl start medqc-frontend.service

sleep 3

echo ""
echo "📊 服务状态："
echo "============================================"
echo "后端服务 (medqc-backend):"
sudo systemctl status medqc-backend.service --no-pager | head -10
echo ""
echo "前端服务 (medqc-frontend):"
sudo systemctl status medqc-frontend.service --no-pager | head -10
echo ""
echo "============================================"
echo "✅ 安装完成！服务将在系统重启后自动启动"
echo ""
echo "常用命令："
echo "  查看状态: sudo systemctl status medqc-backend medqc-frontend"
echo "  查看日志: sudo journalctl -u medqc-backend -f"
echo "  重启服务: sudo systemctl restart medqc-backend medqc-frontend"
echo "  停止服务: sudo systemctl stop medqc-backend medqc-frontend"
