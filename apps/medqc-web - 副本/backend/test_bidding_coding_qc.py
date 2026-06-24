"""
编码质控招标场景实测脚本 v2
输出完整原始 JSON 到文件
"""
import json
import requests
import sys

# 场景A：肿瘤主诊断，但没有病理编码
scenario_a = {
    "frontpage": {
        "sex": "男",
        "age": "65",
        "diagnoses": [
            {"code": "C34.901", "name": "肺腺癌"}
        ],
        "surgeries": [],
        "clinical_summary": "患者因发现肺部占位入院，行穿刺活检示肺腺癌。"
    }
}

# 场景B：阑尾炎+腹膜炎（应该合并编码）
scenario_b = {
    "frontpage": {
        "sex": "男",
        "age": "30",
        "diagnoses": [
            {"code": "K35.900", "name": "急性阑尾炎"},
            {"code": "K65.900", "name": "急性腹膜炎"}
        ],
        "surgeries": [
            {"code": "47.0901", "name": "腹腔镜下阑尾切除术"}
        ],
        "clinical_summary": "患者因右下腹痛入院，急诊行腹腔镜探查示急性化脓性阑尾炎伴局限性腹膜炎，行阑尾切除术。"
    }
}

# 场景C：冠状动脉支架置入术，应补充附加编码
scenario_c = {
    "frontpage": {
        "sex": "女",
        "age": "70",
        "diagnoses": [
            {"code": "I21.900", "name": "急性心肌梗死"}
        ],
        "surgeries": [
            {"code": "36.0700", "name": "冠状动脉支架置入术"}
        ],
        "clinical_summary": "患者因急性心梗入院，急诊行冠状动脉造影及支架植入术（PCI），术中予以球囊预扩张后植入药物洗脱支架1枚。"
    }
}

results = {}
scenarios = [
    ("场景A_肿瘤病理检查", scenario_a),
    ("场景B_阑尾炎合并编码", scenario_b),
    ("场景C_支架附加编码", scenario_c),
]

for name, payload in scenarios:
    print(f"正在测试: {name}...", file=sys.stderr)
    try:
        resp = requests.post("http://localhost:8001/api/v1/qc/coding-qc/check", json=payload, timeout=60)
        results[name] = resp.json()
    except Exception as e:
        results[name] = {"error": str(e)}

# 输出到文件
with open("bidding_qc_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("结果已保存到 bidding_qc_results.json", file=sys.stderr)
