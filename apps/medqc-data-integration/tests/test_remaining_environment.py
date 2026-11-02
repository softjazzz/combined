"""集中42接口验收的四库、续跑、导出边界；只用 fake，不访问PG或Caché。"""

from __future__ import annotations

import importlib
import json
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind, IngestError

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
environment_tool = importlib.import_module("remaining_environment")
entry = importlib.import_module("run_remaining_acceptance")


def arguments(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    for name in ("source.json", "admin.pgpass", "runtime.pgpass", "cache-password"):
        (tmp_path / name).write_text("synthetic fixture only", encoding="utf-8")
    backend, pg_bin = tmp_path / "backend", tmp_path / "bin"
    (backend / "scripts").mkdir(parents=True)
    (backend / "scripts/bootstrap_cache_sync_database.py").write_text("# fake", encoding="utf-8")
    pg_bin.mkdir()
    for name in ("pg_dump.exe", "pg_restore.exe"):
        (pg_bin / name).write_bytes(b"not executable fixture")
    return SimpleNamespace(
        output=output,
        run_dir=output,
        suffix="20991101070001",
        port=62994,
        pg_major=18,
        synthetic=True,
        admin_user="postgres",
        admin_passfile=tmp_path / "admin.pgpass",
        runtime_passfile=tmp_path / "runtime.pgpass",
        source_config=tmp_path / "source.json",
        backend=backend,
        pg_bin=pg_bin,
        cohort_file=None,
        resume=False,
        statement_timeout_seconds=120,
    )


def fake_connection(settings, *, readonly=False, marker="medqc_remaining_synthetic"):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        settings.database,
        settings.user,
        settings.user,
        settings.port,
        180000,
        "on" if readonly else "off",
        marker,
    )
    return connection


def test_exact_four_database_scope_never_uses_historical_or_business_names(tmp_path):
    env = environment_tool.Environment(arguments(tmp_path))
    assert env.databases == {
        role: f"medqc_remaining_{role}_20991101070001" for role in environment_tool.ROLES
    }
    assert len(set(env.databases.values())) == 4
    assert not set(env.databases.values()) & {"medqc", "medqc_cache_poc", "medqc_bundle_acceptance"}
    for role, database in env.databases.items():
        assert env.settings(role).database == database
        assert env.settings(role).host == "127.0.0.1"
        assert env.settings(role).user == "medqc_sync"
        assert env.settings(role, admin=True).user == "postgres"
    for role in ("medqc", "old_ingest", "cdm_takeover", "../postgres", ""):
        with pytest.raises(IngestError):
            env.settings(role)


@pytest.mark.parametrize("suffix", ["20261101", "20991101070001;DROP", "../20991101070001"])
def test_invalid_suffix_stops_before_any_connection(tmp_path, suffix):
    args = arguments(tmp_path)
    args.suffix = suffix
    with pytest.raises(IngestError) as error:
        environment_tool.Environment(args)
    assert error.value.location == "remaining_suffix"


def test_environment_resume_rejects_changed_four_database_identity(tmp_path):
    args = arguments(tmp_path)
    path = args.output / "environment-progress.json"
    environment_tool.write_json(path, {"databases": {"ingest": "medqc"}, "stages": {}})
    with pytest.raises(IngestError) as error:
        environment_tool.Environment(args)
    assert error.value.location == "remaining_environment_identity"


def test_readonly_connection_identity_and_scope_are_enforced(tmp_path, monkeypatch):
    import psycopg2

    env = environment_tool.Environment(arguments(tmp_path))
    connection = fake_connection(env.settings("ingest"), readonly=True)
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(psycopg2, "connect", connect)
    assert env.connect("ingest", readonly=True) is connection
    kwargs = connect.call_args.kwargs
    assert kwargs["dbname"] == env.databases["ingest"]
    assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 62994
    assert kwargs["application_name"] == "medqc_remaining_acceptance"
    assert "default_transaction_read_only=on" in kwargs["options"]
    assert "password" not in kwargs
    with pytest.raises(IngestError):
        env.connect("postgres")
    assert connect.call_count == 1


