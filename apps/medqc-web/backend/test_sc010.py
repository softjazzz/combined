#!/usr/bin/env python3
"""
SC-010 现病史与主诉不符 测试脚本

测试目标：
1. 验证 LLM 能正确识别主诉与现病史一致的正例
2. 验证 LLM 能正确识别主诉与现病史矛盾的反例（时间不符、症状不符）
3. 验证评估结果的准确性与证据提取能力
"""

import requests
import json
from datetime import datetime

# API 配置
BASE_URL = "http://localhost:8000"
EVALUATE_ENDPOINT = f"{BASE_URL}/api/v1/qc/sichuan/evaluate"

# 测试用例
test_cases = [
    {
        "name": "正例：主诉与现病史一致（呼吸系统疾病）",
        "expected_compliant": True,
        "document_content": """【主诉】
反复咳嗽咳痰 2 周，加重伴发热 3 天。

【现病史】
患者 2 周前无明显诱因出现咳嗽，为阵发性干咳，偶有少量白色黏痰，无发热、胸痛、呼吸困难。自行口服止咳糖浆（具体不详）后症状无明显缓解。1 周前咳嗽加重，痰量增多，呈黄色脓性痰，量约 20-30ml/日，伴咽痛、声音嘶哑，无畏寒寒战，仍未就诊。3 天前出现发热，体温最高 38.5°C，伴畏寒、乏力、食欲减退，咳嗽咳痰进一步加重，痰呈黄绿色脓性，量约 50ml/日，并出现轻度胸闷、气促，活动后加重，无胸痛、咯血、夜间阵发性呼吸困难。自行服用对乙酰氨基酚退热，体温可暂时降至 37.5°C，但 4-6 小时后再次升高。今日症状持续无缓解，遂来我院急诊就诊。发病以来，精神食欲差，睡眠可，大小便正常，体重无明显变化。"""
    },
    {
        "name": "反例：主诉与现病史时间和症状严重矛盾",
        "expected_compliant": False,
        "document_content": """【主诉】
胸痛 3 天。

【现病史】
患者 1 周前无明显诱因出现右上腹疼痛，呈持续性钝痛，无放射，伴恶心，无呕吐、发热、腹泻。自行口服"胃痛宁"后疼痛略有缓解。5 天前疼痛加重，并出现食欲减退、乏力。自行至社区医院就诊，诊断为"胃炎"，予奥美拉唑、铝碳酸镁治疗，效果不佳。2 天前出现头晕、心悸，伴出汗，但无胸痛、胸闷。昨日再次就诊于某诊所，查心电图示"窦性心动过速"，建议来我院进一步检查，遂以"冠心病？"收入院。发病以来，精神差，食欲减退，睡眠可，大小便正常。"""
    },
    {
        "name": "反例：时间不符（主诉3天但现病史描述1个月）",
        "expected_compliant": False,
        "document_content": """【主诉】
头痛 3 天。

【现病史】
患者 1 个月前开始出现头痛，呈间歇性胀痛，伴头晕、恶心。自行口服止痛药略有缓解。近 2 周头痛加重，呈持续性钝痛，伴视物模糊。1 周前至社区医院就诊，行头部 CT 检查未见明显异常，诊断为"紧张性头痛"。昨日头痛进一步加重，伴呕吐，遂来我院就诊。"""
    }
]


def evaluate_sc010(document_content: str, case_id: str) -> dict:
    """调用 API 评估 SC-010 规则"""
    payload = {
        "document_id": case_id,
        "document_content": document_content,
        "document_type": "入院记录",
        "rule_ids": ["SC-010"]
    }

    try:
        response = requests.post(
            EVALUATE_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def print_result(case_name: str, result: dict, expected_compliant: bool):
    """打印测试结果"""
    print(f"\n{'='*80}")
    print(f"测试用例: {case_name}")
    print(f"{'='*80}")

    if "error" in result:
        print(f"❌ API 调用失败: {result['error']}")
        return False

    # Check for 'status' field (new format) instead of 'success'
    status_field = result.get("status", "")
    if status_field != "success":
        print(f"❌ API 返回失败: {result.get('error', 'Unknown error')}")
        print(f"完整响应: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
        return False

    # Get evaluation results from the response
    evaluation_results = result.get("evaluation_results", [])

    if not evaluation_results:
        print("❌ 未返回评估结果")
        return False

    sc010_result = evaluation_results[0]  # 只评估 SC-010
    is_compliant = sc010_result.get("is_compliant")
    findings = sc010_result.get("findings", "")
    evidence = sc010_result.get("evidence", "")
    suggestion = sc010_result.get("suggestion", "")
    confidence = sc010_result.get("confidence", 0.0)

    # 判断是否符合预期
    is_correct = (is_compliant == expected_compliant)
    status = "✅ 通过" if is_correct else "❌ 失败"

    print(f"\n{status}")
    print(f"预期结果: {'符合' if expected_compliant else '不符合'}")
    print(f"实际结果: {'符合' if is_compliant else '不符合'}")
    print(f"置信度: {confidence:.2%}")
    print(f"\n发现问题:")
    print(findings)
    print(f"\n证据:")
    print(evidence)
    if suggestion:
        print(f"\n改进建议:")
        print(suggestion)

    return is_correct


def main():
    print(f"\n{'='*80}")
    print(f"SC-010 现病史与主诉不符 - LLM 评估功能测试")
    print(f"{'='*80}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API 地址: {EVALUATE_ENDPOINT}")

    # 检查后端服务
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/system/health", timeout=5)
        if health_check.status_code == 200:
            print("✅ 后端服务运行正常")
        else:
            print(f"⚠️ 后端服务响应异常: {health_check.status_code}")
    except Exception as e:
        print(f"❌ 无法连接后端服务: {e}")
        print("请确保后端服务已启动: cd apps/medqc-web/backend && uvicorn app.main:app --reload --port 8000")
        return

    # 运行测试用例
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*80}")
        print(f"# 测试 {i}/{len(test_cases)}")
        print(f"{'#'*80}")

        case_id = f"test_sc010_{i}"
        result = evaluate_sc010(test_case["document_content"], case_id)
        is_correct = print_result(
            test_case["name"],
            result,
            test_case["expected_compliant"]
        )
        results.append(is_correct)

    # 汇总结果
    print(f"\n\n{'='*80}")
    print(f"测试汇总")
    print(f"{'='*80}")
    total = len(results)
    passed = sum(results)
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"总计: {total} 个测试用例")
    print(f"通过: {passed} 个 ✅")
    print(f"失败: {failed} 个 ❌")
    print(f"通过率: {pass_rate:.1f}%")

    if pass_rate == 100:
        print("\n🎉 所有测试通过！SC-010 LLM 评估功能正常。")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试。")


if __name__ == "__main__":
    main()
