#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四川省质控API服务启动脚本
避免导入时运行测试代码
"""

import os
import sys
import uvicorn

# 设置环境变量避免测试代码运行
os.environ['SKIP_TESTS'] = '1'

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def start_api_server():
    """启动API服务器"""
    print("🚀 启动四川省住院病历语义质控API服务器")
    print("=" * 60)
    print("📡 服务地址: http://0.0.0.0:8001")
    print("📚 API文档: http://localhost:8001/docs")
    print("🔍 健康检查: http://localhost:8001/api/health")
    print()
    print("🎯 新增四川省质控API端点:")
    print("  - POST /api/qc/sichuan/evaluate - 单文档质控评估")
    print("  - POST /api/qc/sichuan/evaluate/batch - 批量文档质控")
    print("  - GET /api/qc/sichuan/stats - 质控统计信息")
    print("  - GET /api/qc/sichuan/rules - 获取规则列表")
    print("=" * 60)
    
    # 启动服务器
    uvicorn.run(
        "backend.main_api:app",
        host="0.0.0.0",
        port=8001,
        reload=False,  # 避免重载时运行测试
        log_level="info"
    )

if __name__ == "__main__":
    start_api_server()