@pytest.mark.parametrize(
    "index,value",
    [
        (0, "medqc"),
        (1, "postgres"),
        (2, "postgres"),
        (3, 5432),
        (4, 160000),
        (5, "off"),
        (6, "not_the_synthetic_cluster"),
    ],
)
def test_wrong_connection_identity_or_synthetic_marker_closes_connection(
    tmp_path, monkeypatch, index, value
):
    import psycopg2

    env = environment_tool.Environment(arguments(tmp_path))
    connection = fake_connection(env.settings("ingest"), readonly=True)
    cursor = connection.cursor.return_value.__enter__.return_value
    row = list(cursor.fetchone.return_value)
    row[index] = value
    cursor.fetchone.return_value = tuple(row)
    monkeypatch.setattr(psycopg2, "connect", MagicMock(return_value=connection))
    with pytest.raises(IngestError):
        env.connect("ingest", readonly=True)
    connection.close.assert_called_once()


def test_interrupted_prepare_requires_positive_reconciliation_without_repeating_write(tmp_path):
    args = arguments(tmp_path)
    env = environment_tool.Environment(args)
    action = MagicMock(side_effect=RuntimeError("synthetic interruption after unknown commit"))
    with pytest.raises(RuntimeError):
        env._stage("create_ingest", action)
    saved = json.loads(env.path.read_text(encoding="utf-8"))
    assert saved["stages"]["create_ingest"] == "running"
    resumed = environment_tool.Environment(args)
    with pytest.raises(IngestError) as error:
        resumed._stage("create_ingest", action, lambda: False)
    assert error.value.location == "remaining_environment_reconcile_required"
    resumed._stage("create_ingest", action, lambda: True)
    assert resumed.state["stages"]["create_ingest"] == "done"
    resumed._stage("create_ingest", action)
    action.assert_called_once()


@pytest.fixture()
def preflight_context(tmp_path, monkeypatch):
    import prepare_sync_control_acceptance

    import medqc_ingest.periop_live

    args = arguments(tmp_path)
    args.run_dir = tmp_path / "new-run"
    args.port, args.pg_major, args.synthetic = 5432, 16, False
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setattr(prepare_sync_control_acceptance, "check_acl", MagicMock())
    monkeypatch.setattr(prepare_sync_control_acceptance, "protect", MagicMock())
    monkeypatch.setattr(
        medqc_ingest.periop_live,
        "source_settings",
        lambda _path: SimpleNamespace(password_file=tmp_path / "cache-password"),
    )
    return args


def test_run_manifest_resume_retains_suffix_and_rejects_changed_references(preflight_context):
    args = preflight_context
    manifest = entry.preflight(args)
    assert not manifest["production_enabled"] and manifest["scope"] == "remaining25_periop17"
    args.resume = True
    assert entry.preflight(args) == manifest
    args.source_config.write_text("changed synthetic config", encoding="utf-8")
    with pytest.raises(IngestError) as error:
        entry.preflight(args)
    assert error.value.location == "remaining_resume_configuration_changed"


def test_existing_directory_without_manifest_is_never_adopted(preflight_context):
    args = preflight_context
    args.run_dir.mkdir()
    args.resume = True
    with pytest.raises(IngestError) as error:
        entry.preflight(args)
    assert error.value.location == "remaining_resume_required"


@pytest.mark.parametrize("credential", ["source_config", "admin_passfile", "runtime_passfile"])
@pytest.mark.parametrize("name", [".env", ".env.local", "cache.env"])
def test_dotenv_credential_files_are_rejected(preflight_context, credential, name):
    args = preflight_context
    path = args.run_dir.parent / name
    path.write_text("synthetic only", encoding="utf-8")
    setattr(args, credential, path)
    with pytest.raises(IngestError) as error:
        entry.preflight(args)
    assert error.value.location == "remaining_existing_credential_file"
    assert not args.run_dir.exists()


def test_nested_cache_password_dotenv_file_is_rejected(preflight_context, monkeypatch):
    import medqc_ingest.periop_live

    args = preflight_context
    secret = args.run_dir.parent / ".env.secret"
    secret.write_text("synthetic only", encoding="utf-8")
    monkeypatch.setattr(
        medqc_ingest.periop_live,
        "source_settings",
        lambda _path: SimpleNamespace(password_file=secret),
    )
    with pytest.raises(IngestError):
        entry.preflight(args)
    assert not args.run_dir.exists()


