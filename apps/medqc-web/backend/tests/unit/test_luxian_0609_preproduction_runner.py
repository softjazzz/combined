from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import preproduction_runner


def _all_rule_ids() -> tuple[str, ...]:
    return tuple(f"LX0609-{index:03d}" for index in range(1, 50))


def _bundle() -> dict:
    return {
        "scene": "running",
        "institute_id": "PRIVATE-INSTITUTE-MARKER",
        "patient_id": "PRIVATE-PATIENT-MARKER",
        "visit_id": "PRIVATE-VISIT-MARKER",
        "medical_text": "PRIVATE-BODY-MARKER",
        "structured_context": {
            "documents": {
                "daily_course_record": [
                    {"content": "PRIVATE-DOCUMENT-MARKER"},
                ]
            }
        },
        "source_doc_priority": ["daily_course_record"],
    }


@dataclass
class _FakeContext:
    enabled: bool = True
    native_llm_call_count: int = 2
    native_prompt_tokens: int = 30
    native_completion_tokens: int = 10
    native_total_tokens: int = 40
    native_api_time: float = 0.25


@pytest.mark.asyncio
async def test_preproduction_runner_is_independent_ordered_and_privacy_safe(monkeypatch):
    selected = _all_rule_ids()
    base_settings = SimpleNamespace(UNRELATED_SETTING="kept")
    captured: dict = {}

    async def _fake_prepare(**kwargs):
        captured.update(kwargs)
        assert kwargs["prepared_rules"] == []
        assert kwargs["selected_customer_rule_ids"] == selected
        assert kwargs["evaluation_as_of_date"] == "2026-07-17"
        assert kwargs["settings"] is not base_settings
        assert kwargs["settings"].UNRELATED_SETTING == "kept"
        assert kwargs["settings"].LUXIAN_0609_UNIFIED_ENGINE_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_007_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED is True
        return [], _FakeContext()

    def _fake_aggregate(*, orchestrated, context, **_):
        orchestrated.update(
            {
                "results": [
                    {
                        "rule_id": rule_id,
                        "rule_code": rule_id,
                        "rule_name": rule_id,
                        "status": "compliant",
                        "is_compliant": True,
                        "findings": "就诊PRIVATE-VISIT-MARKER存在问题",
                        "suggestion": "参考正文片段 PRIVATE-BODY-MA",
                        "issues": [{"category": "safe-category"}],
                        "evidence": {"summary": "安全证据摘要"},
                        "qc_point_id": rule_id,
                        "rule_set_key": "luxian_0609_qc_v1",
                        "schema_version": "safe-schema-v1",
                        "executor_type": "program",
                        "result_status": "compliant",
                        "trigger": {"applicable": True},
                        "dependencies": {"source_coverage_level": "full"},
                        "missing_sources": [],
                        "evidence_items": [
                            {
                                "source_table": "daily_course_record",
                                "source_document_type": "日常病程记录",
                                "field_path": "record_time",
                                "evidence_role": "frequency_evidence",
                                "quote": "证据片段 PRIVATE-DOCUMENT-MA",
                                "record_time": "2026-07-17 08:30:00",
                            },
                            {
                                "source_table": "daily_course_record",
                                "source_document_type": "日常病程记录",
                                "field_path": "record_time",
                                "evidence_role": "frequency_summary",
                                "quote": "相邻记录间隔未超过两个自然日。",
                                "record_time": "2026-07-17 09:00:00",
                            },
                        ],
                        "source_table": "daily_course_record",
                        "source_document": "日常病程记录",
                        "source_field": "record_time",
                        "decision": {"decision_summary": "安全判定"},
                        "review": {"review_status": "not_required"},
                        "audit": {
                            "visit_id": "PRIVATE-VISIT-MARKER",
                            "model_name": "private-model",
                            "prompt_version": "PRIVATE-PROMPT-MARKER",
                            "executed_at": "2026-07-17T08:31:00+08:00",
                            "elapsed_ms": 12.5,
                            "technical_status": "success",
                        },
                        "evidence_payload": {"content": "PRIVATE-BODY-MARKER"},
                        "metadata": {
                            "execution_source": "lx0609_native",
                            "prompt": "PRIVATE-PROMPT-MARKER",
                        },
                    }
                    for rule_id in selected
                ],
                "total_prompt_tokens": context.native_prompt_tokens,
                "total_completion_tokens": context.native_completion_tokens,
                "total_tokens": context.native_total_tokens,
                "total_api_time": context.native_api_time,
            }
        )
        return orchestrated

    monkeypatch.setattr(preproduction_runner, "prepare_luxian_0609_execution", _fake_prepare)
    monkeypatch.setattr(
        preproduction_runner,
        "aggregate_luxian_0609_orchestrated_results",
        _fake_aggregate,
    )

    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=base_settings,
        model_name="private-model",
        source_schema="cdm",
    )

    assert tuple(item["rule_id"] for item in result["results"]) == selected
    assert result["metrics"]["llm_call_count"] == 2
    assert result["metrics"]["total_tokens"] == 40
    assert result["metrics"]["rule_decision_count"] == 19
    assert result["metrics"]["typed_shadow_adapter_count"] == 3
    assert result["metrics"]["legacy_projection_count"] == 27
    assert result["metrics"]["customer_rule_count"] == 49
    assert result["metrics"]["technical_error_count"] == 0
    first = result["results"][0]
    assert first["findings"] == "[redacted]"
    assert first["suggestion"] == "[redacted]"
    assert first["issues"] == [{"category": "safe-category"}]
    assert first["evidence"] == {"summary": "安全证据摘要"}
    assert first["evidence_items"][0] == {
        "source_table": "daily_course_record",
        "source_document_type": "日常病程记录",
        "field_path": "record_time",
        "evidence_role": "frequency_evidence",
        "quote": "[redacted]",
        "record_time": "2026-07-17 08:30:00",
    }
    assert first["evidence_items"][1]["quote"] == "相邻记录间隔未超过两个自然日。"
    assert first["evidence_items"][1]["record_time"] == "2026-07-17 09:00:00"
    assert first["decision"] == {"decision_summary": "安全判定"}
    assert first["review"] == {"review_status": "not_required"}
    assert first["audit"] == {
        "executed_at": "2026-07-17T08:31:00+08:00",
        "elapsed_ms": 12.5,
        "technical_status": "success",
    }
    rendered = repr(result)
    for marker in (
        "PRIVATE-INSTITUTE-MARKER",
        "PRIVATE-PATIENT-MARKER",
        "PRIVATE-VISIT-MARKER",
        "PRIVATE-BODY-MARKER",
        "PRIVATE-DOCUMENT-MARKER",
        "PRIVATE-PROMPT-MARKER",
        "evidence_payload",
        "fact_refs",
        "snapshot",
    ):
        assert marker not in rendered
    assert base_settings.__dict__ == {"UNRELATED_SETTING": "kept"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected",
    [
        ("LX0609-001", "LX0609-001"),
        ("LX0609-002", "LX0609-001"),
        ("LX0609-050",),
        ("SC-001",),
        (),
    ],
)
async def test_preproduction_runner_rejects_invalid_or_unordered_scope(selected):
    with pytest.raises(ValueError):
        await preproduction_runner.run_luxian_0609_preproduction(
            bundle=_bundle(),
            selected_customer_rule_ids=selected,
            evaluation_as_of_date="2026-07-17",
            llm_client=object(),
            base_settings=SimpleNamespace(),
            model_name="model",
        )


