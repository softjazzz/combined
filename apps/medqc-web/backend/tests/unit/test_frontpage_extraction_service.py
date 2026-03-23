"""
FrontPageExtractionService 单元测试

测试病案首页自动生成服务的各项功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

from app.services.frontpage_extraction_service import (
    FrontPageExtractionService,
    FrontPageLLMClient,
    BASIC_INFO_PROMPT,
    DIAGNOSES_PROMPT,
    ADMISSION_CONDITION_PROMPT,
)
from app.schemas.frontpage import FrontPageDraft


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    client = MagicMock(spec=FrontPageLLMClient)
    client.api_endpoint = "https://mock-api.example.com"
    client.api_key = "mock-key"
    client.generate = AsyncMock()
    return client


@pytest.fixture
def sample_medical_text():
    """示例病历文本"""
    return """
【入院记录】
姓名：张三  性别：男  年龄：65岁
身份证号：510123195901011234
婚姻状况：已婚
现住址：四川省成都市武侯区
联系人：张小三（儿子）电话：13800138000

入院时间：2025-01-01 10:30
入院科室：心内科
病案号：2025001234

主诉：胸痛3天
初步诊断：
1. 急性心肌梗死？
2. 高血压3级

【出院记录】
出院时间：2025-01-10 14:00
出院诊断：
1. 急性前壁心肌梗死
2. 高血压3级（极高危）
3. 术后心力衰竭

手术：
2025-01-02 经皮冠状动脉介入术（PCI）
术者：李主任  麻醉方式：局麻

科主任：王教授
主治医师：李主任
住院医师：小王
"""


@pytest.fixture
def mock_basic_info_response():
    """Mock 患者基本信息 LLM 响应"""
    return json.dumps({
        "patient_name": "张三",
        "gender": "1",
        "gender_text": "男",
        "birth_date": "1959-01-01",
        "age_years": 65,
        "marital_status": "2",
        "marital_status_text": "已婚",
        "id_number": "510123195901011234",
        "current_address": "四川省成都市武侯区",
        "contact_name": "张小三",
        "contact_relation": "儿子",
        "contact_phone": "13800138000"
    })


@pytest.fixture
def mock_diagnoses_response():
    """Mock 诊断信息 LLM 响应"""
    return json.dumps({
        "ed_diagnosis_texts": [],
        "discharge_main_diagnosis_text": "急性前壁心肌梗死",
        "discharge_other_diagnoses_texts": ["高血压3级（极高危）", "术后心力衰竭"],
        "admission_condition": "1"
    })


@pytest.fixture
def mock_admission_condition_response():
    """Mock 入院病情推理 LLM 响应"""
    return json.dumps({
        "results": [
            {
                "diagnosis": "急性前壁心肌梗死",
                "admission_condition": 2,
                "reasoning": "入院记录初步诊断为'急性心肌梗死？'，带问号标记为疑诊"
            },
            {
                "diagnosis": "高血压3级（极高危）",
                "admission_condition": 1,
                "reasoning": "入院记录初步诊断已明确记录'高血压3级'"
            },
            {
                "diagnosis": "术后心力衰竭",
                "admission_condition": 4,
                "reasoning": "入院记录无此诊断，为术后并发症"
            }
        ]
    })


# ============================================================================
# FrontPageLLMClient 测试
# ============================================================================

class TestFrontPageLLMClient:
    """LLM 客户端测试"""

    def test_init_without_config(self):
        """测试不带配置初始化（回退到环境变量）"""
        client = FrontPageLLMClient()
        assert client.temperature == 0.1  # 默认值
        assert client.max_tokens == 4000

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {
            "api_endpoint": "https://api.example.com",
            "api_key": "test-key",
            "model": "qwen-max",
            "custom_parameters": {
                "temperature": 0.2,
                "max_tokens": 8000
            }
        }
        client = FrontPageLLMClient(config)
        assert client.api_endpoint == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.model == "qwen-max"
        assert client.temperature == 0.2
        assert client.max_tokens == 8000


# ============================================================================
# FrontPageExtractionService 测试
# ============================================================================

class TestFrontPageExtractionService:
    """病案首页抽取服务测试"""

    def test_init_without_llm(self, monkeypatch):
        """测试无 LLM 配置时的初始化"""
        # Mock 环境变量使 LLM 不可用
        monkeypatch.setattr(
            "app.services.frontpage_extraction_service.get_settings",
            lambda: type('Settings', (), {
                'LLM_API_ENDPOINT': None,
                'LLM_API_KEY': None,
                'LLM_MODEL': 'test-model'
            })()
        )
        service = FrontPageExtractionService()
        assert service._use_llm is False  # 未配置 LLM

    def test_init_with_llm_config(self):
        """测试带 LLM 配置的初始化"""
        config = {
            "api_endpoint": "https://api.example.com",
            "api_key": "test-key",
            "model": "qwen-max"
        }
        service = FrontPageExtractionService(llm_config=config)
        assert service._use_llm is True
        assert service.llm_client.api_endpoint == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_generate_draft_from_visit_demo_mode(self):
        """测试 demo 模式下的首页生成"""
        service = FrontPageExtractionService()
        # 未配置 LLM，应使用 demo 数据
        draft = await service.generate_draft_from_visit("demo")
        
        assert isinstance(draft, FrontPageDraft)
        assert draft.basic_info is not None
        assert draft.hospitalization is not None

    @pytest.mark.asyncio
    async def test_parse_json_response_with_code_block(self):
        """测试解析带代码块的 JSON 响应"""
        service = FrontPageExtractionService()
        
        response = '''```json
{
    "patient_name": "张三",
    "age_years": 65
}
```'''
        result = service._parse_json_response(response)
        
        assert result is not None
        assert result["patient_name"] == "张三"
        assert result["age_years"] == 65

    @pytest.mark.asyncio
    async def test_parse_json_response_without_code_block(self):
        """测试解析不带代码块的 JSON 响应"""
        service = FrontPageExtractionService()
        
        response = '{"patient_name": "李四", "age_years": 50}'
        result = service._parse_json_response(response)
        
        assert result is not None
        assert result["patient_name"] == "李四"

    @pytest.mark.asyncio
    async def test_parse_json_response_invalid(self):
        """测试解析无效 JSON"""
        service = FrontPageExtractionService()
        
        result = service._parse_json_response("这不是 JSON")
        assert result is None

    def test_normalize_diagnoses_structure_split_multiline_discharge_section(self):
        """出院诊断多行时，应拆分为多条诊断而不是拼成一条。"""
        service = FrontPageExtractionService()
        medical_text = """
