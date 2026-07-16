from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


CREATED_AT = "2026-07-16T12:00:00+08:00"


def _fact(
    fact_type: str,
    *,
    state: str = "present",
    source_key: str = "surgery_record",
    value: object | None = None,
    **extra: object,
) -> dict:
    item = {
        "fact_type": fact_type,
        "state": state,
        "source_key": source_key,
        "current_visit_bound": True,
    }
    if value is not None:
        item["value"] = value
    item.update(extra)
    return item


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "surgery_record": [
            {
                "record_time": "2026-01-01 10:00:00+08",
                "surgeon": "术者甲",
                "recorder": "一助乙",
                "signer": "术者甲",
            }
        ],
        "anesthesia_record": [{"record_time": "2026-01-01 09:00:00+08"}],
        "pathology_exam_report": [{"report_status": "完成"}],
        "implant_usage": [{"device_code": "device-safe", "usage_status": "used"}],
        "inpat_drug_order": [{"drug_code": "drug-safe", "order_status": "执行"}],
        "daily_course_record": [{"record_time": "2026-01-01 12:00:00+08"}],
        "surgery_inform_consent": [{"record_time": "2026-01-01 08:00:00+08"}],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


def _performed() -> dict:
    return _fact("current_visit_surgery_confirmed", state="performed")


def _snapshot_for_surgery(mode: str, *, selected_rule_id: str = "LX0609-024"):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            if mode == "exact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            elif mode == "empty":
                rows = ()
            elif mode == "nonexact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08:00"},)
            elif mode == "unavailable":
                raise SourceEvidenceUnavailable()
            else:
                raise SourceEvidenceQueryError()
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=False,
                limit_rows=50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(selected_rule_id,),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    ).snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_calls"),
    [
        ("exact", "compliant", 1),
        ("empty", "not_applicable", 0),
        ("nonexact", "data_gap", 0),
        ("unavailable", "data_gap", 0),
        ("error", "data_gap", 0),
    ],
)
async def test_snapshot_performed_fact_replaces_surgery_gate_live_query(
    monkeypatch,
    mode: str,
    expected_status: str,
    expected_calls: int,
) -> None:
    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得自行读取手术来源")

    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        forbidden_reader,
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        forbidden_reader,
    )
    client = _Client([{"is_compliant": True}] if expected_calls else [])

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[_fact("current_visit_malignant_surgery_confirmed")]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=_snapshot_for_surgery(mode),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == expected_calls
    assert len(client.prompts) == expected_calls


