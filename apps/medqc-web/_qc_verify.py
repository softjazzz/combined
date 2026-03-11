"""简化验证脚本 - 调 QC API 并把结果保存为 JSON 文件，避免 PowerShell 编码问题。"""
import json, time, requests

API = 'http://localhost:8001'

# 用张三的首次病程记录（较短，测试速度快）
content = """首次病程记录
记录时间：2026-01-01 14:00

患者张三，男，58岁，以"反复胸闷、心悸3年，加重伴胸痛1周"为主诉入院。

病例特点：
1. 老年男性，慢性病程，急性加重
2. 主要表现为活动后胸闷、心悸，近1周出现胸痛，放射至左肩背
3. 有高血压、糖尿病、吸烟等冠心病危险因素
4. 心电图示ST-T改变
5. 心肌酶轻度升高，肌钙蛋白阳性

诊断依据：
1. 冠心病 不稳定型心绞痛：依据典型心绞痛症状、危险因素、心电图及心肌标志物改变
2. 高血压病3级：高血压病史10年，血压最高180/110mmHg，合并心脏靶器官损害
3. 2型糖尿病：糖尿病病史5年，口服降糖药

鉴别诊断：
1. 急性心肌梗死：患者肌钙蛋白轻度升高，心电图ST段压低，需动态观察
2. 心包炎：无发热、心包摩擦音，不考虑
3. 主动脉夹层：无撕裂样疼痛、血压差异，暂不考虑

诊疗计划：
1. 完善冠脉造影前准备
2. 拟于明日行冠状动脉造影检查，必要时行PCI术
3. 加强抗栓治疗，监测心肌酶变化

医师签名：李医师"""

print("Calling QC API...")
start = time.time()
try:
    resp = requests.post(f"{API}/api/v1/qc/sichuan/evaluate", json={
        "document_id": "verify-test-001",
        "document_content": content,
        "document_type": "first_course_record",
        "persist": False,
    }, timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code}, Time: {elapsed:.1f}s")
    
    if resp.status_code == 200:
        result = resp.json()
        # 保存完整结果到文件
        with open('_qc_verify_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Result saved to _qc_verify_result.json")
        
        # 打印关键信息（纯ASCII）
        summary = result.get('evaluation_summary', {})
        perf = result.get('performance_metrics', {})
        evals = result.get('evaluation_results', [])
        
        print(f"Mode: {result.get('mode', 'N/A')}")
        print(f"Model: {summary.get('model', 'N/A')}")
        print(f"Total rules: {summary.get('total_rules', 0)}")
        print(f"Compliant: {summary.get('compliant_rules', 0)}")
        print(f"Issues: {summary.get('issues_found', 0)}")
        print(f"Compliance rate: {summary.get('compliance_rate', 0)}%")
        print(f"LLM calls: {perf.get('llm_calls', 0)}")
        print(f"Token usage: {perf.get('token_usage', 0)}")
        print(f"Pipeline time: {perf.get('pipeline_time', 0)}s")
        
        non_compliant = [r for r in evals if not r.get('is_compliant', True)]
        print(f"\nNon-compliant rules ({len(non_compliant)}):")
        for r in non_compliant:
            print(f"  [{r.get('rule_id')}] {r.get('rule_name', '')[:40]}")
    else:
        print(f"FAILED: {resp.text[:300]}")
except Exception as e:
    print(f"ERROR: {e}")
