#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多文书质控系统测试脚本
验证重构后的分文书类型质控功能
"""

import asyncio
import json
import time
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from services.sichuan_qc_service import SichuanQCService
from services.document_separator import DocumentSeparator

# 测试用的病历内容
TEST_MEDICAL_RECORD = """
入院记录

患者姓名：张三
性别：男
年龄：45岁
入院时间：2024-01-15 10:30

主诉：胸痛3天，加重1天

现病史：患者3天前无明显诱因出现胸痛，位于胸骨后，呈压榨性疼痛，持续性，伴有气短、出汗。1天前症状加重，遂来我院就诊。

既往史：高血压病史5年，规律服用降压药物。否认糖尿病、冠心病病史。

体格检查：
T 36.8℃，P 88次/分，R 20次/分，BP 150/90mmHg
心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
双肺呼吸音清，未闻及干湿性啰音。

入院诊断：
1. 急性冠脉综合征？
2. 高血压病2级

病程记录

2024-01-15 14:00 首次病程记录
患者入院后完善相关检查，心电图示：V1-V4导联ST段压低0.1-0.2mV，T波倒置。
肌钙蛋白I：0.8ng/ml（正常<0.04ng/ml）
诊断：急性非ST段抬高型心肌梗死
治疗方案：
1. 双联抗血小板治疗：阿司匹林100mg qd，氯吡格雷75mg qd
2. 抗凝治疗：低分子肝素钠4000IU q12h皮下注射
3. 他汀类药物：阿托伐他汀20mg qn
4. ACEI类药物：依那普利5mg bid

2024-01-16 08:00 日常病程记录
患者昨夜睡眠可，无胸痛发作。今晨查房，患者一般情况好，生命体征平稳。
继续目前治疗方案，密切观察病情变化。

2024-01-17 08:00 主治医师查房记录
主治医师查房，患者病情稳定，胸痛症状明显缓解。
复查心电图较前好转，肌钙蛋白I降至0.2ng/ml。
建议择期行冠脉造影检查，明确冠脉病变情况。

手术记录

手术名称：经皮冠状动脉介入治疗术（PCI）
手术日期：2024-01-18
术者：李医师
助手：王医师
麻醉方式：局部麻醉

术前诊断：急性非ST段抬高型心肌梗死，冠心病

手术过程：
患者取仰卧位，常规消毒铺巾，局麻下经右侧桡动脉穿刺成功，置入6F动脉鞘管。
造影显示：左前降支近段95%狭窄，回旋支中段70%狭窄，右冠状动脉未见明显狭窄。
决定对左前降支病变行PCI治疗。
成功植入药物洗脱支架1枚（3.0×18mm），术后造影显示血流TIMI3级，无残余狭窄。
手术顺利，患者安返病房。

术后诊断：
1. 急性非ST段抬高型心肌梗死，PCI术后
2. 冠心病，左前降支支架植入术后

出院记录

出院时间：2024-01-22 10:00

入院情况：患者因"胸痛3天，加重1天"入院，入院诊断为急性冠脉综合征。

诊疗经过：
入院后完善相关检查，确诊为急性非ST段抬高型心肌梗死。
给予规范的药物治疗，病情稳定后行PCI治疗，成功植入支架1枚。
术后恢复良好，无并发症发生。

出院诊断：
1. 急性非ST段抬高型心肌梗死，PCI术后
2. 冠心病，左前降支支架植入术后
3. 高血压病2级

出院情况：患者一般情况良好，生命体征平稳，切口愈合良好。

出院医嘱：
1. 双联抗血小板治疗：阿司匹林100mg qd，氯吡格雷75mg qd，服用12个月
2. 他汀类药物：阿托伐他汀20mg qn
3. ACEI类药物：依那普利5mg bid
4. 定期复查心电图、心肌酶谱
5. 1个月后门诊复查

