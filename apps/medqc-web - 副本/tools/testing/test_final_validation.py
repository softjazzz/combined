#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终验证测试 - 验证三层漏斗 + 真实LLM的完整功能
"""

import sys
import os
import json
import time

# 添加路径
sys.path.append('poc_test')
sys.path.append('semantic_rules_engine')

print("🎯 最终验证测试 - 三层漏斗 + 真实LLM")
print("=" * 60)

try:
    # 导入必要的模块
    from llm_client import LLMClient
    from three_layer_funnel import ThreeLayerFunnelEngine
    
    # 加载配置
    with open('poc_test/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 初始化LLM客户端
    llm_client = LLMClient(config['llm'])
    print(f"✅ LLM客户端初始化成功 (模拟模式: {llm_client.mock_mode})")
    
    # 初始化三层漏斗引擎
    funnel_engine = ThreeLayerFunnelEngine(llm_client)
    print("✅ 三层漏斗引擎初始化成功")
    
    # 读取测试文件
    with open('测试文件1.txt', 'r', encoding='utf-8') as f:
        medical_record = f.read()
    
    print(f"✅ 测试文件加载成功 (长度: {len(medical_record)} 字符)")
    
    # 测试规则
    test_rule = "S3.5.1"
    print(f"🧪 测试规则: {test_rule}")
    
    print("\n🔍 开始三层漏斗优化...")
    start_time = time.time()
    
    # 执行三层漏斗优化
    optimized_result = funnel_engine.optimize_for_rule(test_rule, medical_record)
    
    optimization_time = time.time() - start_time
    print(f"✅ 三层漏斗优化完成 (耗时: {optimization_time:.2f}秒)")
    
    # 显示优化效果
    original_tokens = funnel_engine._estimate_tokens(medical_record)
    optimized_tokens = optimized_result.optimized_tokens
    compression_ratio = original_tokens / optimized_tokens if optimized_tokens > 0 else 1
    
    print(f"📊 优化效果:")
    print(f"   原始Tokens: {original_tokens}")
    print(f"   优化后Tokens: {optimized_tokens}")
    print(f"   压缩比: {compression_ratio:.1f}:1")
    print(f"   节省率: {((original_tokens - optimized_tokens) / original_tokens * 100):.1f}%")
    
    # 执行LLM质控
    print(f"\n🤖 开始LLM质控判断...")
    llm_start_time = time.time()
    
    # 使用优化后的上下文调用LLM
    llm_result = llm_client.execute_semantic_rule(test_rule, optimized_result.final_context)
    
    llm_time = time.time() - llm_start_time
    print(f"✅ LLM质控完成 (耗时: {llm_time:.2f}秒)")
    
    # 显示结果
    print(f"\n📋 质控结果:")
    print(f"   合规性: {'✅ 合规' if llm_result['compliant'] else '❌ 不合规'}")
    print(f"   置信度: {llm_result['confidence']}")
    print(f"   Token使用: {llm_result.get('tokens_used', 'N/A')}")
    
    if llm_result.get('explanation'):
        explanation = llm_result['explanation'][:200] + "..." if len(llm_result['explanation']) > 200 else llm_result['explanation']
        print(f"   解释: {explanation}")
    
    # 总结
    total_time = time.time() - start_time
    print(f"\n🎉 测试完成!")
    print(f"📊 总体统计:")
    print(f"   总耗时: {total_time:.2f}秒")
    print(f"   优化耗时: {optimization_time:.2f}秒")
    print(f"   LLM耗时: {llm_time:.2f}秒")
    print(f"   Token节省: {original_tokens - optimized_tokens}")
    
    # 成本估算
    if not llm_client.mock_mode and llm_result.get('tokens_used'):
        cost_per_1k_tokens = 0.003  # 假设成本
        original_cost = (original_tokens / 1000) * cost_per_1k_tokens
        optimized_cost = (optimized_tokens / 1000) * cost_per_1k_tokens
        savings = original_cost - optimized_cost
        
        print(f"💰 成本估算:")
        print(f"   原始成本: ${original_cost:.4f}")
        print(f"   优化后成本: ${optimized_cost:.4f}")
        print(f"   节省成本: ${savings:.4f}")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n🎯 验证测试结束")