出院诊断：
1. 冠状动脉粥样硬化性心脏病
不稳定型心绞痛
冠状动脉支架植入术后
2. 高血压病3级 极高危
3. 2型糖尿病
4. 心功能II级
"""
        diagnoses = {
            "discharge_main_diagnosis_text": "冠状动脉粥样硬化性心脏病 不稳定型心绞痛 冠状动脉支架植入术后",
            "discharge_other_diagnoses_texts": [],
        }

        normalized = service._normalize_diagnoses_structure(medical_text, diagnoses)

        assert normalized["discharge_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病"
        assert "不稳定型心绞痛" in normalized["discharge_other_diagnoses_texts"]
        assert "冠状动脉支架植入术后" in normalized["discharge_other_diagnoses_texts"]
        assert "高血压病3级 极高危" in normalized["discharge_other_diagnoses_texts"]
        assert "2型糖尿病" in normalized["discharge_other_diagnoses_texts"]
        assert "心功能II级" in normalized["discharge_other_diagnoses_texts"]

    def test_normalize_diagnoses_structure_align_other_icds_length(self):
        """诊断拆分后，应自动补齐/截断 other ICD 列表长度。"""
        service = FrontPageExtractionService()
        medical_text = """
出院诊断：
1. 冠心病
不稳定型心绞痛
2. 高血压病3级
"""
        diagnoses = {
            "discharge_main_diagnosis_text": "冠心病 不稳定型心绞痛",
            "discharge_other_diagnoses_texts": [],
            "discharge_other_icds": ["I10"],
        }

        normalized = service._normalize_diagnoses_structure(medical_text, diagnoses)

        others = normalized["discharge_other_diagnoses_texts"]
        other_icds = normalized.get("discharge_other_icds")
        assert isinstance(other_icds, list)
        assert len(other_icds) == len(others)

    def test_build_diagnosis_evidence_marks_system_recommendation_when_differs(self):
        """医生主诊断与系统推荐不一致时，应输出差异标注与推荐理由。"""
        service = FrontPageExtractionService()
        medical_text = """
