from __future__ import annotations

"""
病案首页自动生成服务（LLM 抽取版）

功能：
- 从 visit_id 获取全病历文书（当前为 mock，后续接入真实 EMR）
- 调用 LLM 分步抽取各模块字段（患者信息、住院信息、诊断、手术等）
- 返回结构化的 FrontPageDraft
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator, Tuple, Coroutine
import json
import re
import logging
import asyncio

from pydantic import ValidationError

from ..schemas.frontpage import FrontPageDraft
from ..core.settings import get_settings
from ..core.http import safe_post_json

logger = logging.getLogger(__name__)


class FrontPageLLMClient:
    """病案首页抽取专用 LLM 客户端"""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.api_endpoint: Optional[str] = None
        self.api_key: Optional[str] = None
        self.model: str = "qwen-max"
        self.timeout_seconds: int = 60
        self.temperature: float = 0.1
        self.max_tokens: int = 4000
        self.provider_code: str = "alibaba"

        if config:
            self.apply_runtime_config(config)
        else:
            self.apply_settings_fallback()

        logger.info(f"FrontPageLLMClient 初始化: model={self.model}")

    def apply_runtime_config(self, config: Dict[str, Any]) -> None:
        custom_params = config.get("custom_parameters", {}) or {}
        self.api_endpoint = config.get("api_endpoint")
        self.api_key = config.get("api_key")
        self.model = str(config.get("model") or self.model or "qwen-max")
        self.provider_code = str(config.get("provider_code") or self.provider_code or "alibaba")
        self.timeout_seconds = int(config.get("timeout_seconds") or self.timeout_seconds or 60)
        self.temperature = float(custom_params.get("temperature", 0.1))
        self.max_tokens = int(custom_params.get("max_tokens", 4000))

    def apply_settings_fallback(self) -> None:
        s = get_settings()
        self.api_endpoint = str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None
        self.api_key = s.LLM_API_KEY
        self.model = s.LLM_MODEL
        self.provider_code = "alibaba"
        self.timeout_seconds = 60
        self.temperature = 0.1
        self.max_tokens = 4000

    async def generate(
        self, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None
    ) -> str:
        """调用 LLM 生成响应"""
        if not (self.api_endpoint and self.api_key):
            logger.warning("LLM 未配置，返回空响应")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
            "enable_thinking": False,  # 关闭 CoT 推理，加速结构化抽取
        }

        try:
            result = await safe_post_json(
                url=f"{self.api_endpoint}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise


# ============================================================================
# 码表映射（第二层：编码 ↔ 文本互转）
# ============================================================================

CODE_MAPS = {
    "sex": {"男": "1", "女": "2"},
    "marital_status": {"未婚": "1", "已婚": "2", "丧偶": "3", "离婚": "4", "其他": "9"},
    "payment_method": {
        "城镇职工基本医疗保险": "1", "城镇居民基本医疗保险": "2",
        "新型农村合作医疗": "3", "贫困救助": "4", "商业医疗保险": "5",
        "全公费": "6", "全自费": "7", "其他社会保险": "8", "其他": "9",
        # 简写也支持
        "城镇职工": "1", "城镇居民": "2", "新农合": "3",
        "商业保险": "5", "市职工": "1",
    },
    "admission_route": {"急诊": "1", "门诊": "2", "其他医疗机构转入": "3", "其他": "9", "转入": "3"},
    "blood_abo": {"A": "A", "B": "B", "O": "O", "AB": "AB", "不详": "不详", "未查": "未查",
                  "A型": "A", "B型": "B", "O型": "O", "AB型": "AB"},
    "blood_rh": {"阴": "1", "阳": "2", "阴性": "1", "阳性": "2", "不详": "3", "未查": "4"},
    "allergy": {"无": "1", "有": "2"},
}


def _code_to_text(category: str, code: str) -> str:
    """编码→文本（反向查找）"""
    mapping = CODE_MAPS.get(category, {})
    reverse = {v: k for k, v in mapping.items()}
    return reverse.get(str(code), str(code))


def _text_to_code(category: str, text: str) -> str:
    """文本→编码"""
    if not text:
        return ""
    mapping = CODE_MAPS.get(category, {})
    return mapping.get(str(text).strip(), str(text))


# ============================================================================
# Prompt 模板
# ============================================================================

SYSTEM_PROMPT = """你是一位专业的病案信息提取专家，擅长从病历文书中提取结构化信息。
请严格按照要求的 JSON 格式输出，不要添加任何额外说明。"""

BASIC_INFO_PROMPT = """从以下病历中提取患者基本信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "patient_name": "姓名",
  "gender": "1=男, 2=女",
  "gender_text": "男/女",
  "birth_date": "YYYY-MM-DD",
  "age_years": 年龄数字,
  "nationality": "国籍",
  "ethnicity": "民族",
  "marital_status": "1=未婚, 2=已婚, 3=丧偶, 4=离婚, 9=其他",
  "marital_status_text": "婚姻状况文本",
  "id_number": "身份证号",
  "occupation": "职业",
  "birthplace": "出生地（省市县）",
  "nativeplace": "籍贯",
  "current_address": "现住址（省市县街道）",
  "current_address_phone": "现住址电话",
  "current_address_zip": "现住址邮编",
  "household_address": "户口地址（省市县街道）",
  "household_address_zip": "户口地址邮编",
  "work_unit": "工作单位及地址",
  "work_unit_phone": "工作单位电话",
  "work_unit_zip": "工作单位邮编",
  "contact_name": "联系人姓名",
  "contact_relation": "联系人关系",
  "contact_phone": "联系人电话",
  "contact_address": "联系人地址"
}}
```

直接输出 JSON，不要添加说明："""

HOSPITALIZATION_PROMPT = """从以下病历中提取住院相关信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "hospital_name": "医院名称",
  "admission_times_in_hospital": 第几次住院(数字),
  "medical_record_no": "病案号",
  "payment_method_text": "医疗付费方式",
  "admission_way_text": "入院途径",
  "admission_dept": "入院科别",
  "admission_ward": "入院病房",
  "admission_datetime": "YYYY-MM-DD HH:MM:SS",
  "discharge_dept": "出院科别",
  "discharge_ward": "出院病房",
  "discharge_datetime": "YYYY-MM-DD HH:MM:SS",
  "actual_hospital_days": 住院天数(数字),
  "transfer_dept": "转科科别(无则填-)",
  "leaving_hospital_way": "离院方式(医嘱离院/自动出院等)",
  "rehospital_within_month": "31天内再住院计划(有/无)",
  "daily_ability_admission": "日常生活能力Barthel指数(入院时,数字)",
  "daily_ability_discharge": "日常生活能力Barthel指数(出院时,数字)",
  "inpat_type": "住院医疗类型(住院/日间手术)",
  "therapy_type": "治疗类别(1=西医, 2=中医, 3=中西医)",
  "receiving_institution": "拟接收机构名称(转院时填写,无则null)"
}}
```

直接输出 JSON，不要添加说明："""

DIAGNOSES_PROMPT = """从以下病历中提取诊断信息，并严格按《住院病案首页填写规范》判断主诊断与其他诊断。

【主诊断选择规范（必须执行）】
1. 主诊断应为“本次住院主要治疗的疾病”，即对本次住院医疗资源消耗最大、治疗措施最集中、对住院结局影响最大的疾病。
2. 不得机械按“出院诊断第一条”作为主诊断；若第一条与本次主要治疗目标不一致，应改选更符合规范的诊断。
3. 当存在“基础病 + 急性发作/并发症”时，优先选择导致本次住院和主要治疗行为的急性问题作为主诊断。
4. “术后状态/植入后状态/既往病史”通常不作为主诊断，除非其确为本次住院主要治疗对象。
5. 主诊断需与主要手术/关键治疗过程一致（如介入、手术、重症治疗等）。

【其他诊断填写要求（漏填补齐）】
1. 其他诊断应包含：并存疾病、合并症、并发症、术后状态、影响治疗决策或资源消耗的疾病。
2. 必须避免漏填：若病历中明确出现但出院诊断列表未列出，仍需补充到 `discharge_other_diagnoses_texts`。
3. 复合诊断必须拆分为独立条目（例如“冠心病 不稳定型心绞痛”要拆成两条）。
4. 去重：同义重复仅保留一次（如“冠脉粥样硬化性心脏病”与“冠心病”）。

【门急诊/入院诊断规则】
1. `ed_diagnosis_texts` 提取门诊、急诊、入院初步诊断。
2. 若无明确“出院诊断”，仍需提取 `ed_diagnosis_texts`，但不得直接把全部门急诊诊断原样当作出院主诊断。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "ed_diagnosis_texts": ["门/急诊诊断1", "门/急诊诊断2"],
  "discharge_main_diagnosis_text": "出院主要诊断（按规范选定，仅1条）",
  "discharge_main_diagnosis_reason": "主诊断判定依据（需体现规范口径：主要治疗目标/资源消耗/与关键治疗一致）",
  "discharge_main_outcome": "治愈/好转/未愈/死亡/其他",
  "discharge_other_diagnoses_texts": ["其他诊断1", "其他诊断2"],
  "discharge_other_outcomes": ["好转", "好转"],
  "admission_condition": "1=有, 2=临床未确定, 3=情况不明, 4=无"
}}
```

只输出 JSON，不要输出解释性正文。"""

PROCEDURES_PROMPT = """从以下病历中提取手术及操作信息，并严格按《住院病案首页填写规范》判定主要手术与其他手术。

【主要手术填写要求（必须执行）】
1. 主要手术应为本次住院中治疗作用最直接、技术难度和资源消耗最高、对预后影响最大的操作，仅能有1条。
2. 主要手术应与主诊断直接相关，优先选择“治疗性操作”，不要机械选第一条记录。
3. 同次住院存在“诊断性操作 + 治疗性操作”时，治疗性操作作为主要手术，诊断性操作归入其他手术。
4. “术前检查/单纯诊断性检查”通常不作为主要手术，除非病历明确其为本次主要干预。
5. 常见口径：`冠状动脉造影 + 支架植入`，主要手术应为`支架植入`，造影归入其他手术。

【其他手术填写要求（漏填补齐）】
1. 其他手术应完整记录同次住院发生的其他治疗性或重要诊断性操作。
2. 复合手术必须拆分为独立条目（用“+、及、并、联合”等连接的操作要拆开）。
3. 不得漏填：病程记录、手术记录、麻醉记录中明确出现的手术/操作，如未进入主手术，需补入 `other_procedures_texts`。
4. 去重：同一操作不同写法仅保留一次。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "main_procedure_text": "主要手术名称（按规范选定，仅1条）",
  "main_procedure_reason": "主要手术判定依据（需体现：治疗作用/资源消耗/与主诊断一致）",
  "main_procedure_date": "YYYY-MM-DD",
  "main_procedure_level": "手术级别",
  "main_procedure_start_time": "YYYY-MM-DD HH:MM",
  "main_procedure_end_time": "YYYY-MM-DD HH:MM",
  "incision_grade": "切口等级(0类/I类/II类/III类)",
  "anesthesia_grade": "麻醉分级",
  "is_main_surgery": "是/否",
  "unplanned_reoperation": "是/否",
  "other_procedures_texts": ["其他手术1", "其他手术2"],
  "other_procedures": [{{"text": "手术名称", "date": "YYYY-MM-DD"}}],
  "surgeon_name": "术者姓名",
  "surgeon_code": "术者医师代码（工号/编码）",
  "assistant1_name": "I助姓名",
  "assistant1_code": "I助医师代码（工号/编码）",
  "assistant2_name": "II助姓名",
  "assistant2_code": "II助医师代码（工号/编码）",
  "anesthesia_method": "麻醉方式",
  "anesthetist_name": "麻醉医师姓名",
  "anesthetist_code": "麻醉医师代码（工号/编码）",
  "incision_healing_grade": "切口愈合等级"
}}
```

如果无手术记录，相关字段返回 `null`，`other_procedures_texts` 返回 `[]`。
只输出 JSON，不要输出解释性正文。"""

DIAG_PROC_PROMPT = """从以下病历中一次性提取“诊断信息”和“手术/操作信息”，仅输出 JSON。

要求：
1. 必须返回两个对象：diagnoses、procedures。
2. diagnoses 的字段结构与诊断提取任务一致。
3. procedures 的字段结构与手术提取任务一致。
4. 若无手术，main_procedure_text/main_procedure_date/main_procedure_level 等字段返回 null，other_procedures_texts 返回 []。
5. 仅输出 JSON，不要输出解释文本。
6. 主诊断必须按《住院病案首页填写规范》判定，不得机械取第一条出院诊断。
7. 主要手术必须按《住院病案首页填写规范》判定，不得机械取第一条手术记录。
8. 其他诊断与其他手术需做“漏填补齐”，病历中明确出现但未入组的条目要补全，并去重。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "diagnoses": {{
    "ed_diagnosis_texts": ["门/急诊诊断1", "门/急诊诊断2"],
    "discharge_main_diagnosis_text": "出院主要诊断",
    "discharge_main_diagnosis_reason": "主诊断选择依据",
    "discharge_main_outcome": "治愈/好转/未愈/死亡/其他",
    "discharge_other_diagnoses_texts": ["其他诊断1", "其他诊断2"],
    "discharge_other_outcomes": ["好转", "好转"],
    "admission_condition": "1/2/3/4"
  }},
  "procedures": {{
    "main_procedure_text": "主要手术名称",
    "main_procedure_reason": "主要手术判定依据",
    "main_procedure_date": "YYYY-MM-DD",
    "main_procedure_level": "手术级别",
    "main_procedure_start_time": "YYYY-MM-DD HH:MM",
    "main_procedure_end_time": "YYYY-MM-DD HH:MM",
    "incision_grade": "切口等级",
    "anesthesia_grade": "麻醉分级",
    "is_main_surgery": "是/否",
    "unplanned_reoperation": "是/否",
    "other_procedures_texts": ["其他手术1", "其他手术2"],
    "other_procedures": [{{"text": "手术名", "date": "YYYY-MM-DD"}}],
    "surgeon_name": "术者姓名",
    "surgeon_code": "术者医师代码",
    "assistant1_name": "I助",
    "assistant1_code": "I助医师代码",
    "assistant2_name": "II助",
    "assistant2_code": "II助医师代码",
    "anesthesia_method": "麻醉方式",
    "anesthetist_name": "麻醉医师",
    "anesthetist_code": "麻醉医师代码",
    "incision_healing_grade": "切口愈合等级"
  }}
}}
```"""

OTHER_MEDICAL_INFO_PROMPT = """从以下病历中提取其他医疗信息。

【病历内容】
{medical_text}

【提取规则】
- 损伤中毒外部原因：仅当诊断包含外伤、中毒、烧伤等V/W/X/Y章编码相关诊断时填写
  常见外因：交通事故、跌落、自残、他人殴打、火灾、药物中毒等
- 昏迷时间：仅当颅脑损伤患者存在昏迷记录时填写，分入院前和入院后两组

【输出格式】
```json
{{
  "pathology_text": "病理诊断",
  "pathology_icd": "病理诊断编码（如可提取）",
  "pathology_no": "病理号",
  "drug_allergy_flag": "1=无, 2=有",
  "drug_allergy_drugs": ["过敏药物1", "过敏药物2"],
  "abo_blood_type": "A/B/O/AB/不详/未查",
  "rh_blood_type": "1=阴, 2=阳, 3=不详, 4=未查",
  "rh_blood_type_text": "Rh血型文本",
  "ventilation_hours": 机械通气小时数,
  "icu_type": "ICU类型",
  "icu_enter_time": "进入ICU时间",
  "icu_leave_time": "退出ICU时间",
  "icu_transfer_status": "ICU转移情况（如：普通病房/他院/死亡等）",
  "injury_poison_flag": "1=无, 2=有（仅外伤/中毒等诊断时填2）",
  "injury_poison_cause_text": "损伤中毒外部原因名称（如：机动车交通事故、意外跌落）",
  "injury_poison_cause_icd": "损伤中毒外部原因ICD编码（V/W/X/Y章节，如V01-V99）",
  "coma_before_admission": {{"days": 天数, "hours": 小时, "minutes": 分钟}},
  "coma_after_admission": {{"days": 天数, "hours": 小时, "minutes": 分钟}}
}}
```

注意：coma_before_admission 和 coma_after_admission 仅在颅脑损伤昏迷患者中填写，非昏迷患者填 null。
直接输出 JSON，不要添加说明："""


STAFF_PROMPT = """从以下病历中提取医护人员信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "dept_director": "科主任",
  "chief_physician": "主任(副主任)医师",
  "attending_physician": "主治医师",
  "resident_physician": "住院医师",
  "responsible_nurse": "责任护士",
  "coder": "编码员",
  "qc_physician": "质控医师",
  "qc_nurse": "质控护士",
  "qc_date": "YYYY-MM-DD",
  "medical_record_quality": "病案质量(例如：甲)"
}}
```

