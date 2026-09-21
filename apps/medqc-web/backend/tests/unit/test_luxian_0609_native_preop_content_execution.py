from __future__ import annotations

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_preop_content_execution import (
    evaluate_preop_content_rules,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError


class _Client:
    def __init__(self, payload):
        self.payload, self.prompts = payload, []

    async def generate(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        return {
            "content": self.payload,
            "usage": {"prompt_tokens": 11, "completion_tokens": 12, "total_tokens": 23},
        }


def _session(
    summary=(),
    discussion=(),
    surgery_records=(),
    mr_surgeries=(),
    truncated=False,
    error_sources=(),
):
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key in set(error_sources):
            raise SourceEvidenceQueryError("test query failure")
        rows = (
            summary
            if key == "presurg_summary"
            else discussion
            if key == "presurg_discussion"
            else surgery_records
            if key == "surgery_record"
            else mr_surgeries
            if key == "mr_surgery"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows,
            truncated=truncated and key == "presurg_summary",
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-078", "LX0609-079"),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-09-20T00:00:00+08:00",
        row_reader=reader,
    )


def _payload(*documents):
    import json

    return json.dumps({"documents": list(documents)}, ensure_ascii=False)


def _surgery_record(*, document_id, name, begin, end=None):
    return {
        "document_id": document_id,
        "surgery_name": name,
        "surgery_begin_time": begin,
        "surgery_end_time": end,
        "surgery_process": "手术经过。",
    }


def _summary_items(*, text, procedure, missing=()):
    fields = (
        "brief_condition",
        "preop_diagnosis",
        "surgical_indication",
        "planned_procedure",
        "planned_anesthesia",
        "precautions",
        "surgeon_preop_visit",
    )
    items = {field: text for field in fields}
    items["planned_procedure"] = procedure
    for field in missing:
        items[field] = None
    return items


@pytest.mark.asyncio
async def test_empty_sources_are_not_applicable_without_model():
    session = _session()
    client = _Client("{}")
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078", "LX0609-079"),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert [item.applicability.value for item in result.decisions] == [
        "not_applicable",
        "not_applicable",
    ]
    assert result.llm_call_count == 0 and client.prompts == []


def test_running_preop_rules_do_not_request_mr_surgery():
    calls = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "mr_surgery":
            raise AssertionError("running preop rules must not request mr_surgery")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-078", "LX0609-079"),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-09-20T00:00:00+08:00",
        row_reader=reader,
    )
    assert "mr_surgery" not in calls
    assert set(calls) == {"presurg_summary", "presurg_discussion", "surgery_record"}


def test_079_only_reads_its_own_discussion_source():
    calls = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "surgery_record":
            raise AssertionError("079 content completeness must not depend on surgery association")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-079",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-09-20T00:00:00+08:00",
        row_reader=reader,
    )
    assert calls == ["presurg_discussion"]


@pytest.mark.asyncio
async def test_both_rules_share_one_call_and_missing_is_per_document():
    summary_text = "术前诊断：胆囊炎。简要病情：腹痛。手术指征：反复发作。拟行腹腔镜胆囊切除术。拟全麻。注意事项：禁食。术者已查看患者。"
    discussion_text = "术前准备已完成。手术指征明确。手术方案：腹腔镜手术。可能出血，备血防范。参加讨论者：张医生 主治医师。具体讨论意见：同意手术。主持人小结：同意。讨论日期：2026-01-01。记录者签名：李医生。"
    session = _session(
        summary=({"document_id": "summary-1", "record_content": summary_text},),
        discussion=(
            {"document_id": "discussion-1", "record_content": discussion_text},
        ),
    )
    complete_summary = {
        field: "原文"
        for field in (
            "brief_condition",
            "preop_diagnosis",
            "surgical_indication",
            "planned_procedure",
            "planned_anesthesia",
            "precautions",
            "surgeon_preop_visit",
        )
    }
    incomplete_discussion = {
        field: "原文"
        for field in (
            "preop_preparation",
            "surgical_indication",
            "surgical_plan",
            "risk_and_prevention",
            "participants_with_titles",
            "specific_opinions",
            "chair_summary",
            "discussion_date",
            "recorder_signature",
        )
    }
    # grounding only requires continuous text; use actual substrings.
    complete_summary = {
        key: next(word for word in summary_text.split("。") if word)
        for key in complete_summary
    }
    incomplete_discussion = {
        key: next(word for word in discussion_text.split("。") if word)
        for key in incomplete_discussion
    }
    incomplete_discussion["recorder_signature"] = None
    client = _Client(
        _payload(
            {
                "document_id": "summary-1",
                "source_type": "presurg_summary",
                "items": complete_summary,
            },
            {
                "document_id": "discussion-1",
                "source_type": "presurg_discussion",
                "items": incomplete_discussion,
            },
        )
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078", "LX0609-079"),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert [item.qc_direction.value for item in result.decisions] == [
        "satisfied",
        "defect",
    ]
    assert result.llm_call_count == 1 and len(client.prompts) == 1


