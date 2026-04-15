from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple


LLMGenerateFn = Callable[[str], Awaitable[Dict[str, Any]]]


@dataclass
class ApplicabilityResult:
    is_applicable: bool
    reason: str = ""
    method: str = "unknown"


class ApplicabilityChecker:
    """
    针对规则的适用性检查。
    检查顺序：
    1. 文书类型匹配（applicable_documents vs 当前文书类型）
    2. 手术标志检测（手术类规则仅对手术患者适用）
    3. 年龄/规则特定逻辑（如 LX-003 婴幼儿、LX-006 儿科年龄段）
    """

    PEDIATRIC_HINTS = ["患儿", "婴儿", "新生儿", "儿科", "月龄"]

    # 仅适用于手术患者的规则 ID 前缀/集合
    SURGERY_ONLY_RULES = {
        "SC-080", "SC-081", "SC-082", "SC-083", "SC-084", "SC-085",  # 术前小结/讨论
        "SC-086", "SC-092", "SC-093", "SC-094", "SC-095", "SC-096",  # 麻醉/手术记录
        "SC-097", "SC-098", "SC-099", "SC-100", "SC-101", "SC-102",
        "SC-103", "SC-104", "SC-105", "SC-106", "SC-107", "SC-108",
        "SC-109", "SC-110", "SC-111", "SC-112", "SC-113", "SC-114",
        "SC-115",
        "LX-019", "LX-020", "LX-021", "LX-022", "LX-023", "LX-024",
        "LX-025", "LX-026", "LX-027", "LX-028",
    }

    SURGERY_HINTS = ["手术", "术中", "术后", "术前", "麻醉", "切除", "切开",
                     "缝合", "PCI", "介入", "植入", "移植", "造口"]

    # 英文→中文文书类型映射（从共享常量导入，避免重复维护）
    from app.constants.doc_types import DOC_TYPE_MAP
    _DOC_TYPE_CN_MAP = DOC_TYPE_MAP


    def check(self, rule: Dict[str, Any], medical_record: Dict[str, Any]) -> ApplicabilityResult:
        rule_id = (rule.get("rule_id") or "").upper()
        text = medical_record.get("content") or ""
        document_type = medical_record.get("document_type") or ""

        # ---- 1. 文书类型匹配 ----
        applicable_docs = rule.get("applicable_documents") or []
        if applicable_docs and document_type:
            matched = self._match_document_type(document_type, applicable_docs)
            if not matched:
                return ApplicabilityResult(
                    is_applicable=False,
                    reason=f"规则适用文书类型 {applicable_docs}，当前文书为 '{document_type}'",
                    method="document_type_guard",
                )

        # ---- 2. 手术标志检测 ----
        if rule_id in self.SURGERY_ONLY_RULES:
            has_surgery = any(hint in text for hint in self.SURGERY_HINTS)
            if not has_surgery:
                return ApplicabilityResult(
                    is_applicable=False,
                    reason=f"规则 {rule_id} 仅适用于手术患者，病历中未检测到手术特征",
                    method="surgery_guard",
                )

        # ---- 3. 年龄 / 规则特定逻辑 ----
        if rule_id == "LX-003":
            return ApplicabilityResult(
                is_applicable=True, reason="", method="lx003_via_llm",
            )
        elif rule_id == "LX-005":
            return ApplicabilityResult(
                is_applicable=True, reason="", method="lx005_via_llm",
            )
        elif rule_id == "LX-006":
            age_years = self._extract_age(text)
            pediatric_hints = any(hint in text for hint in self.PEDIATRIC_HINTS)

            if age_years is not None:
                if age_years < 7:
                    return ApplicabilityResult(
                        is_applicable=False,
                        reason=f"患者年龄 {age_years} 岁 < 7 岁，不在规则覆盖范围",
                        method="lx006_age_guard",
                    )
                if age_years >= 18:
                    return ApplicabilityResult(
                        is_applicable=False,
                        reason=f"患者年龄 {age_years} 岁，为成人患者，本规则仅适用于儿科≥7岁人群。",
                        method="lx006_age_guard",
                    )

            if (age_years is None or age_years >= 18) and not pediatric_hints:
                return ApplicabilityResult(
                    is_applicable=False,
                    reason="病历无儿科特征（未发现'患儿'/'儿科'等标记，且无法解析到≤17岁的年龄）",
                    method="lx006_age_guard",
                )

        return ApplicabilityResult(is_applicable=True, reason="", method="default")

    def _match_document_type(self, current_type: str, applicable_docs: list) -> bool:
        """检查当前文书类型是否匹配规则的适用文书列表（兼容中英文）"""
        # 直接匹配
        if current_type in applicable_docs:
            return True
        # 英文→中文转换后匹配
        for doc in applicable_docs:
            cn_name = self._DOC_TYPE_CN_MAP.get(doc)
            if cn_name and cn_name == current_type:
                return True
        # 中文→英文反向匹配
        cn_to_en = {v: k for k, v in self._DOC_TYPE_CN_MAP.items()}
        current_en = cn_to_en.get(current_type)
        if current_en and current_en in applicable_docs:
            return True
        return False

    @staticmethod
    def _extract_age(text: str) -> Optional[int]:
        if not text:
            return None

        patterns = [
            r"年龄[:：]?\s*(\d+)\s*岁",
            r"(\d+)\s*岁"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    continue
        return None



class EvidenceVerifier:
    """
    简单的证据校验器：检查 evidence 文本是否来自病历原文。
    """

    def verify(self, evidence_text: str, medical_content: str) -> Dict[str, Any]:
        if not evidence_text:
            return {
                "text": "",
                "verified": True,
                "span": None
            }

        normalized_evidence = self._normalize(evidence_text)
        normalized_content = self._normalize(medical_content)

        verified = bool(normalized_evidence and normalized_evidence in normalized_content)

        # 计算一个大致的字符范围，用于前端高亮
        span = None
        if verified:
            # 尝试在原文中找到首次出现的位置
            stripped = evidence_text.strip()
            idx = medical_content.find(stripped)
            if idx != -1:
                span = (idx, idx + len(stripped))

        return {
            "text": evidence_text,
            "verified": verified,
            "span": span
        }

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.split()) if value else ""