出院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 高血压病3级（极高危组）

病程记录：
患者因胸痛入院，完善冠脉造影提示前降支重度狭窄，行经皮冠状动脉支架植入术。
术后继续双联抗血小板治疗及心电监护。
"""
        diagnoses = {
            "discharge_main_diagnosis_text": "冠状动脉粥样硬化性心脏病",
            "discharge_other_diagnoses_texts": ["高血压病3级（极高危组）"],
        }
        procedures = {
            "main_procedure_text": "经皮冠状动脉支架植入术",
        }
        evidence = service._build_diagnosis_evidence(
            medical_text=medical_text,
            diagnoses=diagnoses,
            procedures=procedures,
            clinician_main_diagnosis="高血压病3级（极高危组）",
        )

        main_ev = next((x for x in evidence if x.get("diagnosis_type") == "main"), None)
        assert isinstance(main_ev, dict)
        assert main_ev.get("clinician_main_diagnosis") == "高血压病3级（极高危组）"
        assert "冠状动脉" in str(main_ev.get("system_recommended_main_diagnosis") or "")
        assert main_ev.get("recommendation_differs_from_clinician") is True
        assert main_ev.get("recommendation_label") == "更适合作为主要诊断"
        reasons = main_ev.get("recommendation_reasons") or []
        assert isinstance(reasons, list) and reasons
        reason_text = " ".join(str(item.get("reason") or "") for item in reasons if isinstance(item, dict))
        assert ("手术" in reason_text) or ("资源消耗" in reason_text)

    def test_build_diagnosis_evidence_no_diff_when_recommendation_matches_clinician(self):
        """医生主诊断与系统推荐一致时，不应触发差异标注。"""
        service = FrontPageExtractionService()
        medical_text = """
出院诊断：
1. 急性阑尾炎
2. 高血压病

