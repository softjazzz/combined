"""06-01-04 合成 POC 的旁路验收；不选择医学状态、不调用模型。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609.exam_lab_fact_extraction import (
    _material_document_refs_by_row, build_exam_lab_text_projection, events_for_family,
)


@dataclass(frozen=True)
class SyntheticCase:
    name: str
    course: str
    expected_kind: str

    def rows(self) -> dict[str, tuple[dict, ...]]:
        # 与第一轮真实 POC 完全相同；不在原始输入中补造评价上界。
        return {
            "exam_master": ({"exam_id": "SYN-EX-1", "exam_name": "胸部CT平扫",
                             "exam_time": "2026-01-02 10:00:00", "report_time": "2026-01-02 11:00:00",
                             "exam_conclusion": "右肺下叶见8mm结节影，考虑炎性结节；建议随访。"},),
            "daily_course_record": ({"document_id": "SYN-DOC-1", "record_time": "2026-01-02 15:00:00",
                                     "record_content": self.course},),
        }

    def projection(self):
        return build_exam_lab_text_projection(rows_by_source=self.rows())


CASES = (
    SyntheticCase("result_paraphrase", "已阅本次胸部CT：右肺下叶小结节，倾向炎性，继续观察。", "result_recorded"),
    SyntheticCase("plan_only", "拟完善胸部CT检查，进一步了解病变情况。", "plan_only"),
    SyntheticCase("external_prior_exam", "外院既往胸部CT曾见右肺下叶结节，本次检查结果尚待回报。", "other_exam"),
)
MODELS = ("qwen3.8-flash", "qwen3.6-35b-a3b")
REPORT_VERSION = "exam-poc-acceptance-v2"


def inspect_completion(projection, completion: Mapping[str, Any], *, expected_kinds=None, source_rows=None) -> dict:
    """先调用真实解析器，再展示原始分类；协议通过不代表语义正确。"""
    targets = check._targets(projection)
    expected = {position: refs for position, (_, refs) in targets.items() if refs}
    reports = {position: report for position, (report, _) in targets.items() if expected.get(position)}
    input_complete = all(check._input_complete_for_event(projection, position, refs)
                         for position, (_, refs) in targets.items())
    try:
        recorded, conflicts = check._parse(completion, projection, expected, reports)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        return {"protocol_valid": False, "validation_reason": str(error),
                "validation_details": [issue.reason for issue in getattr(error, "issues", ())],
                "pairs": [], "recorded_refs": {}, "conflict_refs": {}, "coverage_complete": False,
                "input_projection_complete": input_complete}
    recorded, conflicts, incomplete = check._accept_complete_input(projection, expected, recorded, conflicts)
    raw = check._json_response_object(check._response_content(completion))
    events = events_for_family(projection, "exam")
    source_rows = source_rows or {}
    identities = {material_ref: {"source_key": source, **{
        key: source_rows[source][index - 1].get(key) for key in ("document_id", "exam_id", "test_id")
        if source_rows[source][index - 1].get(key)}}
        for (source, index), material_ref in _material_document_refs_by_row(source_rows).items()}
    pairs = []
    for item in raw["docs"]:
        position, ref = item["event_position"], item["course_doc_ref"]
        wanted = (expected_kinds or {}).get((position, ref))
        pairs.append({**item, "event_refs": list(events[position - 1].document_refs),
                      "event_material_refs": [(projection.safe_refs or {}).get(event_ref)
                                              for event_ref in events[position - 1].document_refs],
                      "event_sources": [identities.get((projection.safe_refs or {}).get(event_ref))
                                        for event_ref in events[position - 1].document_refs],
                      "source_document": list((projection.source_document_refs or {}).get(ref, ())),
                      "expected_quote_type": wanted,
                      "category_matches_expectation": None if wanted is None else item["quote_type"] == wanted,
                      "accepted_recorded": ref in recorded.get(position, ()),
                      "accepted_conflict": ref in conflicts.get(position, ())})
    return {"protocol_valid": True, "validation_reason": None, "validation_details": [],
            "pairs": pairs, "recorded_refs": recorded, "conflict_refs": conflicts,
            "expected_pairs": sum(map(len, expected.values())), "covered_pairs": len(pairs),
            "coverage_complete": set(recorded) == set(expected), "input_projection_complete": input_complete,
            "incomplete_event_positions": sorted(incomplete)}


def compare_arms(reference: dict, candidate: dict) -> dict:
    """分别比较类别、事件引用、冲突和方向；不把 Flash 当作医学金标准。"""
    def indexed(arm):
        return {(item["event_position"], item["course_doc_ref"]): item for item in arm["pairs"]}

    left, right = indexed(reference), indexed(candidate)
    differences = []
    for key in sorted(set(left) | set(right)):
        a, b = left.get(key), right.get(key)
        fields = ("quote_type", "event_refs", "event_material_refs", "event_sources", "source_document",
                  "accepted_recorded", "accepted_conflict")
        changed = [field for field in fields if (a or {}).get(field) != (b or {}).get(field)]
        if changed:
            differences.append({"event_position": key[0], "course_doc_ref": key[1], "fields": changed,
                                "reference_class": (a or {}).get("quote_type"),
                                "candidate_class": (b or {}).get("quote_type")})
    valid = reference["protocol_valid"] and candidate["protocol_valid"]
    return {"both_protocol_valid": valid, "differences": differences,
            "same_recorded_direction": valid and reference["recorded_refs"] == candidate["recorded_refs"],
            "same_conflict_facts": valid and reference["conflict_refs"] == candidate["conflict_refs"],
            "manual_review_required": bool(differences) or not valid}


def validate_recording(payload: dict) -> list[tuple[SyntheticCase, dict, list[dict]]]:
    """旧报告没有请求归属时，仅接受固定完整顺序；新报告还必须核对显式归属。"""
    if not isinstance(payload, dict) or payload.get("synthetic_only") is not True or payload.get("database_writes") != 0:
        raise ValueError("recording is not a synthetic database-free POC")
    if payload.get("models") != list(MODELS):
        raise ValueError("unexpected recording models")
    results, requests = payload.get("results"), payload.get("requests")
    if not isinstance(results, list) or not isinstance(requests, list) or len(requests) > 12:
        raise ValueError("invalid recording entries")
    # 旧报告的对应关系只由已知循环和每个 arm 的请求数重建；不能随意重排。
    if len(results) not in {2, 4, 6}:
        raise ValueError("incomplete recording arms")
    segments, offset = [], 0
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError("invalid recording result")
        case, arm = CASES[index // 2], ("reference", "cascade")[index % 2]
        if result.get("case") != case.name or result.get("arm") != arm:
            raise ValueError("ambiguous recording order")
        count = result.get("http_calls")
        if type(count) is not int or not 1 <= count <= 8:
            raise ValueError("invalid arm request count")
        segment = requests[offset:offset + count]
        if len(segment) != count:
            raise ValueError("missing recorded requests")
        for attempt, request in enumerate(segment):
            if not isinstance(request, dict):
                raise ValueError("invalid recording request")
            model = MODELS[0] if arm == "reference" else (MODELS[1] if attempt == 0 else MODELS[0])
            if (request.get("model") != model or request.get("returned_model") != model
                    or request.get("status") != "success" or request.get("http_status") != 200
                    or request.get("enable_thinking_sent") is not False
                    or not isinstance(request.get("completion"), dict)
                    or request["completion"].get("model") != model):
                raise ValueError("recorded request attribution mismatch or incomplete HTTP response")
            for key, value in (("case", case.name), ("arm", arm), ("attempt", attempt + 1)):
                if key in request and request[key] != value:
                    raise ValueError("explicit request attribution mismatch")
        segments.append((case, result, deepcopy(segment)))
        offset += count
    if offset != len(requests):
        raise ValueError("unassigned recorded requests")
    return segments


def inspect_recording(payload: dict) -> dict:
    arms, comparisons = [], []
    for case, result, requests in validate_recording(payload):
        p = case.projection()
        kinds = {(position, ref): case.expected_kind for position, (_, refs) in check._targets(p).items() for ref in refs}
        attempts = [inspect_completion(p, item["completion"], expected_kinds=kinds, source_rows=case.rows()) for item in requests]
        recoveries = []
        for index, attempt in enumerate(attempts[:-1]):
            if attempt["protocol_valid"]:
                raise ValueError("recording has an unexplained request after an accepted answer")
            recoveries.append({"after_attempt": index + 1, "reason": attempt["validation_reason"],
                               "details": attempt["validation_details"]})
        upgrades = recoveries[:1] if result["arm"] == "cascade" else []
        arms.append({"case": case.name, "arm": result["arm"], "model_sequence": [r["model"] for r in requests],
                     "attempts": attempts, "accepted": attempts[-1], "upgrade_count": len(upgrades),
                     "upgrade_reasons": upgrades, "protocol_retry_reasons": recoveries[len(upgrades):],
                     "recorded_upgrade_observed": bool(upgrades)})
        if result["arm"] == "cascade":
            comparisons.append({"case": case.name, **compare_arms(arms[-2]["accepted"], arms[-1]["accepted"])})
    return {"schema_version": REPORT_VERSION, "synthetic_only": True, "new_model_calls": 0,
            "business_database_writes": 0, "new_real_upgrade_tested": False,
            "arms": arms, "comparisons": comparisons,
            "semantic_expectations": {
                "checked_pairs": sum(len(a["accepted"]["pairs"]) for a in arms),
                "category_mismatches": sum(p["category_matches_expectation"] is False
                                           for a in arms for p in a["accepted"]["pairs"]),
                "interpretation": "分类差异须单独复核，方向一致不能替代医学质量验收"},
            "limitations": ["仅重放既有专项应答；主抽取应答使用固定夹具",
                            "原始三例未提供评价上界，不补造超时结论",
                            "协议和引用校验不能证明分类语义正确", "没有新增真实升级或性能验收"]}
