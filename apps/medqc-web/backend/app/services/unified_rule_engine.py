from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .effect_priority_qc import (
    BATCH_OUTPUT_MODE_MINIMAL,
    evidence_limits_for_family,
    family_check_limit,
    family_keywords,
    is_effect_priority_profile,
    normalize_batch_output_mode,
    normalize_rule_family,
    normalize_quality_profile,
    select_family_snippet,
)


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
    DEATH_ONLY_RULES = {"SC-119", "SC-120", "SC-127"}
    DEATH_HINTS = ["患者死亡", "死亡时间", "死亡记录", "死亡证明", "抢救无效死亡", "宣布死亡", "临床死亡"]

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

        if rule_id in self.DEATH_ONLY_RULES and not self._has_death_context(medical_record):
            return ApplicabilityResult(
                is_applicable=False,
                reason=f"规则 {rule_id} 仅适用于死亡病例，当前病历未检测到死亡记录或死亡事件",
                method="death_case_guard",
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

    def _has_death_context(self, medical_record: Dict[str, Any]) -> bool:
        evidence_payload = medical_record.get("evidence_payload")
        if isinstance(evidence_payload, dict):
            document_hits = evidence_payload.get("document_hits") or {}
            if isinstance(document_hits, dict) and bool(document_hits.get("death_record")):
                return True
            for item in list(evidence_payload.get("supporting_documents") or []):
                if not isinstance(item, dict):
                    continue
                doc_type = str(item.get("document_type") or item.get("source_table") or "").lower()
                if "death" in doc_type or "死亡" in doc_type:
                    return True

        text = str(medical_record.get("content") or "")
        return any(hint in text for hint in self.DEATH_HINTS)

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

    @staticmethod
    def _collect_evidence_sources(medical_record: Dict[str, Any]) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        primary_content = str(medical_record.get("content") or "").strip()
        primary_document_type = str(medical_record.get("document_type") or "").strip()
        if primary_content:
            sources.append(
                {
                    "document_type": primary_document_type or "当前文书",
                    "content": primary_content,
                    "is_primary": True,
                }
            )

        evidence_payload = medical_record.get("evidence_payload")
        if isinstance(evidence_payload, dict):
            for item in list(evidence_payload.get("supporting_documents") or []):
                if not isinstance(item, dict):
                    continue
                evidence_text = str(
                    item.get("evidence_text") or item.get("content") or item.get("text_preview") or ""
                ).strip()
                if not evidence_text:
                    continue
                sources.append(
                    {
                        "document_type": str(item.get("document_type") or item.get("source_table") or "辅助文书").strip(),
                        "content": evidence_text,
                        "is_primary": False,
                    }
                )
        return sources

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return re.sub(r"\s+", "", str(text or ""))

    @classmethod
    def _extract_match_keywords(cls, *texts: str) -> List[str]:
        stop_words = {
            "患者", "病历", "记录", "提示", "建议", "情况", "当前", "相关", "内容", "符合", "要求", "进行",
            "存在", "需要", "以及", "其中", "已经", "未见", "缺少", "补充", "完善", "进一步", "检查",
            "治疗", "病程", "首次", "入院", "会诊", "意见", "执行", "病例特点", "诊断依据", "鉴别诊断",
        }
        ordered: List[str] = []
        seen: set[str] = set()
        for text in texts:
            candidate_text = str(text or "")
            for token in re.split(r"[，。；：、,.;:\s（）()【】\[\]\-]+", candidate_text):
                normalized = token.strip("“”\"'：:，,。；;（）()")
                if len(normalized) < 2 or len(normalized) > 16:
                    continue
                if normalized.isdigit() or normalized in stop_words:
                    continue
                if normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
        return ordered[:8]

    @classmethod
    def _extract_quote_from_content(cls, content: str, keywords: List[str]) -> str:
        raw = str(content or "").strip()
        if not raw:
            return ""
        fragments = [
            fragment.strip()
            for fragment in re.split(r"(?<=[。！？；])|\n+", raw)
            if fragment and fragment.strip()
        ]
        if not fragments:
            fragments = [raw]

        best_fragment = ""
        best_score = -1
        normalized_raw = cls._normalize_for_match(raw)
        for fragment in fragments:
            normalized_fragment = cls._normalize_for_match(fragment)
            score = 0
            for keyword in keywords:
                if cls._normalize_for_match(keyword) and cls._normalize_for_match(keyword) in normalized_fragment:
                    score += 2
            if best_score < score:
                best_fragment = fragment
                best_score = score
            if score >= max(2, min(4, len(keywords) * 2)):
                break

        if best_fragment:
            return best_fragment[:120].rstrip("，,。；; ") + ("..." if len(best_fragment) > 120 else "")

        # 兜底：直接返回前 80 字，避免 evidence 变成抽象标签。
        fallback = raw[:80].rstrip("，,。；; ")
        return fallback + ("..." if len(raw) > 80 else "")

    @classmethod
    def _refine_evidence_text(
        cls,
        *,
        evidence_text: str,
        findings_text: str,
        medical_record: Dict[str, Any],
    ) -> Tuple[str, bool, Any]:
        original = str(evidence_text or "").strip()
        sources = cls._collect_evidence_sources(medical_record)
        primary_content = str(medical_record.get("content") or "")
        verifier = EvidenceVerifier()
        original_info = verifier.verify(original, primary_content)
        if original and original_info.get("verified"):
            return original, True, original_info.get("span")

        keywords = cls._extract_match_keywords(original, findings_text)
        for source in sources:
            content = str(source.get("content") or "")
            if not content:
                continue
            snippet = cls._extract_quote_from_content(content, keywords)
            if not snippet:
                continue
            document_type = str(source.get("document_type") or "").strip()
            refined = f"【{document_type}】{snippet}" if document_type else snippet
            if source.get("is_primary"):
                info = verifier.verify(snippet, primary_content)
                return refined, bool(info.get("verified")), info.get("span")
            return refined, True, None

        return original, bool(original_info.get("verified")), original_info.get("span")

    @staticmethod
    def _build_rewrite_example(
        *,
        rule_id: str,
        status: str,
        medical_record: Dict[str, Any],
    ) -> str:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"non_compliant", "uncertain"}:
            return ""

        document_type = str(medical_record.get("document_type") or "").strip()
        template_map = {
            "SC-024": "病例特点：反复上腹痛2月，进食后加重；胃镜示胃窦溃疡；上腹轻压痛，无反跳痛，考虑胃溃疡可能。",
            "SC-026": "诊断依据：反复上腹痛2月，胃镜示胃窦溃疡。鉴别诊断：胃癌，结合胃镜及病理结果暂不支持。",
            "SC-027": "诊疗计划：继续抑酸护胃，完善幽门螺杆菌检测，根据结果调整治疗并复查胃镜。",
            "SC-070": "今日记录会诊意见：继续抑酸治疗，完善幽门螺杆菌检测，已开立相关医嘱并向患者交代。",
            "SC-032": "今日病程：患者体温升高至38.6℃，考虑感染活动，已复查血常规并调整抗感染方案。",
            "SC-033": "今日病程：复查胃镜提示胃窦溃疡，结合腹痛持续，继续抑酸治疗并密切观察疗效。",
            "SC-036": "今日病程：腹痛较前加重，结合检查结果考虑病情进展，已请上级医师评估并调整处理计划。",
        }
        if rule_id in template_map:
            return template_map[rule_id]

        if document_type == "首次病程记录":
            return "建议补写：概括主要症状演变、关键阳性/阴性体征、检查结果及诊断导向性判断。"
        if document_type == "日常病程记录":
            return "建议补写：记录病情变化、相关检查结果、已采取处理及下一步诊疗计划。"
        if document_type == "入院记录":
            return "建议补写：补充与本次诊疗直接相关的病史要点、查体结果及入院诊断依据。"
        return "建议补写：围绕关键异常、证据依据和处理动作，形成一段可直接入病历的完整记录。"

    _DOMAIN_CONTEXT_BUDGET_DELTA: Dict[str, int] = {
        "admission": 200,
        "course": 300,
        "surgery": 900,
        "consult_discussion": 500,
        "terminal": 0,
        "index_coding_settlement": -700,
        "generic": 0,
    }

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
        usage_breakdown = dict(llm_result.get("_usage_breakdown") or {})
        api_time = llm_result.get("_api_time", 0.0)
        first_result_latency = float(llm_result.get("_first_result_latency", 0.0) or 0.0)
        cot_observation = dict(llm_result.get("_cot_observation") or {})

        parsed = self._parse_llm_response(raw_output)

        parsed["findings"] = self._stringify_llm_text(parsed.get("findings", ""))
        parsed["evidence"] = self._stringify_llm_text(parsed.get("evidence", ""))
        parsed["suggestion"] = self._stringify_llm_text(parsed.get("suggestion", ""))

        refined_evidence, evidence_verified, evidence_span = self._refine_evidence_text(
            evidence_text=parsed["evidence"],
            findings_text=parsed["findings"],
            medical_record=medical_record,
        )
        parsed["evidence"] = refined_evidence
        if not evidence_verified:
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

        result = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "status": status,
            "is_compliant": is_compliant,
            "issues": parsed["issues"],
            "findings": parsed["findings"],
            "evidence": parsed["evidence"],
            "suggestion": self._normalize_suggestion_by_status(
                status=status,
                suggestion=parsed["suggestion"],
                rule_name=str(rule_name or ""),
            ),
            "rewrite_example": self._build_rewrite_example(
                rule_id=str(rule_id or "").strip().upper(),
                status=status,
                medical_record=medical_record,
            ),
            "confidence": parsed["confidence"],
            "llm_raw_output": raw_output,
            "applicability": applicability_data,
            "evidence_verified": evidence_verified,
            "evidence_span": evidence_span,
            "metadata": {
                "tokens_used": usage.get("total_tokens", 0),
                "prompt_tokens": int(usage_breakdown.get("prompt_tokens") or 0),
                "completion_tokens": int(usage_breakdown.get("completion_tokens") or 0),
                "input_tokens": int(usage_breakdown.get("input_tokens") or 0),
                "output_tokens": int(usage_breakdown.get("output_tokens") or 0),
                "api_time": api_time,
                "first_result_latency": first_result_latency,
                "cot_mode": str(cot_observation.get("cot_mode") or "disabled"),
                "requested_enable_thinking": bool(cot_observation.get("requested_enable_thinking") is True),
                "thinking_heuristic_applied": bool(cot_observation.get("thinking_heuristic_applied") is True),
                "response_has_think_tags": bool(cot_observation.get("response_has_think_tags") is True),
                "response_has_reasoning_content": bool(cot_observation.get("response_has_reasoning_content") is True),
            }
        }
        return self._apply_result_sanity(result)

    async def evaluate_batch_compact(
        self,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        *,
        pack_id: str = "",
        pack_size: int = 0,
        low_confidence_threshold: float = 0.45,
        context_token_budget: int = 7000,
        quality_profile: str = "throughput_v1",
        batch_output_mode: str = "full",
    ) -> Dict[str, Any]:
        quality_profile_normalized = normalize_quality_profile(quality_profile)
        batch_output_mode_normalized = normalize_batch_output_mode(
            batch_output_mode,
            quality_profile=quality_profile_normalized,
        )
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
                        "quality_profile": quality_profile_normalized,
                        "batch_output_mode": batch_output_mode_normalized,
                        "pack_id": pack_id,
                        "pack_size": int(pack_size or len(effective_rules)),
                        "pack_fallback": False,
                        "context_tokens_estimate": 0,
                    },
                }
            )

        if not applicable_rules:
            return {
                "results": [
                    self._apply_batch_output_mode(item, batch_output_mode=batch_output_mode_normalized)
                    for item in not_applicable_results
                ],
                "tokens_used": 0,
                "api_time": 0.0,
                "raw_output": "",
                "parse_error": False,
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "context_tokens_estimate": 0,
            }

        resolved_budget = self._resolve_context_token_budget(
            rules=applicable_rules,
            medical_record=medical_record,
            base_budget=context_token_budget,
            quality_profile=quality_profile_normalized,
        )
        prompt, context_tokens_estimate = self._build_batch_prompt_compact(
            applicable_rules,
            medical_record,
            context_token_budget=resolved_budget,
            quality_profile=quality_profile_normalized,
            batch_output_mode=batch_output_mode_normalized,
        )
        llm_result = await self._llm_generate(prompt)
        raw_output = (
            llm_result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        usage = llm_result.get("usage", {})
        usage_breakdown = dict(llm_result.get("_usage_breakdown") or {})
        tokens_used = int(usage_breakdown.get("total_tokens") or usage.get("total_tokens", 0) or 0)
        prompt_tokens = int(usage_breakdown.get("prompt_tokens") or 0)
        completion_tokens = int(usage_breakdown.get("completion_tokens") or 0)
        api_time = float(llm_result.get("_api_time", 0.0) or 0.0)
        first_result_latency = float(llm_result.get("_first_result_latency", 0.0) or 0.0)
        cot_observation = dict(llm_result.get("_cot_observation") or {})

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
        distributed_prompt_tokens = int(prompt_tokens / max(1, len(applicable_rules)))
        distributed_completion_tokens = int(completion_tokens / max(1, len(applicable_rules)))
        distributed_api_time = float(api_time / max(1, len(applicable_rules)))

        llm_results: List[Dict[str, Any]] = []
        for rule in applicable_rules:
            rule_id = str(rule.get("rule_id") or "").strip().upper()
            rule_name = str(rule.get("name") or "")
            parsed_item = dict(parsed_map.get(rule_id) or {})

            if not parsed_item:
                llm_results.append(
                    self._apply_batch_output_mode(
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
                                "prompt_tokens": distributed_prompt_tokens,
                                "completion_tokens": distributed_completion_tokens,
                                "input_tokens": distributed_prompt_tokens,
                                "output_tokens": distributed_completion_tokens,
                                "api_time": distributed_api_time,
                                "first_result_latency": first_result_latency,
                                "cot_mode": str(cot_observation.get("cot_mode") or "disabled"),
                                "requested_enable_thinking": bool(cot_observation.get("requested_enable_thinking") is True),
                                "thinking_heuristic_applied": bool(cot_observation.get("thinking_heuristic_applied") is True),
                                "response_has_think_tags": bool(cot_observation.get("response_has_think_tags") is True),
                                "response_has_reasoning_content": bool(cot_observation.get("response_has_reasoning_content") is True),
                                "prompt_strategy": "batch_compact_v1",
                                "quality_profile": quality_profile_normalized,
                                "batch_output_mode": batch_output_mode_normalized,
                                "pack_id": pack_id,
                                "pack_size": int(pack_size or len(effective_rules)),
                                "pack_fallback": False,
                                "context_tokens_estimate": context_tokens_estimate,
                            },
                        },
                        batch_output_mode=batch_output_mode_normalized,
                    )
                )
                continue

            confidence = float(parsed_item.get("confidence") or 0.7)
            evidence_text, evidence_verified, evidence_span = self._refine_evidence_text(
                evidence_text=str(parsed_item.get("evidence") or ""),
                findings_text=str(parsed_item.get("findings") or ""),
                medical_record=medical_record,
            )
            if not evidence_verified:
                confidence = min(confidence, 0.5)
            if confidence < low_confidence_threshold:
                low_confidence_ids.append(rule_id)

            status = str(parsed_item.get("status") or "").strip().lower()
            is_compliant = bool(parsed_item.get("is_compliant") is True)
            if status not in {"compliant", "non_compliant", "not_applicable", "uncertain"}:
                status = "compliant" if is_compliant else "non_compliant"
            if status == "not_applicable":
                is_compliant = True

            result_item = {
                    "rule_id": rule.get("rule_id"),
                    "rule_name": rule_name,
                    "status": status,
                    "is_compliant": is_compliant,
                    "issues": parsed_item.get("issues") or [],
                    "findings": parsed_item.get("findings") or "",
                    "evidence": evidence_text,
                    "suggestion": self._normalize_suggestion_by_status(
                        status=status,
                        suggestion=str(parsed_item.get("suggestion") or ""),
                        rule_name=str(rule_name or ""),
                    ),
                    "rewrite_example": self._build_rewrite_example(
                        rule_id=str(rule_id or "").strip().upper(),
                        status=status,
                        medical_record=medical_record,
                    ),
                    "confidence": confidence,
                    "llm_raw_output": raw_output,
                    "applicability": {
                        "is_applicable": True,
                        "reason": "",
                        "method": "default",
                    },
                    "evidence_verified": evidence_verified,
                    "evidence_span": evidence_span,
                    "metadata": {
                        "tokens_used": distributed_tokens,
                        "prompt_tokens": distributed_prompt_tokens,
                        "completion_tokens": distributed_completion_tokens,
                        "input_tokens": distributed_prompt_tokens,
                        "output_tokens": distributed_completion_tokens,
                        "api_time": distributed_api_time,
                        "first_result_latency": first_result_latency,
                        "cot_mode": str(cot_observation.get("cot_mode") or "disabled"),
                        "requested_enable_thinking": bool(cot_observation.get("requested_enable_thinking") is True),
                        "thinking_heuristic_applied": bool(cot_observation.get("thinking_heuristic_applied") is True),
                        "response_has_think_tags": bool(cot_observation.get("response_has_think_tags") is True),
                        "response_has_reasoning_content": bool(cot_observation.get("response_has_reasoning_content") is True),
                        "prompt_strategy": "batch_compact_v1",
                        "quality_profile": quality_profile_normalized,
                        "batch_output_mode": batch_output_mode_normalized,
                        "pack_id": pack_id,
                        "pack_size": int(pack_size or len(effective_rules)),
                        "pack_fallback": False,
                        "context_tokens_estimate": context_tokens_estimate,
                    },
                }
            llm_results.append(
                self._apply_batch_output_mode(
                    self._apply_result_sanity(result_item),
                    batch_output_mode=batch_output_mode_normalized,
                )
            )

        return {
            "results": [
                *[
                    self._apply_batch_output_mode(item, batch_output_mode=batch_output_mode_normalized)
                    for item in not_applicable_results
                ],
                *llm_results,
            ],
            "tokens_used": tokens_used,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "api_time": api_time,
            "first_result_latency": first_result_latency,
            "cot_observation": cot_observation,
            "raw_output": raw_output,
            "parse_error": bool(parsed.get("parse_error") is True),
            "missing_rule_ids": missing_ids,
            "low_confidence_rule_ids": sorted(set(low_confidence_ids)),
            "context_tokens_estimate": context_tokens_estimate,
        }

    @staticmethod
    def _apply_batch_output_mode(result: Dict[str, Any], *, batch_output_mode: str) -> Dict[str, Any]:
        if batch_output_mode != BATCH_OUTPUT_MODE_MINIMAL:
            return result
        normalized = dict(result or {})
        status = str(normalized.get("status") or "").strip().lower()
        findings = re.sub(r"\s+", " ", str(normalized.get("findings") or "")).strip()
        evidence = re.sub(r"\s+", " ", str(normalized.get("evidence") or "")).strip()
        suggestion = re.sub(r"\s+", " ", str(normalized.get("suggestion") or "")).strip()
        rewrite_example = re.sub(r"\s+", " ", str(normalized.get("rewrite_example") or "")).strip()

        if len(findings) > 40:
            findings = findings[:40].rstrip("，,。；; ") + "..."
        if len(evidence) > 80:
            evidence = evidence[:80].rstrip("，,。；; ") + "..."
        if status in {"compliant", "not_applicable"}:
            suggestion = ""
        elif len(suggestion) > 30:
            suggestion = suggestion[:30].rstrip("，,。；; ") + "..."
        if len(rewrite_example) > 120:
            rewrite_example = rewrite_example[:120].rstrip("，,。；; ") + "..."

        normalized["findings"] = findings
        normalized["evidence"] = evidence
        normalized["suggestion"] = suggestion
        normalized["rewrite_example"] = rewrite_example
        normalized["issues"] = []
        return normalized

    def _build_batch_prompt_compact(
        self,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        *,
        context_token_budget: int = 7000,
        quality_profile: str = "throughput_v1",
        batch_output_mode: str = "full",
    ) -> Tuple[str, int]:
        content = str(medical_record.get("content") or "")
        evidence_payload = medical_record.get("evidence_payload")
        quality_profile_normalized = normalize_quality_profile(quality_profile)
        batch_output_mode_normalized = normalize_batch_output_mode(
            batch_output_mode,
            quality_profile=quality_profile_normalized,
        )
        rule_families = [
            normalize_rule_family(rule.get("rule_family"))
            for rule in list(rules or [])
        ]
        dominant_family = self._dominant_rule_family(rule_families)
        context_text, context_tokens = self._build_compact_context(
            content=content,
            evidence_payload=evidence_payload if isinstance(evidence_payload, dict) else {},
            context_token_budget=context_token_budget,
            rule_family=dominant_family,
            quality_profile=quality_profile_normalized,
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
            check_limit = family_check_limit(
                rule.get("rule_family") or dominant_family,
                quality_profile=quality_profile_normalized,
            )
            if len(checks) > check_limit:
                checks = checks[:check_limit] + "..."
            card_lines.append(
                f"- rule_id: {rule_id}\n"
                f"  rule_name: {rule_name}\n"
                f"  defect_level: {defect_level}\n"
                f"  rule_family: {normalize_rule_family(rule.get('rule_family') or dominant_family)}\n"
                f"  checks: {checks}\n"
                f"  guardrails: {self._compact_rule_guardrails(rule_id)}"
            )

        output_rules = (
            "- findings 最多 40 字，只写一句结论，不要分点展开。\n"
            "- evidence 最多 80 字，只保留 1-2 个直接原文片段。\n"
            "- suggestion 最多 30 字，只给最短整改动作；compliant/not_applicable 置空。\n"
            "- issues 固定输出空数组 []。\n"
            if batch_output_mode_normalized == BATCH_OUTPUT_MODE_MINIMAL
            else "- evidence 尽量引用原文短句。\n"
        )

        prompt = (
            "你是资深病历质控专家。请基于下方病历证据，对规则列表逐条判定。\n"
            "要求：\n"
            "1. 只输出 JSON，不要解释。\n"
            "2. 必须覆盖全部 rule_id，每条只输出一次。\n"
            "3. 若证据不足，status=uncertain，is_compliant=false，并说明缺失证据。\n"
            f"{output_rules}"
            "- 不得因轻微格式问题、术语不够漂亮、标题顺序一般，就直接判 non_compliant。\n"
            "- 若核心内容已存在，只是提炼一般、表达一般或边界不清，优先 uncertain。\n"
            "- findings / evidence / suggestion 必须一致，不得出现“不合规但无需修改”。\n\n"
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
        rule_family: str = "general",
        quality_profile: str = "throughput_v1",
    ) -> Tuple[str, int]:
        budget = max(1200, int(context_token_budget or 7000))
        primary = str(content or "").strip()
        quality_profile_normalized = normalize_quality_profile(quality_profile)
        family = normalize_rule_family(rule_family)
        limits = evidence_limits_for_family(family, quality_profile=quality_profile_normalized)
        primary_limit = min(len(primary), int(limits["primary_limit"]))
        primary_text = select_family_snippet(primary, rule_family=family, limit=primary_limit)

        supporting = list(evidence_payload.get("supporting_documents") or [])
        timeline = list(evidence_payload.get("timeline_facts") or [])
        document_hits = evidence_payload.get("document_hits") or {}
        quality_flags = list(evidence_payload.get("data_quality_flags") or [])

        supporting = self._rank_supporting_documents(
            supporting,
            rule_family=family,
            quality_profile=quality_profile_normalized,
        )
        timeline = self._rank_timeline_facts(
            timeline,
            rule_family=family,
            quality_profile=quality_profile_normalized,
        )

        support_limit = min(len(supporting), int(limits["support_limit"]))
        timeline_limit = min(len(timeline), int(limits["timeline_limit"]))
        support_snippet_limit = int(limits["support_snippet_limit"])
        timeline_snippet_limit = int(limits["timeline_snippet_limit"])
        min_primary_limit = int(limits["min_primary_limit"])

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
                    if len(snippet) > support_snippet_limit:
                        snippet = select_family_snippet(snippet, rule_family=family, limit=support_snippet_limit)
                    if snippet:
                        lines.append(f"- [{doc_type}] {snippet}")
            if timeline_limit > 0:
                lines.append("【时间线事实】")
                for fact in timeline[:timeline_limit]:
                    text = str(fact).strip()
                    if not text:
                        continue
                    if len(text) > timeline_snippet_limit:
                        text = text[:timeline_snippet_limit] + "..."
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
        while estimated_tokens > budget and len(primary_text) > min_primary_limit:
            primary_text = primary_text[: max(min_primary_limit, int(len(primary_text) * 0.8))]
            context_text = _render_ctx()
            estimated_tokens = self._estimate_tokens(context_text)

        return context_text, estimated_tokens

    def _resolve_context_token_budget(
        self,
        *,
        rules: List[Dict[str, Any]],
        medical_record: Dict[str, Any],
        base_budget: int,
        quality_profile: str = "throughput_v1",
    ) -> int:
        budget = max(4500, int(base_budget or 7000))
        if is_effect_priority_profile(quality_profile):
            budget = max(budget, 8600)

        execution_domain = str(medical_record.get("execution_domain") or "").strip().lower()
        if not execution_domain:
            for rule in rules:
                execution_domain = str(rule.get("execution_domain") or "").strip().lower()
                if execution_domain:
                    break
        if not execution_domain:
            execution_domain = "generic"

        doc_scope = str(medical_record.get("doc_scope") or "").strip().lower()
        if not doc_scope:
            for rule in rules:
                doc_scope = str(rule.get("doc_scope") or "").strip().lower()
                if doc_scope:
                    break
        if not doc_scope:
            doc_scope = "primary"

        budget += int(self._DOMAIN_CONTEXT_BUDGET_DELTA.get(execution_domain, 0))
        if doc_scope not in {"", "primary"}:
            budget += 400

        model_version = str(medical_record.get("model_version") or "").strip().lower()
        if model_version:
            if any(token in model_version for token in ("7b", "8b", "13b", "14b", "mini", "small")):
                budget -= 900
            elif any(token in model_version for token in ("32b", "34b", "35b", "70b", "72b", "110b", "gpt-4", "gpt-5", "claude-3-opus")):
                budget += 500

        upper_bound = 12500 if is_effect_priority_profile(quality_profile) else 9800
        return max(4500, min(upper_bound, int(budget)))

    @staticmethod
    def _dominant_rule_family(rule_families: List[str]) -> str:
        counts: Dict[str, int] = {}
        for family in rule_families:
            normalized = normalize_rule_family(family)
            counts[normalized] = counts.get(normalized, 0) + 1
        if not counts:
            return "general"
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    @staticmethod
    def _rank_supporting_documents(
        supporting: List[Any],
        *,
        rule_family: str,
        quality_profile: str,
    ) -> List[Any]:
        if not is_effect_priority_profile(quality_profile):
            return list(supporting or [])

        keywords = [keyword.lower() for keyword in family_keywords(rule_family)]

        def _score(item: Any) -> int:
            if not isinstance(item, dict):
                return 0
            text = " ".join(
                [
                    str(item.get("document_type") or ""),
                    str(item.get("source_table") or ""),
                    str(item.get("evidence_text") or item.get("content") or item.get("text_preview") or ""),
                ]
            ).lower()
            score = sum(4 for keyword in keywords if keyword and keyword in text)
            source = str(item.get("document_type") or item.get("source_table") or "").lower()
            family = normalize_rule_family(rule_family)
            if family == "procedure_order_linkage" and any(token in source for token in ("surgery", "anesthesia", "order", "exam", "pathology", "手术", "麻醉", "医嘱", "检查", "病理")):
                score += 8
            if family == "signature_authority" and any(token in text for token in ("签名", "签字", "审核", "医师")):
                score += 8
            if family == "timeliness" and any(token in text for token in ("时间", "小时", "日期", "记录")):
                score += 6
            return score

        return sorted(list(supporting or []), key=_score, reverse=True)

    @staticmethod
    def _rank_timeline_facts(
        timeline: List[Any],
        *,
        rule_family: str,
        quality_profile: str,
    ) -> List[Any]:
        if not is_effect_priority_profile(quality_profile):
            return list(timeline or [])
        if normalize_rule_family(rule_family) != "timeliness":
            return list(timeline or [])
        return sorted(
            list(timeline or []),
            key=lambda item: 0 if any(token in str(item) for token in ("入院", "出院", "术后", "记录", "完成", "时间")) else 1,
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 1
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        latin_digit_count = len(re.findall(r"[A-Za-z0-9]", text))
        whitespace_count = len(re.findall(r"\s", text))
        other_count = max(0, len(text) - cjk_count - latin_digit_count - whitespace_count)

        # 中文 token 密度高于英文；这里做混合估算，便于预算裁剪更接近真实开销。
        estimate = (
            cjk_count * 0.95
            + latin_digit_count / 3.6
            + other_count / 2.1
        )
        return max(1, int(estimate))

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
            base = "；".join(snippets)
        else:
            base = source[:260]
        guardrails = UnifiedRuleEngine._compact_rule_guardrails(
            str(rule.get("rule_id") or rule.get("rule_code") or "")
        )
        if guardrails:
            return f"{base}；{guardrails}"
        return base

    @staticmethod
    def _compact_rule_guardrails(rule_id: str) -> str:
        normalized_rule_id = str(rule_id or "").strip().upper()
        if not normalized_rule_id:
            return ""
        guardrails = {
            "SC-023": "仅在病例特点核心内容实质缺失时判不合规；已写但提炼一般优先uncertain",
            "SC-024": "病例特点若只是现病史/查体/检查原文堆砌且无概括性总结，直接判non_compliant；已有分点概括或诊断导向性总结则判compliant",
            "SC-025": "仅看诊断依据/鉴别诊断/诊疗计划三项；不要把中医项缺失并入主结论",
            "SC-011": "现病史若仅复述主诉且无任何鉴别相关症状或专科要点，直接判non_compliant；已有关键症状或专科查体则判compliant",
            "SC-012": "长病程或有门诊/外院处理线索却未交代检查治疗效果，直接判non_compliant；明确写未诊治/仅观察则判compliant",
            "SC-019": "已明确写出入院前检查名称和关键结果则判compliant；只有完全未记录、抄写错误或结果混乱不清时才判non_compliant",
            "SC-026": "已有具体鉴别病种且有至少一条具体排除依据则判compliant；若只有病名加“依据不支持/待排”等空话、无具体推理，直接判non_compliant",
            "SC-027": "仅当缺少关键诊疗动作或明显不具体时判不合规；格式问题不要硬判",
            "SC-032": "日常病程若仅写病情同前/继续治疗等套话且无任何具体症状体征变化，直接判non_compliant",
            "SC-033": "已有感染/检查/用药线索但无分析或具体处理意见时，直接判non_compliant；有疗效判断或后续计划则判compliant",
            "SC-036": "上下文有重要异常检查结果而病程未提及或无分析处理时，直接判non_compliant；无异常检查线索不要硬判",
            "SC-070": "病程记录若只是照抄会诊意见、未写是否采纳及具体执行动作/结果，直接判non_compliant；写明已落实的检查/用药/处理或未采纳理由则判compliant",
            "SC-050": "若主文书与辅助证据全文或核心句子基本相同且无新增分析/计划，直接判non_compliant；若有新增判断或计划则判compliant",
            "SC-121": "只抓关键诊疗经过缺失，不做药理学或格式化发散点评",
            "SC-125": "优先判断出院诊断明显漏填/错填/顺序错误，不把既往史展开不足作为主依据",
        }
        return guardrails.get(normalized_rule_id, "")

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
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "")
        evidence_context = ""
        if isinstance(evidence_payload, dict) and evidence_payload:
            evidence_context = self._format_evidence_payload(evidence_payload)
        marked_medical_text = (
            "\n\n==================== 以下是待评估的实际病历文本 ====================\n"
            f"{medical_text}\n"
            "==================== 病历文本结束 ====================\n"
        )
        prompt_input_text = f"{marked_medical_text}{evidence_context}"
        guardrails = self._compact_rule_guardrails(rule_id)
        common_guardrails = (
            "\n\n【统一判定约束】\n"
            "- 不得因轻微格式问题、术语不够漂亮、段落顺序一般，直接判 non_compliant。\n"
            "- 若核心内容已存在，只是提炼一般、表达一般或边界不清，优先判 uncertain。\n"
            "- findings / evidence / suggestion 必须一致，不得出现“不合规但无需修改”。\n"
        )
        if guardrails:
            common_guardrails += f"【规则级收敛要求】\n- {guardrails}\n"

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
            prompt += common_guardrails
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
{common_guardrails}
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
        default_result["findings"] = UnifiedRuleEngine._stringify_llm_text(parsed_json.get("findings", ""))
        default_result["evidence"] = UnifiedRuleEngine._stringify_llm_text(parsed_json.get("evidence", ""))
        default_result["suggestion"] = UnifiedRuleEngine._stringify_llm_text(parsed_json.get("suggestion", ""))
        try:
            default_result["confidence"] = float(parsed_json.get("confidence", 0.7))
        except Exception:
            default_result["confidence"] = 0.7

        return default_result

    @staticmethod
    def _stringify_llm_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "；".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _is_no_change_suggestion(text: str) -> bool:
        normalized = str(text or "").strip().replace(" ", "")
        if not normalized:
            return False
        patterns = (
            r"(无需|无须).{0,4}(修改|调整|处理|整改|更改|改动|补充)",
            r"无需整改",
            r"无需处理",
            r"无需完善",
            r"符合规则要求",
            r"符合要求",
            r"无明显问题",
        )
        return any(re.search(pattern, normalized) for pattern in patterns)

    @classmethod
    def _normalize_suggestion_by_status(
        cls,
        *,
        status: str,
        suggestion: str,
        rule_name: str = "",
    ) -> str:
        normalized_status = str(status or "").strip().lower()
        suggestion_text = str(suggestion or "").strip()

        if normalized_status == "non_compliant":
            if (not suggestion_text) or cls._is_no_change_suggestion(suggestion_text):
                if rule_name:
                    return f"请按“{rule_name}”规则补充或修正相关记录。"
                return "请根据规则要求补充或修正相关记录。"
            return suggestion_text

        if normalized_status == "uncertain" and cls._is_no_change_suggestion(suggestion_text):
            return "证据不足，建议人工复核相关文书并补充佐证。"

        return suggestion_text

    @classmethod
    def _apply_result_sanity(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(result or {})
        rule_id = str(normalized.get("rule_id") or "").strip().upper()
        status = str(normalized.get("status") or "").strip().lower()
        findings = str(normalized.get("findings") or "").strip()
        suggestion = str(normalized.get("suggestion") or "").strip()
        evidence = str(normalized.get("evidence") or "").strip()
        confidence = float(normalized.get("confidence") or 0.7)
        evidence_verified = bool(normalized.get("evidence_verified") is True)

        if status == "non_compliant" and cls._is_no_change_suggestion(suggestion):
            normalized["status"] = "uncertain"
            normalized["is_compliant"] = False
            normalized["confidence"] = min(confidence, 0.5)
            normalized["suggestion"] = "当前结论与整改建议不一致，建议人工复核后再确认是否需要修改。"
            return normalized

        if status == "non_compliant" and not evidence:
            normalized["status"] = "uncertain"
            normalized["is_compliant"] = False
            normalized["confidence"] = min(confidence, 0.5)
            normalized["suggestion"] = "当前缺少可直接支撑结论的原文证据，建议人工复核相关文书。"
            return normalized

        if status == "non_compliant" and not evidence_verified:
            findings_text = str(normalized.get("findings") or "")
            evidence_text = str(normalized.get("evidence") or "")
            if rule_id == "SC-024":
                strong_feature_copy_hints = (
                    "原文堆砌",
                    "缺乏归纳提炼",
                    "无概括性总结",
                    "直接复制现病史",
                    "只是现病史与检查原文",
                )
                if any(hint in findings_text or hint in evidence_text for hint in strong_feature_copy_hints):
                    return normalized

            if rule_id in {"SC-023", "SC-025", "SC-125"}:
                normalized["status"] = "uncertain"
                normalized["is_compliant"] = False
                normalized["confidence"] = min(confidence, 0.5)
                normalized["suggestion"] = "当前规则边界较敏感，且原文证据支撑不足，建议人工复核后再决定是否判为不合规。"
                return normalized

            if rule_id in {"SC-024", "SC-026", "SC-027", "SC-036", "SC-121"} and confidence <= 0.5:
                normalized["status"] = "uncertain"
                normalized["is_compliant"] = False
                normalized["confidence"] = min(confidence, 0.5)
                normalized["suggestion"] = "当前原文证据支撑不足，更适合作为待复核问题处理。"
                return normalized

        if rule_id == "SC-032" and status == "compliant":
            uncertainty_hints = (
                "最终判定：uncertain",
                "优先判 uncertain",
                "证据不足",
                "边界",
                "细节不足",
            )
            if any(hint in findings for hint in uncertainty_hints):
                normalized["status"] = "uncertain"
                normalized["is_compliant"] = False
                normalized["confidence"] = min(confidence, 0.5)
                normalized["suggestion"] = "当前结果处于合规与不合规的边界，建议人工复核病程记录细节。"
                return normalized

        return normalized

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
