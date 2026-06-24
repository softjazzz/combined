#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试LLM客户端 - 找出卡住的具体位置
"""

import sys
import os
import json
import time

# 添加路径
sys.path.append('poc_test')

print("🚀 开始LLM客户端直接测试...")

try:
    print("📦 导入LLM客户端...")
    from llm_client import LLMClient
    print("✅ LLM客户端导入成功")
    
    print("📋 加载配置...")
    with open('poc_test/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    print("✅ 配置加载成功")
    
    print("🔧 初始化LLM客户端...")
    print(f"🔑 API Key: '{config['llm']['api_key']}'")
    print(f"🌐 Base URL: '{config['llm']['base_url']}'")
    llm_client = LLMClient(config['llm'])
    print(f"🎭 模拟模式: {llm_client.mock_mode}")
    print("✅ LLM客户端初始化成功")
    
    print("💬 准备测试数据...")
    test_rule_id = "S3.5.1"
    test_context = "患者主诉：发现肛旁肿物疼痛2+天。初步诊断：肛周脓肿。"
    print(f"📝 测试规则: {test_rule_id}")
    print(f"📝 测试上下文: {test_context}")
    
    print("⏱️  开始调用LLM (添加详细日志)...")
    start_time = time.time()
    
    # 使用execute_semantic_rule方法
    print("🔍 调用 execute_semantic_rule 方法...")
    result = llm_client.execute_semantic_rule(test_rule_id, test_context)
    
    elapsed = time.time() - start_time
    print(f"✅ LLM调用完成，耗时: {elapsed:.2f}秒")
    print(f"📊 结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
except ImportError as e:
    print(f"❌ 导入错误: {e}")
except FileNotFoundError as e:
    print(f"❌ 文件未找到: {e}")
except Exception as e:
    print(f"💥 执行错误: {e}")
    import traceback
    traceback.print_exc()

print("🎯 测试完成")
