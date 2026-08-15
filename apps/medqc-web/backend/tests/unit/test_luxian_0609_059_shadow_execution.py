from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.settings import Settings
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.execution import (
    aggregate_luxian_0609_orchestrated_results,
    attach_luxian_0609_execution_metadata,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609.native_treatment_order_consistency import TreatmentOrderConsistencyResult
from app.services.luxian_0609.source_evidence_reader import (
    SnapshotSourceRows,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.treatment_order_consistency_shadow import (
    LUXIAN_0609_059_SHADOW_CONTRACT_VERSION,
    run_luxian_0609_059_shadow,
)


RULE_ID = "LX0609-059"
COORDINATES = ("PRIVATE-INSTITUTE", "PRIVATE-PATIENT", "PRIVATE-VISIT")


class FakeLLM:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def generate(self, prompt: str, **_: Any) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("PRIVATE-LLM-FAILURE")
        event_refs = re.findall(r'"event_ref":"([^"]+)"', prompt)
        course_refs = re.findall(r'"course_ref":"([^"]+)"', prompt)
        return {
            "events": [
                {
                    "event_ref": ref,
                    "verdict": "consistent",
                    "course_refs": course_refs[:1],
                }
                for ref in event_refs
            ],
            "usage": {"prompt_tokens": 17, "completion_tokens": 5},
        }


def rows_by_source() -> dict[str, list[dict[str, Any]]]:
    return {
        "exam_master": [{
            "exam_id": "RAW-EXAM-ID", "order_id": "RAW-ORDER-ID",
            "exam_name": "头颅CT", "exam_time": "2026-08-14T08:30:00+08:00",
            "record_content": "PRIVATE-EXAM-BODY",
        }],
        "exam_item_report": [{
            "document_id": "RAW-REPORT-ID", "exam_id": "RAW-EXAM-ID",
            "exam_name": "头颅CT", "report_time": "2026-08-14T09:00:00+08:00",
            "record_content": "PRIVATE-REPORT-BODY",
        }],
        "surgery_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [{
            "order_id": "RAW-ORDER-ID", "order_name": "头颅CT检查",
            "order_status": "已执行", "order_time": "2026-08-14T08:00:00+08:00",
            "record_content": "PRIVATE-ORDER-BODY",
        }],
        "daily_course_record": [{
            "document_id": "RAW-COURSE-ID", "document_title": "日常病程记录",
            "record_time": "2026-08-14T10:00:00+08:00",
            "record_content": "复核头颅CT检查并继续观察。PRIVATE-COURSE-BODY",
        }],
        "senior_course_record": [],
    }


def evidence_session(*, omit_source: str = ""):
    source_rows = rows_by_source()

    def read(**kwargs: Any) -> SnapshotSourceRows:
        source_key = kwargs["source_key"]
        if source_key == omit_source:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=source_rows.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0], patient_id=COORDINATES[1], visit_id=COORDINATES[2],
        source_schema=None, created_at="2026-08-15T09:00:00+08:00", row_reader=read,
    )


def settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
        "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": False,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        "LUXIAN_0609_059_SHADOW_ENABLED": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def prepare(
    monkeypatch: pytest.MonkeyPatch, *, config: SimpleNamespace,
    selected_rule_ids: tuple[str, ...] = (RULE_ID,),
    coordinates: tuple[str, str, str] = COORDINATES,
    session: Any = None, llm_client: Any = None,
):
    if session is not None:
        monkeypatch.setattr(
            "app.services.luxian_0609.execution.build_luxian_0609_evidence_read_session",
            lambda **_: session,
        )
    return asyncio.run(prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[{"rule_id": rule_id} for rule_id in selected_rule_ids],
        visit_id=coordinates[2], medical_text="", evidence_payload=None,
        llm_client=llm_client or FakeLLM(), settings=config,
        institute_id=coordinates[0], patient_id=coordinates[1],
        selected_customer_rule_ids=selected_rule_ids,
    ))


def attach(context: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    attach_luxian_0609_execution_metadata(
        orchestrated=metadata, rule_set_key=LUXIAN_0609_RULE_SET_KEY, context=context,
    )
    return metadata


def formal_result(context: Any) -> dict[str, Any]:
    results = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id=COORDINATES[2],
        model_name="unused", evidence_payload=None,
    )["results"]
    return next(item for item in results if item["rule_id"] == RULE_ID)


def test_059_shadow_setting_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUXIAN_0609_059_SHADOW_ENABLED", raising=False)
    assert Settings(JWT_SECRET="test-secret").LUXIAN_0609_059_SHADOW_ENABLED is False


@pytest.mark.parametrize(
    ("enabled", "selected_rule_ids", "coordinates"),
    (
        (False, (RULE_ID,), COORDINATES),
        (True, ("LX0609-001",), COORDINATES),
        (True, (RULE_ID,), ("", COORDINATES[1], COORDINATES[2])),
    ),
)
def test_prerequisite_failures_do_not_call_llm_or_attach_metadata(
    monkeypatch: pytest.MonkeyPatch, enabled: bool,
    selected_rule_ids: tuple[str, ...], coordinates: tuple[str, str, str],
) -> None:
    llm = FakeLLM()
    _, context = prepare(
        monkeypatch, config=settings(LUXIAN_0609_059_SHADOW_ENABLED=enabled),
        selected_rule_ids=selected_rule_ids, coordinates=coordinates, llm_client=llm,
    )
    assert llm.calls == 0
    assert "luxian_0609_059_shadow" not in attach(context)


