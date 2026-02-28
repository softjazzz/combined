from __future__ import annotations

"""
病案首页自动生成服务（LLM 抽取版）

功能：
- 从 visit_id 获取全病历文书（当前为 mock，后续接入真实 EMR）
- 调用 LLM 分步抽取各模块字段（患者信息、住院信息、诊断、手术等）
- 返回结构化的 FrontPageDraft
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator, Tuple
import json
import logging
import asyncio
import re

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
  "current_address": "现住址",
  "contact_name": "联系人姓名",
  "contact_relation": "联系人关系",
  "contact_phone": "联系人电话"
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
  "actual_hospital_days": 住院天数(数字)
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
  "discharge_other_diagnoses_texts": ["其他诊断1", "其他诊断2"],
  "admission_condition": "1=有, 2=临床未确定, 3=情况不明, 4=无"
}}
```

直接输出 JSON，不要添加说明："""

PROCEDURES_PROMPT = """从以下病历中提取手术及操作信息。

【病历内容】
{medical_text}

【输出格式】
```json
{{
  "main_procedure_text": "主要手术名称",
  "main_procedure_date": "YYYY-MM-DD",
  "main_procedure_level": "手术级别",
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
  "icu_leave_time": "退出ICU时间"
}}
```

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
  "coder": "编码员"
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
    "1": 综合医疗服务费,
    "2": 诊断类费用,
    "3": 治疗类费用,
    "4": 康复类费用,
    "5": 中医类费用,
    "6": 西药类费用,
    "7": 中药类费用,
    "8": 血液和血液制品类费用,
    "9": 耗材类费用,
    "10": 其他类费用
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
        self, medical_text: str
    ) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
        """
        逐步抽取首页信息，按模块产出结果（用于前端分批展示）。

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
                    "current_address": "",
                    "contact_name": "",
                    "contact_relation": "",
                    "contact_phone": "",
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

        if not medical_text or not medical_text.strip():
            demo = await self._load_demo_frontpage()
            yield ("done", {"frontpage": demo.model_dump(), "fallback": "empty_text"})
            return

        if not self._use_llm:
            demo = await self._load_demo_frontpage()
            yield ("update", {"frontpage": demo.model_dump(), "fallback": "llm_not_configured"})
            yield ("done", {"frontpage": demo.model_dump(), "fallback": "llm_not_configured"})
            return

        fp_data: Dict[str, Any] = default_frontpage()
        validation_info: Dict[str, Any] = {}

        logger.info("stream: Step 1: 提取基本信息...")
        basic_info = await self._extract_json(BASIC_INFO_PROMPT.format(medical_text=medical_text)) or {}
        fp_data["basic_info"] = {**fp_data["basic_info"], **basic_info}
        yield ("update", {"module": "basic_info", "frontpage": fp_data})

        patient_context = {
            "gender": (basic_info or {}).get("gender_text", "未说明"),
            "age": (basic_info or {}).get("age_years", 0),
        }

        logger.info("stream: Step 2: 并行提取其他模块及外部编码...")
        from .external_coding_service import get_external_coding_service

        ext_coding_service = get_external_coding_service()

        async def run_named(name: str, coro):
            try:
                return name, await coro
            except Exception as e:
                return name, e

        import time
        task_start_times: Dict[str, float] = {}
        
        async def run_named_timed(name: str, coro: Coroutine) -> Tuple[str, Any]:
            """Wrapper that tracks timing for each task."""
            task_start_times[name] = time.time()
            try:
                result = await coro
                return name, result
            except Exception as e:
                return name, e

        named_tasks: List[asyncio.Task] = [
            asyncio.create_task(
                run_named_timed(
                    "hospitalization",
                    self._extract_json(HOSPITALIZATION_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "diagnoses",
                    self._extract_json(DIAGNOSES_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "procedures",
                    self._extract_json(PROCEDURES_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "other_medical_info",
                    self._extract_json(OTHER_MEDICAL_INFO_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "staff",
                    self._extract_json(STAFF_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "costs",
                    self._extract_json(COSTS_PROMPT.format(medical_text=medical_text)),
                )
            ),
            asyncio.create_task(
                run_named_timed(
                    "coding_result",
                    ext_coding_service.extract_coding(medical_text, patient_context),
                )
            ),
        ]

        for finished in asyncio.as_completed(named_tasks):
            name, result = await finished
            elapsed = time.time() - task_start_times.get(name, time.time())
            logger.info(f"Task '{name}' completed in {elapsed:.2f}s")
            
            if isinstance(result, Exception):
                logger.warning(f"stream: task {name} failed: {result}")
                result = None

            if name == "coding_result":
                coding_result = result or None
                logger.info(f"stream: coding_result received")
                if coding_result:
                    try:
                        # Extract coding_data from nested structure
                        coding_data = coding_result.get("coding_data", coding_result)
                        diagnoses = fp_data.get("diagnoses") or {}
                        procedures = fp_data.get("procedures") or {}
                        logger.info(f"stream: before merge, diagnoses keys: {list(diagnoses.keys())}")

                        if coding_data.get("principal_diagnosis"):
                            pd = coding_data["principal_diagnosis"]
                            diagnoses["discharge_main_diagnosis_text"] = pd.get("name")
                            diagnoses["discharge_main_icd"] = pd.get("code")
                            validation_info["principal_diagnosis_confidence"] = pd.get("confidence")
                            logger.info(f"stream: merged principal diagnosis: {pd.get('name')} -> {pd.get('code')}")

                        if coding_data.get("secondary_diagnoses"):
                            sd_list = coding_data["secondary_diagnoses"]
                            diagnoses["discharge_other_diagnoses_texts"] = [d.get("name") for d in sd_list]
                            diagnoses["discharge_other_icds"] = [d.get("code") for d in sd_list]
                            logger.info(f"stream: merged {len(sd_list)} secondary diagnoses")

                        if coding_data.get("principal_procedures"):
                            pp_list = coding_data["principal_procedures"]
                            if pp_list:
                                main_proc = pp_list[0]
                                procedures["main_procedure_text"] = main_proc.get("name")
                                procedures["main_procedure_code"] = main_proc.get("code")
                                logger.info(f"stream: merged principal procedure: {main_proc.get('name')} -> {main_proc.get('code')}")

                        if coding_result.get("warnings") or coding_data.get("warnings"):
                            warnings = coding_result.get("warnings") or coding_data.get("warnings") or []
                            if warnings:
                                validation_info["warnings"] = warnings
                                logger.info(f"stream: 捕获到 {len(warnings)} 条编码警告")

                        diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
                        fp_data["diagnoses"] = diagnoses
                        fp_data["procedures"] = procedures
                        logger.info(f"stream: after merge, discharge_main_icd = {diagnoses.get('discharge_main_icd')}")
                    except Exception as e:
                        logger.warning(f"stream: merge coding result failed: {e}")

                fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}
                yield ("update", {"module": "confidence", "frontpage": fp_data})
                continue

            if isinstance(result, dict):
                if name == "diagnoses":
                    result = self._normalize_diagnoses_structure(medical_text, result)
                fp_data[name] = result
            else:
                fp_data[name] = fp_data.get(name) or {}

            yield ("update", {"module": name, "frontpage": fp_data})

        # Post-processing (may trigger extra LLM calls; still stream when finished)
        try:
            if fp_data.get("diagnoses"):
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(medical_text, fp_data["diagnoses"])
                fp_data["diagnoses"] = await self._infer_admission_conditions(medical_text, fp_data["diagnoses"])
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(medical_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception as e:
            logger.warning(f"stream: infer admission conditions failed: {e}")

        try:
            if fp_data.get("diagnoses") and not fp_data["diagnoses"].get("discharge_main_icd"):
                fp_data["diagnoses"] = await self._suggest_diagnosis_codes(fp_data["diagnoses"])
                fp_data["diagnoses"] = self._normalize_diagnoses_structure(medical_text, fp_data["diagnoses"])
                yield ("update", {"module": "diagnoses", "frontpage": fp_data})
        except Exception as e:
            logger.warning(f"stream: suggest diagnosis codes failed: {e}")

        try:
            if fp_data.get("procedures") and not fp_data["procedures"].get("main_procedure_code"):
                fp_data["procedures"] = await self._suggest_procedure_codes(fp_data["procedures"])
                yield ("update", {"module": "procedures", "frontpage": fp_data})
        except Exception as e:
            logger.warning(f"stream: suggest procedure codes failed: {e}")

        fp_data["confidence"] = {**fp_data.get("confidence", {}), **validation_info}

        # Final validation (best effort)
        try:
            draft = FrontPageDraft.model_validate(fp_data)
            yield ("done", {"frontpage": draft.model_dump()})
        except Exception as e:
            logger.warning(f"stream: final validation failed, returning raw frontpage: {e}")
            yield ("done", {"frontpage": fp_data, "warning": str(e)})

    async def _get_medical_text(self, visit_id: str) -> str:
        """获取病历全文（当前为 demo，后续接入真实 EMR）"""
        # TODO: 根据 visit_id 从 EMR 系统获取病历文书
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
        if coding_result:
            logger.info("合并外部编码服务结果...")
            # 主诊断
            if coding_result.get("principal_diagnosis"):
                pd = coding_result["principal_diagnosis"]
                diagnoses["discharge_main_diagnosis_text"] = pd.get("name")
                diagnoses["discharge_main_icd"] = pd.get("code")
                # 记录置信度
                validation_info["principal_diagnosis_confidence"] = pd.get("confidence")
            
            # 其他诊断
            if coding_result.get("secondary_diagnoses"):
                sd_list = coding_result["secondary_diagnoses"]
                diagnoses["discharge_other_diagnoses_texts"] = [d.get("name") for d in sd_list]
                diagnoses["discharge_other_icds"] = [d.get("code") for d in sd_list]
                
            # 手术
            if coding_result.get("principal_procedures"):
                pp_list = coding_result["principal_procedures"]
                if pp_list:
                    main_proc = pp_list[0]
                    procedures["main_procedure_text"] = main_proc.get("name")
                    procedures["main_procedure_code"] = main_proc.get("code")
                    
                    # 其他手术
                    if len(pp_list) > 1:
                        procedures["other_procedures_texts"] = [p.get("name") for p in pp_list[1:]]
                        procedures["other_procedures_codes"] = [p.get("code") for p in pp_list[1:]]
            
            # 校验警告
            if coding_result.get("warnings"):
                validation_info["warnings"] = coding_result["warnings"]
                logger.info(f"捕获到 {len(coding_result['warnings'])} 条编码警告")

        # F4: 入院病情推理（只在没有外部结果时使用 mock/LLM 推理，或者作为补充）
        # 这里我们仍然运行它来获取 admission_condition
        if diagnoses:
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
            diagnoses = await self._infer_admission_conditions(medical_text, diagnoses)
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
        
        # F5/F7: ICD 编码推荐（如果在 step 3 中已经填充了编码，_suggest 方法内部应该检查是否存在）
        # 我们修改一下逻辑：如果已经有 code 了，就不再重新 suggest，或者 suggest 作为补充
        if diagnoses and not diagnoses.get("discharge_main_icd"):
            diagnoses = await self._suggest_diagnosis_codes(diagnoses)
            diagnoses = self._normalize_diagnoses_structure(medical_text, diagnoses)
            
        if procedures and not procedures.get("main_procedure_code"):
            procedures = await self._suggest_procedure_codes(procedures)
        
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
        
        logger.info("LLM 抽取完成，构建 FrontPageDraft")
        return FrontPageDraft.model_validate(frontpage_data)

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

    def _normalize_diag_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        text = value.strip().replace("\u3000", " ")
        text = re.sub(r"^[\-\u2022•·]+\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ;；,，。")

    def _unique_texts(self, texts: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for text in texts:
            cleaned = self._normalize_diag_text(text)
            if not cleaned:
                continue
            key = cleaned.lower()
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
        Normalize diagnosis granularity to avoid merged multi-line diagnoses.
        """
        diag: Dict[str, Any] = dict(diagnoses or {})

        main = self._normalize_diag_text(diag.get("discharge_main_diagnosis_text"))
        raw_others = diag.get("discharge_other_diagnoses_texts") or []
        others = self._unique_texts(raw_others if isinstance(raw_others, list) else [])

        existing_all = self._unique_texts(([main] if main else []) + others)
        if existing_all:
            main = existing_all[0]
            others = existing_all[1:]

        parsed_from_text = self._extract_discharge_diagnoses_from_text(medical_text)
        should_use_parsed = False
        if parsed_from_text:
            if len(parsed_from_text) > len(existing_all):
                should_use_parsed = True
            elif main and " " in main and len(parsed_from_text) >= 2:
                # Composite principal diagnosis like "A B C".
                hit_count = sum(1 for item in parsed_from_text if item and item in main)
                if hit_count >= 2:
                    should_use_parsed = True

        if should_use_parsed:
            logger.info(
                "diagnoses normalization applied: existing=%d parsed=%d",
                len(existing_all),
                len(parsed_from_text),
            )
            merged = self._unique_texts(parsed_from_text + existing_all)
            if merged:
                main = merged[0]
                others = merged[1:]

        diag["discharge_main_diagnosis_text"] = main or None
        diag["discharge_other_diagnoses_texts"] = others

        other_icds = diag.get("discharge_other_icds")
        if isinstance(other_icds, list):
            if len(other_icds) < len(others):
                other_icds = other_icds + [None] * (len(others) - len(other_icds))
            elif len(other_icds) > len(others):
                other_icds = other_icds[: len(others)]
            diag["discharge_other_icds"] = other_icds

        return diag

    async def _infer_admission_conditions(
        self, medical_text: str, diagnoses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        F4: 入院病情推理
        
        对每个出院诊断推理其入院病情代码（1-4）
        """
        # 构建诊断列表文本
        all_diagnoses = []
        
        main_diag = diagnoses.get("discharge_main_diagnosis_text")
        if main_diag:
            all_diagnoses.append(f"1. 主要诊断: {main_diag}")
        
        other_diags = diagnoses.get("discharge_other_diagnoses_texts", [])
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
            
            if result and "results" in result:
                # 提取主诊断的入院病情
                for item in result["results"]:
                    if item.get("diagnosis") == main_diag or "主要诊断" in item.get("diagnosis", ""):
                        diagnoses["admission_condition"] = str(item.get("admission_condition", ""))
                        diagnoses["admission_condition_reasoning"] = item.get("reasoning", "")
                        break
                
                # 可选：存储所有诊断的入院病情推理结果
                diagnoses["_admission_condition_details"] = result["results"]
                logger.info(f"入院病情推理完成，共处理 {len(result['results'])} 个诊断")
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
        """
        F7: 为手术推荐 ICD-9-CM-3 编码
        """
        from .icd_coding_service import get_icd_coding_service
        icd_service = get_icd_coding_service()
        
        main_proc = procedures.get("main_procedure_text")
        if main_proc:
            suggestions = await icd_service.suggest_procedure_codes(main_proc, top_k=3)
            if suggestions:
                procedures["main_procedure_code_suggestions"] = suggestions
                # 自动填入最高置信度的编码
                procedures["main_procedure_code"] = suggestions[0].get("code")
                logger.info(f"主手术编码推荐: {main_proc} -> {suggestions[0].get('code')}")
        
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
