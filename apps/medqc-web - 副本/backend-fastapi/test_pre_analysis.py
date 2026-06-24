#!/usr/bin/env python3
"""
测试事前分析三个测试病历的提取和 DRG 入组
"""

import json
import time
import requests

BASE_URL = "http://localhost:8000"

# 三个测试病历
TEST_CASES = [
    {
        "name": "高血压合并冠心病",
        "medical_text": """入院记录

患者张三，男，58岁，因"反复胸闷、心悸3年，加重1周"于2026年1月1日入院。

现病史：患者3年前开始出现胸闷、心悸症状，活动后加重，休息后可缓解。近1周上述症状加重，夜间阵发性呼吸困难，双下肢轻度水肿。

既往史：高血压病史10年，血压最高180/110mmHg，规律服用降压药物。无糖尿病史。

入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能III级
3. 高血压病3级（极高危）

手术情况：2026年1月3日行冠状动脉造影术+支架植入术。

出院诊断：冠心病、心力衰竭、高血压病3级"""
    },
    {
        "name": "急性阑尾炎手术",
        "medical_text": """入院记录

患者李四，男，32岁，因"转移性右下腹痛6小时"入院。

现病史：6小时前无明显诱因出现脐周疼痛，后转移至右下腹，持续性疼痛，伴恶心、低热。

体格检查：T 37.8℃，右下腹麦氏点压痛、反跳痛阳性。

入院诊断：急性阑尾炎

手术情况：2026年1月2日行腹腔镜阑尾切除术，手术顺利。

出院诊断：急性化脓性阑尾炎"""
    },
    {
        "name": "肺炎住院治疗",
        "medical_text": """入院记录

患者王五，女，65岁，因"咳嗽咳痰伴发热5天"入院。

现病史：5天前受凉后出现咳嗽，咳黄色粘痰，伴发热，体温最高39.2℃。

胸部CT：双下肺感染性病变。

入院诊断：社区获得性肺炎

治疗经过：予头孢曲松抗感染、氨溴索化痰治疗，症状好转。

出院诊断：社区获得性肺炎（双下肺）"""
    }
]


