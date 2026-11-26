"""00717/00718：住院超过48小时血尿常规结果及可核验门诊转抄。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Any, Mapping, Sequence

from .basic_timeliness_facts import (
    AdmissionAnchorState,
    extract_admission_anchor,
    parse_authoritative_datetime,
)
from .handbook_exam_lab import _FINAL_REPORT_STATES
from .source_evidence_reader import (
    ROUTINE_LAB_ITEM_SOURCE_KEY,
    authoritative_document_time_value,
)

ROUTINE_RULES = {"LX0609-06-03-05": "blood", "LX0609-06-03-06": "urine"}
ITEM_SOURCE = ROUTINE_LAB_ITEM_SOURCE_KEY
COURSE_SOURCES = (
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
)
SOURCE_KEYS = (
    "labtest_master",
    "labtest_item_report",
    ITEM_SOURCE,
    "inpat_registration",
    *COURSE_SOURCES,
    "evaluation_context.horizon",
)
OPTIONAL_ORDER_SOURCES = (
    "inpat_nondrug_order",
    "inpat_nondrug_order.exam_lab_order",
)
BLOOD_ITEMS = dict(
    zip(
        (f"AA{x:03}" for x in range(1, 25)),
        (
            "白细胞计数",
            "中性粒细胞百分数",
            "淋巴细胞百分数",
            "单核细胞百分数",
            "嗜酸性粒细胞百分数",
            "嗜碱性粒细胞百分数",
            "中性粒细胞绝对数",
            "淋巴细胞绝对数",
            "单核细胞绝对数",
            "嗜酸性粒细胞绝对数",
            "嗜碱性粒细胞绝对数",
            "红细胞计数",
            "血红蛋白",
            "红细胞比容",
            "平均红细胞体积",
            "平均红细胞血红蛋白量",
            "平均红细胞血红蛋白浓度",
            "红细胞体积分布宽度SD",
            "红细胞体积分布宽度CV",
            "血小板计数",
            "平均血小板体积",
            "血小板比容",
            "血小板体积分布宽度",
            "大型血小板比率",
        ),
    )
)
URINE_ITEMS = dict(
    zip(
        (f"AA{x:03}" for x in range(81, 91)),
        (
            "白细胞",
            "酮体定性",
            "亚硝酸盐",
            "尿胆原定性",
            "尿胆红素定性",
            "尿葡萄糖",
            "尿比重",
            "隐血",
            "尿蛋白定性",
            "酸碱度",
        ),
    )
)
_PENDING = re.compile(
    r"待|未(?:完成|审核|发布)|初步|取消|撤销|作废|pending|preliminary|cancel", re.I
)
_CANCELLED_ORDER = re.compile(r"撤销|取消|作废|cancel", re.I)
_LAB_ORDER_CLASS = re.compile(r"检验|\blab(?:oratory)?\b", re.I)
_LAB_ORDER_NAME = re.compile(
    r"血常规|尿常规|尿液分析|尿沉渣|大便常规|粪常规|"
    r"(?:细菌|真菌|血|痰|尿|分泌物|大便|腹水|胸水|灌洗液|结核菌)?培养|药敏|"
    r"血气分析|肝功|肾功|生化|电解质|凝血|降钙素原|C反应蛋白|CRP",
    re.I,
)
_NUMBER = re.compile(r"^[<>≤≥]?\s*[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?%?$")
_QUALITATIVE = frozenset(
    {
        "阴性",
        "阳性",
        "弱阳性",
        "阴性(-)",
        "阴性（-）",
        "阳性(+)",
        "阳性（+）",
        "-",
        "±",
        "+-",
        "+",
        "++",
        "+++",
        "++++",
    }
)
_DATE = re.compile(r"(?<!\d)(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})(?:日)?(?!\d)")
_COPY_RESULT = {
    "blood": re.compile(
        r"(?:白细胞(?:计数)?|红细胞(?:计数)?|血红蛋白|血小板(?:计数)?|WBC|RBC|HGB|Hb|PLT)\s*[:：=]?\s*[<>≤≥]?\s*\d+(?:\.\d+)?",
        re.I,
    ),
    "urine": re.compile(
        r"(?:尿蛋白|尿糖|尿葡萄糖|尿比重|酸碱度|隐血|潜血|亚硝酸盐|白细胞|酮体|尿胆原|尿胆红素)\s*[:：=]?\s*(?:[<>≤≥]?\d+(?:\.\d+)?|阴性|阳性|弱阳性|[（(]?[+±-]{1,4}[)）]?)"
    ),
}


@dataclass(frozen=True)
class RoutineLabOutcome:
    status: str
    reason: str
    facts: Mapping[str, Any] | None = None
    refs: tuple[str, ...] = ()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _item_name(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).lstrip("*＊")


def _is_active_lab_order(row: Mapping[str, Any]) -> bool:
    """识别有效检验类非药医嘱，排除已撤销/取消及纯影像/治疗/护理医嘱。"""
    if row.get("validation_material_state") in {"held", "version_review"}:
        return False
    if _CANCELLED_ORDER.search(_text(row.get("order_status"))):
        return False
    for field in ("order_type", "order_class"):
        if _LAB_ORDER_CLASS.search(_text(row.get(field))):
            return True
    return bool(_LAB_ORDER_NAME.search(_text(row.get("order_name"))))


def _has_active_lab_orders(
    sources: Mapping[str, Sequence[tuple[str, Mapping[str, Any]]]],
) -> bool:
    for source_key in OPTIONAL_ORDER_SOURCES:
        for _, row in sources.get(source_key, ()):
            if isinstance(row, Mapping) and _is_active_lab_order(row):
                return True
    return False


def _gap(reason: str) -> RoutineLabOutcome:
    return RoutineLabOutcome("data_gap", reason)


def _has_result(panel: str, value: Any) -> bool:
    text = _text(value).replace("－", "-")
    # 本院尿常规将尿胆原结果记作 Normal、弱阳性记作 +-；二者是结果值，
    # 不等同于病程中笼统描述“尿常规正常”，也不放宽血常规数值要求。
    return bool(
        _NUMBER.fullmatch(text)
        or (panel == "urine" and (text in _QUALITATIVE or text.lower() == "normal"))
    )


def _pending(row: Mapping[str, Any]) -> bool:
    if row.get("validation_material_state") in {"held", "version_review"}:
        return True
    for key in ("labtest_result_status", "report_status"):
        state = _text(row.get(key)).lower()
        if state and state not in _FINAL_REPORT_STATES:
            return True
    state = _text(row.get("document_status")).lower()
    return bool(
        state
        and (
            bool(_PENDING.search(state))
            or state
            not in {
                *_FINAL_REPORT_STATES,
                "有效",
                "正常",
                "已签名",
                "已提交",
                "正式",
                "active",
                "signed",
            }
        )
    )


def _copy_result_count(panel: str, text: str) -> int:
    """只接受目标项目下连续的结果项，遇到其他项目/语境即停止。"""
    count = 0
    for part in re.split(r"[，,]", text):
        part = _DATE.sub("", part).strip()
        match = _COPY_RESULT[panel].search(part)
        prefix = part[: match.start()] if match else part
        prefix = re.sub(
            r"检验日期|检查|检验|检测|报告|结果|提示|显示|复查|日期|示|为|于",
            "",
            prefix,
        )
        prefix = prefix.strip(" \t:：=()（）[]【】")
        if match and not prefix:
            count += 1
            continue
        if not match and prefix in {
            "",
            "正常",
            "已查",
            "无异常",
            "未见异常",
            "未见明显异常",
        }:
            continue
        break
    return count


def evaluate_routine_lab_presence(
    *,
    rule_id: str,
    sources: Mapping[str, Sequence[tuple[str, Mapping[str, Any]]]],
    source_error: str = "",
) -> RoutineLabOutcome:
    """只消费同一已证明完整的快照；按真实test_id分组，不调用模型。"""
    if source_error:
        return _gap(source_error)
    panel = ROUTINE_RULES[rule_id]
    required = BLOOD_ITEMS if panel == "blood" else URINE_ITEMS
    anchor = extract_admission_anchor(
        registration_rows=[r for _, r in sources.get("inpat_registration", ())],
        admission_rows=[r for _, r in sources.get("admission_record", ())],
        discharge_rows=(),
        allow_date_fallback=False,
    )
    if anchor.state is not AdmissionAnchorState.EXACT:
        return _gap(
            "authoritative_time_conflict"
            if anchor.state is AdmissionAnchorState.CONFLICT
            else "authoritative_time_missing"
        )
    start = anchor.anchor_time
    horizons = sources.get("evaluation_context.horizon", ())
    if len(horizons) != 1:
        return _gap(
            "authoritative_time_missing"
            if not horizons
            else "authoritative_time_conflict"
        )
    horizon = horizons[0][1]
    if horizon.get("basis") not in {"discharge_date", "evaluation_as_of"}:
        return _gap("authoritative_time_missing")
    raw_end = horizon.get("horizon_datetime")
    end = parse_authoritative_datetime(raw_end)
    if _text(raw_end) and end is None:
        return _gap("authoritative_time_missing")
    try:
        end_date = (
            date.fromisoformat(str(horizon.get("horizon_date")))
            if horizon.get("horizon_date")
            else None
        )
    except ValueError:
        return _gap("authoritative_time_missing")
    if end is not None:
        if end_date and end.date() != end_date:
            return _gap("authoritative_time_conflict")
        end_date = end.date()
        lower = upper = end
    elif end_date is not None:
        lower = datetime.combine(end_date, datetime.min.time())
        upper = lower + timedelta(days=1) - timedelta(microseconds=1)
    else:
        return _gap("authoritative_time_missing")
    if upper < start:
        return _gap("authoritative_time_conflict")
    facts = {
        "verification_kind": "routine_lab_presence_check",
        "panel": panel,
        "minimum_stay_hours": 48,
        "admission_time": start.isoformat(sep=" "),
        "evaluation_time": end.isoformat(sep=" ") if end else None,
        "evaluation_date": end_date.isoformat(),
        "evidence_kind": "none",
        "report_time": None,
        "report_date": None,
        "matched_item_count": 0,
        "required_item_count": len(required),
    }
    if upper - start <= timedelta(hours=48):
        return RoutineLabOutcome("not_applicable", "trigger_absent_complete", facts)
    if lower - start <= timedelta(hours=48):
        return _gap("authoritative_time_missing")

    masters: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    items: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    unresolved = False
    for ref, row in sources.get("labtest_master", ()):
        key = _text(row.get("test_id"))
        if key:
            masters.setdefault(key, []).append((ref, row))
        else:
            unresolved = True
    for ref, row in sources.get(ITEM_SOURCE, ()):
        key = _text(row.get("test_id"))
        if key:
            items.setdefault(key, []).append((ref, row))
        else:
            unresolved = True
    candidates = []
    for key, main_rows in masters.items():
        report_rows = items.get(key, [])
        if not report_rows:
            unresolved = True
            continue
        matched = {
            _text(row.get("item_code")) for _, row in report_rows
        } & required.keys()
        if not matched:
            continue
        if len(main_rows) != 1:
            unresolved = True
            continue
        main_ref, main = main_rows[0]
        if _pending(main):
            unresolved = True
            continue
        moment = parse_authoritative_datetime(main.get("report_datetime"))
        if moment is None:
            unresolved = True
            continue
        if moment > upper:
            continue
        if moment < start or moment > lower or matched != required.keys():
            unresolved = True
            continue
        by_code = {
            code: [
                (ref, row)
                for ref, row in report_rows
                if _text(row.get("item_code")) == code
            ]
            for code in required
        }
        good = True
        for code, entries in by_code.items():
            values = set()
            for _, row in entries:
                clock = parse_authoritative_datetime(
                    row.get("report_time") or row.get("report_datetime")
                )
                if (
                    _item_name(row.get("item_name") or row.get("lab_item_name"))
                    != required[code]
                    or not _has_result(panel, row.get("result"))
                    or _pending(row)
                    or clock != moment
                ):
                    good = False
                    break
                values.add(_text(row.get("result")))
            if len(values) != 1:
                good = False
        if not good:
            unresolved = True
            continue
        refs = tuple(dict.fromkeys((main_ref, *(ref for ref, _ in report_rows))))
        if len(refs) > 128:
            unresolved = True
            continue
        candidates.append((moment, key, refs))
    if candidates:
        moment, _, refs = min(candidates, key=lambda item: (item[0], item[1]))
        return RoutineLabOutcome(
            "compliant",
            "requirement_satisfied",
            {
                **facts,
                "evidence_kind": "inpatient_report",
                "report_time": moment.isoformat(sep=" "),
                "report_date": moment.date().isoformat(),
                "matched_item_count": len(required),
            },
            refs,
        )
    if any(key not in masters for key in items):
        unresolved = True

    label = "血常规" if panel == "blood" else "尿常规"
    copies = []
    for source in COURSE_SOURCES:
        for ref, row in sources.get(source, ()):
            if row.get("validation_material_state") in {"held", "version_review"}:
                continue
            body = _text(row.get("record_content"))
            for clause in re.split(r"[。；;\n\r]+", body):
                if label not in clause or "门诊" not in clause:
                    continue
                # 门诊来源仅约束同一语境的结果，不能借用逗号后住院/复查的新结果。
                outpatient_position = clause.index("门诊")
                current_context = re.search(
                    r"入院|住院|本次|此次|今日|今晨|现复查",
                    clause[outpatient_position + 2 :],
                )
                if current_context:
                    clause = clause[: outpatient_position + 2 + current_context.start()]
                if label not in clause:
                    unresolved = True
                    continue
                if re.search(r"拟|计划|建议|待查|未查|未在门诊|否认|复查计划", clause):
                    continue
                matched_count = _copy_result_count(
                    panel, clause[clause.index(label) + len(label) :]
                )
                if not matched_count:
                    unresolved = True
                    continue
                dates = []
                for match in _DATE.finditer(clause):
                    try:
                        dates.append(date(*map(int, match.groups())))
                    except ValueError:
                        pass
                doc_clock = parse_authoritative_datetime(
                    authoritative_document_time_value(row)
                )
                document_id = _text(row.get("document_id"))
                if (
                    len(set(dates)) != 1
                    or doc_clock is None
                    or not start <= doc_clock <= lower
                    or dates[0] > start.date()
                    or not document_id
                    or _pending(row)
                ):
                    unresolved = True
                    continue
                if any(
                    _text(other.get("document_id")) == document_id
                    and dict(other) != dict(row)
                    for _, other in sources.get(source, ())
                ):
                    unresolved = True
                    continue
                copies.append((doc_clock, ref, dates[0], matched_count))
    if copies:
        _, ref, report_date, count = min(copies, key=lambda item: (item[0], item[1]))
        return RoutineLabOutcome(
            "compliant",
            "requirement_satisfied",
            {
                **facts,
                "evidence_kind": "outpatient_transcription",
                "report_date": report_date.isoformat(),
                "matched_item_count": count,
            },
            (ref,),
        )
    if unresolved:
        return _gap("required_field_missing")
    # 检验主表与明细均为空但本次住院存在有效检验医嘱（血常规/尿液分析/培养等）时，
    # 说明检验报告数据源未同步，降级资料缺口而非误判临床未查。
    if (
        not sources.get("labtest_master")
        and not sources.get(ITEM_SOURCE)
        and not sources.get("labtest_item_report")
        and _has_active_lab_orders(sources)
    ):
        return _gap("source_empty")
    return RoutineLabOutcome("non_compliant", "required_document_missing", facts)


def safe_routine_lab_facts(rule_id: str, raw: Any) -> dict[str, Any] | None:
    """公开层只校验字段/类型，不重新判断完整组合或48小时。"""
    keys = {
        "verification_kind",
        "panel",
        "minimum_stay_hours",
        "admission_time",
        "evaluation_time",
        "evaluation_date",
        "evidence_kind",
        "report_time",
        "report_date",
        "matched_item_count",
        "required_item_count",
    }
    if (
        not isinstance(raw, Mapping)
        or set(raw) != keys
        or raw.get("verification_kind") != "routine_lab_presence_check"
        or raw.get("panel") != ROUTINE_RULES[rule_id]
        or type(raw.get("minimum_stay_hours")) is not int
        or raw["minimum_stay_hours"] != 48
        or raw.get("evidence_kind")
        not in {"none", "inpatient_report", "outpatient_transcription"}
    ):
        return None
    for key in ("admission_time", "evaluation_time", "report_time"):
        value = raw[key]
        if value is None and key != "admission_time":
            continue
        if type(value) is not str or parse_authoritative_datetime(value) is None:
            return None
    for key in ("evaluation_date", "report_date"):
        value = raw[key]
        if value is None and key == "report_date":
            continue
        try:
            if type(value) is not str or date.fromisoformat(value).isoformat() != value:
                return None
        except ValueError:
            return None
    if any(
        type(raw[key]) is not int or not 0 <= raw[key] <= 100
        for key in ("matched_item_count", "required_item_count")
    ):
        return None
    return dict(raw)


def routine_lab_decision(rule_id, outcome, snapshot):
    """把本规则已裁决状态写入标准Decision，保留准确来源错误原因。"""
    from .decision_model import (
        ApplicabilityState,
        EvidenceState,
        QcDirection,
        RuleDecision,
    )

    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
        ),
    }
    applicability, evidence, direction = dimensions[outcome.status]
    refs = outcome.refs or tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in SOURCE_KEYS
    )
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence,
        qc_direction=direction,
        reason_code=outcome.reason,
        fact_refs=refs,
        evaluator_version="routine-lab-presence-v1",
        confidence=None,
    )
