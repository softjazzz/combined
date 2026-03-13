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
import logging
import asyncio
import re

from pydantic import ValidationError

from ..schemas.frontpage import FrontPageDraft
from ..core.settings import get_settings
from ..core.http import safe_post_json

logger = logging.getLogger(__name__)


class FrontPageLLMClient:
    """病案首页抽取专用 LLM 客户端"""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config:
            self.api_endpoint: Optional[str] = config.get("api_endpoint")
            self.api_key: Optional[str] = config.get("api_key")
            self.model: str = config.get("model", "qwen-max")
            self.timeout_seconds: int = config.get("timeout_seconds", 60)
            custom_params = config.get("custom_parameters", {})
            self.temperature: float = custom_params.get("temperature", 0.1)
            self.max_tokens: int = custom_params.get("max_tokens", 4000)
        else:
            s = get_settings()
            self.api_endpoint = str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None
            self.api_key = s.SICHUAN_API_KEY
            self.model = s.SICHUAN_MODEL
            self.timeout_seconds = 60
            self.temperature = 0.1
            self.max_tokens = 4000

        logger.info(f"FrontPageLLMClient 初始化: model={self.model}")

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
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
            "max_tokens": self.max_tokens,
            "stream": False,
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

DIAGNOSES_PROMPT = """从以下病历中提取诊断信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "ed_diagnosis_texts": ["门/急诊诊断1", "门/急诊诊断2"],
  "discharge_main_diagnosis_text": "出院主要诊断",
  "discharge_main_outcome": "主诊断出院转归(治愈/好转/未愈/死亡/其他)",
  "discharge_other_diagnoses_texts": ["其他诊断1", "其他诊断2"],
  "discharge_other_outcomes": ["好转", "好转"],
  "admission_condition": "1=有, 2=临床未确定, 3=情况不明, 4=无"
}}
```

直接输出 JSON，不要添加说明："""

PROCEDURES_PROMPT = """从以下病历中提取手术及操作信息。

【重要规则】
- 如果手术记录中包含多个手术操作（用"+"或"及"或顿号连接），必须将每个手术拆分为独立条目
- 第一个手术为主要手术，其余放入 other_procedures
- 例如："高位复杂性肛瘘切除术+肛周脓肿切开引流术+亚甲蓝肛周封闭术" 应拆分为3个独立手术

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "main_procedure_text": "主要手术名称（仅第一个手术）",
  "main_procedure_date": "YYYY-MM-DD",
  "main_procedure_level": "手术级别",
  "main_procedure_start_time": "YYYY-MM-DD HH:MM",
  "main_procedure_end_time": "YYYY-MM-DD HH:MM",
  "incision_grade": "切口等级(0类/I类/II类/III类)",
  "anesthesia_grade": "麻醉分级(如ASA I级/II级)",
  "is_main_surgery": "是/否",
  "unplanned_reoperation": "是/否",
  "other_procedures_texts": ["其他手术1", "其他手术2"],
  "other_procedures": [{{"text": "手术名", "date": "日期"}}],
  "surgeon_name": "术者姓名",
  "assistant1_name": "I助姓名",
  "assistant2_name": "II助姓名",
  "anesthesia_method": "麻醉方式",
  "anesthetist_name": "麻醉医师姓名",
  "incision_healing_grade": "切口愈合等级"
}}
```

如果没有手术记录，所有字段返回 null。
直接输出 JSON，不要添加说明："""

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


