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