def test_missing_evidence_session_does_not_attach_shadow_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.luxian_0609.execution.build_luxian_0609_evidence_read_session",
        lambda **_: (_ for _ in ()).throw(RuntimeError("PRIVATE-SOURCE-FAILURE")),
    )
    llm = FakeLLM()
    _, context = prepare(
        monkeypatch,
        config=settings(),
        selected_rule_ids=("LX0609-050", RULE_ID),
        llm_client=llm,
    )
    assert llm.calls == 0
    assert "luxian_0609_059_shadow" not in attach(context)


def test_enabled_shadow_calls_llm_once_attaches_safe_summary_and_keeps_formal_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    executable_rules, context = prepare(
        monkeypatch, config=settings(), selected_rule_ids=("LX0609-050", RULE_ID),
        session=evidence_session(), llm_client=llm,
    )
    shadow = attach(context)["luxian_0609_059_shadow"]
    assert [item["rule_id"] for item in executable_rules] == ["LX0609-050"]
    assert llm.calls == 1
    assert shadow == {
        "shadow_only": True, "release_eligible": False,
        "status": "compliant", "reason_code": "requirement_satisfied",
        "event_count": 1, "matched_order_count": 1,
        "missing_order_count": 0, "conflict_order_count": 0,
        "llm_calls": 1, "prompt_tokens": 17, "completion_tokens": 5,
        "total_tokens": 22, "elapsed_ms": shadow["elapsed_ms"],
        "contract_version": LUXIAN_0609_059_SHADOW_CONTRACT_VERSION,
    }
    assert isinstance(shadow["elapsed_ms"], int) and shadow["elapsed_ms"] >= 0
    serialized = json.dumps(shadow, ensure_ascii=False)
    for private_value in (*COORDINATES, "RAW-EXAM-ID", "RAW-ORDER-ID", "RAW-REPORT-ID",
                          "RAW-COURSE-ID", "PRIVATE-EXAM-BODY", "PRIVATE-ORDER-BODY",
                          "PRIVATE-COURSE-BODY"):
        assert private_value not in serialized
    assert "prompt" not in shadow
    assert "response" not in shadow

    formal = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": [], "total_prompt_tokens": 3,
                      "total_completion_tokens": 4, "total_tokens": 7},
        context=context, visit_id=COORDINATES[2], model_name="unused", evidence_payload=None,
    )
    assert (formal["total_prompt_tokens"], formal["total_completion_tokens"], formal["total_tokens"]) == (3, 4, 7)
    formal_059 = next(item for item in formal["results"] if item["rule_id"] == RULE_ID)
    assert formal_059["status"] == "not_executed"


def test_missing_material_source_is_controlled_and_keeps_formal_result(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM()
    _, context = prepare(
        monkeypatch, config=settings(), selected_rule_ids=("LX0609-050", RULE_ID),
        session=evidence_session(omit_source="exam_item_report"),
        llm_client=llm,
    )
    shadow = attach(context)["luxian_0609_059_shadow"]
    assert llm.calls == 0
    assert shadow["status"] == "data_gap"
    assert shadow["reason_code"] == "events_source_unavailable"
    assert formal_result(context)["status"] == "not_executed"


@pytest.mark.parametrize("failure", ("invalid_core", "llm_exception"))
def test_shadow_failures_fail_open_and_keep_formal_059_not_executed(
    monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    llm = FakeLLM(fail=failure == "llm_exception")
    if failure == "invalid_core":
        async def invalid_core(**_: Any) -> TreatmentOrderConsistencyResult:
            return TreatmentOrderConsistencyResult(
                final_state="PRIVATE-INVALID-STATE", reason_code="PRIVATE-INVALID-REASON",
                llm_call_count=2, prompt_tokens=1, completion_tokens=1,
            )
        monkeypatch.setattr(
            "app.services.luxian_0609.treatment_order_consistency_shadow.evaluate_lx0609_059_treatment_order_consistency",
            invalid_core,
        )
    _, context = prepare(
        monkeypatch, config=settings(), selected_rule_ids=("LX0609-050", RULE_ID),
        session=evidence_session(), llm_client=llm,
    )
    shadow = attach(context)["luxian_0609_059_shadow"]
    assert shadow["status"] == "shadow_error"
    assert shadow["reason_code"] in {"result_contract_invalid", "llm_transport_error"}
    serialized = json.dumps(shadow, ensure_ascii=False)
    assert "PRIVATE-INVALID" not in serialized
    assert "PRIVATE-LLM-FAILURE" not in serialized
    assert formal_result(context)["status"] == "not_executed"


def test_shadow_runner_without_material_store_returns_no_metadata() -> None:
    llm = FakeLLM()
    summary = asyncio.run(run_luxian_0609_059_shadow(
        enabled=True, selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0], patient_id=COORDINATES[1], visit_id=COORDINATES[2],
        evidence_materials=None, llm_client=llm,
    ))
    assert summary is None
    assert llm.calls == 0
