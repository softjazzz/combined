from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids

import importlib.util
import json
from pathlib import Path

import pytest

from scripts.build_luxian_0609_runtime_manifest import (
    atomic_write_json,
    build_artifact_metadata,
    runtime_manifest_hash,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, relative_path: str):
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_gate = _load_script(
    "run_luxian_0609_release_gate_contract_test",
    "scripts/qc/run_luxian_0609_release_gate.py",
)
evaluate_rules = _load_script(
    "evaluate_luxian_0609_rules_contract_test",
    "scripts/qc/evaluate_luxian_0609_rules.py",
)
page_evidence = _load_script(
    "build_luxian_0609_page_closure_evidence_contract_test",
    "scripts/qc/build_luxian_0609_page_closure_evidence.py",
)


def _runtime_manifest() -> dict:
    return {
        "schema_version": "lx0609-runtime-manifest-v1",
        "generated_at": "2026-07-23T18:00:00Z",
        "git_head": "a" * 40,
        "customer_rule_count": 49,
        "flags": {},
        "rule_set": {
            "key": "luxian_0609_qc_v1",
            "version": "2026-06-09",
            "rule_count": 49,
            "rule_ids": list(published_rule_ids(1, 49)),
        },
        "runtime": {
            "models": {"primary": "safe-model", "adjudicator": "safe-adjudicator"},
        },
        "rules": [],
    }


def _artifact(
    manifest: dict,
    *,
    schema_version: str,
    evidence_scope: str = "mixed",
) -> dict:
    return {
        **build_artifact_metadata(
            runtime_manifest=manifest,
            schema_version=schema_version,
            evidence_scope=evidence_scope,
            generated_at="2026-07-23T18:05:00Z",
        ),
        "summary": {},
    }


def test_release_artifact_contract_accepts_only_same_runtime_without_pending() -> None:
    manifest = _runtime_manifest()
    artifacts = {
        "evaluation": _artifact(manifest, schema_version="lx0609-qc-eval-v2"),
        "page_evidence": _artifact(
            manifest,
            schema_version="lx0609-page-evidence-v2",
        ),
    }

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts=artifacts,
        current_git_head=manifest["git_head"],
    )

    assert result["status"] == "pass"
    assert result["runtime_manifest_hash"] == runtime_manifest_hash(manifest)
    assert result["invalid_artifacts"] == []


def test_release_artifact_contract_fails_on_missing_fields_or_stale_head() -> None:
    manifest = _runtime_manifest()
    missing = {"summary": {}}
    stale = _artifact(manifest, schema_version="lx0609-page-evidence-v2")
    stale["git_head"] = "b" * 40

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts={"evaluation": missing, "page_evidence": stale},
        current_git_head=manifest["git_head"],
    )

    assert result["status"] == "fail"
    assert {item["artifact"] for item in result["invalid_artifacts"]} == {
        "evaluation",
        "page_evidence",
    }
    assert "missing_version_fields" in result["reason_codes"]
    assert "git_head_mismatch" in result["reason_codes"]


def test_release_artifact_contract_fails_when_any_input_contains_pending() -> None:
    manifest = _runtime_manifest()
    evaluation = _artifact(manifest, schema_version="lx0609-qc-eval-v2")
    evaluation["summary"]["launch_status"] = {"formal_candidate": 48, "pending": 1}

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts={"evaluation": evaluation},
        current_git_head=manifest["git_head"],
    )

    assert result["status"] == "fail"
    assert "pending_evidence" in result["reason_codes"]


def test_release_artifact_contract_rejects_wrong_schema_and_dirty_source() -> None:
    manifest = _runtime_manifest()
    page = _artifact(manifest, schema_version="wrong-page-schema")
    page["source_state"] = "dirty"

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts={"page_evidence": page},
        current_git_head=manifest["git_head"],
    )

    assert result["status"] == "fail"
    assert "artifact_schema_mismatch" in result["reason_codes"]
    assert "dirty_source" in result["reason_codes"]