病程记录：
患者因右下腹痛入院，急诊行腹腔镜阑尾切除术，术后恢复可。
"""
        diagnoses = {
            "discharge_main_diagnosis_text": "急性阑尾炎",
            "discharge_other_diagnoses_texts": ["高血压病"],
        }
        procedures = {
            "main_procedure_text": "腹腔镜阑尾切除术",
        }
        evidence = service._build_diagnosis_evidence(
            medical_text=medical_text,
            diagnoses=diagnoses,
            procedures=procedures,
            clinician_main_diagnosis="急性阑尾炎",
        )

        main_ev = next((x for x in evidence if x.get("diagnosis_type") == "main"), None)
        assert isinstance(main_ev, dict)
        assert main_ev.get("recommendation_differs_from_clinician") is False

    def test_select_context_text_strategy_full_and_retrieval(self):
        """context_strategy=full/retrieval 应构建不同上下文且可控。"""
        service = FrontPageExtractionService()
        long_text = (
            ("无关内容" * 1200)
            + "\n出院诊断：\n1. 冠状动脉粥样硬化性心脏病\n"
            + ("病程记录：胸痛，行冠脉造影及支架植入。\n" * 200)
        )

        full_ctx = service._select_context_text(
            long_text,
            "full",
            max_chars=4200,
            default_mode="full",
        )
        retrieval_ctx = service._select_context_text(
            long_text,
            "retrieval",
            max_chars=4200,
            default_mode="full",
        )
        fallback_ctx = service._select_context_text(
            long_text,
            "unknown_mode",
            max_chars=4200,
            default_mode="retrieval",
        )

        assert full_ctx == long_text
        assert len(retrieval_ctx) <= 4200
        assert "出院诊断" in retrieval_ctx
        assert len(fallback_ctx) <= 4200

    @pytest.mark.asyncio
    async def test_build_main_diagnosis_llm_evidence_success(self):
        """主诊断 LLM 解释应按约定字段返回。"""
        service = FrontPageExtractionService()
        service._use_llm = True

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "主诊断推荐解释" in prompt:
                return {
                    "clinician_main_diagnosis": "高血压病3级（极高危组）",
                    "llm_recommended_main_diagnosis": "冠状动脉粥样硬化性心脏病",
                    "is_consistent_with_clinician": False,
                    "confidence": 0.84,
                    "conclusion": "LLM 推荐冠状动脉粥样硬化性心脏病作为主诊断。",
                    "key_evidence": [
                        {
                            "quote": "患者胸痛入院，行经皮冠状动脉支架植入术。",
                            "source": "病程记录 第3天",
                            "why_it_supports": "主要治疗行为直接指向冠脉疾病。",
                        }
                    ],
                    "reasoning_summary": "本次住院核心资源消耗集中在冠脉介入治疗。",
                }
            return {}

        service._extract_json = _fake_extract_json
        result = await service._build_main_diagnosis_llm_evidence(
            medical_text="病程记录：患者胸痛入院，行经皮冠状动脉支架植入术。",
            diagnoses={
                "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
                "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
            },
            procedures={"main_procedure_text": "经皮冠状动脉支架植入术"},
            clinician_main_diagnosis="高血压病3级（极高危组）",
        )

        assert isinstance(result, dict)
        assert result.get("llm_recommended_main_diagnosis") == "冠状动脉粥样硬化性心脏病"
        assert result.get("is_consistent_with_clinician") is False
        assert isinstance(result.get("key_evidence"), list)
        assert result.get("reasoning_summary")

    @pytest.mark.asyncio
    async def test_build_main_diagnosis_llm_evidence_consistent(self):
        """主诊断一致场景应输出 is_consistent_with_clinician=true。"""
        service = FrontPageExtractionService()
        service._use_llm = True

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "主诊断推荐解释" in prompt:
                return {
                    "clinician_main_diagnosis": "急性阑尾炎",
                    "llm_recommended_main_diagnosis": "急性阑尾炎",
                    "confidence": 0.91,
                    "conclusion": "医生填写与LLM推荐一致。",
                    "key_evidence": [
                        {
                            "quote": "急诊行腹腔镜阑尾切除术，术后恢复可。",
                            "source": "手术记录 第1条",
                            "why_it_supports": "本次住院主要治疗行为为阑尾切除。",
                        }
                    ],
                    "reasoning_summary": "诊断与主要手术一致，且住院资源消耗集中在阑尾炎处理。",
                }
            return {}

        service._extract_json = _fake_extract_json
        result = await service._build_main_diagnosis_llm_evidence(
            medical_text="患者因右下腹痛入院，急诊行腹腔镜阑尾切除术。",
            diagnoses={
                "discharge_main_diagnosis_text": "急性阑尾炎",
                "discharge_other_diagnoses_texts": ["高血压病"],
            },
            procedures={"main_procedure_text": "腹腔镜阑尾切除术"},
            clinician_main_diagnosis="急性阑尾炎",
        )

        assert isinstance(result, dict)
        assert result.get("llm_recommended_main_diagnosis") == "急性阑尾炎"
        assert result.get("is_consistent_with_clinician") is True

    @pytest.mark.asyncio
    async def test_build_main_and_audit_llm_evidence_single_call_payload(self):
        """单次 LLM 审核应同时返回 main_diagnosis_llm 与 coding_audit_llm。"""
        service = FrontPageExtractionService()
        service._use_llm = True

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "一次完成“主诊断推荐解释 + 编码审核风险识别”" in prompt:
                return {
                    "main_diagnosis_llm": {
                        "clinician_main_diagnosis": "高血压病3级（极高危组）",
                        "llm_recommended_main_diagnosis": "冠状动脉粥样硬化性心脏病",
                        "is_consistent_with_clinician": False,
                        "confidence": 0.87,
                        "conclusion": "建议以冠状动脉粥样硬化性心脏病作为主诊断。",
                        "key_evidence": [
                            {
                                "quote": "行经皮冠状动脉支架植入术。",
                                "source": "病程记录 第2天",
                                "why_it_supports": "主要治疗行为指向冠脉疾病。",
                            }
                        ],
                        "reasoning_summary": "本次住院资源消耗集中于冠脉介入治疗。",
                    },
                    "coding_audit_llm": {
                        "version": "v1",
                        "summary": "识别到主诊断不当和漏写诊断风险。",
                        "confidence": 0.81,
                        "counts": {
                            "diagnosis_missing": 1,
                            "procedure_missing": 0,
                            "diagnosis_inappropriate": 1,
                            "diagnosis_insufficient_evidence": 0,
                        },
                        "findings": [
                            {
                                "type": "diagnosis_missing",
                                "severity": "high",
                                "clinician_text": "",
                                "llm_recommendation": "混合型高脂血症",
                                "reason": "病历明确记录高脂血症。",
                                "evidence": [
                                    {
                                        "quote": "血脂：TG 2.8mmol/L↑。",
                                        "source": "化验结果",
                                        "why_it_supports": "支持补充高脂血症诊断。",
                                    }
                                ],
                            }
                        ],
                    },
                }
            return {}

        service._extract_json = _fake_extract_json
        merged = await service._build_main_and_audit_llm_evidence(
            medical_text="病程记录：患者胸痛入院，行经皮冠状动脉支架植入术。",
            diagnoses={
                "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
                "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
            },
            procedures={"main_procedure_text": "经皮冠状动脉支架植入术"},
            clinician_main_diagnosis="高血压病3级（极高危组）",
        )

        assert isinstance(merged, dict)
        assert isinstance(merged.get("main_diagnosis_llm"), dict)
        assert isinstance(merged.get("coding_audit_llm"), dict)
        assert merged["main_diagnosis_llm"]["llm_recommended_main_diagnosis"] == "冠状动脉粥样硬化性心脏病"
        assert merged["coding_audit_llm"]["counts"]["diagnosis_missing"] == 1

    @pytest.mark.asyncio
    async def test_build_main_and_audit_llm_evidence_filters_dedup_and_limits(self):
        """审核 findings 应去重、类型/等级合法化并限制数量。"""
        service = FrontPageExtractionService()
        service._use_llm = True

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "一次完成“主诊断推荐解释 + 编码审核风险识别”" in prompt:
                return {
                    "main_diagnosis_llm": {
                        "clinician_main_diagnosis": "A",
                        "llm_recommended_main_diagnosis": "B",
                        "confidence": 1.5,
                    },
                    "coding_audit_llm": {
                        "counts": {
                            "diagnosis_missing": -2,
                            "procedure_missing": 0,
                            "diagnosis_inappropriate": 1,
                            "diagnosis_insufficient_evidence": 0,
                        },
                        "findings": [
                            {
                                "type": "diagnosis_missing",
                                "severity": "critical",
                                "clinician_text": "A",
                                "llm_recommendation": "B",
                                "reason": "r1",
                                "evidence": [{"quote": "q1"}, {"quote": "q2"}, {"quote": "q3"}],
                            },
                            {
                                "type": "diagnosis_missing",
                                "severity": "high",
                                "clinician_text": "A",
                                "llm_recommendation": "B",
                                "reason": "r1-dup",
                                "evidence": [{"quote": "q-dup"}],
                            },
                            {"type": "unknown", "severity": "high", "llm_recommendation": "X"},
                        ],
                    },
                }
            return {}

        service._extract_json = _fake_extract_json
        merged = await service._build_main_and_audit_llm_evidence(
            medical_text="病历",
            diagnoses={
                "discharge_main_diagnosis_text": "A",
                "discharge_other_diagnoses_texts": ["B"],
            },
            procedures={"main_procedure_text": "P"},
            clinician_main_diagnosis="A",
        )

        audit = merged.get("coding_audit_llm")
        assert isinstance(audit, dict)
        assert audit["counts"]["diagnosis_missing"] == 0
        assert len(audit["findings"]) == 1
        assert audit["findings"][0]["severity"] == "medium"
        assert len(audit["findings"][0]["evidence"]) == 2

    @pytest.mark.asyncio
    async def test_infer_admission_conditions(
        self,
        mock_llm_client,
        sample_medical_text,
        mock_admission_condition_response
    ):
        """测试入院病情推理"""
        # 设置 mock 返回
        mock_llm_client.generate.return_value = mock_admission_condition_response
        
        service = FrontPageExtractionService()
        service.llm_client = mock_llm_client
        service._use_llm = True
        
        diagnoses = {
            "discharge_main_diagnosis_text": "急性前壁心肌梗死",
            "discharge_other_diagnoses_texts": ["高血压3级（极高危）", "术后心力衰竭"],
        }
        
        result = await service._infer_admission_conditions(sample_medical_text, diagnoses)
        
        # 验证调用
        mock_llm_client.generate.assert_called_once()
        
        # 验证结果
        assert "admission_condition" in result
        assert "_admission_condition_details" in result
        assert len(result["_admission_condition_details"]) == 3

    @pytest.mark.asyncio
    async def test_infer_admission_conditions_no_diagnoses(self):
        """测试无诊断时跳过入院病情推理"""
        service = FrontPageExtractionService()
        
        diagnoses = {
            "discharge_main_diagnosis_text": None,
            "discharge_other_diagnoses_texts": [],
        }
        
        result = await service._infer_admission_conditions("", diagnoses)
        
        # 应该直接返回原始诊断，不调用 LLM
        assert result == diagnoses


# ============================================================================
# 集成测试（Mock LLM）
# ============================================================================

class TestFrontPageExtractionIntegration:
    """集成测试（使用 Mock LLM）"""

    @pytest.mark.asyncio
    async def test_full_extraction_flow(
        self,
        mock_llm_client,
        sample_medical_text,
        mock_basic_info_response,
        mock_diagnoses_response,
        mock_admission_condition_response
    ):
        """测试完整的抽取流程"""
        # 配置 mock 返回序列
        mock_llm_client.generate.side_effect = [
            mock_basic_info_response,  # 基本信息
            json.dumps({  # 住院信息
                "hospital_name": "成都市人民医院",
                "admission_datetime": "2025-01-01 10:30",
                "discharge_datetime": "2025-01-10 14:00",
                "admission_dept": "心内科",
                "actual_hospital_days": 9
            }),
            mock_diagnoses_response,  # 诊断
            json.dumps({  # 手术
                "main_procedure_text": "经皮冠状动脉介入术",
                "main_procedure_date": "2025-01-02",
                "surgeon_name": "李主任",
                "anesthesia_method": "局麻"
            }),
            json.dumps({}),  # 其他医疗信息
            json.dumps({  # 人员
                "dept_director": "王教授",
                "attending_physician": "李主任",
                "resident_physician": "小王"
            }),
            mock_admission_condition_response  # 入院病情推理
        ]
        
        service = FrontPageExtractionService()
        service.llm_client = mock_llm_client
        service._use_llm = True
        
        # 注入 mock 病历文本
        async def mock_get_medical_text(visit_id):
            return sample_medical_text
        
        service._get_medical_text = mock_get_medical_text
        
        # 执行
        draft = await service.generate_draft_from_visit("test-visit-001")
        
        # 验证结果
        assert isinstance(draft, FrontPageDraft)
        assert draft.basic_info.patient_name == "张三"
        assert draft.diagnoses.discharge_main_diagnosis_text == "急性前壁心肌梗死"

    @pytest.mark.asyncio
    async def test_stream_and_nonstream_both_include_guideline_trace_and_clinician_main(
        self,
        monkeypatch,
    ):
        """流式与非流式路径都应返回规则轨迹与医生主诊断基线。"""

        class _FakeCodingService:
            async def extract_coding(self, medical_text, patient_context):
                return {"coding_data": {}}

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "discharge_main_diagnosis_text" in prompt:
                return {
                    "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
                    "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
                }
            if "main_procedure_text" in prompt:
                return {
                    "main_procedure_text": "经皮冠状动脉支架植入术",
                }
            if "主诊断推荐解释" in prompt:
                return {
                    "main_diagnosis_llm": {
                        "clinician_main_diagnosis": "高血压病3级（极高危组）",
                        "llm_recommended_main_diagnosis": "冠状动脉粥样硬化性心脏病",
                        "is_consistent_with_clinician": False,
                        "confidence": 0.88,
                        "conclusion": "LLM 推荐冠状动脉粥样硬化性心脏病作为主诊断。",
                        "key_evidence": [
                            {
                                "quote": "病程记录：患者胸痛入院，行经皮冠状动脉支架植入术治疗。",
                                "source": "病程记录 第1条",
                                "why_it_supports": "主要治疗行为与冠脉疾病高度一致。",
                            }
                        ],
                        "reasoning_summary": "综合治疗路径与资源消耗，冠脉疾病应作为主诊断。",
                    },
                    "coding_audit_llm": {
                        "version": "v1",
                        "summary": "识别到主诊断不当风险，建议人工复核。",
                        "confidence": 0.83,
                        "counts": {
                            "diagnosis_missing": 0,
                            "procedure_missing": 0,
                            "diagnosis_inappropriate": 1,
                            "diagnosis_insufficient_evidence": 0,
                        },
                        "findings": [
                            {
                                "type": "diagnosis_inappropriate",
                                "severity": "high",
                                "clinician_text": "高血压病3级（极高危组）",
                                "llm_recommendation": "冠状动脉粥样硬化性心脏病",
                                "reason": "主要治疗行为是冠脉支架植入。",
                                "evidence": [
                                    {
                                        "quote": "病程记录：患者胸痛入院，行经皮冠状动脉支架植入术治疗。",
                                        "source": "病程记录 第1条",
                                        "why_it_supports": "治疗行为与冠脉疾病一致。",
                                    }
                                ],
                            }
                        ],
                    },
                }
            return {}

        async def _fake_infer_admission_conditions(medical_text, diagnoses):
            return diagnoses

        monkeypatch.setattr(
            "app.services.external_coding_service.get_external_coding_service",
            lambda: _FakeCodingService(),
        )
        monkeypatch.setattr(
            "app.services.local_icd_service.resolve_diagnosis_codes",
            lambda diagnoses: diagnoses,
        )
        monkeypatch.setattr(
            "app.services.local_icd_service.resolve_procedure_codes",
            lambda procedures: procedures,
        )

        service = FrontPageExtractionService()
        service._use_llm = True
        service._extract_json = _fake_extract_json
        service._infer_admission_conditions = _fake_infer_admission_conditions

        medical_text = """