@pytest.mark.asyncio
async def test_real_client_compatible_generate_signature_is_used():
    summary_text = "术前诊断：胆囊炎。简要病情：腹痛。手术指征：反复发作。拟行腹腔镜胆囊切除术。拟全麻。注意事项：禁食。术者已查看患者。"
    payload = _payload(
        {
            "document_id": "summary-1",
            "source_type": "presurg_summary",
            "items": _summary_items(
                text="术前诊断：胆囊炎",
                procedure="拟行腹腔镜胆囊切除术",
            ),
        }
    )

    class _StrictClient:
        def __init__(self):
            self.kwargs = None

        async def generate(
            self,
            prompt,
            *,
            max_completion_tokens=None,
            allow_length_retry=True,
            enable_thinking=None,
        ):
            self.kwargs = {
                "max_completion_tokens": max_completion_tokens,
                "allow_length_retry": allow_length_retry,
                "enable_thinking": enable_thinking,
            }
            return {"content": payload, "usage": {}}

    client = _StrictClient()
    session = _session(
        summary=({"document_id": "summary-1", "record_content": summary_text},),
        surgery_records=(
            _surgery_record(
                document_id="surgery-1",
                name="腹腔镜胆囊切除术",
                begin="2026-01-02 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert result.llm_call_count == 1
    assert client.kwargs == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "enable_thinking": False,
    }


@pytest.mark.asyncio
async def test_two_procedures_are_matched_and_checked_within_their_own_events():
    first_name, second_name = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    first_text = f"术前小结：拟行{first_name}，其余字段完整。"
    second_text = f"术前小结：拟行{second_name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary-first",
                "record_time": "2026-01-01 07:00:00",
                "record_content": first_text,
            },
            {
                "document_id": "summary-second",
                "record_time": "2026-01-01 10:00:00",
                "record_content": second_text,
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name=first_name,
                begin="2026-01-01 08:00:00+08:00",
                end="2026-01-01 09:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name=second_name,
                begin="2026-01-01 11:00:00+08:00",
                end="2026-01-01 12:00:00+08:00",
            ),
        ),
    )
    client = _Client(
        _payload(
            {
                "document_id": "summary-first",
                "source_type": "presurg_summary",
                "items": _summary_items(text=first_text, procedure=first_name),
            },
            {
                "document_id": "summary-second",
                "source_type": "presurg_summary",
                "items": _summary_items(
                    text=second_text, procedure=second_name, missing=("precautions",)
                ),
            },
        )
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    decision = result.decisions[0]
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert decision.qc_direction.value == "defect"
    assert facts["missing_fields"] == ["precautions"]
    assert [item["event_index"] for item in facts["documents"]] == [1, 2]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_same_name_surgeries_without_time_narrowing_are_data_gap():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {"document_id": "summary", "record_time": "2026-01-01 07:00:00", "record_content": text},
        ),
        surgery_records=(
            _surgery_record(document_id="surgery-first", name=name, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="surgery-second", name=name, begin="2026-01-02 08:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    assert result.decisions[0].reason_code == "association_failed"


@pytest.mark.asyncio
async def test_single_surgery_conflicting_explicit_procedure_is_data_gap_without_event_attribution():
    actual_name, documented_name = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    text = f"术前小结：拟行{documented_name}，其余字段完整。"
    session = _session(
        summary=(
            {"document_id": "summary", "record_content": text},
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery-actual",
                name=actual_name,
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=documented_name),
                }
            )
        ),
    )

    decision = result.decisions[0]
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert (
        decision.applicability.value,
        decision.evidence_state.value,
        decision.qc_direction.value,
        decision.reason_code,
    ) == (
        "unknown",
        "data_gap",
        "unknown",
        "association_failed",
    )
    assert facts["documents"] == [
        {
            "document_index": 1,
            "event_index": None,
            "association_state": "ambiguous",
            "missing_fields": [],
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actual_name", "documented_name"),
    (
        ("全子宫切除术", "次全子宫切除术"),
        ("次全子宫切除术", "全子宫切除术"),
        ("胆囊切除术", "腹腔镜胆囊切除术"),
        ("腹腔镜胆囊切除术", "胆囊切除术"),
        ("肾镜取石术", "经皮肾镜取石术"),
        (
            "全子宫切除术+双侧输卵管切除术+盆腔粘连松解术",
            "次全子宫切除术+双侧输卵管切除术+盆腔粘连松解术",
        ),
    ),
)
async def test_single_surgery_identity_variant_is_data_gap_without_event_attribution(
    actual_name, documented_name
):
    """“全切”与“次全切”是不同术式，不能被共享关联函数吞没。"""

    text = f"术前小结：拟行{documented_name}，其余字段完整。"
    session = _session(
        summary=({"document_id": "summary", "record_content": text},),
        surgery_records=(
            _surgery_record(
                document_id="surgery-actual",
                name=actual_name,
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=documented_name),
                }
            )
        ),
    )

    decision = result.decisions[0]
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert (
        decision.applicability.value,
        decision.evidence_state.value,
        decision.qc_direction.value,
        decision.reason_code,
    ) == (
        "unknown",
        "data_gap",
        "unknown",
        "association_failed",
    )
    assert facts["documents"] == [
        {
            "document_index": 1,
            "event_index": None,
            "association_state": "ambiguous",
            "missing_fields": [],
        }
    ]