def test_eval_and_page_artifacts_inherit_the_same_runtime_binding() -> None:
    manifest = _runtime_manifest()

    evaluation = evaluate_rules.build_eval(
        runtime_manifest=manifest,
        current_git_head=manifest["git_head"],
    )
    evidence = page_evidence.build_evidence(
        runtime_manifest=manifest,
        current_git_head=manifest["git_head"],
    )

    for artifact in (evaluation, evidence):
        assert artifact["git_head"] == manifest["git_head"]
        assert artifact["runtime_manifest_hash"] == runtime_manifest_hash(manifest)
        assert artifact["evidence_scope"] in {"synthetic", "real", "mixed"}
        assert artifact["generated_at"].endswith("Z")


def test_eval_rejects_unbound_legacy_prediction_instead_of_restamping_it(
    tmp_path: Path,
) -> None:
    manifest = _runtime_manifest()
    prediction_path = tmp_path / "legacy-predictions.json"
    prediction_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "qc_point_id": "LX0609-01-01-01",
                        "case_id": "legacy-case",
                        "status": "non_compliant",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_rules.build_eval(
        runtime_manifest=manifest,
        prediction_path=prediction_path,
        current_git_head=manifest["git_head"],
    )

    assert evaluation["prediction_binding"]["status"] == "invalid"
    assert "prediction_schema_invalid" in evaluation["prediction_binding"]["reason_codes"]
    assert evaluation["summary"]["launch_status"].get("formal_candidate", 0) == 0


def test_stale_runtime_manifest_cannot_self_attest_artifacts() -> None:
    manifest = _runtime_manifest()
    evaluation = _artifact(manifest, schema_version="lx0609-qc-eval-v2")

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts={"evaluation": evaluation},
        current_git_head="b" * 40,
    )

    assert result["status"] == "fail"
    assert "runtime_manifest_head_mismatch" in result["reason_codes"]


def test_bound_prediction_scope_is_inherited_and_cannot_be_overridden(
    tmp_path: Path,
) -> None:
    manifest = _runtime_manifest()
    prediction_path = tmp_path / "bound-predictions.json"
    prediction_path.write_text(
        json.dumps(
            {
                **build_artifact_metadata(
                    runtime_manifest=manifest,
                    schema_version="lx0609-predictions-v1",
                    evidence_scope="real",
                    generated_at="2026-07-23T18:10:00Z",
                ),
                "results": [],
            }
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_rules.build_eval(
        runtime_manifest=manifest,
        prediction_path=prediction_path,
        current_git_head=manifest["git_head"],
    )
    assert evaluation["evidence_scope"] == "real"

    with pytest.raises(ValueError, match="cannot override"):
        evaluate_rules.build_eval(
            runtime_manifest=manifest,
            prediction_path=prediction_path,
            evidence_scope="synthetic",
            current_git_head=manifest["git_head"],
        )


def test_release_artifact_contract_recomputes_input_hashes() -> None:
    manifest = _runtime_manifest()
    evaluation = _artifact(manifest, schema_version="lx0609-qc-eval-v2")
    evaluation["input_hashes"] = {"catalog": "old"}

    result = release_gate.build_artifact_contract_check(
        runtime_manifest=manifest,
        artifacts={"evaluation": evaluation},
        current_git_head=manifest["git_head"],
        expected_input_hashes={"evaluation": {"catalog": "current"}},
    )

    assert result["status"] == "fail"
    assert "input_hash_mismatch" in result["reason_codes"]


def test_atomic_json_write_never_leaves_partial_temp_file(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    atomic_write_json(output, {"value": 1})
    atomic_write_json(output, {"value": 2})

    assert json.loads(output.read_text(encoding="utf-8")) == {"value": 2}
    assert list(tmp_path.glob("*.tmp")) == []
