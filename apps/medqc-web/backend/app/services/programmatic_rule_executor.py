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
    keywords_all: tuple[str, ...] = ()
    max_hours: Optional[int] = None
    anchor_labels: tuple[str, ...] = ()
    completion_labels: tuple[str, ...] = ()
    rule_hint: str = ""


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
    "SC-021": ProgrammaticRuleSpec(
        rule_id="SC-021",
        strategy="exists_any",
        description="首次病程记录存在性",
        keywords=("首次病程记录",),
    ),
    "SC-022": ProgrammaticRuleSpec(
        rule_id="SC-022",
        strategy="time_within_hours_between_labels",
        description="首次病程记录 8 小时时效",
        max_hours=8,
        anchor_labels=("入院日期", "入院时间"),
        completion_labels=("记录时间", "记录日期", "书写时间", "完成时间"),
        rule_hint="入院后8小时内完成",
    ),
    "SC-048": ProgrammaticRuleSpec(
        rule_id="SC-048",
        strategy="timeline_attending_round_48h",
        description="入院 48 小时内主治医师首次查房",
    ),
    "SC-049": ProgrammaticRuleSpec(
        rule_id="SC-049",
        strategy="timeline_senior_round_72h",
        description="入院 72 小时内高级职称/副主任以上首次查房",
    ),
    "SC-028": ProgrammaticRuleSpec(
        rule_id="SC-028",
        strategy="doctor_signature_required",
        description="病程记录经治医师签名",
    ),
    "SC-045": ProgrammaticRuleSpec(
        rule_id="SC-045",
        strategy="exists_any",
        description="有创诊疗操作记录存在性",
        keywords=("有创诊疗操作记录", "穿刺记录", "操作记录"),
    ),
    "SC-051": ProgrammaticRuleSpec(
        rule_id="SC-051",
        strategy="exists_any",
        description="上级医师查房记录存在性",
        keywords=("主任医师查房记录", "副主任医师查房记录", "查房记录"),
    ),
    "SC-052": ProgrammaticRuleSpec(
        rule_id="SC-052",
        strategy="doctor_signature_required",
        description="上级医师查房记录签名",
    ),
    "SC-056": ProgrammaticRuleSpec(
        rule_id="SC-056",
        strategy="exists_any",
        description="疑难病例讨论记录存在性",
        keywords=("疑难病例讨论", "疑难讨论"),
    ),
    "SC-067": ProgrammaticRuleSpec(
        rule_id="SC-067",
        strategy="exists_any",
        description="会诊记录存在性",
        keywords=("会诊记录", "会诊单"),
    ),
    "SC-071": ProgrammaticRuleSpec(
        rule_id="SC-071",
        strategy="time_within_hours_between_labels",
        description="常规会诊 24 小时时效",
        max_hours=24,
        anchor_labels=("会诊申请时间", "申请时间"),
        completion_labels=("会诊时间", "记录时间", "完成时间"),
        rule_hint="会诊申请后24小时内完成",
    ),
    "SC-082": ProgrammaticRuleSpec(
        rule_id="SC-082",
        strategy="exists_any",
        description="术前讨论记录存在性",
        keywords=("术前讨论",),
    ),
    "SC-087": ProgrammaticRuleSpec(
        rule_id="SC-087",
        strategy="exists_any",
        description="手术同意书存在性",
        keywords=("手术同意书", "手术知情同意"),
    ),
    "SC-090": ProgrammaticRuleSpec(
        rule_id="SC-090",
        strategy="exists_any",
        description="麻醉同意书存在性",
        keywords=("麻醉同意书", "麻醉知情同意"),
    ),
    "SC-095": ProgrammaticRuleSpec(
        rule_id="SC-095",
        strategy="exists_any",
        description="手术记录存在性",
        keywords=("手术记录",),
    ),
    "SC-096": ProgrammaticRuleSpec(
        rule_id="SC-096",
        strategy="time_within_hours_between_labels",
        description="手术记录 24 小时时效",
        max_hours=24,
        anchor_labels=("手术结束时间", "手术时间", "手术日期"),
        completion_labels=("记录时间", "记录日期", "书写时间", "完成时间"),
        rule_hint="术后24小时内完成",
    ),
    "SC-098": ProgrammaticRuleSpec(
        rule_id="SC-098",
        strategy="doctor_signature_required",
        description="主刀医师签名",
    ),
    "SC-104": ProgrammaticRuleSpec(
        rule_id="SC-104",
        strategy="exists_all",
        description="术后首次病程与麻醉术后访视记录完整性",
        keywords_all=("术后首次病程记录", "麻醉术后访视记录"),
    ),
    "SC-111": ProgrammaticRuleSpec(
        rule_id="SC-111",
        strategy="exists_any",
        description="手术风险评估表存在性",
        keywords=("手术风险评估表", "手术风险评估"),
    ),
    "SC-112": ProgrammaticRuleSpec(
        rule_id="SC-112",
        strategy="doctor_signature_required",
        description="手术风险评估表签名",
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
    "SC-122": ProgrammaticRuleSpec(
        rule_id="SC-122",
        strategy="exists_any",
        description="出院医嘱存在性",
        keywords=("出院医嘱",),
    ),
    "SC-124": ProgrammaticRuleSpec(
        rule_id="SC-124",
        strategy="exists_any",
        description="出院/死亡诊断存在性",
        keywords=("出院诊断", "死亡诊断"),
    ),
    "SC-126": ProgrammaticRuleSpec(
        rule_id="SC-126",
        strategy="doctor_signature_required",
        description="出院/死亡记录医师签名",
    ),
    "LXE-18": ProgrammaticRuleSpec(
        rule_id="LXE-18",
        strategy="timeline_course_gap_72h",
        description="非危重症患者 3 天未完成一次病程",
    ),
    "LXE-35": ProgrammaticRuleSpec(
        rule_id="LXE-35",
        strategy="timeline_postop_course_3d",
        description="术后未连续 3 天书写病程记录",
    ),
    "SC-133": ProgrammaticRuleSpec(
        rule_id="SC-133",
        strategy="exists_any",
        description="输血知情同意书存在性",
        keywords=("输血治疗知情同意书", "输血同意书"),
    ),
    "LX-019": ProgrammaticRuleSpec(
        rule_id="LX-019",
        strategy="exists_any",
        description="手术患者术前讨论记录存在性",
        keywords=("术前讨论",),
    ),
    "LX-022": ProgrammaticRuleSpec(
        rule_id="LX-022",
        strategy="exists_any",
        description="麻醉知情同意书存在性",
        keywords=("麻醉同意书", "麻醉知情同意"),
    ),
    "LX-026": ProgrammaticRuleSpec(
        rule_id="LX-026",
        strategy="time_within_hours_between_labels",
        description="手术记录 24 小时时效",
        max_hours=24,
        anchor_labels=("手术结束时间", "手术时间", "手术日期"),
        completion_labels=("记录时间", "记录日期", "书写时间", "完成时间"),
        rule_hint="术后24小时内完成",
    ),
    "LX-029": ProgrammaticRuleSpec(
        rule_id="LX-029",
        strategy="time_within_24h_after_discharge_or_death",
        description="出院记录 24 小时时效",
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
        (
            status,
            is_compliant,
            findings,
            evidence,
            suggestion,
            confidence,
            applicability,
            evidence_source,
        ) = self._dispatch(
            spec=spec,
            rule=rule,
            medical_record=medical_record,
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
                "evidence_source": evidence_source,
            },
        }

    def _dispatch(
        self,
        *,
        spec: ProgrammaticRuleSpec,
        rule: dict[str, Any],
        medical_record: dict[str, Any],
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        if spec.strategy == "exists_any":
            return self._evaluate_exists_any(spec=spec, content=content)
        if spec.strategy == "exists_all":
            return self._evaluate_exists_all(spec=spec, content=content)
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
        if spec.strategy == "time_within_hours_between_labels":
            return self._evaluate_time_window(
                content=content,
                anchor_labels=spec.anchor_labels or self._ADMISSION_TIME_LABELS,
                completion_labels=spec.completion_labels or self._COMPLETION_TIME_LABELS,
                rule_hint=spec.rule_hint or "规定时限内完成",
                max_hours=max(1, int(spec.max_hours or 24)),
            )
        if spec.strategy == "required_fields_from_title":
            return self._evaluate_required_fields_from_title(rule=rule, content=content)
        if spec.strategy == "timeline_attending_round_48h":
            return self._evaluate_timeline_attending_round(medical_record=medical_record, max_hours=48)
        if spec.strategy == "timeline_senior_round_72h":
            return self._evaluate_timeline_senior_round(medical_record=medical_record, max_hours=72)
        if spec.strategy == "timeline_course_gap_72h":
            return self._evaluate_timeline_course_gap(medical_record=medical_record, max_hours=72)
        if spec.strategy == "timeline_postop_course_3d":
            return self._evaluate_timeline_postop_course(medical_record=medical_record)
        raise ValueError(f"未知程序化策略: {spec.strategy}")

    def _evaluate_exists_any(
        self,
        *,
        spec: ProgrammaticRuleSpec,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
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
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            "未检测到规则要求的文书记录。",
            f"缺失关键字: {', '.join(spec.keywords)}",
            "请补充对应文书并完成签署。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "program_exists"},
            "medical_text",
        )

    def _evaluate_exists_all(
        self,
        *,
        spec: ProgrammaticRuleSpec,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        required_keywords = tuple(kw for kw in spec.keywords_all if kw)
        if not required_keywords:
            return self._evaluate_exists_any(spec=spec, content=content)
        missing_keywords = [kw for kw in required_keywords if kw not in content]
        if not missing_keywords:
            return (
                "compliant",
                True,
                "文书完整性检查通过。",
                f"已命中关键词: {', '.join(required_keywords[:4])}",
                "",
                0.94,
                {"is_applicable": True, "reason": "", "method": "program_exists_all"},
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            "规则要求的关联文书不完整。",
            f"缺失关键词: {', '.join(missing_keywords)}",
            "请补充缺失记录并补齐对应签署信息。",
            0.9,
            {"is_applicable": True, "reason": "", "method": "program_exists_all"},
            "medical_text",
        )

    def _evaluate_doctor_signature(
        self,
        *,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        if any(hint in content for hint in self._NEGATIVE_SIGNATURE_HINTS):
            return (
                "non_compliant",
                False,
                "检测到签名缺失描述。",
                "命中缺签关键词",
                "请补充记录医师签名并校对签名位置。",
                0.9,
                {"is_applicable": True, "reason": "", "method": "program_signature"},
                "medical_text",
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
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            "未检测到明确签名信息。",
            "未命中签名关键词",
            "请在文书末尾补充医师签名信息。",
            0.82,
            {"is_applicable": True, "reason": "", "method": "program_signature"},
            "medical_text",
        )

    def _evaluate_non_licensed_review_signature(
        self,
        *,
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
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
                "medical_text",
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
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            "存在非执业医师书写但未检测到审阅签名。",
            "命中非执业关键词，未命中审阅签名关键词",
            "请由本机构注册医务人员补充审阅、修改并签名。",
            0.9,
            {"is_applicable": True, "reason": "", "method": "program_non_licensed_review"},
            "medical_text",
        )

    def _evaluate_time_window(
        self,
        *,
        content: str,
        anchor_labels: tuple[str, ...],
        completion_labels: tuple[str, ...],
        rule_hint: str,
        max_hours: int = 24,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
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
                "medical_text",
            )
        delta_hours = (completion_dt - anchor_dt).total_seconds() / 3600
        evidence = f"锚点={anchor_raw}；完成={completion_raw}；间隔={delta_hours:.1f}h"
        if delta_hours <= max_hours:
            return (
                "compliant",
                True,
                "时效性检查通过。",
                evidence,
                "",
                0.92,
                {"is_applicable": True, "reason": "", "method": "program_time_window"},
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            f"文书未在{rule_hint}内完成。",
            evidence,
            "请补录并规范记录完成时间，确保时效符合质控要求。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "program_time_window"},
            "medical_text",
        )

    def _evaluate_required_fields_from_title(
        self,
        *,
        rule: dict[str, Any],
        content: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
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
                "medical_text",
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
                "medical_text",
            )
        return (
            "non_compliant",
            False,
            "关键字段记录不完整。",
            f"缺失字段: {', '.join(missing)}",
            "请补充缺失字段并核对文书内容一致性。",
            0.9,
            {"is_applicable": True, "reason": "", "method": "program_required_fields"},
            "medical_text",
        )

    def _evaluate_timeline_attending_round(
        self,
        *,
        medical_record: dict[str, Any],
        max_hours: int,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        timeline = self._get_programmatic_timeline(medical_record)
        if not timeline:
            return self._build_uncertain_timeline_result("缺少结构化时间轴，无法判断首次主治查房时效。")
        admission_time = self._parse_datetime(str(timeline.get("admission_time") or ""))
        if admission_time is None:
            return self._build_uncertain_timeline_result("缺少入院时间，无法判断首次主治查房时效。")
        events = [
            event
            for event in self._collect_course_events(timeline)
            if str(event.get("author_role") or "") == "attending"
        ]
        if not events:
            return (
                "non_compliant",
                False,
                "未找到主治医师首次查房记录。",
                "时间轴未命中主治医师查房事件",
                "请补充主治医师首次查房记录并确保入院 48 小时内完成。",
                0.9,
                {"is_applicable": True, "reason": "", "method": "timeline_attending_round"},
                "timeline",
            )
        first_event = events[0]
        authored_at = self._parse_datetime(str(first_event.get("authored_at") or ""))
        if authored_at is None:
            return self._build_uncertain_timeline_result("主治医师查房事件缺少书写时间。")
        delta_hours = (authored_at - admission_time).total_seconds() / 3600
        evidence = f"入院={admission_time.isoformat(sep=' ', timespec='seconds')}；首次主治查房={authored_at.isoformat(sep=' ', timespec='seconds')}；间隔={delta_hours:.1f}h"
        if delta_hours <= max_hours:
            return (
                "compliant",
                True,
                "主治医师首次查房时效符合要求。",
                evidence,
                "",
                0.92,
                {"is_applicable": True, "reason": "", "method": "timeline_attending_round"},
                "timeline",
            )
        return (
            "non_compliant",
            False,
            "主治医师首次查房超过 48 小时。",
            evidence,
            "请补充主治医师首次查房记录，并校正入院后 48 小时内完成的时效要求。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "timeline_attending_round"},
            "timeline",
        )

    def _evaluate_timeline_senior_round(
        self,
        *,
        medical_record: dict[str, Any],
        max_hours: int,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        timeline = self._get_programmatic_timeline(medical_record)
        if not timeline:
            return self._build_uncertain_timeline_result("缺少结构化时间轴，无法判断高级职称首次查房时效。")
        admission_time = self._parse_datetime(str(timeline.get("admission_time") or ""))
        if admission_time is None:
            return self._build_uncertain_timeline_result("缺少入院时间，无法判断高级职称首次查房时效。")
        events = [
            event
            for event in self._collect_course_events(timeline)
            if str(event.get("author_role") or "") == "senior"
        ]
        if not events:
            return (
                "non_compliant",
                False,
                "未找到副主任及以上首次查房记录。",
                "时间轴未命中高级职称查房事件",
                "请补充副主任/主任医师首次查房记录并确保入院 72 小时内完成。",
                0.9,
                {"is_applicable": True, "reason": "", "method": "timeline_senior_round"},
                "timeline",
            )
        first_event = events[0]
        authored_at = self._parse_datetime(str(first_event.get("authored_at") or ""))
        if authored_at is None:
            return self._build_uncertain_timeline_result("高级职称查房事件缺少书写时间。")
        delta_hours = (authored_at - admission_time).total_seconds() / 3600
        evidence = f"入院={admission_time.isoformat(sep=' ', timespec='seconds')}；首次高级查房={authored_at.isoformat(sep=' ', timespec='seconds')}；间隔={delta_hours:.1f}h"
        if delta_hours <= max_hours:
            return (
                "compliant",
                True,
                "高级职称首次查房时效符合要求。",
                evidence,
                "",
                0.92,
                {"is_applicable": True, "reason": "", "method": "timeline_senior_round"},
                "timeline",
            )
        return (
            "non_compliant",
            False,
            "高级职称首次查房超过 72 小时。",
            evidence,
            "请补充副主任/主任医师首次查房记录，并校正入院后 72 小时内完成的时效要求。",
            0.92,
            {"is_applicable": True, "reason": "", "method": "timeline_senior_round"},
            "timeline",
        )

    def _evaluate_timeline_course_gap(
        self,
        *,
        medical_record: dict[str, Any],
        max_hours: int,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        timeline = self._get_programmatic_timeline(medical_record)
        if not timeline:
            return self._build_uncertain_timeline_result("缺少结构化时间轴，无法判断病程记录间隔。")
        risk_flags = {str(item).strip().lower() for item in list(timeline.get("risk_flags") or []) if str(item).strip()}
        if {"critical", "serious"} & risk_flags:
            return (
                "not_applicable",
                True,
                "病历被识别为病重/危重，本规则不适用。",
                f"risk_flags={','.join(sorted(risk_flags)) or 'unknown'}",
                "",
                0.9,
                {"is_applicable": False, "reason": "serious_or_critical", "method": "timeline_course_gap_guard"},
                "timeline",
            )
        events = self._collect_course_events(timeline)
        if len(events) < 2:
            return self._build_uncertain_timeline_result("病程/查房时间轴事件不足，无法判断是否超过 72 小时间隔。")
        previous_dt: Optional[datetime] = None
        previous_title = ""
        for event in events:
            authored_at = self._parse_datetime(str(event.get("authored_at") or ""))
            if authored_at is None:
                continue
            if previous_dt is not None:
                delta_hours = (authored_at - previous_dt).total_seconds() / 3600
                if delta_hours > max_hours:
                    evidence = (
                        f"前一条={previous_title or '病程/查房'}@{previous_dt.isoformat(sep=' ', timespec='seconds')}；"
                        f"后一条={str(event.get('title') or '')}@{authored_at.isoformat(sep=' ', timespec='seconds')}；"
                        f"间隔={delta_hours:.1f}h"
                    )
                    return (
                        "non_compliant",
                        False,
                        "存在超过 72 小时未完成病程/查房记录的区间。",
                        evidence,
                        "请按患者病情至少每 3 天补充 1 次病程或查房记录。",
                        0.92,
                        {"is_applicable": True, "reason": "", "method": "timeline_course_gap"},
                        "timeline",
                    )
            previous_dt = authored_at
            previous_title = str(event.get("title") or "")
        return (
            "compliant",
            True,
            "未发现超过 72 小时的病程/查房记录间隔。",
            f"已检查 {len(events)} 条病程/查房事件",
            "",
            0.9,
            {"is_applicable": True, "reason": "", "method": "timeline_course_gap"},
            "timeline",
        )

    def _evaluate_timeline_postop_course(
        self,
        *,
        medical_record: dict[str, Any],
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        timeline = self._get_programmatic_timeline(medical_record)
        if not timeline:
            return self._build_uncertain_timeline_result("缺少结构化时间轴，无法判断术后连续 3 天病程记录。")
        surgery_events = list((timeline.get("documents") or {}).get("surgery_record") or [])
        surgery_end_times = [
            self._parse_datetime(str(item.get("surgery_end_at") or item.get("authored_at") or ""))
            for item in surgery_events
        ]
        surgery_end_times = [item for item in surgery_end_times if item is not None]
        if not surgery_end_times:
            return self._build_uncertain_timeline_result("缺少手术结束时间，无法判断术后连续 3 天病程记录。")
        surgery_end = min(surgery_end_times)
        course_events = self._collect_course_events(timeline)
        coverage: dict[int, list[str]] = {1: [], 2: [], 3: []}
        for event in course_events:
            authored_at = self._parse_datetime(str(event.get("authored_at") or ""))
            if authored_at is None or authored_at <= surgery_end:
                continue
            delta_days = (authored_at.date() - surgery_end.date()).days
            if delta_days in coverage:
                coverage[delta_days].append(str(event.get("title") or "病程记录"))
        missing_days = [day for day, hits in coverage.items() if not hits]
        evidence = "；".join(
            f"术后第{day}天={'、'.join(hits) if hits else '缺失'}"
            for day, hits in coverage.items()
        )
        if missing_days:
            return (
                "non_compliant",
                False,
                f"术后第 {', '.join(str(day) for day in missing_days)} 天缺少病程/查房记录。",
                evidence,
                "请补充术后连续 3 天的病程或查房记录，确保每天至少 1 条。",
                0.92,
                {"is_applicable": True, "reason": "", "method": "timeline_postop_course"},
                "timeline",
            )
        return (
            "compliant",
            True,
            "术后连续 3 天病程/查房记录齐全。",
            evidence,
            "",
            0.92,
            {"is_applicable": True, "reason": "", "method": "timeline_postop_course"},
            "timeline",
        )

    def _build_uncertain_timeline_result(
        self,
        findings: str,
    ) -> tuple[str, bool, str, str, str, float, dict[str, Any], str]:
        return (
            "uncertain",
            False,
            findings,
            "缺少可复核的结构化时间轴证据",
            "请补齐 bundle 时间轴或相关结构化文书后重试。",
            0.55,
            {"is_applicable": True, "reason": "missing_programmatic_timeline", "method": "timeline_guard"},
            "timeline_missing",
        )

    def _get_programmatic_timeline(self, medical_record: dict[str, Any]) -> dict[str, Any]:
        evidence_payload = medical_record.get("evidence_payload")
        if isinstance(evidence_payload, dict):
            timeline = evidence_payload.get("programmatic_timeline")
            if isinstance(timeline, dict):
                return timeline
        timeline = medical_record.get("programmatic_timeline")
        return dict(timeline) if isinstance(timeline, dict) else {}

    def _collect_course_events(self, timeline: dict[str, Any]) -> list[dict[str, Any]]:
        documents = dict(timeline.get("documents") or {})
        events: list[dict[str, Any]] = []
        for key in ("first_course_record", "daily_course_record", "senior_course_record"):
            for raw_event in list(documents.get(key) or []):
                if not isinstance(raw_event, dict):
                    continue
                authored_at = self._parse_datetime(str(raw_event.get("authored_at") or ""))
                if authored_at is None:
                    continue
                event = dict(raw_event)
                event["authored_at"] = authored_at.isoformat(sep=" ", timespec="seconds")
                events.append(event)
        events.sort(key=lambda item: str(item.get("authored_at") or ""))
        return events

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
