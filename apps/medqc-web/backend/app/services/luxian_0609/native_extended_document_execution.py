"""第一阶段新增的确定性文书规则。

本执行器只消费同一个 Evidence Snapshot/Material Store，不调用旧四川规则，
也不从自由文本结论反推状态。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .extended_document.death_discussion import (
    evaluate_death_discussion_timeliness,
)
from .extended_document.consultation_timeliness import (
    evaluate_consultation_timeliness,
)
from .extended_document.discharge_documentation import (
    evaluate_discharge_documentation_timeliness,
)
from .extended_document.discharge_course import (
    evaluate_predischarge_course_presence,
)
from .extended_document.physician_handoff import evaluate_physician_handoff
from .extended_document.shared import _clean, _parse_datetime, _row_time
from .extended_document.transfer_documentation import (
    evaluate_transfer_documentation,
)
from .extended_document_critical_value import (
    CRITICAL_VALUE_RULE_IDS,
    CRITICAL_VALUE_SOURCE_KEYS,
    CriticalValueDisposition,
    CriticalValueInput,
    CriticalValueItem,
    evaluate_critical_value_rules,
)
from .source_evidence_reader import (
    parse_strict_performed_time,
    trusted_performed_surgery_times,
)
from .native_transfusion_execution import evaluate_pretransfusion_nine_items
from .surgery_applicability import (
    SurgeryApplicability,
    resolve_surgery_applicability,
)
from .surgery_procedure_catalog import catalog_surgery_state


EXECUTOR_KEY = "extended_document"
EXTENDED_DOCUMENT_RULE_IDS = (
    "LX0609-050",
    "LX0609-051",
    "LX0609-052",
    "LX0609-053",
    "LX0609-054",
    "LX0609-055",
    "LX0609-056",
    "LX0609-057",
    "LX0609-058",
    "LX0609-059",
    "LX0609-060",
    "LX0609-061",
    "LX0609-062",
    "LX0609-063",
    "LX0609-064",
    "LX0609-065",
    "LX0609-066",
    "LX0609-067",
    "LX0609-068",
    "LX0609-069",
    "LX0609-070",
    "LX0609-071",
    "LX0609-072",
    "LX0609-073",
    "LX0609-074",
    "LX0609-075",
)

EXTENDED_DOCUMENT_SOURCE_KEYS = (
    "inpat_registration",
    "admission_record",
    "death_record",
    "death_discussion",
    "discharge_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "mr_surgery",
    "surgery_record",
    "consultation_record",
    "handoff_record",
    "handover_record",
    "physician_change_event",
    "transfer_in_record",
    "transfer_out_record",
    "inpat_nondrug_order",
    "diagnosis",
    "diffcase_discussion_record",
    "crisis_value_record",
    "labtest_item_report",
    "labtest_master",
    "inpat_drug_order",
    "discharge_record_diagnosis",
    "mr_bloodtrans",
    "bloodtrans_record",
)

_DEATH_MARKERS = ("死亡", "病故")
_ALIVE_DISCHARGE_MARKERS = ("出院", "转院", "医嘱离院", "非医嘱离院")
_UNCERTAIN_DIAGNOSIS_MARKERS = ("诊断仍不明确", "诊断不明确")
_LOCAL_DIAGNOSIS_UNCERTAINTY_MARKERS = ("原因待查", "性质待定")
_DISCHARGE_MEDICATION_SIGNAL_PATTERN = re.compile(
    r"(?:药品|药物|用药|服药|服用|口服|停药|带药)"
)
_SPECIAL_ANTIMICROBIALS = (
    "头孢他啶/阿维巴坦", "头孢吡肟", "氨曲南", "美罗培南",
    "亚胺培南", "万古霉素", "伏立康唑",
)
_ANTIMICROBIALS = _SPECIAL_ANTIMICROBIALS + (
    "阿莫西林", "舒他西林", "青霉素", "苯唑西林", "哌拉西林",
    "头孢唑林", "头孢曲松", "头孢他啶", "头孢西丁", "厄他培南",
    "阿米卡星", "阿奇霉素", "莫西沙星", "左氧氟沙星", "环丙沙星",
    "甲硝唑", "替硝唑", "奥硝唑", "克林霉素", "氟康唑",
)
_ANTIMICROBIAL_EFFECT_EVALUATION_OUTCOMES = (
    "有效", "好转", "改善", "感染控制", "疗效不佳", "效果不佳",
    "无改善", "未改善", "无效", "治疗失败", "感染未控制", "病情加重",
    "恶化", "调整方案", "更换抗菌药", "升级抗菌药", "降阶梯", "停用",
)
_ANTIMICROBIAL_EFFECT_CONTEXT_MARKERS = ("抗菌", "抗感染", "抗生素")
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS = (
    "感染专家", "专家会诊", "专家查房", "同意特殊级",
)
_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN = re.compile(
    r"(?:拒绝|不同意|未(?:行|完成|进行)|尚未|无).{0,12}"
    r"(?:感染专家|专家会诊|专家查房|会诊意见)|"
    r"(?:感染专家|专家会诊|专家查房|会诊意见).{0,12}"
    r"(?:未(?:行|完成|进行)|尚未|缺失|不存在|无)",
)
_INVASIVE_PROCEDURES = (
    "中心静脉置管", "胸腔穿刺", "腹腔穿刺", "腰椎穿刺",
    "气管插管", "支气管镜", "动脉置管",
)
_DISCHARGE_APPROVAL_PATTERN = re.compile(
    r"(?:同意|准予|可以)(?:患者)?(?:于|拟于)?"
    r"(?:今日|明日|次日)?(?:办理)?出院"
)
_DISCHARGE_APPROVAL_NEGATED_PATTERN = re.compile(
    r"(?:不|未|未获|未取得|未得到|尚未|尚不|暂不).{0,12}"
    r"(?:同意|准予|可以).{0,8}出院"
)
_SENIOR_PHYSICIAN_REFERENCE_PATTERN = re.compile(
    r"(?:上级医师|上级医生|主治医师|副主任医师|主任医师|[\u4e00-\u9fff]{1,4}(?:主任|主治))"
)
_AUTOMATIC_DISCHARGE_PATTERN = re.compile(r"自动出院")
_SENIOR_PHYSICIAN_CONSULTED_PATTERN = re.compile(
    r"(?:请示|报请|报告).{0,12}"
    r"(?:上级医师|上级医生|主治医师|副主任医师|主任医师|[\u4e00-\u9fff]{1,4}(?:主任|主治))"
)
_AUTOMATIC_DISCHARGE_SIGNED_PATTERN = re.compile(
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书)[》\"”]?"
)
_AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN = re.compile(
    r"(?:未|未予|尚未|拒绝|拒不).{0,8}"
    r"(?:签署|签订|签字|签)[《\"“]?自动出院(?:书|协议|知情同意书)"
)


def _critical_value_event_key(
    source_key: str,
    row: Mapping[str, Any],
) -> str | None:
    """按来源选择可跨表证明的危急值事件键，不把处置文书自身 ID 当关联键。"""

    fields = (
        ("report_id", "test_id", "document_id")
        if source_key == "labtest_item_report"
        else ("report_id", "test_id")
        if source_key == "crisis_value_record"
        else ()
    )
    for field in fields:
        value = _clean(row.get(field))
        if value:
            return f"{field}:{value}"
    return None


def _discharge_approval_path(
    row: Mapping[str, Any],
    *,
    source_key: str,
) -> str | None:
    text = _row_text(row)
    if not text:
        return None

    if (
        _AUTOMATIC_DISCHARGE_PATTERN.search(text)
        and _SENIOR_PHYSICIAN_CONSULTED_PATTERN.search(text)
        and _AUTOMATIC_DISCHARGE_SIGNED_PATTERN.search(text)
        and not _AUTOMATIC_DISCHARGE_UNSIGNED_PATTERN.search(text)
    ):
        return "automatic_discharge"

    approval = _DISCHARGE_APPROVAL_PATTERN.search(text)
    if approval is None:
        return None
    local_context = text[max(0, approval.start() - 80): approval.end() + 40]
    if _DISCHARGE_APPROVAL_NEGATED_PATTERN.search(local_context):
        return None
    author_title = _clean(row.get("author_title"))
    if (
        source_key == "senior_course_record"
        or _SENIOR_PHYSICIAN_REFERENCE_PATTERN.search(local_context)
        or _SENIOR_PHYSICIAN_REFERENCE_PATTERN.search(author_title)
    ):
        return "senior_approval"
    return None


def _source_rows(
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return (), "source_truncated"
    except EvidenceMaterialUnavailable:
        return (), "source_unavailable"
    return tuple(dict(row) for row in rows), ""


def _fact_refs(
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
) -> tuple[str, ...]:
    wanted = set(source_keys)
    return tuple(
        sorted(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key in wanted
        )
    )


def _decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
    final_state: str,
    reason_code: str,
) -> RuleDecision:
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
    applicability, evidence_state, direction = dimensions[final_state]
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=reason_code,
        fact_refs=_fact_refs(snapshot, source_keys),
        evaluator_version="extended-document-v2",
        confidence=None,
    )


def _registration_status(rows: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(
        _clean(
            row.get("patient_status")
            or row.get("discharge_status")
            or row.get("discharge_type")
        )
        for row in rows
    )


def _death_context(
    *,
    registration_rows: Sequence[Mapping[str, Any]],
    death_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, datetime | None]:
    explicit_death_times = {
        candidate
        for row in (*death_rows, *registration_rows)
        if (
            candidate := _parse_datetime(
                row.get("death_datetime") or row.get("death_time")
            )
        )
        is not None
    }
    if len(explicit_death_times) > 1:
        return "conflict", None

    if death_rows:
        # 文书 record_time/submit_time 只表示记录完成时间，不能替代实际死亡时间。
        # 死亡记录存在仍足以确认死亡状态；时限规则会因缺少死亡时刻而数据缺口关闭。
        return "present", next(iter(explicit_death_times), None)

    status = _registration_status(registration_rows)
    death_time = next(iter(explicit_death_times), None)
    if death_time is not None or any(marker in status for marker in _DEATH_MARKERS):
        return "present", death_time
    if (
        status and any(marker in status for marker in _ALIVE_DISCHARGE_MARKERS)
    ) or discharge_rows:
        return "absent", None
    return "unknown", None


def _discharge_time(
    registration_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
) -> datetime | None:
    for row in registration_rows:
        parsed = _parse_datetime(row.get("discharge_datetime") or row.get("discharge_time"))
        if parsed is not None:
            return parsed
    for row in discharge_rows:
        parsed = _parse_datetime(
            row.get("discharge_datetime")
            or row.get("discharge_time")
            or row.get("discharge_date")
        )
        if parsed is not None:
            return parsed
    return None


def _row_text(row: Mapping[str, Any]) -> str:
    return "\n".join(
        _clean(row.get(key))
        for key in ("record_content", "discharge_order", "document_title")
        if _clean(row.get(key))
    )


def _material_text(row: Mapping[str, Any]) -> str:
    return "\n".join(
        _clean(row.get(key))
        for key in (
            "record_content", "document_title", "order_name", "generic_name",
            "item_code", "item_name", "item_abbreviation", "result",
            "result_flag", "abnormal_flag", "diagnosis_name", "labtest_subject",
            "specimen",
        )
        if _clean(row.get(key))
    )


def _antimicrobial_orders(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        row for row in rows if any(name in _material_text(row) for name in _ANTIMICROBIALS)
    )


def _antimicrobial_names_in(
    row: Mapping[str, Any], names: Sequence[str] = _ANTIMICROBIALS
) -> tuple[str, ...]:
    text = _material_text(row)
    return tuple(name for name in names if name in text)


def _is_antimicrobial_effect_evaluation(row: Mapping[str, Any]) -> bool:
    """只接受明确治疗评价，不以单独的检验趋势替代病程评价。"""

    text = _material_text(row)
    has_outcome = any(
        marker in text for marker in _ANTIMICROBIAL_EFFECT_EVALUATION_OUTCOMES
    )
    if not has_outcome:
        return False
    has_antimicrobial_context = any(
        marker in text for marker in _ANTIMICROBIAL_EFFECT_CONTEXT_MARKERS
    ) or any(name in text for name in _ANTIMICROBIALS)
    # “治疗效果/疗效评价”本身可能描述镇痛、补液等非抗菌治疗；必须同时
    # 出现抗菌/抗感染语境或具体抗菌药名，才能作为本规则的疗效评价。
    return has_antimicrobial_context


def _is_special_antimicrobial_expert_support(row: Mapping[str, Any]) -> bool:
    """排除明确拒绝/未完成的会诊文字，避免否定句充当支持证据。"""

    text = _material_text(row)
    return (
        _has_any_text((row,), _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
        and not _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_NEGATED_PATTERN.search(text)
    )


def _has_any_text(rows: Sequence[Mapping[str, Any]], markers: Sequence[str]) -> bool:
    return any(any(marker in _material_text(row) for marker in markers) for row in rows)


def _documented_antimicrobial_names(
    rows: Sequence[Mapping[str, Any]],
    antimicrobial_names: Sequence[str],
) -> tuple[str, ...]:
    """同一病程必须同时出现药物、用药动作和临床理由，禁止仅凭“启用”通过。"""

    actions = ("使用", "启用", "停用", "更换", "联合", "超说明书")
    reasons = (
        "因为", "由于", "考虑", "依据", "理由", "重症感染", "覆盖",
        "培养", "药敏", "感染证据", "无样可采",
    )
    return tuple(
        name
        for name in antimicrobial_names
        if any(
            name in (text := _material_text(row))
            and any(action in text for action in actions)
            and any(reason in text for reason in reasons)
            for row in rows
        )
    )


def _linked_order_id(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("related_order_id")
        or row.get("source_order_id")
        or row.get("order_id")
    )


def _repeated_antimicrobial_association_failed(
    order_rows: Sequence[Mapping[str, Any]],
    course_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """同药重复事件必须逐医嘱显式关联，不能复用一份泛化病程。"""

    for name in _ANTIMICROBIALS:
        matching_orders = tuple(
            row for row in order_rows if name in _material_text(row)
        )
        if len(matching_orders) < 2:
            continue
        order_ids = tuple(_clean(row.get("order_id")) for row in matching_orders)
        if not all(order_ids) or len(set(order_ids)) != len(order_ids):
            return True
        if any(
            name not in _documented_antimicrobial_names(
                tuple(row for row in course_rows if _linked_order_id(row) == order_id),
                (name,),
            )
            for order_id in order_ids
        ):
            return True
    return False


def _diagnosis_sequence(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    ordered = sorted(
        (
            int(row.get("diagnosis_no") or 9999),
            _clean(row.get("diagnosis_name") or row.get("diagnosis")),
        )
        for row in rows
        if _clean(row.get("diagnosis_name") or row.get("diagnosis"))
    )
    return tuple(name for _position, name in ordered)


def _structured_discharge_medications(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]] | None, str]:
    for row in rows:
        value = row.get("discharge_medications")
        if value is None:
            continue
        if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
            return list(value), ""
        return None, "required_field_missing"
    has_discharge_instruction = False
    has_medication_signal = False
    for row in rows:
        value = _clean(row.get("discharge_order"))
        if not value:
            continue
        has_discharge_instruction = True
        has_medication_signal = (
            has_medication_signal
            or _DISCHARGE_MEDICATION_SIGNAL_PATTERN.search(value) is not None
        )
        labels = {
            "drug_name": "药品名称",
            "dose": "用药剂量",
            "route": "给药途径",
            "duration": "用药时间",
        }
        parsed: dict[str, str] = {}
        for key, marker in labels.items():
            match = re.search(rf"{marker}\s*[:：]\s*([^；;]+)", value)
            if match:
                parsed[key] = match.group(1).strip()
        if parsed:
            return [parsed], ""
    if has_discharge_instruction and not has_medication_signal:
        return [], ""
    return None, "required_field_missing"


def _course_dates(
    rows: Sequence[Mapping[str, Any]],
) -> set:
    return {
        parsed.date()
        for row in rows
        if (parsed := _row_time(row)) is not None
    }


def _qualified_surgery_rows(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    return (
        tuple(
            row
            for row in mr_surgery_rows
            if catalog_surgery_state(row) is not False
        ),
        tuple(
            row
            for row in surgery_record_rows
            if catalog_surgery_state(row) is not False
        ),
    )


def _surgery_applicability_outcome(
    applicability: SurgeryApplicability,
) -> tuple[str, str] | None:
    """将规则族共用门控投影为扩展文书执行器的受控状态。"""

    if applicability.state == "applicable":
        return None
    if applicability.state == "not_applicable":
        return "not_applicable", "performed_event_absent"
    if applicability.state == "technical_error":
        return "technical_error", applicability.reason_code
    return "data_gap", applicability.reason_code


def _performed_surgery_times(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[datetime, ...]:
    values: list[datetime] = []
    qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    for source_key, rows in (
        ("mr_surgery", qualified_mr_rows),
        ("surgery_record", qualified_record_rows),
    ):
        for row in rows:
            values.extend(
                parsed
                for value in trusted_performed_surgery_times(
                    source_key=source_key, row=row
                )
                if (parsed := _parse_datetime(value)) is not None
            )
    return tuple(sorted(set(values)))


def _performed_surgery_event_count(
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> int:
    """按权威手术主表优先计数，避免把同台手术的开始/结束时间算成两台。"""

    qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    # 正式手术记录是一台手术事件的主依据；mr_surgery 是操作目录补充，
    # 同一台手术可包含多行操作，不能在正式记录存在时用它虚增台次。
    authoritative_rows = qualified_record_rows or qualified_mr_rows
    source_key = "surgery_record" if qualified_record_rows else "mr_surgery"
    return sum(
        1
        for row in authoritative_rows
        if trusted_performed_surgery_times(source_key=source_key, row=row)
    )


@dataclass(frozen=True)
class _PostoperativeSurgeryEvent:
    """064/065 的最小事件投影：正式手术记录一行即一台手术。"""

    source_key: str
    document_id: str
    surgery_name: str
    surgery_end_time: datetime | None
    surgeon_names: tuple[str, ...]
    surgeon_tokens: frozenset[str]


_PHYSICIAN_TITLE_SUFFIXES = (
    "副主任医师",
    "主任医师",
    "主治医师",
    "住院医师",
    "医师",
)
_TITLE_ROUND_MARKER_PATTERN = re.compile(r"(?:查房|巡诊)")
_TITLE_ROUND_ROLE_DESCRIPTION_PATTERN = re.compile(
    r"(?:术者\s*[:：]|手术由[^，,；;。]*完成)"
)
_MASKED_PHYSICIAN_IDENTITY_PATTERN = re.compile(r"(?:某|匿名|脱敏|[*＊×])")


def _normalized_physician_token(value: Any) -> str:
    token = re.sub(r"\s+", "", _clean(value)).lower()
    for suffix in _PHYSICIAN_TITLE_SUFFIXES:
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return token


def _physician_identity_is_masked(value: Any) -> bool:
    """脱敏姓名不能用于证明或否定术者与查房医师是同一人。"""

    return bool(_MASKED_PHYSICIAN_IDENTITY_PATTERN.search(_clean(value)))


def _surgery_event_surgeon_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """正式手术事件只接受术者专属字段，不能把文书作者当作术者。"""

    return frozenset(
        token
        for key in (
            "surgeon",
            "surgeon_sign",
            "main_surgery_sign",
        )
        if (token := _normalized_physician_token(row.get(key)))
    )


def _surgery_event_surgeon_names(row: Mapping[str, Any]) -> tuple[str, ...]:
    """保留术者专属字段中的客户可读姓名，不展示标准化匹配 token。"""

    names: list[str] = []
    for key in ("surgeon", "surgeon_sign", "main_surgery_sign"):
        name = _clean(row.get(key))
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _course_record_physician_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    """病程记录仅从受控的作者或签名字段获取记录医师。"""

    return frozenset(
        token
        for key in (
            "author_name",
            "physician_sign",
            "author_signature",
            "doctor_signature",
        )
        if (token := _normalized_physician_token(row.get(key)))
    )


def _title_round_physician_tokens(
    row: Mapping[str, Any],
    *,
    candidate_tokens: frozenset[str],
) -> frozenset[str]:
    """仅确认查房标题中、查房标记前明确列出的当前术者。"""

    title = _clean(row.get("document_title"))
    marker = _TITLE_ROUND_MARKER_PATTERN.search(title)
    if marker is None:
        return frozenset()
    title_header = title[: marker.start()]
    # 标题中的角色说明（如“手术由…完成”）不构成查房医师名单；
    # 不从正文、科室或查房标记后的附注反向推断术者。
    if _TITLE_ROUND_ROLE_DESCRIPTION_PATTERN.search(title_header):
        return frozenset()
    return frozenset(
        token
        for token in candidate_tokens
        if token
        and re.search(
            rf"{re.escape(token)}(?:副主任医师|主任医师|主治医师|住院医师|医师)",
            title_header,
        )
    )


def _actual_surgery_end_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """术后规则只能读取实际结束字段；不得回退到申请或文书时间。"""

    for field in ("surgery_end_time", "surgery_end_datetime"):
        value = row.get(field)
        if source_key == "surgery_record":
            if (parsed := parse_strict_performed_time(value)) is not None:
                return parsed
        elif source_key == "mr_surgery" and isinstance(value, datetime) and value.tzinfo is None:
            return value
    return None


def _postoperative_surgery_events(
    *,
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    surgery_record_rows: Sequence[Mapping[str, Any]],
) -> tuple[_PostoperativeSurgeryEvent, ...]:
    """正式手术记录优先；仅在正式记录缺失时兼容既有 mr_surgery 触发。"""

    _qualified_mr_rows, qualified_record_rows = _qualified_surgery_rows(
        mr_surgery_rows, surgery_record_rows
    )
    source_key = "surgery_record" if qualified_record_rows else "mr_surgery"
    source_rows = qualified_record_rows if qualified_record_rows else _qualified_mr_rows
    return tuple(
        _PostoperativeSurgeryEvent(
            source_key=source_key,
            document_id=_clean(row.get("document_id") or row.get("id")) or f"{source_key}:{index}",
            surgery_name=_clean(
                row.get("surgery_name")
                or row.get("operation_name")
                or row.get("procedure_name")
            ),
            surgery_end_time=_actual_surgery_end_time(source_key=source_key, row=row),
            surgeon_names=_surgery_event_surgeon_names(row),
            surgeon_tokens=_surgery_event_surgeon_tokens(row),
        )
        for index, row in enumerate(source_rows, start=1)
    )


def _link_postoperative_first_course_records(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    postoperative_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...], str]:
    """按最近一台已结束的正式手术，将术后首次病程唯一归属到单个事件。

    仅使用实际手术结束时间和文书权威记录时间；结束时间相同或任一待核对文书
    缺时间时无法做安全归属，保持数据不足而不猜测。
    """

    if any(event.surgery_end_time is None for event in surgery_events):
        return (), "authoritative_time_missing"
    ordered_events = tuple(sorted(surgery_events, key=lambda item: item.surgery_end_time))
    if len({item.surgery_end_time for item in ordered_events}) != len(ordered_events):
        return (), "association_failed"

    # 事件身份按本次有序事件序号保存，不能用展示用 document_id 作字典键：
    # 上游允许不同正式记录行复用同一个 document_id。
    linked_rows: list[list[Mapping[str, Any]]] = [[] for _event in ordered_events]
    for row in postoperative_rows:
        record_time = _row_time(row)
        if record_time is None:
            return (), "authoritative_time_missing"
        eligible_event_indexes = tuple(
            index
            for index, event in enumerate(ordered_events)
            if event.surgery_end_time is not None and event.surgery_end_time <= record_time
        )
        if not eligible_event_indexes:
            continue
        # 归属最近一台已经结束的手术，一份术后首次病程不会复用到更早手术。
        linked_rows[eligible_event_indexes[-1]].append(row)

    return (
        tuple(
            (event, tuple(rows))
            for event, rows in zip(ordered_events, linked_rows)
        ),
        "",
    )


def _event_display_base(event: _PostoperativeSurgeryEvent) -> dict[str, Any]:
    return {
        "document_id": event.document_id,
        "surgery_name": event.surgery_name,
        "surgeon_names": list(event.surgeon_names),
        "surgery_end_time": (
            event.surgery_end_time.isoformat(sep=" ")
            if event.surgery_end_time is not None
            else None
        ),
    }


def _postoperative_window_gate(
    *,
    surgery_events: Sequence[_PostoperativeSurgeryEvent],
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[str, str, Mapping[str, Any]] | None:
    """在逐台核对前确认术后三日观察窗口已经成熟。

    评价终点必须来自同一冻结 Evidence Session。只有日期时按保守口径，
    评价日期严格晚于每台手术结束日后的第三个自然日，避免在窗口当天提前
    把尚未发生的病程判为缺失。
    """

    def unavailable(issue: str) -> tuple[str, str, Mapping[str, Any]]:
        return (
            "data_gap",
            issue,
            {
                "verification_kind": "postoperative_three_day_window_unavailable",
                "issue": issue,
            },
        )

    if horizon_error:
        return unavailable(horizon_error)
    if len(horizon_rows) != 1:
        return unavailable("authoritative_time_missing")

    row = horizon_rows[0]
    horizon_time = _parse_datetime(row.get("horizon_datetime"))
    raw_date = _clean(row.get("horizon_date"))
    horizon_date: date | None = None
    if raw_date:
        try:
            horizon_date = date.fromisoformat(raw_date)
        except ValueError:
            return unavailable("authoritative_time_missing")
    if horizon_time is None and horizon_date is None:
        return unavailable("authoritative_time_missing")
    if horizon_time is not None and horizon_date is not None and horizon_time.date() != horizon_date:
        return unavailable("authoritative_time_conflict")

    deadlines = tuple(
        event.surgery_end_time.date() + timedelta(days=3)
        for event in surgery_events
        if event.surgery_end_time is not None
    )
    if len(deadlines) != len(surgery_events):
        return unavailable("authoritative_time_missing")
    if any(
        (horizon_time is not None and horizon_time < event.surgery_end_time)
        or (horizon_time is None and horizon_date < event.surgery_end_time.date())
        for event in surgery_events
        if event.surgery_end_time is not None
    ):
        return unavailable("authoritative_time_conflict")

    mature = (
        all(horizon_time.date() > deadline for deadline in deadlines)
        if horizon_time is not None
        else all(horizon_date > deadline for deadline in deadlines)
    )
    if mature:
        return None

    facts: dict[str, Any] = {
        "verification_kind": "postoperative_three_day_window_not_mature",
        "surgery_times": [
            event.surgery_end_time.isoformat(sep=" ")
            for event in surgery_events
            if event.surgery_end_time is not None
        ],
        "deadline_dates": [deadline.isoformat() for deadline in deadlines],
    }
    if horizon_time is not None:
        facts["evaluation_time"] = horizon_time.isoformat(sep=" ")
    else:
        facts["evaluation_date"] = horizon_date.isoformat()
    return "data_gap", "evaluation_window_not_mature", facts


def _person_tokens(row: Mapping[str, Any]) -> set[str]:
    return {
        _clean(row.get(key)).lower()
        for key in (
            "surgeon",
            "surgeon_physician_code",
            "main_surgery_sign",
            "author_id",
            "author_name",
            "physician_sign",
            "submitter",
            "submitter_id",
        )
        if _clean(row.get(key))
    }


@dataclass(frozen=True)
class NativeExtendedDocumentExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...]
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


async def execute_luxian_0609_native_extended_document_rules(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    decision_rule_ids: Sequence[str] = (),
    **_: Any,
) -> NativeExtendedDocumentExecutionResult:
    selected = tuple(
        rule_id
        for rule_id in EXTENDED_DOCUMENT_RULE_IDS
        if rule_id in {str(item or "").strip().upper() for item in rule_ids}
    )
    if not selected:
        return NativeExtendedDocumentExecutionResult((), (), ())
    if (
        not isinstance(evidence_snapshot, Luxian0609EvidenceSnapshot)
        or not isinstance(evidence_materials, Luxian0609EvidenceMaterialStore)
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("extended document rules require one evidence session")
    if set(decision_rule_ids) != set(selected):
        raise ValueError("extended document rules require typed decisions")

    registration_rows, registration_error = _source_rows(
        evidence_materials, "inpat_registration"
    )
    admission_rows, admission_error = _source_rows(
        evidence_materials, "admission_record"
    )
    death_rows, death_error = _source_rows(evidence_materials, "death_record")
    discussion_rows, discussion_error = _source_rows(
        evidence_materials, "death_discussion"
    )
    horizon_rows, horizon_error = (
        _source_rows(evidence_materials, "evaluation_context.horizon")
        if {"LX0609-051", "LX0609-064"}.intersection(selected)
        else ((), "")
    )
    discharge_rows, discharge_error = _source_rows(
        evidence_materials, "discharge_record"
    )
    daily_rows, daily_error = _source_rows(evidence_materials, "daily_course_record")
    senior_rows, senior_error = _source_rows(
        evidence_materials, "senior_course_record"
    )
    postop_first_rows, postop_first_error = _source_rows(
        evidence_materials, "postsurg_firstcourse_record"
    )
    mr_surgery_rows, mr_surgery_error = _source_rows(
        evidence_materials, "mr_surgery"
    )
    surgery_record_rows, surgery_record_error = _source_rows(
        evidence_materials, "surgery_record"
    )
    consultation_rows, consultation_error = _source_rows(
        evidence_materials, "consultation_record"
    )
    handoff_rows, handoff_error = _source_rows(evidence_materials, "handoff_record")
    handover_rows, handover_error = _source_rows(evidence_materials, "handover_record")
    physician_change_rows, physician_change_error = _source_rows(
        evidence_materials, "physician_change_event"
    )
    transfer_in_rows, transfer_in_error = _source_rows(
        evidence_materials, "transfer_in_record"
    )
    transfer_out_rows, transfer_out_error = _source_rows(
        evidence_materials, "transfer_out_record"
    )
    nondrug_order_rows, nondrug_order_error = _source_rows(
        evidence_materials, "inpat_nondrug_order"
    )
    diagnosis_rows, diagnosis_error = _source_rows(evidence_materials, "diagnosis")
    diffcase_rows, diffcase_error = _source_rows(
        evidence_materials, "diffcase_discussion_record"
    )
    crisis_rows, crisis_error = _source_rows(
        evidence_materials, "crisis_value_record"
    )
    lab_item_rows, lab_item_error = _source_rows(
        evidence_materials, "labtest_item_report"
    )
    lab_master_rows, lab_master_error = _source_rows(
        evidence_materials, "labtest_master"
    )
    drug_order_rows, drug_order_error = _source_rows(
        evidence_materials, "inpat_drug_order"
    )
    discharge_diagnosis_rows, discharge_diagnosis_error = _source_rows(
        evidence_materials, "discharge_record_diagnosis"
    )
    mr_bloodtrans_rows, mr_bloodtrans_error = _source_rows(
        evidence_materials, "mr_bloodtrans"
    )
    death_state, death_time = _death_context(
        registration_rows=registration_rows,
        death_rows=death_rows,
        discharge_rows=discharge_rows,
    )
    if (
        death_state == "unknown"
        and registration_rows
        and not (registration_error or death_error or discharge_error)
    ):
        # 本次住院存在，死亡/出院三类权威来源均已完整读取且无死亡事实。
        death_state = "absent"
    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    surgery_applicability = (
        resolve_surgery_applicability(
            snapshot=evidence_snapshot,
            materials=evidence_materials,
        )
        if {"LX0609-064", "LX0609-065", "LX0609-066"}.intersection(selected)
        else None
    )
    critical_value_outcomes = {
        item.rule_id: item
        for item in evaluate_critical_value_rules(
            rule_ids=tuple(rule_id for rule_id in CRITICAL_VALUE_RULE_IDS if rule_id in selected),
            inputs=CriticalValueInput(
                lab_item_error=lab_item_error or None,
                crisis_error=crisis_error or None,
                lab_report_count=len(lab_master_rows),
                lab_detail_count=len(lab_item_rows),
                items=tuple(
                    CriticalValueItem(
                        item_name=_clean(row.get("item_name") or row.get("item_code")),
                        flag_values=tuple(
                            _clean(row.get(key))
                            for key in (
                                "result_flag",
                                "abnormal_flag",
                                "abnormal_indicator",
                                "result_status",
                                "result_hint",
                            )
                        ),
                        marker_text=_material_text(row),
                        display_flag=_clean(
                            row.get("result_flag")
                            or row.get("abnormal_flag")
                            or row.get("abnormal_indicator")
                        ),
                        report_time=_parse_datetime(
                            row.get("report_time")
                            or row.get("report_datetime")
                            or row.get("record_time")
                        ),
                        event_key=_critical_value_event_key("labtest_item_report", row),
                    )
                    for row in lab_item_rows
                ),
                dispositions=tuple(
                    CriticalValueDisposition(
                        disposition_time=parsed,
                        event_key=_critical_value_event_key("crisis_value_record", row),
                    )
                    for row in crisis_rows
                    for parsed in (_row_time(row),)
                    if parsed is not None
                ),
            ),
        )
    } if set(selected).intersection(CRITICAL_VALUE_RULE_IDS) else {}

    for rule_id in selected:
        if rule_id == "LX0609-050":
            source_error = (
                (registration_error and admission_error)
                or daily_error
                or diffcase_error
            )
            admission_time = next(
                (
                    _parse_datetime(row.get("admission_datetime") or row.get("admission_time"))
                    for row in (*registration_rows, *admission_rows)
                    if _parse_datetime(row.get("admission_datetime") or row.get("admission_time"))
                    is not None
                ),
                None,
            )
            strong_uncertain_rows = tuple(
                row
                for row in daily_rows
                if any(marker in _material_text(row) for marker in _UNCERTAIN_DIAGNOSIS_MARKERS)
                and admission_time is not None
                and (row_time := _row_time(row)) is not None
                and row_time >= admission_time + timedelta(days=7)
            )
            local_uncertain_rows = tuple(
                row for row in daily_rows
                if any(marker in _material_text(row) for marker in _LOCAL_DIAGNOSIS_UNCERTAINTY_MARKERS)
                and admission_time is not None and (row_time := _row_time(row)) is not None
                and row_time >= admission_time + timedelta(days=7)
            )
            uncertain_rows = strong_uncertain_rows or local_uncertain_rows
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif admission_time is None:
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif not uncertain_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif not strong_uncertain_rows:
                final_state, reason_code = "data_gap", "diagnosis_scope_uncertain"
            elif diffcase_rows:
                final_state, reason_code = "compliant", "requirement_satisfied"
            else:
                final_state, reason_code = "non_compliant", "required_document_missing"
            scope_uncertain = reason_code == "diagnosis_scope_uncertain"
            if admission_time is not None and not source_error:
                display.append((rule_id, {
                    "verification_kind": (
                        "uncertain_diagnosis_scope_unverified" if scope_uncertain
                        else "uncertain_diagnosis_discussion_check"
                    ),
                    "admission_time": admission_time.isoformat(sep=" "),
                    "uncertain_record_times": [
                        value.isoformat(sep=" ")
                        for row in (local_uncertain_rows if scope_uncertain else strong_uncertain_rows)
                        if (value := _row_time(row)) is not None
                    ],
                    "discussion_count": len(diffcase_rows),
                }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    "inpat_registration",
                    "admission_record",
                    "daily_course_record",
                    "diffcase_discussion_record",
                ),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id in {"LX0609-052", "LX0609-053"}:
            outcome = critical_value_outcomes[rule_id]
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=CRITICAL_VALUE_SOURCE_KEYS,
                final_state=outcome.final_state, reason_code=outcome.reason_code,
            ))
            continue

        if rule_id in {
            "LX0609-054", "LX0609-055", "LX0609-056",
            "LX0609-057", "LX0609-058", "LX0609-059",
        }:
            antimicrobial_orders = _antimicrobial_orders(drug_order_rows)
            course_rows = (*daily_rows, *senior_rows)
            source_error = drug_order_error or (
                "" if rule_id == "LX0609-058" else daily_error or senior_error
            )
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif not antimicrobial_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif rule_id == "LX0609-054":
                used_names = tuple(
                    name for name in _ANTIMICROBIALS
                    if any(name in _material_text(row) for row in antimicrobial_orders)
                )
                association_failed = _repeated_antimicrobial_association_failed(
                    antimicrobial_orders, course_rows
                )
                documented_names = (
                    ()
                    if association_failed
                    else _documented_antimicrobial_names(course_rows, used_names)
                )
                unmatched_names = tuple(
                    name for name in used_names if name not in documented_names
                )
                complete = not association_failed and not unmatched_names
                if association_failed:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    final_state = "compliant" if complete else "non_compliant"
                    reason_code = (
                        "requirement_satisfied"
                        if complete
                        else "requirement_violated"
                    )
                display.append((rule_id, {
                    "verification_kind": "antimicrobial_reason_documentation_check",
                    "antimicrobials": list(used_names),
                    "reason_documented": complete,
                    "unmatched_antimicrobials": list(unmatched_names),
                    "association_ambiguous": association_failed,
                }))
            elif rule_id == "LX0609-055":
                order_events = tuple(
                    (row, name, _parse_datetime(row.get("planned_start_datetime")))
                    for row in antimicrobial_orders
                    for name in _antimicrobial_names_in(row)
                )
                effect_evaluation_rows = tuple(
                    row for row in course_rows
                    if _is_antimicrobial_effect_evaluation(row)
                )
                ambiguous_evaluation = len(order_events) > 1 and any(
                    not _linked_order_id(row)
                    and (
                        not (mentioned := _antimicrobial_names_in(row))
                        or any(
                            sum(name == event_name for _, event_name, _ in order_events) > 1
                            for name in mentioned
                        )
                    )
                    for row in effect_evaluation_rows
                )
                intervals: list[float] = []
                unmatched_names: list[str] = []
                has_untimed_match = False
                if any(start is None for _, _, start in order_events):
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                elif ambiguous_evaluation:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in order_events:
                        order_id = _clean(order.get("order_id"))
                        matching_rows = tuple(
                            row
                            for row in effect_evaluation_rows
                            if (
                                (_linked_order_id(row) == order_id and bool(order_id) and (
                                    name in _antimicrobial_names_in(row)
                                    or len(_antimicrobial_names_in(order)) == 1
                                ))
                                or (
                                    not _linked_order_id(row)
                                    and name in _antimicrobial_names_in(row)
                                )
                                or (not _linked_order_id(row) and len(order_events) == 1)
                            )
                        )
                        event_intervals = [
                            (value - start).total_seconds() / 3600
                            for row in matching_rows
                            if (value := _row_time(row)) is not None and value >= start
                        ]
                        intervals.extend(event_intervals)
                        if not any(48 <= value <= 72 for value in event_intervals):
                            unmatched_names.append(name)
                            has_untimed_match = has_untimed_match or any(
                                _row_time(row) is None for row in matching_rows
                            )
                    if not unmatched_names:
                        final_state, reason_code = "compliant", "requirement_within_threshold"
                    elif has_untimed_match:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    else:
                        final_state, reason_code = "non_compliant", "threshold_exceeded"
                display.append((rule_id, {
                    "verification_kind": "antimicrobial_effect_evaluation_check",
                    "antimicrobials": list(dict.fromkeys(
                        name for _, name, _ in order_events
                    )),
                    "window_hours": [48, 72],
                    "evaluation_intervals": [round(value, 2) for value in intervals],
                    "unmatched_antimicrobials": list(dict.fromkeys(unmatched_names)),
                    "association_ambiguous": ambiguous_evaluation,
                }))
            elif rule_id == "LX0609-056":
                special_orders = tuple(
                    row for row in antimicrobial_orders
                    if any(name in _material_text(row) for name in _SPECIAL_ANTIMICROBIALS)
                )
                if len(special_orders) < 2:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif lab_master_error or lab_item_error:
                    final_state, reason_code = "data_gap", lab_master_error or lab_item_error
                else:
                    special_order_times = tuple(
                        value
                        for row in special_orders
                        if (value := _parse_datetime(row.get("prescribed_datetime")))
                        is not None
                    )
                    first_order = min(special_order_times, default=None)
                    specimen_times = tuple(
                        value
                        for row in lab_master_rows
                        if _has_any_text((row,), ("培养", "药敏", "病原"))
                        and (value := _parse_datetime(row.get("request_datetime") or row.get("sample_datetime")))
                        is not None
                    )
                    if first_order is None:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    else:
                        complete = any(value <= first_order for value in specimen_times)
                        final_state = "compliant" if complete else "non_compliant"
                        reason_code = "requirement_satisfied" if complete else "requirement_violated"
            elif rule_id == "LX0609-057":
                structured_empiric = any(
                    "培养" in (text := _material_text(row))
                    and "药敏" in text
                    and "调整" in text
                    and any(action in text for action in ("启用", "使用", "给予"))
                    and (any(name in text for name in _ANTIMICROBIALS) or (
                        len(antimicrobial_orders) == 1
                        and any(term in text for term in ("抗菌药", "抗感染治疗"))))
                    for row in course_rows
                )
                empiric = structured_empiric or _has_any_text(
                    (*antimicrobial_orders, *course_rows), ("经验性", "经验用药")
                )
                if not empiric:
                    final_state, reason_code = "data_gap", "applicability_source_gap"
                else:
                    complete = structured_empiric or _has_any_text(
                        course_rows,
                        ("重症感染", "覆盖耐药菌", "已留取", "无样可采，", "无样可采；"),
                    )
                    final_state = "compliant" if complete else "non_compliant"
                    reason_code = "requirement_satisfied" if complete else "requirement_violated"
                    display.append((rule_id, {
                        "verification_kind": "empiric_antimicrobial_reason_check",
                        "antimicrobials": [
                            name for name in _ANTIMICROBIALS
                            if any(name in _material_text(row) for row in antimicrobial_orders)
                        ],
                        "empiric_use_confirmed": True,
                        "reason_or_no_specimen_documented": complete,
                    }))
            elif rule_id == "LX0609-058":
                special_events = tuple(
                    (row, name, _parse_datetime(row.get("planned_start_datetime")))
                    for row in antimicrobial_orders
                    for name in _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                )
                special_names = tuple(dict.fromkeys(
                    name for _, name, _ in special_events
                ))
                expert_support_rows = tuple(
                    row
                    for row in (*consultation_rows, *senior_rows)
                    if _is_special_antimicrobial_expert_support(row)
                )
                timed_expert_supports = tuple(
                    value
                    for row in expert_support_rows
                    if (value := _row_time(row)) is not None
                )
                first_order_time = min(
                    (start for _, _, start in special_events if start is not None),
                    default=None,
                )
                expert_support_time = min(timed_expert_supports, default=None)
                ambiguous_support = len(special_events) > 1 and any(
                    not _linked_order_id(row)
                    and (
                        not (mentioned := _antimicrobial_names_in(
                            row, _SPECIAL_ANTIMICROBIALS
                        ))
                        or any(
                            sum(name == event_name for _, event_name, _ in special_events) > 1
                            for name in mentioned
                        )
                    )
                    for row in expert_support_rows
                )
                unmatched_names: list[str] = []
                late_support = False
                untimed_support = False
                if not special_events:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif any(start is None for _, _, start in special_events):
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                elif ambiguous_support:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in special_events:
                        order_id = _clean(order.get("order_id"))
                        matching_rows = tuple(
                            row for row in expert_support_rows
                            if (_linked_order_id(row) == order_id and bool(order_id) and (
                                name in _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS)
                                or len(_antimicrobial_names_in(
                                    order, _SPECIAL_ANTIMICROBIALS
                                )) == 1
                            ))
                            or (
                                not _linked_order_id(row)
                                and name in _antimicrobial_names_in(
                                    row, _SPECIAL_ANTIMICROBIALS
                                )
                            )
                            or (not _linked_order_id(row) and len(special_events) == 1)
                        )
                        matching_times = tuple(
                            value for row in matching_rows
                            if (value := _row_time(row)) is not None
                        )
                        if any(value <= start for value in matching_times):
                            continue
                        unmatched_names.append(name)
                        late_support = late_support or bool(matching_times)
                        untimed_support = untimed_support or any(
                            _row_time(row) is None for row in matching_rows
                        )
                    if not unmatched_names:
                        final_state, reason_code = "compliant", "requirement_satisfied"
                    elif untimed_support:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif consultation_error or senior_error:
                        final_state, reason_code = "data_gap", consultation_error or senior_error
                    else:
                        final_state = "non_compliant"
                        reason_code = (
                            "requirement_violated"
                            if late_support
                            else "required_document_missing"
                        )
                if special_events:
                    display.append((rule_id, {
                        "verification_kind": "special_antimicrobial_expert_support_check",
                        "special_antimicrobials": list(special_names),
                        "expert_support_present": bool(expert_support_rows),
                        "first_antimicrobial_time": (
                            first_order_time.isoformat(sep=" ")
                            if first_order_time is not None
                            else None
                        ),
                        "expert_support_time": (
                            expert_support_time.isoformat(sep=" ")
                            if expert_support_time is not None
                            else None
                        ),
                        "support_before_use": final_state == "compliant",
                        "unmatched_special_antimicrobials": list(dict.fromkeys(unmatched_names)),
                        "association_ambiguous": ambiguous_support,
                    }))
            else:
                used_names = tuple(
                    name for name in _ANTIMICROBIALS
                    if any(name in _material_text(row) for row in antimicrobial_orders)
                )
                complete = bool(used_names) and all(
                    _has_any_text(course_rows, (name,)) for name in used_names
                )
                final_state = "compliant" if complete else "non_compliant"
                reason_code = "requirement_satisfied" if complete else "requirement_violated"
                display.append((rule_id, {
                    (
                        "verification_kind"
                        if complete
                        else "failure_kind"
                    ): (
                        "antimicrobial_course_documentation_complete"
                        if complete
                        else "antimicrobial_course_documentation_missing"
                    ),
                    "antimicrobials": list(used_names),
                    "course_documented": complete,
                }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    ("inpat_drug_order", "senior_course_record", "consultation_record")
                    if rule_id == "LX0609-058"
                    else (
                        "inpat_drug_order", "daily_course_record", "senior_course_record",
                        "consultation_record", "labtest_master", "labtest_item_report",
                    )
                ),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id == "LX0609-063":
            if discharge_error:
                final_state, reason_code = "data_gap", discharge_error
            elif not discharge_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif diagnosis_error or discharge_diagnosis_error:
                final_state, reason_code = "data_gap", diagnosis_error or discharge_diagnosis_error
            else:
                authority = _diagnosis_sequence(diagnosis_rows)
                written = _diagnosis_sequence(discharge_diagnosis_rows)
                if not authority or not written:
                    final_state, reason_code = "data_gap", "required_field_missing"
                else:
                    complete = authority == written
                    final_state = "compliant" if complete else "non_compliant"
                    reason_code = "requirement_satisfied" if complete else "requirement_violated"
                    display.append((rule_id, {
                        "verification_kind": "discharge_diagnosis_consistency_check",
                        "authoritative_diagnoses": list(authority),
                        "written_diagnoses": list(written),
                        "diagnoses_consistent": complete,
                    }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=("discharge_record", "diagnosis", "discharge_record_diagnosis"),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id == "LX0609-070":
            if mr_bloodtrans_error:
                final_state, reason_code = "data_gap", mr_bloodtrans_error
            elif not mr_bloodtrans_rows:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif registration_error:
                final_state, reason_code = "data_gap", registration_error
            elif lab_item_error:
                final_state, reason_code = "data_gap", lab_item_error
            else:
                final_state, detail_reason, facts = evaluate_pretransfusion_nine_items(
                    {
                        "inpat_registration": list(registration_rows),
                        "mr_bloodtrans": list(mr_bloodtrans_rows),
                        "labtest_item_report": list(lab_item_rows),
                        "blood_application": [],
                        "__logical_source_states__": {
                            "labtest_item_report": "available" if lab_item_rows else "empty",
                        },
                    },
                    require_current_stay=True,
                )
                reason_code = {
                    "pretransfusion_items_complete": "requirement_satisfied",
                    "pretransfusion_items_incomplete": "requirement_violated",
                    "pretransfusion_tests_after_transfusion": "requirement_violated",
                    "pretransfusion_test_time_missing": "authoritative_time_missing",
                    "authoritative_time_missing": "authoritative_time_missing",
                    "transfusion_time_unavailable": "authoritative_time_missing",
                    "admission_time_unavailable": "authoritative_time_missing",
                    "pretransfusion_item_contract_unavailable": "source_unavailable",
                    "pretransfusion_tests_outside_current_stay": "requirement_violated",
                    "source_query_error": "source_query_error",
                }.get(detail_reason, "required_field_missing")
                if facts is not None:
                    display.append((rule_id, dict(facts)))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=(
                    "inpat_registration",
                    "mr_bloodtrans",
                    "labtest_item_report",
                ),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id == "LX0609-075":
            invasive_orders = tuple(
                row for row in nondrug_order_rows
                if any(name in _material_text(row) for name in _INVASIVE_PROCEDURES)
            )
            if nondrug_order_error:
                final_state, reason_code = "data_gap", nondrug_order_error
            elif not invasive_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif daily_error:
                final_state, reason_code = "data_gap", daily_error
            else:
                ordered_names = tuple(
                    name for name in _INVASIVE_PROCEDURES
                    if any(name in _material_text(row) for row in invasive_orders)
                )
                complete = all(_has_any_text(daily_rows, (name,)) for name in ordered_names)
                final_state = "compliant" if complete else "non_compliant"
                reason_code = "requirement_satisfied" if complete else "required_document_missing"
                display.append((rule_id, {
                    (
                        "verification_kind"
                        if complete
                        else "failure_kind"
                    ): (
                        "invasive_procedure_course_record_complete"
                        if complete
                        else "invasive_procedure_course_record_missing"
                    ),
                    "ordered_procedures": list(ordered_names),
                    "course_documented": complete,
                }))
            decisions.append(_decision(
                rule_id=rule_id, snapshot=evidence_snapshot,
                source_keys=("inpat_nondrug_order", "daily_course_record"),
                final_state=final_state, reason_code=reason_code,
            ))
            continue

        if rule_id in {"LX0609-051", "LX0609-060"}:
            source_error = registration_error or death_error or discharge_error
            if source_error and death_state == "unknown":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="data_gap",
                        reason_code=source_error,
                    )
                )
                continue
            if death_state == "absent":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
            if death_state != "present":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=(
                            "inpat_registration",
                            "death_record",
                            "discharge_record",
                        ),
                        final_state="data_gap",
                        reason_code=(
                            "authoritative_time_conflict"
                            if death_state == "conflict"
                            else "applicability_source_gap"
                        ),
                    )
                )
                continue

        if rule_id == "LX0609-060":
            final_state = "compliant" if death_rows else "non_compliant"
            display.append((rule_id, {
                "verification_kind": "death_record_presence_check",
                "death_confirmed": True,
                "death_time": death_time.isoformat(sep=" ") if death_time else None,
                "death_record_count": len(death_rows),
            }))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=("inpat_registration", "death_record"),
                    final_state=final_state,
                    reason_code=(
                        "requirement_satisfied"
                        if death_rows
                        else "required_document_missing"
                    ),
                )
            )
            continue

        if rule_id == "LX0609-051":
            outcome = evaluate_death_discussion_timeliness(
                death_time=death_time,
                death_rows=death_rows,
                discussion_rows=discussion_rows,
                discussion_error=discussion_error,
                horizon_rows=horizon_rows,
                horizon_error=horizon_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "death_record",
                        "death_discussion",
                        "evaluation_context.horizon",
                    ),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                )
            )
            continue

        if rule_id == "LX0609-061":
            outcome = evaluate_discharge_documentation_timeliness(
                death_state=death_state,
                death_error=death_error,
                registration_error=registration_error,
                discharge_error=discharge_error,
                discharge_time=_discharge_time(registration_rows, discharge_rows),
                discharge_rows=discharge_rows,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            source_keys = (
                ("inpat_registration", "death_record")
                if death_state == "present" or (death_state == "unknown" and death_error)
                else ("inpat_registration", "discharge_record")
            )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=source_keys,
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                )
            )
            continue

        if rule_id == "LX0609-062":
            if discharge_error:
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("discharge_record",),
                        final_state="data_gap",
                        reason_code=discharge_error,
                    )
                )
                continue
            if not discharge_rows:
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("discharge_record",),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
            medications, medication_error = _structured_discharge_medications(
                discharge_rows
            )
            if medication_error:
                final_state, reason_code = "data_gap", medication_error
            elif not medications:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            else:
                required_groups = (
                    ("drug_name", "generic_name", "name"),
                    ("dose", "single_dose"),
                    ("route", "drug_apply_method"),
                    ("duration", "usage_time", "frequency"),
                )
                complete = all(
                    all(
                        any(_clean(item.get(key)) for key in group)
                        for group in required_groups
                    )
                    for item in medications
                )
                final_state = "compliant" if complete else "non_compliant"
                reason_code = (
                    "requirement_satisfied" if complete else "requirement_violated"
                )
                missing_fields = sorted({
                    group[0]
                    for item in medications
                    for group in required_groups
                    if not any(_clean(item.get(key)) for key in group)
                })
                display.append(
                    (
                        rule_id,
                        {
                            "verification_kind": "discharge_medication_completeness_check",
                            "medication_count": len(medications),
                            "required_fields": [
                                "drug_name",
                                "dose",
                                "route",
                                "duration",
                            ],
                            "missing_fields": missing_fields,
                        },
                    )
                )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=("discharge_record",),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id == "LX0609-066":
            assert surgery_applicability is not None
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            else:
                surgery_events = _postoperative_surgery_events(
                    mr_surgery_rows=mr_surgery_rows,
                    surgery_record_rows=surgery_record_rows,
                )
                linked_events: tuple[
                    tuple[_PostoperativeSurgeryEvent, tuple[Mapping[str, Any], ...]], ...
                ] = ()
                linkage_error = postop_first_error
                if not linkage_error:
                    linked_events, linkage_error = _link_postoperative_first_course_records(
                        surgery_events=surgery_events,
                        postoperative_rows=postop_first_rows,
                    )
                if linkage_error:
                    final_state, reason_code = "data_gap", linkage_error
                else:
                    unmet_events = [
                        event.document_id
                        for event, linked_rows in linked_events
                        if not linked_rows
                    ]
                    final_state = "compliant" if not unmet_events else "non_compliant"
                    reason_code = (
                        "requirement_satisfied"
                        if not unmet_events
                        else "required_document_missing"
                    )
            if gate_outcome is None:
                display.append((rule_id, {
                    "verification_kind": "postoperative_first_course_presence_check",
                    "performed_surgery_count": len(surgery_events),
                    "postoperative_first_course_count": len(postop_first_rows),
                    "surgery_events": [
                        {
                            **_event_display_base(event),
                            "postoperative_first_course_document_ids": [
                                _clean(row.get("document_id") or row.get("id"))
                                for row in linked_rows
                            ],
                        }
                        for event, linked_rows in linked_events
                    ],
                    "unmet_surgery_events": (
                        [
                            event.document_id
                            for event, linked_rows in linked_events
                            if not linked_rows
                        ]
                        if not linkage_error
                        else []
                    ),
                }))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "mr_surgery",
                        "surgery_record",
                        "postsurg_firstcourse_record",
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id in {"LX0609-064", "LX0609-065"}:
            assert surgery_applicability is not None
            gate_outcome = _surgery_applicability_outcome(surgery_applicability)
            surgery_events = _postoperative_surgery_events(
                mr_surgery_rows=mr_surgery_rows,
                surgery_record_rows=surgery_record_rows,
            )
            if gate_outcome is not None:
                final_state, reason_code = gate_outcome
            elif not surgery_events:
                final_state, reason_code = "data_gap", "authoritative_time_missing"
            elif (
                len(surgery_events) > 1
                and all(event.source_key == "mr_surgery" for event in surgery_events)
            ):
                # 没有正式手术记录时，多个操作目录行仍无法安全证明逐台关联。
                # 本轮仅收敛“正式手术记录一行即一事件”的主路径。
                final_state, reason_code = "data_gap", "association_failed"
            elif any(event.surgery_end_time is None for event in surgery_events):
                final_state, reason_code = "data_gap", "authoritative_time_missing"
                display.append((rule_id, {
                    "verification_kind": "postoperative_surgery_event_time_check",
                    "performed_surgery_count": len(surgery_events),
                    "surgery_events": [_event_display_base(event) for event in surgery_events],
                    "missing_surgery_end_events": [
                        event.document_id
                        for event in surgery_events
                        if event.surgery_end_time is None
                    ],
                }))
            elif rule_id == "LX0609-064" and (
                window_gate := _postoperative_window_gate(
                    surgery_events=surgery_events,
                    horizon_rows=horizon_rows,
                    horizon_error=horizon_error,
                )
            ) is not None:
                final_state, reason_code, window_facts = window_gate
                display.append((rule_id, window_facts))
            elif (
                (daily_error or senior_error)
                if rule_id == "LX0609-064"
                else senior_error
            ):
                final_state, reason_code = "data_gap", (
                    daily_error or senior_error
                    if rule_id == "LX0609-064"
                    else senior_error
                )
            elif rule_id == "LX0609-064" and any(
                event.surgeon_names
                and all(
                    _physician_identity_is_masked(name)
                    for name in event.surgeon_names
                )
                for event in surgery_events
            ):
                final_state, reason_code = "data_gap", "association_failed"
            else:
                if rule_id == "LX0609-065":
                    event_facts: list[dict[str, Any]] = []
                    unmet_events: list[dict[str, Any]] = []
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        deadline = event.surgery_end_time + timedelta(hours=72)
                        senior_round_times = [
                            value.isoformat(sep=" ")
                            for row in senior_rows
                            if (value := _row_time(row)) is not None
                            and event.surgery_end_time <= value <= deadline
                        ]
                        event_fact = {
                            **_event_display_base(event),
                            "deadline": deadline.isoformat(sep=" "),
                            "senior_round_times": senior_round_times,
                        }
                        event_facts.append(event_fact)
                        if not senior_round_times:
                            unmet_events.append({
                                "document_id": event.document_id,
                                "senior_round_times": [],
                            })
                    final_state = "compliant" if not unmet_events else "non_compliant"
                    reason_code = (
                        "requirement_satisfied"
                        if not unmet_events
                        else "required_document_missing"
                    )
                    senior_round_delivery_values = sorted({
                        value
                        for item in event_facts
                        for value in item["senior_round_times"]
                    })
                    if unmet_events:
                        senior_round_delivery_values = [
                            f"共{len(event_facts)}台手术中，{len(unmet_events)}台手术结束后72小时内"
                            "未查到上级医师查房",
                            *senior_round_delivery_values,
                        ]
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "senior_round_times": senior_round_delivery_values,
                    }
                    display.append((rule_id, {
                        "verification_kind": "postoperative_senior_round_check",
                        "threshold_hours": 72,
                        "performed_surgery_count": len(surgery_events),
                        "surgery_events": event_facts,
                        "unmet_surgery_events": unmet_events,
                        **legacy_summary_facts,
                    }))
                else:
                    event_facts = []
                    unmet_events = []
                    missing_surgeon_events = []
                    for event in surgery_events:
                        assert event.surgery_end_time is not None
                        required_dates = {
                            (event.surgery_end_time + timedelta(days=offset)).date()
                            for offset in (1, 2, 3)
                        }
                        postop_rows = tuple(
                            row
                            for row in (*daily_rows, *senior_rows)
                            if (record_time := _row_time(row)) is not None
                            and record_time.date() in required_dates
                        )
                        covered_dates = _course_dates(postop_rows)
                        surgeon_round = bool(event.surgeon_tokens) and any(
                            bool(
                                event.surgeon_tokens.intersection(
                                    _course_record_physician_tokens(row)
                                    | _title_round_physician_tokens(
                                        row,
                                        candidate_tokens=event.surgeon_tokens,
                                    )
                                )
                            )
                            for row in postop_rows
                        )
                        missing_dates = sorted(
                            item.isoformat()
                            for item in required_dates.difference(covered_dates)
                        )
                        event_facts.append({
                            **_event_display_base(event),
                            "required_postop_dates": sorted(
                                item.isoformat() for item in required_dates
                            ),
                            "covered_postop_dates": sorted(
                                item.isoformat() for item in covered_dates
                            ),
                            "surgeon_round_present": surgeon_round,
                        })
                        if not event.surgeon_tokens:
                            missing_surgeon_events.append(event.document_id)
                        if missing_dates or not surgeon_round:
                            unmet_events.append({
                                "document_id": event.document_id,
                                "missing_postop_dates": missing_dates,
                                "surgeon_round_present": surgeon_round,
                            })
                    if missing_surgeon_events:
                        final_state, reason_code = (
                            "data_gap",
                            "required_field_missing",
                        )
                    else:
                        final_state = "compliant" if not unmet_events else "non_compliant"
                        reason_code = (
                            "requirement_satisfied"
                            if not unmet_events
                            else "requirement_violated"
                        )
                    legacy_summary_facts = {
                        "surgery_time": "；".join(
                            str(item["surgery_end_time"])
                            for item in event_facts
                            if item.get("surgery_end_time")
                        ),
                        "required_postop_dates": sorted({
                            value
                            for item in event_facts
                            for value in item["required_postop_dates"]
                        }),
                        "covered_postop_dates": sorted({
                            value
                            for item in event_facts
                            for value in item["covered_postop_dates"]
                        }),
                        "surgeon_round_present": all(
                            item["surgeon_round_present"] is True
                            for item in event_facts
                        ),
                    }
                    display.append(
                        (
                            rule_id,
                            {
                                "verification_kind": "postoperative_three_day_coverage_check",
                                "performed_surgery_count": len(surgery_events),
                                "surgery_events": event_facts,
                                "unmet_surgery_events": unmet_events,
                                "missing_surgeon_events": missing_surgeon_events,
                                **legacy_summary_facts,
                            },
                        )
                    )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        ("mr_surgery", "surgery_record", "senior_course_record")
                        if rule_id == "LX0609-065"
                        else (
                            "mr_surgery",
                            "surgery_record",
                            "daily_course_record",
                            "senior_course_record",
                            "evaluation_context.horizon",
                        )
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id == "LX0609-067":
            outcome = evaluate_predischarge_course_presence(
                death_state=death_state,
                death_error=death_error,
                registration_error=registration_error,
                discharge_error=discharge_error,
                discharge_time=_discharge_time(registration_rows, discharge_rows),
                daily_error=daily_error,
                senior_error=senior_error,
                daily_rows=daily_rows,
                senior_rows=senior_rows,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration",
                        "discharge_record",
                        "daily_course_record",
                        "senior_course_record",
                    ),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                )
            )
            continue

        if rule_id == "LX0609-068":
            if death_state == "present":
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "death_record"),
                        final_state="not_applicable",
                        reason_code="trigger_absent_complete",
                    )
                )
                continue
            if (
                death_state == "unknown" and death_error
            ):
                decisions.append(
                    _decision(
                        rule_id=rule_id,
                        snapshot=evidence_snapshot,
                        source_keys=("inpat_registration", "death_record"),
                        final_state="data_gap",
                        reason_code=death_error,
                    )
                )
                continue
            source_error = registration_error or discharge_error
            discharge_time = _discharge_time(registration_rows, discharge_rows)
            approval_match: tuple[str, str, Mapping[str, Any]] | None = None
            render_display = False
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif discharge_time is None:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            else:
                valid_dates = {
                    discharge_time.date(),
                    (discharge_time - timedelta(days=1)).date(),
                }
                approval_match = next(
                    (
                        (source_key, approval_path, row)
                        for source_key, rows in (
                            ("daily_course_record", daily_rows),
                            ("senior_course_record", senior_rows),
                        )
                        for row in rows
                        if _row_time(row) is not None
                        and _row_time(row).date() in valid_dates
                        if (
                            approval_path := _discharge_approval_path(
                                row,
                                source_key=source_key,
                            )
                        )
                    ),
                    None,
                )
                present = approval_match is not None
                if approval_match is None and (daily_error or senior_error):
                    final_state, reason_code = (
                        "data_gap",
                        daily_error or senior_error,
                    )
                else:
                    final_state = "compliant" if present else "data_gap"
                    reason_code = (
                        "requirement_satisfied"
                        if present
                        else "source_empty"
                    )
                    render_display = True
                if render_display:
                    approval_facts: dict[str, Any] = {}
                    if approval_match is not None:
                        approval_facts["approval_path"] = approval_match[1]
                        document_id = _clean(
                            approval_match[2].get("document_id")
                            or approval_match[2].get("id")
                        )
                        if document_id:
                            approval_facts["source_document_refs"] = [{
                                "source_type": approval_match[0],
                                "source_document_id": document_id,
                            }]
                    display.append(
                        (
                            rule_id,
                            {
                                (
                                    "verification_kind"
                                    if present
                                    else "failure_kind"
                                ): (
                                    "senior_discharge_approval_present"
                                    if present
                                    else "senior_discharge_approval_missing"
                                ),
                                "discharge_date": discharge_time.date().isoformat(),
                                "checked_dates": tuple(
                                    sorted(item.isoformat() for item in valid_dates)
                                ),
                                "checked_source": (
                                    approval_match[0]
                                    if approval_match is not None
                                    else "daily_course_record,senior_course_record"
                                ),
                                "approval_present": present,
                                **approval_facts,
                            },
                        )
                    )
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_registration",
                        "discharge_record",
                        "daily_course_record",
                        "senior_course_record",
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id == "LX0609-069":
            outcome = evaluate_consultation_timeliness(
                consultation_rows=consultation_rows,
                consultation_error=consultation_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=("consultation_record",),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                )
            )
            continue

        if rule_id == "LX0609-071":
            outcome = evaluate_physician_handoff(
                physician_change_rows=physician_change_rows,
                physician_change_error=physician_change_error,
                nondrug_order_rows=nondrug_order_rows,
                nondrug_order_error=nondrug_order_error,
                handoff_rows=handoff_rows,
                handoff_error=handoff_error,
                handover_rows=handover_rows,
                handover_error=handover_error,
            )
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        outcome.change_source_key,
                        "handoff_record",
                        "handover_record",
                    ),
                    final_state=outcome.final_state,
                    reason_code=outcome.reason_code,
                )
            )
            continue

        if rule_id in {"LX0609-072", "LX0609-073"}:
            outcome = evaluate_transfer_documentation(
                rule_id=rule_id,
                nondrug_order_error=nondrug_order_error,
                transfer_in_error=transfer_in_error,
                transfer_out_error=transfer_out_error,
                nondrug_order_rows=nondrug_order_rows,
                transfer_in_rows=transfer_in_rows,
                transfer_out_rows=transfer_out_rows,
            )
            final_state, reason_code = outcome.final_state, outcome.reason_code
            if outcome.display_facts is not None:
                display.append((rule_id, outcome.display_facts))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "inpat_nondrug_order",
                        "transfer_in_record",
                        "transfer_out_record",
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        if rule_id == "LX0609-074":
            if diagnosis_error or daily_error or senior_error:
                final_state, reason_code = (
                    "data_gap",
                    diagnosis_error or daily_error or senior_error,
                )
            else:
                diagnoses_by_slot: dict[tuple[str, str], list[tuple[datetime, str]]] = {}
                invalid_reason: str | None = None
                association_issue: str | None = None
                for row in diagnosis_rows:
                    diagnosis_time = _parse_datetime(row.get("diagnosis_datetime"))
                    diagnosis_name = _clean(row.get("diagnosis_name"))
                    diagnosis_type = _clean(row.get("diagnosis_type")).casefold()
                    diagnosis_no = _clean(row.get("diagnosis_no")).casefold()
                    if diagnosis_time is None or not diagnosis_name:
                        invalid_reason = "authoritative_time_missing"
                        break
                    if not diagnosis_type or not diagnosis_no:
                        invalid_reason = "association_failed"
                        association_issue = "slot_missing"
                        break
                    diagnoses_by_slot.setdefault(
                        (diagnosis_type, diagnosis_no), []
                    ).append((diagnosis_time, diagnosis_name))

                change_events: list[tuple[datetime, str]] = []
                if invalid_reason is None:
                    for slot_diagnoses in diagnoses_by_slot.values():
                        names_by_time: dict[datetime, set[str]] = {}
                        for diagnosis_time, diagnosis_name in slot_diagnoses:
                            names_by_time.setdefault(diagnosis_time, set()).add(diagnosis_name)
                        if any(len(names) > 1 for names in names_by_time.values()):
                            invalid_reason = "association_failed"
                            association_issue = "same_time_conflict"
                            break
                        ordered_diagnoses = sorted(
                            (
                                (diagnosis_time, next(iter(names)))
                                for diagnosis_time, names in names_by_time.items()
                            ),
                            key=lambda item: item[0],
                        )
                        change_events.extend(
                            (current_time, current_name)
                            for (_, previous_name), (current_time, current_name) in zip(
                                ordered_diagnoses, ordered_diagnoses[1:]
                            )
                            if current_name != previous_name
                        )

                if invalid_reason is not None:
                    final_state, reason_code = "data_gap", invalid_reason
                    if invalid_reason == "association_failed":
                        display.append((rule_id, {
                            "failure_kind": "diagnosis_change_association_failed",
                            "diagnosis_record_count": len(diagnosis_rows),
                            "diagnosis_change_count": len(change_events),
                            "association_issue": association_issue,
                        }))
                elif not change_events:
                    final_state, reason_code = (
                        "not_applicable",
                        "trigger_absent_complete",
                    )
                else:
                    course_rows = tuple(
                        (_row_time(row), _row_text(row))
                        for row in (*daily_rows, *senior_rows)
                    )
                    reason_markers = (
                        "修正诊断",
                        "补充诊断",
                        "修改理由",
                    )
                    basis_markers = ("诊断依据", "依据为", "依据：", "依据:")
                    candidate_rows = tuple(
                        (record_time, text)
                        for record_time, text in course_rows
                        if any(marker in text for marker in reason_markers)
                        and any(marker in text for marker in basis_markers)
                    )
                    if len(change_events) == 1:
                        has_reason_and_basis = any(
                            record_time is not None and record_time >= change_events[0][0]
                            for record_time, _ in candidate_rows
                        )
                        if (
                            not has_reason_and_basis
                            and candidate_rows
                            and all(record_time is None for record_time, _ in candidate_rows)
                        ):
                            final_state, reason_code = (
                                "data_gap",
                                "authoritative_time_missing",
                            )
                            display.append((rule_id, {
                                "failure_kind": "diagnosis_change_documentation_time_missing",
                                "diagnosis_change_count": len(change_events),
                                "untimed_document_count": len(candidate_rows),
                                "issue": "candidate_document_time_missing",
                            }))
                        else:
                            final_state = (
                                "compliant" if has_reason_and_basis else "non_compliant"
                            )
                            reason_code = (
                                "requirement_satisfied"
                                if has_reason_and_basis
                                else "requirement_violated"
                            )
                    else:
                        matching_course_indexes = tuple(
                            tuple(
                                index
                                for index, (record_time, text) in enumerate(candidate_rows)
                                if record_time is not None
                                and record_time >= change_time
                                and diagnosis_name in text
                            )
                            for change_time, diagnosis_name in change_events
                        )
                        uniquely_matched = (
                            len(matching_course_indexes) == len(change_events)
                            and all(len(indexes) == 1 for indexes in matching_course_indexes)
                            and len({indexes[0] for indexes in matching_course_indexes})
                            == len(matching_course_indexes)
                        )
                        if uniquely_matched:
                            final_state, reason_code = (
                                "compliant",
                                "requirement_satisfied",
                            )
                        else:
                            final_state, reason_code = (
                                "data_gap",
                                "association_failed",
                            )
                            display.append((rule_id, {
                                "failure_kind": "diagnosis_change_association_failed",
                                "diagnosis_record_count": len(diagnosis_rows),
                                "diagnosis_change_count": len(change_events),
                                "association_issue": "multiple_changes_unresolved",
                            }))
                        has_reason_and_basis = uniquely_matched
                    if reason_code not in {
                        "association_failed",
                        "authoritative_time_missing",
                    }:
                        display.append((rule_id, {
                            "verification_kind": "diagnosis_change_documentation_check",
                            "diagnosis_change_count": len(change_events),
                            "reason_recorded": has_reason_and_basis,
                            "basis_recorded": has_reason_and_basis,
                        }))
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(
                        "diagnosis",
                        "daily_course_record",
                        "senior_course_record",
                    ),
                    final_state=final_state,
                    reason_code=reason_code,
                )
            )
            continue

        decisions.append(
            _decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                source_keys=EXTENDED_DOCUMENT_SOURCE_KEYS,
                final_state="data_gap",
                reason_code="source_readiness_unproven",
            )
        )

    return NativeExtendedDocumentExecutionResult(
        results=(),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(display),
    )