def backup_environment(tmp_path):
    args = arguments(tmp_path)
    for folder in ("reports", "backups", "private-logs"):
        (args.output / folder).mkdir()
    env = environment_tool.Environment(args)
    native_calls, restored = [], set()
    expected = {
        "tables": {"synthetic.table": {"rows": 2, "sha256": "a" * 64}},
        "sequences": {"synthetic.sequence": [3, True]},
    }
    env.fingerprint = lambda _role: expected
    env._empty = lambda role: role not in restored

    def native(tool, values):
        native_calls.append((tool, list(values)))
        if tool == "pg_dump":
            Path(values[values.index("-f") + 1]).write_bytes(b"synthetic dump")
        else:
            database = values[values.index("-d") + 1]
            restored.add(next(role for role, name in env.databases.items() if name == database))

    env._native = native
    return env, native_calls, restored, expected


def test_backup_restore_uses_only_four_new_databases_and_atomic_dump_files(tmp_path):
    env, calls, _, expected = backup_environment(tmp_path)
    report = env.backup_restore()
    assert report["restore_fingerprint_equal"]
    assert set(report["databases"]) == {"ingest", "cdm"}
    assert all(row["fingerprint"] == expected for row in report["databases"].values())
    assert [tool for tool, _ in calls] == ["pg_dump", "pg_restore", "pg_dump", "pg_restore"]
    for tool, values in calls:
        if tool == "pg_dump":
            assert values[-1] in env.databases.values()
            assert values[values.index("-f") + 1].endswith(".pending")
        else:
            assert "--single-transaction" in values and "--exit-on-error" in values
            assert values[values.index("-d") + 1] in {
                env.databases["restore_ingest"],
                env.databases["restore_cdm"],
            }
    previous = list(calls)
    assert env.backup_restore() == report
    assert calls == previous


def test_interrupted_restore_reconciles_fingerprint_without_repeating_committed_restore(tmp_path):
    env, calls, restored, _ = backup_environment(tmp_path)
    native = env._native
    crashed = False

    def interrupt(tool, values):
        nonlocal crashed
        native(tool, values)
        if tool == "pg_restore" and not crashed:
            crashed = True
            raise RuntimeError("synthetic after commit unknown result")

    env._native = interrupt
    with pytest.raises(RuntimeError):
        env.backup_restore()
    assert restored == {"restore_ingest"}
    assert not (env.args.output / "reports/backup-restore.json").exists()
    env.backup_restore()
    assert sum(tool == "pg_dump" for tool, _ in calls) == 2
    assert sum(tool == "pg_restore" for tool, _ in calls) == 2


def test_restore_mismatch_never_writes_success_report(tmp_path):
    env, _, _, expected = backup_environment(tmp_path)
    env.fingerprint = lambda role: expected if role in {"ingest", "cdm"} else {"corrupt": True}
    with pytest.raises(IngestError) as error:
        env.backup_restore()
    assert error.value.location == "remaining_restore_fingerprint_mismatch"
    assert not (env.args.output / "reports/backup-restore.json").exists()


def mutable_backup_environment(tmp_path):
    """四个固定fake库各持有自己的指纹，模拟源库更新及恢复库被外部修改。"""
    env, calls, restored, expected = backup_environment(tmp_path)
    fingerprints = {
        role: deepcopy(expected) for role in ("ingest", "cdm", "restore_ingest", "restore_cdm")
    }
    env.fingerprint = lambda role: deepcopy(fingerprints[role])
    native = env._native

    def native_with_restore(tool, values):
        native(tool, values)
        if tool == "pg_restore":
            database = values[values.index("-d") + 1]
            role = next(role for role, name in env.databases.items() if name == database)
            fingerprints[role] = deepcopy(fingerprints[role.removeprefix("restore_")])

    env._native = native_with_restore
    return env, calls, restored, fingerprints


