from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from app.services.luxian_0609.native_package import (
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from scripts.build_luxian_0609_runtime_manifest import build_runtime_manifest


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "LUXIAN_0609_TRIGGER_GATE_ENABLED": True,
        "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": True,
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXECUTION_ENABLED": True,
        "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": True,
        "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": False,
        "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED": False,
        "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED": True,
        "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
        "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED": True,
        "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_NATIVE_MDT_040_ENABLED": True,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": False,
        "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED": True,
        "LLM_MODEL": "safe-model-name",
        "LLM_ADJUDICATOR_MODEL": "safe-adjudicator-name",
        "LLM_API_KEY": "must-not-leak",
        "LLM_API_ENDPOINT": "https://secret-endpoint.example/v1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_manifest_binds_all_rules_to_current_safe_runtime() -> None:
    manifest = build_runtime_manifest(
        git_head="a" * 40,
        settings=_settings(),
        rule_catalog=load_luxian_0609_rules(),
        inventory=load_luxian_0609_dependency_inventory(),
        generated_at="2026-07-23T18:00:00Z",
    )

    assert manifest["schema_version"] == "lx0609-runtime-manifest-v1"
    assert manifest["git_head"] == "a" * 40
    assert manifest["generated_at"] == "2026-07-23T18:00:00Z"
    assert manifest["rule_set"]["rule_count"] == 49
    assert manifest["rule_set"]["rule_ids"] == [
        f"LX0609-{index:03d}" for index in range(1, 50)
    ]
    assert len(manifest["rules"]) == 49
    assert len({item["rule_id"] for item in manifest["rules"]}) == 49

    by_rule = {item["rule_id"]: item for item in manifest["rules"]}
    assert by_rule["LX0609-020"]["active_path"] == "compatibility"
    assert by_rule["LX0609-029"]["active_path"] == "native"
    assert by_rule["LX0609-030"]["active_path"] == "native"
    assert by_rule["LX0609-032"]["active_path"] == "native"
    assert manifest["flags"]["unified_engine"] is True
    assert manifest["flags"]["rule_decision_surgery_document"] is True
    assert manifest["flags"]["native_consultation"] is False
    assert manifest["runtime"]["models"] == {
        "primary": "safe-model-name",
        "adjudicator": "safe-adjudicator-name",
    }
    assert manifest["runtime"]["gate_only_is_request_scoped"] is True

    encoded = json.dumps(manifest, ensure_ascii=False)
    assert "must-not-leak" not in encoded
    assert "secret-endpoint" not in encoded
    assert "api_key" not in encoded.lower()
    assert "endpoint" not in encoded.lower()


def test_runtime_manifest_identity_ignores_secret_configuration() -> None:
    common = {
        "git_head": "b" * 40,
        "rule_catalog": load_luxian_0609_rules(),
        "inventory": load_luxian_0609_dependency_inventory(),
        "generated_at": "2026-07-23T18:00:00Z",
    }
    first = build_runtime_manifest(
        settings=_settings(
            LLM_API_KEY="secret-a",
            LLM_API_ENDPOINT="https://endpoint-a.example/v1",
        ),
        **common,
    )
    second = build_runtime_manifest(
        settings=_settings(
            LLM_API_KEY="secret-b",
            LLM_API_ENDPOINT="https://endpoint-b.example/v1",
        ),
        **common,
    )

    assert first == second


def test_runtime_manifest_rejects_explicit_empty_inventory() -> None:
    try:
        build_runtime_manifest(
            git_head="c" * 40,
            settings=_settings(),
            rule_catalog=load_luxian_0609_rules(),
            inventory=(),
            generated_at="2026-07-23T18:00:00Z",
        )
    except ValueError as exc:
        assert "inventory" in str(exc)
    else:
        raise AssertionError("explicit empty inventory must fail closed")


def test_runtime_manifest_script_can_run_directly_from_project_root() -> None:
    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "backend" / "scripts" / "build_luxian_0609_runtime_manifest.py"

    completed = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "LX0609" in completed.stdout
