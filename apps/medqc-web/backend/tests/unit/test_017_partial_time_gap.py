"""017 部分记录缺时不能遮蔽已被完整文书证明的复制。"""

import pytest

from app.services.luxian_0609.course_quality.rules_016_017 import (
    _assess_copy,
    _review_copy_candidates,
    _selected_copy_document_refs,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


_BODY = "患者持续咳嗽伴活动后气促，双肺呼吸音粗，可闻及湿性啰音，继续抗感染及化痰治疗，复查血常规和胸部影像。"
_OTHER = "术后切口干燥无渗出，胃肠功能逐渐恢复，已经开始下床行走，今日更换敷料并指导康复训练，逐步增加清淡饮食。"


def _documents(right_body=_BODY, valid_count=2, missing_first=False):
    valid = [
        {"document_id": "round-1", "record_time": "2026-01-01 08:00:00", "record_content": _BODY},
        {"document_id": "round-2", "record_time": "2026-01-02 08:00:00", "record_content": right_body},
    ][:valid_count]
    missing = {"document_id": "round-missing", "record_content": _BODY}
    return {"daily_course_record": [missing, *valid] if missing_first else [*valid, missing], "senior_course_record": []}


@pytest.mark.parametrize("missing_first", [False, True])
def test_missing_time_does_not_hide_deterministic_copy(missing_first):
    docs = _documents(missing_first=missing_first)
    outcome = _assess_copy(docs, source_complete=True)
    assert (outcome.status, outcome.reason_code) == ("non_compliant", "copy_similarity_threshold_exceeded")
    assert outcome.safe_metadata["comparable_document_count"] == 2
    assert outcome.safe_metadata["missing_time_document_count"] == 1
    assert outcome.safe_metadata["precise_pair_count"] == 1

    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=docs.get(source, []), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-017",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
    )
    selected = _selected_copy_document_refs(outcome=outcome, snapshot=session.snapshot, materials=session.materials)
    assert {row["document_id"] for ref, row in session.materials.document_rows("daily_course_record", snapshot=session.snapshot) if ref in selected} == {"round-1", "round-2"}


@pytest.mark.parametrize("valid_count,right_body", [(0, _BODY), (1, _BODY), (2, _OTHER), (2, _BODY.replace("持续咳嗽", "间断咳嗽")), (2, "患者病情稳定，生命体征平稳，一般情况良好，查体无明显异常，继续当前治疗，观察病情。")])
@pytest.mark.asyncio
async def test_unproven_copy_remains_gap_without_llm(valid_count, right_body):
    class RejectLLM:
        calls = 0

        async def generate(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("资料缺口分支不得新增模型调用")

    outcomes = []
    for missing_first in (False, True):
        outcome = _assess_copy(_documents(right_body, valid_count, missing_first), source_complete=True)
        assert (outcome.status, outcome.reason_code) == ("data_gap", "copy_authoritative_time_missing")
        assert outcome.safe_metadata["comparable_document_count"] == valid_count
        assert outcome.safe_metadata["missing_time_document_count"] == 1
        assert outcome.safe_metadata["precise_pair_count"] == (1 if valid_count == 2 else 0)
        assert outcome.review_candidates == ()
        client = RejectLLM()
        assert await _review_copy_candidates(outcome, client) is outcome
        assert client.calls == 0
        outcomes.append(outcome.safe_metadata)
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("has_missing", [False, True])
def test_identical_template_shell_preserves_exemption(has_missing):
    template = "患者病情稳定，生命体征平稳，一般情况良好，查体无明显异常，继续当前治疗，观察病情。"
    docs = _documents(right_body=template)
    docs["daily_course_record"][0]["record_content"] = template
    if not has_missing:
        docs["daily_course_record"].pop()
    outcome = _assess_copy(docs, source_complete=True)
    assert outcome.status == ("data_gap" if has_missing else "compliant")
    assert outcome.reason_code == ("copy_authoritative_time_missing" if has_missing else "copy_template_shell_only")
    assert outcome.safe_metadata["template_shell_only"] is True
    assert outcome.review_candidates == ()
