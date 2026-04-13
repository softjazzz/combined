from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


@dataclass(frozen=True)
class ProgrammaticRuleSpec:
    rule_id: str
    strategy: str
    description: str
    keywords: tuple[str, ...] = ()


PROGRAMMATIC_RULE_SPECS: dict[str, ProgrammaticRuleSpec] = {
    "SC-001": ProgrammaticRuleSpec(
        rule_id="SC-001",
        strategy="exists_any",
        description="入院记录/24小时内入出院记录存在性",
        keywords=("入院记录", "再次入院记录", "多次入院记录", "24小时内入出院", "24小时内入出院(死亡)记录"),
    ),
    "SC-002": ProgrammaticRuleSpec(
        rule_id="SC-002",
        strategy="time_within_24h_after_admission",
        description="入院记录 24 小时时效",
    ),
    "SC-003": ProgrammaticRuleSpec(
        rule_id="SC-003",
        strategy="time_within_24h_after_discharge_or_death",
        description="24 小时内入出院(死亡)记录时效",
    ),
    "SC-005": ProgrammaticRuleSpec(
        rule_id="SC-005",
        strategy="non_licensed_review_signature",
        description="非执业医师书写需审阅签名",
    ),
    "SC-006": ProgrammaticRuleSpec(
        rule_id="SC-006",
        strategy="doctor_signature_required",
        description="入院记录医师签名",
    ),
    "SC-116": ProgrammaticRuleSpec(
        rule_id="SC-116",
        strategy="exists_any",
        description="出院/死亡记录存在性",
        keywords=("出院记录", "死亡记录"),
    ),
    "SC-117": ProgrammaticRuleSpec(
        rule_id="SC-117",
        strategy="time_within_24h_after_discharge_or_death",
        description="出院/死亡记录 24 小时时效",
    ),
    "SC-118": ProgrammaticRuleSpec(
        rule_id="SC-118",
        strategy="required_fields_from_title",
        description="出院记录关键字段完整性",
    ),
    "SC-119": ProgrammaticRuleSpec(
        rule_id="SC-119",
        strategy="required_fields_from_title",
        description="死亡记录关键字段完整性",
    ),
    "SC-120": ProgrammaticRuleSpec(
        rule_id="SC-120",
        strategy="exists_any",
        description="死亡证明书存在性",
        keywords=("死亡证明书", "死亡医学证明", "居民死亡医学证明"),
    ),
}


