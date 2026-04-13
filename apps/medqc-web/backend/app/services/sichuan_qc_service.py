from typing import Dict, Any, List, Optional, Tuple
import logging

from ..core.settings import get_settings
from ..core.http import safe_post_json
from ..core.supabase_client import get_supabase
from .unified_rule_engine import UnifiedRuleEngine
from .llm_config_loader import LLMConfigLoader
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

logger = logging.getLogger(__name__)

# SichuanQCLLMClient 已拆分至 qc_llm_client.py
# 通过上方 import 重新导出，外部引用不受影响



class SichuanQCService:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化四川质控服务

        Args:
            config: LLM 配置字典，如果为 None 则从 .env 文件加载
        """
        # LLM 客户端（config 为 None 时，SichuanQCLLMClient 自动从 .env 加载）
        self.client = SichuanQCLLMClient(config)

        # 规则缓存
        self._rules_cache: Optional[List[Dict[str, Any]]] = None
        self._custom_rules_cache: Optional[List[Dict[str, Any]]] = None

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

        execution_domain = str(normalized.get("execution_domain") or "").strip().lower()
        if not execution_domain:
            execution_domain = route_rule_to_domain(normalized).execution_domain
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

        return normalized

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

        import json
        import os

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", "sichuan_rules_146.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
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

        import json
        import os

        json_path = os.path.join(
            os.path.dirname(__file__),
            "..", "data", "custom_rules_33.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
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

    async def _load_applicable_rules(self, document_type: str) -> List[Dict[str, Any]]:
        """
        加载适用于指定文书类型的质控规则（统一从 JSON 文件加载）。

        Args:
            document_type: 文书类型（如 "病程记录"、"入院记录" 等）

        Returns:
            适用规则列表。如果加载失败，返回空列表。

        规则筛选逻辑：
        1. 通用规则（applicable_documents 为空）会被包含
        2. 特定规则（applicable_documents 包含指定的 document_type）会被包含
        """
        sc_rules = self._load_rules_from_json()
        custom_rules = self._load_custom_rules_from_json()
        # 合并并按 rule_id 去重，避免 LX 规则在两份文件中重复执行。
        merged_rules: Dict[str, Dict[str, Any]] = {}
        extra_rules: List[Dict[str, Any]] = []

        for rule in [*sc_rules, *custom_rules]:
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
            f"从 JSON 加载了 {len(applicable_rules)}/{len(all_rules)} 条适用于 '{document_type}' 的规则"
            f"（匹配类型: {sorted(target_doc_types)}）"
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
    ) -> Dict[str, Any]:
        prepared_rules = [self._ensure_rule_execution_meta(rule) for rule in rules]
        model_version = str(self.client.model or "")
        llm_concurrency = 6

        async def _llm_evaluate(rule: Dict[str, Any], medical_record: Dict[str, Any]) -> Dict[str, Any]:
            return await self.rule_engine.evaluate(rule, medical_record=medical_record)

        return await self.rule_orchestrator.evaluate_rules(
            rules=prepared_rules,
            medical_record={
                "id": document_id,
                "content": content,
                "document_type": document_type,
            },
            llm_evaluate=_llm_evaluate,
            evidence_source=evidence_source,
            llm_concurrency=llm_concurrency,
            model_version=model_version,
            execution_cache=self.execution_cache,
            cache_ttl_seconds=1800,
        )

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

    def _build_rule_execution_input_from_bundle(
        self,
        *,
        rule: Dict[str, Any],
        routing: Any,
        domain_bundle: Dict[str, Any],
    ) -> RuleExecutionInput:
        source_documents = list(domain_bundle.get("source_documents") or [])
        primary_candidates = self._find_source_documents_for_types(
            source_documents,
            list(routing.primary_doc_types),
        )
        auxiliary_candidates = self._find_source_documents_for_types(
            source_documents,
            list(routing.aux_doc_types),
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

    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None
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
        # P0 任务 1: 从数据库加载规则（按文书类型）
        rules = await self._load_applicable_rules(document_type)

        # 如果指定了 rule_ids，优先按 ID 精确取规则（支持 SC-/LX- 前缀跨来源）
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
                # 回退：在已加载的规则集中按 ID 过滤（保持与旧行为兼容）
                rules = [
                    r for r in rules
                    if r.get("rule_id") in rule_ids or r.get("rule_code") in rule_ids or r.get("id") in rule_ids
                ]
                logger.info(f"Filtered to {len(rules)} rules based on rule_ids within loaded set: {rule_ids}")

        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules,
            evidence_source="medical_text",
        )
        rule_results = list(orchestrated.get("results") or [])
        total_tokens = int(orchestrated.get("total_tokens") or 0)
        total_api_time = float(orchestrated.get("total_api_time") or 0.0)

        total_rules = len(rules)
        compliant_rules = sum(
            1 for r in rule_results
            if r.get("status") in ("compliant", "not_applicable")
        )
        not_applicable_count = sum(1 for r in rule_results if r.get("status") == "not_applicable")
        issues_found = sum(1 for r in rule_results if r.get("status") == "non_compliant")
        compliance_rate = (compliant_rules / total_rules * 100.0) if total_rules else 100.0

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
            })

        logger.info(
            f"质控评估完成: {compliant_rules}/{total_rules} 条规则符合（含不适用），合规率 {compliance_rate:.1f}%"
        )

        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": total_rules,
            "applicable_rules": [r.get("rule_code", r.get("id", "")) for r in rules],
            "evaluation_summary": {
                "compliance_rate": round(compliance_rate, 2),
                "issues_found": issues_found,
                "not_applicable": not_applicable_count,
                "total_rules": total_rules,
                "compliant_rules": compliant_rules,
                "model": self.client.model,
                "executor_breakdown": orchestrated.get("executor_breakdown") or {},
                "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            },
            "parsed_evaluation_results": rule_results,
            "evaluation_results": evaluation_results,
            "llm_output": None,
            "token_usage": {"total_tokens": total_tokens},
            "api_time": total_api_time,
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            "trace": orchestrated.get("trace") or [],
        }

    async def evaluate_running_final_bundle_input(
        self,
        bundle: Dict[str, Any],
        *,
        rule_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        通过 running/final bundle 输入复用旧规则链入口（evaluate_document）。

        说明：
        - 不改规则引擎本体；
        - 仅做输入适配；
        - 仅支持 running/final 场景。
        """
        from .qc_input_adapters import adapt_bundle_to_sichuan_eval_args

        scene = str((bundle or {}).get("scene") or "").strip().lower()
        if scene not in {"running", "final"}:
            raise ValueError(f"仅支持 running/final bundle，当前 scene={scene or 'unknown'}")

        eval_args = adapt_bundle_to_sichuan_eval_args(bundle, rule_ids=rule_ids or [])
        result = await self.evaluate_document(
            document_id=str(eval_args["document_id"]),
            content=str(eval_args["content"]),
            document_type=str(eval_args["document_type"]),
            rule_ids=list(eval_args.get("rule_ids") or []),
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
    ) -> Dict[str, Any]:
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

        medical_text = render_rule_execution_medical_text(rule_input)
        orchestrated = await self._evaluate_rules_orchestrated(
            document_id=f"{visit_id}:{rule.get('rule_id')}",
            content=medical_text,
            document_type=rule_input.document_type,
            rules=[rule],
            evidence_source="bundle",
        )
        orchestrated_results = list(orchestrated.get("results") or [])
        if not orchestrated_results:
            raise ValueError("规则执行失败：未返回结果")
        engine_result = orchestrated_results[0]

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
            ).to_dict(),
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
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
        # SC- 开头：四川省规则（sichuan_rules_146.json）
        # LX- / LXE- 开头：泸县自定义规则（custom_rules_33.json）
        if normalized_rule_id.startswith("SC-"):
            all_rules = self._load_rules_from_json()
        elif normalized_rule_id.startswith("LX-") or normalized_rule_id.startswith("LXE-"):
            all_rules = self._load_custom_rules_from_json()
        else:
            # 兼容旧调用：允许传入 rule_code/original_id，再从两套规则里回查
            all_rules = [*self._load_rules_from_json(), *self._load_custom_rules_from_json()]

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

    def update_rule_prompt(self, rule_id: str, custom_prompt: Optional[str]) -> bool:
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

        def _rule_file_and_id(target: str) -> tuple[str, str] | None:
            if target.startswith("SC-"):
                return ("sichuan_rules_146.json", target)
            if target.startswith("LX-") or target.startswith("LXE-"):
                return ("custom_rules_33.json", target)

            # 兼容 rule_code/original_id 入参：回查规则并落到真实 rule_id
            resolved = self.get_rule_by_id(target)
            if not resolved:
                return None
            resolved_rule_id = str(resolved.get("rule_id") or "").strip().upper()
            if resolved_rule_id.startswith("SC-"):
                return ("sichuan_rules_146.json", resolved_rule_id)
            if resolved_rule_id.startswith("LX-") or resolved_rule_id.startswith("LXE-"):
                return ("custom_rules_33.json", resolved_rule_id)
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
            if persisted_rule_id.startswith("SC-"):
                self._rules_cache = None

            logger.info(f"成功更新规则 {persisted_rule_id} 的提示词（文件：{json_filename}）")
            return True

        except Exception as e:
            logger.error(f"更新规则提示词失败: {e}", exc_info=True)
            return False
