from __future__ import annotations

import re
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .decision_reducer import ReducedRuleDecision
from .evidence_material import EvidenceMaterialUnavailable, Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .source_evidence_reader import authoritative_document_time_value
from .source_registry import resolve_luxian_0609_customer_document_type


_IDENTITY_FIELDS = (
    "source_version_key",
    "document_id",
    "exam_id",
    "test_id",
    "labtest_id",
    "report_id",
    "pathology_exam_id",
    "pathology_id",
    "order_id",
    "application_id",
    "event_id",
    "diagnosis_id",
    "surgery_id",
    "id",
)
_TIME_FIELDS = (
    "request_datetime",
    "request_time",
    "application_datetime",
    "application_time",
    "apply_datetime",
    "consultation_time",
    "exam_datetime",
    "exam_time",
    "report_datetime",
    "report_time",
    "order_time",
    "prescribed_datetime",
    "surgery_begin_time",
    "surgery_end_time",
    "surgery_begin_datetime",
    "surgery_end_datetime",
    "start_time",
    "transfution_datetime",
    "death_datetime",
    "death_time",
    "handoff_datetime",
    "handoff_time",
    "transfer_date",
    "diagnosis_datetime",
)
_EXCERPT_FIELDS = (
    "record_content",
    # 转入记录通用正文为空时，抗菌药处置写在转入诊疗计划（1019 C10）。
    "transfer_treatment_plan",
    "consultation_opinion",
    "consultation_advice",
    "surgery_process",
    "report_content",
    "result_content",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "conclusion",
    "result",
    "description",
    "impression",
    "recommendation",
    "reason",
    "indication",
    "transfusion_reason",
    "reason_for_blood",
    "condition_summary",
    "case_characteristic",
    "chief_complaint",
    "diagnosis",
    "order_name",
    "generic_name",
    "brand_name",
    "document_title",
)
_TIME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2})?)?"
)
_CUSTOMER_SOURCE_REF_PATTERN = re.compile(r"src_[0-9a-f]{24}")
_SAFE_SOURCE_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHARED_PARENT_DOCUMENT_SOURCES = {
    "admission_record_diagnosis": "admission_record",
    "discharge_record_diagnosis": "discharge_record",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _row_has_identity(row: Mapping[str, Any], document_id: str) -> bool:
    return any(_text(row.get(field)) == document_id for field in _IDENTITY_FIELDS)


def project_selected_grouped_document_refs(
    *,
    raw_refs: Any,
    public: bool,
    allowed_source_types: frozenset[str],
) -> list[dict[str, str]] | None:
    """安全投影执行器已经选择的一组文书引用。

    该公共边界只验证来源类型、去重和安全引用形状：公开引用原样透传，内部业务
    文书 ID 仅在此处转换为既有 ``src_`` 引用。调用方负责自己的逐项业务合同，
    因此本函数不按规则号解释事实、选择文书或拼装客户证据坐标。
    """

    if not isinstance(raw_refs, list) or len(raw_refs) > 8:
        return None
    projected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    projection_key = ""
    if not public:
        # 复用既有客户安全引用机制；这里是公共投影边界，避免规则族自行处理
        # 业务文书 ID 或把它泄漏给客户展示事实。
        from app.services.qc_workspace.canonical_result_store import (
            customer_safe_projection_key,
        )

        projection_key = customer_safe_projection_key()
    for raw_ref in raw_refs:
        if not isinstance(raw_ref, Mapping):
            return None
        if public:
            if set(raw_ref) != {"source_type", "source_ref"}:
                return None
            source_type = _text(raw_ref.get("source_type"))
            source_ref = _text(raw_ref.get("source_ref"))
            if (
                source_type not in allowed_source_types
                or _CUSTOMER_SOURCE_REF_PATTERN.fullmatch(source_ref) is None
            ):
                return None
        else:
            if set(raw_ref) != {"source_type", "source_document_id"}:
                return None
            source_type = _text(raw_ref.get("source_type"))
            document_id = _text(raw_ref.get("source_document_id"))
            if (
                source_type not in allowed_source_types
                or not document_id
                or len(document_id) > 256
            ):
                return None
            from app.services.qc_workspace.canonical_result_store import keyed_ref

            source_ref = keyed_ref("src", document_id, hmac_key=projection_key)
        identity = (source_type, source_ref)
        if identity in seen:
            return None
        seen.add(identity)
        projected.append({"source_type": source_type, "source_ref": source_ref})
    return projected


def _valid_legacy_source_level_document_id(value: Any) -> str:
    """仅允许内部已验证的文书 ID 进入后续安全签名环节。"""

    candidate = str(value or "").strip()
    return (
        candidate
        if candidate
        and len(candidate) <= 256
        and "\n" not in candidate
        and "\r" not in candidate
        else ""
    )


def project_legacy_source_level_evidence(
    *,
    decision: ReducedRuleDecision,
    evidence_snapshot: Any,
    evidence_materials: Any,
) -> list[dict[str, str]]:
    """投影尚未迁移旧合同的来源级证据；不新增任何 fallback。

    只接受 decision 已引用的 FactV2 或来源快照。事实未携带单行 ID 时，仅在
    同一冻结材料中该来源唯一对应一份文书时补回；多行、非法来源或非法 ID 均保持
    无证据，不按标题、正文或 display facts 猜测文书。
    """

    facts = getattr(evidence_snapshot, "facts", ())
    observations = getattr(evidence_snapshot, "observations", ())
    if not decision.fact_refs:
        return []
    referenced = set(decision.fact_refs)
    rows: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for fact in facts if isinstance(facts, tuple) else ():
        fact_id = str(getattr(fact, "fact_id", "") or "")
        source_snapshot_hash = str(
            getattr(fact, "source_snapshot_hash", "") or ""
        ).removeprefix("sha256:")
        if fact_id not in referenced and source_snapshot_hash not in referenced:
            continue
        document_id = _valid_legacy_source_level_document_id(
            getattr(fact, "source_document_id", "")
        )
        source_type = str(getattr(fact, "source_key", "") or "").strip().lower()
        # 部分确定性事实只绑定来源快照，不携带单行文书 ID。仅当本次冻结
        # 材料恰好一行且该行带有效 ID 时，才可安全补回当前 Bundle 的真实 ID；
        # 多行（即使仅一个非空 ID 或复用同一 ID）时保持无证据，避免猜测行。
        if (
            not document_id
            and evidence_materials is not None
            and _SAFE_SOURCE_TYPE.fullmatch(source_type)
        ):
            try:
                material_rows = tuple(evidence_materials.rows(source_type))
            except Exception:
                material_rows = ()
            if len(material_rows) == 1 and isinstance(material_rows[0], Mapping):
                document_id = _valid_legacy_source_level_document_id(
                    material_rows[0].get("document_id") or material_rows[0].get("id")
                )
        if (
            not document_id
            or document_id in seen_document_ids
            or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
        ):
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {
                "source_type": source_type,
                "source_document_id": document_id,
            }
        )
        if len(rows) >= 8:
            return rows

    # 一部分纯 Python 决策直接绑定来源快照而非 FactV2。仅当该来源在同一
    # Evidence Session 内唯一对应一份原始文书，才可补出引用。
    source_keys: set[str] = set()
    if isinstance(observations, tuple):
        for observation in observations:
            snapshot_ref = str(
                getattr(observation, "snapshot_ref", "") or ""
            ).removeprefix("sha256:")
            if snapshot_ref in referenced:
                source_keys.add(
                    str(getattr(observation, "source_key", "") or "").strip().lower()
                )
    for source_key in sorted(source_keys):
        if not _SAFE_SOURCE_TYPE.fullmatch(source_key):
            continue
        try:
            material_rows = tuple(evidence_materials.rows(source_key))
        except Exception:
            continue
        if len(material_rows) != 1 or not isinstance(material_rows[0], Mapping):
            continue
        document_id = _valid_legacy_source_level_document_id(
            material_rows[0].get("document_id") or material_rows[0].get("id")
        )
        if not document_id or document_id in seen_document_ids:
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {"source_type": source_key, "source_document_id": document_id}
        )
        if len(rows) >= 8:
            break
    return rows


