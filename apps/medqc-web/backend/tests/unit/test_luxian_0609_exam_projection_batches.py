from datetime import datetime, timedelta
import json

import pytest

from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
)
from app.services.luxian_0609 import native_exam_lab_execution as native
from test_luxian_0609_native_exam_lab_execution import _typed_session


def _rows(count=18, text_size=80):
    reports, courses = [], []
    for index in range(count):
        anchor = datetime(2026, 1, 1, 8) + timedelta(days=index * 5)
        reports.append(
            {
                "test_id": f"TEST-{index}",
                "test_type": "血培养",
                "report_time": anchor.isoformat(),
                "result": "培养阳性，检出合成菌。",
            }
        )
        for hour in (1, 2):
            courses.append(
                {
                    "document_id": f"DOC-{index}-{hour}",
                    "record_time": (anchor + timedelta(hours=hour)).isoformat(),
                    "record_content": "合成病程。"
                    + "甲" * text_size
                    + f"末尾标记{index}。",
                }
            )
    return {"labtest_master": tuple(reports), "daily_course_record": tuple(courses)}


def test_projection_batches_preserve_complete_event_windows_and_global_refs():
    from app.services.luxian_0609.exam_lab_projection_batching import (
        build_exam_lab_projection_batches,
    )

    rows = _rows()
    legacy = build_exam_lab_text_projection(rows_by_source=rows)
    assert legacy.course_projection_truncated
    plan = build_exam_lab_projection_batches(rows_by_source=rows)
    assert len(plan.batches) > 1
    assert len(plan.projection.course_times) == 36
    covered = []
    for batch in plan.batches:
        assert len(batch.projection.course_times) <= 32
        assert len(batch.projection.context) <= 32000
        assert not batch.projection.course_projection_truncated
        for (family, local), global_position in batch.event_positions.items():
            covered.append((family, global_position))
            expected = plan.projection.event_course_refs[(family, global_position)]
            assert batch.projection.event_course_refs[(family, local)] == expected
            for ref in expected:
                assert (
                    batch.projection.course_texts[ref]
                    == plan.projection.course_texts[ref]
                )
                assert batch.projection.safe_refs[ref] == plan.projection.safe_refs[ref]
                assert batch.projection.course_texts[ref] in batch.projection.context
    assert covered == [("culture", p) for p in range(1, 19)]


class _AbsentClient:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        payload = json.loads(prompt.splitlines()[-1])
        for fact in payload["facts"]:
            fact.update(
                applicability="applicable",
                semantic_state="absent",
                positive_state="not_relevant",
            )
        return {"content": json.dumps(payload), "usage": {"total_tokens": 7}}


@pytest.mark.asyncio
@pytest.mark.parametrize(("count", "text_size"), [(18, 80), (8, 1900)])
async def test_native_exam_batches_evaluate_every_event_after_union_overflow(
    monkeypatch, count, text_size
):
    rows = _rows(count, text_size)
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )
    client = _AbsentClient()
    rule = "LX0609-06-03-03"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert len(client.prompts) > 1
    assert result.total_tokens == 7 * len(client.prompts)
    # 每个事件的报告都进入了抽取；末事件不能因前批已发现缺陷而省略。
    for index in range(1, count + 1):
        assert (
            sum(f"EVENT_DOC=L03-{index:02d}|" in prompt for prompt in client.prompts)
            == 1
        )


@pytest.mark.parametrize(("row_count", "text_size"), [(33, 80), (18, 1900)])
@pytest.mark.asyncio
async def test_single_exam_event_over_budget_remains_data_gap(
    monkeypatch, row_count, text_size
):
    rows = _rows(1, text_size)
    courses = tuple(
        dict(rows["daily_course_record"][0], document_id=f"OVER-{i}")
        for i in range(row_count)
    )
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=courses,
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )
    client = _AbsentClient()
    rule = "LX0609-06-03-03"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].reason_code == "source_truncated"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_native_exam_within_budget_keeps_original_single_projection(monkeypatch):
    rows = _rows(2)
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )
    client = _AbsentClient()
    rule = "LX0609-06-03-03"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert len(client.prompts) == 1
    original = build_exam_lab_text_projection(rows_by_source=rows)
    from app.services.luxian_0609.exam_lab_fact_extraction import (
        build_exam_lab_fact_prompt,
    )

    assert client.prompts[0] == build_exam_lab_fact_prompt(
        selected_rule_ids=(rule,), projection=original
    )


@pytest.mark.asyncio
async def test_native_exam_single_projection_keeps_long_course_body_uncut(monkeypatch):
    """总上下文未超限时，长病程不得逐行裁去中段（首次查房的诊断依据常在中段）。"""

    rows = _rows(2, 3000)
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )
    client = _AbsentClient()
    rule = "LX0609-06-03-03"
    await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert len(client.prompts) == 1
    assert "已裁剪" not in client.prompts[0]
    assert all(f"末尾标记{index}。" in client.prompts[0] for index in range(2))


