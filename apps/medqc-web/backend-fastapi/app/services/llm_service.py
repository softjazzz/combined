"""
LLM 服务封装
使用 DeepSeek-V3 进行医疗编码辅助
"""

import json
import httpx
from typing import List, Optional, Dict, Any
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings
from app.models.schemas import (
    ICDSuggestion, 
    ValidationWarning,
    ExtractionResult,
    ClinicalEntity,
    CodingGap,
    Evidence
)


class LLMService:
    """LLM 服务类"""

    def __init__(self):
        """初始化 OpenAI 客户端（兼容 OpenAI 格式 API）"""
        self.client = None
        if OpenAI and settings.LLM_API_KEY:
            http_client = httpx.Client(trust_env=False)
            self.client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_API_URL,
                http_client=http_client
            )
        self.model = settings.LLM_MODEL

    async def suggest_icd_codes(
        self,
        diagnosis_name: str,
        context: Optional[str] = None,
        category: str = 'diagnosis',
        top_k: int = 3
    ) -> List[ICDSuggestion]:
        """
        推荐 ICD 编码

        Args:
            diagnosis_name: 诊断名称
            context: 病历上下文
            category: 编码类型（diagnosis/procedure）
            top_k: 返回推荐数量

        Returns:
            ICD 编码推荐列表
        """
        try:
            if not self.client:
                return [
                    ICDSuggestion(
                        code="MOCK.001",
                        name=f"（演示）{diagnosis_name}",
                        confidence=0.75,
                        note="未配置 LLM Key，返回演示结果"
                    )
                ]
            # 构建系统提示
            system_prompt = self._build_coding_system_prompt(category)

            # 构建用户提示
            user_prompt = self._build_coding_user_prompt(
                diagnosis_name, context, category
            )

            logger.info(f"LLM 编码推荐: {diagnosis_name}, 类型: {category}")

            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # 降低随机性，提高准确度
                max_tokens=1000,
                response_format={"type": "json_object"}  # 强制 JSON 输出
            )

            # 解析响应
            content = response.choices[0].message.content
            result = json.loads(content)

            # 转换为 Pydantic 模型
            suggestions = []
            for item in result.get('candidates', [])[:top_k]:
                suggestions.append(ICDSuggestion(
                    code=item.get('code', ''),
                    name=item.get('name', ''),
                    confidence=float(item.get('confidence', 0.0)),
                    note=item.get('note')
                ))

            logger.info(f"LLM 返回 {len(suggestions)} 条推荐")
            return suggestions

        except Exception as e:
            logger.error(f"LLM 编码推荐失败: {str(e)}")
            # 返回空列表而不是抛出异常
            return []

    async def validate_coding(
        self,
        primary_diagnosis: Dict[str, str],
        secondary_diagnoses: List[Dict[str, str]],
        procedures: List[Dict[str, str]],
        medical_record: Optional[str] = None
    ) -> List[ValidationWarning]:
        """
        编码校验

        Args:
            primary_diagnosis: 主诊断
            secondary_diagnoses: 次诊断列表
            procedures: 手术操作列表
            medical_record: 病历摘要（可选）

        Returns:
            校验警告列表
        """
        try:
            if not self.client:
                return [
                    ValidationWarning(
                        type='missing_diagnosis',
                        message='（演示）建议补充完善次诊断/合并症编码，以提升分组准确性',
                        evidence='（演示）病历摘要：...（未配置 LLM Key）',
                        severity='info'
                    )
                ]
            # 构建系统提示
            system_prompt = """你是一位经验丰富的病案编码质控专家。
你的任务是检查病案编码的完整性和准确性。

重点检查：
1. 诊断编码完整性（是否遗漏重要诊断）
2. 手术操作编码完整性
3. 并发症标记是否准确
4. 主诊断和次诊断的逻辑关系
5. 诊断与手术操作的匹配性

输出格式为 JSON：
{
  "warnings": [
    {
      "type": "missing_diagnosis",  // 类型：missing_diagnosis, procedure_missing, complication_marking, logic_conflict
      "message": "具体的警告信息",
      "evidence": "病历中的依据（如果有）",
      "severity": "info"  // info, warning, error
    }
  ]
}
"""

            # 构建用户提示
            user_prompt = f"""请检查以下编码：

主诊断：
- {primary_diagnosis['code']}: {primary_diagnosis['name']}

次诊断（{len(secondary_diagnoses)}个）：
"""
            for i, diag in enumerate(secondary_diagnoses, 1):
                user_prompt += f"{i}. {diag['code']}: {diag['name']}\n"

            if procedures:
                user_prompt += f"\n手术操作（{len(procedures)}个）：\n"
                for i, proc in enumerate(procedures, 1):
                    user_prompt += f"{i}. {proc['code']}: {proc['name']}\n"

            if medical_record:
                user_prompt += f"\n病历摘要：\n{medical_record}\n"

            user_prompt += "\n请分析以上编码是否完整、准确，给出建议。"

            logger.info("LLM 编码校验开始")

            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            # 解析响应
            content = response.choices[0].message.content
            result = json.loads(content)

            # 转换为 Pydantic 模型
            warnings = []
            for item in result.get('warnings', []):
                warnings.append(ValidationWarning(
                    type=item.get('type', 'missing_diagnosis'),
                    message=item.get('message', ''),
                    evidence=item.get('evidence'),
                    severity=item.get('severity', 'info')
                ))

            logger.info(f"LLM 返回 {len(warnings)} 条校验警告")
            return warnings

        except Exception as e:
            logger.error(f"LLM 编码校验失败: {str(e)}")
            return []

    def _build_coding_system_prompt(self, category: str) -> str:
        """构建编码推荐的系统提示"""
        if category == 'diagnosis':
            return """你是一位经验丰富的医疗编码专家，精通 ICD-10 国家临床版 2.0。
你的任务是根据诊断名称推荐最合适的 ICD-10 编码。

注意事项：
1. 优先推荐最具体、最准确的编码
2. 考虑编码的临床意义和 DRG 分组影响
3. 提供置信度评估（0-1）
4. 给出简短的推荐说明

输出格式为 JSON：
{
  "candidates": [
    {
      "code": "I21.001",
      "name": "急性前壁ST段抬高型心肌梗死",
      "confidence": 0.92,
      "note": "根据'前壁'和'ST段抬高'特征推荐"
    }
  ]
}
"""
        else:  # procedure
            return """你是一位经验丰富的医疗编码专家，精通 ICD-9-CM-3 手术操作编码。
你的任务是根据手术操作名称推荐最合适的 ICD-9-CM-3 编码。

注意事项：
1. 优先推荐最具体的手术操作编码
2. 考虑手术入路、方法等细节
3. 提供置信度评估（0-1）
4. 给出简短的推荐说明

输出格式为 JSON：
{
  "candidates": [
    {
      "code": "36.0700",
      "name": "经皮冠状动脉介入术",
      "confidence": 0.95,
      "note": "PCI 手术的标准编码"
    }
  ]
}
"""

    def _build_coding_user_prompt(
        self,
        diagnosis_name: str,
        context: Optional[str],
        category: str
    ) -> str:
        """构建编码推荐的用户提示"""
        if category == 'diagnosis':
            prompt = f"请为以下诊断推荐 ICD-10 编码：\n\n诊断名称：{diagnosis_name}\n"
        else:
            prompt = f"请为以下手术操作推荐 ICD-9-CM-3 编码：\n\n操作名称：{diagnosis_name}\n"

        if context:
            prompt += f"\n病历上下文：\n{context}\n"

        prompt += "\n请推荐最合适的编码（最多3个），并按置信度降序排列。"
        return prompt


    # ============================================
    # 3.5 编码完整性分析 (Layer A: 实体抽取)
    # ============================================

    async def extract_clinical_entities(
        self,
        medical_record: str
    ) -> ExtractionResult:
        """
        Layer A: 从病历中抽取临床实体
        """
        try:
            if not self.client:
                return ExtractionResult()

            system_prompt = self._build_extraction_system_prompt()
            user_prompt = f"病历文本：\n{medical_record}\n\n请抽取其中的临床实体。"

            logger.info("LLM 实体抽取开始 (Layer A)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1, # 抽取任务需要极低随机性
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            # 转换模型
            entities = ExtractionResult(
                explicit_diagnoses=[ClinicalEntity(**item) for item in result.get('explicit_diagnoses', [])],
                clinical_indicators=[ClinicalEntity(**item) for item in result.get('clinical_indicators', [])],
                procedure_mentions=[ClinicalEntity(**item) for item in result.get('procedure_mentions', [])]
            )
            
            logger.info(f"LLM 抽取完成: 诊断={len(entities.explicit_diagnoses)}, 指标={len(entities.clinical_indicators)}")
            return entities

        except Exception as e:
            logger.error(f"LLM 实体抽取失败: {str(e)}")
            return ExtractionResult()

    def _build_extraction_system_prompt(self) -> str:
        return """你是一个医疗文本结构化专家。任务是从病历中精准抽取临床实体。
需抽取三类信息：
1. explicit_diagnoses: 文中明确提到的疾病诊断（如"急性心肌梗死"）。
2. clinical_indicators: 异常的检验检查指标（如"肌钙蛋白T升高"、"EF 35%"）。
3. procedure_mentions: 提及的手术或治疗操作（如"PCI术后"、"行冠脉造影"）。

对于每个实体，必须提取原文证据（evidence），格式如下：
{
  "explicit_diagnoses": [
    {
      "text": "实体名称",
      "category": "diagnosis",
      "evidence": {
        "source": "admission_note",
        "text": "原文片段",
        "evidence_type": "explicit_statement",
        "strength": "strong"
      }
    }
  ],
  ...
}
"""

    # ============================================
    # 3.5 编码完整性分析 (Layer B: 差距分析)
    # ============================================

    async def analyze_coding_gaps(
        self,
        extraction_result: ExtractionResult,
        current_codes: Dict[str, Any],
        cc_mcc_info: Dict[str, Any]
    ) -> List[CodingGap]:
        """
        Layer B: 分析编码差距
        """
        try:
            if not self.client:
                return []

            system_prompt = self._build_gap_analysis_system_prompt()
            user_prompt = self._build_gap_analysis_user_prompt(
                extraction_result, current_codes, cc_mcc_info
            )

            logger.info("LLM 差距分析开始 (Layer B)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            gaps = []
            for item in result.get('suggestions', []):
                # 确保 required_documentation 是列表
                if 'required_documentation' in item and isinstance(item['required_documentation'], str):
                     item['required_documentation'] = [item['required_documentation']]
                
                gaps.append(CodingGap(**item))
                
            return gaps

        except Exception as e:
            logger.error(f"LLM 差距分析失败: {str(e)}")
            return []

    def _build_gap_analysis_system_prompt(self) -> str:
        return """你是一位DRG编码专家和临床文档改进(CDI)专家。
任务：对比"已编码数据"和"临床抽取实体"，发现编码遗漏或优化空间。

重点关注：
1. CC/MCC 遗漏：临床有证据（如指标异常），但未编码为并发症。
2. 编码特异性：已编码但不具体（如"心力衰竭" vs "慢性收缩性心力衰竭"）。
3. 手术遗漏：病历提及手术但未编码。

规则：
- 仅建议有强证据支持的编码。
- 区分 action: 'add_code' (补充) 或 'needs_doc_update' (需医生澄清).
- 如果建议添加编码，risk_level 应基于证据强度。

输出 JSON 格式：
{
  "suggestions": [
    {
      "id": "gap_1",
      "category": "diagnosis",
      "subtype": "missing_code",
      "action": "add_code",
      "risk_level": "low",
      "target_name": "建议的诊断名称",
      "target_code": "建议的ICD编码(可选)",
      "confidence": 0.95,
      "evidence": [...],
      "justification_points": ["理由1", "理由2"],
      "required_documentation": []
    }
  ]
}
"""

    def _build_gap_analysis_user_prompt(
        self,
        extraction: ExtractionResult,
        current: Dict[str, Any],
        cc_mcc: Dict[str, Any]
    ) -> str:
        prompt = "【已编码数据】\n"
        prompt += f"主诊断: {current.get('primary_diagnosis', {}).get('code')} {current.get('primary_diagnosis', {}).get('name')}\n"
        prompt += "次诊断:\n"
        for d in current.get('secondary_diagnoses', []):
            prompt += f"- {d.get('code')} {d.get('name')}\n"
        prompt += "手术操作:\n"
        for p in current.get('procedures', []):
            prompt += f"- {p.get('code')} {p.get('name')}\n"
            
        prompt += "\n【临床抽取实体 (Layer A)】\n"
        prompt += "明确诊断:\n"
        for e in extraction.explicit_diagnoses:
            prompt += f"- {e.text} (证据: {e.evidence.text})\n"
        prompt += "临床指标:\n"
        for e in extraction.clinical_indicators:
            prompt += f"- {e.text} (证据: {e.evidence.text})\n"
            
        return prompt

    # ============================================
    # 病案首页结构化提取 - 分模块并行实现
    # ============================================

    async def _extract_patient_hospitalization(self, medical_text: str) -> Dict[str, Any]:
        """模块1：提取患者基本信息和住院信息"""
        if not self.client:
            return {}
        
        system_prompt = """你是一位专业的医疗文档结构化专家。请从病历原文中提取患者基本信息和住院信息。

【输出格式】JSON，包含 basic_info 和 hospitalization 两个顶级对象。

【basic_info 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| patient_name | string | 患者姓名 | "张三" |
| gender | string | 性别编码：1=男，2=女 | "1" |
| gender_text | string | 性别文本 | "男" |
| birth_date | string | 出生日期 YYYY-MM-DD | "1981-02-04" |
| age_years | number | 年龄（岁） | 44 |
| nationality | string | 国籍 | "中国" |
| ethnicity | string | 民族 | "汉族" |
| marital_status | string | 婚姻编码：1=未婚 2=已婚 3=丧偶 4=离婚 9=其他 | "2" |
| marital_status_text | string | 婚姻文本 | "已婚" |
| id_number | string | 身份证号18位 | "510521198102040018" |
| occupation | string | 职业 | "农民" |
| current_address | string | 现住址 | "泸州市..." |
| contact_name | string | 联系人姓名 | "张伟" |
| contact_relation | string | 与患者关系 | "本人" |
| contact_phone | string | 联系人电话 | "13541593206" |

【hospitalization 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| hospital_name | string | 医疗机构名称 | "泸县人民医院" |
| medical_record_no | string | 住院号/病案号 | "350827" |
| admission_times_in_hospital | number | 本院第几次住院 | 2 |
| payment_method | string | 付费方式编码：1=城镇职工 2=城镇居民 3=新农合 4=贫困救助 5=商业保险 6=全公费 7=全自费 8=其他社保 9=其他 | "2" |
| payment_method_text | string | 付费方式文本 | "城镇居民医保" |
| admission_way | string | 入院途径编码：1=急诊 2=门诊 3=转诊 9=其他 | "2" |
| admission_way_text | string | 入院途径文本 | "门诊" |
| admission_dept | string | 入院科室 | "外二科" |
| admission_ward | string | 入院病房 | "54床" |
| admission_datetime | string | 入院时间 YYYY-MM-DD HH:mm | "2025-03-29 13:49" |
| discharge_dept | string | 出院科室 | "外二科" |
| discharge_ward | string | 出院病房 | "54床" |
| discharge_datetime | string | 出院时间 YYYY-MM-DD HH:mm | "2025-04-02 10:00" |
| actual_hospital_days | number | 实际住院天数 | 5 |
| transfer_depts | string | 转科科别（用→连接） | "外一科→外二科" |

【提取原则】
1. 严格基于病历原文提取，未明确提及的字段填 null
2. 日期格式统一为 YYYY-MM-DD 或 YYYY-MM-DD HH:mm
3. 数字字段提取纯数字
4. 编码字段同时提供编码和文本（如 gender + gender_text）"""

        user_prompt = f"请从以下病历原文中提取患者基本信息和住院信息：\n\n{medical_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("模块1（患者+住院信息）提取完成")
            return result
        except Exception as e:
            logger.error(f"模块1提取失败: {str(e)}")
            return {}

    async def _extract_diagnoses(self, medical_text: str) -> Dict[str, Any]:
        """模块2：提取诊断信息"""
        if not self.client:
            return {}
        
        system_prompt = """你是一位专业的医疗文档结构化专家。请从病历原文中提取诊断信息。

【输出格式】JSON，包含 diagnoses 一个顶级对象。

【diagnoses 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| ed_diagnosis_texts | string[] | 门/急诊诊断名称列表 | ["肛周脓肿"] |
| ed_diagnosis_codes | string[] | 门/急诊诊断编码列表 | ["K61.001"] |
| admission_main_diagnosis_text | string | 入院主诊断名称 | "肛周脓肿" |
| admission_main_icd | string | 入院主诊断ICD-10编码（无法确定填"待编码"） | "K61.001" |
| admission_other_diagnoses_texts | string[] | 入院其他诊断名称列表 | ["甲状腺功能减退"] |
| admission_other_icds | string[] | 入院其他诊断编码列表 | ["E03.900"] |
| admission_condition | number | 入院病情：1=有 2=临床未确定 3=情况不明 4=无 | 1 |
| discharge_main_diagnosis_text | string | 出院主诊断名称【首页主诊断】 | "高位复杂性肛瘘" |
| discharge_main_icd | string | 出院主诊断ICD-10编码 | "K60.300" |
| discharge_other_diagnoses_texts | string[] | 出院其他诊断名称列表 | ["肛周脓肿", "脂肪肝"] |
| discharge_other_icds | string[] | 出院其他诊断编码列表 | ["K61.001", "K76.000"] |

【诊断识别规则】
1. "入院诊断"、"初步诊断"、"目前诊断" → 填写到 admission_* 字段
2. "出院诊断"、"最终诊断"、"确定诊断"、"术后诊断" → 填写到 discharge_* 字段
3. 如果只有一种诊断，尝试同时填写入院和出院诊断
4. 诊断名称保持原文表述，不要改写
5. ICD编码如无法确定，填"待编码"

【重要】病案首页的主诊断取"出院主诊断"（discharge_main_diagnosis_text）"""

        user_prompt = f"请从以下病历原文中提取诊断信息：\n\n{medical_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("模块2（诊断信息）提取完成")
            return result
        except Exception as e:
            logger.error(f"模块2提取失败: {str(e)}")
            return {}

    async def _extract_procedures_staff(self, medical_text: str) -> Dict[str, Any]:
        """模块3：提取手术操作和人员信息"""
        if not self.client:
            return {}
        
        system_prompt = """你是一位专业的医疗文档结构化专家。请从病历原文中提取手术操作和人员信息。

【输出格式】JSON，包含 procedures 和 staff 两个顶级对象。

【procedures 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| main_procedure_text | string | 主要手术/操作名称 | "高位复杂性肛瘘切除术" |
| main_procedure_code | string | 主要手术ICD-9-CM-3编码（无法确定填"待编码"） | "49.12" |
| main_procedure_date | string | 手术日期 YYYY-MM-DD | "2025-03-31" |
| main_procedure_level | string | 手术级别：1=一级 2=二级 3=三级 4=四级 | "3" |
| surgeon_name | string | 术者姓名 | "王标" |
| assistant1_name | string | I助姓名 | "孙治庆" |
| assistant2_name | string | II助姓名 | null |
| anesthesia_method | string | 麻醉方式 | "腰麻联合硬脊膜外腔阻滞麻醉" |
| anesthetist_name | string | 麻醉医师姓名 | "刘杰" |
| incision_healing_grade | string | 切口愈合等级（0=无切口/I/甲/I/乙/.../III/丙） | "I/甲" |
| other_procedures | object[] | 其他手术操作列表 | [{"text":"...", "code":"...", "date":"..."}] |

【staff 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| dept_director | string | 科主任 | "王飞" |
| chief_physician | string | 主任/副主任医师 | "张云海" |
| attending_physician | string | 主治医师 | "王标" |
| resident_physician | string | 住院医师 | "冯军" |
| responsible_nurse | string | 责任护士 | "高利萍" |
| coder | string | 编码员 | null |
| quality_control_physician | string | 质控医师 | null |
| quality_control_nurse | string | 质控护士 | null |

【提取原则】
1. 手术名称保持原文表述，不要改写
2. 日期格式统一为 YYYY-MM-DD
3. 如无手术操作，procedures 各字段填 null
4. 从"术前讨论"、"手术记录"等段落识别人员信息"""

        user_prompt = f"请从以下病历原文中提取手术操作和人员信息：\n\n{medical_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("模块3（手术+人员信息）提取完成")
            return result
        except Exception as e:
            logger.error(f"模块3提取失败: {str(e)}")
            return {}

    async def _extract_other_medical_costs(self, medical_text: str) -> Dict[str, Any]:
        """模块4：提取其他医疗信息和费用"""
        if not self.client:
            return {}
        
        system_prompt = """你是一位专业的医疗文档结构化专家。请从病历原文中提取其他医疗信息和费用信息。

【输出格式】JSON，包含 other_medical_info 和 costs 两个顶级对象。

【other_medical_info 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| pathology_no | string | 病理号 | "P2025001" |
| pathology_text | string | 病理诊断名称 | "鳞状细胞癌" |
| pathology_code | string | 病理诊断编码 | "M80703" |
| drug_allergy_flag | number | 药物过敏标志：1=无 2=有 | 1 |
| drug_allergy_flag_text | string | 药物过敏标志文本 | "无" |
| drug_allergy_drugs | string[] | 过敏药物列表 | ["青霉素"] |
| abo_blood_type | string | ABO血型：A/B/O/AB/不详/未查 | "O" |
| rh_blood_type | string | Rh血型编码：1=阴 2=阳 3=不详 4=未查 | "2" |
| rh_blood_type_text | string | Rh血型文本 | "阳性" |
| autopsy | string | 死亡患者尸检：1=是 2=否，非死亡填"-" | "-" |
| ventilation_hours | number | 机械通气总时长（小时） | 48 |
| icu_type | string | ICU类型 | "综合ICU" |
| icu_enter_time | string | 进入ICU时间 | "2025-03-31 14:00" |
| icu_leave_time | string | 退出ICU时间 | "2025-04-01 10:00" |
| discharge_method | number | 离院方式：1=医嘱离院 2=医嘱转院 3=转社区 4=非医嘱 5=死亡 9=其他 | 1 |
| readmission_plan | number | 31天内再住院计划：1=有 2=无 | 2 |
| readmission_purpose | string | 再住院目的 | "化疗" |

【costs 字段定义】
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| total_cost | number | 住院总费用（元） | 8562.50 |
| self_paid | number | 自付金额（元） | 1285.00 |

【提取原则】
1. 费用只提取 total_cost 和 self_paid，其他费用明细由 HIS 系统提供
2. 费用提取纯数字，不含单位
3. 药物过敏：如病历提到"否认过敏史"、"无药物过敏"，drug_allergy_flag 填 1
4. 如病历未提及某字段，填 null"""

        user_prompt = f"请从以下病历原文中提取其他医疗信息和费用信息：\n\n{medical_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("模块4（其他信息+费用）提取完成")
            return result
        except Exception as e:
            logger.error(f"模块4提取失败: {str(e)}")
            return {}

    async def extract_frontpage_structured(
        self,
        medical_text: str
    ) -> Dict[str, Any]:
        """
        从病历原文中提取病案首页结构化数据（分模块并行提取）
        
        Args:
            medical_text: 病历原文（入院记录、出院小结等）
            
        Returns:
            结构化的病案首页数据（患者信息、诊断、手术操作等 7 大类）
        """
        import asyncio
        
        try:
            if not self.client:
                logger.warning("LLM 客户端未初始化，返回空结果")
                return {}

            logger.info("开始分模块并行提取病案首页数据...")
            
            # 并行执行 4 个提取模块
            results = await asyncio.gather(
                self._extract_patient_hospitalization(medical_text),
                self._extract_diagnoses(medical_text),
                self._extract_procedures_staff(medical_text),
                self._extract_other_medical_costs(medical_text),
                return_exceptions=True
            )
            
            # 合并结果
            merged = {}
            module_names = ["患者+住院", "诊断", "手术+人员", "其他+费用"]
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"模块 {module_names[i]} 提取异常: {str(result)}")
                    continue
                if isinstance(result, dict):
                    merged.update(result)
            
            # 确保所有顶级键都存在
            default_keys = ["basic_info", "hospitalization", "diagnoses", 
                           "procedures", "other_medical_info", "staff", "costs"]
            for key in default_keys:
                if key not in merged:
                    merged[key] = {}
            
            logger.info(f"病案首页结构化提取完成: 成功合并 {len([r for r in results if isinstance(r, dict)])} 个模块")
            
            # 日志输出关键信息
            diagnoses = merged.get("diagnoses", {})
            main_diag = diagnoses.get("discharge_main_diagnosis_text") or diagnoses.get("admission_main_diagnosis_text")
            logger.info(f"主诊断: {main_diag or 'N/A'}")
            
            return merged

        except Exception as e:
            logger.error(f"LLM 病案首页结构化提取失败: {str(e)}")
            return {}


    async def generate_icd_codes(
        self,
        diagnoses: List[str],
        procedures: List[str] = None
    ) -> Dict[str, Any]:
        """
        为诊断和手术名称生成 ICD 编码
        
        Args:
            diagnoses: 诊断名称列表
            procedures: 手术/操作名称列表
            
        Returns:
            包含 diagnoses_with_codes 和 procedures_with_codes 的字典
        """
        try:
            if not self.client:
                logger.warning("LLM 客户端未初始化，返回空编码")
                return {"diagnoses_with_codes": [], "procedures_with_codes": []}

            if not diagnoses and not procedures:
                return {"diagnoses_with_codes": [], "procedures_with_codes": []}

            system_prompt = """你是一位专业的病案编码员，精通 ICD-10 诊断编码和 ICD-9-CM-3 手术操作编码。
你的任务是为给定的诊断名称和手术名称生成对应的 ICD 编码。

编码规则：
1. 诊断使用 ICD-10 编码标准（中国临床版）
2. 手术/操作使用 ICD-9-CM-3 编码标准
3. 编码格式：主码.亚目（如 I10.x00, K61.001）
4. 如果诊断可能对应多个编码，选择最匹配的一个
5. 如果完全无法确定编码，填写 "待人工编码"

输出 JSON 格式：
{
  "diagnoses_with_codes": [
    {"name": "诊断名称", "icd_code": "I10.x00", "confidence": 0.95},
    ...
  ],
  "procedures_with_codes": [
    {"name": "手术名称", "icd_code": "88.55", "confidence": 0.90},
    ...
  ]
}

confidence 表示编码置信度（0-1），高于0.8表示高置信度。"""

            diagnoses_list = diagnoses or []
            procedures_list = procedures or []
            
            user_prompt = f"""请为以下诊断和手术生成 ICD 编码：

诊断列表：
{chr(10).join([f"- {d}" for d in diagnoses_list]) if diagnoses_list else "无"}

手术/操作列表：
{chr(10).join([f"- {p}" for p in procedures_list]) if procedures_list else "无"}

请按 JSON 格式输出编码结果。"""

            logger.info(f"LLM ICD 编码开始: {len(diagnoses_list)} 个诊断, {len(procedures_list)} 个手术")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"LLM ICD 编码完成: {len(result.get('diagnoses_with_codes', []))} 个诊断编码")
            return result

        except Exception as e:
            logger.error(f"LLM ICD 编码生成失败: {str(e)}")
            return {"diagnoses_with_codes": [], "procedures_with_codes": []}

    async def analyze_patient_profile(
        self,
        medical_text: str,
        frontpage_diagnoses: List[str] = None,
        frontpage_procedures: List[str] = None
    ) -> Dict[str, Any]:
        """
        AI 患者画像分析
        
        从病历原文中提取：
        - 诊断发生发展时间轴
        - 生命体征趋势
        - 化验检查结果分析
        - 风险评估
        - 人体部位标记
        
        Args:
            medical_text: 病历原文
            frontpage_diagnoses: 首页诊断列表（用于交叉验证）
            frontpage_procedures: 首页手术列表（用于交叉验证）
            
        Returns:
            患者画像分析结果
        """
        try:
            if not self.client:
                logger.warning("LLM 客户端未初始化，返回模拟数据")
                return self._get_mock_profile_data()

            system_prompt = """你是一位资深医疗数据分析师，擅长从病历中提取关键临床信息并进行深度分析。

请从病历原文中提取以下信息，输出 JSON 格式：

{
  "diagnosis_timeline": [
    {
      "date": "日期或时间点",
      "event": "诊断/症状/检查事件描述",
      "type": "symptom|diagnosis|examination|treatment",
      "severity": "mild|moderate|severe|critical"
    }
  ],
  "vital_signs": {
    "blood_pressure": {
      "values": [{"time": "时间", "systolic": 收缩压, "diastolic": 舒张压}],
      "trend": "stable|rising|falling|fluctuating",
      "assessment": "评估说明"
    },
    "heart_rate": {
      "values": [{"time": "时间", "value": 心率}],
      "trend": "stable|rising|falling",
      "assessment": "评估说明"
    },
    "temperature": {
      "values": [{"time": "时间", "value": 体温}],
      "assessment": "评估说明"
    }
  },
  "lab_results": {
    "blood_glucose": {"value": 数值, "unit": "mmol/L", "status": "normal|high|low"},
    "cholesterol": {"value": 数值, "unit": "mmol/L", "status": "normal|high|low"},
    "triglycerides": {"value": 数值, "unit": "mmol/L", "status": "normal|high|low"},
    "creatinine": {"value": 数值, "unit": "μmol/L", "status": "normal|high|low"},
    "ldl": {"value": 数值, "unit": "mmol/L", "status": "normal|high|low"}
  },
  "risk_assessment": {
    "overall_risk_score": 0-100的风险评分,
    "risk_level": "low|medium|high|critical",
    "primary_risks": ["主要风险因素1", "主要风险因素2"],
    "recommendations": ["建议1", "建议2"]
  },
  "body_markers": [
    {
      "region": "heart|lung|liver|kidney|brain|pancreas|stomach",
      "condition": "诊断/问题描述",
      "severity": "mild|moderate|severe",
      "position": {"top": "百分比", "left": "百分比"}
    }
  ],
  "discrepancies": [
    {
      "type": "missing|mismatch|incomplete",
      "field": "存在问题的字段",
      "description": "差异描述",
      "suggestion": "修正建议"
    }
  ]
}

注意：
- 如果病历中未提及某项检查，对应字段设为 null
- 时间轴按时间顺序排列
- 风险评分基于诊断严重程度、合并症数量、年龄等综合评估
- body_markers 的 position 用于前端可视化定位"""

            frontpage_info = ""
            if frontpage_diagnoses:
                frontpage_info += f"\n首页诊断列表：{', '.join(frontpage_diagnoses)}"
            if frontpage_procedures:
                frontpage_info += f"\n首页手术列表：{', '.join(frontpage_procedures)}"

            user_prompt = f"""请对以下病历进行深度画像分析：

{medical_text}
{frontpage_info}

请按照系统提示的 JSON 格式输出分析结果。"""

            logger.info("LLM 患者画像分析开始")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"LLM 患者画像分析完成: 时间轴事件数={len(result.get('diagnosis_timeline', []))}")
            return result

        except Exception as e:
            logger.error(f"LLM 患者画像分析失败: {str(e)}")
            return self._get_mock_profile_data()

    def _get_mock_profile_data(self) -> Dict[str, Any]:
        """返回模拟的患者画像数据"""
        return {
            "diagnosis_timeline": [
                {"date": "2026-01-01 10:30", "event": "因胸闷心悸入院", "type": "symptom", "severity": "moderate"},
                {"date": "2026-01-01 14:00", "event": "心电图检查示ST段改变", "type": "examination", "severity": "moderate"},
                {"date": "2026-01-02 09:00", "event": "冠状动脉造影术", "type": "treatment", "severity": "moderate"},
                {"date": "2026-01-02 15:00", "event": "确诊冠状动脉粥样硬化", "type": "diagnosis", "severity": "severe"}
            ],
            "vital_signs": {
                "blood_pressure": {
                    "values": [
                        {"time": "08:00", "systolic": 135, "diastolic": 85},
                        {"time": "12:00", "systolic": 138, "diastolic": 88},
                        {"time": "16:00", "systolic": 142, "diastolic": 92},
                        {"time": "20:00", "systolic": 140, "diastolic": 90}
                    ],
                    "trend": "fluctuating",
                    "assessment": "血压控制欠佳，需调整降压方案"
                },
                "heart_rate": {
                    "values": [
                        {"time": "08:00", "value": 78},
                        {"time": "12:00", "value": 82},
                        {"time": "16:00", "value": 85},
                        {"time": "20:00", "value": 80}
                    ],
                    "trend": "stable",
                    "assessment": "心率在正常范围内"
                }
            },
            "lab_results": {
                "blood_glucose": {"value": 7.8, "unit": "mmol/L", "status": "high"},
                "cholesterol": {"value": 6.2, "unit": "mmol/L", "status": "high"},
                "triglycerides": {"value": 2.8, "unit": "mmol/L", "status": "high"},
                "creatinine": {"value": 95, "unit": "μmol/L", "status": "normal"},
                "ldl": {"value": 3.5, "unit": "mmol/L", "status": "high"}
            },
            "risk_assessment": {
                "overall_risk_score": 85,
                "risk_level": "high",
                "primary_risks": ["高血压控制不良", "血糖偏高", "血脂异常", "冠心病"],
                "recommendations": ["调整降压药物", "强化血糖管理", "他汀类药物治疗", "定期心脏随访"]
            },
            "body_markers": [
                {"region": "heart", "condition": "冠状动脉粥样硬化", "severity": "severe", "position": {"top": "32%", "left": "52%"}},
                {"region": "pancreas", "condition": "糖代谢异常", "severity": "moderate", "position": {"top": "45%", "left": "55%"}}
            ],
            "discrepancies": []
        }


# 全局 LLM 服务实例
llm_service = LLMService()
