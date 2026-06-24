#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最简单的测试 - 隔离问题
"""

print("🚀 开始简单测试...")

# 测试1: 基本Python功能
print("✅ 测试1: Python基本功能正常")

# 测试2: 文件读取
try:
    with open("测试文件1.txt", 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"✅ 测试2: 文件读取成功，长度: {len(content)}")
except Exception as e:
    print(f"❌ 测试2: 文件读取失败: {e}")

# 测试3: JSON配置加载
try:
    import json
    with open("poc_test/config.json", 'r', encoding='utf-8') as f:
        config = json.load(f)
    print(f"✅ 测试3: 配置加载成功，模型: {config['llm']['model']}")
except Exception as e:
    print(f"❌ 测试3: 配置加载失败: {e}")

# 测试4: 检查API key
try:
    api_key = config['llm']['api_key']
    if api_key and api_key.startswith('sk-'):
        print(f"⚠️ 测试4: 发现真实API key，这可能导致程序卡住")
        print(f"   建议: 临时移除API key测试模拟模式")
    else:
        print(f"✅ 测试4: 无API key，将使用模拟模式")
except:
    print(f"✅ 测试4: 无API key配置")

print("🎯 简单测试完成")
