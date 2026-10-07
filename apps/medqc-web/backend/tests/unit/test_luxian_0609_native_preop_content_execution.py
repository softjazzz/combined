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
        selected_rule_ids=("LX0609-04-01-04", "LX0609-04-01-05"),
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
        rule_ids=("LX0609-04-01-04", "LX0609-04-01-05"),
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
        selected_rule_ids=("LX0609-04-01-04", "LX0609-04-01-05"),
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
        selected_rule_ids=("LX0609-04-01-05",),
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
    incomplete_discussion["recorder_signature"] = {"state": "missing", "quote": None, "reviewed_all_sections": True}
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
        rule_ids=("LX0609-04-01-04", "LX0609-04-01-05"),
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    decision = result.decisions[0]
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
async def test_unlinked_preop_documents_cannot_complete_each_other():
    """尚无实际手术记录时，两份小结不能仅因同住院而相互补缺。"""
    rows, documents = [], []
    for index, (procedure, missing) in enumerate((
        ("清创术", ("precautions",)),
        ("植皮术", ("planned_anesthesia",)),
    )):
        text = f"术前小结：拟行{procedure}，已记录诊断、病情、麻醉及术者查看情况。"
        doc_id = f"unlinked-{index}"
        rows.append({"document_id": doc_id, "record_content": text})
        documents.append({"document_id": doc_id, "source_type": "presurg_summary",
                          "items": _summary_items(text=text, procedure=procedure, missing=missing)})
    session = _session(summary=tuple(rows))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",), snapshot=session.snapshot,
        materials=session.materials, llm_client=_Client(_payload(*documents)),
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert set(dict(result.customer_display_facts)["LX0609-04-01-04"]["missing_fields"]) == {
        "precautions", "planned_anesthesia",
    }


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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
    # 归属不明的文书不能补齐字段，也不能证明合规；但它记载了该项，因此
    # “确认缺少”无法成立：该项列为待确认，整例保持资料不足而不是合规。
    decision = result.decisions[0]
    assert decision.qc_direction.value != "satisfied"
    assert decision.evidence_state.value == "data_gap"
    facts = dict(result.customer_display_facts)["LX0609-04-01-04"]
    assert facts["missing_fields"] == []
    assert facts["pending_fields"] == ["planned_anesthesia"]


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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
        rule_ids=("LX0609-04-01-04",),
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
    items = {field: {"state": "missing", "quote": None, "reviewed_all_sections": True} for field in fields}
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
        rule_ids=("LX0609-04-01-05",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert result.decisions[0].qc_direction.value == "defect"
    assert "recorder_signature" not in dict(result.customer_display_facts)["LX0609-04-01-05"][
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
        rule_ids=("LX0609-04-01-05",),
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
    assert dict(result.customer_display_facts)["LX0609-04-01-05"]["missing_fields"] == []


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
        rule_ids=("LX0609-04-01-05",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-01-05"]
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
        rule_ids=("LX0609-04-01-05",),
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
                "items": _complete_discussion_items({"state": "missing", "quote": None, "reviewed_all_sections": True}),
            }
        )
    )
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-05",),
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
    assert dict(result.customer_display_facts)["LX0609-04-01-05"]["missing_fields"] == [
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
        rule_ids=("LX0609-04-01-05",),
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
        rule_ids=("LX0609-04-01-05",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=client,
    )
    assert "讨论建议：术后观察。" in client.prompts[0][0]
    assert "不得进入提示词" not in client.prompts[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("state,reviewed,direction", [
    (None, False, "unknown"),
    ("unknown", True, "unknown"),
    ("missing", False, "unknown"),
    ("missing", True, "defect"),
])
async def test_discussion_unextracted_is_not_confirmed_missing(state, reviewed, direction):
    row = _structured_discussion(submitter="")
    value = None if state is None else {"state": state, "quote": None, "reviewed_all_sections": reviewed}
    client = _Client(_payload({"document_id": row["document_id"], "source_type": "presurg_discussion",
                               "items": _complete_discussion_items(value)}))
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(rule_ids=("LX0609-04-01-05",),
        snapshot=session.snapshot, materials=session.materials, llm_client=client)
    assert result.decisions[0].qc_direction.value == direction
    assert result.llm_call_count == 1


def test_discussion_present_quote_must_be_in_source():
    from app.services.luxian_0609.native_preop_content_execution import _validated_items, RULE_FIELDS
    items = {field: {"state": "unknown", "quote": None, "reviewed_all_sections": False}
             for field in RULE_FIELDS["LX0609-04-01-05"]}
    items["surgical_plan"] = {"state": "present", "quote": "虚构术式", "reviewed_all_sections": True}
    assert _validated_items({"documents": [{"document_id": "d", "source_type": "presurg_discussion", "items": items}]},
        {("presurg_discussion", "d"): "术前准备已完善，无手术禁忌"}, ("LX0609-04-01-05",)) is None


@pytest.mark.asyncio
async def test_discussion_confirmed_defect_survives_another_unknown_field():
    row = _structured_discussion(submitter="")
    items = _complete_discussion_items({"state": "missing", "quote": None, "reviewed_all_sections": True})
    items["surgical_plan"] = {"state": "unknown", "quote": None, "reviewed_all_sections": False}
    session = _session(discussion=(row,))
    result = await evaluate_preop_content_rules(rule_ids=("LX0609-04-01-05",), snapshot=session.snapshot,
        materials=session.materials, llm_client=_Client(_payload({"document_id": row["document_id"],
        "source_type": "presurg_discussion", "items": items})))
    assert result.decisions[0].qc_direction.value == "defect"
    assert dict(result.customer_display_facts)["LX0609-04-01-05"]["missing_fields"] == ["recorder_signature"]


# ---- 归属不明文书只能阻止“确认缺少”，不能补齐或证明合规（第三轮最小修复） ----

_C04_PLAN = "胸腔镜下右肺上叶结节楔形切除术"
_C04_PERFORMED = "胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术"
_C04_CORE = (
    "手术适应症：患者诊断右肺上叶结节明确，有手术指征。"
    f"拟施手术名称和方式：{_C04_PLAN}拟施 麻醉方式：全麻"
    "手术要点：尽可能彻底切除原发病灶。术前准备：常规术前宣教、备皮。手术医师签名：甲"
)
_C04_NARRATIVE = "患者老年女性，因腹胀腹痛入院。查体：生命体征平稳。辅助检查：心脏彩超左房增大。"


def _core_items(text=_C04_CORE):
    return {
        "brief_condition": None,
        "preop_diagnosis": None,
        "surgical_indication": "手术适应症：患者诊断右肺上叶结节明确，有手术指征。",
        "planned_procedure": _C04_PLAN,
        "planned_anesthesia": "全麻",
        "precautions": "手术要点：尽可能彻底切除原发病灶。",
        "surgeon_preop_visit": None,
    }


def _narrative_items():
    items = {field: None for field in _core_items()}
    items["brief_condition"] = "患者老年女性，因腹胀腹痛入院。"
    return items


def _facts_for_summary(result):
    return dict(result.customer_display_facts)["LX0609-04-01-04"]


@pytest.mark.asyncio
async def test_ambiguous_plan_document_blocks_false_confirmed_missing_but_keeps_true_missing():
    """C04 形态：计划术式与实施术式不一致 → 核心小结 ambiguous，叙述小结回退 matched。"""
    session = _session(
        summary=(
            {"document_id": "core", "record_content": _C04_CORE},
            {
                "document_id": "narrative",
                "record_content": _C04_NARRATIVE,
                "record_time": "2026-01-01 07:50:00",
            },
        ),
        surgery_records=(
            _surgery_record(document_id="s1", name=_C04_PERFORMED, begin="2026-01-01 09:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "core", "source_type": "presurg_summary", "items": _core_items()},
                {"document_id": "narrative", "source_type": "presurg_summary", "items": _narrative_items()},
            )
        ),
    )
    facts = _facts_for_summary(result)
    assert [d["association_state"] for d in facts["documents"]] == ["ambiguous", "matched"]
    # 两份文书都没有的项目仍是确认缺项，不被归属不明文书遮蔽。
    assert facts["missing_fields"] == ["preop_diagnosis", "surgeon_preop_visit"]
    # 仅在归属不明文书中有记录的项目：待确认，不是缺项，也没有补齐。
    assert facts["pending_fields"] == [
        "planned_anesthesia", "planned_procedure", "precautions", "surgical_indication",
    ]
    assert result.decisions[0].qc_direction.value == "defect"
    assert facts["verification_kind"] == "preop_content_incomplete"


@pytest.mark.asyncio
async def test_unrelated_empty_ambiguous_document_does_not_mask_true_missing():
    session = _session(
        summary=(
            {"document_id": "core", "record_content": _C04_CORE},
            {"document_id": "narrative", "record_content": _C04_NARRATIVE, "record_time": "2026-01-01 07:50:00"},
            {"document_id": "stray", "record_content": "患者情况稳定，拟行其他手术，详见另页记录内容。"},
        ),
        surgery_records=(
            _surgery_record(document_id="s1", name=_C04_PERFORMED, begin="2026-01-01 09:00:00+08:00"),
        ),
    )
    stray_items = {field: None for field in _core_items()}
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "core", "source_type": "presurg_summary", "items": _core_items()},
                {"document_id": "narrative", "source_type": "presurg_summary", "items": _narrative_items()},
                {"document_id": "stray", "source_type": "presurg_summary", "items": stray_items},
            )
        ),
    )
    facts = _facts_for_summary(result)
    assert facts["missing_fields"] == ["preop_diagnosis", "surgeon_preop_visit"]
    assert result.decisions[0].qc_direction.value == "defect"