class ProgrammaticRuleExecutor:
    """
    首批确定性规则执行器（P0）。

    仅处理可稳定程序判定的规则，不处理复杂跨文书语义规则。
    """

    _NEGATIVE_SIGNATURE_HINTS = ("无签名", "未签名", "缺签名", "未见签名", "签名缺失")
    _POSITIVE_SIGNATURE_HINTS = ("医师签名", "签名:", "签名：", "签字", "审核医师", "审阅医师", "上级医师")
    _NON_LICENSED_HINTS = ("非执业医师", "规培", "实习", "住院医师")
    _REVIEW_HINTS = ("审阅", "审核", "修改并签名", "上级医师签名", "带教医师签名")

    _ADMISSION_TIME_LABELS = ("入院日期", "入院时间")
    _DISCHARGE_TIME_LABELS = ("出院日期", "出院时间", "死亡时间")
    _COMPLETION_TIME_LABELS = ("记录时间", "记录日期", "书写时间", "完成时间")

    def can_execute(self, rule: dict[str, Any]) -> bool:
        rule_id = str(rule.get("rule_id") or "").strip().upper()
        return rule_id in PROGRAMMATIC_RULE_SPECS

    def evaluate(
        self,
        *,
        rule: dict[str, Any],
        medical_record: dict[str, Any],
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        rule_id = str(rule.get("rule_id") or "").strip().upper()
        spec = PROGRAMMATIC_RULE_SPECS.get(rule_id)
        if not spec:
            raise ValueError(f"程序化执行器不支持该规则: {rule_id or 'unknown'}")

        content = str(medical_record.get("content") or "")
        started_at = datetime.utcnow()
        status, is_compliant, findings, evidence, suggestion, confidence, applicability = self._dispatch(
            spec=spec,
            rule=rule,
            content=content,
        )
        api_time = (datetime.utcnow() - started_at).total_seconds()

        return {
            "rule_id": rule_id,
            "rule_name": str(rule.get("name") or ""),
            "status": status,
            "is_compliant": is_compliant,
            "issues": [],
            "findings": findings,
            "evidence": evidence,
            "suggestion": suggestion,
            "confidence": confidence,
            "llm_raw_output": None,
            "applicability": applicability,
            "evidence_verified": True,
            "evidence_span": None,
            "metadata": {
                "tokens_used": 0,
                "api_time": api_time,
                "executor_type": "program",
                "rule_version": str((meta or {}).get("rule_version") or ""),
                "prompt_version": str((meta or {}).get("prompt_version") or ""),
                "model_version": "programmatic-v1",
            },
        }

    def _dispatch(
        self,
        *,
        spec: ProgrammaticRuleSpec,
        rule: dict[str, Any],
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        if spec.strategy == "exists_any":
            return self._evaluate_exists_any(spec=spec, content=content)
        if spec.strategy == "doctor_signature_required":
            return self._evaluate_doctor_signature(content=content)
        if spec.strategy == "non_licensed_review_signature":
            return self._evaluate_non_licensed_review_signature(content=content)
        if spec.strategy == "time_within_24h_after_admission":
            return self._evaluate_time_window(
                content=content,
                anchor_labels=self._ADMISSION_TIME_LABELS,
                completion_labels=self._COMPLETION_TIME_LABELS,
                rule_hint="入院后24小时内完成",
            )
        if spec.strategy == "time_within_24h_after_discharge_or_death":
            return self._evaluate_time_window(
                content=content,
                anchor_labels=self._DISCHARGE_TIME_LABELS,
                completion_labels=self._COMPLETION_TIME_LABELS,
                rule_hint="出院(死亡)后24小时内完成",
            )
        if spec.strategy == "required_fields_from_title":
            return self._evaluate_required_fields_from_title(rule=rule, content=content)
        raise ValueError(f"未知程序化策略: {spec.strategy}")

    def _evaluate_exists_any(
        self,
        *,
        spec: ProgrammaticRuleSpec,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        hit_keywords = [kw for kw in spec.keywords if kw and kw in content]
        if hit_keywords:
            evidence = f"命中文本关键字: {', '.join(hit_keywords[:3])}"
            return (
                "compliant",
                True,
                "文书存在性检查通过。",
                evidence,
                "",
                0.95,
                {"is_applicable": True, "reason": "", "method": "program_exists"},
            )
        return (
            "non_compliant",
            False,
            "未检测到规则要求的文书记录。",
            f"缺失关键字: {', '.join(spec.keywords)}",
            "请补充对应文书并完成签署。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "program_exists"},
        )

    def _evaluate_doctor_signature(
        self,
        *,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        if any(hint in content for hint in self._NEGATIVE_SIGNATURE_HINTS):
            return (
                "non_compliant",
                False,
                "检测到签名缺失描述。",
                "命中缺签关键词",
                "请补充记录医师签名并校对签名位置。",
                0.9,
                {"is_applicable": True, "reason": "", "method": "program_signature"},
            )
        if any(hint in content for hint in self._POSITIVE_SIGNATURE_HINTS):
            return (
                "compliant",
                True,
                "检测到医师签名信息。",
                "命中签名关键词",
                "",
                0.9,
                {"is_applicable": True, "reason": "", "method": "program_signature"},
            )
        return (
            "non_compliant",
            False,
            "未检测到明确签名信息。",
            "未命中签名关键词",
            "请在文书末尾补充医师签名信息。",
            0.82,
            {"is_applicable": True, "reason": "", "method": "program_signature"},
        )

    def _evaluate_non_licensed_review_signature(
        self,
        *,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        non_licensed = any(hint in content for hint in self._NON_LICENSED_HINTS)
        if not non_licensed:
            return (
                "not_applicable",
                True,
                "未发现非执业医师书写场景，本规则不适用。",
                "",
                "",
                0.95,
                {"is_applicable": False, "reason": "未命中非执业医师条件", "method": "program_non_licensed_guard"},
            )
        has_review_signature = any(hint in content for hint in self._REVIEW_HINTS)
        if has_review_signature:
            return (
                "compliant",
                True,
                "检测到审阅/上级签名信息。",
                "命中审阅签名关键词",
                "",
                0.9,
                {"is_applicable": True, "reason": "", "method": "program_non_licensed_review"},
            )
        return (
            "non_compliant",
            False,
            "存在非执业医师书写但未检测到审阅签名。",
            "命中非执业关键词，未命中审阅签名关键词",
            "请由本机构注册医务人员补充审阅、修改并签名。",
            0.9,
            {"is_applicable": True, "reason": "", "method": "program_non_licensed_review"},
        )

    def _evaluate_time_window(
        self,
        *,
        content: str,
        anchor_labels: tuple[str, ...],
        completion_labels: tuple[str, ...],
        rule_hint: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        anchor_dt, anchor_raw = self._extract_labeled_datetime(content, anchor_labels)
        completion_dt, completion_raw = self._extract_labeled_datetime(content, completion_labels)
        if not anchor_dt or not completion_dt:
            return (
                "not_applicable",
                True,
                "缺少可用于程序判定的时间锚点，本规则暂按不适用处理。",
                f"锚点时间={anchor_raw or '缺失'}；完成时间={completion_raw or '缺失'}",
                "请补充明确的入/出院(死亡)时间和文书书写时间。",
                0.8,
                {"is_applicable": False, "reason": "missing_time_anchor", "method": "program_time_guard"},
            )
        delta_hours = (completion_dt - anchor_dt).total_seconds() / 3600
        evidence = f"锚点={anchor_raw}；完成={completion_raw}；间隔={delta_hours:.1f}h"
        if delta_hours <= 24:
            return (
                "compliant",
                True,
                "时效性检查通过。",
                evidence,
                "",
                0.92,
                {"is_applicable": True, "reason": "", "method": "program_time_window"},
            )
        return (
            "non_compliant",
            False,
            f"文书未在{rule_hint}内完成。",
            evidence,
            "请补录并规范记录完成时间，确保时效符合质控要求。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "program_time_window"},
        )

    def _evaluate_required_fields_from_title(
        self,
        *,
        rule: dict[str, Any],
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any]]:
        title = str(rule.get("name") or "")
        required_fields = self._extract_fields_from_title(title)
        if not required_fields:
            return (
                "not_applicable",
                True,
                "规则标题未解析到必填字段，本规则暂按不适用处理。",
                "",
                "",
                0.75,
                {"is_applicable": False, "reason": "missing_required_field_config", "method": "program_required_fields"},
            )
        missing = [field for field in required_fields if field not in content]
        if not missing:
            return (
                "compliant",
                True,
                "关键字段完整性检查通过。",
                f"已覆盖字段: {', '.join(required_fields)}",
                "",
                0.9,
                {"is_applicable": True, "reason": "", "method": "program_required_fields"},
            )
        return (
            "non_compliant",
            False,
            "关键字段记录不完整。",
            f"缺失字段: {', '.join(missing)}",
            "请补充缺失字段并核对文书内容一致性。",
            0.9,
            {"is_applicable": True, "reason": "", "method": "program_required_fields"},
        )

    @staticmethod
    def _extract_fields_from_title(title: str) -> list[str]:
        bracket_match = re.search(r"[（(]([^()（）]+)[)）]", title or "")
        raw = bracket_match.group(1) if bracket_match else ""
        if not raw:
            return []
        fields = [item.strip() for item in re.split(r"[、，,；;]", raw) if item.strip()]
        dedup: list[str] = []
        seen: set[str] = set()
        for field in fields:
            if field in seen:
                continue
            seen.add(field)
            dedup.append(field)
        return dedup

    def _extract_labeled_datetime(
        self,
        content: str,
        labels: tuple[str, ...],
    ) -> tuple[Optional[datetime], str]:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:：]?\s*([12]\d{{3}}[年/\-.]\d{{1,2}}[月/\-.]\d{{1,2}}(?:[日\sT]\s*\d{{1,2}}[:时]\d{{1,2}}(?::\d{{1,2}})?)?)"
            match = re.search(pattern, content)
            if not match:
                continue
            raw = match.group(1)
            parsed = self._parse_datetime(raw)
            if parsed:
                return parsed, raw
        return None, ""

    @staticmethod
    def _parse_datetime(raw: str) -> Optional[datetime]:
        if not raw:
            return None
        text = (
            raw.replace("年", "-")
            .replace("月", "-")
            .replace("日", " ")
            .replace("时", ":")
            .replace("分", "")
            .replace("/", "-")
            .replace(".", "-")
        )
        text = re.sub(r"\s+", " ", text).strip()
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
