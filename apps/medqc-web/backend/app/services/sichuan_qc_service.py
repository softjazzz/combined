from typing import Dict, Any, List, Optional, Tuple
import time
import logging

from ..core.settings import get_settings
from ..core.http import safe_post_json
from ..core.supabase_client import get_supabase
from .unified_rule_engine import UnifiedRuleEngine
from .llm_config_loader import LLMConfigLoader
from .qc_llm_client import SichuanQCLLMClient  # 拆分出的 LLM 客户端
from .qc_prompt_builder import QCPromptBuilder  # 拆分出的 Prompt 构建器

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
        results: List[Dict[str, Any]] = []
        total_tokens = 0
        total_api_time = 0.0

        for rule in rules:
            engine_result = await self.rule_engine.evaluate(
                rule,
                medical_record={
                    "id": document_id,
                    "content": content,
                    "document_type": document_type,
                },
            )
            results.append(engine_result)
            meta = engine_result.get("metadata", {}) or {}
            total_tokens += int(meta.get("tokens_used") or 0)
            total_api_time += float(meta.get("api_time") or 0.0)

        return results, total_tokens, total_api_time



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

        # 使用统一规则引擎逐条执行
        rule_results, total_tokens, total_api_time = await self._evaluate_rules_with_engine(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=rules
        )

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
            },
            "parsed_evaluation_results": rule_results,
            "evaluation_results": evaluation_results,
            "llm_output": None,
            "token_usage": {"total_tokens": total_tokens},
            "api_time": total_api_time,
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
        快速质控模式：一次性调用 LLM 评估所有规则（批量模式）

        与 evaluate_document 的区别：
        - evaluate_document: 逐条规则调用 LLM（串行模式）
        - evaluate_document_fast: 一次调用评估所有规则（快速模式）

        Args:
            document_id: 文档 ID
            content: 病历内容
            document_type: 文书类型（默认为 "病程记录"）
            rule_ids: 可选的规则ID列表，用于过滤只评估指定的规则
            prompt_mode: 提示词优化方案（current/plan_a/plan_b/plan_c）

        Returns:
            质控评估结果
        """
        # 1. 加载规则
        if rule_ids and len(rule_ids) > 0:
            # 与串行模式保持一致：优先通过 get_rule_by_id 精确加载规则
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
                # 回退：从数据库按文书类型加载，再按 rule_ids 过滤
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

        # 3. 构建批量提示词（传递 prompt_mode）
        prompt = await self._build_prompt(rules, content, document_type, prompt_mode)

        # 4. 调用 LLM（一次性评估所有规则）
        api_start = time.time()
        llm_response = await self.client.generate(prompt)
        api_time = time.time() - api_start

        # 5. 解析响应
        llm_output = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        token_usage = llm_response.get("usage", {}).get("total_tokens", 0)

        # 6. 解析 JSON 结果
        try:
            evaluation_results = self._parse_llm_json_response(llm_output, rules)
        except Exception as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            evaluation_results = []

        # 7. 计算统计信息
        total_rules = len(rules)
        compliant_rules = sum(
            1 for r in evaluation_results
            if r.get("is_compliant") is True or r.get("status") in ("compliant", "not_applicable")
        )
        issues_found = total_rules - compliant_rules
        compliance_rate = (compliant_rules / total_rules * 100) if total_rules > 0 else 100.0

        # 8. 计算成本（假设 ¥0.002/1000 tokens）
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
            "llm_output": llm_output
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
        # 根据规则ID前缀明确区分规则来源
        # SC- 开头：四川省规则（sichuan_rules_146.json）
        # LX- / LXE- 开头：泸县自定义规则（custom_rules_33.json）
        if rule_id.startswith("SC-"):
            all_rules = self._load_rules_from_json()
        elif rule_id.startswith("LX-") or rule_id.startswith("LXE-"):
            all_rules = self._load_custom_rules_from_json()
        else:
            logger.warning(f"未知的规则ID前缀: {rule_id}")
            return None

        for rule in all_rules:
            if rule.get("rule_id") == rule_id:
                return rule
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

        # 根据规则ID前缀明确确定要更新的文件
        # SC- 开头：四川省规则（sichuan_rules_146.json）
        # LX- 开头：自定义规则（custom_rules_33.json）
        if rule_id.startswith("SC-"):
            json_filename = "sichuan_rules_146.json"
        elif rule_id.startswith("LX-"):
            json_filename = "custom_rules_33.json"
        else:
            logger.warning(f"未知的规则ID前缀: {rule_id}")
            return False

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
                if rule.get("rule_id") == rule_id:
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
            if rule_id.startswith("SC-"):
                self._rules_cache = None

            logger.info(f"成功更新规则 {rule_id} 的提示词（文件：{json_filename}）")
            return True

        except Exception as e:
            logger.error(f"更新规则提示词失败: {e}", exc_info=True)
            return False
