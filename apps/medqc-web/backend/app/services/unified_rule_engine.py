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
    目前只实现了泸县规则中的典型场景（如 LX-003 婴幼儿喂养史），
    后续可以根据 rule_config 扩展。
    """

    PEDIATRIC_HINTS = ["患儿", "婴儿", "新生儿", "儿科", "月龄"]

    def check(self, rule: Dict[str, Any], medical_record: Dict[str, Any]) -> ApplicabilityResult:
        rule_id = (rule.get("rule_id") or "").upper()
        text = medical_record.get("content") or ""

        if rule_id == "LX-003":
            # 适用性完全交给大模型判断，不在这里做年龄/科室过滤
            return ApplicabilityResult(
                is_applicable=True,
                reason="",
                method="lx003_via_llm",
            )
        elif rule_id == "LX-005":
            # 体格检查缺生命体征：是否儿科由大模型按提示词判断
            return ApplicabilityResult(
                is_applicable=True,
                reason="",
                method="lx005_via_llm",
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

        prompt = self._build_prompt(rule, medical_record["content"])
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

    def _build_prompt(self, rule: Dict[str, Any], medical_text: str) -> str:
        template = rule.get("custom_prompt")
        marked_medical_text = (
            "\n\n==================== 以下是待评估的实际病历文本 ====================\n"
            f"{medical_text[:2000]}\n"
            "==================== 病历文本结束 ====================\n"
        )

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
                medical_text=marked_medical_text
            )
            # 兜底：如果模板中没有 {medical_text} 占位符，强制追加病历文本
            if "{medical_text}" not in template:
                logging.getLogger(__name__).warning(
                    "custom_prompt for rule %s is missing {medical_text} placeholder; appending medical text block.",
                    rule.get("rule_id")
                )
                prompt += f"\n\n【病历文本】\n{marked_medical_text}\n\n请根据上述病历文本进行质控评估，严格按照JSON格式输出结果。"
            return prompt

        # 默认提示词（与历史逻辑保持一致）
        return f"""
你是一名病历质控专家。请根据以下规则评估病历文本是否合规，只输出 JSON。

规则名称：{rule.get("name", "")}
规则描述：{rule.get("description", "")}
缺陷等级：{rule.get("defect_level", "")}

{marked_medical_text}
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