def test_projection_batches_keep_long_body_and_singleton_failure():
    from app.services.luxian_0609.exam_lab_projection_batching import (
        build_exam_lab_projection_batches,
    )

    plan = build_exam_lab_projection_batches(rows_by_source=_rows(3, 7000))
    assert len(plan.batches) > 1
    for batch in plan.batches:
        for text in batch.projection.course_texts.values():
            assert text in batch.projection.context
            assert "末尾标记" in text
        assert "已裁剪" not in batch.projection.context
    with pytest.raises(ValueError, match="exam lab text projection truncated"):
        build_exam_lab_projection_batches(rows_by_source=_rows(1, 20000))


@pytest.mark.asyncio
async def test_failed_exam_batch_cannot_be_masked_by_other_batches(monkeypatch):
    rows = _rows()
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )

    class _FailedBatchClient(_AbsentClient):
        async def generate(self, prompt, **kwargs):
            if not self.prompts:
                self.prompts.append(prompt)
                raise RuntimeError("合成传输失败")
            return await super().generate(prompt, **kwargs)

    client = _FailedBatchClient()
    rule = "LX0609-06-03-03"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].reason_code == "model_transport_error"
    assert len(client.prompts) > 1
    assert any("EVENT_DOC=L03-18|" in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_exam_batch_merges_complete_global_event_facts_without_duplicates(
    monkeypatch,
):
    rows = _rows()
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=rows["labtest_master"],
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )

    class _PresentClient(_AbsentClient):
        async def generate(self, prompt, **kwargs):
            self.prompts.append(prompt)
            catalog, _ = json.JSONDecoder().raw_decode(
                prompt.split("逐规则事件目录=", 1)[1]
            )
            payload = json.loads(prompt.splitlines()[-1])
            for fact in payload["facts"]:
                position = fact.get("event_position", 1)
                event = catalog[fact["rule_id"]][position - 1]
                fact.update(
                    applicability="applicable",
                    semantic_state="present",
                    positive_state="not_relevant",
                    course_doc_positions=event["course_doc_positions"][:1],
                )
            return {"content": json.dumps(payload)}

    client = _PresentClient()
    rule = "LX0609-06-03-03"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].qc_direction.value == "satisfied"
    details = dict(result.customer_display_facts)[rule]["event_results"]
    assert [item["event_position"] for item in details] == list(range(1, 19))
    assert all(item["event_status"] == "compliant" for item in details)
    assert all(item["interval_hours"] == 1 for item in details)
    assert len(result.decisions[0].fact_refs) == len(set(result.decisions[0].fact_refs))


def test_exam_batches_map_both_families_and_share_stable_course_references():
    from app.services.luxian_0609.exam_lab_projection_batching import (
        build_exam_lab_projection_batches,
    )

    rows = _rows(3)
    rows["exam_master"] = tuple(
        {
            "exam_id": f"EX-{i}",
            "exam_type": "CT",
            "report_time": report["report_time"],
            "result": "阳性：合成所见。",
        }
        for i, report in enumerate(rows["labtest_master"])
    )
    plan = build_exam_lab_projection_batches(rows_by_source=rows, max_course_rows=3)
    covered = []
    shared_refs = {}
    for batch in plan.batches:
        for key, global_position in batch.event_positions.items():
            covered.append((key[0], global_position))
            assert (
                batch.projection.event_course_refs[key]
                == plan.projection.event_course_refs[(key[0], global_position)]
            )
        for ref in batch.projection.course_times:
            safe = batch.projection.safe_refs[ref]
            assert shared_refs.setdefault(ref, safe) == safe
    assert sorted(covered) == [
        ("culture", 1),
        ("culture", 2),
        ("culture", 3),
        ("exam", 1),
        ("exam", 2),
        ("exam", 3),
    ]
    assert len(covered) == len(set(covered))


@pytest.mark.asyncio
async def test_exam_batches_run_result_record_verification_for_all_global_events(
    monkeypatch,
):
    rows = _rows()
    exams = tuple(
        {
            "exam_id": f"EXAM-{i}",
            "exam_type": "CT",
            "report_time": report["report_time"],
            "result": "阳性：合成所见。",
        }
        for i, report in enumerate(rows["labtest_master"])
    )
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=exams,
        course_rows=rows["daily_course_record"],
        evaluation_horizon_rows=({"horizon_date": "2026-12-31"},),
    )

    class _ExamClient(_AbsentClient):
        def __init__(self):
            super().__init__()
            self.checked_refs = set()

        async def generate(self, prompt, **kwargs):
            if "EVENTS_JSON=" not in prompt:
                return await super().generate(prompt, **kwargs)
            self.prompts.append(prompt)
            events = json.loads(prompt.split("EVENTS_JSON=", 1)[1])
            docs = []
            for event in events:
                for doc in event["course_docs"]:
                    self.checked_refs.add(doc["course_doc_ref"])
                    docs.append(
                        {
                            "event_position": event["event_position"],
                            "course_doc_ref": doc["course_doc_ref"],
                            "quote_type": "none",
                            "quote": "",
                            "report_span": "",
                        }
                    )
            return {
                "content": json.dumps(
                    {"schema_version": "lx0609-exam-result-record-v1", "docs": docs}
                )
            }

    client = _ExamClient()
    rule = "LX0609-06-01-04"
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        wrapper_rules=(),
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule,),
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert client.checked_refs == {f"D06-{i:02d}" for i in range(1, 37)}
    details = dict(result.customer_display_facts)[rule]["event_results"]
    assert [item["event_position"] for item in details] == list(range(1, 19))
