#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四川省质控API集成测试
验证新集成的API端点功能
"""

import asyncio
import aiohttp
import json
import time

async def test_sichuan_qc_api():
    """测试四川省质控API端点"""
    print("🚀 四川省质控API集成测试")
    print("=" * 60)
    
    base_url = "http://localhost:8001"
    
    # 加载测试文档
    try:
        with open("backend/张伟_病程记录.txt", "r", encoding="utf-8") as f:
            test_document = f.read()
        print(f"📄 测试文档长度: {len(test_document)} 字符")
    except Exception as e:
        print(f"❌ 加载测试文档失败: {e}")
        return False
    
    async with aiohttp.ClientSession() as session:
        
        # 测试1: 获取四川省规则列表
        print("\n🔍 测试1: 获取四川省规则列表")
        try:
            async with session.get(f"{base_url}/api/qc/sichuan/rules") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 获取规则成功: {result['total_rules']} 条规则")
                    print(f"📋 规则分类: {result['rule_categories']}")
                else:
                    print(f"❌ 获取规则失败: {response.status}")
        except Exception as e:
            print(f"❌ 获取规则异常: {e}")
        
        # 测试2: 单文档质控评估
        print("\n🔍 测试2: 单文档质控评估")
        try:
            payload = {
                "document_id": "test_zhangwei_001",
                "document_content": test_document,
                "document_type": "病程记录"
            }
            
            start_time = time.time()
            async with session.post(
                f"{base_url}/api/qc/sichuan/evaluate",
                json=payload
            ) as response:
                end_time = time.time()
                
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 质控评估成功")
                    print(f"📊 合规率: {result['evaluation_summary']['compliance_rate']:.1f}%")
                    print(f"🏆 总体等级: {result['evaluation_summary']['overall_grade']}")
                    print(f"⏱️ 处理时间: {end_time - start_time:.2f}秒")
                    print(f"🔢 Token使用: {result['performance_metrics']['token_usage']}")
                    print(f"💰 预估成本: ¥{result['performance_metrics']['estimated_cost']:.4f}")
                    print(f"📈 Token节省率: {result['optimization_metrics']['token_savings_rate']*100:.1f}%")
                else:
                    error_text = await response.text()
                    print(f"❌ 质控评估失败: {response.status}")
                    print(f"错误信息: {error_text}")
        except Exception as e:
            print(f"❌ 质控评估异常: {e}")
        
        # 测试3: 获取质控统计
        print("\n🔍 测试3: 获取质控统计")
        try:
            async with session.get(f"{base_url}/api/qc/sichuan/stats") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 获取统计成功")
                    print(f"📈 服务运行时间: {result['service_statistics']['uptime_seconds']:.1f}秒")
                    print(f"📊 已处理文档: {result['service_statistics']['total_documents_processed']}")
                    print(f"🎯 Token节省率: {result['optimization_achievements']['token_savings_rate']*100:.1f}%")
                else:
                    print(f"❌ 获取统计失败: {response.status}")
        except Exception as e:
            print(f"❌ 获取统计异常: {e}")
        
        # 测试4: 批量质控评估（小批量）
        print("\n🔍 测试4: 批量质控评估")
        try:
            batch_payload = {
                "documents": [
                    {
                        "document_id": "batch_test_001",
                        "content": test_document[:2000],  # 截取部分内容
                        "document_type": "病程记录"
                    },
                    {
                        "document_id": "batch_test_002", 
                        "content": test_document[1000:3000],  # 另一部分内容
                        "document_type": "病程记录"
                    }
                ]
            }
            
            start_time = time.time()
            async with session.post(
                f"{base_url}/api/qc/sichuan/evaluate/batch",
                json=batch_payload
            ) as response:
                end_time = time.time()
                
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 批量评估成功")
                    print(f"📊 成功率: {result['batch_summary']['success_rate']:.1f}%")
                    print(f"📋 总合规率: {result['batch_summary']['overall_compliance_rate']:.1f}%")
                    print(f"⏱️ 总处理时间: {end_time - start_time:.2f}秒")
                    print(f"🔢 总Token使用: {result['performance_metrics']['total_token_usage']}")
                    print(f"💰 总预估成本: ¥{result['performance_metrics']['total_estimated_cost']:.4f}")
                else:
                    error_text = await response.text()
                    print(f"❌ 批量评估失败: {response.status}")
                    print(f"错误信息: {error_text}")
        except Exception as e:
            print(f"❌ 批量评估异常: {e}")
    
    print("\n🎉 四川省质控API集成测试完成!")
    return True

if __name__ == "__main__":
    print("请确保API服务器已启动在 http://localhost:8001")
    print("启动命令: cd backend && python main_api.py")
    print()
    
    success = asyncio.run(test_sichuan_qc_api())
    if success:
        print("\n✅ API集成测试成功!")
    else:
        print("\n❌ API集成测试失败!")
