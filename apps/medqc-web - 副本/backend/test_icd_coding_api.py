#!/usr/bin/env python3
"""
ICD 编码推荐服务测试脚本

测试内容：
1. ICDCodingService.suggest_diagnosis_codes() - ICD-10 诊断编码推荐
2. ICDCodingService.suggest_procedure_codes() - ICD-9-CM-3 手术编码推荐
3. /api/v1/case-front-page/extract-coding - 从病历文本提取编码 API
"""

import asyncio
import sys
sys.path.insert(0, '/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend')

from app.services.icd_coding_service import get_icd_coding_service


async def test_icd_coding_service():
    """测试 ICD 编码推荐服务"""
    
    print("=" * 60)
    print("🧪 ICD 编码推荐服务测试")
    print("=" * 60)
    
    service = get_icd_coding_service()
    print(f"\n📌 服务配置: use_llm={service._use_llm}")
    
    # ================================
    # 测试 1: 诊断编码推荐
    # ================================
    print("\n" + "-" * 40)
    print("📋 测试 1: 诊断编码推荐 (ICD-10)")
    print("-" * 40)
    
    test_diagnoses = [
        "急性心肌梗死",
        "2型糖尿病",
        "肺炎",
        "高血压",
        "慢性肾病",
        "急性阑尾炎",
    ]
    
    for diag in test_diagnoses:
        suggestions = await service.suggest_diagnosis_codes(diag, top_k=3)
        print(f"\n🔍 诊断: {diag}")
        if suggestions:
            for s in suggestions:
                print(f"   ✅ {s['code']}: {s['name']} (置信度: {s['confidence']})")
        else:
            print("   ❌ 无匹配结果")
    
    # ================================
    # 测试 2: 手术编码推荐
    # ================================
    print("\n" + "-" * 40)
    print("📋 测试 2: 手术编码推荐 (ICD-9-CM-3)")
    print("-" * 40)
    
    test_procedures = [
        "冠状动脉支架植入术",
        "腹腔镜胆囊切除术",
        "全髋关节置换术",
        "阑尾切除术",
        "血液透析",
    ]
    
    for proc in test_procedures:
        suggestions = await service.suggest_procedure_codes(proc, top_k=3)
        print(f"\n🔍 手术: {proc}")
        if suggestions:
            for s in suggestions:
                print(f"   ✅ {s['code']}: {s['name']} (置信度: {s['confidence']})")
        else:
            print("   ❌ 无匹配结果")
    
    print("\n" + "=" * 60)
    print("✅ ICD 编码推荐服务测试完成")
    print("=" * 60)


async def test_extract_coding_api():
    """测试从病历文本提取编码 API"""
    
    print("\n" + "=" * 60)
    print("🧪 测试 /extract-coding API")
    print("=" * 60)
    
    import requests
    
    api_url = "http://localhost:8001/api/v1/case-front-page/extract-coding"
    
    test_text = """
    入院记录
    
    主诉：反复胸闷、心悸3年，加重1周
    
    诊断：
    1. 冠状动脉粥样硬化性心脏病
    2. 急性非ST段抬高型心肌梗死
    3. 高血压病3级 极高危
    4. 2型糖尿病
    
    手术：
    经皮冠状动脉介入治疗术(PCI) 前降支支架植入
    """
    
    payload = {
        "medical_text": test_text,
        "patient_age": 65,
        "patient_gender": "M"
    }
    
    try:
        response = requests.post(
            api_url, 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ API 调用成功!")
            print(f"\n📄 返回数据:")
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n❌ API 调用失败: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"\n⚠️ API 调用异常 (服务可能未启动): {e}")
        print("   请先启动后端服务: cd backend && python main.py")


if __name__ == "__main__":
    asyncio.run(test_icd_coding_service())
    asyncio.run(test_extract_coding_api())

