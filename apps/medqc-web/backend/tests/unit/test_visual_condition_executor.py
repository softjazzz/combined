from __future__ import annotations

from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from app.services.qc_rule_orchestrator import QCRuleOrchestrator
from app.routers import custom_qc
from fastapi import Request
from app.services.visual_condition_executor import VisualConditionExecutor
from app.services.visual_condition_service import (
    VisualConditionInvalid,
    normalize_visual_condition,
    visual_condition_options,
)


def _condition(kind: str, **values):
    return {"id": values.pop("id", f"c-{kind}"), "kind": kind, **values}


def _config(*conditions, group_operator: str = "all", root_operator: str = "all"):
    return {
        "schema_version": "visual-condition-v1",
        "root_operator": root_operator,
        "groups": [
            {
                "id": "group-1",
                "operator": group_operator,
                "conditions": list(conditions),
            }
        ],
    }


def _record(*, readiness: str = "complete", first_course=(), admission="2026-01-01 08:00:00"):
    return {
        "id": "visit-1",
        "evidence_payload": {
            "programmatic_timeline": {
                "admission_time": admission,
                "admission_time_basis": "registration_admission_datetime",
                "admission_time_trusted": True,
                "discharge_time": "2026-01-03 08:00:00",
                "discharge_time_trusted": True,
                "documents": {"first_course_record": list(first_course)},
                "source_readiness": {"first_course_record": readiness},
            }
        },
    }


def _evaluate(config, record):
    return VisualConditionExecutor().evaluate(
        rule={"rule_code": "LXE-TEST", "name": "测试规则", "check_logic": {"visual_condition": config}},
        medical_record=record,
    )


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def _qc_service():
    return SimpleNamespace(
        client=SimpleNamespace(model="unit-test"),
        rule_orchestrator=QCRuleOrchestrator(),
        rule_engine=SimpleNamespace(evaluate=AsyncMock(side_effect=AssertionError("LLM not allowed"))),
        execution_cache=None,
    )


def test_options_are_explicit_and_do_not_offer_free_expressions():
    options = visual_condition_options()
    assert options["schema_version"] == "visual-condition-v1"
    assert {item["value"] for item in options["document_types"]} >= {
        "first_course_record",
        "discharge_record",
    }
    assert isinstance(options["timeliness"]["allowed_pairs"], list)
    assert all(set(item) == {"start_fact", "end_fact"} for item in options["timeliness"]["allowed_pairs"])
    department = next(item for item in options["fields"] if item["key"] == "record.department")
    assert {item["value"] for item in department["operators"]} == {
        "eq", "ne", "in", "not_in", "exists", "not_exists",
    }


def test_normalizer_rejects_unknown_fact_and_free_expression():
    with pytest.raises(VisualConditionInvalid):
        normalize_visual_condition(
            _config(_condition("field", fact_key="record.secret", operator="eq", value="x"))
        )
    raw = _config(_condition("document_presence", document_type="first_course_record", operator="exists"))
    raw["expression"] = "exec('x')"
    with pytest.raises(VisualConditionInvalid):
        normalize_visual_condition(raw)


@pytest.mark.parametrize(
    "condition",
    [
        _condition("field", fact_key="record.department", operator="eq", value=True),
        _condition("field", fact_key="record.department", operator="in", value=["心内科", None]),
        _condition("field", fact_key="record.department", operator="exists", value="多余"),
    ],
)
def test_field_values_are_strictly_typed(condition):
    with pytest.raises(VisualConditionInvalid):
        normalize_visual_condition(_config(condition))


@pytest.mark.parametrize(
    ("group_operator", "conditions", "expected"),
    [
        (
            "all",
            (
                _condition("document_presence", id="known-false", document_type="first_course_record", operator="exists"),
                _condition("document_presence", id="unknown", document_type="surgery_record", operator="exists"),
            ),
            "compliant",
        ),
        (
            "any",
            (
                _condition("document_presence", id="known-true", document_type="first_course_record", operator="not_exists"),
                _condition("document_presence", id="unknown", document_type="surgery_record", operator="exists"),
            ),
            "non_compliant",
        ),
        (
            "all",
            (_condition("document_presence", id="unknown", document_type="surgery_record", operator="exists"),),
            "data_gap",
        ),
    ],
)
def test_kleene_three_value_groups(group_operator, conditions, expected):
    result = _evaluate(_config(*conditions, group_operator=group_operator), _record())
    assert result["status"] == expected
    assert result["metadata"]["tokens_used"] == 0