class UnifiedRuleEngine:
    """
    统一规则执行引擎。
    目前用于单条规则测试，后续可以在批量接口中复用。
    """

    def __init__(self, llm_generate: LLMGenerateFn) -> None:
        self._llm_generate = llm_generate
        self._app_checker = ApplicabilityChecker()
        self._evidence_verifier = EvidenceVerifier()

    async def evaluate(self, rule: Dict[str, Any], medical_record: Dict[str, Any]) -> Dict[str, Any]:
        applicability = self._app_checker.check(rule, medical_record)
        rule_id = rule.get("rule_id")
        rule_name = rule.get("name")

        if not applicability.is_applicable:
            return {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "status": "not_applicable",
                "is_compliant": True,
                "issues": [],
                "findings": applicability.reason or "本规则不适用，判定为合规。",
                "evidence": "",
                "suggestion": "",
                "confidence": 0.9,
                "llm_raw_output": None,
                "applicability": {
                    "is_applicable": False,
                    "reason": applicability.reason,
                    "method": applicability.method
                },
                "evidence_verified": True,
                "metadata": {
                    "tokens_used": 0,
                    "api_time": 0.0
                }
            }

        # 对部分规则使用内置逻辑，避免过度依赖 LLM
        # NOTE: 应用户需求，LX-003 也统一走大模型提示词逻辑
        # if (rule_id or "").upper() == "LX-003":
        #     return self._evaluate_lx003(rule, medical_record, applicability)

        prompt = self._build_prompt(
            rule,
            medical_record["content"],
            evidence_payload=medical_record.get("evidence_payload"),
        )
        llm_result = await self._llm_generate(prompt)
        raw_output = (
            llm_result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        usage = llm_result.get("usage", {})
        api_time = llm_result.get("_api_time", 0.0)

        parsed = self._parse_llm_response(raw_output)

        evidence_info = self._evidence_verifier.verify(
            parsed.get("evidence", ""),
            medical_record["content"]
        )
        if not evidence_info["verified"]:
            parsed["confidence"] = min(parsed.get("confidence") or 0.6, 0.5)

        status = "non_compliant"
        is_compliant = parsed["is_compliant"]
        if is_compliant:
            status = "compliant"
        if parsed.get("uncertain"):
            status = "uncertain"

        # 默认适用性（可被特定规则覆盖）
        applicability_data = {
            "is_applicable": True,
            "reason": applicability.reason,
            "method": applicability.method,
        }

        # 对 LX-003 / LX-005 允许由大模型在 findings 中声明“不适用”
        if (rule_id or "").upper() in ("LX-003", "LX-005"):
            findings_text = parsed.get("findings") or ""
            if "不适用" in findings_text or "不符合适用范围" in findings_text:
                status = "not_applicable"
                is_compliant = True
                applicability_data = {
                    "is_applicable": False,
                    "reason": findings_text,
                    "method": f"{(rule_id or '').lower()}_via_llm",
                }

        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "status": status,
            "is_compliant": is_compliant,
            "issues": parsed["issues"],
            "findings": parsed["findings"],
            "evidence": parsed["evidence"],
            "suggestion": parsed["suggestion"],
            "confidence": parsed["confidence"],
            "llm_raw_output": raw_output,
            "applicability": applicability_data,
            "evidence_verified": evidence_info["verified"],
            "evidence_span": evidence_info["span"],
            "metadata": {
                "tokens_used": usage.get("total_tokens", 0),
                "api_time": api_time,
            }
        }

    async def evaluate_batch_compact(
        self,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        *,
        pack_id: str = "",
        pack_size: int = 0,
        low_confidence_threshold: float = 0.45,
        context_token_budget: int = 7000,
    ) -> Dict[str, Any]:
        effective_rules = list(rules or [])
        if not effective_rules:
            return {
                "results": [],
                "tokens_used": 0,
                "api_time": 0.0,
                "raw_output": "",
                "parse_error": False,
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "context_tokens_estimate": 0,
            }

        not_applicable_results: List[Dict[str, Any]] = []
        applicable_rules: List[Dict[str, Any]] = []
        for rule in effective_rules:
            applicability = self._app_checker.check(rule, medical_record)
            if applicability.is_applicable:
                applicable_rules.append(rule)
                continue
            not_applicable_results.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "rule_name": rule.get("name"),
                    "status": "not_applicable",
                    "is_compliant": True,
                    "issues": [],
                    "findings": applicability.reason or "本规则不适用，判定为合规。",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "llm_raw_output": None,
                    "applicability": {
                        "is_applicable": False,
                        "reason": applicability.reason,
                        "method": applicability.method,
                    },
                    "evidence_verified": True,
                    "metadata": {
                        "tokens_used": 0,
                        "api_time": 0.0,
                        "prompt_strategy": "batch_compact_v1",
                        "pack_id": pack_id,
                        "pack_size": int(pack_size or len(effective_rules)),
                        "pack_fallback": False,
                        "context_tokens_estimate": 0,
                    },
                }
            )

        if not applicable_rules:
            return {
                "results": not_applicable_results,
                "tokens_used": 0,
                "api_time": 0.0,
                "raw_output": "",
                "parse_error": False,
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "context_tokens_estimate": 0,
            }

        prompt, context_tokens_estimate = self._build_batch_prompt_compact(
            applicable_rules,
            medical_record,
            context_token_budget=context_token_budget,
        )
        llm_result = await self._llm_generate(prompt)
        raw_output = (
            llm_result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        usage = llm_result.get("usage", {})
        tokens_used = int(usage.get("total_tokens", 0) or 0)
        api_time = float(llm_result.get("_api_time", 0.0) or 0.0)

        parsed = self._parse_batch_llm_response(raw_output)
        parsed_items = parsed.get("items") or []
        parsed_map: Dict[str, Dict[str, Any]] = {}
        for item in parsed_items:
            rid = str(item.get("rule_id") or "").strip().upper()
            if rid and rid not in parsed_map:
                parsed_map[rid] = item

        expected_ids = {str(rule.get("rule_id") or "").strip().upper() for rule in applicable_rules if str(rule.get("rule_id") or "").strip()}
        missing_ids = sorted(expected_ids - set(parsed_map.keys()))
        low_confidence_ids: List[str] = []
        distributed_tokens = int(tokens_used / max(1, len(applicable_rules)))
        distributed_api_time = float(api_time / max(1, len(applicable_rules)))

        llm_results: List[Dict[str, Any]] = []
        for rule in applicable_rules:
            rule_id = str(rule.get("rule_id") or "").strip().upper()
            rule_name = str(rule.get("name") or "")
            parsed_item = dict(parsed_map.get(rule_id) or {})

            if not parsed_item:
                llm_results.append(
                    {
                        "rule_id": rule.get("rule_id"),
                        "rule_name": rule_name,
                        "status": "uncertain",
                        "is_compliant": False,
                        "issues": [],
                        "findings": "批量响应缺少该规则结果，待回退重试。",
                        "evidence": "",
                        "suggestion": "",
                        "confidence": 0.0,
                        "llm_raw_output": raw_output,
                        "applicability": {
                            "is_applicable": True,
                            "reason": "",
                            "method": "default",
                        },
                        "evidence_verified": False,
                        "metadata": {
                            "tokens_used": distributed_tokens,
                            "api_time": distributed_api_time,
                            "prompt_strategy": "batch_compact_v1",
                            "pack_id": pack_id,
                            "pack_size": int(pack_size or len(effective_rules)),
                            "pack_fallback": False,
                            "context_tokens_estimate": context_tokens_estimate,
                        },
                    }
                )
                continue

            confidence = float(parsed_item.get("confidence") or 0.7)
            evidence_text = str(parsed_item.get("evidence") or "")
            evidence_info = self._evidence_verifier.verify(
                evidence_text,
                str(medical_record.get("content") or ""),
            )
            if not evidence_info.get("verified"):
                confidence = min(confidence, 0.5)
            if confidence < low_confidence_threshold:
                low_confidence_ids.append(rule_id)

            status = str(parsed_item.get("status") or "").strip().lower()
            is_compliant = bool(parsed_item.get("is_compliant") is True)
            if status not in {"compliant", "non_compliant", "not_applicable", "uncertain"}:
                status = "compliant" if is_compliant else "non_compliant"
            if status == "not_applicable":
                is_compliant = True

            llm_results.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "rule_name": rule_name,
                    "status": status,
                    "is_compliant": is_compliant,
                    "issues": parsed_item.get("issues") or [],
                    "findings": parsed_item.get("findings") or "",
                    "evidence": evidence_text,
                    "suggestion": parsed_item.get("suggestion") or "",
                    "confidence": confidence,
                    "llm_raw_output": raw_output,
                    "applicability": {
                        "is_applicable": True,
                        "reason": "",
                        "method": "default",
                    },
                    "evidence_verified": bool(evidence_info.get("verified") is True),
                    "evidence_span": evidence_info.get("span"),
                    "metadata": {
                        "tokens_used": distributed_tokens,
                        "api_time": distributed_api_time,
                        "prompt_strategy": "batch_compact_v1",
                        "pack_id": pack_id,
                        "pack_size": int(pack_size or len(effective_rules)),
                        "pack_fallback": False,
                        "context_tokens_estimate": context_tokens_estimate,
                    },
                }
            )

        return {
            "results": [*not_applicable_results, *llm_results],
            "tokens_used": tokens_used,
            "api_time": api_time,
            "raw_output": raw_output,
            "parse_error": bool(parsed.get("parse_error") is True),
            "missing_rule_ids": missing_ids,
            "low_confidence_rule_ids": sorted(set(low_confidence_ids)),
            "context_tokens_estimate": context_tokens_estimate,
        }

    def _build_batch_prompt_compact(
        self,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        *,
        context_token_budget: int = 7000,
    ) -> Tuple[str, int]:
        content = str(medical_record.get("content") or "")
        evidence_payload = medical_record.get("evidence_payload")
        context_text, context_tokens = self._build_compact_context(
            content=content,
            evidence_payload=evidence_payload if isinstance(evidence_payload, dict) else {},
            context_token_budget=context_token_budget,
        )

        card_lines: List[str] = []
        for idx, rule in enumerate(rules, start=1):
            rule_id = str(rule.get("rule_id") or rule.get("rule_code") or f"RULE-{idx}")
            rule_name = str(rule.get("name") or "")
            defect_level = str(rule.get("defect_level") or "")
            checks = self._extract_compact_checks(
                str(rule.get("custom_prompt") or rule.get("prompt_template") or ""),
                rule=rule,
            )
            checks = re.sub(r"\s+", " ", checks).strip()
            if len(checks) > 200:
                checks = checks[:200] + "..."
            card_lines.append(
                f"- rule_id: {rule_id}\n"
                f"  rule_name: {rule_name}\n"
                f"  defect_level: {defect_level}\n"
                f"  checks: {checks}"
            )

        prompt = (
            "你是资深病历质控专家。请基于下方病历证据，对规则列表逐条判定。\n"
            "要求：\n"
            "1. 只输出 JSON，不要解释。\n"
            "2. 必须覆盖全部 rule_id，每条只输出一次。\n"
            "3. 若证据不足，status=uncertain，is_compliant=false，并说明缺失证据。\n"
            "4. evidence 尽量引用原文短句。\n\n"
            f"适用规则数 {len(rules)}\n"
            "规则卡片：\n"
            f"{chr(10).join(card_lines)}\n\n"
            "病历证据上下文：\n"
            f"{context_text}\n\n"
            "输出格式：\n"
            "{\n"
            "  \"results\": [\n"
            "    {\n"
            "      \"rule_id\": \"SC-001\",\n"
            "      \"is_compliant\": true,\n"
            "      \"status\": \"compliant|non_compliant|uncertain|not_applicable\",\n"
            "      \"findings\": \"结论\",\n"
            "      \"evidence\": \"证据\",\n"
            "      \"suggestion\": \"建议\",\n"
            "      \"confidence\": 0.0,\n"
            "      \"issues\": []\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        return prompt, context_tokens

    def _build_compact_context(
        self,
        *,
        content: str,
        evidence_payload: Dict[str, Any],
        context_token_budget: int,
    ) -> Tuple[str, int]:
        budget = max(1200, int(context_token_budget or 7000))
        primary = str(content or "").strip()
        primary_limit = min(len(primary), 12000)
        primary_text = primary[:primary_limit]

        supporting = list(evidence_payload.get("supporting_documents") or [])
        timeline = list(evidence_payload.get("timeline_facts") or [])
        document_hits = evidence_payload.get("document_hits") or {}
        quality_flags = list(evidence_payload.get("data_quality_flags") or [])

        support_limit = min(len(supporting), 6)
        timeline_limit = min(len(timeline), 12)

        def _render_ctx() -> str:
            lines: List[str] = []
            lines.append("【主文书】")
            lines.append(primary_text)
            if document_hits:
                hit_parts = [f"{k}:{'Y' if bool(v) else 'N'}" for k, v in document_hits.items()]
                lines.append("【文书命中】" + "；".join(hit_parts))
            if quality_flags:
                lines.append("【数据质量】" + "；".join([str(x) for x in quality_flags if str(x).strip()]))
            if support_limit > 0:
                lines.append("【辅助证据】")
                for item in supporting[:support_limit]:
                    if not isinstance(item, dict):
                        continue
                    doc_type = str(item.get("document_type") or item.get("source_table") or "辅助文书")
                    snippet = str(item.get("evidence_text") or item.get("content") or item.get("text_preview") or "").strip()
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "..."
                    if snippet:
                        lines.append(f"- [{doc_type}] {snippet}")
            if timeline_limit > 0:
                lines.append("【时间线事实】")
                for fact in timeline[:timeline_limit]:
                    text = str(fact).strip()
                    if not text:
                        continue
                    if len(text) > 220:
                        text = text[:220] + "..."
                    lines.append(f"- {text}")
            return "\n".join(lines)

        context_text = _render_ctx()
        estimated_tokens = self._estimate_tokens(context_text)
        # 预算降级顺序：先减辅助证据，再减时间线，再缩主文书
        while estimated_tokens > budget and support_limit > 0:
            support_limit -= 1
            context_text = _render_ctx()
            estimated_tokens = self._estimate_tokens(context_text)
        while estimated_tokens > budget and timeline_limit > 0:
            timeline_limit -= 1
            context_text = _render_ctx()
            estimated_tokens = self._estimate_tokens(context_text)
        while estimated_tokens > budget and len(primary_text) > 1500:
            primary_text = primary_text[: max(1500, int(len(primary_text) * 0.8))]
            context_text = _render_ctx()
            estimated_tokens = self._estimate_tokens(context_text)

        return context_text, estimated_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return int(max(1, len(text or "")) / 4)

    @staticmethod
    def _extract_compact_checks(custom_prompt: str, *, rule: Dict[str, Any]) -> str:
        source = str(custom_prompt or "").strip()
        if not source:
            return str(rule.get("description") or "")
        source = source.replace("{medical_text}", "")
        source = source.replace("{rule_id}", str(rule.get("rule_id") or ""))
        source = source.replace("{name}", str(rule.get("name") or ""))
        source = re.sub(r"\s+", " ", source).strip()
        if not source:
            return str(rule.get("description") or "")
        pattern = re.compile(r"(检查|判定|不合规|需满足|必须|缺失|禁止)")
        snippets: List[str] = []
        for part in re.split(r"[。；;]\s*", source):
            cleaned = part.strip()
            if not cleaned:
                continue
            if pattern.search(cleaned):
                snippets.append(cleaned)
            if len(snippets) >= 3:
                break
        if snippets:
            return "；".join(snippets)
        return source[:260]

    def _parse_batch_llm_response(self, raw_output: str) -> Dict[str, Any]:
        if not raw_output:
            return {"items": [], "parse_error": True}

        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_output or "", flags=re.IGNORECASE).strip()
        payload: Any = None

        object_match = re.search(r"\{[\s\S]*\}", cleaned)
        array_match = re.search(r"\[[\s\S]*\]", cleaned)
        candidates: List[str] = []
        if object_match:
            candidates.append(object_match.group(0))
        if array_match:
            candidates.append(array_match.group(0))

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
                break
            except Exception:
                continue

        if payload is None:
            return {"items": [], "parse_error": True}

        items_raw: List[Any]
        if isinstance(payload, dict):
            maybe_items = payload.get("results")
            items_raw = maybe_items if isinstance(maybe_items, list) else []
        elif isinstance(payload, list):
            items_raw = payload
        else:
            items_raw = []

        items: List[Dict[str, Any]] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "rule_id": str(item.get("rule_id") or item.get("rule_code") or "").strip(),
                    "is_compliant": bool(item.get("is_compliant") is True),
                    "status": str(item.get("status") or "").strip().lower(),
                    "findings": str(item.get("findings") or ""),
                    "evidence": str(item.get("evidence") or ""),
                    "suggestion": str(item.get("suggestion") or ""),
                    "confidence": float(item.get("confidence") or 0.7),
                    "issues": item.get("issues") or [],
                }
            )

        return {"items": items, "parse_error": False}

    @staticmethod
    def _format_evidence_payload(evidence_payload: Dict[str, Any]) -> str:
        supporting_documents = evidence_payload.get("supporting_documents") or []
        timeline_facts = evidence_payload.get("timeline_facts") or []
        document_hits = evidence_payload.get("document_hits") or {}
        data_quality_flags = evidence_payload.get("data_quality_flags") or []

        lines: List[str] = []
        if isinstance(document_hits, dict) and document_hits:
            hit_parts = [f"{k}={'Y' if bool(v) else 'N'}" for k, v in document_hits.items()]
            lines.append("命中文书：" + "，".join(hit_parts))

        if isinstance(data_quality_flags, list) and data_quality_flags:
            lines.append("数据质量标记：" + "，".join([str(item) for item in data_quality_flags if str(item).strip()]))

        if isinstance(supporting_documents, list) and supporting_documents:
            lines.append("辅助证据：")
            for idx, item in enumerate(supporting_documents[:5], start=1):
                if not isinstance(item, dict):
                    continue
                doc_type = str(item.get("document_type") or item.get("source_table") or f"doc_{idx}")
                evidence_text = str(
                    item.get("evidence_text")
                    or item.get("content")
                    or item.get("text_preview")
                    or ""
                ).strip()
                if evidence_text:
                    lines.append(f"{idx}. [{doc_type}] {evidence_text}")

        if isinstance(timeline_facts, list) and timeline_facts:
            lines.append("时间线事实：")
            for idx, item in enumerate(timeline_facts[:10], start=1):
                lines.append(f"{idx}. {str(item)}")

        if not lines:
            return ""
        return (
            "\n\n==================== 结构化证据上下文（Bundle）====================\n"
            + "\n".join(lines)
            + "\n==================== 证据上下文结束 ====================\n"
        )

    def _build_prompt(
        self,
        rule: Dict[str, Any],
        medical_text: str,
        *,
        evidence_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        template = rule.get("custom_prompt")
        evidence_context = ""
        if isinstance(evidence_payload, dict) and evidence_payload:
            evidence_context = self._format_evidence_payload(evidence_payload)
        marked_medical_text = (
            "\n\n==================== 以下是待评估的实际病历文本 ====================\n"
            f"{medical_text}\n"
            "==================== 病历文本结束 ====================\n"
        )
        prompt_input_text = f"{marked_medical_text}{evidence_context}"

        if template:
            applicable_docs = rule.get("applicable_documents")
            if isinstance(applicable_docs, list):
                applicable_docs = ", ".join(applicable_docs)
            prompt = template.format(
                rule_id=rule.get("rule_id", ""),
                name=rule.get("name", ""),
                description=rule.get("description", ""),
                applicable_documents=applicable_docs or "",
                defect_level=rule.get("defect_level", ""),
                complexity=rule.get("complexity", ""),
                medical_text=prompt_input_text
            )
            # 兜底：如果模板中没有 {medical_text} 占位符，强制追加病历文本
            if "{medical_text}" not in template:
                logging.getLogger(__name__).warning(
                    "custom_prompt for rule %s is missing {medical_text} placeholder; appending medical text block.",
                    rule.get("rule_id")
                )
                prompt += f"\n\n【病历文本】\n{prompt_input_text}\n\n请根据上述病历文本进行质控评估，严格按照JSON格式输出结果。"
            return prompt

        # 默认提示词（与历史逻辑保持一致）
        return f"""
你是一名病历质控专家。请根据以下规则评估病历文本是否合规，只输出 JSON。

规则名称：{rule.get("name", "")}
规则描述：{rule.get("description", "")}
缺陷等级：{rule.get("defect_level", "")}

{prompt_input_text}
"""

    @staticmethod
    def _parse_llm_response(raw_output: str) -> Dict[str, Any]:
        default_result = {
            "is_compliant": True,
            "issues": [],
            "findings": "",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.7,
            "uncertain": False
        }

        if not raw_output:
            default_result["uncertain"] = True
            default_result["findings"] = "LLM 未返回任何内容。"
            return default_result

        match = re.search(r"\{[\s\S]*\}", raw_output)
        parsed_json: Dict[str, Any] = {}
        if match:
            try:
                parsed_json = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed_json = {}

        if not parsed_json:
            default_result["uncertain"] = True
            default_result["findings"] = "LLM 返回了非结构化结果，请查看原始输出。"
            default_result["evidence"] = raw_output[:200]
            return default_result

        default_result["is_compliant"] = bool(parsed_json.get("is_compliant", True))
        default_result["issues"] = parsed_json.get("issues", [])
        default_result["findings"] = parsed_json.get("findings", "")
        default_result["evidence"] = parsed_json.get("evidence", "")
        default_result["suggestion"] = parsed_json.get("suggestion", "")
        try:
            default_result["confidence"] = float(parsed_json.get("confidence", 0.7))
        except Exception:
            default_result["confidence"] = 0.7

        return default_result

    def _evaluate_lx003(
        self,
        rule: Dict[str, Any],
        medical_record: Dict[str, Any],
        applicability: ApplicabilityResult
    ) -> Dict[str, Any]:
        """
        LX-003 专用规则：儿童患者无婴幼儿喂养史和生长发育史。

        逻辑：
        - 适用对象：儿科/婴幼儿，年龄 ≤14 岁（由 ApplicabilityChecker 保证）。
        - 喂养史：需包含喂养方式/状况等具体描述（母乳/配方/混合喂养/辅食等），仅出现“喂养史”字样不视为已记录。
        - 生长发育史：需有身高/体重等客观指标，或发育里程碑（抬头/翻身/坐/爬/行走/语言等）；仅“发育正常”视为缺失。
        """
        text = medical_record.get("content") or ""
        rule_id = rule.get("rule_id")
        rule_name = rule.get("name")

        lowered = text.lower()

        # 喂养相关关键词（排除仅提到“喂养史”但无具体描述的情况）
        feeding_positive_keywords = [
            "母乳喂养", "纯母乳", "配方奶", "配方喂养", "奶粉喂养",
            "混合喂养", "人工喂养", "辅食", "添加辅食", "加用辅食",
            "喂奶", "喂水", "喂养良好", "喂养情况良好"
        ]

        def has_feeding_info(t: str) -> bool:
            if "喂养史" in t and not any(k in t for k in feeding_positive_keywords):
                # 仅有“喂养史”字样（例如“未见喂养史记录”）不算记录完整
                return False
            return any(k in t for k in feeding_positive_keywords)

        # 生长发育相关关键词（不把“发育正常”视为充分记录）
        dev_positive_keywords = [
            "身高", "身長", "身长", "体重", "体质量",
            "抬头", "翻身", "会坐", "独坐", "会爬", "会走", "行走", "会跑",
            "会喊", "会叫", "会说", "会讲话", "语言发育",
            "大运动", "精细动作", "生长发育良好", "生长发育迟缓", "发育落后"
        ]

        def has_dev_info(t: str) -> bool:
            if "发育正常" in t and not any(k in t for k in dev_positive_keywords):
                return False
            # 简单数值模式：体重/身高后面带单位
            import re
            if re.search(r"(身高|身长|体重).{0,12}(cm|厘米|kg|公斤|千克|g|克|斤)", t):
                return True
            return any(k in t for k in dev_positive_keywords)

        feeding_present = has_feeding_info(text)
        dev_present = has_dev_info(text)

        is_compliant = feeding_present and dev_present
        status = "compliant" if is_compliant else "non_compliant"

        issues: List[Dict[str, Any]] = []
        if not feeding_present:
            issues.append({
                "description": "缺喂养史",
                "evidence": "入院记录/个人史中未见婴幼儿喂养方式或喂养状况的具体描述。"
            })
        if not dev_present:
            issues.append({
                "description": "缺生长发育史",
                "evidence": "入院记录中未见身高体重等客观指标或发育里程碑的具体描述，仅有笼统表述。"
            })

        if is_compliant:
            findings = "入院记录中对婴幼儿喂养史和生长发育史均有较为完整的记录，符合质控要求。"
        else:
            missing_parts = []
            if not feeding_present:
                missing_parts.append("喂养史")
            if not dev_present:
                missing_parts.append("生长发育史")
            findings = f"入院记录中缺少{'、'.join(missing_parts)}的具体记录，不符合质控要求。"

        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "status": status,
            "is_compliant": is_compliant,
            "issues": issues,
            "findings": findings,
            "evidence": "",
            "suggestion": "",
            "confidence": 0.8,
            "llm_raw_output": None,
            "applicability": {
                "is_applicable": True,
                "reason": applicability.reason,
                "method": applicability.method,
            },
            "evidence_verified": True,
            "evidence_span": None,
            "metadata": {
                "tokens_used": 0,
                "api_time": 0.0,
            },
        }