@pytest.mark.asyncio
async def test_same_name_surgeries_on_different_days_use_structured_planned_time():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary",
                "record_content": text,
                "planned_surgery_time": "2026-01-02 00:00:00",
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name=name,
                begin="2026-01-02 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert result.decisions[0].qc_direction.value == "satisfied"
    assert facts["documents"][0]["event_index"] == 2


@pytest.mark.asyncio
async def test_same_name_surgeries_use_planned_time_label_from_synced_content():
    name = "腹腔镜胆囊切除术"
    text = (
        f"拟实施手术：{name}\n"
        "手术时间：2026-01-02 00:00:00\n"
        "术前小结其余字段完整。"
    )
    session = _session(
        summary=({"document_id": "summary", "record_content": text},),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name=name,
                begin="2026-01-02 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert result.decisions[0].qc_direction.value == "satisfied"
    assert facts["documents"][0]["event_index"] == 2


@pytest.mark.asyncio
async def test_same_name_same_day_surgeries_require_exact_planned_minute():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary",
                "record_content": text,
                "planned_surgery_time": "2026-01-01 14:00:30",
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name=name,
                begin="2026-01-01 14:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    facts = dict(result.customer_display_facts)["LX0609-078"]
    assert result.decisions[0].qc_direction.value == "satisfied"
    assert facts["documents"][0]["event_index"] == 2


@pytest.mark.asyncio
async def test_named_surgery_with_conflicting_planned_clock_time_is_data_gap():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary",
                "record_content": text,
                "planned_surgery_time": "2026-01-01 14:00:00",
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    assert result.decisions[0].reason_code == "association_failed"


@pytest.mark.asyncio
async def test_same_name_same_day_surgeries_with_date_only_planned_time_are_data_gap():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary",
                "record_content": text,
                "planned_surgery_time": "2026-01-01 00:00:00",
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name=name,
                begin="2026-01-01 14:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    assert result.decisions[0].reason_code == "association_failed"


@pytest.mark.asyncio
async def test_named_surgery_with_conflicting_planned_date_is_data_gap():
    name = "腹腔镜胆囊切除术"
    text = f"术前小结：拟行{name}，其余字段完整。"
    session = _session(
        summary=(
            {
                "document_id": "summary",
                "record_content": text,
                "planned_surgery_time": "2026-01-02 00:00:00",
            },
        ),
        surgery_records=(
            _surgery_record(
                document_id="surgery",
                name=name,
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary",
                    "source_type": "presurg_summary",
                    "items": _summary_items(text=text, procedure=name),
                }
            )
        ),
    )
    assert result.decisions[0].reason_code == "association_failed"


