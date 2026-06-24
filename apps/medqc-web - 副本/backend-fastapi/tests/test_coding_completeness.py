"""
编码完整性分析测试
验证 /advisor/coding-completeness/analyze 接口
"""

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import (
    ExtractionResult,
    ClinicalEntity,
    CodingGap,
    Evidence
)

class TestCodingCompleteness:
    """完整性分析集成测试"""

    def test_analyze_flow(self):
        """测试完整性分析流程 (Mock LLM)"""
        client = TestClient(app)

        # 1. 准备 Mock 数据
        mock_extraction = ExtractionResult(
            explicit_diagnoses=[
                ClinicalEntity(
                    text="急性肾衰竭",
                    category="diagnosis",
                    evidence=Evidence(
                        source="admission_note",
                        text="肌酐显著升高，考虑急性肾衰",
                        evidence_type="explicit_statement",
                        strength="strong"
                    )
                )
            ],
            clinical_indicators=[
                ClinicalEntity(
                    text="肌酐 450umol/L",
                    category="indicator",
                    evidence=Evidence(
                        source="lab_report",
                        text="Cr 450",
                        evidence_type="lab_indicator",
                        strength="strong"
                    )
                )
            ]
        )

        mock_gaps = [
            CodingGap(
                id="gap_1",
                category="diagnosis",
                subtype="missing_code",
                action="add_code",
                risk_level="medium",
                target_name="急性肾功能衰竭",
                target_code="N17.900",
                confidence=0.9,
                evidence=[
                    Evidence(
                        source="admission_note",
                        text="考虑急性肾衰",
                        evidence_type="explicit_statement",
                        strength="strong"
                    )
                ],
                justification_points=["病历明确提及", "指标支持"],
                required_documentation=[]
            )
        ]

        # 2. Patch LLM Service
        with patch("app.services.advisor_service.llm_service") as mock_llm:
            mock_llm.extract_clinical_entities = AsyncMock(return_value=mock_extraction)
            mock_llm.analyze_coding_gaps = AsyncMock(return_value=mock_gaps)

            # 3. 发送请求
            payload = {
                "medical_record": "患者因少尿入院...\n肌酐 450umol/L...",
                "current_data": {
                    "primary_diagnosis": {"code": "I10", "name": "高血压"},
                    "secondary_diagnoses": [],
                    "procedures": []
                }
            }

            response = client.post("/api/v1/advisor/coding-completeness/analyze", json=payload)

            # 4. 验证结果
            assert response.status_code == 200
            data = response.json()
            
            print(f"\nAPI Response: {data}")

            # 验证 Layer A
            assert len(data['structure_extraction']['explicit_diagnoses']) == 1
            assert data['structure_extraction']['explicit_diagnoses'][0]['text'] == "急性肾衰竭"
            
            # 验证 Layer B
            assert len(data['suggestions']) == 1
            suggestion = data['suggestions'][0]
            assert suggestion['target_code'] == "N17.900"
            assert suggestion['action'] == "add_code"

            # 验证 Mock 调用是否正确
            mock_llm.extract_clinical_entities.assert_called_once()
            mock_llm.analyze_coding_gaps.assert_called_once()

if __name__ == "__main__":
    tester = TestCodingCompleteness()
    tester.test_analyze_flow()
    print("✅ 完整性分析测试通过")