出院诊断：
1. 高血压病3级（极高危组）
2. 冠状动脉粥样硬化性心脏病
病程记录：患者胸痛入院，行经皮冠状动脉支架植入术治疗。
"""
        draft = await service.extract_from_text(medical_text)
        assert isinstance(draft.evidence.get("guideline_rule_trace"), list)
        assert draft.evidence.get("clinician_main_diagnosis") == "高血压病3级（极高危组）"
        llm_evidence = draft.evidence.get("main_diagnosis_llm")
        assert isinstance(llm_evidence, dict)
        assert llm_evidence.get("llm_recommended_main_diagnosis") == "冠状动脉粥样硬化性心脏病"
        assert isinstance(draft.evidence.get("coding_audit_llm"), dict)

        done_payload = None
        async for event_name, payload in service.extract_from_text_stream(medical_text):
            if event_name == "done":
                done_payload = payload

        assert isinstance(done_payload, dict)
        frontpage = done_payload.get("frontpage") or {}
        evidence = frontpage.get("evidence") or {}
        assert isinstance(evidence.get("guideline_rule_trace"), list)
        assert evidence.get("clinician_main_diagnosis") == "高血压病3级（极高危组）"
        assert isinstance(evidence.get("main_diagnosis_llm"), dict)
        assert evidence["main_diagnosis_llm"].get("llm_recommended_main_diagnosis") == "冠状动脉粥样硬化性心脏病"
        assert isinstance(evidence.get("coding_audit_llm"), dict)

    @pytest.mark.asyncio
    async def test_stream_and_nonstream_call_merged_evidence_once(
        self,
        monkeypatch,
    ):
        """流式与非流式都应仅调用一次合并证据构建。"""

        class _FakeCodingService:
            async def extract_coding(self, medical_text, patient_context):
                return {"coding_data": {}}

        async def _fake_extract_json(prompt: str, max_tokens: int = None):
            if "仅输出 JSON" in prompt and '"diagnoses"' in prompt and '"procedures"' in prompt:
                return {
                    "diagnoses": {
                        "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
                        "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
                    },
                    "procedures": {
                        "main_procedure_text": "经皮冠状动脉支架植入术",
                    },
                }
            if "discharge_main_diagnosis_text" in prompt:
                return {
                    "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
                    "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
                }
            if "main_procedure_text" in prompt:
                return {"main_procedure_text": "经皮冠状动脉支架植入术"}
            return {}

        async def _fake_infer_admission_conditions(medical_text, diagnoses):
            return diagnoses

        monkeypatch.setattr(
            "app.services.external_coding_service.get_external_coding_service",
            lambda: _FakeCodingService(),
        )
        monkeypatch.setattr(
            "app.services.local_icd_service.resolve_diagnosis_codes",
            lambda diagnoses: diagnoses,
        )
        monkeypatch.setattr(
            "app.services.local_icd_service.resolve_procedure_codes",
            lambda procedures: procedures,
        )

        service = FrontPageExtractionService()
        service._use_llm = True
        service._extract_json = _fake_extract_json
        service._infer_admission_conditions = _fake_infer_admission_conditions
        service._build_main_and_audit_llm_evidence = AsyncMock(
            return_value={
                "main_diagnosis_llm": {
                    "clinician_main_diagnosis": "高血压病3级（极高危组）",
                    "llm_recommended_main_diagnosis": "冠状动脉粥样硬化性心脏病",
                    "is_consistent_with_clinician": False,
                    "confidence": 0.8,
                    "conclusion": "建议复核主诊断。",
                    "key_evidence": [],
                    "reasoning_summary": "摘要",
                },
                "coding_audit_llm": {
                    "version": "v1",
                    "summary": "识别到1项风险。",
                    "confidence": 0.7,
                    "counts": {
                        "diagnosis_missing": 0,
                        "procedure_missing": 0,
                        "diagnosis_inappropriate": 1,
                        "diagnosis_insufficient_evidence": 0,
                    },
                    "findings": [],
                },
            }
        )

        medical_text = """