def test_changed_sources_create_new_fingerprinted_dumps_and_clean_only_our_restore_databases(
    tmp_path,
):
    env, calls, _, fingerprints = mutable_backup_environment(tmp_path)
    original = env.backup_restore()
    revision = env.backup_revision()
    old_dumps = set((env.args.output / "backups").glob("*.dump"))
    calls.clear()
    for role in ("ingest", "cdm"):
        fingerprints[role]["tables"]["synthetic.table"] = {"rows": 3, "sha256": "b" * 64}
    assert env.backup_revision() != revision
    refreshed = env.backup_restore()
    assert refreshed != original and refreshed["restore_fingerprint_equal"]
    all_dumps = set((env.args.output / "backups").glob("*.dump"))
    assert len(old_dumps) == 2 and len(all_dumps) == 4 and old_dumps < all_dumps
    assert [tool for tool, _ in calls] == ["pg_dump", "pg_restore", "pg_dump", "pg_restore"]
    for tool, values in calls:
        if tool == "pg_restore":
            assert {"--clean", "--if-exists", "--single-transaction", "--exit-on-error"} <= set(
                values
            )
            assert values[values.index("-d") + 1] in {
                env.databases["restore_ingest"],
                env.databases["restore_cdm"],
            }
    for role in ("ingest", "cdm"):
        assert fingerprints["restore_" + role] == fingerprints[role]
        assert refreshed["databases"][role]["fingerprint"] == fingerprints[role]


def test_changed_source_refuses_clean_when_restore_is_not_our_previous_backup(tmp_path):
    env, calls, _, fingerprints = mutable_backup_environment(tmp_path)
    env.backup_restore()
    report_path = env.args.output / "reports/backup-restore.json"
    previous_report = report_path.read_bytes()
    calls.clear()
    fingerprints["ingest"]["tables"]["synthetic.table"]["sha256"] = "b" * 64
    fingerprints["restore_ingest"] = {"externally_modified": True}
    with pytest.raises(IngestError) as error:
        env.backup_restore()
    assert error.value.location == "remaining_restore_not_our_prior_backup"
    assert not any(tool == "pg_restore" for tool, _ in calls)
    assert fingerprints["restore_ingest"] == {"externally_modified": True}
    assert report_path.read_bytes() == previous_report


def test_unchanged_source_rechecks_restore_instead_of_reusing_stale_pass(tmp_path):
    env, calls, _, fingerprints = mutable_backup_environment(tmp_path)
    env.backup_restore()
    report_path = env.args.output / "reports/backup-restore.json"
    previous_report = report_path.read_bytes()
    revision = env.backup_revision()
    calls.clear()
    fingerprints["restore_ingest"] = {"externally_modified": True}
    assert env.backup_revision() == revision  # 源未变不能替代恢复库的重新核对。
    with pytest.raises(IngestError) as error:
        env.backup_restore()
    assert error.value.location == "remaining_restore_not_our_prior_backup"
    assert not calls  # 不重新dump，也绝不能对未知恢复库自动clean。
    assert report_path.read_bytes() == previous_report


def test_native_failure_keeps_private_error_out_of_public_exception(tmp_path, monkeypatch):
    env, _, _, _ = backup_environment(tmp_path)
    monkeypatch.setattr(
        environment_tool.subprocess,
        "run",
        MagicMock(return_value=SimpleNamespace(returncode=1, stderr=b"fictional-private-payload")),
    )
    # fixture文件存在，但subprocess被fake替换，不可能启动任何真实工具。
    with pytest.raises(IngestError) as error:
        environment_tool.Environment._native(env, "pg_dump", [env.databases["ingest"]])
    assert "fictional-private" not in str(error.value)
    assert (env.args.output / "private-logs/pg_dump.stderr").read_bytes() == (
        b"fictional-private-payload"
    )


