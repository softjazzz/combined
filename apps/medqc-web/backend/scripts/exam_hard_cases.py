"""真实模型对照前固定的合成难例及答案；不读取病例、配置或凭据。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


CATALOG_VERSION = "exam-hard-catalog-v1"


@dataclass(frozen=True)
class HardCase:
    name: str
    rows_by_source: dict
    gold: tuple[tuple[int, str, str], ...]
    guard_only: bool = False

    def rows(self):
        return deepcopy(self.rows_by_source)

    def projection(self):
        from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection

        return build_exam_lab_text_projection(rows_by_source=self.rows())

    def expected_kinds(self, projection):
        from app.services.luxian_0609 import exam_result_record_check as check

        by_id = {doc_id: ref for ref, (source, doc_id) in projection.source_document_refs.items()
                 if source == "daily_course_record"}
        result = {(position, by_id[doc_id]): kind for position, doc_id, kind in self.gold}
        actual = {(position, ref) for position, (_, refs) in check._targets(projection).items() for ref in refs}
        if set(result) != actual:
            raise ValueError("fixed catalog no longer matches the formal candidate set")
        return result


def _single(name, text, kind, *, guard=False):
    return HardCase(name, {
        "exam_master": ({"document_id": "SYN-REPORT-1", "exam_id": "SYN-EX-1", "exam_name": "胸部CT平扫",
                         "exam_time": "2026-01-02 10:00:00", "report_time": "2026-01-02 11:00:00",
                         "exam_conclusion": "右肺下叶见8mm结节影，考虑炎性结节；建议随访。"},),
        "daily_course_record": ({"document_id": "SYN-DOC-1", "record_time": "2026-01-02 15:00:00",
                                 "record_content": text},),
    }, ((1, "SYN-DOC-1", kind),), guard)


def hard_cases():
    yield _single("same_exam_laterality", "本次胸部CT提示左肺下叶小结节。", "result_conflicting")
    yield _single("explicit_other_modality", "另一次头颅MRI（SYN-OTHER）提示左额叶小结节。", "other_exam")
    yield HardCase("repeated_similar_events", {
        "exam_master": (
            {"document_id": "SYN-REPORT-1", "exam_id": "SYN-EX-1", "exam_name": "胸部CT平扫",
             "exam_time": "2026-01-02 09:00:00", "report_time": "2026-01-02 10:00:00",
             "exam_conclusion": "2026-01-02 10:00胸部CT：左肺上叶见5mm结节影，考虑炎性。"},
            {"document_id": "SYN-REPORT-2", "exam_id": "SYN-EX-2", "exam_name": "胸部CT复查",
             "exam_time": "2026-01-02 13:00:00", "report_time": "2026-01-02 14:00:00",
             "exam_conclusion": "2026-01-02 14:00胸部CT：右肺下叶见12mm结节影，较前增大。"},
        ),
        "daily_course_record": (
            {"document_id": "SYN-DOC-1", "record_time": "2026-01-02 12:00:00",
             "record_content": "10点那次胸部CT在左上肺发现约0.5cm小结节，倾向炎症。"},
            {"document_id": "SYN-DOC-2", "record_time": "2026-01-02 15:00:00",
             "record_content": "14点复查胸部CT右下肺结节约1.2cm，较前增大。"},
        ),
    }, ((1, "SYN-DOC-1", "result_recorded"), (1, "SYN-DOC-2", "other_exam"),
        (2, "SYN-DOC-2", "result_recorded")))
    yield _single("clinical_reinterpretation",
        "已阅本次CT：右下肺约0.8cm小结节。报告考虑炎性，临床另考虑肿瘤可能，拟随访。", "result_recorded")
    yield _single("same_exam_negation", "已阅本次胸部CT，未见右下肺结节或其他异常。", "result_conflicting")
    recorded = "已阅本次胸部CT：右肺下叶小结节，倾向炎性，继续观察。"
    noise = ("一般情况平稳，继续观察。" * 600)
    yield _single("long_readable_tail", noise[:5400] + "。" + recorded, "result_recorded")
    yield _single("long_truncated_tail", noise[:6600] + "。" + recorded, "result_recorded", guard=True)


def planned_runs(rounds=2):
    """同一场景两轮反转先后顺序；截断保护仅一轮，不能计作35B质量样本。"""
    for case_index, case in enumerate(hard_cases()):
        for round_index in range(1 if case.guard_only else rounds):
            arms = ("reference", "cascade") if (case_index + round_index) % 2 == 0 else ("cascade", "reference")
            for arm in arms:
                yield case, round_index + 1, arm


def score_attempt(audit, expected, *, guard_only=False):
    """参考答案在调用前固定。误报/漏报按质控缺陷方向统计，不把Flash当金标准。"""
    pairs = []
    for pair in audit["pairs"]:
        key = (pair["event_position"], pair["course_doc_ref"])
        wanted = expected[key]
        covered = pair["event_position"] in audit["recorded_refs"]
        pairs.append({"event_position": key[0], "course_doc_ref": key[1], "gold": wanted,
            "actual": pair["quote_type"], "category_correct": wanted == pair["quote_type"],
            "covered": covered, "conflict_correct": pair["accepted_conflict"] == (wanted == "result_conflicting")})
    events = []
    for position in sorted({key[0] for key in expected}):
        gold_recorded = any(kind == "result_recorded" for (p, _), kind in expected.items() if p == position)
        actual_recorded = bool(audit["recorded_refs"][position]) if position in audit["recorded_refs"] else None
        events.append({"event_position": position, "gold_recorded": gold_recorded,
            "actual_recorded": actual_recorded,
            "false_positive_defect": not guard_only and gold_recorded and actual_recorded is False,
            "false_negative_defect": not guard_only and not gold_recorded and actual_recorded is True})
    return {"protocol_valid": audit["protocol_valid"], "guard_only": guard_only,
            "coverage_complete": audit["coverage_complete"], "pairs": pairs, "events": events,
            "category_mismatches": sum(not p["category_correct"] for p in pairs),
            "conflict_mismatches": sum(not p["conflict_correct"] for p in pairs) if not guard_only else None,
            "false_positive_defects": sum(p["false_positive_defect"] for p in events),
            "false_negative_defects": sum(p["false_negative_defect"] for p in events)}
