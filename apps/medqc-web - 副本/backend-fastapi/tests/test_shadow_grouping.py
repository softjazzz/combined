"""
影子分组测试
验证 AdvisorService 和 API 接口
"""

from fastapi.testclient import TestClient
from app.main import app

class TestShadowGrouping:
    """影子分组测试集"""
    
    def test_batch_shadow_grouping(self):
        """测试批量影子分组试算"""
        client = TestClient(app)
        
        # 1. 构造请求数据
        # Baseline: 急性心肌梗死 + 1个普通诊断 (预期: 无并发症组)
        payload = {
            "request_id": "test_001",
            "baseline": {
                "primary_diagnosis": "I21.001", # 急性透壁性前壁心肌梗死 (Mock映射为 FB1)
                "secondary_diagnoses": ["I10.001"], # 高血压
                "procedures": [],
                "patient_age": 65,
                "patient_gender": "M",
                "total_hospital_days": 10
            },
            "candidates": [
                {
                    # 候选 1: 添加一个 Mock 中的 MCC (E11.901)
                    # 预期: 升级为 FB19 (伴严重并发症)
                    "id": "sug_001",
                    "add_secondary_diagnoses": ["E11.901"],
                    "eligible": True
                },
                {
                    # 候选 2: 添加一个普通诊断，凑够2个并发症
                    # 预期: 升级为 FB15 (伴并发症)
                    # Mock逻辑: len(sdx) >= 2 -> has_complications
                    "id": "sug_002",
                    "add_secondary_diagnoses": ["J00.001"],
                    "eligible": True
                },
                {
                    # 候选 3: 无效/被跳过
                    "id": "sug_skip",
                    "add_secondary_diagnoses": [],
                    "eligible": False
                }
            ]
        }
        
        # 2. 调用 API
        response = client.post("/api/v1/advisor/shadow-grouping/batch", json=payload)
        
        # 3. 验证基础响应
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nAPI Response: {data}")
        
        # 验证 Baseline
        baseline = data['baseline']
        assert baseline['drg'].startswith('FB1')
        assert '伴严重合并症' not in baseline['drg_name']
        
        # 验证结果列表
        results = data['results']
        assert len(results) == 3
        
        # 验证结果 1 (MCC 升级)
        res1 = next(r for r in results if r['id'] == 'sug_001')
        assert res1['status'] == 'computed'
        # mock group logic: if MCC -> ends with 9 and weight * 1.5
        assert res1['with_candidate']['drg'].endswith('9') 
        assert res1['drg_change_type'] == 'cc_to_mcc' or 'mcc' in res1['impact_description']
        assert res1['rw_delta'] > 0
        
        # 验证结果 2 (CC 升级)
        res2 = next(r for r in results if r['id'] == 'sug_002')
        assert res2['status'] == 'computed'
        # mock group logic: if len>=2 -> ends with 5 and weight * 1.2
        assert res2['with_candidate']['drg'].endswith('5')
        # check impact description or logic
        print(f"Result 2 Impact: {res2['impact_description']}")
        
        # 验证结果 3 (跳过)
        res3 = next(r for r in results if r['id'] == 'sug_skip')
        assert res3['status'] == 'skipped'

if __name__ == "__main__":
    # 手动运行
    tester = TestShadowGrouping()
    tester.test_batch_shadow_grouping()
    print("✅ 影子分组测试通过")