def test_extraction_and_drg(case: dict) -> dict:
    """测试单个病历的提取和 DRG 入组"""
    result = {
        "name": case["name"],
        "extraction_success": False,
        "drg_success": False,
        "admission_id": None,
        "primary_diagnosis": None,
        "drg_code": None,
        "drg_name": None,
        "weight": None,
        "baseline_payment": None,
        "error": None
    }
    
    print(f"\n{'='*60}")
    print(f"🏥 测试病历: {case['name']}")
    print(f"{'='*60}")
    
    # Step 1: 调用提取 API
    print("\n📝 Step 1: 调用 AI 结构化提取...")
    try:
        start_time = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/case-front-page/extract",
            json={"medical_text": case["medical_text"]},
            timeout=120  # LLM 可能比较慢
        )
        elapsed = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("data"):
                fp = data["data"]
                result["extraction_success"] = True
                result["admission_id"] = fp.get("admission_id")
                
                # 提取诊断信息（防止 None）
                diagnoses = fp.get("diagnoses") or {}
                main_diag = diagnoses.get("discharge_main_diagnosis_text") or diagnoses.get("admission_main_diagnosis_text")
                main_icd = diagnoses.get("discharge_main_icd") or diagnoses.get("admission_main_icd")
                result["primary_diagnosis"] = f"{main_diag} ({main_icd})" if main_diag else None
                
                print(f"   ✅ 提取成功! (耗时: {elapsed:.2f}s)")
                print(f"   📋 admission_id: {result['admission_id']}")
                print(f"   🩺 主诊断: {result['primary_diagnosis']}")
                
                # 打印诊断详情
                other_diags = diagnoses.get("discharge_other_diagnoses_texts") or []
                other_icds = diagnoses.get("discharge_other_icds") or []
                if other_diags:
                    print(f"   📋 其他诊断:")
                    for i, diag in enumerate(other_diags[:3]):
                        icd = other_icds[i] if i < len(other_icds) else "待编码"
                        print(f"      - {diag} ({icd})")
                
                # 打印手术信息（防止 None）
                procedures = fp.get("procedures") or {}
                main_proc = procedures.get("main_procedure_text")
                main_proc_code = procedures.get("main_procedure_code")
                if main_proc:
                    print(f"   🔪 主要手术: {main_proc} ({main_proc_code})")
            else:
                result["error"] = data.get("detail") or "提取返回无数据"
                print(f"   ❌ 提取失败: {result['error']}")
        else:
            result["error"] = f"HTTP {resp.status_code}"
            print(f"   ❌ 提取失败: {result['error']}")
            
    except Exception as e:
        result["error"] = str(e)
        print(f"   ❌ 提取异常: {e}")
        return result
    
    # 如果提取失败，跳过 DRG 分组
    if not result["extraction_success"] or not result["admission_id"]:
        print("\n⚠️  跳过 DRG 分组 (提取失败或无 admission_id)")
        return result
    
    # Step 2: 调用 DRG 分组 API
    print("\n📊 Step 2: 调用 DRG 分组预测...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/drg/predict",
            json={
                "admission_id": result["admission_id"],
                "region": "四川省"
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            drg_data = resp.json()
            if drg_data.get("data"):
                drg = drg_data["data"]
                result["drg_success"] = True
                result["drg_code"] = drg.get("drg_code")
                result["drg_name"] = drg.get("drg_name")
                result["weight"] = drg.get("weight")
                result["baseline_payment"] = drg.get("baseline_payment")
                
                print(f"   ✅ DRG 入组成功!")
                print(f"   🏷️  DRG 编码: {result['drg_code']}")
                print(f"   📝 DRG 名称: {result['drg_name']}")
                print(f"   ⚖️  权重 (RW): {result['weight']}")
                if result['baseline_payment']:
                    print(f"   💰 基准支付: ¥{result['baseline_payment']:,.2f}")
            else:
                result["error"] = drg_data.get("detail") or "DRG 分组返回无数据"
                print(f"   ❌ DRG 分组失败: {result['error']}")
        else:
            try:
                error_detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            except:
                error_detail = f"HTTP {resp.status_code}"
            result["error"] = error_detail
            print(f"   ❌ DRG 分组失败: {error_detail}")
            
    except Exception as e:
        result["error"] = f"DRG 异常: {str(e)}"
        print(f"   ❌ DRG 分组异常: {e}")
    
    return result


def main():
    print("\n" + "="*70)
    print("🧪 事前分析测试 - 三个测试病历提取 + DRG 入组")
    print("="*70)
    print(f"📍 后端地址: {BASE_URL}")
    print(f"📅 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    for case in TEST_CASES:
        result = test_extraction_and_drg(case)
        results.append(result)
    
    # 汇总结果
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    print(f"\n{'病历名称':<20} {'提取':<8} {'DRG入组':<10} {'DRG编码':<12} {'权重':<8}")
    print("-"*70)
    
    for r in results:
        extract_status = "✅" if r["extraction_success"] else "❌"
        drg_status = "✅" if r["drg_success"] else "❌"
        drg_code = r["drg_code"] or "-"
        weight = f"{r['weight']:.4f}" if r['weight'] else "-"
        print(f"{r['name']:<20} {extract_status:<8} {drg_status:<10} {drg_code:<12} {weight:<8}")
    
    # 统计
    extract_success = sum(1 for r in results if r["extraction_success"])
    drg_success = sum(1 for r in results if r["drg_success"])
    total = len(results)
    
    print("-"*70)
    print(f"{'总计':<20} {extract_success}/{total}     {drg_success}/{total}")
    
    if drg_success == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️  {total - drg_success} 个测试未通过 DRG 入组")
        for r in results:
            if r.get("error"):
                print(f"   - {r['name']}: {r['error']}")


if __name__ == "__main__":
    main()