def test_not_exists_requires_complete_source_readiness():
    condition = _condition(
        "document_presence",
        document_type="first_course_record",
        operator="not_exists",
    )
    assert _evaluate(_config(condition), _record(readiness="complete"))["status"] == "non_compliant"
    gap = _evaluate(_config(condition), _record(readiness="partial"))
    assert gap["status"] == "data_gap"
    assert gap["issues"] == []


def test_timeliness_uses_only_complete_trusted_source_record_times_and_hospital_timezone():
    condition = _condition(
        "timeliness",
        start_fact="record.admission_datetime",
        end_fact="document.first_course_record.earliest_authored_at",
        operator="gt",
        threshold={"value": 24, "unit": "hours"},
    )
    trusted = {
        "visual_record_time": "2026-01-02T09:00:00+08:00",
        "visual_record_time_trusted": True,
    }
    result = _evaluate(_config(condition), _record(first_course=(trusted,)))
    assert result["status"] == "non_compliant"
    trace = result["metadata"]["visual_condition_trace"][0]["conditions"][0]
    assert trace["actual_seconds"] == 25 * 3600
    assert trace["threshold"] == {"value": 24, "unit": "hours"}

    fallback_only = {"authored_at": "2026-01-02 09:00:00", "time_basis": "update_time_fallback"}
    assert _evaluate(_config(condition), _record(first_course=(fallback_only,)))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_published_workspace_visual_rule_uses_program_dispatch_without_llm():
    config = _config(
        _condition(
            "document_presence",
            document_type="first_course_record",
            operator="not_exists",
        )
    )
    llm = AsyncMock(side_effect=AssertionError("visual rule must not call llm"))
    result = await QCRuleOrchestrator().evaluate_rules(
        rules=[{
            "rule_id": "LXE-PUBLISHED",
            "name": "已发布自定义规则",
            "check_logic": {
                "source": "custom_rule_workspace",
                "workspace_draft_id": "draft-1",
                "visual_condition": config,
            },
        }],
        medical_record=_record(),
        llm_evaluate=llm,
        execution_cache=None,
    )
    assert result["results"][0]["status"] == "non_compliant"
    assert result["executor_breakdown"] == {"program": 1, "llm": 0, "llm_fallback": 0}
    llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_visual_schema_fails_closed_without_llm():
    llm = AsyncMock(side_effect=AssertionError("invalid visual rule must not call llm"))
    result = await QCRuleOrchestrator().evaluate_rules(
        rules=[{
            "rule_id": "LXE-BROKEN",
            "check_logic": {"visual_condition": {"schema_version": "future-v9"}},
        }],
        medical_record=_record(),
        llm_evaluate=llm,
        execution_cache=None,
    )
    assert result["results"][0]["status"] == "technical_error"
    llm.assert_not_awaited()


def test_department_source_is_lazy_and_read_failure_is_technical_error(monkeypatch):
    from app.services.medical_records import query_service

    monkeypatch.setattr(
        query_service,
        "load_scoring_departments",
        lambda *_args, **_kwargs: pytest.fail("非科室条件不得读取科室owner"),
    )
    presence = _condition(
        "document_presence", document_type="first_course_record", operator="not_exists",
    )
    assert _evaluate(_config(presence), _record())["status"] == "non_compliant"

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(query_service, "load_scoring_departments", unavailable)
    department = _condition(
        "field", fact_key="record.department", operator="eq", value="心内科",
    )
    record = {
        **_record(),
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "V1",
    }
    result = _evaluate(_config(department), record)
    assert result["status"] == "technical_error"
    assert result["metadata"]["visual_condition_error"] == "department_source_unavailable"


