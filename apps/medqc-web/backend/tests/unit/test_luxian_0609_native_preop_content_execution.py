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


def _session(summary=(), discussion=(), truncated=False, error_sources=()):
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key in set(error_sources):
            raise SourceEvidenceQueryError("test query failure")
        rows = (
            summary
            if key == "presurg_summary"
            else discussion
            if key == "presurg_discussion"
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


@pytest.mark.asyncio
async def test_both_rules_share_one_call_and_missing_is_per_document():
    summary_text = "术前诊断：胆囊炎。简要病情：腹痛。手术指征：反复发作。拟行腹腔镜胆囊切除术。拟全麻。注意事项：禁食。术者已查看患者。"
    discussion_text = "术前准备已完成。手术指征明确。手术方案：腹腔镜手术。可能出血，备血防范。参加讨论者：张医生 主治医师。具体讨论意见：同意手术。主持人小结：同意。讨论日期：2026-01-01。记录者签名：李医生。"
    session = _session(
        summary=({"document_id": "summary-1", "record_content": summary_text},),
        discussion=(
            {"document_id": "discussion-1", "record_content": discussion_text, "physician_sign": ""},
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
                "physician_sign": "赵医生",
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
            "recorder_signature": "记录者签名：赵医生",
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
    assert result.llm_call_count == 1 and client.prompts


_MISSING = object()


def _structured_discussion(*, physician_sign_marker=_MISSING, v2_schema=None):
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
        "submitter": "不应作为记录者签名",
    }
    if physician_sign_marker is not _MISSING:
        row["physician_sign"] = physician_sign_marker
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
async def test_missing_signature_source_is_data_gap_not_non_compliant():
    row = _structured_discussion(physician_sign_marker=_MISSING)
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
        "data_gap",
        "unknown",
    )
    assert decision.reason_code == "source_readiness_unproven"
    assert "不应作为记录者签名" not in client.prompts[0][0]


@pytest.mark.asyncio
async def test_explicit_blank_signature_is_non_compliant():
    row = _structured_discussion(physician_sign_marker="")
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
    assert result.decisions[0].qc_direction.value == "defect"
    assert dict(result.customer_display_facts)["LX0609-079"]["missing_fields"] == [
        "recorder_signature"
    ]


@pytest.mark.asyncio
async def test_v2_schema_whitelists_only_discussion_suggestion():
    row = _structured_discussion(
        physician_sign_marker="赵医生",
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
    assert kwargs["temperature"] == 0
    assert kwargs["top_p"] == 1
    assert kwargs["enable_thinking"] is False


@pytest.mark.asyncio
async def test_json_v2_schema_still_whitelists_only_discussion_suggestion():
    row = _structured_discussion(
        physician_sign_marker="赵医生",
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
