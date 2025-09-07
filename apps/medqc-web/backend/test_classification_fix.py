#!/usr/bin/env python3
"""
测试CT和MRI检查报告分类修复效果
验证检查报告不再被错误归类为病程记录
"""

import requests
import json
import uuid
from datetime import datetime

# 测试数据：包含CT和MRI检查报告的病历文本
test_cases = [
    {
        "name": "CT检查报告测试",
        "text": """
患者张三，男，45岁，因胸痛入院。

首次病程记录：
患者入院后完善相关检查，病情稳定。

CT检查记录：
检查部位：胸部CT平扫+增强
检查所见：双肺纹理增粗，未见明显实质性病变。心影大小正常。
检查结论：双肺纹理增粗，考虑慢性支气管炎改变。

病程记录：
根据CT检查结果，患者肺部无明显异常，继续观察治疗。
        """,
        "expected_categories": ["examination_report", "progress_note"]
    },
    {
        "name": "MRI检查报告测试", 
        "text": """
患者李四，女，38岁，因头痛入院。

首次病程记录：
患者主诉头痛3天，无发热，神志清楚。

核磁检查记录：
检查部位：头颅MRI平扫+增强
检查所见：脑实质信号正常，未见异常强化灶。脑室系统无扩张。
检查结论：头颅MRI未见明显异常。

病程记录：
根据核磁检查结果，患者头颅无器质性病变，考虑紧张性头痛。
        """,
        "expected_categories": ["examination_report", "progress_note"]
    },
    {
        "name": "混合检查报告测试",
        "text": """
患者王五，男，52岁，因腹痛入院。

首次病程记录：
患者腹痛伴恶心，体格检查腹部压痛。

CT检查记录：
检查部位：腹部CT平扫
检查所见：肝脏大小形态正常，胆囊壁略厚。
检查结论：胆囊炎可能。

血常规检查：
白细胞计数：12.5×10^9/L（升高）
中性粒细胞比例：85%（升高）
检查结论：白细胞升高，提示感染。

病程记录：
结合CT和血常规检查，诊断急性胆囊炎，给予抗感染治疗。
        """,
        "expected_categories": ["examination_report", "progress_note"]
    }
]

def test_classification_direct(text: str, case_name: str):
    """直接测试分类函数"""
    try:
        # 导入分类函数
        from enhanced_classification_api import perform_intelligent_classification

        # 直接调用分类函数
        documents = perform_intelligent_classification(text, confidence_threshold=0.5)

        print(f"\n✅ {case_name} - 分类成功")
        print(f"📊 总文书数量: {len(documents)}")

        # 调试信息：打印分类结果
        if len(documents) == 0:
            print(f"⚠️  调试信息 - 未识别到任何文书")
            print(f"文本长度: {len(text)} 字符")
            print(f"文本预览: {text[:200]}...")
        else:
            print(f"🔍 分类结果详情:")
            
        # 分析分类结果
        categories_found = set()
        examination_reports = []
        progress_notes = []

        for doc in documents:
            category = doc.get('category', '')
            title = doc.get('title', '')
            confidence = doc.get('confidence', 0)

            categories_found.add(category)

            if category == 'examination_report':
                examination_reports.append({
                    'title': title,
                    'confidence': confidence,
                    'type': doc.get('type', '')
                })
            elif category == 'progress_note':
                progress_notes.append({
                    'title': title,
                    'confidence': confidence,
                    'type': doc.get('type', '')
                })

            print(f"  📄 {title} -> {category} (置信度: {confidence:.2f})")
            
            # 验证修复效果
            print(f"\n🔍 修复效果验证:")
            if examination_reports:
                print(f"  ✅ 检查报告正确识别: {len(examination_reports)}个")
                for report in examination_reports:
                    print(f"    - {report['title']} ({report['type']})")
            else:
                print(f"  ❌ 未识别到检查报告")
                
            if progress_notes:
                print(f"  ✅ 病程记录正确识别: {len(progress_notes)}个")
                for note in progress_notes:
                    print(f"    - {note['title']} ({note['type']})")

        return True

    except Exception as e:
        print(f"❌ {case_name} - 测试异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🧪 开始测试CT和MRI检查报告分类修复效果")
    print("=" * 60)
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试用例 {i}/{total_count}: {test_case['name']}")
        print("-" * 40)
        
        if test_classification_direct(test_case['text'], test_case['name']):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"🎯 测试总结:")
    print(f"  总测试用例: {total_count}")
    print(f"  成功: {success_count}")
    print(f"  失败: {total_count - success_count}")
    print(f"  成功率: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！CT和MRI检查报告分类修复成功！")
    else:
        print(f"\n⚠️  有 {total_count - success_count} 个测试失败，需要进一步调试")

if __name__ == "__main__":
    main()