出院诊断：
1. 高血压病3级（极高危组）
2. 冠状动脉粥样硬化性心脏病
病程记录：患者胸痛入院，行经皮冠状动脉支架植入术治疗。
"""
        await service.extract_from_text(medical_text)
        assert service._build_main_and_audit_llm_evidence.await_count == 1

        service._build_main_and_audit_llm_evidence.reset_mock()
        async for _event_name, _payload in service.extract_from_text_stream(medical_text):
            pass
        assert service._build_main_and_audit_llm_evidence.await_count == 1


# ============================================================================
# Prompt 模板测试
# ============================================================================

class TestPromptTemplates:
    """Prompt 模板测试"""

    def test_basic_info_prompt_format(self):
        """测试基本信息 Prompt 格式化"""
        formatted = BASIC_INFO_PROMPT.format(medical_text="测试病历内容")
        assert "测试病历内容" in formatted
        assert "patient_name" in formatted

    def test_diagnoses_prompt_format(self):
        """测试诊断 Prompt 格式化"""
        formatted = DIAGNOSES_PROMPT.format(medical_text="测试病历内容")
        assert "测试病历内容" in formatted
        assert "discharge_main_diagnosis_text" in formatted

    def test_admission_condition_prompt_format(self):
        """测试入院病情推理 Prompt 格式化"""
        formatted = ADMISSION_CONDITION_PROMPT.format(
            medical_text="测试病历",
            diagnoses_text="1. 主要诊断: 测试诊断"
        )
        assert "测试病历" in formatted
        assert "测试诊断" in formatted
        assert "入院病情分类标准" in formatted

def test_normalize_diagnoses_structure_supplements_llm_others_from_parsed_text():
    service = FrontPageExtractionService()
    medical_text = (
        "\u51fa\u9662\u8bca\u65ad\uff1a\n"
        "1. \u51a0\u72b6\u52a8\u8109\u7ca5\u6837\u786c\u5316\u6027\u5fc3\u810f\u75c5 "
        "\u4e0d\u7a33\u5b9a\u578b\u5fc3\u7ede\u75db \u51a0\u8109\u652f\u67b6\u690d\u5165\u540e\u72b6\u6001\n"
        "2. \u9ad8\u8840\u538b\u75c53\u7ea7\uff08\u6781\u9ad8\u5371\u7ec4\uff09\n"
        "3. 2\u578b\u7cd6\u5c3f\u75c5\n"
        "4. \u6df7\u5408\u578b\u9ad8\u8102\u8840\u75c7\n"
        "5. \u51a0\u72b6\u52a8\u8109\u652f\u67b6\u690d\u5165\u540e\u72b6\u6001\n"
    )
    diagnoses = {
        "discharge_main_diagnosis_text": "\u51a0\u72b6\u52a8\u8109\u7ca5\u6837\u786c\u5316\u6027\u5fc3\u810f\u75c5",
        "discharge_other_diagnoses_texts": [
            "\u4e0d\u7a33\u5b9a\u578b\u5fc3\u7ede\u75db",
            "\u9ad8\u8840\u538b\u75c53\u7ea7\uff08\u6781\u9ad8\u5371\u7ec4\uff09",
            "2\u578b\u7cd6\u5c3f\u75c5",
            "\u6df7\u5408\u578b\u9ad8\u8102\u8840\u75c7",
        ],
    }

    normalized = service._normalize_diagnoses_structure(medical_text, diagnoses)
    others = normalized["discharge_other_diagnoses_texts"]

    assert "\u51a0\u8109\u652f\u67b6\u690d\u5165\u540e\u72b6\u6001" in others
    assert len(others) == 5