随访计划：术后1个月、3个月、6个月门诊随访
"""

async def test_document_separator():
    """测试文书分离功能"""
    print("🔍 测试文书分离功能...")
    
    separator = DocumentSeparator()
    sections = separator.separate_document(TEST_MEDICAL_RECORD)
    
    print(f"✅ 成功分离 {len(sections)} 种文书类型:")
    for doc_type, section in sections.items():
        print(f"  📋 {doc_type}:")
        print(f"    - 内容长度: {len(section.content)}字符")
        print(f"    - 置信度: {section.confidence:.2f}")
        print(f"    - 关键词: {', '.join(section.keywords_found)}")
        print(f"    - 内容预览: {section.content[:100]}...")
        print()
    
    return sections

async def test_single_prompt_mode():
    """测试单一prompt模式"""
    print("📝 测试单一prompt模式...")
    
    service = SichuanQCService()
    
    start_time = time.time()
    result = await service.evaluate_document(
        document_id="test_single_001",
        document_content=TEST_MEDICAL_RECORD,
        document_type="病程记录"
    )
    end_time = time.time()
    
    print(f"✅ 单一prompt模式完成:")
    print(f"  - 处理时间: {end_time - start_time:.2f}秒")
    print(f"  - 总规则数: {result.total_rules}")
    print(f"  - 合规规则: {result.compliant_rules}")
    print(f"  - 合规率: {result.compliant_rules/result.total_rules*100:.1f}%")
    print(f"  - Token使用: {result.token_usage}")
    print(f"  - 总体等级: {result.overall_grade}")
    print()
    
    return result

async def test_multi_document_mode():
    """测试多文书模式"""
    print("🔄 测试多文书模式...")
    
    service = SichuanQCService()
    
    start_time = time.time()
    result = await service.evaluate_multi_document(
        document_id="test_multi_001",
        document_content=TEST_MEDICAL_RECORD,
        document_types=['入院记录', '病程记录', '手术记录', '出院记录']
    )
    end_time = time.time()
    
    print(f"✅ 多文书模式完成:")
    print(f"  - 处理时间: {end_time - start_time:.2f}秒")
    print(f"  - 总规则数: {result.overall_summary['total_rules']}")
    print(f"  - 合规规则: {result.overall_summary['compliant_rules']}")
    print(f"  - 合规率: {result.overall_summary['compliance_rate']:.1f}%")
    print(f"  - Token使用: {result.total_token_usage}")
    print(f"  - 总体等级: {result.overall_grade}")
    print()
    
    print("📊 各文书类型详情:")
    for doc_type, doc_result in result.document_results.items():
        print(f"  📋 {doc_type}:")
        print(f"    - 规则数: {doc_result.total_rules}")
        print(f"    - 合规: {doc_result.compliant_rules}")
        print(f"    - 合规率: {doc_result.compliant_rules/doc_result.total_rules*100:.1f}%")
        print(f"    - 处理时间: {doc_result.processing_time:.2f}秒")
        print(f"    - Token: {doc_result.token_usage}")
        print(f"    - 置信度: {doc_result.confidence:.2f}")
    print()
    
    return result

async def compare_modes():
    """对比两种模式的性能"""
    print("⚖️ 对比两种模式的性能...")
    
    # 测试单一prompt模式
    single_result = await test_single_prompt_mode()
    
    # 测试多文书模式
    multi_result = await test_multi_document_mode()
    
    # 性能对比
    print("📈 性能对比结果:")
    print(f"  处理时间:")
    print(f"    - 单一prompt: {single_result.processing_time:.2f}秒")
    print(f"    - 多文书模式: {multi_result.total_processing_time:.2f}秒")
    print(f"    - 时间节省: {(1 - multi_result.total_processing_time/single_result.processing_time)*100:.1f}%")
    print()
    
    print(f"  Token使用:")
    print(f"    - 单一prompt: {single_result.token_usage}")
    print(f"    - 多文书模式: {multi_result.total_token_usage}")
    print(f"    - Token节省: {(1 - multi_result.total_token_usage/single_result.token_usage)*100:.1f}%")
    print()
    
    print(f"  质控准确性:")
    single_rate = single_result.compliant_rules/single_result.total_rules*100
    multi_rate = multi_result.overall_summary['compliance_rate']
    print(f"    - 单一prompt合规率: {single_rate:.1f}%")
    print(f"    - 多文书模式合规率: {multi_rate:.1f}%")
    print(f"    - 准确性提升: {multi_rate - single_rate:.1f}个百分点")

async def main():
    """主测试函数"""
    print("🚀 开始多文书质控系统测试")
    print("=" * 60)
    
    try:
        # 1. 测试文书分离
        await test_document_separator()
        
        # 2. 对比两种模式
        await compare_modes()
        
        print("✅ 所有测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
