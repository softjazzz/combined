"""限定联验工具的合成边界：默认不导入应用，显式执行也不触及真实能力。"""
from contextlib import nullcontext
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


def trial_module():
    path = Path(__file__).resolve().parents[2] / "scripts/verify_primary_material_trial.py"
    spec = importlib.util.spec_from_file_location("primary_trial_test_only", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(module):
    return {"source_commit": module.SOURCE, "contract": "clinical-primary-four-v1",
            "metadata_revision": "clinical-primary-real-fields-v2", "document_types": list(module.KINDS),
            "approved_policy_file": "/protected/approved.json", "expected_source_binding": "synthetic",
            "cases": [{"alias": alias, "institute_id": "i", "patient_id": "p" + alias, "visit_id": "v",
                       "expected_policy_hash": "approved-hash", "expected_selection_id": "selection",
                       "expected_selected_counts": {kind: 5 if kind == "daily_course_record" else 1
                                                    for kind in module.KINDS}} for alias in ("P01", "P02")]}


def test_prepare_mode_does_not_import_application(monkeypatch, tmp_path, capsys):
    import builtins
    module = trial_module()
    path = tmp_path / "synthetic.json"
    value = plan(module)
    path.write_text(json.dumps(value), encoding="utf-8")
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name != "app" and not name.startswith("app."), "准备态不得加载业务配置或连接"
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(sys, "argv", ["trial", "--plan", str(path)])
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["database_connections"] == 0
    value["cases"][0]["expected_selected_counts"] = {}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="trial_expected_counts_required"):
        module.load_plan(path)
    with pytest.raises(ValueError, match="trial_execution_not_approved"):
        module.execute(plan(module), tmp_path / "forbidden")
    assert not (tmp_path / "forbidden").exists()


def test_execute_checks_more_than_three_rows_and_refuses_truncation(monkeypatch, tmp_path):
    module = trial_module()
    value = plan(module)
    value.update(authorization="APPROVED", approval_reference="synthetic-only")
    selection = {"policy_hash": "approved-hash", "selection_id": "selection", "items": []}
    rows = {kind: [{"version_id": kind + str(n)} for n in range(5 if kind == "daily_course_record" else 1)]
            for kind in module.KINDS}
    selection["items"] = [{"selected_version": row["version_id"]} for group in rows.values() for row in group]
    state = {"identity": ["synthetic"], "engine": object(), "connection": object()}
    persisted = []
    truncated = False

    def selected_rows(**kwargs):
        return rows[kwargs["table"]][:kwargs.get("limit", 3)]

    def persist(index, captured):
        assert "engine" not in captured and "connection" not in captured
        assert index.startswith("material-trial-") and captured["primary_material_manifest"] == selection
        persisted.append(deepcopy(captured))
        return {**captured, "fingerprint": "synthetic"}

    state["primary_material_manifest"] = selection
    modules = {name: ModuleType(name) for name in (
        "app", "app.database", "app.services", "app.services.luxian_0609", "app.services.bundles")}
    modules["app.database"].clinical_connection = SimpleNamespace(selected=lambda source: nullcontext())
    services = modules["app.services"]
    services.clinical_sources = SimpleNamespace(ordinary_snapshot=lambda: {"binding": "synthetic"})
    services.primary_material_readonly = SimpleNamespace(SOURCE_COMMIT=module.SOURCE, CONTRACT="clinical-primary-four-v1")
    services.primary_material_projection = SimpleNamespace(live_context=lambda identity: nullcontext(),
        manifest=lambda identity: selection, project_documents=lambda s: [], display_scope=lambda s: {})
    services.case_material_snapshot = SimpleNamespace(context=lambda: state, PROTOCOL="case-material-v1",
        persist=persist, activate=lambda saved: nullcontext())
    modules["app.services.luxian_0609"].source_evidence_reader = SimpleNamespace(
        read_luxian_0609_snapshot_source_rows=lambda **kw: SimpleNamespace(rows=rows[kw["source_key"]], truncated=truncated))
    modules["app.services.bundles"].assembly = SimpleNamespace(_select_records=selected_rows)
    for name, fake in modules.items():
        monkeypatch.setitem(sys.modules, name, fake)
    assert module.execute(value, tmp_path / "first")["case_count"] == 2
    assert len(persisted) == 2
    truncated = True
    with pytest.raises(ValueError, match="trial_input_truncated_stop"):
        module.execute(value, tmp_path / "second")
    assert len(persisted) == 2
