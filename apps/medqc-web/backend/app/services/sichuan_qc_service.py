from typing import Callable, Dict, Any, List, Optional, Tuple
import json
import hashlib
import logging
import time
import re
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone

from app.constants.doc_types import DOC_TYPE_CN_TO_EN, DOC_TYPE_FULL_MAP
from ..core.settings import get_settings
from ..core.http import safe_post_json
from ..core.supabase_client import get_supabase
from ..database.connection import SessionLocal
from ..database.models.cdm import Diagnosis, FirstCourseRecord
from .copy_content_similarity import (
    ADMISSION_SOURCE_TABLES,
    FIRST_COURSE_SOURCE_TABLES,
    ROUND_SENTENCE_MATCH_THRESHOLD,
    ROUND_SOURCE_TABLES,
    compare_text_segments,
    extract_admission_sections,
    extract_first_course_sections,
    normalize_for_sentence,
    parse_document_datetime,
    select_best_lookback_match,
    split_sentences,
)
from .unified_rule_engine import UnifiedRuleEngine
from .llm_config_loader import LLMConfigLoader, build_adjudicator_runtime_config
from .qc_llm_client_runtime import SichuanQCLLMClient  # 拆分出的 LLM 客户端（runtime 源码版）
from .qc_prompt_builder import QCPromptBuilder  # 拆分出的 Prompt 构建器
from .bundles import load_or_assemble_domain_bundle
from .rule_domain_router import (
    build_evidence_payload_from_rule_input,
    RuleExecutionInput,
    display_name_for_doc_type,
    render_rule_execution_medical_text,
    route_rule_to_domain,
)
from .programmatic_rule_executor import PROGRAMMATIC_RULE_SPECS
from .qc_execution_cache import QCExecutionCache
from .qc_rule_orchestrator import QCRuleOrchestrator
from .qc_rule_registry_service import QCRuleRegistryService
from .effect_priority_qc import (
    BATCH_OUTPUT_MODE_FULL,
    DEFAULT_MAX_REFINE_CANDIDATES,
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
    merge_refined_results,
    normalize_batch_output_mode,
    normalize_max_refine_candidates,
    normalize_quality_profile,
    select_refine_candidates,
)
from .qc_rule_sets import should_refine_rule_by_default
from .qc_cancellation import raise_if_cancelled
from .customer_rule_sets import load_customer_luxian_rules, invalidate_customer_rule_set_cache
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY, load_luxian_0609_rules
from .luxian_0609_result_aggregator import aggregate_luxian_0609_results, summarize_luxian_0609_results
from .luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules
from .luxian_0609_trigger_gate import evaluate_luxian_0609_trigger_gates, filter_executable_rules_by_gate
from .sc_rule_family import (
    DEFAULT_RULE_FAMILY,
    load_sc_rule_family_map,
    resolve_rule_family,
    validate_sc_rule_family_map,
)

logger = logging.getLogger(__name__)

_COPY_ROUND_RULE_IDS = {"CL-037", "CL-275"}
_COPY_FIRST_COURSE_RULE_IDS = {"CL-273", "CL-274", "CL-276"}
_COPY_SIGNAL_RULE_IDS = _COPY_ROUND_RULE_IDS | _COPY_FIRST_COURSE_RULE_IDS
_COPY_SIMILARITY_THRESHOLD = 0.5
_ROUND_LATER_COVERAGE_THRESHOLD = 0.85
_ROUND_LOOKBACK_COUNT = 3
_ROUND_SENTENCE_MATCH_THRESHOLD = ROUND_SENTENCE_MATCH_THRESHOLD
_ROUND_SIMILARITY_RULE_IDS = _COPY_ROUND_RULE_IDS
_ROUND_SIMILARITY_SOURCE_TABLES = ROUND_SOURCE_TABLES
_SC050_SIMILARITY_THRESHOLD = _COPY_SIMILARITY_THRESHOLD

_SC_032_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-032：病程记录重要病情变化(症状及体征)未记录或记录不全。

【检查要点】
1. 只检查日常病程记录中是否完整记录了当日重要病情变化，重点看症状、体征、病情演变和关键阴性情况是否写清。
2. 下列情形通常判定为不合规：
   (a) 记录仅有一句套话，如“病情同前”“继续治疗”“继续观察”，没有任何具体病情变化；
   (b) 记录过于简略，未写患者当前症状、体征、查房结论或病情变化；
   (c) 上下文能看出患者当日存在明确变化，但病程正文未体现。
3. 若病情稳定，只要病程已明确写出“无特殊不适/症状缓解/生命体征平稳/切口情况/查体情况”等关键变化，也可判定为合规。
4. 不要因为文字篇幅短就直接判问题；关键是有没有把当日重要变化写出来。
5. 对“病程记录无具体内容”“病程过于简单/过于简略”“未描述病情变化、目前症状、体征”这类文本，若正文证据也支持，应优先判定为 non_compliant。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 若证据不足以判断，再返回 is_compliant=true，同时 findings 明确写“证据不足”，issues 为空。"""

_SC_036_STRICT_CUSTOM_PROMPT = """【检查要点】
1. 本规则专门检查病程记录中是否对重要辅助检查结果，尤其是异常检查结果，进行了充分分析并给出处理意见。
2. 判断时必须同时检查【主文书正文】、【同域辅助证据】和【时间锚点】；若辅助证据已给出明确异常结果，而主病程未回应，也属于本规则问题。
3. 合规必须同时满足以下至少两层信息：
   (a) 明确指出具体异常结果或异常趋势；
   (b) 结合当前诊断、病情变化或围术期风险说明其临床意义/可能原因；
   (c) 给出针对性的处置、复查、会诊、观察重点或方案调整。
4. 仅罗列检查结果，或仅写“较前好转”“继续观察”“继续原方案”“炎症指标好转”等笼统总结，而未解释具体异常项的意义、原因或后续处理，不算充分分析，应判定为不合规。
5. 若病程中已经明确写出：异常结果提示什么问题、为何如此判断、已采取什么处理或后续计划，例如“尿常规提示泌尿道感染，予左氧氟沙星抗感染，并请泌尿外科会诊”，可判定为合规。
6. 如病历只有正常结果，或虽有轻微波动但无临床意义且记录中已说明病情稳定，可谨慎判定为合规；若证据不足，请在 findings 中说明不足原因，不要过度推断。
7. 【重点收紧】遇到“ESR/PCT/CRP异常后仅写炎症指标较前好转”“肾功异常后仅写继续观察”这类表述时，默认视为分析不足，除非同段或紧邻病程中还有明确的异常原因解释和处理计划。
8. 【强约束】只要【同域辅助证据】或【时间锚点】出现明确异常结果/异常结论，而主病程仅写“较前好转/继续观察/继续原方案/病情稳定/余治疗同前”等泛化套话，且未说明该异常的临床意义、原因或针对性处理，默认判 non_compliant，不得判 compliant 或 uncertain。
9. 【格式要求】你必须严格返回纯JSON格式，禁止输出任何分析过程、思考步骤或解释性文字。"""

_SC_039_STRICT_CUSTOM_PROMPT = """【检查要点】
1. 本规则只根据病历文本本身判断危急值记录是否完整合规，不依赖危急值数据表、阈值表、LIS 结构化标记。
2. 只要病历文本已经明确把某事件当作危急值处理，即进入本规则判定。典型触发文本包括：出现“危急值”“接危急值”“危急值回报”“危急值处理”“接到电话通知”等表述，或同段直接记录危急值处置语境下的关键结果与处理，例如“K 2.76mmol/L，行静脉补钾”“K 1.68mmol/L”“K 2.05mmol/L”等。
3. 合规的危急值病程记录，应尽量完整体现以下闭环要素中的大部分：
   (a) 危急值报告/接收时间，至少应尽量具体到分钟；
   (b) 具体项目和具体数值；
   (c) 患者当时情况、症状、体征或床旁评估；
   (d) 明确的处理措施，不能只写“已处理”“已补钾”“继续观察”；
   (e) 处理后观察、复查结果或下一步计划；
   (f) 责任医师记录归属清晰。
4. 直接判定为不合规的典型情形：
   (a) 只写危急值项目和数值，无其它内容；
   (b) 只写“行静脉补钾”“已处理”“接电脑危急值”等简略表述；
   (c) 未写危急值报告时间、处置时间、具体处置内容；
   (d) 未写查看患者情况、处理后效果或复查计划。
5. 若病历文本仅出现“危急值”字样，但当前提供的内容明显是截断片段，无法判断同一条记录后续是否已补全，才可判定为 uncertain；不要因为写得简单就放宽为 uncertain。
6. 只要文本已经自认是危急值事件，就不要再额外追问它在客观上是否达到危急值阈值；本规则检查的是病历记录质量，不是危急值阈值识别。
7. 【重点案例】对于“K 1.68mmol/L、K 2.05mmol/L 无其它内容”“K 2.76mmol/L，行静脉补钾，未描述危急值报告、处置时间及具体补钾情况”“接到危急值后未查看患者情况”“接电脑危急值”这类文本，默认应判定为 non_compliant。
8. 【格式要求】你必须严格返回纯JSON格式，禁止输出任何分析过程、思考步骤或解释性文字。"""

_SC_011_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-011：现病史中阴性/阳性症状、伴随症状记录缺失或不足。

【检查要点】
1. 仅检查入院记录中的现病史是否围绕主诉补充了必要的阳性症状、阴性症状、伴随症状。
2. 出现下列情况通常判定为不合规：
   (a) 只写主症状，没有交代关键阴性症状；
   (b) 对鉴别诊断有帮助的重要伴随症状未记录；
   (c) 现病史描述过于笼统，无法支撑后续诊断判断。
3. 如果病历已经明确补充了主要阳性表现、关键阴性表现和必要伴随症状，可判合规。
4. 不要因为文本短就直接判问题；关键看是否遗漏了影响诊断判断的重要症状信息。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 证据不足时可返回 is_compliant=true，但 findings 必须明确写“证据不足”，issues 为空。"""

_SC_012_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-012：现病史中的诊治经过记录不全或不清。

【检查要点】
1. 仅检查入院记录现病史中是否清楚记录了发病后的诊治经过，包括门诊就诊、检查项目及结果、既往/院外治疗、用药及效果。
2. 出现下列情况通常判定为不合规：
   (a) 仅写“门诊就诊”或“已治疗”但未写检查/治疗内容；
   (b) 既往重要治疗经过、院外处理、用药情况缺失；
   (c) 现病史无法说明本次住院前已经接受过哪些检查与治疗。
3. 如果已经写清检查结果、治疗措施、用药反应或疗效变化，可判合规。
4. 对“治疗经过不详细”“无诊治经过”“门诊初步诊断未写”“接受检查与治疗未体现”这类问题，若原文也支持，应优先判定为 non_compliant。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 证据不足时可返回 is_compliant=true，但 findings 必须明确写“证据不足”，issues 为空。"""

_SC_019_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-019：现病史中辅助检查记录不完善或记录不准确。

【检查要点】
1. 仅检查入院记录现病史中对院内外辅助检查的记录是否完整、准确。
2. 出现下列情况通常判定为不合规：
   (a) 检查项目名称、部位、结果抄写错误；
   (b) 关键辅助检查结果缺失，只写“完善检查”但没有结果；
   (c) 院外重要检查、院内已有关键检查未记录，影响病情判断。
3. 若病历已清楚、准确写出主要检查项目及关键结果，可判合规。
4. 对“检查项目记录有错误”“辅助检查未记录/抄写不准确”这类问题，若原文支持，应优先判定为 non_compliant。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 证据不足时可返回 is_compliant=true，但 findings 必须明确写“证据不足”，issues 为空。"""

_SC_081_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-081：术前小结记录不完整或内容不当。

【检查要点】
1. 重点检查术前小结是否完整体现病情概况、拟行手术、主要风险、手术要点、术前准备及注意事项。
2. 若术前小结仅有模板化套话，或“手术要点”写成“术中注意无菌操作”这类空泛表述，通常判定为 non_compliant。
3. 若术前小结缺少关键结论、风险提示、术前准备、手术要点等任一重要内容，也应判定为 non_compliant。
4. 若提供的文书并非术前小结，或正文明显残缺无法判断，可返回证据不足。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 若判定不合规，findings 要直接指出缺失项或空泛项；evidence 要引用原文中的关键短句。"""

_SC_105_STRICT_CUSTOM_PROMPT = """你是一名病历质控专家，请只评估规则 SC-105：术后首次病程记录书写不完整或不规范。

【检查要点】
1. 重点检查术后首次病程记录是否写明手术时间、麻醉方式、术式、术中情况、术后处理措施、术后注意事项及向家属告知手术情况。
2. 若手术时间与上下文不一致，或缺少术后处理措施、术后注意事项、向家属告知情况等关键要素，通常判定为 non_compliant。
3. 若术后首次病程仅罗列手术名称，没有具体术后处理和注意事项，也应判定为 non_compliant。
4. 若当前文本不是术后首次病程，或正文明显残缺无法判断，可返回证据不足。

【病历文本】
{medical_text}

