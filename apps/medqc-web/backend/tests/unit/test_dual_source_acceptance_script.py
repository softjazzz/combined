"""客户机验收脚本复用正式写入器，预览无写入、Apply才刷新Bundle。"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


spec = importlib.util.spec_from_file_location("dual_acceptance_script", Path(__file__).parents[2] / "scripts/sync_dual_source_cases.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def setup_cli(tmp_path, monkeypatch):
    scope = tmp_path / "scope-private.json"
    case = {"sample": "C18", "institute_id": "H", "patient_id": "P", "visit_id": "V"}
    scope.write_text(json.dumps({"cases": [case], "source_institutes": {"clinical_data": "H", "homology": "UP", "local": "H"}}), encoding="utf-8")
    monkeypatch.setattr(cli, "configuration", lambda _: ("local", {"clinical_data": "c", "homology": "h"}, {"DB_SCHEMA_MODE": "split"}))
    report = {"data_committed": False, "inserts": 1, "updated_rows": 0, "filled_fields": 0,
              "pending_records": 0, "quarantined_rows": 0, "review_index_path": "review-private.json",
              "report_path": str(tmp_path / "report.json")}
    def execute(**kwargs):
        report["data_committed"] = kwargs["apply"]
        return {"report": report}
    execute_mock = Mock(side_effect=execute)
    monkeypatch.setattr(cli, "run_sync", execute_mock)
    child = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"event": "bundle_result", "ok": true}\n'))
    monkeypatch.setattr(cli.subprocess, "run", child)
    args = ["--backend", str(tmp_path), "--scope", str(scope), "--samples", "C18", "--tables", "bloodtrans_record,discharge_record",
            "--backup-dir", str(tmp_path / "backups"), "--output-dir", str(tmp_path / "reports")]
    return args, execute_mock, child, report


def test_preview_is_default_and_never_refreshes(setup_cli):
    args, execute, child, _ = setup_cli
    assert cli.main(args) == 0
    assert execute.call_args.kwargs["apply"] is False
    child.assert_not_called()


def test_apply_refreshes_only_after_commit(setup_cli):
    args, execute, child, report = setup_cli
    assert cli.main([*args, "--apply"]) == 0
    assert execute.call_args.kwargs["apply"] is True and report["bundle_verified"]
    assert child.call_args.kwargs["cwd"] == Path(args[1]).resolve()
    assert "refresh_all_bundle_variants_for_rows" not in " ".join(child.call_args.args[0])


def test_child_failure_reports_data_already_committed(setup_cli, capsys):
    args, _, child, report = setup_cli
    child.return_value = SimpleNamespace(returncode=1, stdout='{"event": "bundle_result", "ok": false}\n')
    assert cli.main([*args, "--apply"]) == 1
    assert report["data_committed"] is True and report["bundle_verified"] is False
    last = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert last["data_committed"] is True


def test_backup_or_writer_failure_never_calls_refresh(setup_cli):
    args, execute, child, _ = setup_cli
    execute.side_effect = cli.DualSourceWriteError("backup_failed")
    assert cli.main([*args, "--apply"]) == 1
    child.assert_not_called()


def test_more_than_three_cases_rejected_before_connections(setup_cli):
    args, execute, child, _ = setup_cli
    args[args.index("--samples") + 1] = "C01,C02,C03,C04"
    assert cli.main(args) == 1
    execute.assert_not_called()
    child.assert_not_called()


bundle_spec = importlib.util.spec_from_file_location("dual_bundle_child", Path(__file__).parents[2] / "scripts/verify_dual_source_bundles.py")
bundle_child = importlib.util.module_from_spec(bundle_spec)
bundle_spec.loader.exec_module(bundle_child)


def test_bundle_verification_requires_correct_table_identity_and_full_sections():
    documents = [{"source_table": "discharge_record", "document_id": "D", "content": "病程：甲乙\n出院医嘱：丙丁"}]
    bundle_child.check_document("discharge_record", "D", ["甲 乙", "丙丁"], documents)
    with pytest.raises(ValueError, match="bundle_document_missing"):
        bundle_child.check_document("bloodtrans_record", "D", ["甲乙"], documents)
    with pytest.raises(ValueError, match="bundle_content_incomplete"):
        bundle_child.check_document("discharge_record", "D", ["缺失段落"], documents)
    with pytest.raises(ValueError, match="bundle_document_missing"):
        bundle_child.check_document("discharge_record", "", ["甲乙"], documents)


def test_scene_bundle_inventory_uses_real_storage_column():
    assert bundle_child.inventory_expression({"structured_context"}) == "structured_context -> 'document_inventory'"
    assert bundle_child.inventory_expression({"source_documents", "structured_context"}) == "source_documents"
    with pytest.raises(ValueError, match="bundle_inventory_column_missing"):
        bundle_child.inventory_expression({"bundle_text"})


def test_confirmation_mode_never_refreshes_bundles():
    assembly = SimpleNamespace(refresh_all_bundle_variants_for_rows=Mock(side_effect=AssertionError("must stay read only")))
    assert bundle_child.refresh_if_requested(assembly, {"refresh": False}) == {}
    assembly.refresh_all_bundle_variants_for_rows.assert_not_called()


def test_legacy_empty_json_text_is_not_expected_body():
    assert bundle_child.source_sections({"record_content": "[]", "discharge_order": "真实医嘱"}) == ["真实医嘱"]


def test_missing_expected_source_document_cannot_vacuously_pass():
    required = [{"sample": "C18", "table": "bloodtrans_record", "document_id": "D"}]
    with pytest.raises(ValueError, match="expected_document_missing"):
        bundle_child.check_required_documents([], required)
    bundle_child.check_required_documents([{**required[0], "bundle_content_verified": True}], required)