def test_export_excludes_run_manifest_credentials_backups_and_private_logs(tmp_path):
    args = arguments(tmp_path)
    for folder in ("reports", "backups", "private-logs", "secrets"):
        (args.output / folder).mkdir()
    environment_tool.write_json(args.output / "reports/coverage-55.json", {"interfaces": []})
    for name in (
        "run-manifest.json",
        "runtime.json",
        "backups/clinical.dump",
        "private-logs/error.json",
        "secrets/password.json",
    ):
        path = args.output / name
        path.write_text('"fictional-private-marker"', encoding="utf-8")
    output = entry.package_reports(args)
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert names == {"coverage-55.json", "manifest.json", "CHECKSUMS.txt"}
        assert all(b"fictional-private-marker" not in archive.read(name) for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert not manifest["production_enabled"] and not manifest["contains_phi"]


def test_export_never_sweeps_unapproved_json_into_non_phi_package(tmp_path):
    args = arguments(tmp_path)
    (args.output / "reports").mkdir()
    (args.output / "reports/unreviewed-payload.json").write_text(
        '{"payload":"fictional-private-marker"}', encoding="utf-8"
    )
    try:
        output = entry.package_reports(args)
    except IngestError:
        return  # 拒绝非白名单文件也符合安全出口。
    with zipfile.ZipFile(output) as archive:
        assert "unreviewed-payload.json" not in archive.namelist()


@pytest.mark.parametrize(
    "forbidden",
    ["payload", "source_key", "raw_values", "password", "token", "dsn", "connection_string"],
)
def test_export_rejects_sensitive_keys_nested_in_an_approved_report(tmp_path, forbidden):
    args = arguments(tmp_path)
    (args.output / "reports").mkdir()
    environment_tool.write_json(
        args.output / "reports/remaining-acceptance.json",
        {"interface": [{"nested": {forbidden: "fictional-private-marker"}}]},
    )
    with pytest.raises(IngestError):
        entry.package_reports(args)
    assert not (args.output / "cache-remaining-consolidated-result.zip").exists()


def test_export_accepts_false_privacy_labels_and_only_the_reviewed_report_files(tmp_path):
    args = arguments(tmp_path)
    (args.output / "reports").mkdir()
    expected = {
        "remaining-acceptance.json",
        "remaining-progress.json",
        "backup-restore.json",
        "coverage-55.json",
        "inpatient-availability.json",
        "critical-field-audit.json",
        "field-contract-gaps.json",
        "fatal-error.json",
    }
    for name in expected:
        environment_tool.write_json(
            args.output / "reports" / name,
            {"contains_phi": False, "contains_raw_values": False, "contains_keys": False},
        )
    (args.output / "reports/journal.jsonl").write_text("fictional-private", encoding="utf-8")
    output = entry.package_reports(args)
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == expected | {"manifest.json", "CHECKSUMS.txt"}


def test_partial_source_is_not_reported_as_complete_acceptance():
    contract = {"interfaces": [{"interface": f"web.synthetic_{i}"} for i in range(42)]}
    report = {
        "interfaces": [
            {
                "interface": item["interface"],
                "status": "accepted",
                "snapshot_rows": 1,
                "source_complete": i != 0,
            }
            for i, item in enumerate(contract["interfaces"])
        ]
    }
    rows = {row["interface"]: row for row in entry.coverage(report, contract)}
    assert (
        rows["web.synthetic_0"]["status"] == "accepted_successful_windows_with_source_limitations"
    )
    assert rows["web.synthetic_1"]["status"] == "accepted"


def test_missing_and_zero_sample_statuses_are_not_promoted_to_acceptance():
    contract = {"interfaces": [{"interface": f"web.synthetic_{i}"} for i in range(42)]}
    statuses = ["source_blocked", "schema_verified_no_sample", "snapshot_only_no_publish_contract"]
    report = {
        "interfaces": [
            {
                "interface": item["interface"],
                "status": statuses[i % 3],
                "snapshot_rows": 0,
                "source_complete": False,
            }
            for i, item in enumerate(contract["interfaces"])
        ]
    }
    rows = entry.coverage(report, contract)
    assert len(rows) == 55
    for row in rows:
        if row["interface"] in INTERFACE_REGISTRY:
            assert row["status"] == "prior_acceptance_reused_not_retested"
            assert not row["new_source_called"]
        else:
            assert row["status"] in statuses
        assert not row["production_changed"]


@pytest.mark.parametrize(
    "content,code",
    [
        ("unexpected,header\nfictional,value\n", "cohort_header"),
        ("", "cohort_header"),
    ],
)
def test_invalid_cohort_is_controlled_and_does_not_touch_source(
    tmp_path, monkeypatch, content, code
):
    import prepare_sync_control_acceptance

    args = arguments(tmp_path)
    args.cohort_file = tmp_path / "cohort.csv"
    args.cohort_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(prepare_sync_control_acceptance, "check_acl", lambda _path: None)
    fake = MagicMock()
    result = entry.cohort_review(args, fake)
    assert result["status"] == "invalid_local_cohort" and result["error_code"] == code
    assert not result["source_called"]
    fake.connect.assert_not_called()


def test_invalid_cohort_encoding_is_reported_without_blocking_other_interfaces(
    tmp_path, monkeypatch
):
    import prepare_sync_control_acceptance

    args = arguments(tmp_path)
    args.cohort_file = tmp_path / "cohort.csv"
    args.cohort_file.write_bytes(b"\xff\xff\xfe")
    monkeypatch.setattr(prepare_sync_control_acceptance, "check_acl", lambda _path: None)
    fake = MagicMock()
    result = entry.cohort_review(args, fake)
    assert result["status"] == "invalid_local_cohort" and not result["source_called"]
    fake.connect.assert_not_called()


def test_missing_cohort_is_explicit_blocked_instead_of_false_success(tmp_path):
    args = arguments(tmp_path)
    args.cohort_file = tmp_path / "missing-cohort.csv"
    fake = MagicMock()
    result = entry.cohort_review(args, fake)
    assert result["status"] == "blocked_missing_confirmed_inpatient_cohort"
    assert not result["source_called"]
    fake.connect.assert_not_called()


def test_cohort_acl_failure_remains_fatal_safety_boundary(tmp_path, monkeypatch):
    import prepare_sync_control_acceptance

    args = arguments(tmp_path)
    args.cohort_file = tmp_path / "cohort.csv"
    args.cohort_file.write_text("synthetic", encoding="utf-8")
    monkeypatch.setattr(
        prepare_sync_control_acceptance,
        "check_acl",
        MagicMock(side_effect=IngestError(ErrorKind.CONFIGURATION, "synthetic_acl_refused")),
    )
    with pytest.raises(IngestError) as error:
        entry.cohort_review(args, MagicMock())
    assert error.value.location == "synthetic_acl_refused"


def test_main_finishes_other_interfaces_and_exports_after_invalid_cohort_encoding(
    tmp_path, monkeypatch, capsys
):
    import prepare_sync_control_acceptance
    import validate_remaining_interfaces

    args = arguments(tmp_path)
    (args.output / "reports").mkdir()
    args.cohort_file = tmp_path / "bad-cohort.csv"
    args.cohort_file.write_bytes(b"\xff\xff\xfe")
    contract = {"interfaces": [{"interface": f"web.synthetic_{i}"} for i in range(42)]}
    report = {
        "interfaces": [
            {
                "interface": item["interface"],
                "status": "schema_verified_no_sample",
                "snapshot_rows": 0,
                "source_complete": True,
            }
            for item in contract["interfaces"]
        ]
    }
    monkeypatch.setattr(prepare_sync_control_acceptance, "check_acl", lambda _path: None)
    monkeypatch.setattr(entry, "load_combined_profile", lambda _path: (contract, {}))
    monkeypatch.setattr(entry, "Environment", MagicMock())
    monkeypatch.setattr(entry, "critical_field_audit", lambda *_args: {"fields": []})
    run = MagicMock(return_value=report)
    monkeypatch.setattr(validate_remaining_interfaces, "run", run)

    # main 的preflight被fake替换，只提供读取合同所需的引用；不读取任何凭据。
    def fake_preflight(parsed):
        parsed.output, parsed.contract = args.output, tmp_path / "not-read-contract.json"

    monkeypatch.setattr(entry, "preflight", fake_preflight)
    result = entry.main(
        [
            "--run-dir",
            str(args.output),
            "--source-config",
            str(args.source_config),
            "--admin-passfile",
            str(args.admin_passfile),
            "--runtime-passfile",
            str(args.runtime_passfile),
            "--pg-bin",
            str(args.pg_bin),
            "--cohort-file",
            str(args.cohort_file),
        ]
    )
    assert result == 0
    run.assert_called_once()
    exported = json.loads((args.output / "reports/inpatient-availability.json").read_text())
    assert exported["status"] == "invalid_local_cohort"
    assert (args.output / "cache-remaining-consolidated-result.zip").is_file()
    assert "CONSOLIDATED_ACCEPTANCE_COMPLETE_WITH_COVERAGE" in capsys.readouterr().out


def test_critical_field_audit_accepts_unknown_source_schema_without_inventing_fields():
    from unittest.mock import MagicMock

    env = MagicMock()
    result = entry.critical_field_audit(
        env,
        {
            "interfaces": [
                {
                    "interface": "web.surgery_record",
                    "source_columns": None,
                    "mappings": [],
                    "publish_target": "cdm.surgery_record",
                }
            ]
        },
        [],
    )
    assert result["fields"] == [] and result["values_exported"] is False