【输出要求】
1. 只返回单个 JSON 对象，不要输出 Markdown，不要输出解释性文字。
2. JSON 结构固定为：
{{"is_compliant": boolean, "issues": [string], "findings": string, "evidence": string, "suggestion": string, "confidence": number}}
3. 若判定不合规，findings 要写明具体缺项或时间不一致点；evidence 要引用原文中的关键字段。"""

# SichuanQCLLMClient 已拆分至 qc_llm_client.py
# 通过上方 import 重新导出，外部引用不受影响



class RuleSourceGuardError(RuntimeError):
    """规则来源不满足生产治理约束时抛出。"""


class SichuanQCService:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化四川质控服务

        Args:
            config: LLM 配置字典，如果为 None 则从 .env 文件加载
        """
        # LLM 客户端（config 为 None 时，SichuanQCLLMClient 自动从 .env 加载）
        self.client = SichuanQCLLMClient(config)
        self.adjudicator_client = SichuanQCLLMClient(
            build_adjudicator_runtime_config(
                config
                or {
                    "provider_code": self.client.provider_code,
                    "api_endpoint": self.client.api_endpoint,
                    "api_key": self.client.api_key,
                    "model": self.client.model,
                    "timeout_seconds": self.client.timeout_seconds,
                    "allow_mock_when_unconfigured": self.client.allow_mock_when_unconfigured,
                    "source": self.client.config_source,
                    "custom_parameters": {
                        "temperature": self.client.temperature,
                        "top_p": self.client.top_p,
                        "max_tokens": self.client.max_tokens,
                        "enable_thinking": self.client.enable_thinking,
                        "reasoning_effort": self.client.reasoning_effort,
                    },
                }
            )
        )

        # 规则缓存
        self._rules_cache: Optional[List[Dict[str, Any]]] = None
        self._custom_rules_cache: Optional[List[Dict[str, Any]]] = None
        self._customer_rules_cache: Optional[List[Dict[str, Any]]] = None
        self._active_sc_rules_cache: Optional[List[Dict[str, Any]]] = None
        self._active_sc_rules_source: str = "json_file"
        self._active_sc_rules_checksum: str = ""
        self._sc_rule_family_map_cache: Optional[Dict[str, str]] = None
        self._last_registry_error: Optional[str] = None
        self.rule_registry = QCRuleRegistryService()
        data_dir = Path(__file__).resolve().parent.parent / "data"
        self._sc_rules_json_path = data_dir / "sichuan_rules_146.json"
        self._custom_rules_json_path = data_dir / "custom_rules_33.json"
        self._customer_rules_json_path = data_dir / "customer_rules_luxian_v1.json"
        self._last_source_alert_key: str = ""
        self._last_source_alert_at: float = 0.0

        # 统一规则引擎 (用于串行模式)
        self.rule_engine = UnifiedRuleEngine(self.client.generate)
        self.rule_orchestrator = QCRuleOrchestrator()
        self.execution_cache = QCExecutionCache(default_ttl_seconds=1800)

        # 英文到中文文书类型映射（从共享常量导入，避免重复维护）
        from app.constants.doc_types import DOC_TYPE_FULL_MAP
        self.doc_type_mapping = dict(DOC_TYPE_FULL_MAP)


        # 截断配置 + Prompt 构建器
        from ..core.settings import get_settings
        settings = get_settings()
        self.enable_truncate = settings.LLM_ENABLE_TRUNCATE
        self.max_content_length = settings.LLM_MAX_CONTENT_LENGTH
        self.prompt_builder = QCPromptBuilder(
            enable_truncate=self.enable_truncate,
            max_content_length=self.max_content_length,
        )

    def _ensure_rule_execution_meta(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(rule or {})
        rule_id = str(normalized.get("rule_id") or "").strip().upper()
        rule_code = str(normalized.get("rule_code") or "").strip()

        if rule_id == "SC-032":
            normalized["custom_prompt"] = _SC_032_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc032-v1"
        elif rule_id == "SC-011":
            normalized["custom_prompt"] = _SC_011_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc011-v1"
        elif rule_id == "SC-012":
            normalized["custom_prompt"] = _SC_012_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc012-v1"
        elif rule_id == "SC-019":
            normalized["custom_prompt"] = _SC_019_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc019-v1"
        elif rule_id == "SC-036":
            normalized["custom_prompt"] = _SC_036_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc036-v3"
        elif rule_id == "SC-039":
            normalized["custom_prompt"] = _SC_039_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc039-v1"
        elif rule_id == "SC-081":
            normalized["custom_prompt"] = _SC_081_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc081-v1"
        elif rule_id == "SC-105":
            normalized["custom_prompt"] = _SC_105_STRICT_CUSTOM_PROMPT
            normalized["prompt_version"] = "runtime-override-sc105-v1"

        raw_executor_type = str(normalized.get("executor_type") or "").strip().lower()
        executor_type = raw_executor_type
        if executor_type not in {"llm", "program"}:
            executor_type = "llm"
            if rule_id in PROGRAMMATIC_RULE_SPECS:
                executor_type = "program"
            logger.warning(
                "规则 %s(%s) 未标注或标注了无效 executor_type，已默认回退为 %s",
                rule_id or "UNKNOWN_RULE",
                rule_code or "-",
                executor_type,
            )
        normalized["executor_type"] = executor_type

        routing_decision = route_rule_to_domain(normalized)
        execution_domain = str(normalized.get("execution_domain") or "").strip().lower()
        doc_count = len(set(normalized.get("applicable_documents") or []))
        # 单文书规则：强制按文书路由对齐执行域，消除历史 execution_domain 漂移。
        # 多文书规则：保留已标注域，仅在缺失时回填路由域。
        if doc_count == 1:
            execution_domain = routing_decision.execution_domain
        elif not execution_domain:
            execution_domain = routing_decision.execution_domain
        normalized["execution_domain"] = execution_domain

        doc_scope = str(normalized.get("doc_scope") or "").strip().lower()
        if not doc_scope:
            doc_scope = "primary"
        normalized["doc_scope"] = doc_scope

        rule_version = str(normalized.get("rule_version") or "").strip()
        if not rule_version:
            rule_version = "v1"
        normalized["rule_version"] = rule_version

        prompt_version = str(normalized.get("prompt_version") or "").strip()
        if not prompt_version:
            prompt_version = "custom-v1" if str(normalized.get("custom_prompt") or "").strip() else "default-v1"
        normalized["prompt_version"] = prompt_version

        cost_class = str(normalized.get("cost_class") or "").strip().lower()
        if not cost_class:
            cost_class = "low" if executor_type == "program" else "medium"
        normalized["cost_class"] = cost_class

        rule_family = resolve_rule_family(
            normalized,
            sc_mapping=self._load_sc_rule_family_map(),
        )
        normalized["rule_family"] = rule_family or DEFAULT_RULE_FAMILY
        normalized["allow_selective_refine"] = bool(
            normalized.get("allow_selective_refine")
            if normalized.get("allow_selective_refine") is not None
            else should_refine_rule_by_default(rule_id)
        )

        custom_prompt = str(normalized.get("custom_prompt") or "")
        if custom_prompt:
            normalized["custom_prompt"] = self._sync_prompt_doc_hint(
                custom_prompt=custom_prompt,
                applicable_documents=[str(item) for item in (normalized.get("applicable_documents") or []) if str(item).strip()],
            )

        return normalized

    @staticmethod
    def _sync_prompt_doc_hint(*, custom_prompt: str, applicable_documents: List[str]) -> str:
        """
        运行时同步 prompt 中“适用文书”提示，避免历史写死的 operation_record/progress_note
        与当前规则文书标签不一致。
        """
        if not custom_prompt or "{applicable_documents}" in custom_prompt:
            return custom_prompt
        docs_text = "、".join(applicable_documents) if applicable_documents else "未指定"
        pattern = re.compile(r"(适用文书[:：]\s*)([^\n]+)")
        if not pattern.search(custom_prompt):
            return custom_prompt
        return pattern.sub(rf"\1{docs_text}", custom_prompt, count=1)

    async def reload_config(self, config_name: str = "default", user_id: Optional[str] = None) -> bool:
        """
        重新加载 LLM 配置

        Args:
            config_name: 配置名称，默认为 "default"
            user_id: 用户 ID，如果为 None 则加载全局配置

        Returns:
            是否成功重新加载配置
        """
        success = await LLMConfigLoader.reload_config_for_service(self, config_name, user_id)
        if success:
            first_pass_config = {
                "provider_code": self.client.provider_code,
                "api_endpoint": self.client.api_endpoint,
                "api_key": self.client.api_key,
                "model": self.client.model,
                "timeout_seconds": self.client.timeout_seconds,
                "allow_mock_when_unconfigured": self.client.allow_mock_when_unconfigured,
                "source": self.client.config_source,
                "custom_parameters": {
                    "temperature": self.client.temperature,
                    "top_p": self.client.top_p,
                    "max_tokens": self.client.max_tokens,
                    "enable_thinking": self.client.enable_thinking,
                    "reasoning_effort": self.client.reasoning_effort,
                },
            }
            self.adjudicator_client = SichuanQCLLMClient(build_adjudicator_runtime_config(first_pass_config))
            # 同步最新截断配置到 service 与 prompt_builder
            settings = get_settings()
            self.enable_truncate = settings.LLM_ENABLE_TRUNCATE
            self.max_content_length = settings.LLM_MAX_CONTENT_LENGTH
            self.prompt_builder.enable_truncate = self.enable_truncate
            self.prompt_builder.max_content_length = self.max_content_length
        return success

    def _load_rules_from_json(self) -> List[Dict[str, Any]]:
        """
        从 JSON 文件加载四川省规则（带缓存）
        """
        if self._rules_cache is not None:
            return self._rules_cache

        try:
            with self._sc_rules_json_path.open("r", encoding="utf-8") as f:
                rules = json.load(f)

            # 转换 applicable_documents 从英文到中文
            for rule in rules:
                applicable_docs = rule.get("applicable_documents", [])
                if applicable_docs:
                    rule["applicable_documents"] = [
                        self.doc_type_mapping.get(doc, doc)
                        for doc in applicable_docs
                    ]
                normalized_rule = self._ensure_rule_execution_meta(rule)
                rule.clear()
                rule.update(normalized_rule)

            self._rules_cache = rules
            logger.info(f"从 JSON 文件加载了 {len(rules)} 条四川省规则")
            return rules
        except Exception as e:
            logger.error(f"从 JSON 文件加载规则失败: {e}", exc_info=True)
            return []

    def _load_custom_rules_from_json(self) -> List[Dict[str, Any]]:
        """
        从 JSON 文件加载自定义规则（泸县33条规则）
        """
        if self._custom_rules_cache is not None:
            return self._custom_rules_cache

        try:
            with self._custom_rules_json_path.open("r", encoding="utf-8") as f:
                rules = json.load(f)

            # 转换 applicable_documents 从英文到中文
            for rule in rules:
                applicable_docs = rule.get("applicable_documents", [])
                if applicable_docs:
                    rule["applicable_documents"] = [
                        self.doc_type_mapping.get(doc, doc)
                        for doc in applicable_docs
                    ]
                normalized_rule = self._ensure_rule_execution_meta(rule)
                rule.clear()
                rule.update(normalized_rule)

            self._custom_rules_cache = rules
            logger.info(f"从 JSON 文件加载了 {len(rules)} 条自定义规则")
            return rules
        except Exception as e:
            logger.error(f"从 JSON 文件加载自定义规则失败: {e}", exc_info=True)
            return []

    def _load_customer_rules_from_json(self) -> List[Dict[str, Any]]:
        """
        从 JSON 文件加载客户专项规则
        """
        if self._customer_rules_cache is not None:
            return self._customer_rules_cache

        try:
            rules = [dict(item) for item in load_customer_luxian_rules()]

            for rule in rules:
                applicable_docs = rule.get("applicable_documents", [])
                if applicable_docs:
                    rule["applicable_documents"] = [
                        self.doc_type_mapping.get(doc, doc)
                        for doc in applicable_docs
                    ]
                normalized_rule = self._ensure_rule_execution_meta(rule)
                rule.clear()
                rule.update(normalized_rule)

            self._customer_rules_cache = rules
            logger.info(f"从 JSON 文件加载了 {len(rules)} 条客户专项规则")
            return rules
        except Exception as e:
            logger.error(f"从 JSON 文件加载客户专项规则失败: {e}", exc_info=True)
            return []

    def _normalize_rule_documents(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(rule or {})
        applicable_docs = normalized.get("applicable_documents", [])
        if applicable_docs:
            mapped_docs = [
                self.doc_type_mapping.get(doc, doc)
                for doc in applicable_docs
            ]
            dedup_docs: List[str] = []
            seen_docs: set[str] = set()
            for doc in mapped_docs:
                doc_text = str(doc)
                if doc_text in seen_docs:
                    continue
                seen_docs.add(doc_text)
                dedup_docs.append(doc_text)
            normalized["applicable_documents"] = dedup_docs
        return self._ensure_rule_execution_meta(normalized)

    @staticmethod
    def _rule_asset_checksum(rules: List[Dict[str, Any]]) -> str:
        payload = []
        for rule in rules:
            payload.append({
                "rule_id": str(rule.get("rule_id") or ""),
                "rule_version": str(rule.get("rule_version") or ""),
                "prompt_version": str(rule.get("prompt_version") or ""),
                "executor_type": str(rule.get("executor_type") or ""),
            })
        payload.sort(key=lambda item: item["rule_id"])
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _is_prod_env(self) -> bool:
        return str(get_settings().ENV or "").strip().lower() == "production"

    def _is_sc_source_strict_enabled(self) -> bool:
        settings = get_settings()
        strict_flag = bool(getattr(settings, "QC_SC_RULE_SOURCE_STRICT", False))
        return self._is_prod_env() or strict_flag

    def _should_block_batch_on_fallback(self) -> bool:
        settings = get_settings()
        block_flag = bool(getattr(settings, "QC_SC_RULE_SOURCE_BLOCK_BATCH_ON_FALLBACK", False))
        return self._is_prod_env() or block_flag

    def _load_sc_rule_family_map(self) -> Dict[str, str]:
        if self._sc_rule_family_map_cache is None:
            self._sc_rule_family_map_cache = load_sc_rule_family_map()
        return dict(self._sc_rule_family_map_cache)

    def _emit_sc_source_alert(self, message: str, *, source: str, context: str) -> None:
        settings = get_settings()
        dedup_seconds = max(0, int(getattr(settings, "QC_SC_RULE_SOURCE_ALERT_DEDUP_SECONDS", 300) or 0))
        now = time.time()
        alert_key = f"{context}|{source}|{self._active_sc_rules_checksum[:16]}|{self._last_registry_error or ''}"
        if dedup_seconds > 0 and alert_key == self._last_source_alert_key and (now - self._last_source_alert_at) < dedup_seconds:
            return

        self._last_source_alert_key = alert_key
        self._last_source_alert_at = now
        logger.error(
            "【规则来源告警】%s | context=%s source=%s checksum=%s registry_error=%s",
            message,
            context,
            source,
            self._active_sc_rules_checksum[:12],
            self._last_registry_error or "",
        )

    def assert_sc_rule_source_ready(self, *, context: str, block_batch: bool = False) -> Dict[str, Any]:
        overview = self.get_rule_source_overview()
        source = str(overview.get("sc_source") or "").strip() or "unknown"
        strict_mode = self._is_sc_source_strict_enabled()
        batch_block_enabled = self._should_block_batch_on_fallback()
        healthy = source == "pg_governance"

        if healthy:
            return overview

        reason = (
            f"SC 规则来源异常（source={source}），期望 pg_governance；"
            "已触发治理告警。"
        )
        self._emit_sc_source_alert(reason, source=source, context=context)
        should_block = strict_mode or (block_batch and batch_block_enabled)
        if should_block:
            raise RuleSourceGuardError(f"{reason} 当前请求已被阻断。")
        return overview

    def _load_active_sc_rules(self) -> List[Dict[str, Any]]:
        """
        优先从规则治理表加载 SC 规则；不可用时回退本地 JSON。
        """
        if self._active_sc_rules_cache is not None:
            return self._active_sc_rules_cache

        rules: List[Dict[str, Any]] = []
        source = "json_file"
        try:
            loaded_rules, source = self.rule_registry.load_active_rules()
            for rule in loaded_rules:
                rule_id = str(rule.get("rule_id") or "").strip().upper()
                if not rule_id.startswith("SC-"):
                    continue
                rules.append(self._normalize_rule_documents(rule))
        except Exception as exc:
            self._last_registry_error = str(exc)
            logger.warning("从规则治理表加载 SC 规则失败，回退 JSON: %s", exc, exc_info=True)
            rules = []
            source = "json_file"

        if not rules:
            rules = [
                self._normalize_rule_documents(rule)
                for rule in self._load_rules_from_json()
                if str(rule.get("rule_id") or "").strip().upper().startswith("SC-")
            ]
            source = "json_file"

        checksum = self._rule_asset_checksum(rules)
        if self._active_sc_rules_checksum and checksum != self._active_sc_rules_checksum:
            logger.warning(
                "SC 规则资产版本变化: source=%s old=%s new=%s",
                source,
                self._active_sc_rules_checksum[:12],
                checksum[:12],
            )
        self._active_sc_rules_checksum = checksum
        self._active_sc_rules_source = source
        self._active_sc_rules_cache = rules
        logger.info("已加载 %s 条 SC 规则（source=%s）", len(rules), source)
        return rules

    def invalidate_rule_cache(self) -> None:
        self._active_sc_rules_cache = None
        self._rules_cache = None
        self._custom_rules_cache = None
        self._customer_rules_cache = None
        self._sc_rule_family_map_cache = None
        invalidate_customer_rule_set_cache()

    def get_rule_source_overview(self) -> Dict[str, Any]:
        self._load_active_sc_rules()
        strict_mode = self._is_sc_source_strict_enabled()
        batch_block_enabled = self._should_block_batch_on_fallback()
        source = str(self._active_sc_rules_source or "").strip() or "unknown"
        healthy = source == "pg_governance"
        return {
            "sc_source": source,
            "sc_source_expected": "pg_governance",
            "sc_source_healthy": healthy,
            "sc_rule_count": len(self._active_sc_rules_cache or []),
            "sc_checksum": self._active_sc_rules_checksum,
            "last_registry_error": self._last_registry_error,
            "strict_mode": strict_mode,
            "batch_block_on_fallback": batch_block_enabled,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_sc_rules_for_rule_family_poc(self) -> List[Dict[str, Any]]:
        self.assert_sc_rule_source_ready(context="rule_family_ab_poc", block_batch=True)
        sc_mapping = self._load_sc_rule_family_map()
        report = validate_sc_rule_family_map(sc_mapping)
        if not report["ok"]:
            raise ValueError(
                "SC rule_family 映射未准备好: "
                f"missing={len(report['missing_rule_ids'])} "
                f"invalid={len(report['invalid_families'])} "
                f"extra={len(report['extra_rule_ids'])}"
            )

        rules: List[Dict[str, Any]] = []
        seen_rule_ids: set[str] = set()
        for rule in self._load_active_sc_rules():
            rule_id = str(rule.get("rule_id") or "").strip().upper()
            if rule_id not in sc_mapping or rule_id in seen_rule_ids:
                continue
            seen_rule_ids.add(rule_id)
            rules.append(self._normalize_rule_documents(rule))

        missing_active = sorted(set(sc_mapping.keys()) - seen_rule_ids)
        if missing_active:
            raise ValueError(f"治理表缺少 POC 规则: {', '.join(missing_active[:10])}")

        rules.sort(key=lambda item: str(item.get("rule_id") or ""))
        return rules

    async def bootstrap_rule_registry(self, *, operator: str = "system", mark_published: bool = True) -> Dict[str, int]:
        result_sc = self.rule_registry.bootstrap_rules_from_json_to_pg(
            operator=operator,
            mark_published=mark_published,
        )
        custom_registry = QCRuleRegistryService(
            json_path=self._custom_rules_json_path,
        )
        result_custom = custom_registry.bootstrap_rules_from_json_to_pg(
            operator=operator,
            mark_published=mark_published,
        )
        customer_registry = QCRuleRegistryService(
            json_path=self._customer_rules_json_path,
        )
        result_customer = customer_registry.bootstrap_rules_from_json_to_pg(
            operator=operator,
            mark_published=mark_published,
        )
        self.invalidate_rule_cache()
        return {
            "inserted": (
                int(result_sc.get("inserted", 0))
                + int(result_custom.get("inserted", 0))
                + int(result_customer.get("inserted", 0))
            ),
            "skipped": (
                int(result_sc.get("skipped", 0))
                + int(result_custom.get("skipped", 0))
                + int(result_customer.get("skipped", 0))
            ),
            "published": (
                int(result_sc.get("published", 0))
                + int(result_custom.get("published", 0))
                + int(result_customer.get("published", 0))
            ),
            "inserted_sc": int(result_sc.get("inserted", 0)),
            "inserted_lx_lxe": int(result_custom.get("inserted", 0)),
            "inserted_cl": int(result_customer.get("inserted", 0)),
            "skipped_sc": int(result_sc.get("skipped", 0)),
            "skipped_lx_lxe": int(result_custom.get("skipped", 0)),
            "skipped_cl": int(result_customer.get("skipped", 0)),
            "published_sc": int(result_sc.get("published", 0)),
            "published_lx_lxe": int(result_custom.get("published", 0)),
            "published_cl": int(result_customer.get("published", 0)),
        }

    def list_rule_versions(self, *, rule_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.rule_registry.list_rule_versions(rule_id=rule_id, limit=limit)

    def list_rule_publish_history(self, *, rule_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self.rule_registry.list_publish_history(rule_id=rule_id, limit=limit)

    def publish_rule_version(
        self,
        *,
        rule_id: str,
        version_no: int,
        operator: str = "system",
        reason: str = "manual publish",
    ) -> bool:
        ok = self.rule_registry.publish_rule_version(
            rule_id=rule_id,
            version_no=version_no,
            operator=operator,
            reason=reason,
        )
        if ok:
            self.invalidate_rule_cache()
        return ok

    def rollback_rule_version(
        self,
        *,
        rule_id: str,
        version_no: int,
        operator: str = "system",
        reason: str = "manual rollback",
    ) -> bool:
        ok = self.rule_registry.rollback_rule_version(
            rule_id=rule_id,
            version_no=version_no,
            operator=operator,
            reason=reason,
        )
        if ok:
            self.invalidate_rule_cache()
        return ok

    @staticmethod
    def _rule_id_prefix(rule_id: str) -> str:
        rid = str(rule_id or "").strip().upper()
        if rid.startswith("SC-"):
            return "SC"
        if rid.startswith("LXE-"):
            return "LXE"
        if rid.startswith("LX-"):
            return "LX"
        return "OTHER"

    def _family_counts(self, rule_ids: List[str]) -> Dict[str, int]:
        counts = {"SC": 0, "LX": 0, "LXE": 0, "OTHER": 0}
        for rule_id in rule_ids:
            key = self._rule_id_prefix(rule_id)
            counts[key] = int(counts.get(key, 0)) + 1
        return counts

    @staticmethod
    def _rule_payload_digest(rule: Dict[str, Any]) -> str:
        normalized = {
            "rule_id": str(rule.get("rule_id") or "").strip().upper(),
            "name": str(rule.get("name") or "").strip(),
            "description": str(rule.get("description") or "").strip(),
            "category": str(rule.get("category") or "").strip(),
            "defect_level": str(rule.get("defect_level") or "").strip(),
            "complexity": str(rule.get("complexity") or "").strip(),
            "applicable_documents": list(rule.get("applicable_documents") or []),
            "custom_prompt": str(rule.get("custom_prompt") or "").strip(),
            "executor_type": str(rule.get("executor_type") or "").strip().lower(),
            "execution_domain": str(rule.get("execution_domain") or "").strip().lower(),
            "doc_scope": str(rule.get("doc_scope") or "").strip().lower(),
            "rule_version": str(rule.get("rule_version") or "").strip(),
            "prompt_version": str(rule.get("prompt_version") or "").strip(),
            "cost_class": str(rule.get("cost_class") or "").strip().lower(),
        }
        raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def check_rule_registry_consistency(
        self,
        *,
        include_custom_rules: bool = True,
        sample_limit: int = 100,
    ) -> Dict[str, Any]:
        """
        发布前后规则一致性校验：
        - active(治理表) 与 baseline(JSON) 的 rule_id 集合差异
        - 重叠规则 payload 摘要差异（checksum）
        """
        sample_n = max(10, min(500, int(sample_limit or 100)))
        active_rules, active_source = self.rule_registry.load_active_rules()
        active_map: Dict[str, Dict[str, Any]] = {}
        for rule in active_rules:
            rid = str(rule.get("rule_id") or "").strip().upper()
            if rid:
                active_map[rid] = self._normalize_rule_documents(rule)

        baseline_map: Dict[str, Dict[str, Any]] = {}
        for rule in self._load_rules_from_json():
            rid = str(rule.get("rule_id") or "").strip().upper()
            if rid:
                baseline_map[rid] = self._normalize_rule_documents(rule)
        if include_custom_rules:
            for rule in self._load_custom_rules_from_json():
                rid = str(rule.get("rule_id") or "").strip().upper()
                if rid:
                    baseline_map[rid] = self._normalize_rule_documents(rule)
            for rule in self._load_customer_rules_from_json():
                rid = str(rule.get("rule_id") or "").strip().upper()
                if rid:
                    baseline_map[rid] = self._normalize_rule_documents(rule)

        baseline_ids = set(baseline_map.keys())
        active_ids = set(active_map.keys())
        missing_in_registry = sorted(baseline_ids - active_ids)
        extra_in_registry = sorted(active_ids - baseline_ids)

        changed_payload_ids: List[str] = []
        for rid in sorted(baseline_ids.intersection(active_ids)):
            baseline_digest = self._rule_payload_digest(baseline_map[rid])
            active_digest = self._rule_payload_digest(active_map[rid])
            if baseline_digest != active_digest:
                changed_payload_ids.append(rid)

        is_consistent = (
            active_source == "pg_governance"
            and not missing_in_registry
            and not extra_in_registry
            and not changed_payload_ids
        )

        return {
            "ok": bool(is_consistent),
            "active_source": str(active_source),
            "active_rule_count": len(active_ids),
            "baseline_rule_count": len(baseline_ids),
            "family_counts_active": self._family_counts(list(active_ids)),
            "family_counts_baseline": self._family_counts(list(baseline_ids)),
            "missing_in_registry_count": len(missing_in_registry),
            "extra_in_registry_count": len(extra_in_registry),
            "changed_payload_count": len(changed_payload_ids),
            "missing_in_registry_samples": missing_in_registry[:sample_n],
            "extra_in_registry_samples": extra_in_registry[:sample_n],
            "changed_payload_samples": changed_payload_ids[:sample_n],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _load_applicable_rules(self, document_type: str) -> List[Dict[str, Any]]:
        """
        加载适用于指定文书类型的质控规则。

        Args:
            document_type: 文书类型（如 "病程记录"、"入院记录" 等）

        Returns:
            适用规则列表。如果加载失败，返回空列表。

        规则筛选逻辑：
        1. 通用规则（applicable_documents 为空）会被包含
        2. 特定规则（applicable_documents 包含指定的 document_type）会被包含
        """
        sc_rules = self._load_active_sc_rules()
        custom_rules = self._load_custom_rules_from_json()
        customer_rules = self._load_customer_rules_from_json()
        # 合并并按 rule_id 去重，避免 LX 规则在两份文件中重复执行。
        merged_rules: Dict[str, Dict[str, Any]] = {}
        extra_rules: List[Dict[str, Any]] = []

        for rule in [*sc_rules, *custom_rules, *customer_rules]:
            rule_key = str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
            if rule_key:
                # custom_rules 在后，允许覆盖同 ID 的基础规则
                merged_rules[rule_key] = rule
            else:
                extra_rules.append(rule)

        all_rules = [*merged_rules.values(), *extra_rules]
        if not all_rules:
            return []

        # 兼容旧文书类型别名：
        # - "病程记录"/course_record/progress_note -> 首次+日常+上级+抢救
        raw_doc_type = (document_type or "").strip()
        canonical_doc_type = self.doc_type_mapping.get(raw_doc_type, raw_doc_type)
        target_doc_types = {canonical_doc_type}
        if raw_doc_type in {"course_record", "progress_note"} or canonical_doc_type == "病程记录":
            target_doc_types.update({"首次病程记录", "日常病程记录", "上级查房记录", "抢救记录"})

        # 筛选适用于当前文书类型的规则
        applicable_rules = [
            rule for rule in all_rules
            if not rule.get("applicable_documents")
            or bool(target_doc_types.intersection(set(rule.get("applicable_documents", []))))
        ]

        logger.info(
            "加载了 %s/%s 条适用于 '%s' 的规则（SC source=%s, 匹配类型=%s）",
            len(applicable_rules),
            len(all_rules),
            document_type,
            self._active_sc_rules_source,
            sorted(target_doc_types),
        )
        return applicable_rules

    # ──────────────────────────────────────────────
    # 以下方法委托给 QCPromptBuilder（拆分出的模块）
    # 保留方法签名以兼容现有调用
    # ──────────────────────────────────────────────

    def _smart_truncate(self, content: str, max_length: int = 4000) -> str:
        return self.prompt_builder.smart_truncate(content, max_length)

    def _extract_check_points(self, custom_prompt: str) -> str:
        return self.prompt_builder.extract_check_points(custom_prompt)

    def _extract_core_guidance(self, custom_prompt: str) -> str:
        return self.prompt_builder.extract_core_guidance(custom_prompt)

    def _extract_enhanced_guidance(self, custom_prompt: str, rule_id: str) -> str:
        return self.prompt_builder.extract_enhanced_guidance(custom_prompt, rule_id)

    def _precompute_time_facts(self, rule_id: str, content: str) -> str:
        return self.prompt_builder.precompute_time_facts(rule_id, content)

    async def _build_prompt(
        self,
        rules: List[Dict[str, Any]],
        content: str,
        document_type: str,
        prompt_mode: str = "plan_a"
    ) -> str:
        return await self.prompt_builder.build_prompt(rules, content, document_type, prompt_mode)


    async def _evaluate_rules_orchestrated(
        self,
        *,
        document_id: str,
        content: str,
        document_type: str,
        rules: List[Dict[str, Any]],
        evidence_source: str = "medical_text",
        evidence_payload: Optional[Dict[str, Any]] = None,
        bucket_strategy: str = "domain_only",
        quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
        batch_output_mode: str = BATCH_OUTPUT_MODE_FULL,
        enable_selective_refine: bool = False,
        refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
        max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
        use_execution_cache: bool = True,
        rule_set_key: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        raise_if_cancelled(cancellation_check)
        prepared_rules = [self._ensure_rule_execution_meta(rule) for rule in rules]
        settings = get_settings()
        normalized_rule_set_key = str(rule_set_key or "").strip()
        is_luxian_0609 = normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY
        luxian_aggregation_enabled = bool(
            is_luxian_0609 and settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED
        )
        luxian_trigger_gate_enabled = bool(
            luxian_aggregation_enabled and settings.LUXIAN_0609_TRIGGER_GATE_ENABLED
        )
        luxian_evidence_formatter_enabled = bool(
            is_luxian_0609 and settings.LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED
        )
        luxian_wrapper_rules: List[Dict[str, Any]] = []
        luxian_gate_decisions = {}
        quality_profile_normalized = normalize_quality_profile(quality_profile)
        batch_output_mode_normalized = normalize_batch_output_mode(
            batch_output_mode,
            quality_profile=quality_profile_normalized,
        )
        max_refine_candidates_normalized = normalize_max_refine_candidates(max_refine_candidates)
        model_version = str(self.client.model or "")
        llm_concurrency = 6

        async def _llm_evaluate(rule: Dict[str, Any], medical_record: Dict[str, Any]) -> Dict[str, Any]:
            return await self.rule_engine.evaluate(rule, medical_record=medical_record)

        medical_record: Dict[str, Any] = {
            "id": document_id,
            "content": content,
            "document_type": document_type,
        }
        if isinstance(evidence_payload, dict) and evidence_payload:
            medical_record["evidence_payload"] = dict(evidence_payload)

        executable_rules = prepared_rules
        if luxian_aggregation_enabled:
            luxian_wrapper_rules = load_luxian_0609_rules()
            if luxian_trigger_gate_enabled:
                luxian_gate_decisions = evaluate_luxian_0609_trigger_gates(
                    rules=luxian_wrapper_rules,
                    visit_id=str(document_id or ""),
                    medical_text=content,
                    evidence_payload=evidence_payload,
                )
                executable_rules = filter_executable_rules_by_gate(
                    executable_rules=prepared_rules,
                    wrapper_rules=luxian_wrapper_rules,
                    decisions=luxian_gate_decisions,
                )

        orchestrated = await self.rule_orchestrator.evaluate_rules(
            rules=executable_rules,
            medical_record=medical_record,
            llm_evaluate=_llm_evaluate,
            llm_batch_evaluate=self._llm_evaluate_batch_compact,
            prompt_strategy="batch_compact_v1",
            batch_pack_candidates=(3, 5, 8, 10, 12, 15),
            batch_pack_max_size=15,
            evidence_source=evidence_source,
            llm_concurrency=llm_concurrency,
            model_version=model_version,
            bucket_strategy=bucket_strategy,
            quality_profile=quality_profile_normalized,
            batch_output_mode=batch_output_mode_normalized,
            refine_confidence_threshold=refine_confidence_threshold,
            execution_cache=self.execution_cache if use_execution_cache else None,
            cache_ttl_seconds=1800,
            cancellation_check=cancellation_check,
        )
        orchestrated["quality_profile"] = quality_profile_normalized
        orchestrated["batch_output_mode"] = batch_output_mode_normalized
        if is_luxian_0609:
            orchestrated["rule_set_key"] = normalized_rule_set_key
            orchestrated["luxian_0609_execution_rule_count"] = len(prepared_rules)
            orchestrated["luxian_0609_executed_rule_count"] = len(executable_rules)
            if luxian_trigger_gate_enabled:
                orchestrated["luxian_0609_trigger_gate"] = {
                    rule_id: decision.to_metadata()
                    for rule_id, decision in luxian_gate_decisions.items()
                }

        if enable_selective_refine:
            refined = await self._apply_selective_refine(
                orchestrated=orchestrated,
                rules=executable_rules,
                medical_record=medical_record,
                refine_confidence_threshold=refine_confidence_threshold,
                max_refine_candidates=max_refine_candidates_normalized,
            )
            orchestrated = refined
            orchestrated.setdefault("quality_profile", quality_profile_normalized)
            orchestrated.setdefault("batch_output_mode", batch_output_mode_normalized)
            if not luxian_aggregation_enabled:
                return orchestrated
        if luxian_aggregation_enabled:
            orchestrated.setdefault("results", [])
            orchestrated["results"].extend(
                evaluate_luxian_0609_programmatic_rules(
                    wrapper_rules=luxian_wrapper_rules,
                    evidence_payload=evidence_payload,
                )
            )
            customer_results = aggregate_luxian_0609_results(
                wrapper_rules=luxian_wrapper_rules,
                execution_results=list(orchestrated.get("results") or []),
                gate_decisions=luxian_gate_decisions,
                format_evidence=luxian_evidence_formatter_enabled,
                audit_context={
                    "visit_id": str(document_id or ""),
                    "model_name": model_version,
                    "evidence_payload": evidence_payload,
                },
            )
            orchestrated["luxian_0609_raw_result_count"] = len(orchestrated.get("results") or [])
            orchestrated["results"] = customer_results
            orchestrated["display_rule_ids"] = [
                str(rule.get("rule_id") or rule.get("rule_code") or "")
                for rule in luxian_wrapper_rules
            ]
            orchestrated["display_rule_count"] = len(customer_results)
            orchestrated["luxian_0609_summary"] = summarize_luxian_0609_results(customer_results)
            orchestrated.setdefault(
                "refine_summary",
                {
                    "enabled": bool(enable_selective_refine),
                    "candidate_count": 0,
                    "eligible_candidate_count": 0,
                    "refined_rule_count": 0,
                    "refine_failed_count": 0,
                    "budget_applied": max_refine_candidates_normalized if enable_selective_refine else 0,
                    "budget_skipped_count": 0,
                    "refine_reasons": {},
                },
            )
            return orchestrated
        orchestrated.setdefault(
            "refine_summary",
            {
                "enabled": False,
                "candidate_count": 0,
                "eligible_candidate_count": 0,
                "refined_rule_count": 0,
                "refine_failed_count": 0,
                "budget_applied": 0,
                "budget_skipped_count": 0,
                "refine_reasons": {},
            },
        )
        return orchestrated

    async def _llm_evaluate_batch_compact(
        self,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        enriched_record = dict(medical_record or {})
        enriched_record["execution_domain"] = str(options.get("execution_domain") or enriched_record.get("execution_domain") or "")
        enriched_record["doc_scope"] = str(options.get("doc_scope") or enriched_record.get("doc_scope") or "")
        enriched_record["quality_profile"] = str(options.get("quality_profile") or enriched_record.get("quality_profile") or "")
        enriched_record["model_version"] = str(options.get("model_version") or self.client.model or "")
        return await self.rule_engine.evaluate_batch_compact(
            rules=rules,
            medical_record=enriched_record,
            pack_id=str(options.get("pack_id") or ""),
            pack_size=int(options.get("pack_size") or len(rules)),
            low_confidence_threshold=float(options.get("low_confidence_threshold") or 0.45),
            context_token_budget=8600 if normalize_quality_profile(options.get("quality_profile")) == QUALITY_PROFILE_EFFECT_PRIORITY else 7000,
            quality_profile=normalize_quality_profile(options.get("quality_profile")),
            batch_output_mode=normalize_batch_output_mode(
                options.get("batch_output_mode"),
                quality_profile=normalize_quality_profile(options.get("quality_profile")),
            ),
        )

    async def _apply_selective_refine(
        self,
        *,
        orchestrated: Dict[str, Any],
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
        max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
    ) -> Dict[str, Any]:
        results = list(orchestrated.get("results") or [])
        rules_by_id = {
            str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper(): dict(rule)
            for rule in list(rules or [])
            if str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
        }
        raw_candidates = select_refine_candidates(
            results,
            rules_by_id=rules_by_id,
            confidence_threshold=refine_confidence_threshold,
        )
        ineligible_candidates = [
            candidate
            for candidate in raw_candidates
            if not bool((candidate.get("rule") or {}).get("allow_selective_refine") is True)
        ]
        eligible_candidates = [
            candidate
            for candidate in raw_candidates
            if bool((candidate.get("rule") or {}).get("allow_selective_refine") is True)
        ]
        eligible_candidates.sort(
            key=lambda candidate: self._refine_candidate_priority(candidate),
            reverse=True,
        )
        refine_budget = normalize_max_refine_candidates(max_refine_candidates)
        candidates = eligible_candidates[:refine_budget] if refine_budget > 0 else []
        skipped_candidates = eligible_candidates[refine_budget:] if refine_budget > 0 else eligible_candidates

        for skipped in [*ineligible_candidates, *skipped_candidates]:
            skipped_rule_id = str(skipped.get("rule_id") or "").strip().upper()
            for item in results:
                if str(item.get("rule_id") or "").strip().upper() != skipped_rule_id:
                    continue
                metadata = dict(item.get("metadata") or {})
                metadata.setdefault("qc_stage", "screening")
                metadata.setdefault("refined", False)
                metadata["final_decision_source"] = "batch"
                if skipped in ineligible_candidates:
                    metadata["refine_skipped"] = "rule_policy"
                else:
                    metadata["refine_skipped"] = "budget"
                item["metadata"] = metadata
                break

        refined_by_rule: Dict[str, Dict[str, Any]] = {}
        refine_reasons_by_rule: Dict[str, str] = {}
        refine_details: List[Dict[str, Any]] = []
        extra_tokens = 0
        extra_api_time = 0.0

        for candidate in candidates:
            rule_id = str(candidate.get("rule_id") or "").strip().upper()
            rule = dict(candidate.get("rule") or rules_by_id.get(rule_id) or {})
            reason = str(candidate.get("refine_reason") or "")
            refine_reasons_by_rule[rule_id] = reason
            try:
                refined = await self.rule_engine.evaluate(rule, medical_record=medical_record)
                metadata = dict(refined.get("metadata") or {})
                metadata["qc_stage"] = "refine"
                metadata["refined"] = True
                metadata["refine_reason"] = reason
                metadata["screening_status"] = str((candidate.get("screening_result") or {}).get("status") or "")
                metadata["final_decision_source"] = "single_refine"
                metadata.setdefault("quality_profile", QUALITY_PROFILE_EFFECT_PRIORITY)
                refined["metadata"] = metadata
                refined_by_rule[rule_id] = refined
                extra_tokens += int(metadata.get("tokens_used") or 0)
                extra_api_time += float(metadata.get("api_time") or 0.0)
                refine_details.append(
                    {
                        "rule_id": rule_id,
                        "refine_reason": reason,
                        "screening_status": metadata.get("screening_status"),
                        "refined_status": refined.get("status"),
                        "refine_failed": False,
                    }
                )
            except Exception as exc:
                logger.warning("选择性精审失败，保留批量筛查结论: rule_id=%s", rule_id, exc_info=True)
                for item in results:
                    if str(item.get("rule_id") or "").strip().upper() == rule_id:
                        metadata = dict(item.get("metadata") or {})
                        metadata["qc_stage"] = "screening"
                        metadata["refined"] = False
                        metadata["refine_failed"] = True
                        metadata["refine_error"] = str(exc)
                        metadata["refine_reason"] = reason
                        metadata["final_decision_source"] = "batch"
                        item["metadata"] = metadata
                        break
                refine_details.append(
                    {
                        "rule_id": rule_id,
                        "refine_reason": reason,
                        "screening_status": str((candidate.get("screening_result") or {}).get("status") or ""),
                        "refined_status": "",
                        "refine_failed": True,
                        "error": str(exc),
                    }
                )

        merged_results, merge_summary = merge_refined_results(
            screening_results=results,
            refined_results_by_rule=refined_by_rule,
            refine_reasons_by_rule=refine_reasons_by_rule,
        )
        refined = dict(orchestrated)
        refined["results"] = merged_results
        refined["total_tokens"] = int(orchestrated.get("total_tokens") or 0) + extra_tokens
        refined["total_api_time"] = float(orchestrated.get("total_api_time") or 0.0) + extra_api_time
        refined["refine_details"] = refine_details
        refined["refine_summary"] = {
            "enabled": True,
            "candidate_count": len(raw_candidates),
            "eligible_candidate_count": len(eligible_candidates),
            **merge_summary,
            "budget_applied": refine_budget,
            "budget_skipped_count": len(skipped_candidates),
        }
        refined["refined_rule_count"] = int(merge_summary.get("refined_rule_count") or 0)
        refined["refine_reasons"] = dict(merge_summary.get("refine_reasons") or {})
        return refined

    @staticmethod
    def _refine_candidate_priority(candidate: Dict[str, Any]) -> Tuple[int, int, float]:
        screening_result = dict(candidate.get("screening_result") or {})
        reason_text = str(candidate.get("refine_reason") or "")
        reasons = {item.strip() for item in reason_text.split(",") if item.strip()}
        rule = dict(candidate.get("rule") or {})
        defect_level = str(rule.get("defect_level") or screening_result.get("defect_level") or "")
        confidence = float(screening_result.get("confidence") or 0.0)

        priority = 0
        if "logical_contradiction" in reasons:
            priority += 100
        if str(screening_result.get("status") or "").strip().lower() == "non_compliant":
            priority += 60
        if any(reason.startswith("high_risk_family:") for reason in reasons):
            priority += 40
        if "severe_non_compliant" in reasons or ("严重" in defect_level or "重度" in defect_level):
            priority += 30
        if "uncertain" in reasons:
            priority += 10
        if "low_confidence" in reasons:
            priority += 5

        reason_count = len(reasons)
        return priority, reason_count, 1 - confidence

    async def _resolve_rules_for_document(
        self,
        *,
        document_type: str,
        rule_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        rules = await self._load_applicable_rules(document_type)
        if not rule_ids:
            return rules

        selected_rules: List[Dict[str, Any]] = []
        for rid in rule_ids:
            try:
                rule = self.get_rule_by_id(str(rid))
                if rule:
                    selected_rules.append(rule)
            except Exception as e:
                logger.warning(f"get_rule_by_id 失败: {rid} -> {e}")

        if selected_rules:
            logger.info(f"Selected {len(selected_rules)} rules via get_rule_by_id from IDs: {rule_ids}")
            return selected_rules

        filtered_rules = [
            r for r in rules
            if r.get("rule_id") in rule_ids or r.get("rule_code") in rule_ids or r.get("id") in rule_ids
        ]
        logger.info(f"Filtered to {len(filtered_rules)} rules based on rule_ids within loaded set: {rule_ids}")
        return filtered_rules

    def _build_document_evaluation_result(
        self,
        *,
        document_id: str,
        document_type: str,
        rules: List[Dict[str, Any]],
        orchestrated: Dict[str, Any],
    ) -> Dict[str, Any]:
        rule_results = list(orchestrated.get("results") or [])
        total_tokens = int(orchestrated.get("total_tokens") or 0)
        total_prompt_tokens = int(orchestrated.get("total_prompt_tokens") or 0)
        total_completion_tokens = int(orchestrated.get("total_completion_tokens") or 0)
        total_api_time = float(orchestrated.get("total_api_time") or 0.0)
        first_result_latency = float(orchestrated.get("first_result_latency") or 0.0)
        first_result_source = str(orchestrated.get("first_result_source") or "")
        cot_summary = dict(orchestrated.get("cot_summary") or {})

        display_rule_ids = list(orchestrated.get("display_rule_ids") or [])
        total_rules = int(orchestrated.get("display_rule_count") or len(rules))
        compliant_rules = sum(
            1 for r in rule_results
            if r.get("status") == "compliant"
        )
        not_applicable_count = sum(1 for r in rule_results if r.get("status") == "not_applicable")
        data_gap_count = sum(1 for r in rule_results if r.get("status") == "data_gap")
        not_executed_count = sum(1 for r in rule_results if r.get("status") == "not_executed")
        technical_error_count = sum(1 for r in rule_results if r.get("status") in {"technical_error", "technical_error_internal"})
        issues_found = sum(1 for r in rule_results if r.get("status") == "non_compliant")
        compliance_denominator = max(
            0,
            total_rules - not_applicable_count - data_gap_count - not_executed_count - technical_error_count,
        )
        compliance_rate = (compliant_rules / compliance_denominator * 100.0) if compliance_denominator else 100.0

        evaluation_results = []
        for item in rule_results:
            evaluation_results.append({
                "rule_id": item.get("rule_id"),
                "rule_name": item.get("rule_name"),
                "is_compliant": item.get("is_compliant"),
                "status": item.get("status"),
                "findings": item.get("findings"),
                "evidence": item.get("evidence"),
                "suggestion": item.get("suggestion"),
                "confidence": item.get("confidence"),
                "applicability": item.get("applicability"),
                "evidence_verified": item.get("evidence_verified"),
                "metadata": item.get("metadata"),
                "qc_point_id": item.get("qc_point_id"),
                "rule_set_key": item.get("rule_set_key"),
                "rule_set_version": item.get("rule_set_version"),
                "rule_version": item.get("rule_version"),
                "schema_version": item.get("schema_version"),
                "executor_type": item.get("executor_type"),
                "result_status": item.get("result_status"),
                "trigger": item.get("trigger"),
                "trigger_facts": item.get("trigger_facts"),
                "dependencies": item.get("dependencies"),
                "missing_sources": item.get("missing_sources"),
                "evidence_items": item.get("evidence_items"),
                "source_table": item.get("source_table"),
                "source_document": item.get("source_document"),
                "source_field": item.get("source_field"),
                "quote": item.get("quote"),
                "decision_summary": item.get("decision_summary"),
                "decision": item.get("decision"),
                "threshold": item.get("threshold"),
                "expected_value": item.get("expected_value"),
                "actual_value": item.get("actual_value"),
                "delta": item.get("delta"),
                "review": item.get("review"),
                "review_status": item.get("review_status"),
                "audit": item.get("audit"),
            })

        logger.info(
            f"质控评估完成: {compliant_rules}/{compliance_denominator} 条适用规则符合，"
            f"不适用 {not_applicable_count} 条，数据缺口 {data_gap_count} 条，合规率 {compliance_rate:.1f}%"
        )

        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": total_rules,
            "applicable_rules": display_rule_ids or [r.get("rule_code", r.get("id", "")) for r in rules],
            "evaluation_summary": {
                "compliance_rate": round(compliance_rate, 2),
                "issues_found": issues_found,
                "not_applicable": not_applicable_count,
                "data_gap_count": data_gap_count,
                "not_executed_count": not_executed_count,
                "technical_error_count": technical_error_count,
                "total_rules": total_rules,
                "compliance_denominator": compliance_denominator,
                "compliant_rules": compliant_rules,
                "model": self.client.model,
                "executor_breakdown": orchestrated.get("executor_breakdown") or {},
                "cache_breakdown": orchestrated.get("cache_breakdown") or {},
                "pack_metrics": orchestrated.get("pack_metrics") or {},
                "quality_profile": orchestrated.get("quality_profile") or QUALITY_PROFILE_THROUGHPUT,
                "refine_summary": orchestrated.get("refine_summary") or {},
                "refined_rule_count": int(orchestrated.get("refined_rule_count") or 0),
                "refine_reasons": orchestrated.get("refine_reasons") or {},
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "first_result_latency": first_result_latency,
                "first_result_source": first_result_source,
                "cot_summary": cot_summary,
                "luxian_0609_summary": orchestrated.get("luxian_0609_summary") or {},
            },
            "parsed_evaluation_results": rule_results,
            "evaluation_results": evaluation_results,
            "llm_output": None,
            "token_usage": {
                "total_tokens": total_tokens,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
            },
            "api_time": total_api_time,
            "first_result_latency": first_result_latency,
            "first_result_source": first_result_source,
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            "pack_metrics": orchestrated.get("pack_metrics") or {},
            "quality_profile": orchestrated.get("quality_profile") or QUALITY_PROFILE_THROUGHPUT,
            "refine_summary": orchestrated.get("refine_summary") or {},
            "refined_rule_count": int(orchestrated.get("refined_rule_count") or 0),
            "refine_reasons": orchestrated.get("refine_reasons") or {},
            "refine_details": orchestrated.get("refine_details") or [],
            "cot_summary": cot_summary,
            "trace": orchestrated.get("trace") or [],
            "luxian_0609_summary": orchestrated.get("luxian_0609_summary") or {},
        }

    async def _evaluate_rules_with_engine(
        self,
        document_id: str,
        content: str,
        document_type: str,
        rules: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int, float]:
        """
        使用统一规则引擎对一组规则执行质控。

        Returns:
            (results, total_tokens, total_api_time)
        """
        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules,
            evidence_source="medical_text",
        )
        return (
            list(orchestrated.get("results") or []),
            int(orchestrated.get("total_tokens") or 0),
            float(orchestrated.get("total_api_time") or 0.0),
        )



    def _parse_llm_json_response(self, llm_output: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        解析 LLM 返回的 JSON 格式评估结果

        Args:
            llm_output: LLM 原始输出文本
            rules: 适用规则列表（用于降级处理）

        Returns:
            解析后的评估结果列表，每条包含：
            - rule_id, rule_name, is_compliant, findings, evidence, location, suggestion, confidence
        """
        import json
        import re

        try:
            # 双保险：清理 Thinking 模型可能返回的 <think>...</think> 内容
            llm_output = re.sub(r"<think>[\s\S]*?</think>", "", llm_output or "", flags=re.IGNORECASE).strip()

            # 尝试提取 JSON 数组部分
            # 查找第一个 [ 和最后一个 ]
            json_start = llm_output.find('[')
            json_end = llm_output.rfind(']')

            if json_start == -1 or json_end == -1 or json_start >= json_end:
                logger.warning(f"LLM 输出中未找到有效的 JSON 数组边界")
                logger.debug(f"LLM 原始输出: {llm_output[:500]}...")
                return self._create_fallback_results(llm_output, rules)

            json_str = llm_output[json_start:json_end + 1]

            # 尝试解析 JSON
            parsed_results = json.loads(json_str)

            if not isinstance(parsed_results, list):
                logger.warning(f"LLM 返回的 JSON 不是数组格式")
                return self._create_fallback_results(llm_output, rules)

            # 验证和规范化每条结果
            normalized_results = []
            for idx, item in enumerate(parsed_results):
                if not isinstance(item, dict):
                    logger.warning(f"跳过非字典格式的结果项 #{idx}")
                    continue

                # 提取并规范化字段
                normalized_item = {
                    'rule_id': str(item.get('rule_id', f'RULE_{idx+1}')),
                    'rule_name': str(item.get('rule_name', '未命名规则')),
                    'is_compliant': bool(item.get('is_compliant', True)),
                    'findings': str(item.get('findings', '')),
                    'evidence': str(item.get('evidence', '')),
                    'location': str(item.get('location', '')),
                    'suggestion': str(item.get('suggestion', '')),
                    'confidence': float(item.get('confidence', 0.75))
                }

                normalized_results.append(normalized_item)

            if len(normalized_results) == 0:
                logger.warning(f"解析后的结果为空，使用降级方案")
                return self._create_fallback_results(llm_output, rules)

            logger.info(f"✅ 成功解析 LLM JSON 响应，共 {len(normalized_results)} 条规则评估结果")
            return normalized_results

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.debug(f"尝试解析的 JSON 字符串: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
            return self._create_fallback_results(llm_output, rules)
        except Exception as e:
            logger.error(f"解析 LLM 响应时发生未知错误: {e}")
            return self._create_fallback_results(llm_output, rules)

    def _create_fallback_results(self, llm_output: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        当 JSON 解析失败时，创建降级结果

        Args:
            llm_output: LLM 原始输出
            rules: 适用规则列表

        Returns:
            降级的评估结果列表
        """
        logger.warning(f"使用降级方案生成评估结果")

        # 创建一条汇总结果
        fallback_results = [{
            'rule_id': 'SUMMARY',
            'rule_name': '质控分析汇总',
            'is_compliant': True,  # 默认符合，避免误报
            'findings': '模型返回了非结构化的分析结果，请查看原始输出',
            'evidence': llm_output[:200] if llm_output else '（无输出）',
            'location': '整体评估',
            'suggestion': '建议人工复核质控结果',
            'confidence': 0.5
        }]

        return fallback_results

    @staticmethod
    def _find_source_documents_for_types(
        source_documents: List[Dict[str, Any]],
        doc_types: List[str],
    ) -> List[Dict[str, Any]]:
        wanted = {str(item or "").strip() for item in doc_types if str(item or "").strip()}
        matched = [
            dict(item)
            for item in source_documents or []
            if str(item.get("document_type") or item.get("source_table") or "").strip() in wanted
        ]
        matched.sort(
            key=lambda item: (
                0 if item.get("content") else 1,
                str(item.get("display_time") or item.get("record_time") or ""),
            )
        )
        return matched

    @staticmethod
    def _score_primary_candidate_for_rule(
        *,
        rule_id: str,
        candidate: Dict[str, Any],
    ) -> Tuple[int, int, str]:
        content = str(candidate.get("content") or "").strip()
        display_time = str(candidate.get("display_time") or candidate.get("record_time") or "")
        has_content = 1 if content else 0
        normalized_rule_id = str(rule_id or "").strip().upper()
        score = 0

        if normalized_rule_id == "SC-039" and content:
            lowered = content.lower()
            weighted_patterns = (
                ("危急值", 100),
                ("低钾", 90),
                ("静脉补钾", 80),
                ("补钾", 70),
                ("电解质", 20),
                ("查看患者", 20),
                ("复查", 10),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            if re.search(r"\bK\s*\d+(?:\.\d+)?\s*mmol/?l\b", lowered):
                score += 60
            if re.search(r"\bCa\s*\d+(?:\.\d+)?\s*mmol/?l\b", lowered):
                score += 10
            if re.search(r"\bMg\s*\d+(?:\.\d+)?\s*mmol/?l\b", lowered):
                score += 10
        elif normalized_rule_id in {"SC-050", "CL-037", "CL-275"} and content:
            weighted_patterns = (
                ("副主任医师查房", 60),
                ("代主治医师查房", 55),
                ("主治医师查房", 45),
                ("诊断依据", 35),
                ("鉴别诊断", 35),
                ("继续原方案", 10),
                ("治疗有效", 10),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content or keyword in str(candidate.get("document_title") or ""):
                    score += weight
            discharge_like_patterns = (
                "出院前查房",
                "办理出院",
                "同意出院",
                "出院医嘱",
                "门诊随访",
                "随访周期",
                "随访日期",
                "明日办理",
                "今日办理出院",
            )
            for keyword in discharge_like_patterns:
                if keyword in content or keyword in str(candidate.get("document_title") or ""):
                    score -= 120
        elif normalized_rule_id == "SC-146" and content:
            weighted_patterns = (
                ("手术", 70),
                ("明日行", 60),
                ("诊疗计划", 50),
                ("医嘱", 45),
                ("术前", 40),
                ("复查", 20),
                ("继续目前治疗方案", 10),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            if "出院情况" in content:
                score -= 40
            if "出院医嘱" in content:
                score -= 25
        elif normalized_rule_id == "SC-033" and content:
            weighted_patterns = (
                ("输注", 80),
                ("左氧氟沙星", 90),
                ("抗感染", 80),
                ("补钾", 85),
                ("静脉补", 75),
                ("停药", 65),
                ("改用", 60),
                ("处理", 55),
                ("对症", 45),
                ("复查", 30),
                ("瘙痒", 35),
                ("肿痛", 35),
                ("麻木", 35),
                ("不适", 20),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            discharge_like_patterns = (
                "办理出院",
                "出院医嘱",
                "门诊随访",
                "随访周期",
                "随访日期",
                "患者拒绝完善",
            )
            for keyword in discharge_like_patterns:
                if keyword in content:
                    score -= 70
            if "出院情况" in content:
                score -= 60
        elif normalized_rule_id == "SC-032" and content:
            compact = re.sub(r"\s+", "", content)
            if len(compact) < 180:
                score += 80
            weighted_patterns = (
                ("医师签名:", 90),
                ("医生签名:", 90),
                ("查体同前", 80),
                ("治疗方案上无特殊调整", 80),
                ("继续原方案", 45),
                ("密观", 35),
                ("无具体内容", 30),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            if "出院医嘱" in content or "办理出院" in content:
                score -= 60
        elif normalized_rule_id == "SC-026" and content:
            weighted_patterns = (
                ("鉴别诊断", 120),
                ("诊断依据", 100),
                ("目前诊断", 60),
                ("不除外", 55),
                ("待排", 45),
                ("辅助检查", 30),
                ("主诉", 25),
                ("查体", 25),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            discharge_like_patterns = (
                "办理出院",
                "出院医嘱",
                "症状缓解",
                "病情较前明显好转",
                "今日予以办理出院",
                "准许后今日办理出院",
            )
            for keyword in discharge_like_patterns:
                if keyword in content:
                    score -= 90
        elif normalized_rule_id in {"SC-023", "SC-024", "SC-025", "SC-027", "CL-273", "CL-274", "CL-276"} and content:
            weighted_patterns = (
                ("病例特点", 120 if normalized_rule_id in {"SC-023", "SC-024", "CL-273", "CL-274"} else 20),
                ("诊断依据", 120 if normalized_rule_id in {"SC-025", "CL-274", "CL-276"} else 35),
                ("鉴别诊断", 120 if normalized_rule_id in {"SC-025", "CL-274", "CL-276"} else 30),
                ("诊疗计划", 90 if normalized_rule_id in {"SC-025", "SC-027", "CL-276"} else 15),
                ("目前诊断", 45),
                ("主诉", 25),
                ("现病史", 25),
                ("辅助检查", 25),
                ("查体", 20),
            )
            for keyword, weight in weighted_patterns:
                if keyword in content:
                    score += weight
            discharge_like_patterns = (
                "办理出院",
                "出院医嘱",
                "症状缓解",
                "病情较前明显好转",
                "今日予以办理出院",
                "准许后今日办理出院",
            )
            for keyword in discharge_like_patterns:
                if keyword in content:
                    score -= 90

        return (score, has_content, display_time)

    @staticmethod
    def _canonical_doc_type(document_type: Any) -> str:
        text = str(document_type or "").strip()
        if not text:
            return ""
        if text in DOC_TYPE_CN_TO_EN:
            return DOC_TYPE_CN_TO_EN[text]
        mapped = DOC_TYPE_FULL_MAP.get(text)
        if mapped and mapped in DOC_TYPE_CN_TO_EN:
            return DOC_TYPE_CN_TO_EN[mapped]
        return text

    def _select_bundle_document_for_rule(
        self,
        *,
        rule: Dict[str, Any],
        bundle_documents: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        normalized_docs = [
            self._canonical_doc_type(item)
            for item in list(rule.get("applicable_documents") or [])
            if str(item or "").strip()
        ]
        if not normalized_docs:
            return next((dict(item) for item in bundle_documents if str(item.get("content") or "").strip()), None)

        docs_by_code: Dict[str, List[Dict[str, Any]]] = {}
        for item in bundle_documents:
            doc_code = self._canonical_doc_type(item.get("document_type") or item.get("source_table"))
            docs_by_code.setdefault(doc_code, []).append(dict(item))

        for wanted in normalized_docs:
            candidates = docs_by_code.get(wanted) or []
            candidate = next((item for item in candidates if str(item.get("content") or "").strip()), None)
            if candidate is not None:
                return candidate
        return None

    def _build_bundle_evidence_payload_for_document(
        self,
        *,
        primary_document: Dict[str, Any],
        all_documents: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        supporting_documents = []
        primary_id = str(primary_document.get("id") or "")
        for item in all_documents:
            item_id = str(item.get("id") or "")
            if item_id == primary_id:
                continue
            evidence_text = str(item.get("content") or "").strip()
            if not evidence_text:
                continue
            supporting_documents.append(
                {
                    "document_type": str(item.get("document_type") or ""),
                    "source_table": str(item.get("source_table") or ""),
                    "document_id": item_id,
                    "evidence_text": evidence_text,
                    "hit": bool(item.get("hit")),
                }
            )
        derived_signals = self._build_copy_content_similarity_signals(
            primary_document=primary_document,
            source_documents=all_documents,
            rule_ids=[str(item.get("rule_id") or item.get("rule_code") or "") for item in list(rules or [])],
        )
        from .sample_programmatic_evidence import build_programmatic_evidence_payload

        programmatic_payload = build_programmatic_evidence_payload(
            bundle=bundle,
            medical_text=str(bundle.get("medical_text") or ""),
        )
        return {
            "primary_document_text": str(primary_document.get("content") or "").strip(),
            "supporting_documents": supporting_documents,
            "timeline_facts": list(bundle.get("timeline_facts") or []),
            "document_hits": dict(bundle.get("document_hits") or {}),
            "data_quality_flags": list(bundle.get("data_quality_flags") or []),
            "derived_signals": derived_signals,
            "programmatic_timeline": dict(programmatic_payload.get("programmatic_timeline") or {}),
        }

    def _build_bundle_missing_doc_result_item(
        self,
        *,
        rule: Dict[str, Any],
        bucket_strategy: str,
        quality_profile: str,
    ) -> Dict[str, Any]:
        routing = route_rule_to_domain(rule)
        target_docs = [
            display_name_for_doc_type(doc_type)
            for doc_type in routing.primary_doc_types
        ] or [str(item) for item in list(rule.get("applicable_documents") or []) if str(item).strip()]
        return {
            "rule_id": str(rule.get("rule_id") or ""),
            "rule_name": str(rule.get("name") or rule.get("rule_name") or ""),
            "is_compliant": True,
            "status": "not_applicable",
            "findings": f"缺少适用文书，未执行该规则：{', '.join(target_docs) or '未指定文书'}",
            "evidence": "",
            "suggestion": "",
            "confidence": 1.0,
            "applicability": {
                "is_applicable": False,
                "reason": "missing_required_document",
                "method": "bundle_document_guard",
            },
            "evidence_verified": True,
            "metadata": {
                "tokens_used": 0,
                "api_time": 0.0,
                "prompt_strategy": "batch_compact_v1",
                "quality_profile": quality_profile,
                "bucket_strategy": bucket_strategy,
                "rule_family": str(rule.get("rule_family") or DEFAULT_RULE_FAMILY),
                "executor_type": str(rule.get("executor_type") or "llm"),
                "rule_version": str(rule.get("rule_version") or "v1"),
                "prompt_version": str(rule.get("prompt_version") or "custom-v1"),
                "cost_class": str(rule.get("cost_class") or "medium"),
                "execution_domain": str(rule.get("execution_domain") or routing.execution_domain),
                "doc_scope": str(rule.get("doc_scope") or "primary"),
                "evidence_source": "bundle",
                "model_version": str(self.client.model or ""),
                "llm_fallback": False,
                "cache_hit": False,
                "qc_stage": "screening",
                "refined": False,
                "refine_reason": "",
                "screening_status": "not_applicable",
                "final_decision_source": "batch",
            },
        }

    @staticmethod
    def _merge_timeline_facts(
        primary_facts: List[Dict[str, Any]],
        extra_facts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in list(primary_facts or []) + list(extra_facts or []):
            normalized = dict(item or {})
            key = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
        return merged

    @staticmethod
    def _parse_document_datetime(value: str) -> Optional[datetime]:
        return parse_document_datetime(value)

    @staticmethod
    def _normalize_round_similarity_text(value: str) -> str:
        return normalize_for_sentence(value)

    @classmethod
    def _split_round_similarity_sentences(cls, value: str) -> List[str]:
        return split_sentences(value)

    @classmethod
    def _round_sentence_coverage_ratio(
        cls,
        source_sentences: List[str],
        target_sentences: List[str],
        *,
        threshold: float = _ROUND_SENTENCE_MATCH_THRESHOLD,
    ) -> float:
        return compare_text_segments(
            "；".join(source_sentences),
            "；".join(target_sentences),
            threshold=threshold,
        ).source_to_target_sentence_coverage

    @classmethod
    def _build_copy_content_similarity_signals(
        cls,
        *,
        primary_document: Dict[str, Any],
        source_documents: List[Dict[str, Any]],
        rule_ids: List[str],
    ) -> List[Dict[str, Any]]:
        normalized_rule_ids = {
            str(item or "").strip().upper()
            for item in list(rule_ids or [])
            if str(item or "").strip()
        }
        if not (normalized_rule_ids & _COPY_SIGNAL_RULE_IDS):
            return []

        signals: List[Dict[str, Any]] = []
        if normalized_rule_ids & _COPY_ROUND_RULE_IDS:
            round_signal = cls._build_round_note_copy_signal(
                primary_document=primary_document,
                source_documents=source_documents,
            )
            if round_signal:
                signals.append(round_signal)

        if "CL-273" in normalized_rule_ids:
            segment_signal = cls._build_first_course_vs_admission_signal(
                primary_document=primary_document,
                source_documents=source_documents,
            )
            if segment_signal:
                signals.append(segment_signal)

        if "CL-274" in normalized_rule_ids:
            segment_signal = cls._build_first_course_reasoning_self_signal(
                primary_document=primary_document,
            )
            if segment_signal:
                signals.append(segment_signal)

        if "CL-276" in normalized_rule_ids:
            peer_signal = cls._build_same_disease_reasoning_peer_signal(
                primary_document=primary_document,
                source_documents=source_documents,
            )
            if peer_signal:
                signals.append(peer_signal)
        return signals

    @classmethod
    def _build_round_note_copy_signal(
        cls,
        *,
        primary_document: Dict[str, Any],
        source_documents: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
        primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
        if primary_source_table not in ROUND_SOURCE_TABLES or not primary_content:
            return None

        match = select_best_lookback_match(
            primary_document=primary_document,
            candidate_documents=source_documents,
            allowed_source_tables=ROUND_SOURCE_TABLES,
            lookback_count=_ROUND_LOOKBACK_COUNT,
            sentence_threshold=_ROUND_SENTENCE_MATCH_THRESHOLD,
            min_full_similarity=0.3,
        )
        if not match:
            return None

        compare_document = dict(match.get("compare_document") or {})
        compare_time = str(compare_document.get("display_time") or compare_document.get("record_time") or "").strip()
        primary_time = str(primary_document.get("display_time") or primary_document.get("record_time") or "").strip()
        primary_dt = cls._parse_document_datetime(primary_time)
        compare_dt = cls._parse_document_datetime(compare_time)
        later_is_primary = bool(primary_dt and compare_dt and primary_dt >= compare_dt)
        later_to_earlier_cover = (
            float(match.get("source_to_target_sentence_coverage") or 0.0)
            if later_is_primary
            else float(match.get("target_to_source_sentence_coverage") or 0.0)
        )
        return {
            "signal_type": "adjacent_round_similarity",
            "primary_source_table": primary_source_table,
            "primary_document_title": str(primary_document.get("document_title") or primary_source_table),
            "primary_display_time": primary_time,
            "compare_source_table": str(compare_document.get("source_table") or compare_document.get("document_type") or ""),
            "compare_document_title": str(compare_document.get("document_title") or compare_document.get("source_table") or ""),
            "compare_display_time": compare_time,
            "similarity_ratio": round(float(match.get("full_similarity_ratio") or 0.0), 4),
            "threshold_hint": _COPY_SIMILARITY_THRESHOLD,
            "sentence_match_threshold": _ROUND_SENTENCE_MATCH_THRESHOLD,
            "primary_to_compare_sentence_coverage": round(float(match.get("source_to_target_sentence_coverage") or 0.0), 4),
            "compare_to_primary_sentence_coverage": round(float(match.get("target_to_source_sentence_coverage") or 0.0), 4),
            "later_to_earlier_sentence_coverage": round(later_to_earlier_cover, 4),
            "later_is_primary": later_is_primary,
            "coverage_threshold_hint": _ROUND_LATER_COVERAGE_THRESHOLD,
            "lookback_window": _ROUND_LOOKBACK_COUNT,
            "time_gap_hours": match.get("time_gap_hours"),
        }

    @classmethod
    def _build_first_course_vs_admission_signal(
        cls,
        *,
        primary_document: Dict[str, Any],
        source_documents: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
        primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
        if primary_source_table not in FIRST_COURSE_SOURCE_TABLES or not primary_content:
            return None

        admission_document = next(
            (
                dict(item)
                for item in list(source_documents or [])
                if str(item.get("source_table") or item.get("document_type") or "").strip() in ADMISSION_SOURCE_TABLES
                and str(item.get("content") or item.get("text_preview") or "").strip()
            ),
            None,
        )
        if not admission_document:
            return None

        first_sections = extract_first_course_sections(primary_content)
        admission_sections = extract_admission_sections(
            str(admission_document.get("content") or admission_document.get("text_preview") or "")
        )
        source_segment = str(first_sections.get("case_features_candidate") or "").strip()
        target_segment = str(admission_sections.get("symptom_body_signs_candidate") or "").strip()
        if not source_segment or not target_segment:
            return None
        metrics = compare_text_segments(source_segment, target_segment)
        return {
            "signal_type": "copy_segment_similarity",
            "rule_hint": "CL-273",
            "primary_source_table": primary_source_table,
            "primary_document_title": str(primary_document.get("document_title") or primary_source_table),
            "compare_source_table": str(admission_document.get("source_table") or admission_document.get("document_type") or ""),
            "compare_document_title": str(admission_document.get("document_title") or admission_document.get("source_table") or ""),
            "source_section_key": "case_features_candidate",
            "target_section_key": "symptom_body_signs_candidate",
            "full_similarity_ratio": metrics.full_similarity_ratio,
            "source_to_target_sentence_coverage": metrics.source_to_target_sentence_coverage,
            "target_to_source_sentence_coverage": metrics.target_to_source_sentence_coverage,
            "core_section_coverage": metrics.source_to_target_sentence_coverage,
            "threshold_hint": _COPY_SIMILARITY_THRESHOLD,
            "sentence_match_threshold": _ROUND_SENTENCE_MATCH_THRESHOLD,
        }

    @classmethod
    def _build_first_course_reasoning_self_signal(
        cls,
        *,
        primary_document: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
        primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
        if primary_source_table not in FIRST_COURSE_SOURCE_TABLES or not primary_content:
            return None
        first_sections = extract_first_course_sections(primary_content)
        source_segment = str(first_sections.get("reasoning_candidate") or "").strip()
        target_segment = str(first_sections.get("case_features_candidate") or "").strip()
        if not source_segment or not target_segment:
            return None
        metrics = compare_text_segments(source_segment, target_segment)
        return {
            "signal_type": "copy_segment_similarity",
            "rule_hint": "CL-274",
            "primary_source_table": primary_source_table,
            "primary_document_title": str(primary_document.get("document_title") or primary_source_table),
            "compare_source_table": primary_source_table,
            "compare_document_title": str(primary_document.get("document_title") or primary_source_table),
            "source_section_key": "reasoning_candidate",
            "target_section_key": "case_features_candidate",
            "full_similarity_ratio": metrics.full_similarity_ratio,
            "source_to_target_sentence_coverage": metrics.source_to_target_sentence_coverage,
            "target_to_source_sentence_coverage": metrics.target_to_source_sentence_coverage,
            "core_section_coverage": metrics.source_to_target_sentence_coverage,
            "threshold_hint": _COPY_SIMILARITY_THRESHOLD,
            "sentence_match_threshold": _ROUND_SENTENCE_MATCH_THRESHOLD,
        }

    @classmethod
    def _build_same_disease_reasoning_peer_signal(
        cls,
        *,
        primary_document: Dict[str, Any],
        source_documents: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
        primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
        if primary_source_table not in FIRST_COURSE_SOURCE_TABLES or not primary_content:
            return None

        first_sections = extract_first_course_sections(primary_content)
        source_segment = str(first_sections.get("reasoning_candidate") or "").strip()
        if not source_segment:
            return None

        institute_id = str(primary_document.get("institute_id") or "").strip()
        patient_id = str(primary_document.get("patient_id") or "").strip()
        visit_id = str(primary_document.get("visit_id") or "").strip()
        dept_name = str(primary_document.get("dept_name") or "").strip()
        if not (institute_id and patient_id and visit_id and dept_name):
            return None

        diagnosis_context = cls._resolve_primary_diagnosis_context(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
        )
        if not diagnosis_context:
            return None

        peer_documents = cls._load_same_disease_first_course_candidates(
            institute_id=institute_id,
            current_patient_id=patient_id,
            current_visit_id=visit_id,
            dept_name=dept_name,
            diagnosis_code=str(diagnosis_context.get("diagnosis_code") or ""),
            diagnosis_name=str(diagnosis_context.get("diagnosis_name") or ""),
            limit=10,
        )
        best_signal: Optional[Dict[str, Any]] = None
        for item in peer_documents:
            peer_content = str(item.get("record_content") or "").strip()
            if not peer_content:
                continue
            peer_sections = extract_first_course_sections(peer_content)
            target_segment = str(peer_sections.get("reasoning_candidate") or "").strip()
            if not target_segment:
                continue
            metrics = compare_text_segments(source_segment, target_segment)
            candidate = {
                "signal_type": "same_disease_reasoning_similarity",
                "rule_hint": "CL-276",
                "primary_source_table": primary_source_table,
                "primary_document_title": str(primary_document.get("document_title") or primary_source_table),
                "compare_source_table": "first_course_record",
                "compare_document_title": "同科同病种首次病程",
                "compare_visit_id": str(item.get("visit_id") or ""),
                "compare_patient_name": str(item.get("name") or ""),
                "compare_dept_name": str(item.get("dept_name") or ""),
                "source_section_key": "reasoning_candidate",
                "target_section_key": "reasoning_candidate",
                "full_similarity_ratio": metrics.full_similarity_ratio,
                "source_to_target_sentence_coverage": metrics.source_to_target_sentence_coverage,
                "target_to_source_sentence_coverage": metrics.target_to_source_sentence_coverage,
                "core_section_coverage": metrics.average_sentence_coverage,
                "threshold_hint": _COPY_SIMILARITY_THRESHOLD,
                "sentence_match_threshold": _ROUND_SENTENCE_MATCH_THRESHOLD,
                "cohort_diagnosis_code": str(diagnosis_context.get("diagnosis_code") or ""),
                "cohort_diagnosis_name": str(diagnosis_context.get("diagnosis_name") or ""),
            }
            if best_signal is None:
                best_signal = candidate
                continue
            current_key = (
                float(candidate.get("core_section_coverage") or 0.0),
                float(candidate.get("full_similarity_ratio") or 0.0),
            )
            best_key = (
                float(best_signal.get("core_section_coverage") or 0.0),
                float(best_signal.get("full_similarity_ratio") or 0.0),
            )
            if current_key > best_key:
                best_signal = candidate
        return best_signal

    @staticmethod
    def _resolve_primary_diagnosis_context(
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
    ) -> Optional[Dict[str, Any]]:
        if SessionLocal is None:
            return None
        session = SessionLocal()
        try:
            rows = (
                session.query(Diagnosis)
                .filter(
                    Diagnosis.institute_id == institute_id,
                    Diagnosis.patient_id == patient_id,
                    Diagnosis.visit_id == visit_id,
                )
                .order_by(Diagnosis.diagnosis_no.asc(), Diagnosis.diagnosis_type.asc())
                .all()
            )
            for row in rows:
                diagnosis_type = str(row.diagnosis_type or "")
                if "出院主要" in diagnosis_type or "主要" in diagnosis_type or str(row.diagnosis_no or "").strip() == "1":
                    return {
                        "diagnosis_code": str(row.diagnosis_code or ""),
                        "diagnosis_name": str(row.diagnosis_name or ""),
                    }
            if rows:
                first = rows[0]
                return {
                    "diagnosis_code": str(first.diagnosis_code or ""),
                    "diagnosis_name": str(first.diagnosis_name or ""),
                }
            return None
        finally:
            session.close()

    @staticmethod
    def _load_same_disease_first_course_candidates(
        *,
        institute_id: str,
        current_patient_id: str,
        current_visit_id: str,
        dept_name: str,
        diagnosis_code: str,
        diagnosis_name: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        if SessionLocal is None or not dept_name:
            return []
        session = SessionLocal()
        try:
            diagnosis_query = session.query(Diagnosis).filter(
                Diagnosis.institute_id == institute_id,
                Diagnosis.dept_name == dept_name,
                Diagnosis.visit_id != current_visit_id,
            )
            if diagnosis_code:
                diagnosis_query = diagnosis_query.filter(Diagnosis.diagnosis_code == diagnosis_code)
            elif diagnosis_name:
                diagnosis_query = diagnosis_query.filter(Diagnosis.diagnosis_name == diagnosis_name)
            else:
                return []
            diagnosis_rows = diagnosis_query.order_by(Diagnosis.diagnosis_datetime.desc()).limit(max(1, int(limit))).all()
            visit_ids = [str(item.visit_id or "").strip() for item in diagnosis_rows if str(item.visit_id or "").strip()]
            if not visit_ids:
                return []
            first_course_rows = (
                session.query(FirstCourseRecord)
                .filter(
                    FirstCourseRecord.institute_id == institute_id,
                    FirstCourseRecord.visit_id.in_(visit_ids),
                )
                .all()
            )
            return [
                {
                    "patient_id": str(item.patient_id or ""),
                    "visit_id": str(item.visit_id or ""),
                    "name": str(getattr(item, "name", "") or ""),
                    "dept_name": str(getattr(item, "dept_name", "") or dept_name),
                    "record_content": str(item.record_content or ""),
                }
                for item in first_course_rows
                if str(item.record_content or "").strip() and str(item.patient_id or "") != current_patient_id
            ]
        finally:
            session.close()

    @classmethod
    def _build_adjacent_round_similarity_signals(
        cls,
        *,
        primary_document: Dict[str, Any],
        source_documents: List[Dict[str, Any]],
        rule_ids: List[str],
    ) -> List[Dict[str, Any]]:
        # 历史兼容入口：复制粘贴专项已统一迁到新的 copy-content 信号构造器。
        return cls._build_copy_content_similarity_signals(
            primary_document=primary_document,
            source_documents=source_documents,
            rule_ids=rule_ids,
        )
        normalized_rule_ids = {str(item or "").strip().upper() for item in list(rule_ids or []) if str(item or "").strip()}
        if not (normalized_rule_ids & _ROUND_SIMILARITY_RULE_IDS):
            return []

        primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
        primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
        if primary_source_table not in _ROUND_SIMILARITY_SOURCE_TABLES or not primary_content:
            return []

        primary_time = str(primary_document.get("display_time") or primary_document.get("record_time") or "").strip()
        primary_dt = cls._parse_document_datetime(primary_time)
        primary_id = str(primary_document.get("document_id") or primary_document.get("id") or "").strip()
        normalized_primary = cls._normalize_round_similarity_text(primary_content)
        if not normalized_primary:
            return []

        prior_documents: List[tuple[Optional[datetime], Dict[str, Any]]] = []
        for item in list(source_documents or []):
            source_table = str(item.get("source_table") or item.get("document_type") or "").strip()
            if source_table not in _ROUND_SIMILARITY_SOURCE_TABLES:
                continue
            compare_content = str(item.get("content") or item.get("text_preview") or "").strip()
            if not compare_content:
                continue
            compare_id = str(item.get("document_id") or item.get("id") or "").strip()
            compare_time = str(item.get("display_time") or item.get("record_time") or "").strip()
            if (
                compare_id
                and primary_id
                and compare_id == primary_id
                and source_table == primary_source_table
                and compare_time == primary_time
            ):
                continue
            compare_dt = cls._parse_document_datetime(compare_time)
            if primary_dt is not None and compare_dt is not None:
                delta_seconds = (primary_dt - compare_dt).total_seconds()
                if delta_seconds <= 0 or delta_seconds > 72 * 3600:
                    continue
            prior_documents.append((compare_dt, dict(item)))

        if not prior_documents:
            return []

        prior_documents.sort(
            key=lambda pair: pair[0] or datetime.min,
            reverse=True,
        )
        lookback_documents = [item for _dt, item in prior_documents[:_ROUND_LOOKBACK_COUNT]]

        candidates: List[Dict[str, Any]] = []
        for item in lookback_documents:
            compare_content = str(item.get("content") or item.get("text_preview") or "").strip()
            normalized_compare = cls._normalize_round_similarity_text(compare_content)
            if not normalized_compare:
                continue
            compare_time = str(item.get("display_time") or item.get("record_time") or "").strip()
            compare_dt = cls._parse_document_datetime(compare_time)
            time_gap_hours = None
            if primary_dt is not None and compare_dt is not None:
                delta_seconds = abs((primary_dt - compare_dt).total_seconds())
                time_gap_hours = round(delta_seconds / 3600.0, 2)
            similarity_ratio = SequenceMatcher(None, normalized_primary, normalized_compare).ratio()
            if similarity_ratio < 0.3:
                continue
            primary_sentences = cls._split_round_similarity_sentences(primary_content)
            compare_sentences = cls._split_round_similarity_sentences(compare_content)
            primary_to_compare_cover = cls._round_sentence_coverage_ratio(
                primary_sentences,
                compare_sentences,
            )
            compare_to_primary_cover = cls._round_sentence_coverage_ratio(
                compare_sentences,
                primary_sentences,
            )
            later_to_earlier_cover = 0.0
            later_is_primary = False
            if primary_dt is not None and compare_dt is not None:
                if primary_dt >= compare_dt:
                    later_to_earlier_cover = primary_to_compare_cover
                    later_is_primary = True
                else:
                    later_to_earlier_cover = compare_to_primary_cover
            candidates.append(
                {
                    "signal_type": "adjacent_round_similarity",
                    "primary_source_table": primary_source_table,
                    "primary_document_title": str(primary_document.get("document_title") or primary_source_table),
                    "primary_display_time": primary_time,
                    "compare_source_table": source_table,
                    "compare_document_title": str(item.get("document_title") or source_table),
                    "compare_display_time": compare_time,
                    "similarity_ratio": round(similarity_ratio, 4),
                    "threshold_hint": 0.5,
                    "sentence_match_threshold": _ROUND_SENTENCE_MATCH_THRESHOLD,
                    "primary_to_compare_sentence_coverage": primary_to_compare_cover,
                    "compare_to_primary_sentence_coverage": compare_to_primary_cover,
                    "later_to_earlier_sentence_coverage": later_to_earlier_cover,
                    "later_is_primary": later_is_primary,
                    "coverage_threshold_hint": _ROUND_LATER_COVERAGE_THRESHOLD,
                    "lookback_window": _ROUND_LOOKBACK_COUNT,
                    "time_gap_hours": time_gap_hours,
                }
            )

        candidates.sort(
            key=lambda item: (
                float(item.get("later_to_earlier_sentence_coverage") or 0.0),
                float(item.get("similarity_ratio") or 0.0),
                -float(item.get("time_gap_hours") or 9999.0),
            ),
            reverse=True,
        )
        return candidates[:1]

    @staticmethod
    def _merge_rule_input_with_bundle_documents(
        *,
        rule_input: RuleExecutionInput,
        bundle: Dict[str, Any],
        include_doc_types: Optional[tuple[str, ...]] = None,
    ) -> RuleExecutionInput:
        allowed = {
            str(item or "").strip()
            for item in (include_doc_types or ())
            if str(item or "").strip()
        }

        source_documents = [dict(item) for item in list(rule_input.source_documents or [])]
        supporting_evidence = [dict(item) for item in list(rule_input.supporting_evidence or [])]

        existing_source_keys = {
            (
                str(item.get("source_table") or ""),
                str(item.get("document_id") or ""),
                str(item.get("display_time") or ""),
            )
            for item in source_documents
        }
        existing_support_keys = {
            (
                str(item.get("source_table") or ""),
                str(item.get("document_id") or ""),
                str(item.get("display_time") or ""),
            )
            for item in supporting_evidence
        }

        extra_source_documents = list(bundle.get("source_documents") or [])
        for item in extra_source_documents:
            source_table = str(item.get("source_table") or item.get("document_type") or "").strip()
            if allowed and source_table not in allowed:
                continue
            key = (
                source_table,
                str(item.get("document_id") or ""),
                str(item.get("display_time") or item.get("record_time") or ""),
            )
            if key not in existing_source_keys:
                existing_source_keys.add(key)
                source_documents.append(
                    {
                        "document_type": display_name_for_doc_type(str(item.get("document_type") or item.get("source_table") or "")),
                        "source_table": source_table,
                        "document_id": str(item.get("document_id") or ""),
                        "document_title": str(item.get("document_title") or ""),
                        "display_time": str(item.get("display_time") or item.get("record_time") or ""),
                        # 程序信号（如相邻查房重叠率）需要基于完整正文计算，不能在此截断。
                        "content": str(item.get("content") or item.get("text_preview") or ""),
                        "hit": bool(item.get("hit")),
                        "sections": list(item.get("sections") or []),
                        "source_fields": list(item.get("source_fields") or []),
                        "assembly_status": str(item.get("assembly_status") or ""),
                        "data_quality_flags": list(item.get("data_quality_flags") or []),
                    }
                )

            evidence_text = str(item.get("content") or item.get("text_preview") or "").strip()
            if not evidence_text:
                continue
            if key not in existing_support_keys:
                existing_support_keys.add(key)
                supporting_evidence.append(
                    {
                        "document_type": display_name_for_doc_type(str(item.get("document_type") or item.get("source_table") or "")),
                        "source_table": source_table,
                        "document_id": str(item.get("document_id") or ""),
                        "document_title": str(item.get("document_title") or ""),
                        "display_time": str(item.get("display_time") or item.get("record_time") or ""),
                        "evidence_text": evidence_text[:800],
                        "sections": list(item.get("sections") or []),
                        "source_fields": list(item.get("source_fields") or []),
                        "assembly_status": str(item.get("assembly_status") or ""),
                        "data_quality_flags": list(item.get("data_quality_flags") or []),
                    }
                )

        merged_timeline_facts = SichuanQCService._merge_timeline_facts(
            list(rule_input.timeline_facts or []),
            list(bundle.get("timeline_facts") or []),
        )
        return RuleExecutionInput(
            rule_id=rule_input.rule_id,
            document_type=rule_input.document_type,
            execution_domain=rule_input.execution_domain,
            primary_medical_text=rule_input.primary_medical_text,
            supporting_evidence=supporting_evidence,
            timeline_facts=merged_timeline_facts,
            source_documents=source_documents,
        )

    @staticmethod
    def _sum_counter_dicts(values: List[Dict[str, Any]]) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for value in values:
            for key, raw in dict(value or {}).items():
                merged[str(key)] = int(merged.get(str(key), 0)) + int(raw or 0)
        return merged

    def _merge_pack_metrics(self, metrics_list: List[Dict[str, Any]], *, quality_profile: str, bucket_strategy: str) -> Dict[str, Any]:
        if not metrics_list:
            return {}
        total_packs = sum(int(item.get("total_packs") or 0) for item in metrics_list)
        weighted_pack = sum(float(item.get("avg_pack_size") or 0.0) * int(item.get("total_packs") or 0) for item in metrics_list)
        selected_pack_size_by_bucket: Dict[str, Any] = {}
        for item in metrics_list:
            selected_pack_size_by_bucket.update(dict(item.get("selected_pack_size_by_bucket") or {}))
        return {
            "prompt_strategy": "batch_compact_v1",
            "quality_profile": quality_profile,
            "bucket_strategy": bucket_strategy,
            "bucket_count": sum(int(item.get("bucket_count") or 0) for item in metrics_list),
            "total_packs": total_packs,
            "avg_pack_size": round((weighted_pack / total_packs), 2) if total_packs else 0.0,
            "fallback_packs": sum(int(item.get("fallback_packs") or 0) for item in metrics_list),
            "single_rule_retries": sum(int(item.get("single_rule_retries") or 0) for item in metrics_list),
            "pack_parse_retry_count": sum(int(item.get("pack_parse_retry_count") or 0) for item in metrics_list),
            "pack_fallback_count": sum(int(item.get("pack_fallback_count") or 0) for item in metrics_list),
            "pack_parse_failures": sum(int(item.get("pack_parse_failures") or 0) for item in metrics_list),
            "pack_parse_error_count": sum(int(item.get("pack_parse_error_count") or 0) for item in metrics_list),
            "missing_rule_items": sum(int(item.get("missing_rule_items") or 0) for item in metrics_list),
            "low_confidence_items": sum(int(item.get("low_confidence_items") or 0) for item in metrics_list),
            "context_tokens_estimate": sum(int(item.get("context_tokens_estimate") or 0) for item in metrics_list),
            "probe_calls": sum(int(item.get("probe_calls") or 0) for item in metrics_list),
            "selected_pack_size": max(int(item.get("selected_pack_size") or 0) for item in metrics_list),
            "selected_pack_size_by_bucket": selected_pack_size_by_bucket,
        }

    def _build_rule_execution_input_from_bundle(
        self,
        *,
        rule: Dict[str, Any],
        routing: Any,
        domain_bundle: Dict[str, Any],
    ) -> RuleExecutionInput:
        source_documents = list(domain_bundle.get("source_documents") or [])
        normalized_rule_id = str(rule.get("rule_id") or "").strip().upper()
        if normalized_rule_id == "SC-146":
            primary_candidates = self._find_source_documents_for_types(
                source_documents,
                ["daily_course_record", "senior_course_record", "first_course_record"],
            )
            auxiliary_candidates = self._find_source_documents_for_types(
                source_documents,
                ["inpat_drug_order", "inpat_nondrug_order"],
            )
            if not auxiliary_candidates:
                auxiliary_candidates = self._find_source_documents_for_types(
                    source_documents,
                    list(routing.aux_doc_types),
                )
        elif normalized_rule_id == "SC-039":
            primary_candidates = self._find_source_documents_for_types(
                source_documents,
                ["daily_course_record", "senior_course_record", "summary_record", "rescue_record"],
            )
            auxiliary_candidates = self._find_source_documents_for_types(
                source_documents,
                ["senior_course_record", "summary_record", "rescue_record", "daily_course_record"],
            )
        else:
            primary_candidates = self._find_source_documents_for_types(
                source_documents,
                list(routing.primary_doc_types),
            )
            if normalized_rule_id in {"SC-023", "SC-024", "SC-025", "SC-026", "SC-027"} and not any(
                str(item.get("content") or "").strip() for item in primary_candidates
            ):
                primary_candidates = self._find_source_documents_for_types(
                    source_documents,
                    ["senior_course_record", "daily_course_record", "first_course_record"],
                )
            auxiliary_candidates = self._find_source_documents_for_types(
                source_documents,
                list(routing.aux_doc_types),
            )
        if primary_candidates:
            primary_candidates.sort(
                key=lambda item: self._score_primary_candidate_for_rule(
                    rule_id=str(rule.get("rule_id") or ""),
                    candidate=item,
                ),
                reverse=True,
            )

        primary_document = next(
            (item for item in primary_candidates if str(item.get("content") or "").strip()),
            primary_candidates[0] if primary_candidates else None,
        )
        if primary_document is None:
            raise LookupError("missing_required_document")

        primary_text = str(primary_document.get("content") or "").strip()
        if routing.strict_primary_required and not primary_text:
            raise LookupError("missing_required_document")

        supporting_evidence: List[Dict[str, Any]] = []
        for item in auxiliary_candidates[:3]:
            evidence_text = str(item.get("content") or item.get("text_preview") or "").strip()
            if not evidence_text:
                continue
            supporting_evidence.append(
                {
                    "document_type": display_name_for_doc_type(str(item.get("document_type") or item.get("source_table") or "")),
                    "source_table": str(item.get("source_table") or ""),
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": str(item.get("document_title") or ""),
                    "display_time": str(item.get("display_time") or item.get("record_time") or ""),
                    "evidence_text": evidence_text[:800],
                    "sections": list(item.get("sections") or []),
                    "source_fields": list(item.get("source_fields") or []),
                    "assembly_status": str(item.get("assembly_status") or ""),
                    "data_quality_flags": list(item.get("data_quality_flags") or []),
                }
            )

        primary_doc_type = display_name_for_doc_type(
            str(primary_document.get("document_type") or primary_document.get("source_table") or "")
        )
        preserve_full_source_content = normalized_rule_id in _COPY_SIGNAL_RULE_IDS
        if normalized_rule_id == "SC-146" and str(primary_document.get("source_table") or "") in {
            "daily_course_record",
            "senior_course_record",
            "first_course_record",
        }:
            primary_doc_type = "日常病程记录"
        elif normalized_rule_id in {"SC-023", "SC-024", "SC-025", "SC-026", "SC-027"} and str(primary_document.get("source_table") or "") in {
            "daily_course_record",
            "senior_course_record",
            "first_course_record",
        }:
            primary_doc_type = "首次病程记录"
        return RuleExecutionInput(
            rule_id=str(rule.get("rule_id") or ""),
            document_type=primary_doc_type,
            execution_domain=str(domain_bundle.get("execution_domain") or routing.execution_domain),
            primary_medical_text=primary_text,
            supporting_evidence=supporting_evidence,
            timeline_facts=list(domain_bundle.get("timeline_facts") or []),
            source_documents=[
                {
                    "document_type": display_name_for_doc_type(str(item.get("document_type") or item.get("source_table") or "")),
                    "source_table": str(item.get("source_table") or ""),
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": str(item.get("document_title") or ""),
                    "display_time": str(item.get("display_time") or item.get("record_time") or ""),
                    "content": (
                        str(item.get("content") or item.get("text_preview") or "")
                        if preserve_full_source_content
                        else str(item.get("content") or item.get("text_preview") or "")[:800]
                    ),
                    "hit": bool(item.get("hit")),
                    "sections": list(item.get("sections") or []),
                    "source_fields": list(item.get("source_fields") or []),
                    "assembly_status": str(item.get("assembly_status") or ""),
                    "data_quality_flags": list(item.get("data_quality_flags") or []),
                }
                for item in source_documents
            ],
        )

    def _build_missing_primary_result(
        self,
        *,
        rule: Dict[str, Any],
        routing: Any,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        domain_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        primary_docs = [display_name_for_doc_type(item) for item in routing.primary_doc_types]
        result = {
            "rule_id": str(rule.get("rule_id") or ""),
            "rule_name": str(rule.get("name") or ""),
            "status": "not_applicable",
            "is_compliant": True,
            "issues": [],
            "findings": f"缺少主文书，无法执行规则：{', '.join(primary_docs) or '未配置主文书'}",
            "evidence": "",
            "suggestion": "",
            "confidence": 1.0,
            "llm_raw_output": None,
            "applicability": {
                "is_applicable": False,
                "reason": "missing_required_document",
                "method": "domain_primary_guard",
            },
            "evidence_verified": True,
            "evidence_span": None,
            "metadata": {
                "tokens_used": 0,
                "api_time": 0.0,
            },
        }
        return {
            "document_id": visit_id,
            "document_type": ", ".join(primary_docs) or "未知文书",
            "total_rules": 1,
            "applicable_rules": [str(rule.get("rule_id") or "")],
            "evaluation_summary": {
                "compliance_rate": 100.0,
                "issues_found": 0,
                "not_applicable": 1,
                "total_rules": 1,
                "compliant_rules": 1,
                "model": self.client.model,
            },
            "parsed_evaluation_results": [result],
            "evaluation_results": [result],
            "llm_output": None,
            "token_usage": {"total_tokens": 0},
            "api_time": 0.0,
            "routing": routing.to_dict(),
            "rule_execution_input": None,
            "bundle_metadata": {
                "execution_domain": routing.execution_domain,
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_hits": domain_bundle.get("document_hits") or {},
                "data_quality_flags": domain_bundle.get("data_quality_flags") or [],
            },
        }

    @staticmethod
    def _apply_sc039_text_only_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-039":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        lowered = primary_text.lower()
        if status == "non_compliant" or not primary_text:
            return engine_result

        has_k_value = bool(re.search(r"\bk\s*\d+(?:\.\d+)?\s*mmol/?l\b", lowered))
        has_crisis_keyword = any(
            keyword in primary_text
            for keyword in ("危急值", "接危急值", "危急值回报", "危急值处理", "接电脑危急值")
        )
        has_electrolyte_context = any(
            keyword in primary_text
            for keyword in ("低钾", "补钾", "静脉补", "电解质", "复查电解质")
        )
        if not (has_crisis_keyword or (has_k_value and has_electrolyte_context)):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc039_text_only"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "病程记录已涉及危急值/电解质异常处置语境，但未完整记录危急值报告时间、处置时间、具体处理闭环或复查结果。",
                "evidence": primary_text[:200],
                "suggestion": "请补充危急值接收时间、患者当时情况、具体处理措施、复查结果及处理后观察。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.82),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc069_text_only_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-069":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant" or not primary_text:
            return engine_result

        missing_signature = bool(re.search(r"医生签名[:：]\s*$", primary_text))
        missing_dept = "科" not in primary_text[:40]
        if not (missing_signature or missing_dept):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc069_text_only"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "会诊记录存在关键书写要素缺失，至少缺少会诊医师签名或明确科别信息。",
                "evidence": primary_text[:200],
                "suggestion": "请补全会诊医师签名，并明确标注会诊医师所在科别及会诊时间。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.9),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc008_text_only_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-008":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant" or not primary_text:
            return engine_result

        first_line = next((line.strip() for line in primary_text.splitlines() if line.strip()), "")
        if not first_line:
            return engine_result

        trauma_keywords = ("车祸", "撞伤", "摔伤", "坠伤", "刀伤", "打伤", "外伤")
        generic_injury_keywords = ("受伤", "外伤")
        concrete_symptom_keywords = (
            "疼痛",
            "发热",
            "咳嗽",
            "胸痛",
            "腹痛",
            "头痛",
            "头晕",
            "昏迷",
            "呕吐",
            "出血",
            "骨折",
            "麻木",
            "肿胀",
            "呼吸困难",
        )
        has_trauma_context = any(keyword in first_line for keyword in trauma_keywords)
        only_generic_injury = any(keyword in first_line for keyword in generic_injury_keywords) and not any(
            keyword in first_line for keyword in concrete_symptom_keywords
        )
        has_duration = bool(re.search(r"\d+\+?(?:分钟|小时|天)", first_line))
        if not (has_trauma_context and only_generic_injury and has_duration):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc008_text_only"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "主诉仅描述受伤经过/部位及持续时间，未突出主要症状或体征，难以直接导出第一诊断，书写不规范。",
                "evidence": first_line[:200],
                "suggestion": "请在主诉中补充能够直接支持主要诊断的关键症状或体征，并保留持续时间。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.82),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc033_text_only_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-033":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant" or not primary_text:
            return engine_result

        generic_management_patterns = (
            "密观患者病情变化，如有不适，及时处理",
            "密切观察患者病情变化，如有不适，及时处理",
            "继续观察患者病情变化",
            "继续当前治疗方案",
            "继续治疗",
            "继续观察",
            "暂无特殊处理",
        )
        detailed_action_keywords = (
            "给予",
            "加用",
            "停用",
            "改用",
            "补液",
            "补钾",
            "抗感染",
            "止痛",
            "复查",
            "会诊",
            "输注",
            "调整",
            "拟予以",
        )
        has_generic_management = any(keyword in primary_text for keyword in generic_management_patterns)
        has_detailed_action = any(keyword in primary_text for keyword in detailed_action_keywords)
        if not (has_generic_management and not has_detailed_action):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc033_text_only"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "病程记录仅作笼统观察性表述，未结合当日检查/病情变化给出明确分析判断或具体处理措施。",
                "evidence": primary_text[:200],
                "suggestion": "请补充当日病情变化的分析依据，以及对应的具体处理、用药或复查计划。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.82),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc036_supporting_evidence_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-036":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant" or not primary_text:
            return engine_result

        supporting_lines = [
            str(item.get("evidence_text") or "").strip()
            for item in list(rule_input.supporting_evidence or [])
            if isinstance(item, dict) and str(item.get("evidence_text") or "").strip()
        ]
        if not supporting_lines:
            return engine_result

        supporting_text = "\n".join(supporting_lines)
        has_supporting_abnormal = any(
            keyword in supporting_text
            for keyword in (
                "异常",
                "升高",
                "降低",
                "感染",
                "阳性",
                "阻滞",
                "肾功",
                "尿常规",
                "泌尿道感染",
                "尿路感染",
                "心电图",
                "完全右束支传导阻滞",
                "ESR",
                "PCT",
                "CRP",
                "UA ",
                "UA",
                "血压",
            )
        )
        if not has_supporting_abnormal:
            return engine_result

        generic_summary_patterns = (
            "较前好转",
            "明显好转",
            "继续观察",
            "继续原方案",
            "继续当前治疗方案",
            "病情稳定",
            "余治疗同前",
            "续观",
            "密观",
            "完善术前准备",
        )
        primary_has_generic_summary = any(keyword in primary_text for keyword in generic_summary_patterns)
        if not primary_has_generic_summary:
            return engine_result

        reasoning_keywords = ("考虑", "提示", "原因", "所致", "由于", "支持", "诊断依据", "鉴别")
        targeted_followup_keywords = (
            "会诊",
            "抗感染",
            "降压",
            "补液",
            "补钾",
            "调整",
            "复查",
            "监测",
            "控制血压",
            "处理",
            "左氧氟沙星",
        )
        has_reasoning = any(keyword in primary_text for keyword in reasoning_keywords)
        has_targeted_followup = any(keyword in primary_text for keyword in targeted_followup_keywords)
        if has_reasoning or has_targeted_followup:
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc036_supporting_abnormal_without_analysis"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "同域辅助证据已提示明确异常结果，但主病程仅作泛化总结，未说明异常意义、原因或针对性处理。",
                "evidence": f"主病程：{primary_text[:120]}；辅助证据：{supporting_text[:160]}",
                "suggestion": "请在病程中补充异常结果的临床意义、可能原因，以及针对性的处理、复查或会诊计划。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.84),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _rule_input_combined_text(rule_input: RuleExecutionInput) -> str:
        parts = [str(rule_input.primary_medical_text or "").strip()]
        for item in list(rule_input.supporting_evidence or []):
            if not isinstance(item, dict):
                continue
            text = str(item.get("evidence_text") or "").strip()
            if text:
                parts.append(text)
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _apply_sc032_thin_course_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-032":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        combined_text = SichuanQCService._rule_input_combined_text(rule_input)
        if status == "non_compliant" or not combined_text:
            return engine_result

        compact_primary = re.sub(r"\s+", "", primary_text)
        source_documents = [dict(item) for item in list(rule_input.source_documents or []) if isinstance(item, dict)]
        source_course_texts = []
        for item in source_documents:
            source_table = str(item.get("source_table") or item.get("document_type") or "").strip()
            if source_table not in {"daily_course_record", "senior_course_record"}:
                continue
            text = str(item.get("content") or "").strip()
            if text:
                source_course_texts.append(text)
        empty_shell_patterns = (
            "医师签名:",
            "医生签名:",
            "查体同前",
            "治疗方案上无特殊调整",
            "继续原方案",
            "密观",
            "未诉其他不适",
        )
        has_empty_shell_record = any(pattern in combined_text for pattern in ("医师签名:\n", "医生签名:\n"))
        has_source_thin_course = any(
            len(re.sub(r"\s+", "", text)) < 180
            and any(marker in text for marker in ("医师签名:", "医生签名:", "查体同前", "无特殊调整", "继续原方案", "密观"))
            for text in source_course_texts
        )
        is_thin_primary = bool(primary_text) and len(compact_primary) < 180
        has_thin_marker = any(pattern in combined_text for pattern in empty_shell_patterns)
        has_course_context = any(token in combined_text for token in ("日常病程", "查房内容", "今日查房", "病程记录"))
        if not (has_course_context and (has_empty_shell_record or has_source_thin_course or (is_thin_primary and has_thin_marker))):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc032_thin_or_empty_course"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "病程/查房记录存在空壳或过于简略表述，未充分记录患者病情变化、查体和诊疗经过。",
                "evidence": (primary_text or combined_text)[:220],
                "suggestion": "请补充当日症状体征、重点查体、病情变化判断及具体诊疗处理。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.82),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc070_consultation_execution_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id not in {"SC-070", "LX-016"}:
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        if status == "non_compliant":
            return engine_result
        combined_text = SichuanQCService._rule_input_combined_text(rule_input)
        source_documents = [dict(item) for item in list(rule_input.source_documents or []) if isinstance(item, dict)]
        consultation_docs = [
            str(item.get("content") or "").strip()
            for item in source_documents
            if str(item.get("source_table") or item.get("document_type") or "").strip() == "consultation_record"
            and str(item.get("content") or "").strip()
        ]
        course_docs = [
            str(item.get("content") or "").strip()
            for item in source_documents
            if str(item.get("source_table") or item.get("document_type") or "").strip()
            in {"daily_course_record", "senior_course_record"}
            and str(item.get("content") or "").strip()
        ]
        if not combined_text and consultation_docs:
            combined_text = "\n".join(consultation_docs + course_docs)
        if not combined_text or "会诊" not in combined_text:
            return engine_result

        empty_consultation_record = bool(re.search(r"会诊记录[^\n]{0,20}(?:医生签名|医师签名)\s*[:：]?\s*(?:\n|$)", combined_text))
        has_consultation_without_execution_course = bool(consultation_docs) and not any("会诊" in text for text in course_docs)
        generic_followed_only = any(token in combined_text for token in ("遵会诊意见执行", "遵执", "遵医嘱执行"))
        has_specific_execution = any(
            token in combined_text
            for token in (
                "已予",
                "已执行",
                "调整为",
                "改用",
                "停用",
                "换用",
                "复查",
                "请药学",
                "抗感染",
                "万古霉素",
                "哌拉西林",
            )
        )
        if not (empty_consultation_record or has_consultation_without_execution_course or (generic_followed_only and not has_specific_execution)):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc070_missing_or_generic_execution"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "会诊相关记录为空壳，或仅写遵会诊意见执行，未记录具体执行措施。",
                "evidence": combined_text[:240],
                "suggestion": "请补充会诊意见的实际执行情况，包括用药、检查、复查、处置或未执行原因。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.84),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc039_critical_value_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-039":
            return engine_result
        status = str(engine_result.get("status") or "").strip().lower()
        if status == "non_compliant":
            return engine_result
        combined_text = SichuanQCService._rule_input_combined_text(rule_input)
        if not combined_text:
            return engine_result

        has_critical_context = "危急值" in combined_text or bool(re.search(r"\bK\s*[:：]?\s*\d+(?:\.\d+)?\s*mmol/?l\b", combined_text, flags=re.I))
        has_typo_or_incomplete = any(token in combined_text for token in ("接电脑危急值", "尽描写", "仅记录", "未写明原因"))
        has_risk_level_change = "病危" in combined_text and "病重" in combined_text and any(token in combined_text for token in ("改为", "修改", "调整"))
        if not (has_critical_context and (has_typo_or_incomplete or has_risk_level_change)):
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc039_critical_value_record_defect"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "危急值处置记录存在明显错别字、记录过简或病危/病重变更原因不清，影响处置记录完整性。",
                "evidence": combined_text[:240],
                "suggestion": "请补充危急值报告时间、接收人、患者评估、具体处置、复查结果及病情等级变更原因。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.84),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc146_preop_order_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-146":
            return engine_result
        status = str(engine_result.get("status") or "").strip().lower()
        if status == "non_compliant":
            return engine_result
        combined_text = SichuanQCService._rule_input_combined_text(rule_input)
        if not combined_text:
            return engine_result
        has_preop_timing_defect = (
            ("术前小结" in combined_text or "术前讨论" in combined_text)
            and ("手术医嘱" in combined_text or "手术" in combined_text)
            and any(token in combined_text for token in ("之前", "早于", "已下达", "明日行"))
        )
        if not has_preop_timing_defect:
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc146_preop_order_before_record"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "手术医嘱或手术安排早于术前小结/术前讨论等必要病程记录，存在诊疗记录时序不一致。",
                "evidence": combined_text[:240],
                "suggestion": "请核对术前小结、术前讨论、手术医嘱和病程记录时间顺序，并补充合理说明。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.84),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_preop_discussion_presence_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id not in {"SC-083", "SC-084"}:
            return engine_result
        status = str(engine_result.get("status") or "").strip().lower()
        if status == "non_compliant":
            return engine_result

        source_documents = [dict(item) for item in list(rule_input.source_documents or []) if isinstance(item, dict)]
        presurg_discussions = [
            str(item.get("content") or "").strip()
            for item in source_documents
            if str(item.get("source_table") or item.get("document_type") or "").strip() == "presurg_discussion"
            and str(item.get("content") or "").strip()
        ]
        presurg_summaries = [
            str(item.get("content") or "").strip()
            for item in source_documents
            if str(item.get("source_table") or item.get("document_type") or "").strip() == "presurg_summary"
            and str(item.get("content") or "").strip()
        ]
        surgery_context = any(
            str(item.get("content") or "").strip()
            for item in source_documents
            if str(item.get("source_table") or item.get("document_type") or "").strip() == "surgery_record"
        )
        if normalized_rule_id == "SC-083":
            has_mdt_text = any(("多学科" in text or "MDT" in text.upper()) for text in presurg_discussions + presurg_summaries)
            if presurg_discussions and has_mdt_text:
                return engine_result
            if not surgery_context and not presurg_summaries:
                return engine_result
            finding = "未检测到术前讨论/MDT记录正文，或术前讨论记录未体现多学科讨论。"
            evidence = "术前讨论正文缺失" if not presurg_discussions else (presurg_discussions[0][:220])
        else:
            if not presurg_discussions:
                if not surgery_context and not presurg_summaries:
                    return engine_result
                finding = "未检测到术前讨论记录正文，无法体现术前讨论结论。"
                evidence = "术前讨论正文缺失"
            else:
                discussion_text = "\n".join(presurg_discussions)
                missing_fields = [field for field in ("手术时间", "手术医生", "术者", "主刀") if field not in discussion_text]
                if not missing_fields:
                    return engine_result
                finding = "术前讨论记录缺少手术时间或手术医生等关键结论要素。"
                evidence = discussion_text[:220]

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "preop_discussion_presence_or_key_fields"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": finding,
                "evidence": evidence,
                "suggestion": "请补齐术前讨论/MDT记录，并明确讨论结论、手术时间、术者及关键诊疗意见。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.84),
                "metadata": metadata,
            }
        )
        return normalized

    def _apply_lx020_preop_round_order_fallback(
        self,
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id not in {"LX-020", "SC-086"}:
            return engine_result
        status = str(engine_result.get("status") or "").strip().lower()
        if status == "non_compliant":
            return engine_result

        preop_round_events = self._extract_sc146_preop_round_events(rule_input.source_documents)
        preop_summary_events = [
            item
            for item in self._extract_sc146_preop_events(rule_input.source_documents)
            if str(item.get("source_table") or "").strip() == "presurg_summary"
        ]
        if not preop_round_events or not preop_summary_events:
            return engine_result
        earliest_round = preop_round_events[0]
        earliest_summary = preop_summary_events[0]
        if earliest_round["parsed_time"] <= earliest_summary["parsed_time"]:
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "lx020_preop_round_after_summary"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": (
                    f"术前主刀/上级查房时间晚于术前小结：{earliest_round['document_title']} "
                    f"{earliest_round['display_time']}，晚于 {earliest_summary['document_title']} {earliest_summary['display_time']}。"
                ),
                "evidence": (
                    f"术前查房：{earliest_round['document_title']} @ {earliest_round['display_time']}；"
                    f"术前小结：{earliest_summary['document_title']} @ {earliest_summary['display_time']}。"
                ),
                "suggestion": "请核对术前查房与术前小结时间顺序，确保术前小结不早于其所回顾的术前查房。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.88),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _apply_sc026_text_only_fallback(
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-026":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant" or not primary_text:
            return engine_result

        has_differential_heading = "鉴别诊断" in primary_text
        has_reasoning_context = any(
            keyword in primary_text
            for keyword in ("腹痛", "腹泻", "纳差", "干呕", "右下腹", "附件区", "肝硬化")
        )
        thin_differential = False
        if not has_differential_heading and has_reasoning_context:
            thin_differential = True
        elif has_differential_heading:
            diff_segment = primary_text.split("鉴别诊断", 1)[-1][:220]
            has_multiple_candidates = any(token in diff_segment for token in ("；", ";", "2、", "②", "其二"))
            has_weak_reasoning = any(token in diff_segment for token in ("待排", "不除外", "表现为", "完善"))
            if not has_multiple_candidates and has_weak_reasoning:
                thin_differential = True

        if not thin_differential:
            return engine_result

        normalized = dict(engine_result)
        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = "sc026_text_only"
        normalized.update(
            {
                "is_compliant": False,
                "status": "non_compliant",
                "findings": "当前病程文本未见充分的鉴别诊断推理，表现为未单列鉴别诊断，或仅列单一候选疾病且排除依据不足。",
                "evidence": primary_text[:220],
                "suggestion": "请补充与当前症状/检查相匹配的主要鉴别疾病，并写明支持或不支持依据。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.82),
                "metadata": metadata,
            }
        )
        return normalized

    @staticmethod
    def _parse_display_time(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace("T", " ").replace("Z", "+00:00")
        if normalized.endswith("+08"):
            normalized = f"{normalized}:00"
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(normalized, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _extract_sc146_surgery_order_events(source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for item in source_documents:
            source_table = str(item.get("source_table") or "").strip()
            if source_table not in {"inpat_drug_order", "inpat_nondrug_order"}:
                continue
            content = str(item.get("content") or "").strip()
            title = str(item.get("document_title") or "").strip()
            payload = f"{title}\n{content}"
            if not any(keyword in payload for keyword in ("手术", "术后医嘱", "矫正术")):
                continue
            display_time = str(item.get("display_time") or item.get("record_time") or "").strip()
            parsed_time = SichuanQCService._parse_display_time(display_time)
            if parsed_time is None:
                continue
            events.append(
                {
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": title or source_table,
                    "display_time": display_time,
                    "parsed_time": parsed_time,
                    "content": content,
                    "source_table": source_table,
                }
            )
        events.sort(key=lambda item: item["parsed_time"])
        return events

    @staticmethod
    def _extract_sc146_preop_events(source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for item in source_documents:
            source_table = str(item.get("source_table") or "").strip()
            if source_table not in {"presurg_discussion", "presurg_summary"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            display_time = str(item.get("display_time") or item.get("record_time") or "").strip()
            parsed_time = SichuanQCService._parse_display_time(display_time)
            if parsed_time is None:
                continue
            events.append(
                {
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": str(item.get("document_title") or source_table),
                    "display_time": display_time,
                    "parsed_time": parsed_time,
                    "content": content,
                    "source_table": source_table,
                }
            )
        events.sort(key=lambda item: item["parsed_time"])
        return events

    @staticmethod
    def _extract_sc146_preop_round_events(source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for item in source_documents:
            source_table = str(item.get("source_table") or "").strip()
            if source_table not in {"daily_course_record", "senior_course_record"}:
                continue
            title = str(item.get("document_title") or "").strip()
            content = str(item.get("content") or "").strip()
            payload = f"{title}\n{content}"
            if not any(
                keyword in payload
                for keyword in (
                    "术前主刀医师",
                    "主刀医生查房",
                    "术者术前查看患者",
                    "术前查看患者",
                )
            ):
                continue
            display_time = str(item.get("display_time") or item.get("record_time") or "").strip()
            parsed_time = SichuanQCService._parse_display_time(display_time)
            if parsed_time is None:
                continue
            events.append(
                {
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": title or source_table,
                    "display_time": display_time,
                    "parsed_time": parsed_time,
                    "content": content,
                    "source_table": source_table,
                }
            )
        events.sort(key=lambda item: item["parsed_time"])
        return events

    def _apply_sc146_temporal_fallback(
        self,
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
        surgery_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_rule_id = str(rule_input.rule_id or "").strip().upper()
        if normalized_rule_id != "SC-146":
            return engine_result

        status = str(engine_result.get("status") or "").strip().lower()
        primary_text = str(rule_input.primary_medical_text or "").strip()
        if status == "non_compliant":
            return engine_result

        order_events = self._extract_sc146_surgery_order_events(rule_input.source_documents)
        preop_events = self._extract_sc146_preop_events(list((surgery_bundle or {}).get("source_documents") or []))
        preop_round_events = self._extract_sc146_preop_round_events(rule_input.source_documents)
        preop_summary_events = [
            item for item in preop_events if str(item.get("source_table") or "").strip() == "presurg_summary"
        ]
        metadata = dict(engine_result.get("metadata") or {})
        normalized = dict(engine_result)

        if order_events and preop_events:
            earliest_order = order_events[0]
            earliest_preop = preop_events[0]
            if earliest_order["parsed_time"] < earliest_preop["parsed_time"]:
                metadata["llm_fallback"] = True
                metadata["decision_fallback"] = "sc146_temporal_order_before_preop"
                normalized.update(
                    {
                        "is_compliant": False,
                        "status": "non_compliant",
                        "findings": (
                            f"手术相关医嘱时间早于术前文书：{earliest_order['document_title']} "
                            f"{earliest_order['display_time']}，早于 {earliest_preop['document_title']} "
                            f"{earliest_preop['display_time']}。"
                        ),
                        "evidence": (
                            f"医嘱：{earliest_order['document_title']} @ {earliest_order['display_time']}；"
                            f"术前文书：{earliest_preop['document_title']} @ {earliest_preop['display_time']}。"
                        ),
                        "suggestion": "请核对手术医嘱下达时间与术前讨论/术前小结时间，补充或更正手术时序记录。",
                        "confidence": max(float(engine_result.get("confidence") or 0.0), 0.9),
                        "metadata": metadata,
                    }
                )
                return normalized

        if preop_round_events and preop_summary_events:
            earliest_preop_round = preop_round_events[0]
            earliest_preop_summary = preop_summary_events[0]
            if earliest_preop_round["parsed_time"] > earliest_preop_summary["parsed_time"]:
                metadata["llm_fallback"] = True
                metadata["decision_fallback"] = "sc146_preop_round_after_summary"
                normalized.update(
                    {
                        "is_compliant": False,
                        "status": "non_compliant",
                        "findings": (
                            f"术前主刀医生查房记录时间晚于术前小结：{earliest_preop_round['document_title']} "
                            f"{earliest_preop_round['display_time']}，晚于 {earliest_preop_summary['document_title']} "
                            f"{earliest_preop_summary['display_time']}。"
                        ),
                        "evidence": (
                            f"术前主刀查房：{earliest_preop_round['document_title']} @ {earliest_preop_round['display_time']}；"
                            f"术前小结：{earliest_preop_summary['document_title']} @ {earliest_preop_summary['display_time']}。"
                        ),
                        "suggestion": "请核对术前主刀医生查房记录与术前小结的书写时序，确保术前小结不会早于所回顾的术前查房记录。",
                        "confidence": max(float(engine_result.get("confidence") or 0.0), 0.88),
                        "metadata": metadata,
                    }
                )
                return normalized

        if not order_events or not preop_events:
            return engine_result

        primary_is_discharge_note = "出院情况" in primary_text and "出院医嘱" in primary_text
        if status in {"uncertain", "compliant"} and primary_is_discharge_note:
            metadata["llm_fallback"] = True
            metadata["decision_fallback"] = "sc146_temporal_order_after_preop"
            normalized.update(
                {
                    "is_compliant": True,
                    "status": "uncertain",
                    "findings": (
                        f"当前可见手术医嘱时间为 {earliest_order['display_time']}，晚于术前文书 "
                        f"{earliest_preop['display_time']}；但医嘱缺少明确下达时间字段，"
                        "仅凭 update_time 无法支持“术前小结及术前讨论之前已下达手术医嘱”这一问题。"
                    ),
                    "evidence": (
                        f"医嘱：{earliest_order['document_title']} @ {earliest_order['display_time']}；"
                        f"术前文书：{earliest_preop['document_title']} @ {earliest_preop['display_time']}。"
                    ),
                    "suggestion": "请人工复核源系统中的医嘱下达时间/签发时间，确认是否存在早于术前文书的手术医嘱。",
                    "confidence": max(float(engine_result.get("confidence") or 0.0), 0.82),
                    "metadata": metadata,
                }
            )
        return normalized

    def _apply_rule_text_only_fallbacks(
        self,
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
        surgery_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = self._apply_sc039_text_only_fallback(
            rule_input=rule_input,
            engine_result=engine_result,
        )
        normalized = self._apply_sc069_text_only_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc008_text_only_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc033_text_only_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc036_supporting_evidence_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc032_thin_course_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc070_consultation_execution_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc039_critical_value_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc026_text_only_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_sc146_temporal_fallback(
            rule_input=rule_input,
            engine_result=normalized,
            surgery_bundle=surgery_bundle,
        )
        normalized = self._apply_sc146_preop_order_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_preop_discussion_presence_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_lx020_preop_round_order_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        normalized = self._apply_copy_content_semantic_fallback(
            rule_input=rule_input,
            engine_result=normalized,
        )
        return normalized

    def _apply_copy_content_semantic_fallback(
        self,
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(engine_result or {})
        rule_id = str(rule_input.rule_id or "").strip().upper()
        if rule_id not in {"CL-037", "CL-275"}:
            return normalized

        source_documents = [dict(item) for item in list(rule_input.source_documents or []) if isinstance(item, dict)]
        if not source_documents:
            return normalized

        primary_source_document = max(
            source_documents,
            key=lambda item: self._score_primary_candidate_for_rule(rule_id=rule_id, candidate=item),
        )
        derived_signals = self._build_copy_content_similarity_signals(
            primary_document=primary_source_document,
            source_documents=source_documents,
            rule_ids=[rule_id],
        )
        if not derived_signals:
            return normalized

        similarity_signal = next(
            (
                item for item in derived_signals
                if str(item.get("signal_type") or "").strip() == "adjacent_round_similarity"
            ),
            None,
        )
        if not similarity_signal:
            return normalized

        similarity_ratio = float(similarity_signal.get("similarity_ratio") or 0.0)
        later_to_earlier_cover = float(similarity_signal.get("later_to_earlier_sentence_coverage") or 0.0)
        if (
            similarity_ratio < _COPY_SIMILARITY_THRESHOLD
            and later_to_earlier_cover < _ROUND_LATER_COVERAGE_THRESHOLD
        ):
            return normalized

        semantic_checks = dict(normalized.get("semantic_checks") or {})
        has_new_analysis = semantic_checks.get("has_new_analysis")
        has_new_plan = semantic_checks.get("has_new_plan")
        llm_raw_output = str(normalized.get("llm_raw_output") or "").strip()
        allow_program_only_fallback = (
            rule_id == "CL-275"
            and not llm_raw_output
            and has_new_analysis is None
            and has_new_plan is None
            and later_to_earlier_cover >= 0.9
            and similarity_ratio >= 0.55
        )
        if not allow_program_only_fallback and (
            has_new_analysis is not False or has_new_plan is not False
        ):
            return normalized

        metadata = dict(normalized.get("metadata") or {})
        metadata["llm_fallback"] = True
        metadata["decision_fallback"] = (
            "copy_content_similarity_without_llm_output"
            if allow_program_only_fallback
            else "copy_content_similarity_plus_semantic_check"
        )
        metadata["final_decision_source"] = "rule_aggregate"
        metadata["semantic_checks"] = semantic_checks
        metadata["derived_signals"] = derived_signals

        primary_time = str(similarity_signal.get("primary_display_time") or "")
        compare_time = str(similarity_signal.get("compare_display_time") or "")
        if allow_program_only_fallback:
            findings = (
                f"后一天病程/查房被前一天覆盖率为 {later_to_earlier_cover:.2f}，全文相似度为 {similarity_ratio:.2f}，"
                "程序比对已显示高度重复，符合不合理复制病历内容特征。"
            )
            evidence = (
                f"主文书时间：{primary_time}；对照文书时间：{compare_time}；"
                f"后一天被前一天句子覆盖率={later_to_earlier_cover:.2f}，全文相似度={similarity_ratio:.2f}。"
            )
        else:
            findings = (
                f"后一天病程/查房被前一天覆盖率为 {later_to_earlier_cover:.2f}，全文相似度为 {similarity_ratio:.2f}，"
                "且未见明确新增病情分析或后续计划，"
                "符合不合理复制病历内容的高度重复特征。"
            )
            evidence = (
                f"主文书时间：{primary_time}；对照文书时间：{compare_time}；"
                f"后一天被前一天句子覆盖率={later_to_earlier_cover:.2f}，全文相似度={similarity_ratio:.2f}，semantic_checks 显示"
                " has_new_analysis=false、has_new_plan=false。"
            )
        normalized.update(
            {
                "status": "non_compliant",
                "is_compliant": False,
                "findings": findings,
                "evidence": evidence,
                "suggestion": "请避免直接复用既往病程/查房正文，补充本次记录的新增病情分析、诊疗判断及具体后续计划。",
                "confidence": max(float(normalized.get("confidence") or 0.0), 0.86),
                "metadata": metadata,
            }
        )
        return normalized

    def _apply_sc050_similarity_semantic_fallback(
        self,
        *,
        rule_input: RuleExecutionInput,
        engine_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        # 历史兼容：SC-050 不再承担复制粘贴专项兜底，保留空操作包装器以兼容旧调用/测试。
        return dict(engine_result or {})

    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        *,
        evidence_source: str = "medical_text",
        evidence_payload: Optional[Dict[str, Any]] = None,
        bucket_strategy: str = "domain_only",
        quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
        batch_output_mode: str = BATCH_OUTPUT_MODE_FULL,
        enable_selective_refine: bool = False,
        refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
        max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
        use_execution_cache: bool = True,
        rule_set_key: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        对单个病历文档进行质控评估。

        Args:
            document_id: 文档 ID
            content: 病历内容
            document_type: 文书类型（默认为 "病程记录"）
            rule_ids: 可选的规则ID列表，用于过滤只评估指定的规则

        Returns:
            质控评估结果，包含：
            - document_id: 文档 ID
            - document_type: 文书类型
            - total_rules: 适用规则总数
            - applicable_rules: 适用规则代码列表
            - evaluation_summary: 评估摘要
            - llm_output: LLM 原始输出
            - token_usage: Token 使用量
            - api_time: API 调用时间
        """
        rules = await self._resolve_rules_for_document(
            document_type=document_type,
            rule_ids=rule_ids,
        )

        return await self.evaluate_document_with_rules(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules,
            evidence_source=evidence_source,
            evidence_payload=evidence_payload,
            bucket_strategy=bucket_strategy,
            quality_profile=quality_profile,
            batch_output_mode=batch_output_mode,
            enable_selective_refine=enable_selective_refine,
            refine_confidence_threshold=refine_confidence_threshold,
            max_refine_candidates=max_refine_candidates,
            use_execution_cache=use_execution_cache,
            rule_set_key=rule_set_key,
            cancellation_check=cancellation_check,
        )

    async def evaluate_document_with_rules(
        self,
        *,
        document_id: str,
        content: str,
        document_type: str,
        rules: List[Dict[str, Any]],
        evidence_source: str = "medical_text",
        evidence_payload: Optional[Dict[str, Any]] = None,
        bucket_strategy: str = "domain_only",
        quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
        batch_output_mode: str = BATCH_OUTPUT_MODE_FULL,
        enable_selective_refine: bool = False,
        refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
        max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
        use_execution_cache: bool = True,
        rule_set_key: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        prepared_rules = [self._ensure_rule_execution_meta(rule) for rule in rules]

        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=prepared_rules,
            evidence_source=evidence_source,
            evidence_payload=evidence_payload,
            bucket_strategy=bucket_strategy,
            quality_profile=quality_profile,
            batch_output_mode=batch_output_mode,
            enable_selective_refine=enable_selective_refine,
            refine_confidence_threshold=refine_confidence_threshold,
            max_refine_candidates=max_refine_candidates,
            use_execution_cache=use_execution_cache,
            rule_set_key=rule_set_key,
            cancellation_check=cancellation_check,
        )
        return self._build_document_evaluation_result(
            document_id=document_id,
            document_type=document_type,
            rules=prepared_rules,
            orchestrated=orchestrated,
        )

    async def evaluate_running_final_bundle_input(
        self,
        bundle: Dict[str, Any],
        *,
        rule_ids: Optional[List[str]] = None,
        bucket_strategy: str = "domain_only",
        quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
        batch_output_mode: str = BATCH_OUTPUT_MODE_FULL,
        enable_selective_refine: bool = False,
        refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
        max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
        use_execution_cache: bool = True,
        rule_set_key: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        通过 running/final bundle 输入复用旧规则链入口（evaluate_document）。

        说明：
        - 不改规则引擎本体；
        - 仅做输入适配；
        - 仅支持 running/final 场景。
        """
        from .qc_input_adapters import adapt_bundle_to_sichuan_eval_args
        from .qc_input_adapters import extract_bundle_documents

        scene = str((bundle or {}).get("scene") or "").strip().lower()
        if scene not in {"running", "final"}:
            raise ValueError(f"仅支持 running/final bundle，当前 scene={scene or 'unknown'}")

        eval_args = adapt_bundle_to_sichuan_eval_args(bundle, rule_ids=rule_ids or [])
        document_id = str(eval_args["document_id"])
        document_type = str(eval_args["document_type"])
        content = str(eval_args["content"])
        resolved_rule_ids = list(eval_args.get("rule_ids") or [])
        evidence_payload = dict(eval_args.get("evidence_payload") or {})
        quality_profile_normalized = normalize_quality_profile(quality_profile)

        selected_rules: List[Dict[str, Any]] = []
        if resolved_rule_ids:
            for rid in resolved_rule_ids:
                rule = self.get_rule_by_id(str(rid or "").strip())
                if rule:
                    selected_rules.append(self._ensure_rule_execution_meta(rule))
        else:
            selected_rules = await self._resolve_rules_for_document(
                document_type=document_type,
                rule_ids=resolved_rule_ids,
            )

        bundle_documents = [
            dict(item)
            for item in extract_bundle_documents(bundle)
            if str(item.get("content") or "").strip()
        ]

        if not selected_rules or not bundle_documents:
            orchestrated = await self._evaluate_rules_orchestrated(
                document_id=document_id,
                content=content,
                document_type=document_type,
                rules=selected_rules,
                evidence_source="bundle",
                evidence_payload=evidence_payload,
                bucket_strategy=bucket_strategy,
                quality_profile=quality_profile,
                batch_output_mode=batch_output_mode,
                enable_selective_refine=enable_selective_refine,
                refine_confidence_threshold=refine_confidence_threshold,
                max_refine_candidates=max_refine_candidates,
                use_execution_cache=use_execution_cache,
                rule_set_key=rule_set_key,
                cancellation_check=cancellation_check,
            )
        else:
            grouped_rules: Dict[str, Dict[str, Any]] = {}
            result_items: List[Dict[str, Any]] = []
            total_tokens = 0
            total_api_time = 0.0
            executor_breakdown_list: List[Dict[str, Any]] = []
            cache_breakdown_list: List[Dict[str, Any]] = []
            trace_items: List[Any] = []
            pack_metrics_list: List[Dict[str, Any]] = []
            refine_details: List[Dict[str, Any]] = []
            refine_candidate_count = 0
            refine_failed_count = 0
            refine_reasons_agg: Dict[str, int] = {}

            for rule in selected_rules:
                raise_if_cancelled(cancellation_check)
                matched_document = self._select_bundle_document_for_rule(
                    rule=rule,
                    bundle_documents=bundle_documents,
                )
                if matched_document is None:
                    result_items.append(
                        self._build_bundle_missing_doc_result_item(
                            rule=rule,
                            bucket_strategy=bucket_strategy,
                            quality_profile=quality_profile_normalized,
                        )
                    )
                    continue
                doc_key = str(matched_document.get("id") or matched_document.get("document_type") or "")
                slot = grouped_rules.setdefault(
                    doc_key,
                    {
                        "document": matched_document,
                        "rules": [],
                    },
                )
                slot["rules"].append(rule)

            for slot in grouped_rules.values():
                raise_if_cancelled(cancellation_check)
                primary_document = dict(slot.get("document") or {})
                primary_content = str(primary_document.get("content") or "").strip()
                primary_type = str(primary_document.get("document_type") or document_type or "病程记录")
                per_doc_evidence_payload = self._build_bundle_evidence_payload_for_document(
                    primary_document=primary_document,
                    all_documents=bundle_documents,
                    bundle=bundle,
                    rules=list(slot.get("rules") or []),
                )
                per_doc_orchestrated = await self._evaluate_rules_orchestrated(
                    document_id=f"{document_id}:{primary_document.get('source_table') or primary_type}",
                    content=primary_content,
                    document_type=primary_type,
                    rules=list(slot.get("rules") or []),
                    evidence_source="bundle",
                    evidence_payload=per_doc_evidence_payload,
                    bucket_strategy=bucket_strategy,
                    quality_profile=quality_profile,
                    batch_output_mode=batch_output_mode,
                    enable_selective_refine=enable_selective_refine,
                    refine_confidence_threshold=refine_confidence_threshold,
                    max_refine_candidates=max_refine_candidates,
                    use_execution_cache=use_execution_cache,
                    cancellation_check=cancellation_check,
                )
                result_items.extend(list(per_doc_orchestrated.get("results") or []))
                total_tokens += int(per_doc_orchestrated.get("total_tokens") or 0)
                total_api_time += float(per_doc_orchestrated.get("total_api_time") or 0.0)
                executor_breakdown_list.append(dict(per_doc_orchestrated.get("executor_breakdown") or {}))
                cache_breakdown_list.append(dict(per_doc_orchestrated.get("cache_breakdown") or {}))
                trace_items.extend(list(per_doc_orchestrated.get("trace") or []))
                pack_metrics_list.append(dict(per_doc_orchestrated.get("pack_metrics") or {}))
                refine_details.extend(list(per_doc_orchestrated.get("refine_details") or []))
                refine_summary = dict(per_doc_orchestrated.get("refine_summary") or {})
                refine_candidate_count += int(refine_summary.get("candidate_count") or 0)
                refine_failed_count += int(refine_summary.get("refine_failed_count") or 0)
                for reason, count in dict(refine_summary.get("refine_reasons") or {}).items():
                    refine_reasons_agg[str(reason)] = int(refine_reasons_agg.get(str(reason), 0)) + int(count or 0)

            orchestrated = {
                "results": result_items,
                "total_tokens": total_tokens,
                "total_api_time": total_api_time,
                "executor_breakdown": self._sum_counter_dicts(executor_breakdown_list),
                "cache_breakdown": self._sum_counter_dicts(cache_breakdown_list),
                "pack_metrics": self._merge_pack_metrics(
                    pack_metrics_list,
                    quality_profile=quality_profile_normalized,
                    bucket_strategy=bucket_strategy,
                ),
                "quality_profile": quality_profile_normalized,
                "refine_details": refine_details,
                "trace": trace_items,
                "refine_summary": {
                    "enabled": enable_selective_refine,
                    "candidate_count": refine_candidate_count,
                    "eligible_candidate_count": refine_candidate_count,
                    "refined_rule_count": sum(1 for item in result_items if bool((item.get("metadata") or {}).get("refined"))),
                    "refine_failed_count": refine_failed_count,
                    "budget_applied": max_refine_candidates,
                    "budget_skipped_count": 0,
                    "refine_reasons": refine_reasons_agg,
                },
                "refined_rule_count": sum(1 for item in result_items if bool((item.get("metadata") or {}).get("refined"))),
                "refine_reasons": refine_reasons_agg,
            }
            model_version = str(getattr(getattr(self, "client", None), "model", "") or "")
            settings = get_settings()
            if (
                str(rule_set_key or "").strip() == LUXIAN_0609_RULE_SET_KEY
                and settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED
            ):
                wrapper_rules = load_luxian_0609_rules()
                gate_decisions = {}
                if settings.LUXIAN_0609_TRIGGER_GATE_ENABLED:
                    gate_decisions = evaluate_luxian_0609_trigger_gates(
                        rules=wrapper_rules,
                        visit_id=str((bundle or {}).get("visit_id") or document_id or ""),
                        medical_text=content,
                        evidence_payload=evidence_payload,
                    )
                orchestrated.setdefault("results", [])
                orchestrated["results"].extend(
                    evaluate_luxian_0609_programmatic_rules(
                        wrapper_rules=wrapper_rules,
                        evidence_payload=evidence_payload,
                    )
                )
                customer_results = aggregate_luxian_0609_results(
                    wrapper_rules=wrapper_rules,
                    execution_results=list(orchestrated.get("results") or []),
                    gate_decisions=gate_decisions,
                    format_evidence=bool(settings.LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED),
                    audit_context={
                        "visit_id": str((bundle or {}).get("visit_id") or document_id or ""),
                        "model_name": model_version,
                        "evidence_payload": evidence_payload,
                    },
                )
                orchestrated["rule_set_key"] = LUXIAN_0609_RULE_SET_KEY
                orchestrated["luxian_0609_raw_result_count"] = len(orchestrated.get("results") or [])
                orchestrated["results"] = customer_results
                orchestrated["display_rule_ids"] = [
                    str(rule.get("rule_id") or rule.get("rule_code") or "")
                    for rule in wrapper_rules
                ]
                orchestrated["display_rule_count"] = len(customer_results)
                orchestrated["luxian_0609_execution_rule_count"] = len(selected_rules)
                orchestrated["luxian_0609_summary"] = summarize_luxian_0609_results(customer_results)
        result = self._build_document_evaluation_result(
            document_id=document_id,
            document_type="终末病历" if scene == "final" else "运行病历",
            rules=selected_rules,
            orchestrated=orchestrated,
        )
        result["bundle_metadata"] = {
            "scene": scene,
            "visit_id": str((bundle or {}).get("visit_id") or ""),
            "policy_version": str((bundle or {}).get("policy_version") or ""),
            "bundle_schema_version": str((bundle or {}).get("bundle_schema_version") or ""),
            "document_hits": (bundle or {}).get("document_hits") or {},
            "text_available": bool((bundle or {}).get("text_available")),
            "adapter_version": str((eval_args.get("metadata") or {}).get("adapter_version") or ""),
            "compat_strategy": str((eval_args.get("metadata") or {}).get("compat_strategy") or ""),
        }
        result["evidence_payload"] = evidence_payload
        return result

    async def evaluate_rule_for_visit(
        self,
        *,
        rule_id: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        source_schema: Optional[str] = None,
        bundle_schema: str = "public",
        force_refresh_bundle: bool = False,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        raise_if_cancelled(cancellation_check)
        rule = self.get_rule_by_id(str(rule_id or "").strip())
        if not rule:
            raise ValueError(f"规则不存在: {rule_id}")

        routing = route_rule_to_domain(rule)
        domain_bundle = load_or_assemble_domain_bundle(
            execution_domain=routing.execution_domain,
            institute_id=str(institute_id or "").strip(),
            patient_id=str(patient_id or "").strip(),
            visit_id=str(visit_id or "").strip(),
            source_schema=source_schema,
            bundle_schema=bundle_schema,
            force_refresh=force_refresh_bundle,
        )
        surgery_bundle: Optional[Dict[str, Any]] = None
        if str(rule.get("rule_id") or "").strip().upper() == "SC-146":
            surgery_bundle = load_or_assemble_domain_bundle(
                execution_domain="surgery",
                institute_id=str(institute_id or "").strip(),
                patient_id=str(patient_id or "").strip(),
                visit_id=str(visit_id or "").strip(),
                source_schema=source_schema,
                bundle_schema=bundle_schema,
                force_refresh=force_refresh_bundle,
            )

        try:
            rule_input = self._build_rule_execution_input_from_bundle(
                rule=rule,
                routing=routing,
                domain_bundle=domain_bundle,
            )
        except LookupError:
            return self._build_missing_primary_result(
                rule=rule,
                routing=routing,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                domain_bundle=domain_bundle,
            )

        normalized_rule_id = str(rule.get("rule_id") or "").strip().upper()
        if normalized_rule_id == "SC-070":
            consultation_bundle = load_or_assemble_domain_bundle(
                execution_domain="consult_discussion",
                institute_id=str(institute_id or "").strip(),
                patient_id=str(patient_id or "").strip(),
                visit_id=str(visit_id or "").strip(),
                source_schema=source_schema,
                bundle_schema=bundle_schema,
                force_refresh=force_refresh_bundle,
            )
            rule_input = self._merge_rule_input_with_bundle_documents(
                rule_input=rule_input,
                bundle=consultation_bundle,
                include_doc_types=("consultation_record",),
            )
        elif normalized_rule_id == "SC-146" and surgery_bundle is not None:
            rule_input = self._merge_rule_input_with_bundle_documents(
                rule_input=rule_input,
                bundle=surgery_bundle,
                include_doc_types=("presurg_discussion", "presurg_summary", "anesthesia_record", "postsurg_firstcourse_record"),
            )

        medical_text = render_rule_execution_medical_text(rule_input)
        raise_if_cancelled(cancellation_check)
        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=f"{visit_id}:{rule.get('rule_id')}",
            content=medical_text,
            document_type=rule_input.document_type,
            rules=[rule],
            evidence_source="bundle",
            cancellation_check=cancellation_check,
        )
        orchestrated_results = list(orchestrated.get("results") or [])
        if not orchestrated_results:
            raise ValueError("规则执行失败：未返回结果")
        engine_result = self._apply_rule_text_only_fallbacks(
            rule_input=rule_input,
            engine_result=orchestrated_results[0],
            surgery_bundle=surgery_bundle,
        )

        evaluation_results = [
            {
                "rule_id": engine_result.get("rule_id"),
                "rule_name": engine_result.get("rule_name"),
                "is_compliant": engine_result.get("is_compliant"),
                "status": engine_result.get("status"),
                "findings": engine_result.get("findings"),
                "evidence": engine_result.get("evidence"),
                "suggestion": engine_result.get("suggestion"),
                "confidence": engine_result.get("confidence"),
                "applicability": engine_result.get("applicability"),
                "evidence_verified": engine_result.get("evidence_verified"),
                "metadata": engine_result.get("metadata"),
            }
        ]
        status = str(engine_result.get("status") or "")
        not_applicable = 1 if status == "not_applicable" else 0
        compliant_rules = 1 if status in {"compliant", "not_applicable"} else 0
        issues_found = 1 if status == "non_compliant" else 0
        metadata = engine_result.get("metadata") or {}
        primary_source_document = {}
        if list(rule_input.source_documents or []):
            primary_source_document = max(
                (dict(item) for item in list(rule_input.source_documents or [])),
                key=lambda item: self._score_primary_candidate_for_rule(
                    rule_id=str(rule.get("rule_id") or rule.get("rule_code") or ""),
                    candidate=item,
                ),
            )
        derived_signals = self._build_copy_content_similarity_signals(
            primary_document=primary_source_document,
            source_documents=[dict(item) for item in list(rule_input.source_documents or [])],
            rule_ids=[str(rule.get("rule_id") or rule.get("rule_code") or "")],
        )
        return {
            "document_id": visit_id,
            "document_type": rule_input.document_type,
            "total_rules": 1,
            "applicable_rules": [str(rule.get("rule_id") or "")],
            "evaluation_summary": {
                "compliance_rate": 100.0 if compliant_rules else 0.0,
                "issues_found": issues_found,
                "not_applicable": not_applicable,
                "total_rules": 1,
                "compliant_rules": compliant_rules,
                "model": self.client.model,
            },
            "parsed_evaluation_results": [engine_result],
            "evaluation_results": evaluation_results,
            "llm_output": engine_result.get("llm_raw_output"),
            "token_usage": {"total_tokens": int(metadata.get("tokens_used") or 0)},
            "api_time": float(metadata.get("api_time") or 0.0),
            "routing": routing.to_dict(),
            "rule_execution_input": rule_input.to_dict(),
            "evidence_payload": build_evidence_payload_from_rule_input(
                rule_input=rule_input,
                document_hits=domain_bundle.get("document_hits") or {},
                data_quality_flags=domain_bundle.get("data_quality_flags") or [],
                derived_signals=derived_signals,
            ).to_dict(),
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            "pack_metrics": orchestrated.get("pack_metrics") or {},
            "trace": orchestrated.get("trace") or [],
            "bundle_metadata": {
                "execution_domain": routing.execution_domain,
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_hits": domain_bundle.get("document_hits") or {},
                "data_quality_flags": domain_bundle.get("data_quality_flags") or [],
                "bundle_schema_version": domain_bundle.get("bundle_schema_version") or "",
                "policy_version": domain_bundle.get("policy_version") or "",
            },
        }

    async def evaluate_batch(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for doc in documents:
            out.append(
                await self.evaluate_document(
                    document_id=doc.get("document_id", "unknown"),
                    content=doc.get("content", ""),
                    document_type=doc.get("document_type", "病程记录"),
                )
            )
        return out

    async def evaluate_document_fast(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        prompt_mode: str = "plan_a"
    ) -> Dict[str, Any]:
        """
        快速质控模式（P1 后收口版）：
        复用 orchestrator 执行链，保持 /evaluate-fast 响应壳兼容。
        """
        # 1) 加载规则（兼容旧逻辑）
        if rule_ids and len(rule_ids) > 0:
            selected_rules: List[Dict[str, Any]] = []
            for rid in rule_ids:
                try:
                    rule = self.get_rule_by_id(str(rid))
                    if rule:
                        selected_rules.append(rule)
                except Exception as e:
                    logger.warning(f"get_rule_by_id 失败: {rid} -> {e}")

            if selected_rules:
                rules = selected_rules
                logger.info(f"Selected {len(rules)} rules via get_rule_by_id from IDs: {rule_ids}")
            else:
                rules = await self._load_applicable_rules(document_type)
                rules = [
                    r for r in rules
                    if r.get("rule_id") in rule_ids or r.get("rule_code") in rule_ids or r.get("id") in rule_ids
                ]
                logger.info(f"Filtered to {len(rules)} rules based on rule_ids within loaded set: {rule_ids}")
        else:
            rules = await self._load_applicable_rules(document_type)

        if not rules:
            logger.warning(f"未找到适用的规则: document_type={document_type}, rule_ids={rule_ids}")
            return {
                "document_id": document_id,
                "evaluation_summary": {
                    "compliance_rate": 100.0,
                    "issues_found": 0,
                    "model": self.client.model
                },
                "evaluation_results": [],
                "performance_metrics": {
                    "token_usage": 0,
                    "estimated_cost": 0.0
                },
                "total_rules": 0,
                "llm_output": "未找到适用的规则"
            }

        # 2) 统一走 orchestrator
        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules,
            evidence_source="medical_text_fast",
        )
        rule_results = list(orchestrated.get("results") or [])

        evaluation_results = [
            {
                "rule_id": item.get("rule_id"),
                "rule_name": item.get("rule_name"),
                "is_compliant": item.get("is_compliant"),
                "status": item.get("status"),
                "findings": item.get("findings"),
                "evidence": item.get("evidence"),
                "suggestion": item.get("suggestion"),
                "confidence": item.get("confidence"),
                "applicability": item.get("applicability"),
                "evidence_verified": item.get("evidence_verified"),
                "metadata": item.get("metadata"),
            }
            for item in rule_results
        ]

        total_rules = len(rule_results)
        compliant_rules = sum(
            1 for r in evaluation_results
            if r.get("is_compliant") is True or r.get("status") in ("compliant", "not_applicable")
        )
        issues_found = total_rules - compliant_rules
        compliance_rate = (compliant_rules / total_rules * 100) if total_rules > 0 else 100.0

        token_usage = int(orchestrated.get("total_tokens") or 0)
        api_time = float(orchestrated.get("total_api_time") or 0.0)
        estimated_cost = (token_usage / 1000) * 0.002

        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": total_rules,
            "prompt_mode": prompt_mode,  # 添加 prompt_mode 到返回结果
            "evaluation_summary": {
                "total_rules": total_rules,
                "compliant_rules": compliant_rules,
                "issues_found": issues_found,
                "compliance_rate": compliance_rate,
                "model": self.client.model
            },
            "evaluation_results": evaluation_results,
            "performance_metrics": {
                "token_usage": token_usage,
                "api_time": api_time,
                "estimated_cost": estimated_cost
            },
            "parsed_evaluation_results": rule_results,
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            "trace": orchestrated.get("trace") or [],
            "llm_output": None,
            "mode": "orchestrated_fast",
        }

    def stats(self) -> Dict[str, Any]:
        return self.client.stats()

    async def evaluate_multi_document(
        self,
        document_id: str,
        document_content: str,
        document_types: Optional[List[str]] = None,
        preclassified_documents: Optional[Dict[str, Any]] = None,
        rules_by_document_type: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        # Build document map: {doc_type: content}
        def extract_text(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                return "\n\n".join(extract_text(v) for v in val)
            if isinstance(val, dict):
                # Common shapes: {content: text} or {sections: [...]}
                if "content" in val:
                    return extract_text(val["content"])
                if "sections" in val and isinstance(val["sections"], list):
                    return "\n\n".join(extract_text(s) for s in val["sections"])
                return "\n".join(f"{k}: {extract_text(v)}" for k, v in val.items())
            return str(val)

        doc_map: Dict[str, str] = {}
        if preclassified_documents:
            for k, v in preclassified_documents.items():
                doc_map[k] = extract_text(v)
        elif document_types:
            for t in document_types:
                doc_map[t] = document_content
        else:
            doc_map["病程记录"] = document_content

        n_docs = max(1, len(doc_map))

        # P0 任务 1: 从数据库加载规则（如果未提供预加载的规则）
        # 如果前端提供了 rules_by_document_type，优先使用
        # 否则，从数据库动态加载每种文书类型的规则
        if not rules_by_document_type:
            rules_by_document_type = {}
            for doc_type in doc_map.keys():
                rules_by_document_type[doc_type] = await self._load_applicable_rules(doc_type)
            logger.info(f"Loaded rules from database for {len(rules_by_document_type)} document types")

        document_results: Dict[str, Any] = {}
        total_tokens = 0
        total_time = 0.0
        sum_total_rules = 0
        sum_compliant = 0
        sum_not_applicable = 0
        sum_critical = 0

        for doc_type, text in doc_map.items():
            doc_rules = rules_by_document_type.get(doc_type, [])
            rule_results, tokens, api_time = await self._evaluate_rules_with_engine(
                document_id=document_id,
                content=text,
                document_type=doc_type,
                rules=doc_rules
            )

            total_rules = len(doc_rules)
            compliant = sum(
                1 for r in rule_results
                if r.get("status") in ("compliant", "not_applicable")
            )
            not_applicable = sum(1 for r in rule_results if r.get("status") == "not_applicable")
            critical_violations = sum(1 for r in rule_results if r.get("status") == "non_compliant")

            sum_total_rules += total_rules
            sum_compliant += compliant
            sum_not_applicable += not_applicable
            sum_critical += critical_violations
            total_tokens += tokens
            total_time += api_time

            document_results[doc_type] = {
                "total_rules": total_rules,
                "compliant_rules": compliant,
                "not_applicable": not_applicable,
                "processing_time": api_time,
                "token_usage": tokens,
                "critical_violations": critical_violations,
                "evaluation_results": rule_results,
            }

        overall_rate = (sum_compliant / max(sum_total_rules, 1)) * 100
        overall_grade = "A" if overall_rate >= 90 else "B" if overall_rate >= 75 else "C"
        document_breakdown = {}
        for dt, dr in document_results.items():
            total = dr.get("total_rules", 0)
            compliant = dr.get("compliant_rules", 0)
            document_breakdown[dt] = {
                "total_rules": total,
                "compliant_rules": compliant,
                "compliance_rate": round((compliant / total * 100) if total else 100.0, 2),
                "critical_violations": dr.get("critical_violations", 0),
                "not_applicable": dr.get("not_applicable", 0),
            }

        optimization_metrics = {
            "token_savings_rate": 0.0,
            "estimated_original_tokens": total_tokens,
            "actual_tokens_saved": 0,
            "cost_savings": 0.0,
        }

        return {
            "document_id": document_id,
            "overall_summary": {
                "total_rules": sum_total_rules,
                "compliant_rules": sum_compliant,
                "not_applicable": sum_not_applicable,
                "issues_found": sum_critical,
                "compliance_rate": round(overall_rate, 2),
                "overall_grade": overall_grade,
                "critical_violations": sum_critical,
                "document_breakdown": document_breakdown,
            },
            "total_processing_time": total_time,
            "total_token_usage": total_tokens,
            "optimization_metrics": optimization_metrics,
            "document_results": document_results,
        }

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        根据规则ID获取单个规则（支持四川省规则和自定义规则）

        Args:
            rule_id: 规则ID（如 "SC-010" 或 "LX-011"）

        Returns:
            规则对象，如果未找到则返回 None
        """
        normalized_rule_id = str(rule_id or "").strip().upper()
        if not normalized_rule_id:
            return None

        # 根据规则ID前缀明确区分规则来源
        # SC- 开头：优先治理表，再回退 JSON（但生产可被 strict guard 阻断）
        # LX- / LXE- 开头：优先治理表（若已纳管），否则回退 custom JSON
        # CL- 开头：客户专项规则，优先客户专项 JSON
        if normalized_rule_id.startswith("SC-"):
            rule, source = self.rule_registry.load_rule_by_id(normalized_rule_id)
            if rule:
                normalized = self._normalize_rule_documents(rule)
                logger.info("按 rule_id 命中 SC 规则（source=%s）: %s", source, normalized_rule_id)
                return normalized
            all_rules = self._load_active_sc_rules()
        elif normalized_rule_id.startswith("LX-") or normalized_rule_id.startswith("LXE-"):
            rule, source = self.rule_registry.load_rule_by_id(normalized_rule_id)
            if rule and source == "pg_governance":
                normalized = self._normalize_rule_documents(rule)
                logger.info("按 rule_id 命中 LX/LXE 规则（source=%s）: %s", source, normalized_rule_id)
                return normalized
            all_rules = self._load_custom_rules_from_json()
        elif normalized_rule_id.startswith("CL-"):
            all_rules = self._load_customer_rules_from_json()
        else:
            # 兼容旧调用：允许传入 rule_code/original_id，再从两套规则里回查
            all_rules = [
                *self._load_active_sc_rules(),
                *self._load_custom_rules_from_json(),
                *self._load_customer_rules_from_json(),
            ]

        for rule in all_rules:
            candidate_ids = {
                str(rule.get("rule_id") or "").strip().upper(),
                str(rule.get("rule_code") or "").strip().upper(),
                str(rule.get("original_id") or "").strip().upper(),
            }
            candidate_ids.discard("")
            if normalized_rule_id in candidate_ids:
                return rule

        logger.warning(f"未找到规则: {rule_id}")
        return None

    def update_rule_prompt(self, rule_id: str, custom_prompt: Optional[str], *, operator: str = "system") -> bool:
        """
        更新规则的自定义提示词（支持四川省规则和自定义规则）

        Args:
            rule_id: 规则ID（如 "SC-010" 或 "LX-011"）
            custom_prompt: 自定义提示词，如果为 None 则删除自定义提示词

        Returns:
            是否更新成功
        """
        import json
        import os

        normalized_rule_id = str(rule_id or "").strip().upper()
        if not normalized_rule_id:
            return False

        # 规则优先写治理表（版本化发布）。SC 在 strict/生产下不允许回退 JSON。
        updated_in_registry = self.rule_registry.update_rule_prompt_version(
            rule_id=normalized_rule_id,
            custom_prompt=custom_prompt,
            operator=operator,
        )
        if updated_in_registry:
            self.invalidate_rule_cache()
            logger.info("成功更新规则提示词（治理表）: %s", normalized_rule_id)
            return True

        if normalized_rule_id.startswith("SC-") and self._is_sc_source_strict_enabled():
            logger.error("SC 规则提示词更新失败且 strict_mode 开启，拒绝回退 JSON: %s", normalized_rule_id)
            return False
        logger.warning("治理表更新提示词失败，回退 JSON 文件兼容路径: %s", normalized_rule_id)

        def _rule_file_and_id(target: str) -> tuple[str, str] | None:
            if target.startswith("SC-"):
                return ("sichuan_rules_146.json", target)
            if target.startswith("LX-") or target.startswith("LXE-"):
                return ("custom_rules_33.json", target)
            if target.startswith("CL-"):
                return ("customer_rules_luxian_v1.json", target)

            # 兼容 rule_code/original_id 入参：回查规则并落到真实 rule_id
            resolved = self.get_rule_by_id(target)
            if not resolved:
                return None
            resolved_rule_id = str(resolved.get("rule_id") or "").strip().upper()
            if resolved_rule_id.startswith("SC-"):
                return ("sichuan_rules_146.json", resolved_rule_id)
            if resolved_rule_id.startswith("LX-") or resolved_rule_id.startswith("LXE-"):
                return ("custom_rules_33.json", resolved_rule_id)
            if resolved_rule_id.startswith("CL-"):
                return ("customer_rules_luxian_v1.json", resolved_rule_id)
            return None

        resolved_target = _rule_file_and_id(normalized_rule_id)
        if not resolved_target:
            logger.warning(f"未知的规则ID前缀: {rule_id}")
            return False

        json_filename, persisted_rule_id = resolved_target

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", json_filename
        )

        try:
            # 读取所有规则
            with open(json_path, "r", encoding="utf-8") as f:
                rules = json.load(f)

            # 查找并更新指定规则
            rule_found = False
            for rule in rules:
                if str(rule.get("rule_id") or "").strip().upper() == persisted_rule_id:
                    if custom_prompt is None:
                        # 删除自定义提示词
                        rule.pop("custom_prompt", None)
                    else:
                        # 设置自定义提示词
                        rule["custom_prompt"] = custom_prompt
                    rule_found = True
                    break

            if not rule_found:
                return False

            # 保存回文件
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)

            # 清除缓存，强制下次重新加载
            self.invalidate_rule_cache()

            logger.info(f"成功更新规则 {persisted_rule_id} 的提示词（文件：{json_filename}）")
            return True

        except Exception as e:
            logger.error(f"更新规则提示词失败: {e}", exc_info=True)
            return False