@pytest.mark.asyncio
async def test_other_event_matched_document_never_fills_this_events_missing_field():
    first, second = "腹腔镜胆囊切除术", "腹腔镜阑尾切除术"
    first_text = f"术前小结：拟行{first}，麻醉方式待定，其余字段完整记录。"
    second_text = f"术前小结：拟行{second}，全麻，其余字段完整记录。"
    session = _session(
        summary=(
            {"document_id": "first", "record_content": first_text},
            {"document_id": "second", "record_content": second_text},
        ),
        surgery_records=(
            _surgery_record(document_id="s1", name=first, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="s2", name=second, begin="2026-01-01 12:00:00+08:00"),
        ),
    )
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "first", "source_type": "presurg_summary",
                 "items": _summary_items(text=first_text, procedure=first, missing=("planned_anesthesia",))},
                {"document_id": "second", "source_type": "presurg_summary",
                 "items": _summary_items(text=second_text, procedure=second)},
            )
        ),
    )
    facts = _facts_for_summary(result)
    assert [d["event_index"] for d in facts["documents"]] == [1, 2]
    assert facts["missing_fields"] == ["planned_anesthesia"]
    assert "pending_fields" not in facts
    assert result.decisions[0].qc_direction.value == "defect"


@pytest.mark.asyncio
async def test_same_name_two_surgeries_with_unplaceable_documents_stay_data_gap():
    """C01 形态：同名两台手术，两份小结都无法归属 → 资料不足，不跨手术合并。"""
    name = "腹腔镜下胆囊切除术"
    session = _session(
        summary=(
            {"document_id": "core", "record_content": _C04_CORE.replace(_C04_PLAN, name)},
            {"document_id": "narrative", "record_content": _C04_NARRATIVE},
        ),
        surgery_records=(
            _surgery_record(document_id="s1", name=name, begin="2026-01-01 08:00:00+08:00"),
            _surgery_record(document_id="s2", name=name, begin="2026-01-02 08:00:00+08:00"),
        ),
    )
    core = _core_items()
    core["planned_procedure"] = name
    result = await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "core", "source_type": "presurg_summary", "items": core},
                {"document_id": "narrative", "source_type": "presurg_summary", "items": _narrative_items()},
            )
        ),
    )
    facts = _facts_for_summary(result)
    assert all(d["association_state"] == "ambiguous" for d in facts["documents"])
    assert facts["missing_fields"] == []
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.decisions[0].qc_direction.value != "satisfied"


