"""
语义质控规则测试 Fixtures

提供语义质控规则测试所需的各种 fixtures，包括：
- 规则数据（基于 Prompt 模板）
- 病历数据
- LLM 响应模拟数据
"""

import pytest
from typing import Dict, Any, List
import uuid
from datetime import datetime


@pytest.fixture
def sample_semantic_rule_completeness():
    """示例语义规则 - 完整性检查（基于 Prompt 模板）"""
    return {
        "id": str(uuid.uuid4()),
        "rule_code": "SR-COMP-001",
        "name": "主诉完整性检查",
        "description": "检查主诉是否完整、规范、符合医学要求",
        "category": "completeness",
        "rule_type": "subjective",
        "severity": "major",
        "prompt_template": """
你是一位资深病案质控专家。请检查以下病历的主诉是否符合要求：

## 检查标准
1. 主诉是否存在
2. 主诉是否包含主要症状
3. 主诉是否包含时间要素
4. 主诉是否简洁明了（一般不超过20字）
5. 主诉是否使用医学术语
6. 主诉是否与现病史一致

## 病历内容
{content}

请返回JSON格式：
{{
  "is_compliant": true/false,
  "score": 0-100,
  "findings": "发现的问题",
  "evidence": "证据引用",
  "confidence": 0.0-1.0
}}
""".strip(),
        "check_logic": {},
        "applicable_documents": ["首次病程记录", "入院记录"],
        "medical_domain": "通用",
        "is_active": True,
        "version": "1.0",
        "max_score": 100,
        "weight": 1.0,
        "deduction_score": 10,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture
def sample_semantic_rule_consistency():
    """示例语义规则 - 一致性检查（基于 Prompt 模板）"""
    return {
        "id": str(uuid.uuid4()),
        "rule_code": "SR-CONS-001",
        "name": "诊断一致性检查",
        "description": "检查主诉、现病史、诊断之间的一致性",
        "category": "consistency",
        "rule_type": "hybrid",
        "severity": "critical",
        "prompt_template": """
你是一位资深病案质控专家。请检查以下病历中主诉、现病史、诊断之间的一致性：

## 检查标准
1. 主诉的症状是否与现病史描述一致
2. 现病史的症状是否支持初步诊断
3. 辅助检查结果是否支持诊断
4. 诊断是否符合疾病的临床表现

## 病历内容
{content}

请返回JSON格式：
{{
  "is_compliant": true/false,
  "score": 0-100,
  "findings": "发现的问题",
  "evidence": "证据引用",
  "confidence": 0.0-1.0,
  "inconsistencies": ["不一致的地方列表"]
}}
""".strip(),
        "check_logic": {},
        "applicable_documents": ["首次病程记录", "入院记录", "出院记录"],
        "medical_domain": "通用",
        "is_active": True,
        "version": "1.0",
        "max_score": 100,
        "weight": 1.5,
        "deduction_score": 15,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture
def sample_semantic_rule_rationality():
    """示例语义规则 - 合理性检查（基于 Prompt 模板）"""
    return {
        "id": str(uuid.uuid4()),
        "rule_code": "SR-RATI-001",
        "name": "用药合理性检查",
        "description": "检查用药是否合理、是否与诊断相符",
        "category": "rationality",
        "rule_type": "subjective",
        "severity": "major",
        "prompt_template": """
你是一位资深病案质控专家和临床药师。请检查以下病历的用药是否合理：

## 检查标准
1. 用药是否与诊断相符
2. 药物剂量是否合理
3. 用药途径是否正确
4. 是否存在药物配伍禁忌
5. 是否存在重复用药
6. 是否考虑患者的既往史（如过敏史、肝肾功能等）

## 病历内容
{content}

请返回JSON格式：
{{
  "is_compliant": true/false,
  "score": 0-100,
  "findings": "发现的问题",
  "evidence": "证据引用",
  "confidence": 0.0-1.0,
  "medication_issues": ["用药问题列表"]
}}
""".strip(),
        "check_logic": {},
        "applicable_documents": ["首次病程记录", "病程记录", "出院记录"],
        "medical_domain": "通用",
        "is_active": True,
        "version": "1.0",
        "max_score": 100,
        "weight": 1.3,
        "deduction_score": 12,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture
def sample_semantic_rules_batch(
    sample_semantic_rule_completeness,
    sample_semantic_rule_consistency,
    sample_semantic_rule_rationality
):
    """批量语义规则"""
    return [
        sample_semantic_rule_completeness,
        sample_semantic_rule_consistency,
        sample_semantic_rule_rationality
    ]


@pytest.fixture
def sample_llm_response_compliant():
    """示例 LLM 响应 - 合规"""
    return {
        "choices": [
            {
                "message": {
                    "content": """
```json
{
  "is_compliant": true,
  "score": 95,
  "findings": "主诉完整、规范，包含主要症状和时间要素，与现病史一致。",
  "evidence": "主诉：反复胸闷、胸痛3天，加重伴气促1天。现病史：患者于3天前无明显诱因出现胸闷、胸痛...",
  "confidence": 0.95
}
```
""".strip()
                }
            }
        ],
        "usage": {
            "total_tokens": 1500,
            "prompt_tokens": 800,
            "completion_tokens": 700
        }
    }


@pytest.fixture
def sample_llm_response_non_compliant():
    """示例 LLM 响应 - 不合规"""
    return {
        "choices": [
            {
                "message": {
                    "content": """
```json
{
  "is_compliant": false,
  "score": 60,
  "findings": "主诉缺少时间要素，描述不够简洁明了。",
  "evidence": "主诉：胸痛。（缺少时间要素，描述过于简单）",
  "confidence": 0.85
}
```
""".strip()
                }
            }
        ],
        "usage": {
            "total_tokens": 1200,
            "prompt_tokens": 700,
            "completion_tokens": 500
        }
    }


@pytest.fixture
def sample_llm_response_malformed():
    """示例 LLM 响应 - 格式错误"""
    return {
        "choices": [
            {
                "message": {
                    "content": "这是一个格式错误的响应，不是有效的 JSON。"
                }
            }
        ],
        "usage": {
            "total_tokens": 500,
            "prompt_tokens": 300,
            "completion_tokens": 200
        }
    }


@pytest.fixture
def sample_medical_record_first_course():
    """示例病历 - 首次病程记录（完整版）"""
    return {
        "record_id": "record-test-001",
        "record_type": "first_course",
        "patient_name": "张三",
        "age": 65,
        "gender": "男",
        "department": "心内科",
        "admission_number": "2025001001",
        "bed_number": "10床",
        "admission_date": "2025-10-11",
        "admission_time": "10:00",
        "record_date": "2025-10-11 16:00",
        "doctor_name": "李医生",
        "content": """
首次病程记录

记录时间：2025年10月11日 16:00

一、患者基本信息
姓名：张三
性别：男
年龄：65岁
科室：心内科
住院号：2025001001
床号：10床
入院时间：2025年10月11日 10:00

二、主诉
反复胸闷、胸痛3天，加重伴气促1天。

三、现病史
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后，持续时间约5-10分钟，休息后可缓解。1天前上述症状加重，伴有气促、出汗，活动后明显，休息时亦有发作。

四、既往史
1. 高血压病史10年，最高血压180/110 mmHg，平时口服"硝苯地平缓释片"控制。
2. 2型糖尿病病史5年，口服"二甲双胍"控制。
3. 吸烟史30年，每天约20支，已戒烟2年。

五、体格检查
T: 36.8℃  P: 88次/分  R: 20次/分  BP: 145/90 mmHg
一般情况：神志清楚，精神欠佳，体型偏胖，营养中等。

六、辅助检查
1. 心电图：窦性心律，V1-V4导联ST段压低0.1-0.2mV，T波倒置。
2. 心肌酶谱：肌钙蛋白I 0.8 ng/mL ↑，CK-MB 45 U/L ↑。

七、初步诊断
1. 急性冠脉综合征 - 不稳定型心绞痛
2. 高血压病 3级 极高危组
3. 2型糖尿病

八、诊疗计划
1. 心内科一级护理，低盐低脂糖尿病饮食。
2. 心电监护，吸氧。
3. 药物治疗：
   - 抗血小板聚集：阿司匹林 100mg qd po + 氯吡格雷 75mg qd po
   - 抗凝治疗：低分子肝素钙 5000U q12h ih
   - 扩冠治疗：硝酸异山梨酯 10mg tid po
   - 调脂治疗：阿托伐他汀 20mg qn po

记录医师：李医生
记录时间：2025年10月11日 16:00
""".strip()
    }


@pytest.fixture
def sample_medical_record_incomplete():
    """示例病历 - 不完整的首次病程记录"""
    return {
        "record_id": "record-test-002",
        "record_type": "first_course",
        "patient_name": "李四",
        "age": 50,
        "gender": "女",
        "department": "呼吸内科",
        "content": """
首次病程记录

主诉：咳嗽。

现病史：患者咳嗽1周。

诊断：上呼吸道感染。

治疗：抗感染治疗。
""".strip()
    }