def test_registration_source_failure_is_technical_error_only_when_time_fact_is_required():
    condition = _condition(
        "field", fact_key="record.admission_datetime", operator="exists",
    )
    unavailable = _record()
    unavailable["evidence_payload"]["programmatic_timeline"][
        "registration_source_readiness"
    ] = "unavailable"

    result = _evaluate(_config(condition), unavailable)
    assert result["status"] == "technical_error"
    assert result["metadata"]["visual_condition_error"] == "registration_source_unavailable"

    complete_without_value = _record(admission=None)
    complete_without_value["evidence_payload"]["programmatic_timeline"].update({
        "admission_time_trusted": False,
        "registration_source_readiness": "complete",
    })
    assert _evaluate(_config(condition), complete_without_value)["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["single", "batch"])
async def test_workspace_test_paths_use_server_visual_hydration_and_allow_empty_text(
    endpoint, monkeypatch,
):
    config = _config(
        _condition(
            "document_presence", document_type="first_course_record", operator="not_exists",
        )
    )
    draft = {
        "id": "draft-1",
        "rule_code": "LXE-0001",
        "name": "首程缺失",
        "document_type": "首次病程记录",
        "check_logic": {"visual_condition": config},
    }

    class Workspace:
        def __init__(self):
            self.visual_calls = 0
            self.summaries = []

        def get_draft(self, **_kwargs):
            return draft

        def hydrate_records_with_visual_evidence(self, _records):
            self.visual_calls += 1
            return [{
                "record_id": "V1",
                "visit_id": "V1",
                "medical_text": "",
                **_record(),
            }]

        def hydrate_records_with_medical_text(self, _records):
            pytest.fail("visual路径不得使用仅正文水合")

        def save_last_test_summary(self, **kwargs):
            self.summaries.append(kwargs["summary"])

    workspace = Workspace()
    monkeypatch.setattr(custom_qc, "audit_event", lambda *_args, **_kwargs: None)
    payload = custom_qc.WorkspaceTestRequest.model_validate({
        "draft_id": "draft-1",
        "records": [{
            "institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
            "record_id": "V1", "medical_text": "客户端正文不得作为事实",
        }],
    })
    if endpoint == "single":
        response = await custom_qc.test_workspace_single(
            request=_request(), payload=payload, qc_service=_qc_service(),
            current_user={"id": "manager-1"}, workspace=workspace,
        )
        assert response["data"]["result"]["status"] == "non_compliant"
    else:
        response = await custom_qc.test_workspace_batch(
            request=_request(), payload=payload, qc_service=_qc_service(),
            current_user={"id": "manager-1"}, workspace=workspace,
        )
        assert response["data"]["items"][0]["status"] == "non_compliant"
    assert workspace.visual_calls == 1
    assert workspace.summaries[0]["executor_breakdown"] if endpoint == "batch" else True


@pytest.mark.asyncio
async def test_workspace_visual_http_contract_missing_case_coordinates_fails_closed():
    config = _config(
        _condition(
            "document_presence", document_type="first_course_record", operator="not_exists",
        )
    )

    class Workspace:
        def get_draft(self, **_kwargs):
            return {
                "id": "draft-1", "rule_code": "LXE-0001", "name": "首程缺失",
                "document_type": "首次病程记录",
                "check_logic": {"visual_condition": config},
            }

        def hydrate_records_with_visual_evidence(self, records):
            assert records[0]["institute_id"] is None
            assert records[0]["patient_id"] is None
            return [{
                "record_id": "SAME", "visit_id": "SAME", "medical_text": "",
                "visual_evidence_error": "record_identity_unavailable",
            }]

        def save_last_test_summary(self, **_kwargs):
            return None

    payload = custom_qc.WorkspaceTestRequest.model_validate({
        "draft_id": "draft-1",
        "records": [{"record_id": "SAME", "visit_id": "SAME", "medical_text": ""}],
    })
    response = await custom_qc.test_workspace_single(
        request=_request(), payload=payload, qc_service=_qc_service(),
        current_user={"id": "manager-1"}, workspace=Workspace(),
    )
    assert response["data"]["result"]["status"] == "technical_error"
    assert response["data"]["result"]["issues"] == []