# ---- 术式关联：仅对比较值做受限规范化（原始引文与原文校验不变） ----

def _template_core(name, anesthesia="全麻"):
    return (
        "手术适应症：诊断明确，有手术指征。"
        f"拟施手术名称和方式：:{name}拟施 麻醉方式：{anesthesia}"
        "拟诊手术日期：:2026年01月01日手术要点：:仔细操作，避免损伤。术前准备：禁食水。手术医师签名：甲"
    )


def _template_core_items(name, anesthesia="全麻"):
    return {
        "brief_condition": None,
        "preop_diagnosis": None,
        "surgical_indication": "手术适应症：诊断明确，有手术指征。",
        # 真实模型取到的引文：带开头冒号与下一标签残留“拟施”。
        "planned_procedure": f":{name}拟施 ",
        "planned_anesthesia": anesthesia,
        "precautions": "仔细操作，避免损伤。",
        "surgeon_preop_visit": None,
    }


async def _run_template_case(core_text, core_items, surgery_names, narrative_time="2026-01-01 07:00:00"):
    session = _session(
        summary=(
            {"document_id": "core", "record_content": core_text},
            {"document_id": "narrative", "record_content": _C04_NARRATIVE, "record_time": narrative_time},
        ),
        surgery_records=tuple(
            _surgery_record(document_id=f"s{index}", name=name, begin=begin)
            for index, (name, begin) in enumerate(surgery_names, start=1)
        ),
    )
    return await evaluate_preop_content_rules(
        rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        materials=session.materials,
        llm_client=_Client(
            _payload(
                {"document_id": "core", "source_type": "presurg_summary", "items": core_items},
                {"document_id": "narrative", "source_type": "presurg_summary", "items": _narrative_items()},
            )
        ),
    )


