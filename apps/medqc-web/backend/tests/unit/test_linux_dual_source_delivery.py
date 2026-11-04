"""离线交付只补包装和验收，不改变医学执行器。"""
import hashlib
import json
from pathlib import Path


APP = Path(__file__).resolve().parents[3]


def test_offline_defaults_have_no_remote_or_background_activation():
    path = APP / "scripts/linux_offline/deploy/business.env.example"
    values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    assert values["QC_TASK_DISPATCH_MODE"] == "legacy"
    assert values["MEDQC_STARTUP_BACKGROUND_ENABLED"] == "false"
    assert values["MEDQC_RESUME_QC_TASKS"] == "false"
    assert values["QC_SC_RULE_SOURCE_MONITOR_ENABLED"] == "false"
    assert values["CDM_DATABASE_URL"] == values["CDM_PGPASSFILE"] == ""
    assert not any("API_KEY" in key for key in values)
    assert values["LLM_LOCAL_TOKEN_BUDGET_ENABLED"] == "false"


def test_synthetic_clinical_schema_has_provenance_and_no_rows():
    path = APP / "scripts/linux_offline/tests/clinical-schema-060.sql"
    provenance = json.loads(path.with_suffix(".provenance.json").read_text())
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance["schema_sha256"]
    assert provenance["tables"] == raw.count(b"CREATE TABLE cdm.") == 68
    assert provenance["schema_only"] and provenance["synthetic_only"]
    assert b"INSERT INTO " not in raw and b"COPY " not in raw
    assert b"SET transaction_timeout" not in raw


def test_archive_scope_and_current_source_baseline_are_not_stale():
    code = (APP / "scripts/linux_offline/collect.py").read_text(encoding="utf-8")
    assert '"source_base": "998f7ac94ff6d9bf3a5a52383c0f909a36ad6509"' in code
    assert "CDM opt-in" in code
    assert "CDM is not connected" not in code