@pytest.mark.asyncio
async def test_two_summary_roles_can_complete_one_surgery_only_within_the_event():
    name = "腹腔镜胆囊切除术"
    core_text = f"术前小结：拟行{name}，核心内容完整。"
    visit_text = f"术者术前查看患者，拟行{name}。"
    core = _summary_items(text=core_text, procedure=name, missing=("surgeon_preop_visit",))
    visit = _summary_items(text=visit_text, procedure=name, missing=RULE_FIELDS_078_EXCEPT_VISIT)
    visit["surgeon_preop_visit"] = "术者术前查看患者"
    session = _session(
        summary=(
            {"document_id": "summary-core", "record_content": core_text},
            {"document_id": "summary-visit", "record_content": visit_text},
        ),
        surgery_records=(
            _surgery_record(document_id="surgery", name=name, begin="2026-01-01 08:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "summary-core", "source_type": "presurg_summary", "items": core},
                {"document_id": "summary-visit", "source_type": "presurg_summary", "items": visit},
            )
        ),
    )
    assert result.decisions[0].qc_direction.value == "satisfied"


RULE_FIELDS_078_EXCEPT_VISIT = (
    "brief_condition",
    "preop_diagnosis",
    "surgical_indication",
    "planned_anesthesia",
    "precautions",
)


@pytest.mark.asyncio
async def test_document_that_names_two_surgeries_is_ambiguous():
    first_name, second_name = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    combined = f"{first_name}+{second_name}"
    text = f"术前小结：拟行{combined}，其余字段完整。"
    session = _session(
        summary=({"document_id": "summary", "record_content": text},),
        surgery_records=(
            _surgery_record(document_id="surgery-first", name=first_name, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="surgery-second", name=second_name, begin="2026-01-01 12:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "summary", "source_type": "presurg_summary", "items": _summary_items(text=text, procedure=combined)}
            )
        ),
    )
    assert result.decisions[0].evidence_state.value == "data_gap"


@pytest.mark.asyncio
async def test_confirmed_missing_is_not_hidden_by_ambiguous_document_without_that_field():
    first_name, second_name = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    first_text = f"术前小结：拟行{first_name}，其余字段完整。"
    ambiguous_name = f"{first_name}+{second_name}"
    ambiguous_text = f"术前小结：拟行{ambiguous_name}，其余字段完整。"
    session = _session(
        summary=(
            {"document_id": "summary-first", "record_content": first_text},
            {"document_id": "summary-ambiguous", "record_content": ambiguous_text},
        ),
        surgery_records=(
            _surgery_record(document_id="surgery-first", name=first_name, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="surgery-second", name=second_name, begin="2026-01-01 12:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary-first",
                    "source_type": "presurg_summary",
                    "items": _summary_items(
                        text=first_text,
                        procedure=first_name,
                        missing=("planned_anesthesia", "precautions"),
                    ),
                },
                {
                    "document_id": "summary-ambiguous",
                    "source_type": "presurg_summary",
                    "items": _summary_items(
                        text=ambiguous_text,
                        procedure=ambiguous_name,
                        missing=("precautions",),
                    ),
                },
            )
        ),
    )
    assert result.decisions[0].qc_direction.value == "defect"


@pytest.mark.asyncio
async def test_ambiguous_document_cannot_fill_confirmed_missing_field_across_events():
    first_name, second_name = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    first_text = f"术前小结：拟行{first_name}，其余字段完整。"
    ambiguous_name = f"{first_name}+{second_name}"
    ambiguous_text = f"术前小结：拟行{ambiguous_name}，其余字段完整。"
    session = _session(
        summary=(
            {"document_id": "summary-first", "record_content": first_text},
            {"document_id": "summary-ambiguous", "record_content": ambiguous_text},
        ),
        surgery_records=(
            _surgery_record(document_id="surgery-first", name=first_name, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="surgery-second", name=second_name, begin="2026-01-01 12:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "summary-first",
                    "source_type": "presurg_summary",
                    "items": _summary_items(
                        text=first_text,
                        procedure=first_name,
                        missing=("planned_anesthesia",),
                    ),
                },
                {
                    "document_id": "summary-ambiguous",
                    "source_type": "presurg_summary",
                    "items": _summary_items(
                        text=ambiguous_text, procedure=ambiguous_name
                    ),
                },
            )
        ),
    )
    assert result.decisions[0].qc_direction.value == "defect"


