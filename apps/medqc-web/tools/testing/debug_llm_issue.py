#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试LLM调用问题
"""

import sys
import json
import time
from pathlib import Path

# 添加路径
sys.path.append(str(Path(__file__).parent / "poc_test"))

from llm_client import LLMClient

def test_llm_connection():
    """测试LLM连接"""
    print("🔍 调试LLM连接问题")
    print("=" * 50)
    
    # 加载配置
    config_path = Path(__file__).parent / "poc_test" / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print(f"📋 配置信息:")
    print(f"  模型: {config['llm']['model']}")
    print(f"  API Key: sk-***{config['llm']['api_key'][-10:]}")
    print(f"  Base URL: {config['llm']['base_url']}")
    print(f"  超时设置: {config['performance']['timeout_seconds']}s")
    
    # 初始化客户端
    client = LLMClient(config["llm"])
    print(f"\n🤖 LLM客户端状态:")
    print(f"  模式: {'模拟模式' if client.mock_mode else '真实API模式'}")
    
    if client.mock_mode:
        print("✅ 使用模拟模式，应该不会卡住")
        # 测试模拟调用
        try:
            start_time = time.time()
            result = client.execute_semantic_rule("S3.5.1", "测试内容：主诉：发现肛旁肿物疼痛2+天，诊断：肛周脓肿")
            end_time = time.time()
            print(f"✅ 模拟调用成功，耗时: {end_time - start_time:.2f}s")
            print(f"  结果: {result}")
        except Exception as e:
            print(f"❌ 模拟调用失败: {str(e)}")
    else:
        print("⚠️ 使用真实API模式，可能会卡住")
        # 测试真实API调用（设置短超时）
        try:
            print("🚀 开始测试真实API调用...")
            start_time = time.time()
            
            # 使用简单的测试内容
            test_context = "主诉：发现肛旁肿物疼痛2+天\n诊断：肛周脓肿"
            
            # 设置5秒超时测试
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("API调用超时")
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)  # 5秒超时
            
            try:
                result = client.execute_semantic_rule("S3.5.1", test_context)
                signal.alarm(0)  # 取消超时
                end_time = time.time()
                print(f"✅ 真实API调用成功，耗时: {end_time - start_time:.2f}s")
                print(f"  结果: {result}")
            except TimeoutError:
                print(f"❌ API调用超时（>5秒）")
                print("🔧 建议: 切换到模拟模式或检查网络连接")
            finally:
                signal.alarm(0)
                
        except Exception as e:
            print(f"❌ 真实API调用失败: {str(e)}")

def check_imports():
    """检查导入问题"""
    print("\n📦 检查依赖导入:")
    
    try:
        import requests
        print("✅ requests 导入成功")
    except ImportError as e:
        print(f"❌ requests 导入失败: {e}")
    
    try:
        from three_layer_funnel import ThreeLayerFunnelEngine
        print("✅ three_layer_funnel 导入成功")
    except ImportError as e:
        print(f"❌ three_layer_funnel 导入失败: {e}")
    
    try:
        from semantic_rule_engine import SemanticRuleEngine
        print("✅ semantic_rule_engine 导入成功")
    except ImportError as e:
        print(f"❌ semantic_rule_engine 导入失败: {e}")

def main():
    """主函数"""
    print("🐛 LLM调用问题调试工具")
    print("=" * 60)
    
    check_imports()
    test_llm_connection()
    
    print(f"\n💡 调试建议:")
    print(f"  1. 如果API调用超时，检查网络连接")
    print(f"  2. 如果要快速测试，可以临时移除API key使用模拟模式")
    print(f"  3. 检查阿里云DashScope API的可用性")

if __name__ == "__main__":
    main()
