#!/usr/bin/env python3
"""
质控概念验证测试脚本
用于验证语义规则引擎与API的集成
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# 添加当前目录到路径
sys.path.append(os.path.dirname(__file__))

from qc_poc_service import get_qc_poc_service

async def test_qc_poc_service():
    """测试质控概念验证服务"""
    print("🧪 开始质控概念验证测试...")
    
    # 获取服务实例
    qc_service = get_qc_poc_service()
    
    # 测试用例1：包含主诉和现病史的正常文档
    test_content_1 = """
    患者基本信息：
    姓名：张三
    年龄：45岁
    性别：男
    
    主诉：胸痛3天
    
    现病史：患者3天前无明显诱因出现胸痛，呈压榨性，持续性，伴有胸闷、气短。
    无发热、咳嗽、咳痰。既往体健，否认高血压、糖尿病病史。
    
    体格检查：
    T 36.5℃，P 78次/分，R 18次/分，BP 120/80mmHg
    心肺腹查体未见明显异常
    
    初步诊断：
    1. 冠心病？
    2. 心绞痛？
    """
    
    # 测试用例2：缺少主诉的文档
    test_content_2 = """
    患者基本信息：
    姓名：李四
    年龄：38岁
    性别：女
    
    现病史：患者2天前出现腹痛，位于右下腹，呈持续性钝痛。
    伴有恶心、呕吐，无发热。
    
    体格检查：
    T 37.2℃，P 88次/分，R 20次/分，BP 110/70mmHg
    腹部：右下腹压痛明显，反跳痛阳性
    
    初步诊断：
    1. 急性阑尾炎
    """
    
    # 测试用例3：缺少现病史的文档
    test_content_3 = """
    患者基本信息：
    姓名：王五
    年龄：52岁
    性别：男
    
    主诉：头痛、头晕1周
    
    体格检查：
    T 36.8℃，P 92次/分，R 18次/分，BP 160/100mmHg
    神经系统查体无明显异常
    
    初步诊断：
    1. 高血压病
    """
    
    test_cases = [
        ("正常文档（包含主诉和现病史）", test_content_1),
        ("缺少主诉的文档", test_content_2),
        ("缺少现病史的文档", test_content_3)
    ]
    
    print(f"\n📋 共有 {len(test_cases)} 个测试用例")
    
    for i, (case_name, content) in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"🧪 测试用例 {i}: {case_name}")
        print(f"{'='*60}")
        
        try:
            # 执行质控分析
            result = await qc_service.analyze_document(
                document_id=f"test_doc_{i}",
                content=content
            )
            
            print(f"✅ 分析完成")
            print(f"📊 总体状态: {result['qc_status']}")
            print(f"📈 总体评分: {result['qc_score']}")
            print(f"🔍 应用规则数: {result['applied_rules']}")
            print(f"❌ 失败规则数: {result['failed_rules']}")
            print(f"🕒 分析时间: {result['analysis_time']}")
            
            print(f"\n📝 详细结果:")
            for j, rule_result in enumerate(result['results'], 1):
                status_icon = "✅" if rule_result['compliant'] else "❌"
                print(f"  {j}. {status_icon} {rule_result['rule_name']}")
                print(f"     - 合规性: {'通过' if rule_result['compliant'] else '失败'}")
                print(f"     - 置信度: {rule_result['confidence']:.2f}")
                print(f"     - 证据: {rule_result['evidence']}")
                print(f"     - 推理: {rule_result['reasoning']}")
                print(f"     - 执行时间: {rule_result['execution_time']:.3f}s")
                print()
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    # 测试规则列表获取
    print(f"\n{'='*60}")
    print("🔧 测试规则列表获取")
    print(f"{'='*60}")
    
    try:
        rules = qc_service.get_available_rules()
        print(f"✅ 获取到 {len(rules)} 条规则:")
        for rule in rules:
            print(f"  - {rule['rule_id']}: {rule['rule_name']}")
            print(f"    类别: {rule['category']}, 复杂度: {rule['complexity']}")
        
        # 测试引擎统计
        stats = qc_service.get_engine_stats()
        print(f"\n📊 引擎统计信息:")
        print(f"  - 总规则数: {stats['total_rules']}")
        print(f"  - 引擎版本: {stats['engine_version']}")
        print(f"  - 执行统计: {json.dumps(stats['execution_stats'], indent=2, ensure_ascii=False)}")
        
    except Exception as e:
        print(f"❌ 获取规则列表失败: {e}")
    
    print(f"\n🎉 概念验证测试完成！")

def test_content_hash():
    """测试内容哈希功能"""
    print("\n🔐 测试内容哈希功能...")
    
    qc_service = get_qc_poc_service()
    
    content1 = "这是测试内容1"
    content2 = "这是测试内容2"
    content3 = "这是测试内容1"  # 与content1相同
    
    hash1 = qc_service.calculate_content_hash(content1)
    hash2 = qc_service.calculate_content_hash(content2)
    hash3 = qc_service.calculate_content_hash(content3)
    
    print(f"内容1哈希: {hash1}")
    print(f"内容2哈希: {hash2}")
    print(f"内容3哈希: {hash3}")
    
    assert hash1 == hash3, "相同内容的哈希应该相同"
    assert hash1 != hash2, "不同内容的哈希应该不同"
    
    print("✅ 内容哈希功能正常")

async def main():
    """主测试函数"""
    print("🚀 启动质控概念验证测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 测试内容哈希
        test_content_hash()
        
        # 测试质控服务
        await test_qc_poc_service()
        
        print("\n🎊 所有测试通过！概念验证成功！")
        
    except Exception as e:
        print(f"\n💥 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