直接输出 JSON，不要添加说明："""

COSTS_PROMPT = """从以下病历中提取费用信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "total_cost": 住院总费用(数字),
  "self_paid": 自付金额(数字),
  "categories": {{
    "general_medical_service": 一般医疗服务费,
    "general_treatment": 一般治疗操作费,
    "nursing_care": 护理费,
    "other_service": 其他服务费用,
    "pathological_diagnostic": 病理诊断费,
    "laboratory_diagnostic": 实验室诊断费,
    "imaging_diagnostic": 影像学诊断费,
    "clinical_diagnostic": 临床诊断项目费,
    "nonsurgical_treatment": 非手术治疗项目费,
    "clinical_physical_therapy": 临床物理治疗费,
    "surgery_treatment": 手术治疗费,
    "anesthesia": 麻醉费,
    "surgery": 手术费,
    "rehabilitation": 康复费,
    "chinese_medicine_treatment": 中医治疗费,
    "western_medicine": 西药费,
    "antibacterial_drug": 抗菌药物费用,
    "chinese_patent_medicine": 中成药费,
    "chinese_herbal_medicine": 中草药费,
    "blood": 血费,
    "albumin": 白蛋白类制品费,
    "globulin": 球蛋白类制品费,
    "coagulation_factor": 凝血因子类制品费,
    "cytokine": 细胞因子类制品费,
    "exam_disposable_material": 检查用一次性医用材料费,
    "treat_disposable_material": 治疗用一次性医用材料费,
    "surgery_disposable_material": 手术用一次性医用材料费,
    "other": 其他费用
  }}
}}
```

如果某项费用信息不存在，返回 null。只提取明确标注的费用数字。
直接输出 JSON，不要添加说明："""


# ============================================================================
# F4: 入院病情推理 Prompt
# ============================================================================

ADMISSION_CONDITION_PROMPT = """你是一位资深病案编码专家，请根据《住院病案首页填写说明》附件2的标准，推理每个出院诊断的入院病情。

【入院病情分类标准】
| 代码 | 名称 | 判定依据 |
|-----|------|---------|
| 1 | 有 | 入院时已明确诊断（入院记录或初步诊断中有此诊断，且无"？"、"疑"等不确定标记） |
| 2 | 临床未确定 | 入院时为疑诊（诊断带"？"、"待排"、"可疑"、"待查"等标记） |
| 3 | 情况不明 | 窗口期或潜伏期疾病（如乙肝窗口期、肺炎潜伏期等，入院时无法判断） |
| 4 | 无 | 住院期间新发生（入院记录完全无此诊断，在病程记录中首次出现的新发疾病） |

【病历内容】
{medical_text}

【出院诊断列表】
{diagnoses_text}

【任务】
对每个出院诊断，判断其入院病情代码（1-4），并给出推理依据。

【输出格式】
```json
{{
  "results": [
    {{
      "diagnosis": "出院诊断名称",
      "admission_condition": 1,
      "reasoning": "在入院记录初步诊断中明确记录为'急性心肌梗死'，无疑诊标记"
    }},
    {{
      "diagnosis": "术后心力衰竭",
      "admission_condition": 4,
      "reasoning": "入院记录无此诊断，在第5天病程记录中首次出现术后心衰表现"
    }}
  ]
}}
```

直接输出 JSON："""


MAIN_DIAGNOSIS_LLM_EVIDENCE_PROMPT = """你是一位资深病案编码与临床语义分析专家。请基于病历内容与候选诊断，给出“主诊断推荐解释”。

【任务目标】
1. 从医学语义角度判断最适合作为主诊断的疾病（llm_recommended_main_diagnosis）。
2. 给出简洁结论（conclusion）和一段推理摘要（reasoning_summary）。
3. 仅输出最多3条关键证据（key_evidence），每条必须包含：
   - quote: 原文片段
   - source: 来源定位（如“出院诊断第2条”“病程记录第5天”等）
   - why_it_supports: 该证据如何支持推荐

【输入信息】
- 医生填写主诊断：{clinician_main_diagnosis}
- 候选诊断列表：{candidate_diagnoses}
- 主要手术/关键治疗：{main_procedure_text}

【病历精选片段】
{medical_excerpt}

【输出要求】
- 只输出 JSON，不要输出任何解释性正文
- confidence 取值 0~1
- key_evidence 最多 3 条，优先高信息密度句子
- conclusion 使用一句话，面向编码员

【输出格式】
```json
{{
  "clinician_main_diagnosis": "医生填写主诊断",
  "llm_recommended_main_diagnosis": "LLM推荐主诊断",
  "is_consistent_with_clinician": true,
  "confidence": 0.86,
  "conclusion": "一句话结论",
  "key_evidence": [
    {{
      "quote": "原文片段1",
      "source": "来源1",
      "why_it_supports": "支持理由1"
    }}
  ],
  "reasoning_summary": "一段推理摘要"
}}
```"""


CODING_AUDIT_LLM_PROMPT = """你是一位资深病案编码审核专家。请根据病历上下文，完成“医生书写质量审核”。

【任务目标】
1. 识别并输出以下4类问题：
   - diagnosis_missing（医生可能漏写诊断）
   - procedure_missing（医生可能漏写手术/操作）
   - diagnosis_inappropriate（主诊断可能不当）
   - diagnosis_insufficient_evidence（主诊断证据不足）
2. 输出面向编码员的一句话总结（summary）与结构化 findings。
3. 所有结论必须有病历证据支持，避免泛泛描述。

【输入信息】
- 医生填写主诊断：{clinician_main_diagnosis}
- 医生诊断列表：{clinician_diagnoses}
- 医生手术列表：{clinician_procedures}
- 系统诊断列表：{system_diagnoses}
- 系统手术列表：{system_procedures}
- 既有LLM主诊断推荐（如有）：{llm_recommended_main}
- LLM主诊断推荐：{llm_recommended_main}

【病历精选片段】
{medical_excerpt}

【输出要求】
- 只输出 JSON，不要输出解释性正文
- confidence 取值 0~1
- findings 最多 6 条，每条 evidence 最多 2 条
- type 仅允许：diagnosis_missing/procedure_missing/diagnosis_inappropriate/diagnosis_insufficient_evidence
- severity 仅允许：high/medium/low

【输出格式】
```json
{{
  "version": "v1",
  "summary": "一句话总结",
  "confidence": 0.82,
  "counts": {{
    "diagnosis_missing": 1,
    "procedure_missing": 0,
    "diagnosis_inappropriate": 1,
    "diagnosis_insufficient_evidence": 0
  }},
  "findings": [
    {{
      "type": "diagnosis_missing",
      "severity": "high",
      "clinician_text": "医生当前书写",
      "llm_recommendation": "建议补充诊断名称",
      "reason": "判定理由",
      "evidence": [
        {{
          "quote": "病历原文片段",
          "source": "来源定位",
          "why_it_supports": "支持理由"
        }}
      ]
    }}
  ]
}}
```"""


MAIN_AND_AUDIT_LLM_EVIDENCE_PROMPT = """你是一位资深病案编码审核专家。请一次完成“主诊断推荐解释 + 编码审核风险识别”。

【任务目标】
1. 输出主诊断解释（main_diagnosis_llm）：
   - 医生填写主诊断 vs LLM推荐主诊断
   - 推荐策略：优先从“系统诊断列表中的其他诊断”中选择更适合作为主诊断的候选；
     仅在无合适候选时，才建议“细化当前主诊断”
   - 一句话结论 + 置信度 + 最多3条关键证据
2. 输出编码审核风险（coding_audit_llm）：
   - 识别4类风险：diagnosis_missing / procedure_missing / diagnosis_inappropriate / diagnosis_insufficient_evidence
   - 给出 summary、counts、findings（最多6条）

【输入信息】
- 医生填写主诊断：{clinician_main_diagnosis}
- 候选诊断列表：{candidate_diagnoses}
- 主要手术/关键治疗：{main_procedure_text}
- 医生诊断列表：{clinician_diagnoses}
- 医生手术列表：{clinician_procedures}
- 系统诊断列表：{system_diagnoses}
- 系统手术列表：{system_procedures}

【病历精选片段】
{medical_excerpt}

【输出要求】
- 只输出 JSON，不要输出解释性正文
- confidence 取值 0~1
- main_diagnosis_llm.key_evidence 最多 3 条
- coding_audit_llm.findings 最多 6 条，每条 evidence 最多 2 条
- finding.type 仅允许：diagnosis_missing/procedure_missing/diagnosis_inappropriate/diagnosis_insufficient_evidence
- finding.severity 仅允许：high/medium/low

【输出格式】
```json
{{
  "main_diagnosis_llm": {{
    "clinician_main_diagnosis": "医生填写主诊断",
    "llm_recommended_main_diagnosis": "LLM推荐主诊断",
    "is_consistent_with_clinician": true,
    "recommended_main_diagnosis_action": "promote_existing/refine_current/keep",
    "recommended_main_diagnosis_source": "other_diagnosis/llm_refinement/none",
    "recommended_main_diagnosis_source_other_index": 2,
    "recommendation_summary": "建议改为现有诊断：XXX（来自其他诊断第N条）",
    "confidence": 0.86,
    "conclusion": "一句话结论",
    "key_evidence": [
      {{
        "quote": "原文片段1",
        "source": "来源1",
        "why_it_supports": "支持理由1"
      }}
    ],
    "reasoning_summary": "一段推理摘要"
  }},
  "coding_audit_llm": {{
    "version": "v1",
    "summary": "一句话总结",
    "confidence": 0.82,
    "counts": {{
      "diagnosis_missing": 1,
      "procedure_missing": 0,
      "diagnosis_inappropriate": 1,
      "diagnosis_insufficient_evidence": 0
    }},
    "findings": [
      {{
        "type": "diagnosis_missing",
        "severity": "high",
        "clinician_text": "医生当前书写",
        "llm_recommendation": "建议补充诊断名称",
        "reason": "判定理由",
        "evidence": [
          {{
            "quote": "病历原文片段",
            "source": "来源定位",
            "why_it_supports": "支持理由"
          }}
        ]
      }}
    ]
  }}
}}
```"""


class FrontPageExtractionService:
    """病案首页抽取服务（LLM 版）"""

    def __init__(self, base_dir: Optional[Path] = None, llm_config: Optional[Dict[str, Any]] = None) -> None:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = base_dir
        self.demo_data_path = self.base_dir / "data" / "frontpage_demo_case.json"
        self.llm_client = FrontPageLLMClient(llm_config)
        self._sync_with_default_llm_config = llm_config is None
        self._use_llm = bool(self.llm_client.api_endpoint and self.llm_client.api_key)
        logger.info(f"FrontPageExtractionService 初始化: use_llm={self._use_llm}")

    async def _refresh_llm_runtime_from_default(self) -> None:
        """与质控统一：首页抽取每次执行前从 default 配置源刷新模型参数。"""
        if not self._sync_with_default_llm_config:
            self._use_llm = bool(self.llm_client.api_endpoint and self.llm_client.api_key)
            return

        try:
            from .llm_config_loader import LLMConfigLoader

            config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
            if config:
                self.llm_client.apply_runtime_config(config)
            else:
                self.llm_client.apply_settings_fallback()
        except Exception as exc:
            logger.warning("首页抽取刷新默认 LLM 配置失败，回退 env: %s", exc)
            self.llm_client.apply_settings_fallback()

        self._use_llm = bool(self.llm_client.api_endpoint and self.llm_client.api_key)

    async def generate_draft_from_visit(self, visit_id: str) -> FrontPageDraft:
        """
        根据住院 ID 生成首页草稿
        
        - 如果 LLM 已配置，调用 LLM 抽取
        - 否则回退到 demo 数据
        """
        await self._refresh_llm_runtime_from_default()
        # 获取病历文本（当前为 demo，后续接入真实 EMR）
        medical_text = await self._get_medical_text(visit_id)
        
        if self._use_llm and medical_text:
            try:
                return await self._extract_with_llm(medical_text)
            except Exception as e:
                logger.error(f"LLM 抽取失败，回退到 demo 数据: {e}")
                return await self._load_demo_frontpage()
        else:
            return await self._load_demo_frontpage()

    async def generate_draft_from_documents(
        self, documents: List[Dict[str, Any]]
    ) -> FrontPageDraft:
        """根据传入的文书列表生成首页草稿"""
        await self._refresh_llm_runtime_from_default()
        # 合并文书内容
        medical_text = "\n\n".join(
            f"【{doc.get('type', '未知文书')}】\n{doc.get('content', '')}"
            for doc in documents
        )
        
        if self._use_llm and medical_text:
            try:
                return await self._extract_with_llm(medical_text)
            except Exception as e:
                logger.error(f"LLM 抽取失败，回退到 demo 数据: {e}")
                return await self._load_demo_frontpage()
        else:
            return await self._load_demo_frontpage()

    async def extract_from_text(
        self, medical_text: str, context_strategy: Optional[str] = None
    ) -> FrontPageDraft:
        """
        直接从病历文本提取病案首页信息
        
        Args:
            medical_text: 病历全文
            
        Returns:
            FrontPageDraft: 提取的首页草稿
        """
        await self._refresh_llm_runtime_from_default()
        if not medical_text or not medical_text.strip():
            logger.warning("传入的病历文本为空，回退到 demo 数据")
            return await self._load_demo_frontpage()
        
        if self._use_llm:
            try:
                logger.info(f"开始从文本提取首页信息，文本长度: {len(medical_text)}")
                return await self._extract_with_llm(
                    medical_text, context_strategy=context_strategy
                )
            except Exception as e:
                logger.error(f"LLM 抽取失败: {e}")
                raise
        else:
            logger.warning("LLM 未配置，回退到 demo 数据")
            return await self._load_demo_frontpage()

    async def extract_from_text_stream(
        self,
        medical_text: str,
        visit_id: str = None,
        force_llm: bool = False,
        context_strategy: Optional[str] = None,
    ) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
        """
        逐步抽取首页信息，按模块产出结果（用于前端分批展示）。

        三层架构：
        1. 如果有 visit_id → 先从 CDM 源头表 SQL 直读，立即推送（毫秒级）
        2. 码表映射自动完成
        3. 判断缺失字段，仅对缺失模块调用 LLM 补缺

        Yields:
            (event_name, payload) where payload contains partial `frontpage`.
        """
        await self._refresh_llm_runtime_from_default()

        def default_frontpage() -> Dict[str, Any]:
            return {
                "basic_info": {
                    "patient_name": "",
                    "gender": "0",
                    "gender_text": "",
                    "birth_date": "",
                    "age_years": 0,
                    "nationality": "",
                    "ethnicity": "",
                    "marital_status": "9",
                    "marital_status_text": "",
                    "id_number": "",
                    "occupation": "",
                    "birthplace": "",
                    "nativeplace": "",
                    "current_address": "",
                    "current_address_phone": "",
                    "current_address_zip": "",
                    "household_address": "",
                    "household_address_zip": "",
                    "work_unit": "",
                    "work_unit_phone": "",
                    "work_unit_zip": "",
                    "contact_name": "",
                    "contact_relation": "",
                    "contact_phone": "",
                    "contact_address": "",
                },
                "hospitalization": {},
                "diagnoses": {
                    "ed_diagnosis_texts": [],
                    "discharge_main_diagnosis_text": None,
                    "discharge_other_diagnoses_texts": [],
                    "ed_diagnosis_codes": None,
                    "discharge_main_icd": None,
                    "discharge_other_icds": None,
                    "admission_condition": None,
                },
                "procedures": {},
                "other_medical_info": {},
                "staff": {},
                "costs": {"total_cost": None, "self_paid": None, "categories": {}},
                "evidence": {},
                "confidence": {},
            }

        # =================== 第一层 + 第二层：SQL + 码表 ===================
        cdm_prefilled = False
        if visit_id:
            try:
                fp_data = await self._prefill_from_cdm(visit_id)
                cdm_prefilled = True
                logger.info("stream: 三层架构 - SQL 层完成，立即推送已有数据")

                # 立即推送 SQL 已有的数据给前端（毫秒级！）
                if fp_data.get("basic_info", {}).get("patient_name"):
                    yield ("update", {"module": "basic_info", "frontpage": fp_data})

                if fp_data.get("hospitalization", {}).get("admission_datetime"):
                    yield ("update", {"module": "hospitalization", "frontpage": fp_data})

                if fp_data.get("staff", {}).get("attending_physician"):
                    yield ("update", {"module": "staff", "frontpage": fp_data})

                if fp_data.get("costs", {}).get("total_cost"):
                    yield ("update", {"module": "costs", "frontpage": fp_data})

                if fp_data.get("other_medical_info", {}).get("drug_allergy_flag"):
                    yield ("update", {"module": "other_medical_info", "frontpage": fp_data})

            except Exception as exc:
                logger.warning(f"stream: SQL 层异常，回退到纯 LLM 模式: {exc}")
                fp_data = default_frontpage()
                cdm_prefilled = False

        if not cdm_prefilled:
            fp_data = default_frontpage()

        # =================== 第三层：LLM 精准补缺 ===================
        # 获取 LLM 需要看的文本
        if visit_id and cdm_prefilled:
            # 使用新的精简版上下文（不含 mr 表）
            llm_text = await self._get_llm_context_text(visit_id)
            if not llm_text.strip():
                llm_text = medical_text or ""
        else:
            llm_text = medical_text or ""

        if not llm_text or not llm_text.strip():
            if cdm_prefilled and not force_llm:
                # SQL 已有足够数据且未强制 LLM，直接返回
                logger.info("stream: SQL 数据充足且未强制 LLM，跳过 LLM 提取")
                yield ("done", {"frontpage": fp_data})
                return
            if not cdm_prefilled:
                demo = await self._load_demo_frontpage()
                yield ("done", {"frontpage": demo.model_dump(), "fallback": "empty_text"})
                return
            # force_llm=True 但无文本 → 记录日志，继续尝试
            logger.warning("stream: force_llm=True 但 LLM 文本为空，无法调用 LLM")

        if not self._use_llm:
            if cdm_prefilled:
                if force_llm:
                    logger.warning("stream: force_llm=True 但 LLM 未配置，仅返回 SQL 数据")
                yield ("done", {"frontpage": fp_data})
                return
            demo = await self._load_demo_frontpage()
            yield ("update", {"frontpage": demo.model_dump(), "fallback": "llm_not_configured"})
            yield ("done", {"frontpage": demo.model_dump(), "fallback": "llm_not_configured"})
            return

        validation_info: Dict[str, Any] = {}

        # 判断哪些模块需要 LLM 补缺
        # force_llm=True 时，所有模块都强制走 LLM
        need_basic_llm = force_llm or not cdm_prefilled or not fp_data.get("basic_info", {}).get("patient_name")
        need_hosp_llm = force_llm or not cdm_prefilled or not fp_data.get("hospitalization", {}).get("admission_datetime")
        need_staff_llm = force_llm or not fp_data.get("staff", {}).get("attending_physician")
        need_costs_llm = force_llm or not fp_data.get("costs", {}).get("total_cost")
        # 诊断/手术/其他医疗：始终从病历文书 LLM 提取（不从首页目标表读取）
        need_diag_llm = True
        need_proc_llm = True
        need_other_llm = True

        logger.info(
            "stream: LLM 补缺判断: basic=%s hosp=%s diag=%s proc=%s other=%s staff=%s costs=%s",
            need_basic_llm, need_hosp_llm, need_diag_llm,
            need_proc_llm, need_other_llm, need_staff_llm, need_costs_llm
        )

        # 如果需要 LLM 提取 basic_info（纯文本模式 / SQL 层无数据）
        if need_basic_llm:
            logger.info("stream: Step LLM-basic: 提取基本信息...")
            basic_info = await self._extract_json(BASIC_INFO_PROMPT.format(medical_text=llm_text)) or {}
            fp_data["basic_info"] = {**fp_data["basic_info"], **basic_info}
            yield ("update", {"module": "basic_info", "frontpage": fp_data})

        patient_context = {
            "gender": fp_data.get("basic_info", {}).get("gender_text", "未说明"),
            "age": fp_data.get("basic_info", {}).get("age_years", 0),
        }

        logger.info("stream: Step 2: 并行提取其他模块及外部编码...")
        from .external_coding_service import get_external_coding_service

        ext_coding_service = get_external_coding_service()

        import time
        task_start_times: Dict[str, float] = {}
        named_tasks: List[asyncio.Task] = []
        prepared_failures: List[Tuple[str, Exception]] = []
        latest_coding_result: Optional[Dict[str, Any]] = None

        async def run_named_timed(name: str, coro: Coroutine[Any, Any, Any]) -> Tuple[str, Any]:
            """Wrapper that tracks timing for each task."""
            task_start_times[name] = time.time()
            try:
                result = await coro
                return name, result
            except Exception as e:
                return name, e

        def format_prompt_or_none(
            name: str,
            template: str,
            medical_text_override: Optional[str] = None,
        ) -> Optional[str]:
            try:
                source_text = llm_text if medical_text_override is None else medical_text_override
                return template.format(medical_text=source_text)
            except Exception as exc:
                logger.exception("stream: prompt format failed for module '%s'", name)
                prepared_failures.append((name, exc))
                return None

        def add_task(name: str, coro: Optional[Coroutine[Any, Any, Any]]) -> None:
            if coro is None:
                return
            try:
                named_tasks.append(asyncio.create_task(run_named_timed(name, coro)))
            except Exception as exc:
                logger.exception("stream: create task failed for module '%s'", name)
                prepared_failures.append((name, exc))

        def safe_dict_list(value: Any, field_name: str) -> List[Dict[str, Any]]:
            if not isinstance(value, list):
                return []
            valid_items: List[Dict[str, Any]] = []
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    valid_items.append(item)
                else:
                    logger.warning(
                        "stream: ignore non-dict item in %s[%d], type=%s",
                        field_name,
                        idx,
                        type(item).__name__,
                    )
            return valid_items

        def merge_coding_result(coding_result: Any) -> None:
            if not isinstance(coding_result, dict):
                logger.warning(
                    "stream: coding_result is not dict, type=%s",
                    type(coding_result).__name__,
                )
                return

            raw_coding_data = coding_result.get("coding_data", coding_result)
            coding_data = raw_coding_data if isinstance(raw_coding_data, dict) else {}
            if raw_coding_data is not None and not isinstance(raw_coding_data, dict):
                logger.warning(
                    "stream: coding_data is not dict, type=%s",
                    type(raw_coding_data).__name__,
                )

            diagnoses = fp_data.get("diagnoses")
            if not isinstance(diagnoses, dict):
                diagnoses = {}
            procedures = fp_data.get("procedures")
            if not isinstance(procedures, dict):
                procedures = {}

            diagnoses = self._apply_external_diagnosis_codes(
                diagnoses=diagnoses,
                coding_data=coding_data,
                validation_info=validation_info,
            )
            logger.info("stream: merged external diagnosis codes only")

            pp_list = safe_dict_list(coding_data.get("principal_procedures"), "principal_procedures")
            if pp_list:
                main_proc = pp_list[0]
                if not procedures.get("main_procedure_text"):
                    procedures["main_procedure_text"] = main_proc.get("name")
                if not procedures.get("main_procedure_code"):
                    procedures["main_procedure_code"] = main_proc.get("code")
                logger.info(
                    "stream: merged principal procedure: %s -> %s",
                    main_proc.get("name"),
                    main_proc.get("code"),
                )
                if len(pp_list) > 1:
                    existing_others = procedures.get("other_procedures_texts") or []
                    procedures["other_procedures_texts"] = [
                        *existing_others,
                        *[p.get("name") for p in pp_list[1:] if p.get("name")],
                    ]
                    procedures["other_procedures_codes"] = [p.get("code") for p in pp_list[1:]]

            warnings = coding_result.get("warnings") or coding_data.get("warnings") or []
            if isinstance(warnings, list) and warnings:
                validation_info["warnings"] = warnings
                logger.info("stream: 捕获到 %d 条编码警告", len(warnings))
            elif warnings:
                logger.warning("stream: warnings is not list, type=%s", type(warnings).__name__)

            diagnoses = self._normalize_diagnoses_structure(llm_text, diagnoses)
            procedures = self._normalize_procedures_structure(procedures)
            fp_data["diagnoses"] = diagnoses
            fp_data["procedures"] = procedures

        # 条件化创建 LLM 任务：仅对 SQL 层缺失的模块调用 LLM
        if need_hosp_llm:
            prompt = format_prompt_or_none("hospitalization", HOSPITALIZATION_PROMPT)
            add_task("hospitalization", self._extract_json(prompt) if prompt else None)
        diag_proc_text = self._select_context_text(
            llm_text,
            context_strategy,
            max_chars=4200,
            default_mode="retrieval",
        )
        if need_diag_llm:
            prompt = format_prompt_or_none("diagnoses", DIAGNOSES_PROMPT, diag_proc_text)
            add_task("diagnoses", self._extract_json(prompt, max_tokens=1200) if prompt else None)
        if need_proc_llm:
            prompt = format_prompt_or_none("procedures", PROCEDURES_PROMPT, diag_proc_text)
            add_task("procedures", self._extract_json(prompt, max_tokens=1200) if prompt else None)
        if need_other_llm:
            prompt = format_prompt_or_none("other_medical_info", OTHER_MEDICAL_INFO_PROMPT)
            add_task("other_medical_info", self._extract_json(prompt) if prompt else None)
        if need_staff_llm:
            prompt = format_prompt_or_none("staff", STAFF_PROMPT)
            add_task("staff", self._extract_json(prompt) if prompt else None)
        if need_costs_llm:
            prompt = format_prompt_or_none("costs", COSTS_PROMPT)
            add_task("costs", self._extract_json(prompt) if prompt else None)
        add_task("coding_result", ext_coding_service.extract_coding(llm_text, patient_context))

        for name, exc in prepared_failures:
            logger.warning("stream: module %s failed before execution: %s", name, exc)
            if name == "coding_result":
                fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}
                yield ("update", {"module": "confidence", "frontpage": fp_data})
            elif name in ("diagnoses", "procedures"):
                fp_data["diagnoses"] = fp_data.get("diagnoses") or {}
                fp_data["procedures"] = fp_data.get("procedures") or {}
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
                yield ("update", {"module": "procedures", "frontpage": fp_data})
            else:
                fp_data[name] = fp_data.get(name) or {}
                yield ("update", {"module": name, "frontpage": fp_data})

        for finished in asyncio.as_completed(named_tasks):
            try:
                name, result = await finished
            except Exception as exc:
                logger.exception("stream: await task result failed")
                continue

            elapsed = time.time() - task_start_times.get(name, time.time())
            logger.info("Task '%s' completed in %.2fs", name, elapsed)

            if isinstance(result, Exception):
                logger.warning("stream: task %s failed: %s", name, result)
                result = None

            if name == "coding_result":
                if result:
                    try:
                        if isinstance(result, dict):
                            latest_coding_result = result
                        merge_coding_result(result)
                    except Exception:
                        logger.exception("stream: merge coding result failed")

                fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}
                yield ("update", {"module": "confidence", "frontpage": fp_data})
                continue

            if name == "diagnoses":
                try:
                    diag_payload: Dict[str, Any] = {}
                    if isinstance(result, dict):
                        raw_diag = result.get("diagnoses")
                        if not isinstance(raw_diag, dict) and any(
                            k in result for k in ("discharge_main_diagnosis_text", "ed_diagnosis_texts")
                        ):
                            raw_diag = result
                        diag_payload = raw_diag if isinstance(raw_diag, dict) else {}

                    if not diag_payload:
                        logger.warning("stream: diagnoses returned empty payload, retry once")
                        diag_fallback = await self._extract_json(
                            DIAGNOSES_PROMPT.format(medical_text=diag_proc_text), max_tokens=1200
                        )
                        diag_payload = diag_fallback if isinstance(diag_fallback, dict) else {}

                    fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, diag_payload)
                except Exception:
                    logger.exception("stream: failed to process module 'diagnoses' result")
                    fp_data["diagnoses"] = fp_data.get("diagnoses") or {}

                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
                continue

            if name == "procedures":
                try:
                    proc_payload: Dict[str, Any] = {}
                    if isinstance(result, dict):
                        raw_proc = result.get("procedures")
                        if not isinstance(raw_proc, dict) and any(
                            k in result for k in ("main_procedure_text", "other_procedures_texts")
                        ):
                            raw_proc = result
                        proc_payload = raw_proc if isinstance(raw_proc, dict) else {}

                    if not proc_payload:
                        logger.warning("stream: procedures returned empty payload, retry once")
                        proc_fallback = await self._extract_json(
                            PROCEDURES_PROMPT.format(medical_text=diag_proc_text), max_tokens=1200
                        )
                        proc_payload = proc_fallback if isinstance(proc_fallback, dict) else {}

                    fp_data["procedures"] = self._normalize_procedures_structure(proc_payload)
                except Exception:
                    logger.exception("stream: failed to process module 'procedures' result")
                    fp_data["procedures"] = fp_data.get("procedures") or {}

                yield ("update", {"module": "procedures", "frontpage": fp_data})
                continue

            try:
                if isinstance(result, dict):
                    if name == "diagnoses":
                        result = self._normalize_diagnoses_structure(llm_text, result)
                    elif name == "procedures":
                        result = self._normalize_procedures_structure(result)
                    elif name == "other_medical_info":
                        result = self._normalize_other_medical_info_structure(result)
                    fp_data[name] = result
                elif result is None:
                    fp_data[name] = fp_data.get(name) or {}
                else:
                    logger.warning(
                        "stream: task %s returned non-dict result type=%s",
                        name,
                        type(result).__name__,
                    )
                    fp_data[name] = fp_data.get(name) or {}
            except Exception:
                logger.exception("stream: failed to process module '%s' result", name)
                fp_data[name] = fp_data.get(name) or {}

            yield ("update", {"module": name, "frontpage": fp_data})

        # Re-apply external coding to the latest normalized diagnoses to avoid order-sensitive misses.
        try:
            if latest_coding_result and isinstance(fp_data.get("diagnoses"), dict):
                coding_data_raw = latest_coding_result.get("coding_data", latest_coding_result)
                coding_data = coding_data_raw if isinstance(coding_data_raw, dict) else {}
                fp_data["diagnoses"] = self._apply_external_diagnosis_codes(
                    diagnoses=fp_data["diagnoses"],
                    coding_data=coding_data,
                    validation_info=validation_info,
                )
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: re-apply external diagnosis codes failed")

        # Post-processing (may trigger extra LLM calls; still stream when finished)
        try:
            if isinstance(fp_data.get("diagnoses"), dict) and fp_data.get("diagnoses"):
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, fp_data["diagnoses"])
                fp_data["diagnoses"] = await self._infer_admission_conditions(llm_text, fp_data["diagnoses"])
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: infer admission conditions failed")

        # ===== 主诊断规则裁决（在 ICD 编码前） =====
        try:
            if isinstance(fp_data.get("diagnoses"), dict) and fp_data.get("diagnoses"):
                clinician_main_before_rules = str(
                    fp_data["diagnoses"].get("discharge_main_diagnosis_text") or ""
                ).strip()
                from .main_diagnosis_rules import apply_main_diagnosis_guideline_rules
                fp_data["diagnoses"], _rule_trace = apply_main_diagnosis_guideline_rules(
                    medical_text=llm_text,
                    diagnoses=fp_data["diagnoses"],
                    procedures=fp_data.get("procedures") or {},
                )
                fp_data.setdefault("evidence", {})["guideline_rule_trace"] = _rule_trace or []
                if clinician_main_before_rules:
                    fp_data["evidence"]["clinician_main_diagnosis"] = clinician_main_before_rules
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: main diagnosis guideline rules failed")

        try:
            if (
                isinstance(fp_data.get("diagnoses"), dict)
                and fp_data["diagnoses"]
                and not fp_data["diagnoses"].get("discharge_main_icd")
            ):
                fp_data["diagnoses"] = await self._suggest_diagnosis_codes(fp_data["diagnoses"])
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: suggest diagnosis codes failed")

        try:
            if (
                isinstance(fp_data.get("procedures"), dict)
                and fp_data["procedures"]
                and not fp_data["procedures"].get("main_procedure_code")
            ):
                fp_data["procedures"] = await self._suggest_procedure_codes(fp_data["procedures"])
                yield ("update", {"module": "procedures", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: suggest procedure codes failed")

        # 使用本地 ICD 编码库查询国临版编码（替换 LLM 输出的编码）
        try:
            from .local_icd_service import resolve_diagnosis_codes, resolve_procedure_codes
            if isinstance(fp_data.get("diagnoses"), dict) and fp_data["diagnoses"]:
                fp_data["diagnoses"] = resolve_diagnosis_codes(fp_data["diagnoses"])
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(llm_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
            if isinstance(fp_data.get("procedures"), dict) and fp_data["procedures"]:
                fp_data["procedures"] = self._normalize_procedures_structure(fp_data["procedures"])
                fp_data["procedures"] = resolve_procedure_codes(fp_data["procedures"])
                yield ("update", {"module": "procedures", "frontpage": fp_data})
            logger.info("stream: 本地 ICD 编码查询校正完成")
        except Exception:
            logger.exception("stream: local ICD code resolution failed")

        fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}
        fp_data["evidence"] = fp_data.get("evidence") or {}
        try:
            merged_evidence = await self._build_main_and_audit_llm_evidence(
                medical_text=llm_text,
                diagnoses=fp_data.get("diagnoses"),
                procedures=fp_data.get("procedures"),
                clinician_main_diagnosis=fp_data["evidence"].get("clinician_main_diagnosis"),
                context_strategy=context_strategy,
            )
            fp_data["evidence"]["main_diagnosis_llm"] = merged_evidence.get("main_diagnosis_llm")
            fp_data["evidence"]["coding_audit_llm"] = merged_evidence.get("coding_audit_llm")
            yield ("update", {"module": "evidence", "frontpage": fp_data})
        except Exception:
            logger.exception("stream: build llm evidence failed")

        if isinstance(fp_data.get("diagnoses"), dict):
            fp_data["evidence"]["diagnoses"] = self._build_diagnosis_evidence(
                llm_text,
                fp_data.get("diagnoses"),
                fp_data.get("procedures"),
                guideline_rule_trace=fp_data["evidence"].get("guideline_rule_trace"),
                clinician_main_diagnosis=fp_data["evidence"].get("clinician_main_diagnosis"),
            )

        # Final: 直接输出已构建的 fp_data
        yield ("done", {"frontpage": fp_data})

    # ========================================================================
    # 第一层 + 第二层：SQL 直读 + 码表映射
    # ========================================================================

    async def _prefill_from_cdm(self, visit_id: str) -> Dict[str, Any]:
        """
        三层架构 - 第一层 + 第二层：
        从 CDM 源头表直接读取结构化数据，并通过码表映射补充文本。

        数据源（仅上游源头表，不读首页目标表）：
        - inpat_registration → 住院登记（patient_id、入出院时间等）
        - patient_information → 人口学信息（姓名、性别、民族等）
        - admission_record → 入院记录（科别、过敏史、签名等）
        - discharge_record → 出院记录（出院科别、转归等）
        - inpat_bill_item → 住院费用明细（按 item_type 汇总为首页 24 项费用）

        不读取的表（首页目标表 = 我们要填写的表）：
        - mr（病案首页主表）
        - mr_cost（病案首页费用明细）
        - mr_surgery（病案首页手术明细）
        - diagnosis（诊断表，可能属于首页填写流程）

        诊断/手术/其他医疗信息 → 由第三层 LLM 从病历文书中提取。
        """
        logger.info(f"_prefill_from_cdm: visit_id={visit_id}")

        fp_data: Dict[str, Any] = {
            "basic_info": {
                "patient_name": "", "gender": "0", "gender_text": "",
                "birth_date": "", "age_years": 0, "nationality": "",
                "ethnicity": "", "marital_status": "9", "marital_status_text": "",
                "id_number": "", "occupation": "",
                "birthplace": "", "nativeplace": "",
                "current_address": "", "current_address_phone": "", "current_address_zip": "",
                "household_address": "", "household_address_zip": "",
                "work_unit": "", "work_unit_phone": "", "work_unit_zip": "",
                "contact_name": "", "contact_relation": "", "contact_phone": "", "contact_address": "",
            },
            "hospitalization": {},
            "diagnoses": {
                "ed_diagnosis_texts": [],
                "discharge_main_diagnosis_text": None,
                "discharge_other_diagnoses_texts": [],
                "ed_diagnosis_codes": None,
                "discharge_main_icd": None,
                "discharge_other_icds": None,
                "admission_condition": None,
                "discharge_main_outcome": None,
                "discharge_other_outcomes": None,
            },
            "procedures": {},
            "other_medical_info": {},
            "staff": {},
            "costs": {"total_cost": None, "self_paid": None, "categories": {}},
            "evidence": {},
            "confidence": {},
        }

        try:
            from ..database.connection import engine
            from sqlalchemy.orm import Session
            from sqlalchemy import text as sql_text

            with Session(engine) as session:

                # ---- 1. inpat_registration 表 → 住院登记信息 ----
                # 先从登记表获取 patient_id 以便查询 patient_information
                patient_id = None
                try:
                    reg = session.execute(sql_text(
                        "SELECT * FROM inpat_registration WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if reg:
                        patient_id = reg.get("patient_id")
                        fp_data["hospitalization"].update({
                            "medical_record_no": reg.get("mr_no") or "",
                            "admission_datetime": str(reg.get("admission_datetime") or ""),
                            "discharge_datetime": str(reg.get("discharge_datetime") or ""),
                            "admission_dept": reg.get("admission_dept_name") or "",
                            "discharge_dept": reg.get("discharge_dept_name") or "",
                            "payment_method_text": reg.get("insurance_type") or "",
                            "hospital_name": reg.get("hospital_name") or "",
                            "organization_code": reg.get("organization_code") or "",
                        })
                        # 计算住院天数
                        adm_dt = reg.get("admission_datetime")
                        dis_dt = reg.get("discharge_datetime")
                        if adm_dt and dis_dt:
                            try:
                                delta = dis_dt - adm_dt
                                fp_data["hospitalization"]["actual_hospital_days"] = max(delta.days, 1)
                            except Exception:
                                pass
                        # 年龄
                        age_str = reg.get("age_year") or reg.get("age")
                        if age_str and str(age_str).strip():
                            try:
                                fp_data["basic_info"]["age_years"] = int(str(age_str).strip())
                            except (ValueError, TypeError):
                                pass
                        # 基本信息冗余字段
                        fp_data["basic_info"]["patient_name"] = reg.get("name") or ""
                        sex_text = reg.get("sex") or ""
                        fp_data["basic_info"]["gender_text"] = sex_text
                        fp_data["basic_info"]["gender"] = _text_to_code("sex", sex_text)
                        logger.info(f"  inpat_registration 读取成功: patient_id={patient_id}")
                except Exception as e:
                    logger.warning(f"  inpat_registration 查询失败: {e}")

                # ---- 2. patient_information 表 → 人口学信息 ----
                if patient_id:
                    try:
                        pi = session.execute(sql_text(
                            "SELECT * FROM patient_information WHERE patient_id = :pid LIMIT 1"
                        ), {"pid": patient_id}).mappings().first()

                        if pi:
                            fp_data["basic_info"].update({
                                "patient_name": pi.get("name") or fp_data["basic_info"]["patient_name"],
                                "gender_text": pi.get("sex") or fp_data["basic_info"]["gender_text"],
                                "gender": _text_to_code("sex", pi.get("sex") or ""),
                                "birth_date": str(pi.get("birthday") or ""),
                                "nationality": pi.get("nationality") or "",
                                "ethnicity": pi.get("ethnicity") or "",
                                "marital_status": pi.get("marital_status") or "9",
                                "id_number": pi.get("id_card_no") or "",
                                "occupation": pi.get("occupation_category") or "",
                                # 地址类字段（HIS 补充）
                                "birthplace": pi.get("birthplace") or "",
                                "nativeplace": pi.get("nativeplace") or "",
                                "current_address": pi.get("currentaddress") or "",
                                "current_address_phone": pi.get("contact_number") or "",
                                "current_address_zip": pi.get("currentaddress_zip") or "",
                                "household_address": pi.get("household_address") or "",
                                "household_address_zip": pi.get("household_address_zip") or "",
                                "work_unit": pi.get("work_unit") or "",
                                "work_unit_phone": pi.get("work_unit_phone") or "",
                                "work_unit_zip": pi.get("work_unit_zip") or "",
                                # 联系人
                                "contact_name": pi.get("contact_name") or "",
                                "contact_relation": pi.get("contact_relationship") or "",
                                "contact_phone": pi.get("contact_telephone") or "",
                                "contact_address": pi.get("contact_address") or "",
                            })
                            # 码表映射：婚姻状况文本
                            ms = pi.get("marital_status") or ""
                            if ms and ms.isdigit():
                                fp_data["basic_info"]["marital_status_text"] = _code_to_text("marital_status", ms)
                            else:
                                fp_data["basic_info"]["marital_status_text"] = ms
                                fp_data["basic_info"]["marital_status"] = _text_to_code("marital_status", ms)
                            logger.info(f"  patient_information 读取成功: name={pi.get('name')}")
                    except Exception as e:
                        logger.warning(f"  patient_information 查询失败: {e}")

                # ---- 3. admission_record 表 → 入院记录结构化列 ----
                try:
                    adm = session.execute(sql_text(
                        "SELECT * FROM admission_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if adm:
                        # 补充住院信息
                        fp_data["hospitalization"]["admission_dept"] = (
                            adm.get("dept_name") or fp_data["hospitalization"].get("admission_dept") or ""
                        )
                        fp_data["hospitalization"]["admission_ward"] = adm.get("ward_name") or ""
                        route = adm.get("admission_route") or ""
                        fp_data["hospitalization"]["admission_way_text"] = route
                        fp_data["hospitalization"]["admission_way"] = _text_to_code("admission_route", route)

                        # 年龄（入院记录通常更准确）
                        age_str = adm.get("age_year")
                        if age_str and str(age_str).strip():
                            try:
                                fp_data["basic_info"]["age_years"] = int(str(age_str).strip())
                            except (ValueError, TypeError):
                                pass

                        # 人员签名
                        fp_data["staff"]["resident_physician"] = adm.get("resident_physician_sign") or ""
                        fp_data["staff"]["attending_physician"] = adm.get("attending_physician_sign") or ""
                        fp_data["staff"]["chief_physician"] = adm.get("chief_physician_sign") or ""

                        # 过敏史（结构化列）
                        allergy_text = adm.get("allergy_history") or ""
                        if allergy_text:
                            if "无" in allergy_text and len(allergy_text) < 10:
                                fp_data["other_medical_info"]["drug_allergy_flag"] = "1"
                                fp_data["other_medical_info"]["drug_allergy_flag_text"] = "无"
                            else:
                                fp_data["other_medical_info"]["drug_allergy_flag"] = "2"
                                fp_data["other_medical_info"]["drug_allergy_flag_text"] = "有"

                        logger.info("  admission_record 读取成功")
                except Exception as e:
                    logger.warning(f"  admission_record 查询失败: {e}")

                # ---- 4. discharge_record 表 → 出院记录结构化列 ----
                try:
                    dis = session.execute(sql_text(
                        "SELECT * FROM discharge_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if dis:
                        fp_data["hospitalization"]["discharge_dept"] = (
                            dis.get("dept_name") or fp_data["hospitalization"].get("discharge_dept") or ""
                        )
                        fp_data["hospitalization"]["discharge_ward"] = dis.get("ward_name") or ""
                        # 住院天数（出院记录版本）
                        duration = dis.get("inpatient_duration")
                        if duration and not fp_data["hospitalization"].get("actual_hospital_days"):
                            try:
                                fp_data["hospitalization"]["actual_hospital_days"] = int(str(duration).strip())
                            except (ValueError, TypeError):
                                pass
                        # 注：转归(condition_transform)属于诊断信息，
                        # 由 LLM 从病历文书独立提取，不从 SQL 读取，以便质控对照
                        logger.info("  discharge_record 读取成功")
                except Exception as e:
                    logger.warning(f"  discharge_record 查询失败: {e}")

                # ---- 5. inpat_bill_item 表 → 费用汇总（HIS 计费系统源头数据） ----
                # 从住院费用明细按 item_type 分类汇总，映射到首页 24 项费用
                try:
                    bill_rows = session.execute(sql_text(
                        "SELECT item_type, SUM(CAST(cost AS NUMERIC)) as total "
                        "FROM inpat_bill_item WHERE visit_id = :vid "
                        "GROUP BY item_type"
                    ), {"vid": visit_id}).mappings().all()

                    if bill_rows:
                        # item_type 中文名 → 首页费用分类索引的映射
                        type_to_cat = {
                            "一般医疗服务费": "1",
                            "床位费": "1",
                            "一般治疗操作费": "2",
                            "治疗操作费": "2",
                            "护理费": "3",
                            "其他费用": "4",
                            "其他服务费": "4",
                            "病理诊断费": "5",
                            "实验室诊断费": "6",
                            "检验费": "6",
                            "化验费": "6",
                            "影像学诊断费": "7",
                            "影像费": "7",
                            "放射费": "7",
                            "CT费": "7",
                            "MRI费": "7",
                            "临床诊断项目费": "8",
                            "非手术治疗项目费": "9",
                            "临床物理治疗费": "10",
                            "手术治疗费": "11",
                            "麻醉费": "12",
                            "手术费": "13",
                            "康复费": "14",
                            "中医治疗费": "15_cm",
                            "西药费": "15",
                            "抗菌药物费": "16",
                            "抗菌药物费用": "16",
                            "中成药费": "17",
                            "中草药费": "18",
                            "血费": "19",
                            "输血费": "19",
                            "白蛋白类制品费": "20",
                            "球蛋白类制品费": "21",
                            "凝血因子类制品费": "22",
                            "细胞因子类制品费": "23",
                            "检查用一次性医用材料费": "24",
                            "治疗用一次性医用材料费": "25",
                            "手术用一次性医用材料费": "26",
                        }

                        cats = {}
                        total_cost = 0.0
                        for row in bill_rows:
                            item_type = (row.get("item_type") or "").strip()
                            amount = float(row.get("total") or 0)
                            total_cost += amount

                            cat_key = type_to_cat.get(item_type)
                            if cat_key:
                                if cat_key == "15_cm":
                                    # 中医治疗费独立处理
                                    cats["chinese_medicine_treatment"] = cats.get("chinese_medicine_treatment", 0) + amount
                                else:
                                    cats[cat_key] = cats.get(cat_key, 0) + amount
                            else:
                                # 未匹配的费用归入"其他"
                                cats["other"] = cats.get("other", 0) + amount
                                logger.info(f"  费用类型未映射: {item_type} = {amount}")

                        fp_data["costs"]["total_cost"] = round(total_cost, 2)
                        fp_data["costs"]["categories"] = cats
                        logger.info(f"  inpat_bill_item 汇总成功: {len(bill_rows)} 类, 总费用={total_cost:.2f}")
                except Exception as e:
                    logger.warning(f"  inpat_bill_item 查询失败: {e}")

                # ---- 7. mr 表 → 住院过程补充信息（离院方式、转科、Barthel 等） ----
                # 注：mr 是首页目标表，此处仅读取源头文书中无法获取的管理类字段
                try:
                    mr_row = session.execute(sql_text(
                        "SELECT * FROM mr WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if mr_row:
                        # 离院方式
                        leaving_way = mr_row.get("leaving_hospital_way") or ""
                        if leaving_way:
                            fp_data["hospitalization"]["leaving_hospital_way"] = leaving_way
                        # 转科科别
                        transfer_dept = mr_row.get("transfer_dept_name") or "-"
                        fp_data["hospitalization"]["transfer_dept"] = transfer_dept
                        # 31 天内再住院
                        rehospital = mr_row.get("rehospital_with_month") or ""
                        fp_data["hospitalization"]["rehospital_within_month"] = rehospital
                        # 日常生活能力评定量表得分（Barthel 指数）
                        daily_adm = mr_row.get("daily_ability_admission")
                        daily_dis = mr_row.get("daily_ability_discharge")
                        if daily_adm is not None:
                            fp_data["hospitalization"]["daily_ability_admission"] = int(daily_adm)
                        if daily_dis is not None:
                            fp_data["hospitalization"]["daily_ability_discharge"] = int(daily_dis)
                        # 颅脑损伤昏迷时间
                        for field in ("brain_injury_before_admission_hours",
                                      "brain_injury_before_admission_minutes",
                                      "brain_injury_after_admission_hours",
                                      "brain_injury_after_admission_minutes"):
                            val = mr_row.get(field)
                            if val is not None:
                                fp_data["other_medical_info"][field] = int(val)

                        logger.info("  mr 表补充读取成功")
                except Exception as e:
                    logger.warning(f"  mr 表查询失败: {e}")

        except Exception as e:
            logger.error(f"_prefill_from_cdm 整体异常: {e}")

        fp_data["other_medical_info"] = self._normalize_other_medical_info_structure(
            fp_data.get("other_medical_info")
        )
        logger.info(f"_prefill_from_cdm 完成: 已从源头表填充首页草稿")
        return fp_data

    async def _get_llm_context_text(self, visit_id: str) -> str:
        """
        三层架构 - 第三层辅助：
        只拼接 LLM 需要看的源头文书全文（不读 mr 表！）。
        用于精准补缺，而不是全量提取。
        """
        logger.info(f"_get_llm_context_text: visit_id={visit_id}")
        sections = []
        try:
            from ..database.connection import engine
            from sqlalchemy.orm import Session
            from sqlalchemy import text as sql_text

            with Session(engine) as session:
                # 入院记录全文
                try:
                    adm = session.execute(sql_text(
                        "SELECT record_content FROM admission_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()
                    if adm:
                        content = adm.get("record_content") or ""
                        if content.strip():
                            sections.append(f"【入院记录】\n{content}")
                except Exception:
                    pass

                # 出院记录全文
                try:
                    dis = session.execute(sql_text(
                        "SELECT record_content FROM discharge_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()
                    if dis:
                        content = dis.get("record_content") or ""
                        if content.strip():
                            sections.append(f"【出院记录】\n{content}")
                except Exception:
                    pass

                # 病程记录及检验检查报告全文
                extra_tables = [
                    ("first_course_record", "首次病程记录"),
                    ("daily_course_record", "日常病程记录"),
                    ("senior_course_record", "上级医师查房记录"),
                    ("surgery_record", "手术记录"),
                    ("labtest_item_report", "检验报告"),
                    ("exam_item_report", "检查报告"),
                    ("consultation_record", "会诊记录"),
                    ("transfer_in_record", "转入记录"),
                    ("transfer_out_record", "转出记录"),
                    ("rescue_record", "抢救记录"),
                    ("postsurg_firstcourse_record", "术后首次病程记录"),
                ]
                for table_name, label in extra_tables:
                    try:
                        rows = session.execute(sql_text(
                            f"SELECT record_content FROM {table_name} WHERE visit_id = :vid"
                        ), {"vid": visit_id}).mappings().all()
                        if rows:
                            for idx, row in enumerate(rows, 1):
                                content = row.get("record_content") or ""
                                if content.strip():
                                    sections.append(f"【{label} - {idx}】\n{content}")
                    except Exception:
                        pass  # 表不存在时静默跳过

        except Exception as e:
            logger.error(f"_get_llm_context_text 异常: {e}")

        full_text = "\n\n".join(sections)
        logger.info(f"_get_llm_context_text 完成: 长度={len(full_text)}")
        return full_text

    async def _get_medical_text(self, visit_id: str) -> str:
        """
        根据 visit_id 从本地 PG 获取病历文书，拼接为全文供大模型提取。
        支持提取病案首页、入院出院记录、诊断列表及十余种病程和各类报告表。
        单表失败不影响其他表的数据获取。
        """
        logger.info(f"_get_medical_text: visit_id={visit_id}")
        try:
            from ..database.connection import engine
            from sqlalchemy.orm import Session
            from sqlalchemy import text as sql_text

            sections = []

            with Session(engine) as session:
                # 1. 病案首页基本信息
                try:
                    mr_row = session.execute(sql_text(
                        "SELECT * FROM mr WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if mr_row:
                        mr = dict(mr_row)
                        sections.append("【病案首页信息】")
                        sections.append(f"姓名: {mr.get('name', '')}")
                        sections.append(f"性别: {mr.get('sex', '')}")
                        sections.append(f"年龄: {mr.get('age_year', '')}岁")
                        sections.append(f"入院日期: {mr.get('admission_datetime', '')}")
                        sections.append(f"出院日期: {mr.get('discharge_datetime', '')}")
                        sections.append(f"住院天数: {mr.get('hospital_duration', '')}")
                        sections.append(f"出院科室: {mr.get('discharge_dept_name', '')}")
                        sections.append(f"医保类型: {mr.get('insurance_type', '')}")
                        sections.append(f"主治医师: {mr.get('attending_physician_sign', '')}")
                        sections.append(f"病案全文:\n{mr.get('record_content', '')}")
                        sections.append("")
                        logger.info(f"  mr 表查询成功: name={mr.get('name')}")
                except Exception as e:
                    logger.warning(f"  mr 表查询失败: {e}")

                # 2. 入院记录
                try:
                    adm_row = session.execute(sql_text(
                        "SELECT * FROM admission_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if adm_row:
                        adm = dict(adm_row)
                        sections.append("【入院记录】")
                        for field_name, label in [
                            ("chief_complaint", "主诉"),
                            ("present_illness_history", "现病史"),
                            ("past_history", "既往史"),
                            ("personal_history", "个人史"),
                            ("family_history", "家族史"),
                            ("physical_examination", "体格检查"),
                            ("specialty_examination", "专科检查"),
                            ("auxiliary_examination", "辅助检查"),
                            ("preliminary_diagnosis", "初步诊断"),
                            ("record_content", "入院记录全文"),
                        ]:
                            val = adm.get(field_name, "")
                            if val and str(val).strip():
                                sections.append(f"{label}: {val}")
                        sections.append("")
                        logger.info(f"  admission_record 表查询成功")
                except Exception as e:
                    logger.warning(f"  admission_record 表查询失败: {e}")

                # 3. 出院记录
                try:
                    dis_row = session.execute(sql_text(
                        "SELECT * FROM discharge_record WHERE visit_id = :vid LIMIT 1"
                    ), {"vid": visit_id}).mappings().first()

                    if dis_row:
                        dis = dict(dis_row)
                        sections.append("【出院记录】")
                        for field_name, label in [
                            ("admission_situation", "入院情况"),
                            ("treatment_process", "诊疗经过"),
                            ("discharge_situation", "出院情况"),
                            ("discharge_diagnosis", "出院诊断"),
                            ("discharge_order", "出院医嘱"),
                            ("record_content", "出院记录全文"),
                        ]:
                            val = dis.get(field_name, "")
                            if val and str(val).strip():
                                sections.append(f"{label}: {val}")
                        sections.append("")
                        logger.info(f"  discharge_record 表查询成功")
                except Exception as e:
                    logger.warning(f"  discharge_record 表查询失败: {e}")

                # 4. 诊断列表
                try:
                    diag_rows = session.execute(sql_text(
                        "SELECT * FROM diagnosis WHERE visit_id = :vid"
                    ), {"vid": visit_id}).mappings().all()

                    if diag_rows:
                        sections.append("【诊断列表】")
                        for i, row in enumerate(diag_rows, 1):
                            d = dict(row)
                            name = d.get("diagnosis_name", "")
                            code = d.get("diagnosis_code", "")
                            dtype = d.get("diagnosis_type", "")
                            sections.append(f"{i}. {name} ({code}) [{dtype}]")
                        sections.append("")
                        logger.info(f"  diagnosis 表查询成功: {len(diag_rows)} 条")
                except Exception as e:
                    logger.warning(f"  diagnosis 表查询失败: {e}")
                    
                # 5. 其他病程记录与各类报告单全文
                extra_tables = [
                    ("first_course_record", "首次病程记录"),
                    ("daily_course_record", "日常病程记录"),
                    ("senior_course_record", "上级医师查房记录"),
                    ("postsurg_firstcourse_record", "术后首次病程记录"),
                    ("consultation_record", "会诊记录"),
                    ("rescue_record", "抢救记录"),
                    ("transfer_in_record", "转入记录"),
                    ("transfer_out_record", "转出记录"),
                    ("surgery_record", "手术记录"),
                    ("labtest_item_report", "检验报告"),
                    ("exam_item_report", "检查报告")
                ]
                
                for table_name, label in extra_tables:
                    try:
                        rows = session.execute(sql_text(
                            f"SELECT record_content FROM {table_name} WHERE visit_id = :vid"
                        ), {"vid": visit_id}).mappings().all()
                        
                        if rows:
                            for idx, row in enumerate(rows, 1):
                                content = row.get("record_content", "")
                                if content and str(content).strip():
                                    sections.append(f"【{label} - {idx}】\n{content}\n")
                            logger.info(f"  {table_name} 表查询成功: {len(rows)} 条")
                    except Exception as e:
                        # 兼容有些表还没创建或查询异常的情况
                        pass

            if sections:
                full_text = "\n".join(sections)
                logger.info(f"从本地 PG 获取全病历文本成功: visit_id={visit_id}, 组装长度={len(full_text)}")
                return full_text

        except Exception as e:
            logger.warning(f"从本地 PG 获取全病历文本失败: {e}, 回退到 demo 数据")

        # 回退到 demo JSON
        logger.info(f"visit_id={visit_id} 在本地 PG 无数据，使用 demo 数据")
        if self.demo_data_path.exists():
            with self.demo_data_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("medical_text", "")
        return ""

    def _build_diag_proc_context_text(self, medical_text: str, max_chars: int = 4200) -> str:
        """
        Build a compact context for diagnosis/procedure extraction.
        This reduces prompt length by slicing windows around high-signal keywords.
        """
        if not medical_text:
            return ""

        text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
        if len(text) <= max_chars:
            return text

        keywords = [
            "出院诊断",
            "入院诊断",
            "初步诊断",
            "门诊诊断",
            "急诊诊断",
            "术前诊断",
            "术后诊断",
            "手术记录",
            "手术经过",
            "手术名称",
            "手术操作",
            "诊疗经过",
            "病程记录",
            "出院记录",
            "出院小结",
        ]

        windows: List[Tuple[int, int]] = []
        left_pad = 120
        right_pad = 960
        for kw in keywords:
            for m in re.finditer(re.escape(kw), text):
                s = max(0, m.start() - left_pad)
                e = min(len(text), m.end() + right_pad)
                windows.append((s, e))

        if not windows:
            trimmed = text[:max_chars]
            logger.info(
                "diag_proc context trim fallback to head slice: raw=%d trimmed=%d",
                len(text),
                len(trimmed),
            )
            return trimmed

        windows.sort(key=lambda x: x[0])
        merged: List[Tuple[int, int]] = []
        for s, e in windows:
            if not merged or s > merged[-1][1] + 120:
                merged.append((s, e))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))

        chunks: List[str] = []
        for s, e in merged:
            chunk = text[s:e].strip()
            if chunk:
                chunks.append(chunk)

        compact = "\n\n".join(chunks).strip()
        if len(compact) < 240:
            compact = text[:max_chars]
        elif len(compact) > max_chars:
            compact = compact[:max_chars]

        logger.info(
            "diag_proc context trimmed: raw=%d trimmed=%d segments=%d",
            len(text),
            len(compact),
            len(chunks),
        )
        return compact

    def _normalize_context_strategy(
        self,
        context_strategy: Optional[str],
        default_mode: str = "full",
    ) -> str:
        mode = str(context_strategy or "").strip().lower()
        if mode in {"full", "retrieval"}:
            return mode
        if mode:
            logger.warning(
                "unknown context_strategy=%s, fallback=%s", mode, default_mode
            )
        return default_mode

    def _select_context_text(
        self,
        medical_text: str,
        context_strategy: Optional[str],
        *,
        max_chars: int,
        default_mode: str,
    ) -> str:
        mode = self._normalize_context_strategy(context_strategy, default_mode=default_mode)
        text = medical_text or ""
        if mode == "full":
            return text
        return self._build_diag_proc_context_text(text, max_chars=max_chars)

    async def _extract_with_llm(
        self, medical_text: str, context_strategy: Optional[str] = None
    ) -> FrontPageDraft:
        """使用 LLM 分步抽取各模块信息，并结合外部编码服务进行校验"""
        logger.info("开始 LLM 分步抽取病案首页信息...")
        
        # 1. 先提取基本信息（用于为外部编码服务提供上下文）
        try:
            logger.info("Step 1: 提取基本信息...")
            basic_info = await self._extract_json(BASIC_INFO_PROMPT.format(medical_text=medical_text)) or {}
        except Exception as e:
            logger.error(f"基本信息提取失败: {e}")
            basic_info = {}

        # 准备患者上下文
        patient_context = {
            "gender": basic_info.get("gender_text", "未说明"),
            "age": basic_info.get("age_years", 0)
        }
        
        # 2. 并行抽取其他模块 + 外部编码服务
        logger.info("Step 2: 并行提取其他模块及外部编码...")
        from .external_coding_service import get_external_coding_service
        ext_coding_service = get_external_coding_service()
        diag_proc_context_text = self._select_context_text(
            medical_text,
            context_strategy,
            max_chars=4200,
            default_mode="full",
        )
        
        # 定义并行任务
        tasks = {
            "hospitalization": self._extract_json(HOSPITALIZATION_PROMPT.format(medical_text=medical_text)),
            "diagnoses": self._extract_json(
                DIAGNOSES_PROMPT.format(medical_text=diag_proc_context_text),
                max_tokens=1200,
            ),
            "procedures": self._extract_json(
                PROCEDURES_PROMPT.format(medical_text=diag_proc_context_text),
                max_tokens=1200,
            ),
            "other_medical": self._extract_json(OTHER_MEDICAL_INFO_PROMPT.format(medical_text=medical_text)),
            "staff": self._extract_json(STAFF_PROMPT.format(medical_text=medical_text)),
            "coding_result": ext_coding_service.extract_coding(medical_text, patient_context)
        }
        
        try:
            # 执行所有任务
            task_names = list(tasks.keys())
            task_coroutines = list(tasks.values())
            
            results_list = await asyncio.gather(*task_coroutines, return_exceptions=True)
            results = dict(zip(task_names, results_list))
            
            # 处理结果
            hospitalization = results.get("hospitalization") if not isinstance(results.get("hospitalization"), Exception) else {}
            diagnoses = results.get("diagnoses") if not isinstance(results.get("diagnoses"), Exception) else {}
            procedures = results.get("procedures") if not isinstance(results.get("procedures"), Exception) else {}
            other_medical = results.get("other_medical") if not isinstance(results.get("other_medical"), Exception) else {}
            staff = results.get("staff") if not isinstance(results.get("staff"), Exception) else {}
            coding_result = results.get("coding_result") if not isinstance(results.get("coding_result"), Exception) else None
            
            if isinstance(results.get("coding_result"), Exception):
                logger.warning(f"外部编码服务调用失败: {results.get('coding_result')}")
            
            # 初始化默认值
            hospitalization = hospitalization or {}
            diagnoses = diagnoses or {}
            procedures = procedures or {}

            if not diagnoses:
                logger.warning("diagnoses extraction empty, retry once")
                diag_fallback = await self._extract_json(
                    DIAGNOSES_PROMPT.format(medical_text=diag_proc_context_text),
                    max_tokens=1200,
                )
                diagnoses = diag_fallback or {}

            if not procedures:
                logger.warning("procedures extraction empty, retry once")
                proc_fallback = await self._extract_json(
                    PROCEDURES_PROMPT.format(medical_text=diag_proc_context_text),
                    max_tokens=1200,
                )
                procedures = proc_fallback or {}

            other_medical = other_medical or {}
            staff = staff or {}
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
            procedures = self._normalize_procedures_structure(procedures)
            other_medical = self._normalize_other_medical_info_structure(other_medical)

        except Exception as e:
            logger.error(f"并行抽取发生严重错误: {e}")
            raise e
        
        # 3. 合并外部编码结果（如果成功）
        validation_info = {}
        if isinstance(coding_result, dict):
            logger.info("合并外部编码服务结果...")
            coding_data_raw = coding_result.get("coding_data", coding_result)
            coding_data = coding_data_raw if isinstance(coding_data_raw, dict) else {}
            if coding_data_raw is not None and not isinstance(coding_data_raw, dict):
                logger.warning("coding_data 结构异常，type=%s", type(coding_data_raw).__name__)

            # 仅补编码，不覆盖诊断名称
            diagnoses = self._apply_external_diagnosis_codes(
                diagnoses=diagnoses,
                coding_data=coding_data,
                validation_info=validation_info,
            )
                
            # 手术
            pp_raw = coding_data.get("principal_procedures")
            pp_list = [p for p in pp_raw if isinstance(p, dict)] if isinstance(pp_raw, list) else []
            if pp_list:
                main_proc = pp_list[0]
                if not procedures.get("main_procedure_text"):
                    procedures["main_procedure_text"] = main_proc.get("name")
                if not procedures.get("main_procedure_code"):
                    procedures["main_procedure_code"] = main_proc.get("code")
                
                # 其他手术
                if len(pp_list) > 1:
                    existing_others = procedures.get("other_procedures_texts") or []
                    procedures["other_procedures_texts"] = [
                        *existing_others,
                        *[p.get("name") for p in pp_list[1:] if p.get("name")],
                    ]
                    procedures["other_procedures_codes"] = [p.get("code") for p in pp_list[1:]]
            procedures = self._normalize_procedures_structure(procedures)
            
            # 校验警告
            warnings = coding_result.get("warnings") or coding_data.get("warnings")
            if isinstance(warnings, list) and warnings:
                validation_info["warnings"] = warnings
                logger.info(f"捕获到 {len(warnings)} 条编码警告")
        elif coding_result is not None:
            logger.warning("外部编码结果结构异常，type=%s", type(coding_result).__name__)

        # F4: 入院病情推理（只在没有外部结果时使用 mock/LLM 推理，或者作为补充）
        # 这里我们仍然运行它来获取 admission_condition
        if diagnoses:
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
            diagnoses = await self._infer_admission_conditions(medical_text, diagnoses)
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
        

        # ===== 主诊断规则裁决（在 ICD 编码前） =====
        clinician_main_before_rules = ""
        _rule_trace_llm: List[Dict[str, Any]] = []
        if diagnoses:
            clinician_main_before_rules = str(
                diagnoses.get("discharge_main_diagnosis_text") or ""
            ).strip()
            from .main_diagnosis_rules import apply_main_diagnosis_guideline_rules
            diagnoses, _rule_trace_llm = apply_main_diagnosis_guideline_rules(
                medical_text=medical_text,
                diagnoses=diagnoses,
                procedures=procedures or {},
            )
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
        # F5/F7: 使用本地 ICD 编码库查询国临版编码（替换 LLM 输出的编码）
        from .local_icd_service import resolve_diagnosis_codes, resolve_procedure_codes
        if diagnoses:
            diagnoses = resolve_diagnosis_codes(diagnoses)
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
        if procedures:
            procedures = self._normalize_procedures_structure(procedures)
            procedures = resolve_procedure_codes(procedures)

        # LLM 审核证据（单次推理输出 main_diagnosis_llm + coding_audit_llm）
        main_diagnosis_llm: Optional[Dict[str, Any]] = None
        coding_audit_llm: Optional[Dict[str, Any]] = None
        try:
            merged_evidence = await self._build_main_and_audit_llm_evidence(
                medical_text=medical_text,
                diagnoses=diagnoses,
                procedures=procedures,
                clinician_main_diagnosis=clinician_main_before_rules,
                context_strategy=context_strategy,
            )
            main_diagnosis_llm = merged_evidence.get("main_diagnosis_llm")
            coding_audit_llm = merged_evidence.get("coding_audit_llm")
        except Exception:
            logger.exception("build llm evidence failed")
        
        other_medical = self._apply_ventilation_hours_quality_rules(medical_text, other_medical, validation_info)

        # 组装 FrontPageDraft
        frontpage_data = {
            "basic_info": basic_info,
            "hospitalization": hospitalization,
            "diagnoses": diagnoses,
            "procedures": procedures,
            "other_medical_info": other_medical,
            "staff": staff,
            "costs": {"total_cost": None, "self_paid": None, "categories": {}},
            "evidence": {
                "guideline_rule_trace": _rule_trace_llm,
                "clinician_main_diagnosis": clinician_main_before_rules,
                "main_diagnosis_llm": main_diagnosis_llm,
                "coding_audit_llm": coding_audit_llm,
                "diagnoses": self._build_diagnosis_evidence(
                    medical_text,
                    diagnoses,
                    procedures,
                    guideline_rule_trace=_rule_trace_llm,
                    clinician_main_diagnosis=clinician_main_before_rules,
                ),
            },
            "confidence": validation_info, # 将校验信息放入 confidence 字段
        }

        frontpage_data = self._sanitize_frontpage_data(frontpage_data)
        logger.info("LLM 抽取完成，构建 FrontPageDraft")
        logger.debug(
            "frontpage_data before model_validate=%s",
            json.dumps(frontpage_data, ensure_ascii=False, default=str),
        )
        try:
            return FrontPageDraft.model_validate(frontpage_data)
        except ValidationError as e:
            logger.error("FrontPageDraft 验证失败: %s", e)
            logger.error("FrontPageDraft 验证错误详情: %s", e.errors())
            logger.error(
                "frontpage_data.basic_info=%s",
                json.dumps(frontpage_data.get("basic_info", {}), ensure_ascii=False, default=str),
            )
            logger.error(
                "frontpage_data.diagnoses=%s",
                json.dumps(frontpage_data.get("diagnoses", {}), ensure_ascii=False, default=str),
            )
            logger.error(
                "frontpage_data(full)=%s",
                json.dumps(frontpage_data, ensure_ascii=False, default=str),
            )
            raise

    async def _extract_json(
        self, prompt: str, max_tokens: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """调用 LLM 并解析 JSON 响应"""
        try:
            response = await self.llm_client.generate(
                SYSTEM_PROMPT, prompt, max_tokens=max_tokens
            )
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM 抽取失败: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 返回的 JSON"""
        if not response:
            return None
        
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end + 1]
            else:
                return None
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            return None

    def _sanitize_frontpage_data(self, frontpage_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        兜底清洗：在最终 model_validate 前，统一修正常见 LLM 类型偏差。
        重点处理诊断列表里的 None/数字，避免 string_type 触发整包失败。
        """
        if not isinstance(frontpage_data, dict):
            return frontpage_data

        diagnoses = frontpage_data.get("diagnoses")
        if isinstance(diagnoses, dict):
            required_list_fields = [
                "ed_diagnosis_texts",
                "discharge_other_diagnoses_texts",
            ]
            optional_list_fields = [
                "ed_diagnosis_codes",
                "discharge_other_icds",
                "discharge_other_outcomes",
            ]
            scalar_str_fields = [
                "discharge_main_diagnosis_text",
                "discharge_main_icd",
                "admission_condition",
                "discharge_main_outcome",
            ]

            def _clean_list(raw: Any, allow_none: bool) -> Optional[List[str]]:
                if raw is None:
                    return None if allow_none else []
                items = raw if isinstance(raw, list) else [raw]
                out: List[str] = []
                for item in items:
                    if item is None:
                        continue
                    text = str(item).strip()
                    if text:
                        out.append(text)
                if allow_none and not out:
                    return None
                return out

            for field in required_list_fields:
                diagnoses[field] = _clean_list(diagnoses.get(field), allow_none=False) or []
            for field in optional_list_fields:
                diagnoses[field] = _clean_list(diagnoses.get(field), allow_none=True)
            for field in scalar_str_fields:
                val = diagnoses.get(field)
                if isinstance(val, (int, float)):
                    diagnoses[field] = str(int(val)) if float(val).is_integer() else str(val)

            frontpage_data["diagnoses"] = diagnoses

        other_medical_info = self._normalize_other_medical_info_structure(
            frontpage_data.get("other_medical_info")
        )
        frontpage_data["other_medical_info"] = other_medical_info

        costs = frontpage_data.get("costs")
        if isinstance(costs, dict):
            categories = costs.get("categories")
            if isinstance(categories, dict):
                legacy_to_semantic = {
                    "1": "general_medical_service",
                    "2": "general_treatment",
                    "3": "nursing_care",
                    "4": "other_service",
                    "5": "pathological_diagnostic",
                    "6": "laboratory_diagnostic",
                    "7": "imaging_diagnostic",
                    "8": "clinical_diagnostic",
                    "9": "nonsurgical_treatment",
                    "10": "clinical_physical_therapy",
                    "11": "surgery_treatment",
                    "12": "anesthesia",
                    "13": "surgery",
                    "14": "rehabilitation",
                    "15_cm": "chinese_medicine_treatment",
                    "15": "western_medicine",
                    "16": "antibacterial_drug",
                    "17": "chinese_patent_medicine",
                    "18": "chinese_herbal_medicine",
                    "19": "blood",
                    "20": "albumin",
                    "21": "globulin",
                    "22": "coagulation_factor",
                    "23": "cytokine",
                    "24": "exam_disposable_material",
                    "25": "treat_disposable_material",
                    "26": "surgery_disposable_material",
                }
                for legacy_key, semantic_key in legacy_to_semantic.items():
                    if semantic_key not in categories and legacy_key in categories:
                        categories[semantic_key] = categories.get(legacy_key)
                costs["categories"] = categories
            frontpage_data["costs"] = costs

        # basic_info 数值字段容错：空字符串/非法字符串 -> None，避免 model_validate 500
        basic_info = frontpage_data.get("basic_info")
        if isinstance(basic_info, dict):
            age_val = basic_info.get("age_years")
            if isinstance(age_val, str):
                cleaned = age_val.strip()
                if cleaned == "":
                    basic_info["age_years"] = None
                else:
                    try:
                        basic_info["age_years"] = int(float(cleaned))
                    except Exception:
                        basic_info["age_years"] = None
            elif isinstance(age_val, (int, float)):
                try:
                    basic_info["age_years"] = int(age_val)
                except Exception:
                    basic_info["age_years"] = None
            elif age_val is not None:
                basic_info["age_years"] = None

            frontpage_data["basic_info"] = basic_info

        return frontpage_data

    def _normalize_diag_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        text = value.strip().replace("\u3000", " ")
        # Strip trailing discharge-outcome suffix to avoid duplicate diagnoses like:
        # "高血压病3级 极高危（出院转归：好转）" vs "高血压病3级 极高危"
        text = re.sub(r"[（(]\s*出院转归\s*[：:]\s*[^（）()]*[）)]\s*$", "", text)
        text = re.sub(r"[，,;；]\s*出院转归\s*[：:]\s*[^，,;；。]*\s*$", "", text)
        text = re.sub(r"\s*出院转归\s*[：:]\s*[^，,;；。]*\s*$", "", text)
        # Drop trailing unmatched bracket fragments like "冠心病（"
        text = re.sub(r"[（(]\s*$", "", text)
        text = re.sub(r"^[\-\u2022•·]+\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ;；,，。")

    def _diagnosis_canonical_key(self, value: Any) -> str:
        """
        Build a stable key for deduplication.
        It removes noisy punctuation/whitespace and ignores parenthetical suffix.
        """
        text = self._normalize_diag_text(value)
        if not text:
            return ""
        key = text.lower()
        key = re.sub(r"[（(].*$", "", key)
        key = re.sub(r"[\s\-\u2022•·,，;；:：()（）\[\]【】]+", "", key)
        return key

    def _unique_texts(self, texts: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for text in texts:
            cleaned = self._normalize_diag_text(text)
            if not cleaned:
                continue
            key = self._diagnosis_canonical_key(cleaned)
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
        return out

    def _split_compound_diagnosis_line(self, text: str) -> List[str]:
        """
        Split compound diagnoses in one line, e.g.
        "冠状动脉粥样硬化性心脏病 不稳定型心绞痛".
        """
        cleaned = self._normalize_diag_text(text)
        if not cleaned:
            return []

        # Strong delimiters first.
        parts = [p.strip() for p in re.split(r"[；;、，,]+", cleaned) if p and p.strip()]

        # Conservative whitespace split fallback.
        if len(parts) == 1:
            tokenized = [t.strip() for t in re.split(r"\s+", cleaned) if t and t.strip()]
            if len(tokenized) >= 2 and all(len(t) >= 4 for t in tokenized):
                parts = tokenized

        return self._unique_texts(parts)

    def _extract_discharge_diagnoses_from_text(self, medical_text: str) -> List[str]:
        """
        Parse discharge diagnoses from the `出院诊断` section.
        Numbered items can span multiple lines; each continuation line is treated as
        an independent diagnosis candidate.
        """
        if not medical_text or not medical_text.strip():
            return []

        text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")

        start_idx = -1
        inline_text = ""
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            m = re.match(r"^出院诊断\s*[：:]\s*(.*)$", line)
            if m:
                start_idx = i
                inline_text = m.group(1).strip()
                break
            if re.match(r"^出院诊断\s*$", line):
                start_idx = i
                break

        if start_idx < 0:
            return []

        section_lines: List[str] = []
        if inline_text:
            section_lines.append(inline_text)

        stop_header = re.compile(
            r"^(入院诊断|诊疗经过|出院情况|出院医嘱|医师签名|记录时间|主诉|现病史|既往史|体格检查|辅助检查)\s*[：:]?"
        )
        for raw_line in lines[start_idx + 1 :]:
            stripped = raw_line.strip()
            if not stripped:
                continue
            if re.match(r"^={3,}$", stripped):
                break
            if stop_header.match(stripped):
                break
            section_lines.append(raw_line)

        if not section_lines:
            return []

        numbered = re.compile(r"^\s*\d{1,2}[\.、\)]\s*(.+?)\s*$")
        items: List[List[str]] = []
        current: List[str] = []

        for raw_line in section_lines:
            m = numbered.match(raw_line)
            if m:
                if current:
                    items.append(current)
                current = []
                first_line = self._normalize_diag_text(m.group(1))
                if first_line:
                    current.append(first_line)
                continue

            line = self._normalize_diag_text(raw_line)
            if not line:
                continue

            if current:
                current.append(line)
            else:
                items.append([line])

        if current:
            items.append(current)

        flattened: List[str] = []
        for chunk in items:
            for item in chunk:
                split_items = self._split_compound_diagnosis_line(item)
                if split_items:
                    flattened.extend(split_items)
                else:
                    flattened.append(item)

        return self._unique_texts(flattened)

    def _normalize_diagnoses_structure(
        self, medical_text: str, diagnoses: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Normalize diagnosis structure in strict mode:
        diagnosis text is sourced only from the `出院诊断` section in medical_text.
        """
        if isinstance(diagnoses, dict):
            diag: Dict[str, Any] = dict(diagnoses)
        else:
            if diagnoses is not None:
                logger.warning(
                    "normalize diagnoses received non-dict input, type=%s",
                    type(diagnoses).__name__,
                )
            diag = {}

        parsed_from_text = self._unique_texts(
            self._extract_discharge_diagnoses_from_text(medical_text)
        )
        llm_main = self._normalize_diag_text(diag.get("discharge_main_diagnosis_text"))
        llm_main_parts = self._split_compound_diagnosis_line(llm_main) if llm_main else []
        llm_others_raw = diag.get("discharge_other_diagnoses_texts")
        llm_others = self._unique_texts(llm_others_raw if isinstance(llm_others_raw, list) else [])

        # Keep LLM-selected main diagnosis when available, but split compound main
        # so that only one diagnosis is kept as main.
        if llm_main_parts:
            main = llm_main_parts[0]
        elif llm_main:
            main = llm_main
        elif parsed_from_text:
            main = parsed_from_text[0]
        else:
            main = None

        # Use LLM others first; fallback to parsed others.
        if llm_others or len(llm_main_parts) > 1:
            split_main_others = llm_main_parts[1:] if len(llm_main_parts) > 1 else []
            llm_others = self._unique_texts([*split_main_others, *llm_others])
        if llm_others:
            other_candidates = llm_others
        else:
            if llm_main:
                other_candidates = parsed_from_text
            else:
                other_candidates = parsed_from_text[1:] if parsed_from_text else []

        others: List[str] = []
        seen_other_keys = set()
        main_key = self._diagnosis_canonical_key(main) if main else ""
        for text in other_candidates:
            cleaned = self._normalize_diag_text(text)
            if not cleaned:
                continue
            key = self._diagnosis_canonical_key(cleaned)
            if not key or key == main_key or key in seen_other_keys:
                continue
            seen_other_keys.add(key)
            others.append(cleaned)

        diag["discharge_main_diagnosis_text"] = main or None
        diag["discharge_other_diagnoses_texts"] = others

        other_icds = diag.get("discharge_other_icds")
        if not isinstance(other_icds, list):
            other_icds = []
        if len(other_icds) < len(others):
            other_icds = other_icds + [None] * (len(others) - len(other_icds))
        elif len(other_icds) > len(others):
            other_icds = other_icds[: len(others)]
        diag["discharge_other_icds"] = other_icds

        return diag

    def _extract_diagnosis_section_blocks(self, medical_text: str) -> List[Tuple[str, str]]:
        """
        Extract diagnosis-related text blocks for evidence matching.
        Returns list of (section_name, section_text).
        """
        if not medical_text or not medical_text.strip():
            return []

        text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
        section_heads = [
            "出院诊断",
            "初步诊断",
            "入院诊断",
            "门诊诊断",
            "急诊诊断",
            "诊断",
        ]
        stop_heads = [
            "诊疗计划",
            "治疗计划",
            "治疗方案",
            "手术",
            "主诉",
            "现病史",
            "既往史",
            "体格检查",
            "辅助检查",
            "医师签名",
            "记录时间",
        ]
        stop_re = re.compile(rf"^(?:{'|'.join(stop_heads)})\s*[:：]?")
        blocks: List[Tuple[str, str]] = []

        lines = text.split("\n")
        for idx, raw in enumerate(lines):
            line = raw.strip()
            matched_head = None
            inline = ""
            for head in section_heads:
                m = re.match(rf"^{head}\s*[:：]?\s*(.*)$", line)
                if m:
                    matched_head = head
                    inline = (m.group(1) or "").strip()
                    break
            if not matched_head:
                continue

            collected: List[str] = []
            if inline:
                collected.append(inline)
            for nxt in lines[idx + 1 :]:
                s = nxt.strip()
                if not s:
                    continue
                if stop_re.match(s):
                    break
                collected.append(s)
            if collected:
                blocks.append((matched_head, "\n".join(collected)))
        return blocks

    def _build_diagnosis_evidence(
        self,
        medical_text: str,
        diagnoses: Optional[Dict[str, Any]],
        procedures: Optional[Dict[str, Any]] = None,
        guideline_rule_trace: Optional[List[Dict[str, Any]]] = None,
        clinician_main_diagnosis: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build diagnosis evidence list for frontend trust display.
        Includes both direct diagnosis quote and clinical supporting quotes.
        """
        if not isinstance(diagnoses, dict):
            return []

        entries: List[Tuple[str, str]] = []
        main = self._normalize_diag_text(diagnoses.get("discharge_main_diagnosis_text"))
        if main:
            entries.append(("main", main))
        others_raw = diagnoses.get("discharge_other_diagnoses_texts")
        if isinstance(others_raw, list):
            for item in others_raw:
                cleaned = self._normalize_diag_text(item)
                if cleaned:
                    entries.append(("other", cleaned))

        if not entries:
            return []

        clinician_main_text = self._normalize_diag_text(clinician_main_diagnosis or "")
        if not clinician_main_text and isinstance(guideline_rule_trace, list):
            for rule_item in guideline_rule_trace:
                if not isinstance(rule_item, dict):
                    continue
                if rule_item.get("rule") == "主诊断更换":
                    old_main = self._normalize_diag_text(rule_item.get("old_main") or "")
                    if old_main:
                        clinician_main_text = old_main
                        break

        blocks = self._extract_diagnosis_section_blocks(medical_text)
        block_lines: List[Tuple[str, str, int]] = []
        section_line_counter: Dict[str, int] = {}
        for sec, sec_text in blocks:
            for ln in sec_text.split("\n"):
                cleaned_ln = ln.strip()
                if cleaned_ln:
                    section_line_counter[sec] = section_line_counter.get(sec, 0) + 1
                    block_lines.append((sec, cleaned_ln, section_line_counter[sec]))
        diagnosis_line_keys = {
            self._diagnosis_canonical_key(line)
            for _, line, _ in block_lines
            if self._diagnosis_canonical_key(line)
        }

        # Full-text line pool for treatment/procedure/course support searching.
        all_lines = []
        if medical_text:
            for ln in medical_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                s = ln.strip()
                if s and len(s) >= 4:
                    all_lines.append(s)

        treatment_terms = [
            "手术", "术后", "治疗", "介入", "支架", "造影", "PCI", "CABG",
            "药", "病程", "复查", "检验", "检查", "肌钙蛋白", "心电图", "超声", "CT", "MRI",
        ]

        def _diag_keywords(diag_text: str) -> List[str]:
            seeds = [
                x
                for x in re.split(r"[\s,，;；、:：()（）\[\]【】+\-/]+", diag_text or "")
                if len(x) >= 2
            ]
            # keep medium-length terms first, avoid very generic words
            seeds = [x for x in seeds if x not in {"诊断", "疾病", "状态", "综合征"}]
            seeds.sort(key=len, reverse=True)
            return seeds[:6]

        def _compact_text(text: str) -> str:
            return re.sub(r"[\s,，;；、:：()（）\[\]【】\.\-_/+]+", "", text or "").lower()

        def _is_redundant_with_quote(line: str, main_quote: Optional[str]) -> bool:
            if not main_quote:
                return False
            a = _compact_text(line)
            b = _compact_text(main_quote)
            if not a or not b:
                return False
            if a == b:
                return True
            # contain/contained: treat as same-origin sentence variation
            if a in b or b in a:
                return True
            # high overlap fallback
            min_len = max(1, min(len(a), len(b)))
            same = sum(1 for ch in a if ch in b)
            return (same / min_len) >= 0.85

        def _supporting_quotes(diag_text: str, main_quote: Optional[str]) -> List[str]:
            keywords = _diag_keywords(diag_text)
            if not keywords:
                return []
            candidates: List[Tuple[float, str]] = []
            main_key = self._diagnosis_canonical_key(main_quote or "")
            for line in all_lines:
                line_key = self._diagnosis_canonical_key(line)
                if not line_key or (main_key and line_key == main_key):
                    continue
                if line_key in diagnosis_line_keys:
                    # supporting evidence should come from course/treatment context,
                    # not a duplicated diagnosis-section sentence.
                    continue
                if _is_redundant_with_quote(line, main_quote):
                    continue
                if "诊断" in line and "治疗" not in line and "手术" not in line and "病程" not in line:
                    continue
                hit = sum(1 for kw in keywords if kw in line)
                if hit <= 0:
                    continue
                has_treatment = any(term.lower() in line.lower() for term in treatment_terms)
                score = hit + (0.8 if has_treatment else 0.0)
                if score < 1.0:
                    continue
                candidates.append((score, line))
            candidates.sort(key=lambda x: x[0], reverse=True)
            selected: List[str] = []
            seen = set()
            for _, line in candidates:
                key = self._diagnosis_canonical_key(line)
                if not key or key in seen:
                    continue
                seen.add(key)
                selected.append(line)
                if len(selected) >= 3:
                    break
            return selected

        main_proc_text = ""
        if isinstance(procedures, dict):
            main_proc_text = str(procedures.get("main_procedure_text") or "")
        proc_key = self._diagnosis_canonical_key(main_proc_text)

        def _is_status_like(name: str) -> bool:
            return any(k in name for k in ["后状态", "术后", "植入后", "既往", "病史"])

        def _reasoning_checks(
            diag_text: str,
            dtype: str,
            sec: str,
            quote: Optional[str],
            support_quotes: List[str],
        ) -> List[Dict[str, Any]]:
            is_main = dtype == "main"
            checks: List[Dict[str, Any]] = []

            source_ok = sec in {"出院诊断", "初步诊断", "入院诊断"}
            checks.append(
                {
                    "item": "候选来源为诊断条目",
                    "status": bool(source_ok),
                    "evidence_quote": quote or "",
                    "explain": "主要诊断候选应首先来自出院/入院诊断条目。",
                    "rule_ref": "《住院病案首页填写规范（暂行）》第10、11条",
                }
            )

            proc_support_quote = ""
            proc_ok = False
            if main_proc_text:
                diag_key = self._diagnosis_canonical_key(diag_text)
                if diag_key and proc_key and (diag_key[:4] in proc_key or proc_key[:4] in diag_key):
                    proc_ok = True
                    proc_support_quote = main_proc_text
                else:
                    for sq in support_quotes:
                        if any(t in sq for t in ["手术", "介入", "支架", "造影", "治疗"]):
                            proc_ok = True
                            proc_support_quote = sq
                            break
            checks.append(
                {
                    "item": "与主要治疗/手术方向一致",
                    "status": bool(proc_ok) if is_main else True,
                    "evidence_quote": proc_support_quote,
                    "explain": "主要诊断应尽量与主要手术或关键治疗过程一致。",
                    "rule_ref": "《住院病案首页填写规范（暂行）》第11条第（二）项",
                }
            )

            severity_terms = ["重症", "不稳定", "急性", "危重", "监护", "介入", "手术", "PCI", "造影"]
            burden_quote = next(
                (sq for sq in support_quotes if any(term in sq for term in severity_terms)),
                "",
            )
            checks.append(
                {
                    "item": "存在病程严重程度或资源消耗佐证",
                    "status": bool(burden_quote) if is_main else True,
                    "evidence_quote": burden_quote,
                    "explain": "主要诊断通常应与住院主要医疗资源消耗相对应。",
                    "rule_ref": "《住院病案首页填写规范（暂行）》第10条",
                }
            )

            if is_main:
                status_ok = not _is_status_like(diag_text)
                checks.append(
                    {
                        "item": "主诊断不优先选择术后/既往状态",
                        "status": bool(status_ok),
                        "evidence_quote": "" if status_ok else diag_text,
                        "explain": "“术后状态/后状态”通常作为其他诊断记录。",
                        "rule_ref": "《住院病案首页填写规范（暂行）》第18、19条",
                    }
                )
            else:
                checks.append(
                    {
                        "item": "该条目可归入其他诊断",
                        "status": True,
                        "evidence_quote": quote or "",
                        "explain": "该条目作为并存病或状态记录，纳入其他诊断。",
                        "rule_ref": "《住院病案首页填写规范（暂行）》第18、19、20条",
                    }
                )
            return checks

        def _line_match(diag_text: str) -> Optional[Tuple[str, str, str, float, int]]:
            diag_key = self._diagnosis_canonical_key(diag_text)
            if not diag_key:
                return None

            narrative_terms = ("术中", "术后", "治疗", "复查", "给予", "每", "换药", "切除术", "引流术", "麻醉")
            max_quote_len = 42

            def _is_narrative_long(line: str) -> bool:
                compact = re.sub(r"\s+", "", line or "")
                return len(compact) > max_quote_len and any(t in compact for t in narrative_terms)

            # exact-ish match first: prefer concise diagnosis-item lines over long narratives
            sec_priority = {"出院诊断": 0, "入院诊断": 1, "初步诊断": 2, "门诊诊断": 3, "急诊诊断": 4}
            exact_candidates: List[Tuple[int, int, str, str, int]] = []
            for sec, line, line_no in block_lines:
                line_key = self._diagnosis_canonical_key(line)
                if not line_key:
                    continue
                if diag_key in line_key or line_key in diag_key:
                    extra_len = max(0, len(line_key) - len(diag_key))
                    exact_candidates.append((sec_priority.get(sec, 9), extra_len, sec, line, line_no))
            if exact_candidates:
                exact_candidates.sort(key=lambda x: (x[0], x[1], len(x[3])))
                _, _, sec, line, line_no = exact_candidates[0]

                # 强制降级规则：
                # 当命中句过长且包含治疗叙述词时，优先回退到“编号诊断行”（1./2./3.）
                if _is_narrative_long(line):
                    numbered_candidates: List[Tuple[int, int, str, str, int]] = []
                    for nsec, nline, nline_no in block_lines:
                        if not re.match(r"^\s*\d{1,2}[\.、\)]", nline):
                            continue
                        nkey = self._diagnosis_canonical_key(nline)
                        if not nkey:
                            continue
                        if diag_key in nkey or nkey in diag_key:
                            nextra = max(0, len(nkey) - len(diag_key))
                            numbered_candidates.append((sec_priority.get(nsec, 9), nextra, nsec, nline, nline_no))
                    if numbered_candidates:
                        numbered_candidates.sort(key=lambda x: (x[0], x[1], len(x[3])))
                        _, _, sec, line, line_no = numbered_candidates[0]
                        return sec, line, "exact_numbered", 0.93, line_no

                return sec, line, "exact", 0.93, line_no

            # fallback fuzzy by token overlap
            diag_tokens = [t for t in re.split(r"[\s,，;；、]+", diag_text) if len(t) >= 2]
            best: Optional[Tuple[str, str, str, float, int]] = None
            best_score = 0.0
            for sec, line, line_no in block_lines:
                if not line:
                    continue
                hit = 0
                for tk in diag_tokens:
                    if tk in line:
                        hit += 1
                if not diag_tokens:
                    continue
                score = hit / len(diag_tokens)
                if score > best_score and score >= 0.5:
                    best_score = score
                    best = (sec, line, "fuzzy", round(0.6 + 0.3 * score, 2), line_no)
            return best

        evidence: List[Dict[str, Any]] = []
        for dtype, diag_text in entries:
            matched = _line_match(diag_text)
            quote = matched[1] if matched else None
            support_quotes = _supporting_quotes(diag_text, quote)
            if dtype == "main":
                if support_quotes and main_proc_text:
                    logic = f"主诊断优先来自出院/入院诊断条目，并与主要治疗（{main_proc_text}）及病程记录相互印证。"
                elif support_quotes:
                    logic = "主诊断优先来自出院/入院诊断条目，并由病程/治疗记录提供支持。"
                elif quote:
                    logic = "主诊断来自诊断条目，当前证据以诊断原文为主。"
                else:
                    logic = "按首页规范优先取主要出院诊断；当前缺少可追溯原文证据。"
            else:
                logic = "作为其他诊断，来自出院（或初步）诊断条目，并做病历文本一致性校验。"

            if matched:
                sec, quote, mode, conf, line_no = matched
                reasoning_checks = _reasoning_checks(
                    diag_text, dtype, sec, quote, support_quotes
                )
                evidence.append(
                    {
                        "diagnosis_text": diag_text,
                        "diagnosis_type": dtype,
                        "quote": quote,
                        "section": sec,
                        "quote_location": f"{sec} 第{line_no}条",
                        "match_mode": mode,
                        "confidence": conf,
                        "selection_logic": logic,
                        "supporting_quotes": support_quotes,
                        "reasoning_checks": reasoning_checks,
                    }
                )
            else:
                reasoning_checks = _reasoning_checks(
                    diag_text, dtype, "unknown", None, support_quotes
                )
                evidence.append(
                    {
                        "diagnosis_text": diag_text,
                        "diagnosis_type": dtype,
                        "quote": None,
                        "section": "unknown",
                        "quote_location": "unknown",
                        "match_mode": "none",
                        "confidence": 0.0,
                        "selection_logic": logic,
                        "supporting_quotes": support_quotes,
                        "reasoning_checks": reasoning_checks,
                    }
                )

        # Candidate comparison for main diagnosis correction:
        # evaluate whether selected main diagnosis is supported more strongly
        # than competing diagnoses, instead of only trusting chart ordering.
        try:
            candidate_texts: List[str] = []
            if main:
                candidate_texts.append(main)
            if isinstance(others_raw, list):
                for o in others_raw:
                    oo = self._normalize_diag_text(o)
                    if oo and self._diagnosis_canonical_key(oo) not in {
                        self._diagnosis_canonical_key(x) for x in candidate_texts
                    }:
                        candidate_texts.append(oo)

            severity_terms = ["重症", "不稳定", "急性", "危重", "监护", "介入", "手术", "PCI", "造影"]
            candidate_rows: List[Dict[str, Any]] = []
            for cand in candidate_texts:
                matched = _line_match(cand)
                quote = matched[1] if matched else None
                section = matched[0] if matched else "unknown"
                quote_location = f"{matched[0]} 第{matched[4]}条" if matched else "unknown"
                support_quotes = _supporting_quotes(cand, quote)
                has_proc_support = False
                proc_support_quote = ""
                if main_proc_text:
                    ckey = self._diagnosis_canonical_key(cand)
                    if ckey and proc_key and (ckey[:4] in proc_key or proc_key[:4] in ckey):
                        has_proc_support = True
                        proc_support_quote = main_proc_text
                    else:
                        for sq in support_quotes:
                            if any(t in sq for t in ["手术", "介入", "支架", "造影", "治疗"]):
                                has_proc_support = True
                                proc_support_quote = sq
                                break

                has_burden_support = any(
                    any(term in sq for term in severity_terms) for sq in support_quotes
                )
                is_status = _is_status_like(cand)
                section_score = 2 if section in {"出院诊断", "入院诊断", "初步诊断"} else 0
                proc_score = 3 if has_proc_support else 0
                burden_score = 2 if has_burden_support else 0
                status_penalty = -3 if is_status else 0
                total_score = section_score + proc_score + burden_score + status_penalty

                reasons: List[str] = [f"来源章节：{section}"]
                if has_proc_support:
                    reasons.append("与主要治疗/手术方向一致")
                if has_burden_support:
                    reasons.append("存在病程严重程度或资源消耗佐证")
                if is_status:
                    reasons.append("疑似术后/既往状态，不宜优先为主诊断")

                reject_reasons: List[str] = []
                if not has_proc_support:
                    reject_reasons.append("缺少与主要治疗/手术的直接一致性证据")
                if not has_burden_support:
                    reject_reasons.append("缺少明显病情严重程度或资源消耗佐证")
                if is_status:
                    reject_reasons.append("存在“术后/后状态/既往”特征，应优先归入其他诊断")

                candidate_rows.append(
                    {
                        "diagnosis_text": cand,
                        "score": total_score,
                        "section": section,
                        "quote_location": quote_location,
                        "quote": quote,
                        "support_quote": proc_support_quote,
                        "reasons": reasons,
                        "reject_reasons": reject_reasons,
                    }
                )

            candidate_rows.sort(key=lambda x: x.get("score", 0), reverse=True)
            recommended = candidate_rows[0]["diagnosis_text"] if candidate_rows else ""
            selected_main = main or ""
            consistent = (
                self._diagnosis_canonical_key(recommended)
                == self._diagnosis_canonical_key(selected_main)
                if recommended and selected_main
                else True
            )
            clinician_main = clinician_main_text or selected_main
            differs_from_clinician = (
                self._diagnosis_canonical_key(recommended)
                != self._diagnosis_canonical_key(clinician_main)
                if recommended and clinician_main
                else False
            )
            recommended_row = next(
                (
                    row for row in candidate_rows
                    if self._diagnosis_canonical_key(row.get("diagnosis_text"))
                    == self._diagnosis_canonical_key(recommended)
                ),
                None,
            )
            recommendation_reasons: List[Dict[str, Any]] = []
            if isinstance(recommended_row, dict):
                support_quote = str(recommended_row.get("support_quote") or "").strip()
                main_quote = str(recommended_row.get("quote") or "").strip()
                for reason in recommended_row.get("reasons") or []:
                    if not isinstance(reason, str):
                        continue
                    recommendation_reasons.append(
                        {
                            "type": "support",
                            "reason": reason,
                            "evidence_quote": support_quote or main_quote,
                        }
                    )
                for reason in recommended_row.get("reject_reasons") or []:
                    if not isinstance(reason, str):
                        continue
                    recommendation_reasons.append(
                        {
                            "type": "risk",
                            "reason": reason,
                            "evidence_quote": main_quote,
                        }
                    )

            analysis = {
                "recommended_main_diagnosis": recommended,
                "selected_main_diagnosis": selected_main,
                "consistent_with_selection": bool(consistent),
                "summary": (
                    "当前主诊断与系统候选排序一致。"
                    if consistent
                    else "当前主诊断与系统候选排序不一致，建议人工复核并考虑纠偏。"
                ),
                "candidates": candidate_rows[:5],
            }

            def _manual_review_points() -> List[str]:
                points: List[str] = []
                if candidate_rows and len(candidate_rows) > 1:
                    gap = (candidate_rows[0].get("score") or 0) - (candidate_rows[1].get("score") or 0)
                    if gap <= 1:
                        points.append("前两位候选评分接近（<=1分），建议编码员人工复核主诊断。")
                if candidate_rows and not any(
                    any("资源消耗佐证" in r for r in (c.get("reasons") or [])) for c in candidate_rows[:1]
                ):
                    points.append("当前主诊断缺少明确资源消耗佐证，建议补充病程/监护/关键检查证据。")
                if not consistent and recommended:
                    points.append(f"系统候选排序更倾向“{recommended}”，建议复核是否需要纠偏。")
                return points

            coder_summary = (
                f"主诊断候选共{len(candidate_rows)}项，系统推荐“{recommended or '未知'}”，"
                f"当前填写“{selected_main or '未知'}”，一致性：{'一致' if consistent else '不一致'}。"
            )
            recommendation_summary = (
                f"医生填写主诊断为“{clinician_main or '未知'}”，系统推荐“{recommended or '未知'}”。"
                f"{'系统推荐更适合作为主要诊断。' if differs_from_clinician else '系统推荐与医生填写一致。'}"
            )

            for ev in evidence:
                if ev.get("diagnosis_type") == "main":
                    ev["candidate_analysis"] = analysis
                    ev["coder_summary"] = coder_summary
                    ev["clinician_main_diagnosis"] = clinician_main
                    ev["system_recommended_main_diagnosis"] = recommended
                    ev["recommendation_differs_from_clinician"] = bool(differs_from_clinician)
                    ev["recommendation_label"] = "更适合作为主要诊断"
                    ev["recommendation_reasons"] = recommendation_reasons
                    ev["recommendation_summary"] = recommendation_summary
                    ev["manual_review_points"] = _manual_review_points()
                    checks = ev.get("reasoning_checks")
                    if isinstance(checks, list):
                        checks.append(
                            {
                                "item": "与候选排序一致性校验",
                                "status": bool(consistent),
                                "evidence_quote": "",
                                "explain": (
                                    "系统基于章节来源、治疗/手术一致性、资源消耗佐证对候选诊断排序。"
                                ),
                                "rule_ref": "《住院病案首页填写规范（暂行）》第10、11、18、19条",
                            }
                        )
                    if not consistent and recommended:
                        ev["selection_logic"] = (
                            f"当前主诊断为“{selected_main}”，但综合病历证据更倾向“{recommended}”，"
                            "建议人工复核主诊断是否填写偏差。"
                        )
        except Exception:
            logger.exception("build diagnosis candidate analysis failed")

        # Build labeled raw evidence lines for frontend display/audit.
        try:
            key_to_section: Dict[str, str] = {}
            for sec, line, line_no in block_lines:
                k = self._diagnosis_canonical_key(line)
                if k and k not in key_to_section:
                    key_to_section[k] = f"{sec} 第{line_no}条"

            def _source_of_text(text: str) -> str:
                k = self._diagnosis_canonical_key(text)
                if k and k in key_to_section:
                    return key_to_section[k]
                t = str(text or "")
                if any(x in t for x in ("手术", "术中", "术后", "麻醉", "切除", "置入", "引流")):
                    return "手术/治疗记录"
                if any(x in t for x in ("病程", "复查", "检查", "检验", "治疗", "给予")):
                    return "病程/治疗记录"
                return "病历原文"

            for ev in evidence:
                raw_lines: List[Dict[str, str]] = []
                seen = set()

                def _push(text: Any, role: str) -> None:
                    s = str(text or "").strip()
                    if not s:
                        return
                    if "系统推荐：" in s:
                        return
                    if s in seen:
                        return
                    seen.add(s)
                    raw_lines.append(
                        {
                            "text": s,
                            "source": _source_of_text(s),
                            "role": role,
                        }
                    )

                _push(ev.get("quote"), "主证据")
                for sq in ev.get("supporting_quotes") or []:
                    _push(sq, "治疗佐证")

                checks = ev.get("reasoning_checks")
                if isinstance(checks, list):
                    for ck in checks:
                        if isinstance(ck, dict):
                            _push(ck.get("evidence_quote"), "判定佐证")

                ca = ev.get("candidate_analysis")
                if isinstance(ca, dict):
                    cands = ca.get("candidates")
                    if isinstance(cands, list):
                        for c in cands:
                            if isinstance(c, dict):
                                _push(c.get("quote"), "候选证据")
                                _push(c.get("support_quote"), "候选佐证")

                ev["raw_evidence_lines"] = raw_lines
        except Exception:
            logger.exception("build labeled raw evidence lines failed")
        return evidence

    def _apply_external_diagnosis_codes(
        self,
        diagnoses: Optional[Dict[str, Any]],
        coding_data: Optional[Dict[str, Any]],
        validation_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Merge external coding results in code-only mode.
        This method never overwrites diagnosis text fields.
        """
        diag = diagnoses if isinstance(diagnoses, dict) else {}
        data = coding_data if isinstance(coding_data, dict) else {}

        pd = data.get("principal_diagnosis")
        if isinstance(pd, dict):
            main_code = pd.get("code")
            if diag.get("discharge_main_diagnosis_text") and main_code:
                diag["discharge_main_icd"] = main_code
            if validation_info is not None and pd.get("confidence") is not None:
                validation_info["principal_diagnosis_confidence"] = pd.get("confidence")

        other_texts_raw = diag.get("discharge_other_diagnoses_texts")
        other_texts = other_texts_raw if isinstance(other_texts_raw, list) else []
        other_icds_raw = diag.get("discharge_other_icds")
        other_icds = list(other_icds_raw) if isinstance(other_icds_raw, list) else []
        if len(other_icds) < len(other_texts):
            other_icds.extend([None] * (len(other_texts) - len(other_icds)))
        elif len(other_icds) > len(other_texts):
            other_icds = other_icds[: len(other_texts)]

        sd_raw = data.get("secondary_diagnoses")
        sd_list = [item for item in sd_raw if isinstance(item, dict)] if isinstance(sd_raw, list) else []

        if other_texts and sd_list:
            remaining_by_key: Dict[str, List[Any]] = {}
            remaining_codes: List[Any] = []
            for item in sd_list:
                code = item.get("code")
                if not code:
                    continue
                remaining_codes.append(code)
                key = self._diagnosis_canonical_key(item.get("name"))
                if key:
                    remaining_by_key.setdefault(key, []).append(code)

            for idx, text in enumerate(other_texts):
                code = None
                key = self._diagnosis_canonical_key(text)
                if key and remaining_by_key.get(key):
                    code = remaining_by_key[key].pop(0)
                    try:
                        remaining_codes.remove(code)
                    except ValueError:
                        pass
                elif remaining_codes:
                    code = remaining_codes.pop(0)
                if code:
                    other_icds[idx] = code

        diag["discharge_other_icds"] = other_icds
        return diag

    async def _infer_admission_conditions(
        self, medical_text: str, diagnoses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        F4: 入院病情推理
        
        对每个出院诊断推理其入院病情代码（1-4）
        """
        if not isinstance(diagnoses, dict):
            logger.warning(
                "infer admission conditions received non-dict diagnoses, type=%s",
                type(diagnoses).__name__,
            )
            return {}

        # 构建诊断列表文本
        all_diagnoses = []
        
        main_diag = diagnoses.get("discharge_main_diagnosis_text")
        if main_diag:
            all_diagnoses.append(f"1. 主要诊断: {main_diag}")
        
        other_diags_raw = diagnoses.get("discharge_other_diagnoses_texts", [])
        other_diags = other_diags_raw if isinstance(other_diags_raw, list) else []
        if other_diags_raw and not isinstance(other_diags_raw, list):
            logger.warning(
                "discharge_other_diagnoses_texts is not list, type=%s",
                type(other_diags_raw).__name__,
            )
        if other_diags:
            for i, diag in enumerate(other_diags, start=2):
                all_diagnoses.append(f"{i}. 其他诊断: {diag}")
        
        if not all_diagnoses:
            logger.info("无出院诊断，跳过入院病情推理")
            return diagnoses
        
        diagnoses_text = "\n".join(all_diagnoses)
        
        # 调用 LLM 推理
        prompt = ADMISSION_CONDITION_PROMPT.format(
            medical_text=medical_text,
            diagnoses_text=diagnoses_text
        )
        
        try:
            response = await self.llm_client.generate(SYSTEM_PROMPT, prompt)
            result = self._parse_json_response(response)
            
            results_list = result.get("results") if isinstance(result, dict) else None
            if isinstance(results_list, list):
                # 提取主诊断的入院病情
                for item in results_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("diagnosis") == main_diag or "主要诊断" in item.get("diagnosis", ""):
                        diagnoses["admission_condition"] = str(item.get("admission_condition", ""))
                        diagnoses["admission_condition_reasoning"] = item.get("reasoning", "")
                        break
                
                # 可选：存储所有诊断的入院病情推理结果
                diagnoses["_admission_condition_details"] = results_list
                diagnoses["admission_condition_details"] = results_list
                logger.info(f"入院病情推理完成，共处理 {len(results_list)} 个诊断")
            else:
                logger.warning("入院病情推理结果解析失败")
                
        except Exception as e:
            logger.error(f"入院病情推理失败: {e}")
        
        return diagnoses

    def _normalize_main_diagnosis_llm_payload(
        self,
        result: Optional[Dict[str, Any]],
        clinician_main: str,
        fallback_main: str,
        system_other_diagnoses: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(result, dict):
            return None

        recommended = str(result.get("llm_recommended_main_diagnosis") or "").strip()
        if not recommended:
            return None

        source_other_index: Optional[int] = None
        recommendation_action = "keep"
        recommendation_source = "none"
        preferred_other, preferred_idx = self._pick_preferred_main_from_others(
            recommended=recommended,
            clinician_main=clinician_main or fallback_main,
            other_diagnoses=system_other_diagnoses or [],
        )
        if preferred_other:
            recommended = preferred_other
            source_other_index = preferred_idx + 1 if preferred_idx >= 0 else None
            recommendation_action = "promote_existing"
            recommendation_source = "other_diagnosis"

        clinician_key = self._diagnosis_canonical_key(clinician_main or fallback_main)
        recommended_key = self._diagnosis_canonical_key(recommended)
        consistent = bool(clinician_key and recommended_key and clinician_key == recommended_key)
        if not consistent and recommendation_action == "keep":
            recommendation_action = "refine_current"
            recommendation_source = "llm_refinement"

        confidence_raw = result.get("confidence")
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        key_evidence_raw = result.get("key_evidence")
        key_evidence: List[Dict[str, str]] = []
        evidence_seen = set()
        if isinstance(key_evidence_raw, list):
            for item in key_evidence_raw:
                if not isinstance(item, dict):
                    continue
                quote = str(item.get("quote") or "").strip()
                if not quote:
                    continue
                quote_key = self._diagnosis_canonical_key(quote)
                if quote_key and quote_key in evidence_seen:
                    continue
                evidence_seen.add(quote_key)
                key_evidence.append(
                    {
                        "quote": quote,
                        "source": str(item.get("source") or "病历原文").strip() or "病历原文",
                        "why_it_supports": str(item.get("why_it_supports") or "").strip()
                        or "该证据支持当前主诊断推荐。",
                    }
                )
                if len(key_evidence) >= 3:
                    break

        conclusion = str(result.get("conclusion") or "").strip()
        if not conclusion:
            conclusion = (
                f"医生填写主诊断“{clinician_main or fallback_main or '未知'}”，LLM 推荐“{recommended}”，"
                f"{'两者一致。' if consistent else '建议以 LLM 推荐作为主诊断复核重点。'}"
            )
        reasoning_summary = str(result.get("reasoning_summary") or "").strip()
        if not reasoning_summary:
            reasoning_summary = "LLM 已结合候选诊断、关键治疗及病程证据完成主诊断语义推理。"

        recommendation_summary = str(result.get("recommendation_summary") or "").strip()
        if not recommendation_summary and not consistent:
            if recommendation_action == "promote_existing" and source_other_index:
                recommendation_summary = (
                    f"建议改为现有诊断：{recommended}（来自其他诊断第{source_other_index}条）。"
                )
            elif recommendation_action == "promote_existing":
                recommendation_summary = f"建议改为现有诊断：{recommended}。"
            else:
                recommendation_summary = f"建议细化主诊断为：{recommended}。"

        return {
            "clinician_main_diagnosis": clinician_main or fallback_main,
            "llm_recommended_main_diagnosis": recommended,
            "is_consistent_with_clinician": bool(consistent),
            "recommended_main_diagnosis_action": recommendation_action,
            "recommended_main_diagnosis_source": recommendation_source,
            "recommended_main_diagnosis_source_other_index": source_other_index,
            "recommendation_summary": recommendation_summary,
            "confidence": round(confidence, 2),
            "conclusion": conclusion,
            "key_evidence": key_evidence,
            "reasoning_summary": reasoning_summary,
        }

    def _pick_preferred_main_from_others(
        self,
        recommended: str,
        clinician_main: str,
        other_diagnoses: List[str],
    ) -> Tuple[str, int]:
        rec_key = self._diagnosis_canonical_key(recommended)
        clinician_key = self._diagnosis_canonical_key(clinician_main)
        if not rec_key or not isinstance(other_diagnoses, list):
            return "", -1

        acute_terms = ("不稳定", "急性", "危重", "重症", "梗死", "出血", "衰竭")
        candidates: List[Tuple[int, float, str, int]] = []
        for idx, raw in enumerate(other_diagnoses):
            text = self._normalize_diag_text(raw)
            key = self._diagnosis_canonical_key(text)
            if not text or not key:
                continue
            if key == clinician_key:
                continue
            if key == rec_key or key in rec_key or rec_key in key:
                score = 4
                if clinician_key and key != clinician_key:
                    score += 3
                if any(term in text for term in acute_terms):
                    score += 1
                candidates.append((score, len(key) / 100.0, text, idx))

        if not candidates:
            return "", -1
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = candidates[0]
        return best[2], best[3]

    def _normalize_finding_severity(
        self,
        finding_type: str,
        severity: str,
        clinician_text: str,
        llm_recommendation: str,
    ) -> str:
        current = str(severity or "medium").strip().lower()
        if current not in {"high", "medium", "low"}:
            current = "medium"

        if finding_type == "diagnosis_inappropriate":
            if (
                self._diagnosis_canonical_key(clinician_text)
                and self._diagnosis_canonical_key(llm_recommendation)
                and self._diagnosis_canonical_key(clinician_text)
                != self._diagnosis_canonical_key(llm_recommendation)
            ):
                return "high"
            if current == "low":
                return "medium"
        elif finding_type in {"diagnosis_missing", "procedure_missing"} and current == "low":
            return "medium"
        return current

    def _build_top_alert(
        self, findings: List[Dict[str, Any]], counts: Dict[str, int], summary: str
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(findings, list) or not findings:
            return None

        severity_weight = {"high": 3, "medium": 2, "low": 1}
        type_weight = {
            "diagnosis_inappropriate": 4,
            "diagnosis_missing": 3,
            "procedure_missing": 2,
            "diagnosis_insufficient_evidence": 1,
        }
        top = sorted(
            findings,
            key=lambda item: (
                severity_weight.get(str(item.get("severity") or "").lower(), 0),
                type_weight.get(str(item.get("type") or "").lower(), 0),
            ),
            reverse=True,
        )[0]
        alert_type = str(top.get("type") or "").strip().lower()
        if not alert_type:
            return None
        alert_severity = str(top.get("severity") or "medium").strip().lower()
        if alert_severity not in {"high", "medium", "low"}:
            alert_severity = "medium"
        same_type_count = max(
            1, int(counts.get(alert_type, 0) or 0) or sum(1 for x in findings if x.get("type") == alert_type)
        )
        alert_summary = (
            str(top.get("llm_recommendation") or "").strip()
            or str(top.get("reason") or "").strip()
            or str(summary or "").strip()
            or "建议人工复核。"
        )
        return {
            "type": alert_type,
            "severity": alert_severity,
            "summary": alert_summary,
            "count": same_type_count,
        }

    def _extract_clinician_procedures_for_audit(
        self, medical_text: str, max_items: int = 12
    ) -> List[str]:
        if not medical_text:
            return []

        text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.strip() for ln in text.split("\n") if ln and ln.strip()]
        candidates: List[str] = []
        pattern = re.compile(
            r"(?:手术(?:及操作)?(?:名称)?|主要手术|手术操作|手术经过|操作)\s*[:：]\s*(.+)$",
            re.IGNORECASE,
        )
        numbered_pat = re.compile(r"^\s*\d{1,2}[\.、\)]\s*(.+)$")
        surgical_hint = ("术", "操作", "介入", "置入", "切除", "造影", "消融", "缝合")

        for line in lines:
            m = pattern.search(line)
            value = ""
            if m:
                value = (m.group(1) or "").strip()
            else:
                n = numbered_pat.match(line)
                if n:
                    maybe = (n.group(1) or "").strip()
                    if any(h in maybe for h in surgical_hint):
                        value = maybe
            if not value:
                continue
            for part in self._split_procedure_candidates(value):
                if part:
                    candidates.append(part)
                if len(candidates) >= max_items:
                    break
            if len(candidates) >= max_items:
                break

        deduped: List[str] = []
        seen = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:max_items]

    def _normalize_coding_audit_llm_payload(
        self, result: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(result, dict):
            return None

        allowed_types = {
            "diagnosis_missing",
            "procedure_missing",
            "diagnosis_inappropriate",
            "diagnosis_insufficient_evidence",
        }
        allowed_severity = {"high", "medium", "low"}
        findings_raw = result.get("findings")
        findings: List[Dict[str, Any]] = []
        finding_keys = set()
        if isinstance(findings_raw, list):
            for item in findings_raw:
                if not isinstance(item, dict):
                    continue
                f_type = str(item.get("type") or "").strip().lower()
                if f_type not in allowed_types:
                    continue
                severity = str(item.get("severity") or "medium").strip().lower()
                clinician_text = str(item.get("clinician_text") or "").strip()
                llm_recommendation = str(item.get("llm_recommendation") or "").strip()
                severity = self._normalize_finding_severity(
                    finding_type=f_type,
                    severity=severity,
                    clinician_text=clinician_text,
                    llm_recommendation=llm_recommendation,
                )
                if severity not in allowed_severity:
                    severity = "medium"
                finding_key = (
                    f_type,
                    self._diagnosis_canonical_key(clinician_text),
                    self._diagnosis_canonical_key(llm_recommendation),
                )
                if finding_key in finding_keys:
                    continue
                finding_keys.add(finding_key)
                evidence_rows: List[Dict[str, str]] = []
                raw_evidence = item.get("evidence")
                if isinstance(raw_evidence, list):
                    for ev in raw_evidence:
                        if not isinstance(ev, dict):
                            continue
                        quote = str(ev.get("quote") or "").strip()
                        if not quote:
                            continue
                        evidence_rows.append(
                            {
                                "quote": quote,
                                "source": str(ev.get("source") or "病历原文").strip() or "病历原文",
                                "why_it_supports": str(ev.get("why_it_supports") or "").strip()
                                or "该证据支持当前审核结论。",
                            }
                        )
                        if len(evidence_rows) >= 2:
                            break
                findings.append(
                    {
                        "type": f_type,
                        "severity": severity,
                        "clinician_text": clinician_text,
                        "llm_recommendation": llm_recommendation,
                        "reason": str(item.get("reason") or "").strip(),
                        "evidence": evidence_rows,
                    }
                )
                if len(findings) >= 6:
                    break

        counts_result = result.get("counts")
        counts: Dict[str, int] = {
            "diagnosis_missing": 0,
            "procedure_missing": 0,
            "diagnosis_inappropriate": 0,
            "diagnosis_insufficient_evidence": 0,
        }
        if isinstance(counts_result, dict):
            for key in counts:
                try:
                    counts[key] = max(0, int(counts_result.get(key, 0) or 0))
                except (TypeError, ValueError):
                    counts[key] = 0
        else:
            for item in findings:
                f_type = item.get("type")
                if f_type in counts:
                    counts[f_type] += 1

        confidence_raw = result.get("confidence")
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        summary = str(result.get("summary") or "").strip()
        has_structured_payload = isinstance(result.get("counts"), dict) or isinstance(
            result.get("findings"), list
        )
        if not summary and not has_structured_payload:
            return None
        if not summary:
            total_issues = sum(counts.values())
            if total_issues:
                summary = f"共识别{total_issues}项编码审核风险，建议人工复核重点条目。"
            else:
                summary = "当前未识别到明确编码审核风险。"

        top_alert = self._build_top_alert(findings=findings, counts=counts, summary=summary)

        return {
            "version": str(result.get("version") or "v1"),
            "summary": summary,
            "confidence": round(confidence, 2),
            "counts": counts,
            "findings": findings,
            "top_alert": top_alert,
        }

    async def _build_main_and_audit_llm_evidence(
        self,
        medical_text: str,
        diagnoses: Optional[Dict[str, Any]],
        procedures: Optional[Dict[str, Any]],
        clinician_main_diagnosis: Optional[str] = None,
        main_diagnosis_llm: Optional[Dict[str, Any]] = None,
        context_strategy: Optional[str] = None,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        if not self._use_llm or not self.llm_client:
            return {"main_diagnosis_llm": None, "coding_audit_llm": None}
        if not isinstance(diagnoses, dict):
            return {"main_diagnosis_llm": None, "coding_audit_llm": None}

        system_main = str(diagnoses.get("discharge_main_diagnosis_text") or "").strip()
        system_others_raw = diagnoses.get("discharge_other_diagnoses_texts")
        system_others = (
            [str(x).strip() for x in system_others_raw if str(x).strip()]
            if isinstance(system_others_raw, list)
            else []
        )
        system_diagnoses = [x for x in [system_main, *system_others] if x]
        if not system_diagnoses:
            return {"main_diagnosis_llm": None, "coding_audit_llm": None}

        clinician_diagnoses = self._extract_discharge_diagnoses_from_text(medical_text or "")
        if not clinician_diagnoses:
            clinician_diagnoses = list(system_diagnoses)
        clinician_main = str(clinician_main_diagnosis or "").strip()
        if not clinician_main:
            clinician_main = clinician_diagnoses[0] if clinician_diagnoses else system_main

        system_main_proc = ""
        system_other_procs: List[str] = []
        if isinstance(procedures, dict):
            system_main_proc = str(procedures.get("main_procedure_text") or "").strip()
            other = procedures.get("other_procedures_texts")
            if isinstance(other, list):
                system_other_procs = [str(x).strip() for x in other if str(x).strip()]
        system_procedures = [x for x in [system_main_proc, *system_other_procs] if x]

        clinician_procedures = self._extract_clinician_procedures_for_audit(medical_text or "")
        if not clinician_procedures:
            clinician_procedures = list(system_procedures)

        candidate_diagnoses: List[str] = []
        for item in system_diagnoses:
            if item and item not in candidate_diagnoses:
                candidate_diagnoses.append(item)

        llm_recommended_main = ""
        if isinstance(main_diagnosis_llm, dict):
            llm_recommended_main = str(
                main_diagnosis_llm.get("llm_recommended_main_diagnosis") or ""
            ).strip()

        excerpt = self._select_context_text(
            medical_text or "",
            context_strategy,
            max_chars=3600,
            default_mode="retrieval",
        )

        prompt = MAIN_AND_AUDIT_LLM_EVIDENCE_PROMPT.format(
            clinician_main_diagnosis=clinician_main or "未知",
            candidate_diagnoses="；".join(candidate_diagnoses[:10]) or "未提取到",
            main_procedure_text=system_main_proc or "未提取到",
            clinician_diagnoses="；".join(clinician_diagnoses[:10]) or "未提取到",
            clinician_procedures="；".join(clinician_procedures[:10]) or "未提取到",
            system_diagnoses="；".join(system_diagnoses[:10]) or "未提取到",
            system_procedures="；".join(system_procedures[:10]) or "未提取到",
            llm_recommended_main=llm_recommended_main or "未提取到",
            medical_excerpt=excerpt or "（无病历片段）",
        )
        result = await self._extract_json(prompt, max_tokens=1700)
        if not isinstance(result, dict):
            return {"main_diagnosis_llm": None, "coding_audit_llm": None}

        main_result = result.get("main_diagnosis_llm")
        audit_result = result.get("coding_audit_llm")

        # 兼容旧 prompt 结构（扁平主诊断解释 / 扁平审核输出）
        if not isinstance(main_result, dict):
            if any(
                key in result
                for key in (
                    "llm_recommended_main_diagnosis",
                    "key_evidence",
                    "reasoning_summary",
                    "conclusion",
                )
            ):
                main_result = result
        if not isinstance(audit_result, dict):
            if any(key in result for key in ("findings", "counts", "summary")):
                audit_result = result

        normalized_main = self._normalize_main_diagnosis_llm_payload(
            main_result if isinstance(main_result, dict) else None,
            clinician_main=clinician_main,
            fallback_main=system_main,
            system_other_diagnoses=system_others,
        )
        normalized_audit = self._normalize_coding_audit_llm_payload(
            audit_result if isinstance(audit_result, dict) else None
        )

        return {
            "main_diagnosis_llm": normalized_main,
            "coding_audit_llm": normalized_audit,
        }

    async def _build_main_diagnosis_llm_evidence(
        self,
        medical_text: str,
        diagnoses: Optional[Dict[str, Any]],
        procedures: Optional[Dict[str, Any]],
        clinician_main_diagnosis: Optional[str] = None,
        context_strategy: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """兼容壳：内部复用单次推理方法。"""
        merged = await self._build_main_and_audit_llm_evidence(
            medical_text=medical_text,
            diagnoses=diagnoses,
            procedures=procedures,
            clinician_main_diagnosis=clinician_main_diagnosis,
            context_strategy=context_strategy,
        )
        result = merged.get("main_diagnosis_llm")
        return result if isinstance(result, dict) else None

    async def _build_coding_audit_llm(
        self,
        medical_text: str,
        diagnoses: Optional[Dict[str, Any]],
        procedures: Optional[Dict[str, Any]],
        clinician_main_diagnosis: Optional[str] = None,
        main_diagnosis_llm: Optional[Dict[str, Any]] = None,
        context_strategy: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """兼容壳：内部复用单次推理方法。"""
        merged = await self._build_main_and_audit_llm_evidence(
            medical_text=medical_text,
            diagnoses=diagnoses,
            procedures=procedures,
            clinician_main_diagnosis=clinician_main_diagnosis,
            main_diagnosis_llm=main_diagnosis_llm,
            context_strategy=context_strategy,
        )
        result = merged.get("coding_audit_llm")
        return result if isinstance(result, dict) else None

    async def _suggest_diagnosis_codes(self, diagnoses: Dict[str, Any]) -> Dict[str, Any]:
        """
        F5: 为诊断推荐 ICD-10 编码
        """
        from .icd_coding_service import get_icd_coding_service
        icd_service = get_icd_coding_service()
        
        main_diag = diagnoses.get("discharge_main_diagnosis_text")
        if main_diag:
            suggestions = await icd_service.suggest_diagnosis_codes(main_diag, top_k=3)
            if suggestions:
                diagnoses["discharge_main_icd_suggestions"] = suggestions
                # 自动填入最高置信度的编码
                diagnoses["discharge_main_icd"] = suggestions[0].get("code")
                logger.info(f"主诊断编码推荐: {main_diag} -> {suggestions[0].get('code')}")
        
        # 其他诊断编码推荐
        other_diags = diagnoses.get("discharge_other_diagnoses_texts", [])
        if other_diags:
            other_icd_suggestions = []
            other_icds = []
            for diag in other_diags:
                if diag:
                    suggestions = await icd_service.suggest_diagnosis_codes(diag, top_k=1)
                    if suggestions:
                        other_icd_suggestions.append({
                            "diagnosis": diag,
                            "suggestions": suggestions
                        })
                        other_icds.append(suggestions[0].get("code"))
                    else:
                        other_icds.append(None)
                else:
                    other_icds.append(None)
            
            diagnoses["discharge_other_icd_suggestions"] = other_icd_suggestions
            diagnoses["discharge_other_icds"] = other_icds
        
        return diagnoses

    async def _suggest_procedure_codes(self, procedures: Dict[str, Any]) -> Dict[str, Any]:
        """为手术名称推荐 ICD-9 编码"""
        from .icd_coding_service import get_icd_coding_service
        icd_service = get_icd_coding_service()

        procedures = self._normalize_procedures_structure(procedures)
        main_proc = procedures.get("main_procedure_text")
        split_parts = [main_proc] + (procedures.get("other_procedures_texts") or [])
        coding_target = main_proc

        # 复合手术优先选择治疗性操作作为编码目标，避免只编码“造影/检查”
        if isinstance(split_parts, list) and split_parts:
            coding_target = self._select_primary_procedure_candidate(split_parts)

        if coding_target:
            suggestions = await icd_service.suggest_procedure_codes(coding_target, top_k=3)
            if suggestions:
                procedures["main_procedure_code_suggestions"] = suggestions
                procedures["main_procedure_code"] = suggestions[0].get("code")
                logger.info(
                    "主手术编码推荐: display='%s', coding_target='%s' -> %s",
                    main_proc,
                    coding_target,
                    suggestions[0].get("code"),
                )
        return procedures

    @staticmethod
    def _select_primary_procedure_candidate(parts: List[str]) -> str:
        """
        Pick the most treatment-oriented procedure from split parts for coding.
        """
        if not parts:
            return ""

        # 参照病案首页主手术选择原则：
        # 治疗性操作 > 介入治疗 > 诊断性检查
        core_therapy_keywords = (
            "支架",
            "置入",
            "植入",
            "切除",
            "成形",
            "搭桥",
            "修补",
            "吻合",
            "置换",
            "重建",
            "消融",
            "切开",
            "缝合",
        )
        interventional_keywords = (
            "pci",
            "ptca",
            "介入",
            "球囊",
            "扩张",
        )
        diagnostic_keywords = ("造影", "检查", "探查", "镜检", "评估", "活检", "穿刺")
        uncertain_markers = ("必要时", "拟", "可能", "待")

        best_part = parts[0]
        best_score = -10**9
        for idx, part in enumerate(parts):
            text = str(part or "").strip()
            if not text:
                continue
            lower_text = text.lower()
            score = 0
            if any(k in text for k in core_therapy_keywords):
                score += 4
            if any(k in lower_text for k in interventional_keywords):
                score += 3
            if any(k in text for k in diagnostic_keywords):
                score -= 3
            if any(m in text for m in uncertain_markers):
                score -= 0.5
            # Prefer later item on tie (often definitive treatment follows diagnostic step)
            score += idx * 0.01
            if score > best_score:
                best_score = score
                best_part = text

        return best_part

    @staticmethod
    def _split_compound_procedures(procedures: Dict[str, Any]) -> Dict[str, Any]:
        """拆分复合手术名称为独立条目，保留原始主手术文本。"""
        if not isinstance(procedures, dict):
            logger.warning("split compound procedures received non-dict input, type=%s", type(procedures).__name__)
            return {}

        main_text = procedures.get("main_procedure_text", "") or ""
        if not main_text:
            return procedures

        # 检测是否包含分隔符（+、＋、顿号、逗号、分号）
        parts = re.split(r"[+＋、，,；;]", main_text)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            return procedures

        # 保留原始主手术文本，拆分结果用于“其他手术”与编码目标
        procedures["_procedure_split_parts"] = parts
        existing_others = procedures.get("other_procedures_texts") or []
        merged = parts[1:] + existing_others
        deduped = []
        seen = set()
        for t in merged:
            s = str(t or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            deduped.append(s)
        procedures["other_procedures_texts"] = deduped
        logger.info("拆分复合手术(保留主文本): '%s' -> parts=%s", main_text, parts)
        return procedures

    @staticmethod
    def _normalize_procedure_text(text: Any) -> str:
        if text is None:
            return ""
        s = str(text).strip()
        s = s.replace("＋", "+")
        s = re.sub(r"^\s*(拟行|计划行|拟于|行|拟)\s*", "", s)
        s = re.sub(r"^\s*必要时\s*", "", s)
        s = re.sub(r"^\s*\d{1,2}[\.、\)]\s*", "", s)
        return s.strip()

    @classmethod
    def _split_procedure_candidates(cls, text: Any) -> List[str]:
        cleaned = cls._normalize_procedure_text(text)
        if not cleaned:
            return []
        parts = re.split(r"[+＋、，,；;]|(?:\s*(?:及|并|和|联合)\s*)", cleaned)
        out: List[str] = []
        seen = set()
        for p in parts:
            item = cls._normalize_procedure_text(p)
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _normalize_other_medical_info_structure(other_medical: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """规范化“其他医疗信息”，兼容扁平字段与嵌套字段。"""
        out = dict(other_medical) if isinstance(other_medical, dict) else {}

        def _to_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return int(value)
            try:
                text = str(value).strip()
                if not text:
                    return None
                return int(float(text))
            except Exception:
                return None

        pathology = out.get("pathology_diagnosis")
        if isinstance(pathology, dict):
            out["pathology_text"] = out.get("pathology_text") or pathology.get("text")
            out["pathology_icd"] = out.get("pathology_icd") or pathology.get("icd10") or pathology.get("code")
            out["pathology_no"] = out.get("pathology_no") or pathology.get("pathology_no")

        icu_stay = out.get("icu_stay")
        if isinstance(icu_stay, dict):
            out["icu_type"] = out.get("icu_type") or icu_stay.get("icu_type")
            out["icu_enter_time"] = out.get("icu_enter_time") or icu_stay.get("enter_time")
            out["icu_leave_time"] = out.get("icu_leave_time") or icu_stay.get("leave_time")
            out["icu_transfer_status"] = out.get("icu_transfer_status") or icu_stay.get("transfer_status")

        before = out.get("coma_before_admission") if isinstance(out.get("coma_before_admission"), dict) else {}
        after = out.get("coma_after_admission") if isinstance(out.get("coma_after_admission"), dict) else {}

        before_days = _to_int(before.get("days"))
        before_hours = _to_int(before.get("hours"))
        before_minutes = _to_int(before.get("minutes"))
        after_days = _to_int(after.get("days"))
        after_hours = _to_int(after.get("hours"))
        after_minutes = _to_int(after.get("minutes"))

        if before_days is None:
            before_days = _to_int(out.get("brain_injury_before_admission_days"))
        if before_hours is None:
            before_hours = _to_int(out.get("brain_injury_before_admission_hours"))
        if before_minutes is None:
            before_minutes = _to_int(out.get("brain_injury_before_admission_minutes"))
        if after_days is None:
            after_days = _to_int(out.get("brain_injury_after_admission_days"))
        if after_hours is None:
            after_hours = _to_int(out.get("brain_injury_after_admission_hours"))
        if after_minutes is None:
            after_minutes = _to_int(out.get("brain_injury_after_admission_minutes"))

        out["brain_injury_before_admission_days"] = before_days
        out["brain_injury_before_admission_hours"] = before_hours
        out["brain_injury_before_admission_minutes"] = before_minutes
        out["brain_injury_after_admission_days"] = after_days
        out["brain_injury_after_admission_hours"] = after_hours
        out["brain_injury_after_admission_minutes"] = after_minutes

        if out.get("coma_before_admission") is None and (
            before_days is not None or before_hours is not None or before_minutes is not None
        ):
            out["coma_before_admission"] = {
                "days": before_days or 0,
                "hours": before_hours or 0,
                "minutes": before_minutes or 0,
            }
        if out.get("coma_after_admission") is None and (
            after_days is not None or after_hours is not None or after_minutes is not None
        ):
            out["coma_after_admission"] = {
                "days": after_days or 0,
                "hours": after_hours or 0,
                "minutes": after_minutes or 0,
            }

        return out

    @staticmethod
    def _coerce_optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None

    @staticmethod
    def _append_validation_warning(validation_info: Dict[str, Any], message: str) -> None:
        warnings = validation_info.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        if message not in warnings:
            warnings.append(message)
        validation_info["warnings"] = warnings

    @staticmethod
    def _infer_ventilation_hours_from_text(medical_text: str) -> Tuple[Optional[float], bool]:
        text = str(medical_text or "")
        if not text.strip():
            return None, False

        keyword_patterns = [
            r"呼吸机",
            r"机械通气",
            r"辅助通气",
            r"无创通气",
            r"有创机械通气",
        ]
        has_evidence = any(re.search(pattern, text, re.IGNORECASE) for pattern in keyword_patterns)

        explicit_patterns = [
            r"呼吸机(?:辅助通气|通气|使用时间)?[：: ]*([0-9]+(?:\.[0-9]+)?)\s*(?:小时|h|H)",
            r"机械通气(?:时间|共|约)?[：: ]*([0-9]+(?:\.[0-9]+)?)\s*(?:小时|h|H)",
            r"(?:无创|有创)?(?:呼吸机)?辅助通气[：: ]*([0-9]+(?:\.[0-9]+)?)\s*(?:小时|h|H)",
            r"(?:无创|有创)?机械通气[：: ]*([0-9]+(?:\.[0-9]+)?)\s*(?:小时|h|H)",
            r"呼吸机使用时间[：: ]*([0-9]+(?:\.[0-9]+)?)\s*(?:小时|h|H)",
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1)), True
                except Exception:
                    pass

        day_hour_patterns = [
            r"(?:呼吸机|机械通气|辅助通气)[^。；，\n]{0,20}?([0-9]+)天([0-9]+)小时",
            r"([0-9]+)天([0-9]+)小时[^。；，\n]{0,20}?(?:呼吸机|机械通气|辅助通气)",
        ]
        for pattern in day_hour_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    days = float(match.group(1))
                    hours = float(match.group(2))
                    return days * 24 + hours, True
                except Exception:
                    pass

        return None, has_evidence

    def _apply_ventilation_hours_quality_rules(
        self,
        medical_text: str,
        other_medical: Optional[Dict[str, Any]],
        validation_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = self._normalize_other_medical_info_structure(other_medical)
        current_hours = self._coerce_optional_float(normalized.get("ventilation_hours"))
        inferred_hours, has_evidence = self._infer_ventilation_hours_from_text(medical_text)

        if current_hours is not None:
            normalized["ventilation_hours"] = current_hours
            validation_info["ventilation_hours_status"] = "provided"
            return normalized

        raw_value = normalized.get("ventilation_hours")
        if raw_value not in (None, "", []):
            self._append_validation_warning(validation_info, "呼吸机使用时间格式异常，已进入人工复核")
            validation_info["ventilation_hours_status"] = "invalid"
            validation_info["ventilation_hours_manual_review"] = True
            normalized["ventilation_hours"] = None
            return normalized

        if inferred_hours is not None:
            normalized["ventilation_hours"] = inferred_hours
            validation_info["ventilation_hours_status"] = "inferred"
            validation_info["ventilation_hours_inferred"] = inferred_hours
            return normalized

        if has_evidence:
            self._append_validation_warning(validation_info, "病历存在机械通气/呼吸机辅助通气证据，但未抽取出呼吸机使用时间")
            validation_info["ventilation_hours_status"] = "missing_with_evidence"
            validation_info["ventilation_hours_manual_review"] = True
        else:
            validation_info.setdefault("ventilation_hours_status", "not_applicable")

        return normalized

    def _normalize_procedures_structure(self, procedures: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize procedure structure with guideline-style selection:
        - Split compound procedures
        - Select exactly one main procedure
        - Keep the rest in other_procedures_texts
        """
        proc = dict(procedures) if isinstance(procedures, dict) else {}
        main_text = proc.get("main_procedure_text")
        other_raw = proc.get("other_procedures_texts")
        other_list = other_raw if isinstance(other_raw, list) else []

        candidates: List[str] = []
        seen = set()
        for text in self._split_procedure_candidates(main_text):
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(text)
        for other in other_list:
            for text in self._split_procedure_candidates(other):
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(text)

        if not candidates:
            proc["main_procedure_text"] = self._normalize_procedure_text(main_text) or None
            proc["other_procedures_texts"] = []
            return proc

        selected_main = self._select_primary_procedure_candidate(candidates)
        selected_main = self._normalize_procedure_text(selected_main)
        if not selected_main:
            selected_main = candidates[0]

        others = [c for c in candidates if c.lower() != selected_main.lower()]
        proc["main_procedure_text"] = selected_main
        proc["other_procedures_texts"] = others
        return proc

    async def _load_demo_frontpage(self) -> FrontPageDraft:
        """从 demo JSON 文件加载 FrontPageDraft（回退方案）"""
        if not self.demo_data_path.exists():
            raise FileNotFoundError(
                f"示例数据文件不存在: {self.demo_data_path}，请确认 frontpage_demo_case.json 是否存在。"
            )

        with self.demo_data_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        raw_frontpage = payload.get("frontpage") or {}
        if not raw_frontpage:
            raise ValueError("示例数据中缺少 frontpage 字段")

        # 兼容 demo JSON 中的 diagnosis_and_procedures 结构
        diag_proc = raw_frontpage.get("diagnosis_and_procedures") or {}

        # 诊断部分
        ed = diag_proc.get("ed_diagnosis") or []
        ed_texts = [item.get("text", "") for item in ed if isinstance(item, dict)]

        main_diag = diag_proc.get("discharge_main_diagnosis") or {}
        other_diags = diag_proc.get("discharge_other_diagnoses") or []
        other_texts = [
            item.get("text", "") for item in other_diags if isinstance(item, dict)
        ]

        diagnoses = {
            "ed_diagnosis_texts": ed_texts,
            "discharge_main_diagnosis_text": main_diag.get("text"),
            "discharge_other_diagnoses_texts": other_texts,
            "admission_condition": main_diag.get("admission_condition"),
        }

        # 手术部分
        main_proc = diag_proc.get("main_procedure") or {}
        procedures = {
            "main_procedure_text": main_proc.get("name"),
            "main_procedure_date": main_proc.get("date"),
            "main_procedure_level": main_proc.get("level"),
            "surgeon_name": main_proc.get("surgeon_name"),
            "surgeon_code": main_proc.get("surgeon_code"),
            "assistant1_name": main_proc.get("assistant1_name"),
            "assistant1_code": main_proc.get("assistant1_code"),
            "assistant2_name": main_proc.get("assistant2_name"),
            "assistant2_code": main_proc.get("assistant2_code"),
            "anesthesia_method": main_proc.get("anesthesia_method"),
            "anesthetist_name": main_proc.get("anesthetist_name"),
            "anesthetist_code": main_proc.get("anesthetist_code"),
            "incision_healing_grade": main_proc.get("incision_healing_grade"),
        }

        other_medical = self._normalize_other_medical_info_structure(
            raw_frontpage.get("other_medical_info")
        )

        frontpage_data = {
            **raw_frontpage,
            "diagnoses": diagnoses,
            "procedures": procedures,
            "other_medical_info": other_medical,
        }

        return FrontPageDraft.model_validate(frontpage_data)


# 提供单例风格的访问方式
default_frontpage_service = FrontPageExtractionService()
