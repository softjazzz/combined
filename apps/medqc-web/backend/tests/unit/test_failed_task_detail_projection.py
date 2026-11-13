"""失败任务读取投影：合成数据，不连接数据库、不执行规则。"""
from copy import deepcopy
import pytest
from app.services.custom_qc_workspace_service import project_customer_safe_batch_job


def project(failure):
    job = {"id": "synthetic-failed", "status": "failed", "items": [],
           "failed_records": [failure], "error_message": "SECRET-RAW-EXCEPTION"}
    original = deepcopy(job)
    dto = project_customer_safe_batch_job(job, hmac_key="synthetic", _validate_luxian=False)
    assert job == original
    assert "SECRET" not in str(dto)
    return dto["failed_records"][0]


@pytest.mark.parametrize("code", ["model_transport_error", "model_timeout", "model_invalid_output", "model_parse_error"])
def test_known_model_failure_is_preserved_without_raw_error(code):
    dto = project({"reason_code": code, "error_phase": "evaluate_document",
                   "rule_id": "LX0609-04-01-04", "error": "SECRET-KEY"})
    assert dto["reason_code"] == code
    assert dto["error_phase"] == "evaluate_document"
    assert dto["rule_id"] == "LX0609-04-01-04"
    assert dto["status"] == "technical_error"


def test_material_error_uses_controlled_code():
    dto = project({"error": "uncaptured_material_columns", "error_phase": "material_capture"})
    assert dto["reason_code"] == "uncaptured_material_columns"
    assert dto["error_phase"] == "material_capture"


def test_unknown_fields_remain_redacted():
    dto = project({"reason_code": "SECRET-MODEL", "error_phase": "SECRET-PATH", "error": "SECRET-DSN"})
    assert dto["reason_code"] == "record_execution_failed"
    assert "error_phase" not in dto


def test_legacy_failure_contract_is_unchanged():
    dto = project({})
    assert set(dto) == {"record_ref", "status", "reason_code", "rule_id"}
    assert dto["reason_code"] == "record_execution_failed"