def project_selected_document_evidence(
    *,
    decision: ReducedRuleDecision,
    evidence_snapshot: Any,
    evidence_materials: Any,
) -> list[dict[str, Any]] | None:
    """投影已绑定的逐行引用；None 为旧合同，空列表为禁止猜测定位。

    只消费执行器选择，不按时间、标题或客户事实重新选择。保留已有
    enrich_customer_evidence 作为字段、记录时间及文书摘要的唯一补齐位置。
    """
    if decision.reason_code == "snapshot_mismatch":
        return []
    if not isinstance(evidence_snapshot, Luxian0609EvidenceSnapshot):
        return None
    if decision.snapshot_hash != evidence_snapshot.snapshot_hash:
        return []
    selected = tuple(
        dict.fromkeys(
            reference
            for reference in decision.fact_refs
            if reference in evidence_snapshot.document_refs
        )
    )
    if not selected:
        # 明确不存在触发事件时，来源快照只说明判定读过哪些来源，不能回退为
        # 客户文书坐标。空列表会阻止旧来源级投影继续猜测文书。
        if decision.reason_code == "trigger_absent_complete":
            return []
        return None
    if (
        not isinstance(evidence_materials, Luxian0609EvidenceMaterialStore)
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        return []

    selected_refs = set(selected)
    located_by_ref: dict[str, dict[str, Any]] = {}
    resolved: set[str] = set()
    for observation in evidence_snapshot.observations:
        source_key = observation.source_key
        customer_source_type = resolve_luxian_0609_customer_document_type(source_key)
        if customer_source_type is None:
            continue
        try:
            document_rows = evidence_materials.document_rows(
                source_key, snapshot=evidence_snapshot
            )
        except EvidenceMaterialUnavailable:
            continue
        except (TypeError, ValueError):
            # 受控计算来源不一定属于 document_refs；只允许最终全部选中
            # 引用都被验证解析，不让无关计算来源使真实文书定位整体失效。
            continue
        selected_document_rows = tuple(
            (reference, row)
            for reference, row in document_rows
            if reference in selected_refs
        )
        if not selected_document_rows:
            continue
        selected_by_document_id: dict[str, set[str]] = {}
        for reference, row in selected_document_rows:
            document_id = next(
                (
                    _text(row.get(field))
                    for field in _IDENTITY_FIELDS
                    if _text(row.get(field))
                ),
                "",
            )
            if not document_id:
                if source_key == "inpat_registration":
                    # 登记是住院时间锚点，读取合同不提供文书 ID；它参与裁决，
                    # 但不应让已精确绑定的查房文书一起失去定位。
                    resolved.add(reference)
                    continue
                return []
            selected_by_document_id.setdefault(document_id, set()).add(reference)
        for document_id, selected_source_refs in selected_by_document_id.items():
            # 同 ID 的重复材料行必须全部被决策选择，才可安全折叠为一个客户文书；
            # 同一来源可同时投影多个各自完整的业务文书。
            same_document_refs = {
                reference
                for reference, row in document_rows
                if _row_has_identity(row, document_id)
            }
            coordinate_source = customer_source_type
            if not same_document_refs or selected_source_refs != same_document_refs:
                # 入院/出院诊断多行可共用真实父文书 ID；仅按明确外键定位同快照中
                # 唯一的父文书，保留原选中诊断事实，不把其他诊断算作证据。
                parent_source = _SHARED_PARENT_DOCUMENT_SOURCES.get(source_key)
                if parent_source is None or any(
                    _text(row.get("document_id")) != document_id
                    for reference, row in selected_document_rows if reference in selected_source_refs
                ):
                    return []
                try:
                    parents = [row for _reference, row in evidence_materials.document_rows(
                        parent_source, snapshot=evidence_snapshot
                    ) if _text(row.get("document_id")) == document_id]
                except (EvidenceMaterialUnavailable, TypeError, ValueError):
                    return []
                if len(parents) != 1:
                    return []
                coordinate_source = parent_source
            coordinate = {
                "source_type": coordinate_source,
                "source_document_id": document_id,
            }
            if source_key == "admission_record_diagnosis":
                diagnosis_names = tuple(
                    dict.fromkeys(
                        _text(row.get("diagnosis_name"))
                        for reference, row in selected_document_rows
                        if reference in selected_source_refs
                        and _text(row.get("diagnosis_name"))
                    )
                )
                if diagnosis_names:
                    excerpt = "；".join(diagnosis_names)
                    coordinate.update(
                        {
                            "field_path": "admission_record_diagnosis.diagnosis_name",
                            "evidence_excerpt": excerpt[:300]
                            + ("…" if len(excerpt) > 300 else ""),
                            "excerpt_kind": "字段级依据",
                        }
                    )
            resolved.update(selected_source_refs)
            located_by_ref.update(
                {reference: coordinate for reference in selected_source_refs}
            )
        if resolved == selected_refs:
            seen_coordinates: set[tuple[str, str]] = set()
            projected: list[dict[str, Any]] = []
            for reference in selected:
                coordinate = located_by_ref.get(reference)
                if coordinate is None:
                    # 仅已验证的无文书 ID 登记锚点没有客户文书坐标。
                    continue
                key = (coordinate["source_type"], coordinate["source_document_id"])
                if key in seen_coordinates:
                    continue
                seen_coordinates.add(key)
                projected.append(coordinate)
            if decision.rule_id == "LX0609-06-01-01":
                # 索引由执行器的有序引用定义；坐标仍由此处唯一投影，不重新关联医嘱。
                for coordinate in projected:
                    coordinate["decision_reference_positions"] = [
                        index for index, reference in enumerate(decision.fact_refs, 1)
                        if located_by_ref.get(reference) is not None
                        and (located_by_ref[reference]["source_type"], located_by_ref[reference]["source_document_id"])
                        == (coordinate["source_type"], coordinate["source_document_id"])
                    ]
            return projected
    return []


_COURSE_SOURCE_TYPES = frozenset(
    {"first_course_record", "daily_course_record", "senior_course_record"}
)


def _real_record_time(row: Mapping[str, Any]) -> str:
    """仅返回文书自身的记录时间；提交时间不是记录时间，缺失时不填。"""

    for field in ("record_time", "record_datetime"):
        value = _text(row.get(field)).replace("T", " ", 1)
        if value and _TIME_PATTERN.fullmatch(value):
            return value
    return ""


def _record_time(row: Mapping[str, Any]) -> str:
    candidate = authoritative_document_time_value(row)
    if candidate is None:
        candidate = next(
            (row.get(field) for field in _TIME_FIELDS if _text(row.get(field))),
            None,
        )
    value = _text(candidate).replace("T", " ", 1)
    return value if _TIME_PATTERN.fullmatch(value) else ""


def _excerpt(row: Mapping[str, Any], *, limit: int = 300) -> tuple[str, str]:
    matched = next(
        (
            (field, _text(row.get(field)))
            for field in _EXCERPT_FIELDS
            if _text(row.get(field))
        ),
        ("", ""),
    )
    field_path, value = matched
    compact = re.sub(r"\s+", " ", value).strip()
    if not compact:
        return "", ""
    return field_path, compact[:limit] + ("…" if len(compact) > limit else "")


def _discussion_excerpt(
    row: Mapping[str, Any], *, field_path: str = "", limit: int = 300
) -> tuple[str, str]:
    """Locate existing discussion content, never a title or a claim of absence.

    These are the same whitelisted content fields read by the preop executor.
    A document excerpt is only a navigation aid for reviewing the selected source;
    it does not establish that another item is missing or that extraction succeeded.
    """
    candidates = (
        ("record_content", row.get("record_content")),
        ("content", row.get("content")),
        ("host_summary", row.get("host_summary")),
        ("discuss_staff", row.get("discuss_staff")),
    )
    for path, raw in candidates:
        if field_path and path != field_path:
            continue
        if not isinstance(raw, str):
            continue
        compact = re.sub(r"\s+", " ", raw).strip()
        if compact:
            return path, compact[:limit] + ("…" if len(compact) > limit else "")
    return "", ""


def enrich_customer_evidence(
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    evidence_materials: Any,
    preferred_source_fields: Mapping[str, str] | None = None,
    strict_course_record_time: bool = False,
) -> list[dict[str, Any]]:
    """从本次执行的冻结材料中补充精确证据时间和短摘录。

    ``strict_course_record_time`` 为真时，病程证据的时间只取真实记录时间，
    不把提交时间标成记录时间（CT/MRI 报告后 24 小时类规则使用）。

    仅按来源和业务 ID 精确匹配；零条或多条命中均保持原引用，不猜测文书。
    """

    enriched_rows: list[dict[str, Any]] = []
    for raw_evidence in evidence_rows:
        evidence = dict(raw_evidence)
        source_type = _text(evidence.get("source_type")).lower()
        document_id = _text(evidence.get("source_document_id"))
        if not source_type or not document_id or evidence_materials is None:
            enriched_rows.append(evidence)
            continue
        try:
            source_rows = evidence_materials.rows(source_type)
        except Exception:
            enriched_rows.append(evidence)
            continue
        matches = [
            row
            for row in source_rows
            if isinstance(row, Mapping) and _row_has_identity(row, document_id)
        ]
        if len(matches) != 1:
            enriched_rows.append(evidence)
            continue
        matched = matches[0]
        if matched.get("source_version_key"):
            evidence["source_document_id"] = str(matched["source_version_key"])
        record_time = (
            _real_record_time(matched)
            if strict_course_record_time and source_type in _COURSE_SOURCE_TYPES
            else _record_time(matched)
        )
        # 显式字段是来源约束；字段缺失时不得用另一字段正文填充旧坐标。
        explicit_discussion_field = (
            _text(evidence.get("field_path")) if source_type == "presurg_discussion" else ""
        )
        field_path, excerpt = (
            _discussion_excerpt(matched, field_path=explicit_discussion_field)
            if source_type == "presurg_discussion"
            else _excerpt(matched)
        )
        preferred = (preferred_source_fields or {}).get(source_type)
        if preferred and not explicit_discussion_field:
            value = matched.get(preferred)
            path = preferred
            if preferred not in matched:
                schema = matched.get("v2_schema")
                if isinstance(schema, str):
                    try:
                        schema = json.loads(schema)
                    except (TypeError, ValueError):
                        schema = None
                if isinstance(schema, Mapping):
                    value = schema.get(preferred)
                    path = f"v2_schema.{preferred}"
            field_path = path
            excerpt = _text(value)[:300]
            evidence["field_path"] = field_path
            evidence["evidence_excerpt"] = excerpt or "参与人员字段为空或未取得"
            evidence["excerpt_kind"] = "字段级依据"
        if record_time and not _text(evidence.get("record_time")):
            evidence["record_time"] = record_time
        if excerpt and not _text(evidence.get("evidence_excerpt")):
            if field_path and not _text(evidence.get("field_path")):
                evidence["field_path"] = field_path
            evidence["evidence_excerpt"] = excerpt
            evidence["excerpt_kind"] = (
                "字段级依据" if source_type == "presurg_discussion" else "文书级依据"
            )
        enriched_rows.append(evidence)
    return enriched_rows