@pytest.mark.asyncio
async def test_label_residue_and_colon_in_quote_do_not_break_association():
    """C02/C09/C10 形态：引文 `:术式拟施 `，原文紧接“麻醉方式”。"""
    name = "腹腔镜下胆囊切除术"
    result = await _run_template_case(
        _template_core(name), _template_core_items(name), [(name, "2026-01-01 09:00:00+08:00")]
    )
    facts = _facts_for_summary(result)
    assert [d["association_state"] for d in facts["documents"]] == ["matched", "matched"]
    assert facts["missing_fields"] == ["preop_diagnosis", "surgeon_preop_visit"]
    assert "pending_fields" not in facts


@pytest.mark.asyncio
async def test_side_difference_is_not_hidden_by_residue_normalization():
    result = await _run_template_case(
        _template_core("右侧腹股沟疝修补术"),
        _template_core_items("右侧腹股沟疝修补术"),
        [("左侧腹股沟疝修补术", "2026-01-01 09:00:00+08:00")],
    )
    assert _facts_for_summary(result)["documents"][0]["association_state"] == "ambiguous"


@pytest.mark.asyncio
async def test_procedure_scope_difference_is_not_hidden_by_residue_normalization():
    """C04 形态：计划楔形切除，实施肺叶切除，去掉标签残留后仍不同。"""
    result = await _run_template_case(
        _template_core(_C04_PLAN), _template_core_items(_C04_PLAN),
        [(_C04_PERFORMED, "2026-01-01 09:00:00+08:00")],
    )
    assert _facts_for_summary(result)["documents"][0]["association_state"] == "ambiguous"


@pytest.mark.asyncio
async def test_site_difference_is_not_hidden_by_residue_normalization():
    result = await _run_template_case(
        _template_core("T11椎体骨折球囊扩张成形术", "局麻"),
        _template_core_items("T11椎体骨折球囊扩张成形术", "局麻"),
        [("T12椎体骨折球囊扩张成形术", "2026-01-01 09:00:00+08:00")],
    )
    assert _facts_for_summary(result)["documents"][0]["association_state"] == "ambiguous"


@pytest.mark.asyncio
async def test_same_name_two_surgeries_stay_unassociated_after_normalization():
    name = "腹腔镜下胆囊切除术"
    result = await _run_template_case(
        _template_core(name), _template_core_items(name),
        [(name, "2026-01-01 08:00:00+08:00"), (name, "2026-01-02 08:00:00+08:00")],
        narrative_time=None,
    )
    facts = _facts_for_summary(result)
    assert facts["documents"][0]["association_state"] == "ambiguous"
    assert result.decisions[0].qc_direction.value != "satisfied"


def test_residue_is_only_removed_when_the_source_continues_with_that_label():
    from app.services.luxian_0609.native_preop_content_execution import (
        _procedure_name_for_association as normalize,
    )

    text = "拟施手术名称和方式：:腹腔镜下胆囊切除术拟施 麻醉方式：全麻"
    assert normalize(":腹腔镜下胆囊切除术拟施 ", text) == "腹腔镜下胆囊切除术"
    # 原文接下来不是标签：不是残留，不能删字。
    other = "拟施手术名称和方式：:腹腔镜下胆囊切除术拟施后另议"
    assert normalize(":腹腔镜下胆囊切除术拟施", other) == "腹腔镜下胆囊切除术拟施"
    # 引文在原文中出现不唯一：原样返回。
    twice = text + "；腹腔镜下胆囊切除术拟施 麻醉方式：全麻"
    assert normalize("腹腔镜下胆囊切除术拟施", twice) == "腹腔镜下胆囊切除术拟施"
    # 非字符串（缺失）不处理。
    assert normalize(None, text) is None