@pytest.mark.asyncio
async def test_invalid_document_id_or_quote_is_data_gap():
    text = "术前小结：患者情况稳定，拟行手术。"
    session = _session(summary=({"document_id": "summary-1", "record_content": text},))
    payload = _payload(
        {
            "document_id": "other",
            "source_type": "presurg_summary",
            "items": {
                field: "不存在"
                for field in (
                    "brief_condition",
                    "preop_diagnosis",
                    "surgical_indication",
                    "planned_procedure",
                    "planned_anesthesia",
                    "precautions",
                    "surgeon_preop_visit",
                )
            },
        }
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(payload),
    )
    assert result.decisions[0].evidence_state.value == "data_gap"


@pytest.mark.asyncio
async def test_truncated_source_is_data_gap_without_model():
    session = _session(
        summary=(
            {
                "document_id": "summary-1",
                "record_content": "术前小结存在且正文足够长。",
            },
        ),
        truncated=True,
    )
    client = _Client("{}")
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert result.decisions[0].reason_code == "source_truncated"
    assert result.llm_call_count == 0 and client.prompts == []


@pytest.mark.asyncio
async def test_source_query_error_is_delivered_as_data_gap_without_model():
    session = _session(error_sources=("presurg_summary",))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-078",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client("{}"),
    )
    decision = result.decisions[0]
    assert (decision.applicability.value, decision.evidence_state.value) == (
        "unknown",
        "data_gap",
    )
    assert decision.reason_code == "source_readiness_unproven"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_discussion_structured_fields_are_not_treated_as_blank_document():
    session = _session(
        discussion=(
            {
                "document_id": "discussion-structured",
                "record_content": "",
                "host_name": "王主任",
                "host_summary": "同意手术方案。",
                "discuss_staff": "李医生 主治医师",
                "submitter": "赵医生",
                "record_time": "2026-01-01 08:00:00",
            },
        )
    )
    fields = (
        "preop_preparation",
        "surgical_indication",
        "surgical_plan",
        "risk_and_prevention",
        "participants_with_titles",
        "specific_opinions",
        "chair_summary",
        "discussion_date",
        "recorder_signature",
    )
    items = {field: None for field in fields}
    items.update(
        {
            "participants_with_titles": "参加讨论者：李医生 主治医师",
            "chair_summary": "主持人小结：同意手术方案。",
            "discussion_date": "讨论日期：2026-01-01 08:00:00",
            "recorder_signature": None,
        }
    )
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": items,
            }
        )
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert "recorder_signature" not in dict(result.customer_display_facts)["LX0609-079"][
        "missing_fields"
    ]
    assert result.llm_call_count == 1 and client.prompts


def _structured_discussion(*, submitter="王标", v2_schema=None):
    row = {
        "document_id": "discussion-structured",
        "record_content": (
            "术前准备：完成。手术指征：明确。手术方案：腹腔镜手术。"
            "风险及防范：可能出血，已备血。具体讨论意见：同意手术。"
        ),
        "host_name": "王主任",
        "host_summary": "同意上述手术方案。",
        "discuss_staff": "李医生 主治医师",
        "record_time": "2026-01-01 08:00:00",
        "submitter": submitter,
    }
    if v2_schema is not None:
        row["v2_schema"] = v2_schema
    return row


def _complete_discussion_items(signature):
    return {
        "preop_preparation": "术前准备：完成",
        "surgical_indication": "手术指征：明确",
        "surgical_plan": "手术方案：腹腔镜手术",
        "risk_and_prevention": "风险及防范：可能出血，已备血",
        "participants_with_titles": "参加讨论者：李医生 主治医师",
        "specific_opinions": "具体讨论意见：同意手术",
        "chair_summary": "主持人小结：同意上述手术方案",
        "discussion_date": "讨论日期：2026-01-01 08:00:00",
        "recorder_signature": signature,
    }


