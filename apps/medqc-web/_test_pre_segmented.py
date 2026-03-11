"""测试已切分病历的多文档质控模式"""
import time
import requests
import json

API = 'http://localhost:8001'

from _import_and_test_qc import CASE_1_ZHANGSAN

# 模拟前端传来的已切分好的文书 (截取一部分作为演示)
pre_segmented_docs = {
    "admission_record": "患者张三，男性，55岁。因“发作性胸痛1周，加重伴大汗2小时”入院。\n现病史：患者1周前...（此处省略）...初步诊断：冠心病，急性下壁心肌梗死。",
    "first_course_record": "2025-03-30 08:31 首次病程记录\n患者张三，男，55岁，因“发作性胸痛1周，加重伴大汗2小时”平车推入病房。",
    "surgery_record": "2025-03-30 09:30 手术记录\n手术名称：冠状动脉造影术+PCI术\n手术过程顺利，术后安返病房。"
}

print(f"Testing PRE-SEGMENTED records using use_multi_document_mode=True...")
print(f"Passing {len(pre_segmented_docs)} documents.")

start = time.time()

payload = {
    "document_id": "pre-segmented-test-01",
    "document_content": "This should be ignored because documents_by_type is provided",
    "use_multi_document_mode": True,
    "documents_by_type": pre_segmented_docs,
    "persist": False,
}

try:
    resp = requests.post(f"{API}/api/v1/qc/sichuan/evaluate", json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code}, Time: {elapsed:.1f}s")

    if resp.status_code == 200:
        result = resp.json()
        with open('_qc_pre_segmented_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        s = result.get('evaluation_summary', {})
        p = result.get('performance_metrics', {})
        
        print(f"\n=== PRE-SEGMENTED SUMMARY ===")
        print(f"Total rules: {s.get('total_rules')}")
        print(f"Compliant: {s.get('compliant_rules')}")
        print(f"Issues: {s.get('issues_found')}")
        print(f"Compliance rate: {s.get('compliance_rate')}%")
        print(f"Tokens: {p.get('token_usage')}")
        
        # 打印各个文档类型的评估结果概览
        doc_breakdown = s.get('document_breakdown', {})
        for doc_type, breakdown in doc_breakdown.items():
            print(f"  [{doc_type}]: {breakdown.get('total_rules')} rules, rate: {breakdown.get('compliance_rate')}%")

    else:
        print(f"FAILED: {resp.text[:500]}")
except Exception as e:
    print(f"Error calling API: {e}")
