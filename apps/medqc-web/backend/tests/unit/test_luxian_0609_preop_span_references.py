"""术前文书单片段引用合同；语义由固定事实模拟，不宣称抽取准确率。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.luxian_0609.native_preop_content_execution import (
    _document_spans,
    _prompt,
    _source_text,
    _validate_response,
    evaluate_preop_content_rules,
)
from test_luxian_0609_preop_fact_protocol import (
    DISCUSSION,
    SUMMARY,
    TEXT,
    fact,
    assert_invalid_preop_field,
    present_items,
    publish,
)


def span(state="present", span_id="d1:s2", reviewed=True):
    return {"state": state, "span_id": span_id, "reviewed_all_sections": reviewed}


@pytest.mark.parametrize(
    "rule,field", [(SUMMARY, "precautions"), (DISCUSSION, "preop_preparation")]
)
def test_valid_single_span_reaches_published_result(rule, field):
    items = present_items(rule)
    items[field] = span()
    final, prompt = publish(rule, items=items)
    assert final["status"] == "compliant"
    assert '"span_id": "d1:s2"' in prompt
    assert "麻醉方案已拟定。" in prompt


@pytest.mark.parametrize(
    "state,reviewed", [("missing", True), ("unknown", True), ("unknown", False)]
)
def test_span_absence_keeps_three_state_contract(state, reviewed):
    items = present_items(SUMMARY)
    items["precautions"] = span(state, None, reviewed)
    final, _ = publish(SUMMARY, items=items)
    facts = final["customer_display_facts"]
    assert final["status"] == ("non_compliant" if state == "missing" else "data_gap")
    assert facts["missing_fields"] == (["precautions"] if state == "missing" else [])
    if state == "unknown":
        assert facts["uncertain_fields"] == ["precautions"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        1,
        ["d1:s1", "d1:s3"],
        {},
        "d2:s2",
        "d1:s999",
        "d1:s1+d1:s3",
        "d1:s02",
    ],
)
def test_invalid_or_noncontinuous_reference_is_not_repaired(value):
    items = present_items(SUMMARY)
    items["precautions"] = span(span_id=value)
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_invalid_output"
    assert not final.get("customer_display_facts")
    assert_invalid_preop_field(items, SUMMARY, "precautions")


@pytest.mark.parametrize(
    "value",
    [
        span("missing", "d1:s2"),
        span("unknown", "d1:s2"),
        span("missing", None, False),
        span(reviewed=1),
        {**span(), "quote": "麻醉方案已拟定。"},
    ],
)
def test_invalid_span_shape_keeps_failure_semantics(value):
    items = present_items(SUMMARY)
    items["precautions"] = value
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_invalid_output"
    assert not final.get("customer_display_facts")
    assert_invalid_preop_field(items, SUMMARY, "precautions")


def test_different_fields_can_reuse_the_same_original_span():
    items = present_items(SUMMARY)
    items["precautions"] = span()
    items["planned_anesthesia"] = span()
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "compliant"


def test_old_quotes_keep_strict_compatibility_and_no_repair():
    for value in ("麻醉方案已拟定", fact("present", "麻醉方案已拟定")):
        items = present_items(SUMMARY)
        items["precautions"] = value
        final, _ = publish(SUMMARY, items=items)
        assert final["status"] == "compliant"
    for value in (
        "拟行甲手术麻醉方案已拟定",
        fact("present", "拟行甲手术…麻醉方案已拟定"),
    ):
        items = present_items(SUMMARY)
        items["precautions"] = value
        final, _ = publish(SUMMARY, items=items)
        assert final["status"] == "technical_error"
        assert final["reason_code"] == "model_invalid_output"
        assert not final.get("customer_display_facts")
        assert_invalid_preop_field(items, SUMMARY, "precautions")


def test_planned_procedure_requires_existing_short_quote_not_sentence_span():
    items = present_items(SUMMARY)
    items["planned_procedure"] = span(span_id="d1:s1")
    final, prompt = publish(SUMMARY, items=items)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_invalid_output"
    assert not final.get("customer_display_facts")
    assert_invalid_preop_field(items, SUMMARY, "planned_procedure")
    assert "planned_procedure" in prompt and "短" in prompt


def test_cross_document_id_is_rejected_even_when_both_documents_exist():
    expected = {("presurg_summary", "A"): TEXT, ("presurg_summary", "B"): TEXT}
    first, second = present_items(SUMMARY), present_items(SUMMARY)
    first["precautions"] = span(span_id="d2:s2")
    payload = {
        "documents": [
            {"document_id": "A", "source_type": "presurg_summary", "items": first},
            {"document_id": "B", "source_type": "presurg_summary", "items": second},
        ]
    }
    validated = _validate_response(payload, expected, (SUMMARY,))
    assert validated.rule_failures == {SUMMARY: ("field", ("precautions",))}
    assert validated.parsed == {}


def test_invalid_discussion_span_keeps_summary_rule_valid():
    expected = {("presurg_summary", "A"): TEXT, ("presurg_discussion", "B"): TEXT}
    summary, discussion = present_items(SUMMARY), present_items(DISCUSSION)
    summary["precautions"] = span()
    discussion["preop_preparation"] = span(span_id="d1:s2")
    validated = _validate_response(
        {
            "documents": [
                {
                    "document_id": "A",
                    "source_type": "presurg_summary",
                    "items": summary,
                },
                {
                    "document_id": "B",
                    "source_type": "presurg_discussion",
                    "items": discussion,
                },
            ]
        },
        expected,
        (SUMMARY, DISCUSSION),
    )
    assert validated.rule_failures == {DISCUSSION: ("field", ("preop_preparation",))}
    assert set(validated.parsed) == {("presurg_summary", "A")}
    assert validated.parsed[("presurg_summary", "A")]["precautions"] == fact(
        "present", "麻醉方案已拟定。"
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "  ",
        "甲。\n\n乙！？ 丙；丁，戊",
        "\r\n甲\t乙。\n",
        "无手术指征。仍待补充意见。",
        "甲?乙!丙.丁",
    ],
)
def test_spans_preserve_all_characters_order_and_stable_ids(text):
    catalog = _document_spans(text, 1)
    assert "".join(catalog.values()) == text
    assert catalog == _document_spans(text, 1)
    assert list(catalog) == [f"d1:s{i}" for i in range(1, len(catalog) + 1)]


def test_prompt_retains_all_controlled_projections_and_sentence_context():
    row = {
        "record_content": "未发现禁忌。仍需术前准备。",
        "host_name": "合成人员",
        "host_summary": "主持意见。",
        "discuss_staff": "合成参加者",
        "record_time": "2026-01-01",
        "v2_schema": {"discuss_suggestion": "讨论建议。", "secret": "不允许投影"},
    }
    text = _source_text("presurg_discussion", row)
    prompt = _prompt(
        [("A", "presurg_discussion", text), ("B", "presurg_summary", TEXT)],
        (DISCUSSION, SUMMARY),
    )
    docs = json.loads(prompt.split("\n\n文书：\n", 1)[1])["documents"]
    assert "text" not in docs[0]
    assert "".join(s["text"] for s in docs[0]["spans"]) == text
    assert "".join(s["text"] for s in docs[1]["spans"]) == TEXT
    assert "未发现禁忌。" in [s["text"] for s in docs[0]["spans"]]
    assert "仍需术前准备。" in [s["text"] for s in docs[0]["spans"]]
    assert "不允许投影" not in prompt
    assert "主持意见" in prompt and "讨论建议" in prompt
    assert all(s["span_id"].startswith("d2:") for s in docs[1]["spans"])


def test_whitespace_only_span_cannot_be_present():
    items = present_items(DISCUSSION)
    items["preop_preparation"] = span(span_id="d1:s2")
    payload = {
        "documents": [
            {"document_id": "A", "source_type": "presurg_discussion", "items": items}
        ]
    }
    validated = _validate_response(
        payload,
        {("presurg_discussion", "A"): "拟行甲手术。\n正文另有准备。"},
        (DISCUSSION,),
    )
    assert validated.rule_failures == {DISCUSSION: ("field", ("preop_preparation",))}


@pytest.mark.parametrize(
    "short_quote,expected_states",
    [
        ("甲手术", ["matched", "matched"]),
        ("甲手术，另论乙手术", ["ambiguous", "matched"]),
    ],
)
def test_mixed_span_and_short_quote_preserves_existing_surgery_association(
    short_quote, expected_states
):
    from test_luxian_0609_native_preop_content_execution import (
        _Client,
        _payload,
        _session,
        _surgery_record,
    )

    first_text, second_text = (
        "拟行甲手术，另论乙手术。其余内容已逐项核查。",
        "拟行乙手术。其余内容已逐项核查。",
    )
    session = _session(
        summary=(
            {"document_id": "A", "record_content": first_text},
            {"document_id": "B", "record_content": second_text},
        ),
        surgery_records=(
            _surgery_record(
                document_id="S1", name="甲手术", begin="2026-01-01 08:00:00+08:00"
            ),
            _surgery_record(
                document_id="S2", name="乙手术", begin="2026-01-01 12:00:00+08:00"
            ),
        ),
    )
    first, second = present_items(SUMMARY), present_items(SUMMARY)
    for field in first:
        first[field], second[field] = span(span_id="d1:s2"), span(span_id="d2:s2")
    first["planned_procedure"], second["planned_procedure"] = (
        fact("present", short_quote),
        fact("present", "乙手术"),
    )
    client = _Client(
        _payload(
            {"document_id": "A", "source_type": "presurg_summary", "items": first},
            {"document_id": "B", "source_type": "presurg_summary", "items": second},
        )
    )
    result = asyncio.run(
        evaluate_preop_content_rules(
            rule_ids=(SUMMARY,),
            snapshot=session.snapshot,
            materials=session.materials,
            llm_client=client,
        )
    )
    facts = dict(result.customer_display_facts)[SUMMARY]
    assert [d["association_state"] for d in facts["documents"]] == expected_states
    assert len(client.prompts) == 1 and result.llm_call_count == 1
    assert client.prompts[0][1] == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "enable_thinking": False,
    }


@pytest.mark.parametrize(
    "duplicate_text", [TEXT, "另一份同ID正文。正文内容已有实质内容但不能替代第一份。"]
)
def test_duplicate_source_document_identity_is_rejected_before_catalog_or_model(
    duplicate_text,
):
    from test_luxian_0609_native_preop_content_execution import (
        _Client,
        _payload,
        _session,
    )

    session = _session(
        summary=(
            {"document_id": "A", "record_content": TEXT},
            {"document_id": "A", "record_content": duplicate_text},
        )
    )
    items = present_items(SUMMARY)
    items["precautions"] = span()
    client = _Client(
        _payload({"document_id": "A", "source_type": "presurg_summary", "items": items})
    )
    result = asyncio.run(
        evaluate_preop_content_rules(
            rule_ids=(SUMMARY,),
            snapshot=session.snapshot,
            materials=session.materials,
            llm_client=client,
        )
    )
    assert client.prompts == []
    assert result.llm_call_count == 0
    assert result.decisions[0].evidence_state.value == "technical_error"
    assert result.decisions[0].reason_code == "snapshot_mismatch"
