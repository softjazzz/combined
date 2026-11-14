"""出院诊疗经过：最小语义事实抽取，Python校验引用并形成结果。"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any, Mapping

import jsonschema

from . import discharge_course_stages as stages
from .transfer_documentation import select_transfer_order_rows
from ..course_quality.shared import response_json_payload
from ..evidence_material import EvidenceMaterialTruncated, EvidenceMaterialUnavailable
from ..llm_prompt_privacy import redact_luxian_0609_patient_privacy

RULE_ID = "LX0609-08-01-05"
FIELDS = stages.FIELDS
# 用户口径（2026-10-11）：重要住院事件由程序按结构化来源确定，模型只核对出院记录是否提到。
# 每个来源：(事件类型, 重要性依据, 客户可读名称)。
EVENT_SOURCES = {
    "surgery_record": ("surgery", "actual_procedure", "实际手术"),
    "pathology_exam_report": ("test", "diagnostic_basis", "病理结果"),
    "bloodtrans_record": ("treatment", "major_treatment", "输血"),
    "rescue_record": ("treatment", "major_treatment", "抢救"),
    "transfer_out_record": ("change", "major_change", "转科"),
    "transfer_in_record": ("change", "major_change", "转科"),
    "crisis_value_record": ("change", "major_change", "危急值"),
    # 转科优先按正式转科医嘱逐次确定：医嘱写明转入科室，转入/转出文书常只有标题和时间，
    # 且同一次转科会拆成转出、转入两份文书；读不到转科医嘱时才退回文书事件。
    "inpat_nondrug_order": ("change", "major_change", "转科"),
}
TRANSFER_DOCUMENT_SOURCES = ("transfer_out_record", "transfer_in_record")
SOURCES = ("discharge_record", *EVENT_SOURCES, "discharge_record_diagnosis")
# 历史已发布事实曾含病程来源（旧阶段 B），交付校验仍须可读。
PUBLISHED_SOURCES = (*SOURCES, "mr_bloodtrans", "daily_course_record", "senior_course_record")
PROTOCOL_ATTEMPTS = 2
MAX_INPUT_CHARS = 60000
MAX_DOCUMENTS = 80
MAX_PROMPT_CHARS = 180000
SCHEMA = stages.VERSION


@dataclass(frozen=True)
class CourseOutcome:
    state: str
    reason: str
    refs: tuple[str, ...] = ()
    facts: Mapping[str, Any] | None = None
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0

    def __post_init__(self) -> None:
        if self.facts is None:
            object.__setattr__(self, "facts", {
                "verification_kind": "discharge_course_pending", "state": self.state,
            })


def _text(row: Mapping[str, Any], source: str) -> str:
    fields = {
        "discharge_record": ("treatment_course", "record_content", "discharge_condition", "discharge_sympton_condition",
                             "admission_condition", "positive_assist_exam", "condition_transform", "discharge_order"),
        "discharge_record_diagnosis": ("diagnosis_type", "diagnosis_name", "diagnosis_code"),
        "surgery_record": ("surgery_name", "surgery_process", "record_content", "surgery_begin_time", "surgery_end_time"),
        "pathology_exam_report": ("specimen_name", "diagnosis", "microscope_findings", "record_content", "report_datetime"),
        "transfer_out_record": ("document_title", "transferout_department", "transferin_department",
                                "transfer_purpose", "transfer_date", "submit_datetime", "record_content"),
        "transfer_in_record": ("document_title", "transferout_department", "transferin_department",
                               "transfer_purpose", "transfer_date", "submit_datetime", "record_content"),
        "inpat_nondrug_order": ("order_name", "prescribed_datetime"),
        "crisis_value_record": ("document_title", "record_datetime", "dept_name", "record_content"),
    }.get(source, ("document_title", "record_time", "record_content"))
    return "\n".join(f"{key}：{row[key]}" for key in fields if str(row.get(key) or "").strip())


_segments = stages.segments


def _event_row(row: Mapping[str, Any], source: str) -> bool:
    """尚未回报结果的病理申请不构成住院事件，不作为缺项。"""
    if source == "pathology_exam_report":
        return any(str(row.get(key) or "").strip() for key in ("diagnosis", "microscope_findings", "record_content"))
    return True


def _transfer_order_rows(materials: Any, snapshot: Any) -> list[tuple[Any, Mapping[str, Any]]]:
    """正式转科医嘱（复用 10-02 转科判定的筛选口径）；医嘱不可读时返回空，退回文书事件。"""
    try:
        rows = materials.document_rows("inpat_nondrug_order", snapshot=snapshot)
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable, ValueError):
        return []
    selected = {id(row) for row in select_transfer_order_rows([row for _, row in rows])}
    return [(ref, row) for ref, row in rows if id(row) in selected]


def _objective_events(docs: list[dict]) -> list[dict]:
    """程序按结构化来源逐份确定事件；事件坐标为该来源文书全文，重要性依据即其本身。"""
    events = []
    for d in docs:
        if d["source"] not in EVENT_SOURCES:
            continue
        kind, importance, label = EVENT_SOURCES[d["source"]]
        span = {"document_index": d["document_index"], "start": 0, "end": len(d["text"])}
        events.append({"event_id": len(events) + 1, "kind": kind, "label": label, **span,
                       "importance_kind": importance, "importance_refs": [dict(span)]})
    return events


def content_state(facts: Mapping[str, Any]) -> str:
    """仅供执行阶段计算结果；交付校验只检查与这一事实组合是否自洽。"""
    states = [c["state"] for c in facts["checks"]]
    states.extend(m["state"] for event in facts["events"] for m in event["matches"])
    if "missing" in states:
        return "non_compliant"
    incomplete = any(v in {"failed", "uncertain"} for v in facts.get("review", {}).get("stages", {}).values())
    return "data_gap" if "uncertain" in states or incomplete else "compliant"


async def evaluate_discharge_course_content(*, snapshot: Any, materials: Any, llm_client: Any) -> CourseOutcome:
    docs, refs = [], []
    try:
        discharge_rows = materials.document_rows("discharge_record", snapshot=snapshot)
        if not discharge_rows:
            return CourseOutcome("not_applicable", "eligibility_not_met")
        transfer_orders = _transfer_order_rows(materials, snapshot)
        for source in SOURCES:
            if source == "inpat_nondrug_order":
                rows = transfer_orders
            elif source in TRANSFER_DOCUMENT_SOURCES and transfer_orders:
                continue
            else:
                rows = discharge_rows if source == "discharge_record" else materials.document_rows(source, snapshot=snapshot)
            for ref, row in rows:
                if not _event_row(row, source):
                    continue
                parent = None
                if source == "discharge_record_diagnosis":
                    parents = [i + 1 for i, (_, discharge) in enumerate(discharge_rows)
                               if row.get("document_id") and row.get("document_id") == discharge.get("document_id")]
                    if len(parents) != 1:
                        return CourseOutcome("data_gap", "source_readiness_unproven", tuple(refs))
                    parent = parents[0]
                text = redact_luxian_0609_patient_privacy(_text(row, source))
                if not text.strip():
                    return CourseOutcome("data_gap", "source_readiness_unproven")
                refs.append(ref)
                docs.append({"document_index": len(docs) + 1, "source": source,
                             **({"parent_document_index": parent} if parent is not None else {}),
                             "document_ref": ref, "text": text})
    except EvidenceMaterialTruncated:
        return CourseOutcome("data_gap", "source_truncated")
    except (EvidenceMaterialUnavailable, ValueError):
        return CourseOutcome("data_gap", "source_unavailable")
    if len(docs) > MAX_DOCUMENTS or sum(len(d["text"]) for d in docs) > MAX_INPUT_CHARS:
        return CourseOutcome("data_gap", "source_truncated", tuple(refs))
    if llm_client is None:
        return CourseOutcome("data_gap", "source_readiness_unproven", tuple(refs))
    metrics = dict(llm_call_count=0, prompt_tokens=0, completion_tokens=0, total_tokens=0, api_time=0.0)

    async def call(stage, events=()):
        events = list(events)
        try:
            stage_prompt = stages.prompt(stage, docs, events)
            if len(stage_prompt) > MAX_PROMPT_CHARS:
                return None, "failed"
            options = {}
            supports_schema = getattr(llm_client, "supports_strict_json_schema", None)
            if callable(supports_schema) and supports_schema():
                options["response_format"] = {"type": "json_schema", "json_schema": {
                    "name": "discharge_course_" + stage, "strict": True,
                    "schema": stages.schema(stage, docs, events)}}
        except (ValueError, TypeError, KeyError, jsonschema.ValidationError):
            return None, "failed"
        # 用户口径（2026-10-11）：协议违规可确定识别时重试 1 次，仍违规才拒收；传输错误不重试。
        # 原样重发常得到相同输出，重试时附上违反的合同条款。
        attempt_prompt = stage_prompt
        for attempt in range(PROTOCOL_ATTEMPTS):
            metrics["llm_call_count"] += 1
            try:
                response = await llm_client.generate(attempt_prompt,
                    max_completion_tokens=8192, allow_length_retry=False, enable_thinking=False, **options)
            except Exception:
                # 其他阶段已完成事实仍然保留。
                return None, "failed"
            try:
                usage = response.get("usage") or {}
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    metrics[key] += int(usage.get(key) or 0)
                metrics["api_time"] += float(response.get("_api_time") or 0)
                payload = response_json_payload(response)
                return stages.validate_response(stage, payload, docs, events), "complete"
            except (ValueError, TypeError, KeyError, AttributeError, jsonschema.ValidationError) as error:
                if attempt + 1 == PROTOCOL_ATTEMPTS:
                    return None, "failed"
                choices = response.get("choices")
                previous = (choices[0].get("message", {}).get("content") if choices
                            else response.get("content", response.get("text")))
                attempt_prompt = stages.retry_prompt(stage_prompt, error, previous)
        return None, "failed"

    events = _objective_events(docs)
    discharges = [d for d in docs if d["source"] == "discharge_record"]
    if events:
        (a, a_state), (c, c_state) = await asyncio.gather(call("A"), call("C", events))
    else:
        (a, a_state), (c, c_state) = await call("A"), (None, "skipped")
    checks, conflicts = a if a is not None else ([
        {"document_index": d["document_index"], "field": f, "state": "uncertain", "start": None, "end": None}
        for d in discharges for f in FIELDS], [])
    matches, c_conflicts = c if c is not None else ([
        [{"document_index": d["document_index"], "state": "uncertain", "start": None, "end": None}
         for d in discharges] for _ in events], [])
    facts = {
        "verification_kind": "discharge_course_content",
        "checks": checks,
        "events": [{"document_index": e["document_index"], "kind": e["kind"],
                    "start": e["start"], "end": e["end"], "matches": matches[i]} for i, e in enumerate(events)],
        "documents": [{"document_index": d["document_index"], "source": d["source"],
                       **({"parent_document_index": d["parent_document_index"]} if "parent_document_index" in d else {}),
                       "document_ref": d["document_ref"], "text_length": len(d["text"])} for d in docs],
        "review": {"schema_version": SCHEMA, "stages": {"A": a_state, "B": "complete", "C": c_state},
                   "event_basis": [{"event_index": i, "importance_kind": e["importance_kind"],
                                    "anchors": e["importance_refs"]} for i, e in enumerate(events)],
                   "unresolved_events": [], "conflicts": conflicts + c_conflicts},
    }
    state = content_state(facts)
    reason = {"compliant": "requirement_satisfied", "non_compliant": "requirement_violated",
              "data_gap": "source_readiness_unproven"}[state]
    return CourseOutcome(state, reason, tuple(refs), facts, **metrics)