@pytest.mark.asyncio
async def test_preproduction_runner_isolates_infrastructure_failure_without_echo(monkeypatch):
    async def _raise(**_):
        raise RuntimeError("PRIVATE-EXCEPTION-MARKER")

    monkeypatch.setattr(preproduction_runner, "prepare_luxian_0609_execution", _raise)
    selected = _all_rule_ids()
    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
    )

    assert tuple(item["rule_id"] for item in result["results"]) == selected
    assert {item["status"] for item in result["results"]} == {"technical_error"}
    assert result["metrics"]["technical_error_count"] == 49
    assert result["metrics"]["llm_call_count"] == 0
    assert "PRIVATE-EXCEPTION-MARKER" not in repr(result)


def test_preproduction_runner_does_not_depend_on_router_or_sichuan_service():
    source = preproduction_runner.__file__
    text = open(source, encoding="utf-8").read()
    assert "qc_sichuan" not in text
    assert "SichuanQCService" not in text
    assert "load_or_assemble" not in text
    assert "workspace" not in text.lower()


def test_preproduction_runner_as_of_does_not_preconnect_mainline():
    backend_dir = Path(__file__).resolve().parents[2]
    router_text = (backend_dir / "app/routers/qc_sichuan.py").read_text(
        encoding="utf-8"
    )
    service_text = (backend_dir / "app/services/sichuan_qc_service.py").read_text(
        encoding="utf-8"
    )
    assert "evaluation_as_of_date" not in router_text
    assert "evaluation_as_of_date" not in service_text


def test_preproduction_runner_cold_process_does_not_load_sichuan_service():
    backend_dir = Path(__file__).resolve().parents[2]
    script = r'''
import asyncio
import sys
from types import SimpleNamespace

from app.services.luxian_0609 import preproduction_runner as runner

assert "app.services.sichuan_qc_service" not in sys.modules

class Context:
    native_llm_call_count = 0
    native_prompt_tokens = 0
    native_completion_tokens = 0
    native_total_tokens = 0
    native_api_time = 0.0

async def prepare(**_):
    return [], Context()

def aggregate(*, orchestrated, **_):
    orchestrated["results"] = [
        {
            "rule_id": f"LX0609-{index:03d}",
            "rule_code": f"LX0609-{index:03d}",
            "status": "not_applicable",
            "is_compliant": True,
        }
        for index in range(1, 50)
    ]
    return orchestrated

runner.prepare_luxian_0609_execution = prepare
runner.aggregate_luxian_0609_orchestrated_results = aggregate

async def main():
    result = await runner.run_luxian_0609_preproduction(
        bundle={"scene": "running"},
        selected_customer_rule_ids=tuple(
            f"LX0609-{index:03d}" for index in range(1, 50)
        ),
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
    )
    assert len(result["results"]) == 49
    assert "app.services.sichuan_qc_service" not in sys.modules

asyncio.run(main())
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(backend_dir)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