@pytest.mark.asyncio
async def test_submitter_is_deterministic_recorder_signature_when_model_returns_null():
    row = _structured_discussion(submitter="王标")
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": _complete_discussion_items(None),
            }
        )
    )
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    decision = result.decisions[0]
    assert (decision.evidence_state.value, decision.qc_direction.value) == (
        "sufficient",
        "satisfied",
    )
    assert decision.reason_code == "requirement_satisfied"
    assert dict(result.customer_display_facts)["LX0609-079"]["missing_fields"] == []


@pytest.mark.asyncio
async def test_079_content_is_not_blocked_by_unmatched_multi_surgery_association():
    row = _structured_discussion(submitter="王标")
    session = _session(
        discussion=(row,),
        surgery_records=(
            _surgery_record(
                document_id="surgery-first",
                name="腹腔镜胆囊切除术",
                begin="2026-01-01 08:00:00+08:00",
            ),
            _surgery_record(
                document_id="surgery-second",
                name="腹腔镜阑尾切除术",
                begin="2026-01-02 08:00:00+08:00",
            ),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {
                    "document_id": "discussion-structured",
                    "source_type": "presurg_discussion",
                    "items": _complete_discussion_items(None),
                }
            )
        ),
    )
    decision = result.decisions[0]
    assert (decision.evidence_state.value, decision.qc_direction.value) == (
        "sufficient",
        "satisfied",
    )
    assert decision.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-079"]
    assert facts["documents"][0]["association_state"] == "not_required"


@pytest.mark.asyncio
async def test_host_summary_signature_satisfies_when_submitter_is_empty():
    row = _structured_discussion(
        submitter="",
        v2_schema=None,
    )
    row["host_summary"] = "同意上述手术方案。记录医师签名：赵医生。"
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": _complete_discussion_items("记录医师签名：赵医生"),
            }
        )
    )
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    decision = result.decisions[0]
    assert (decision.evidence_state.value, decision.qc_direction.value) == (
        "sufficient",
        "satisfied",
    )


@pytest.mark.asyncio
async def test_missing_submitter_and_body_signature_is_non_compliant():
    row = _structured_discussion(submitter="")
    row["submitter_id"] = "0446"
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": _complete_discussion_items(None),
            }
        )
    )
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    decision = result.decisions[0]
    assert (decision.evidence_state.value, decision.qc_direction.value) == (
        "sufficient",
        "defect",
    )
    assert decision.reason_code == "requirement_violated"
    assert dict(result.customer_display_facts)["LX0609-079"]["missing_fields"] == [
        "recorder_signature"
    ]


@pytest.mark.asyncio
async def test_v2_schema_whitelists_only_discussion_suggestion():
    row = _structured_discussion(
        submitter="赵医生",
        v2_schema={
            "discuss_suggestion": "围术期密切观察。",
            "patient_name": "不得进入提示词",
            "identity_number": "不得进入提示词",
        },
    )
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": _complete_discussion_items("记录者签名：赵医生"),
            }
        )
    )
    session = _session(discussion=(row,))
    await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    prompt, kwargs = client.prompts[0]
    assert "讨论建议：围术期密切观察。" in prompt
    assert "不得进入提示词" not in prompt
    assert kwargs["max_completion_tokens"] == 4096
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert kwargs["enable_thinking"] is False


@pytest.mark.asyncio
async def test_json_v2_schema_still_whitelists_only_discussion_suggestion():
    row = _structured_discussion(
        submitter="赵医生",
        v2_schema='{"discuss_suggestion":"术后观察。","patient_name":"不得进入提示词"}',
    )
    client = _Client(
        _payload(
            {
                "document_id": "discussion-structured",
                "source_type": "presurg_discussion",
                "items": _complete_discussion_items("记录者签名：赵医生"),
            }
        )
    )
    session = _session(discussion=(row,))
    await evaluate_preop_content_rules(
        rule_ids=("LX0609-079",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert "讨论建议：术后观察。" in client.prompts[0][0]
    assert "不得进入提示词" not in client.prompts[0][0]