class FrontPageExtractionService:
    """病案首页抽取服务（LLM 版）"""

    def __init__(self, base_dir: Optional[Path] = None, llm_config: Optional[Dict[str, Any]] = None) -> None:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = base_dir
        self.demo_data_path = self.base_dir / "data" / "frontpage_demo_case.json"
        self.llm_client = FrontPageLLMClient(llm_config)
        self._use_llm = bool(self.llm_client.api_endpoint and self.llm_client.api_key)
        logger.info(f"FrontPageExtractionService 初始化: use_llm={self._use_llm}")

    async def generate_draft_from_visit(self, visit_id: str) -> FrontPageDraft:
        """
        根据住院 ID 生成首页草稿
        
        - 如果 LLM 已配置，调用 LLM 抽取
        - 否则回退到 demo 数据
        """
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

    async def extract_from_text(self, medical_text: str) -> FrontPageDraft:
        """
        直接从病历文本提取病案首页信息
        
        Args:
            medical_text: 病历全文
            
        Returns:
            FrontPageDraft: 提取的首页草稿
        """
        if not medical_text or not medical_text.strip():
            logger.warning("传入的病历文本为空，回退到 demo 数据")
            return await self._load_demo_frontpage()
        
        if self._use_llm:
            try:
                logger.info(f"开始从文本提取首页信息，文本长度: {len(medical_text)}")
                return await self._extract_with_llm(medical_text)
            except Exception as e:
                logger.error(f"LLM 抽取失败: {e}")
                raise
        else:
            logger.warning("LLM 未配置，回退到 demo 数据")
            return await self._load_demo_frontpage()

    async def extract_from_text_stream(
        self, medical_text: str, visit_id: str = None, force_llm: bool = False
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

        def format_prompt_or_none(name: str, template: str) -> Optional[str]:
            try:
                return template.format(medical_text=llm_text)
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
                procedures["main_procedure_text"] = main_proc.get("name")
                procedures["main_procedure_code"] = main_proc.get("code")
                logger.info(
                    "stream: merged principal procedure: %s -> %s",
                    main_proc.get("name"),
                    main_proc.get("code"),
                )
                if len(pp_list) > 1:
                    procedures["other_procedures_texts"] = [p.get("name") for p in pp_list[1:]]
                    procedures["other_procedures_codes"] = [p.get("code") for p in pp_list[1:]]

            warnings = coding_result.get("warnings") or coding_data.get("warnings") or []
            if isinstance(warnings, list) and warnings:
                validation_info["warnings"] = warnings
                logger.info("stream: 捕获到 %d 条编码警告", len(warnings))
            elif warnings:
                logger.warning("stream: warnings is not list, type=%s", type(warnings).__name__)

            diagnoses = self._normalize_diagnoses_structure(llm_text, diagnoses)
            fp_data["diagnoses"] = diagnoses
            fp_data["procedures"] = procedures

        # 条件化创建 LLM 任务：仅对 SQL 层缺失的模块调用 LLM
        if need_hosp_llm:
            prompt = format_prompt_or_none("hospitalization", HOSPITALIZATION_PROMPT)
            add_task("hospitalization", self._extract_json(prompt) if prompt else None)
        if need_diag_llm:
            prompt = format_prompt_or_none("diagnoses", DIAGNOSES_PROMPT)
            add_task("diagnoses", self._extract_json(prompt) if prompt else None)
        if need_proc_llm:
            prompt = format_prompt_or_none("procedures", PROCEDURES_PROMPT)
            add_task("procedures", self._extract_json(prompt) if prompt else None)
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

            try:
                if isinstance(result, dict):
                    if name == "diagnoses":
                        result = self._normalize_diagnoses_structure(llm_text, result)
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
                fp_data["procedures"] = resolve_procedure_codes(fp_data["procedures"])
                yield ("update", {"module": "procedures", "frontpage": fp_data})
            logger.info("stream: 本地 ICD 编码查询校正完成")
        except Exception:
            logger.exception("stream: local ICD code resolution failed")

        fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}

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

    async def _extract_with_llm(self, medical_text: str) -> FrontPageDraft:
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
        
        # 定义并行任务
        tasks = {
            "hospitalization": self._extract_json(HOSPITALIZATION_PROMPT.format(medical_text=medical_text)),
            "diagnoses": self._extract_json(DIAGNOSES_PROMPT.format(medical_text=medical_text)),
            "procedures": self._extract_json(PROCEDURES_PROMPT.format(medical_text=medical_text)),
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
            other_medical = other_medical or {}
            staff = staff or {}
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)

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
                procedures["main_procedure_text"] = main_proc.get("name")
                procedures["main_procedure_code"] = main_proc.get("code")
                
                # 其他手术
                if len(pp_list) > 1:
                    procedures["other_procedures_texts"] = [p.get("name") for p in pp_list[1:]]
                    procedures["other_procedures_codes"] = [p.get("code") for p in pp_list[1:]]
            
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
        
        # F5/F7: 使用本地 ICD 编码库查询国临版编码（替换 LLM 输出的编码）
        from .local_icd_service import resolve_diagnosis_codes, resolve_procedure_codes
        if diagnoses:
            diagnoses = resolve_diagnosis_codes(diagnoses)
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
        if procedures:
            procedures = resolve_procedure_codes(procedures)
        
        # 组装 FrontPageDraft
        frontpage_data = {
            "basic_info": basic_info,
            "hospitalization": hospitalization,
            "diagnoses": diagnoses,
            "procedures": procedures,
            "other_medical_info": other_medical,
            "staff": staff,
            "costs": {"total_cost": None, "self_paid": None, "categories": {}},
            "evidence": {},
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

    async def _extract_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """调用 LLM 并解析 JSON 响应"""
        try:
            response = await self.llm_client.generate(SYSTEM_PROMPT, prompt)
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
            flattened.extend(chunk)

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

        parsed_from_text = self._extract_discharge_diagnoses_from_text(medical_text)
        if parsed_from_text:
            main = parsed_from_text[0]
            others = parsed_from_text[1:]
        else:
            # Strict mode: no discharge diagnosis section -> no discharge diagnosis text.
            logger.warning("no discharge diagnosis section parsed; keep discharge diagnoses empty")
            main = None
            others = []

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
                logger.info(f"入院病情推理完成，共处理 {len(results_list)} 个诊断")
            else:
                logger.warning("入院病情推理结果解析失败")
                
        except Exception as e:
            logger.error(f"入院病情推理失败: {e}")
        
        return diagnoses

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

        # 先拆分复合手术名称
        procedures = self._split_compound_procedures(procedures)

        main_proc = procedures.get("main_procedure_text")
        if main_proc:
            suggestions = await icd_service.suggest_procedure_codes(main_proc, top_k=3)
            if suggestions:
                procedures["main_procedure_code_suggestions"] = suggestions
                procedures["main_procedure_code"] = suggestions[0].get("code")
                logger.info(f"主手术编码推荐: {main_proc} -> {suggestions[0].get('code')}")

        return procedures

    @staticmethod
    def _split_compound_procedures(procedures: Dict[str, Any]) -> Dict[str, Any]:
        """拆分用 + 或顿号连接的复合手术名称为独立条目"""
        if not isinstance(procedures, dict):
            logger.warning("split compound procedures received non-dict input, type=%s", type(procedures).__name__)
            return {}

        main_text = procedures.get("main_procedure_text", "") or ""
        if not main_text:
            return procedures

        # 检测是否包含分隔符（+、＋、、）
        parts = re.split(r'[+＋、]', main_text)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            return procedures

        # 第一个 → 主手术，其余追加到 other_procedures_texts
        procedures["main_procedure_text"] = parts[0]
        existing_others = procedures.get("other_procedures_texts") or []
        procedures["other_procedures_texts"] = parts[1:] + existing_others
        logger.info(f"拆分复合手术: '{main_text}' -> 主: '{parts[0]}', 其他: {parts[1:]}")
        return procedures

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
            "assistant1_name": main_proc.get("assistant1_name"),
            "assistant2_name": main_proc.get("assistant2_name"),
            "anesthesia_method": main_proc.get("anesthesia_method"),
            "anesthetist_name": main_proc.get("anesthetist_name"),
            "incision_healing_grade": main_proc.get("incision_healing_grade"),
        }

        frontpage_data = {
            **raw_frontpage,
            "diagnoses": diagnoses,
            "procedures": procedures,
        }

        return FrontPageDraft.model_validate(frontpage_data)


# 提供单例风格的访问方式
default_frontpage_service = FrontPageExtractionService()
