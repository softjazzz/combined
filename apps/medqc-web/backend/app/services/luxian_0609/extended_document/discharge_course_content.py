"""出院诊疗经过：最小语义事实抽取，Python校验引用并形成结果。"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any, Mapping

import jsonschema

from . import discharge_course_stages as stages
from ..course_quality.shared import response_json_payload
from ..evidence_material import EvidenceMaterialTruncated, EvidenceMaterialUnavailable
from ..llm_prompt_privacy import redact_luxian_0609_patient_privacy

RULE_ID = "LX0609-08-01-05"
FIELDS = stages.FIELDS
SOURCES = ("discharge_record", "daily_course_record", "senior_course_record", "surgery_record", "discharge_record_diagnosis")
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
    }.get(source, ("record_content",))
    return "\n".join(f"{key}：{row[key]}" for key in fields if str(row.get(key) or "").strip())


_segments = stages.segments


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
        for source in SOURCES:
            rows = discharge_rows if source == "discharge_record" else materials.document_rows(source, snapshot=snapshot)
            for ref, row in rows:
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
            metrics["llm_call_count"] += 1
            response = await llm_client.generate(stage_prompt,
                max_completion_tokens=8192, allow_length_retry=False, enable_thinking=False, **options)
            usage = response.get("usage") or {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                metrics[key] += int(usage.get(key) or 0)
            metrics["api_time"] += float(response.get("_api_time") or 0)
            payload = response_json_payload(response)
            return stages.validate_response(stage, payload, docs, events), "complete"
        except (ValueError, TypeError, KeyError, jsonschema.ValidationError):
            return None, "failed"
        except Exception:
            # 同一阶段不追加重试；其他阶段已完成事实仍然保留。
            return None, "failed"

    (a, a_state), (b, b_state) = await asyncio.gather(call("A"), call("B"))
    discharges = [d for d in docs if d["source"] == "discharge_record"]
    checks, conflicts = a if a is not None else ([
        {"document_index": d["document_index"], "field": f, "state": "uncertain", "start": None, "end": None}
        for d in discharges for f in FIELDS], [])
    events, unresolved = b if b is not None else ([], [])
    if unresolved:
        b_state = "uncertain"
    c, c_state = await call("C", events) if events else (None, "skipped")
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
        "review": {"schema_version": SCHEMA, "stages": {"A": a_state, "B": b_state, "C": c_state},
                   "event_basis": [{"event_index": i, "importance_kind": e["importance_kind"],
                                    "anchors": e["importance_refs"]} for i, e in enumerate(events)],
                   "unresolved_events": unresolved, "conflicts": conflicts + c_conflicts},
    }
    state = content_state(facts)
    reason = {"compliant": "requirement_satisfied", "non_compliant": "requirement_violated",
              "data_gap": "source_readiness_unproven"}[state]
    return CourseOutcome(state, reason, tuple(refs), facts, **metrics)