@pytest.mark.asyncio
async def test_003_snapshot_path_never_falls_back_to_mr_surgery_reader(monkeypatch):
    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得自行读取 mr_surgery")

    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        forbidden_reader,
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        forbidden_reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"surgery_begin_time": "NOT_A_TIME"}],
            anesthesia_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=_snapshot_for_surgery(
            "exact", selected_rule_id="LX0609-003"
        ),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == "surgery_time_unavailable"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_strong_facts_execute_selected_rules_once_in_customer_order(monkeypatch):
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: (
            [
                {
                    "surgery_begin_datetime": "2026-01-01 09:00:00+08",
                    "surgical_level": "四级",
                }
            ]
            if kwargs["source_key"] == "mr_surgery"
            else []
        ),
    )
    facts = [
        _performed(),
        _fact(
            "current_visit_malignant_surgery_confirmed",
            source_key="pathology_exam_report",
        ),
        _fact("current_visit_surgical_implant_used", source_key="implant_usage"),
        _fact(
            "current_visit_surgical_incision_class", source_key="mr_surgery", value="II"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial", source_key="inpat_drug_order"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial_interval",
            state="complete",
            source_key="inpat_drug_order",
            duration_hours=18,
        ),
        _fact(
            "current_visit_surgery_consent_source_readiness",
            state="complete",
            source_key="surgery_inform_consent",
        ),
    ]
    client = _Client(
        [
            {"is_compliant": index % 2 == 0}
            for index in range(len(surgery.SURGERY_GATE_RULE_IDS))
        ]
    )

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=tuple(reversed(surgery.SURGERY_GATE_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in surgery.SURGERY_GATE_RULE_IDS],
        evidence_payload=_payload(facts=facts),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(
        surgery.SURGERY_GATE_RULE_IDS
    )
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 6
    assert result.total_tokens == 660
    assert [item["metadata"]["total_tokens"] for item in result.results] == [110] * 6
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_003_rejects_nonexact_surgery_time_before_model(monkeypatch):
    monkeypatch.setattr(surgery, "read_luxian_0609_native_source_rows", lambda **_: [])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"surgery_begin_time": "NOT_A_TIME"}],
            anesthesia_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_live_strict_surgery_time_supplies_performed_fact_once(monkeypatch):
    runtime_calls = 0

    def _runtime_rows(**_):
        nonlocal runtime_calls
        runtime_calls += 1
        return [{"surgery_begin_time": "2026-01-01 09:00:00+08"}]

    monkeypatch.setattr(surgery, "read_luxian_0609_runtime_source_rows", _runtime_rows)
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **_: [{"surgery_begin_datetime": "2026-01-01 09:00:00+08"}],
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003", "LX0609-031", "LX0609-033"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in ("LX0609-003", "LX0609-031", "LX0609-033")
        ],
        evidence_payload=_payload(
            facts=[
                _fact(
                    "current_visit_surgery_consent_source_readiness",
                    state="complete",
                    source_key="surgery_inform_consent",
                )
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([{"is_compliant": True}] * 3),
    )

    assert runtime_calls == 1
    assert [item["status"] for item in result.results] == ["compliant"] * 3


@pytest.mark.asyncio
async def test_024_silence_is_data_gap_and_explicit_negative_is_not_applicable():
    client = _Client([])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[_performed()],
            pathology_exam_report=[{"diagnosis": "既往恶性肿瘤史，普通标本送检"}],
            surgery_record=[{"surgery_name": "腹部肿物切除术"}],
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0
    assert client.prompts == []

    explicit_negative = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_malignant_surgery_confirmed",
                    state="explicit_negative",
                    source_key="pathology_exam_report",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert explicit_negative.results[0]["status"] == "not_applicable"
    assert explicit_negative.llm_call_count == 0


@pytest.mark.asyncio
async def test_025_silence_and_incomplete_source_are_data_gap_but_explicit_no_implant_is_na():
    silence = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(facts=[_performed()]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    incomplete = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_implant_used",
                    state="partial",
                    source_key="implant_usage",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    explicit_negative = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_implant_used",
                    state="explicit_negative",
                    source_key="implant_usage",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert silence.results[0]["status"] == "data_gap"
    assert incomplete.results[0]["status"] == "data_gap"
    assert explicit_negative.results[0]["status"] == "not_applicable"
    assert (
        silence.llm_call_count
        == incomplete.llm_call_count
        == explicit_negative.llm_call_count
        == 0
    )


@pytest.mark.asyncio
async def test_028_needs_i_ii_prophylaxis_and_complete_actual_interval():
    base_facts = [
        _performed(),
        _fact(
            "current_visit_surgical_incision_class", source_key="mr_surgery", value="I"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial", source_key="inpat_drug_order"
        ),
    ]
    missing_interval = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        wrapper_rules=[_wrapper("LX0609-028")],
        evidence_payload=_payload(facts=base_facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    non_target = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        wrapper_rules=[_wrapper("LX0609-028")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_incision_class",
                    source_key="mr_surgery",
                    value="III",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert missing_interval.results[0]["status"] == "data_gap"
    assert non_target.results[0]["status"] == "not_applicable"
    assert missing_interval.llm_call_count == non_target.llm_call_count == 0


@pytest.mark.asyncio
async def test_003_031_033_fail_closed_at_exact_boundaries(monkeypatch):
    monkeypatch.setattr(surgery, "read_luxian_0609_native_source_rows", lambda **_: [])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003", "LX0609-031", "LX0609-033"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in ("LX0609-003", "LX0609-031", "LX0609-033")
        ],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"record_content": "仅正文，无受控时间及签名字段"}],
            surgery_inform_consent=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "data_gap",
        "data_gap",
    ]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_model_error_invalid_json_and_sensitive_marker_never_echo():
    secret = "Bearer_secret_13800138000"
    facts = [_performed(), _fact("current_visit_malignant_surgery_confirmed")]
    failure = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([RuntimeError(secret)]),
    )
    invalid = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )

    assert failure.results[0]["status"] == invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(failure)
    assert secret not in repr(invalid)
