"""集中验收的隔离、断点与失败边界；全部使用虚构元数据和 fake 端口。"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from medqc_ingest.domain import ErrorKind, IngestError, normalize, resolve_interface

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
module_spec = importlib.util.spec_from_file_location(
    "remaining_validation_test_tool", TOOLS / "validate_remaining_interfaces.py"
)
validation = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(validation)


def profile(count=25):
    original = resolve_interface("web.mr")
    specs = {
        f"web.synthetic_{number}": replace(
            original, name=f"web.synthetic_{number}", procedure=f"web.synthetic_{number}"
        )
        for number in range(count)
    }
    document = {"interfaces": [{"interface": name, "argument_count": 1} for name in specs]}
    if count == 42:
        document["scope"] = "remaining25_periop17"
    return document, specs


class Environment:
    databases = {
        role: "synthetic_" + role for role in ("ingest", "cdm", "restore_ingest", "restore_cdm")
    }

    def __init__(self, root):
        self.root, self.prepares, self.backups = root, 0, 0

    def prepare(self):
        self.prepares += 1
        (self.root / "reports").mkdir(parents=True, exist_ok=True)

    def backup_restore(self):
        self.backups += 1
        return {"fingerprint_equal": True}


class Operations:
    def __init__(self):
        self.calls = []
        self.faults = {}
        self.zero = set()
        self.fallback = set()
        self.changed_schema = set()

    def call(self, phase, name, detail=None):
        self.calls.append((phase, name, detail))
        if (phase, name, detail) in self.faults:
            raise self.faults[(phase, name, detail)]

    def capture(self, spec, day):
        self.call("capture", spec.name, day)
        rows = 0 if spec.name in self.zero else 1
        if spec.name in self.fallback and day == "2026-10-20":
            rows = 1
        columns = list(spec.source_columns)
        if spec.name in self.changed_schema:
            columns.append("synthetic_new_column")
        return {
            "status": "captured",
            "interface": spec.name,
            "date": day,
            "rows": rows,
            "columns": columns,
            "source_types": ["str"] * len(columns),
            "schema_hash": "a" * 64,
            "inspection_batch_id": 1,
            "complete": True,
        }

    def preflight(self, spec):
        self.call("catalog", spec.name)
        return {"status": "verified", "target_catalog_verified": True, "maximum_lengths": {}}

    def validate_keys(self, spec, snapshots, metadata=None):
        self.call("keys", spec.name)
        if any(tuple(s["columns"]) != spec.source_columns for s in snapshots):
            raise IngestError(ErrorKind.SCHEMA, "synthetic_schema_changed")
        return {"status": "verified", "target_unique_keys": len(snapshots)}

    def promote(self, spec, snapshot):
        self.call("raw", spec.name, snapshot["date"])
        return {"status": "promoted", "counts": {"inserted": snapshot["rows"]}}

    def publish(self, spec, number):
        self.call("publish", spec.name, number)
        return {"status": "published", "written": 1 if number == 1 else 0}

    def verify(self, spec):
        self.call("verify", spec.name)
        return {"status": "verified", "all_fields_equal": True}


@pytest.fixture()
def context(tmp_path, monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setattr(validation.os, "fsync", lambda _descriptor: None)
    args = SimpleNamespace(
        output=tmp_path / "run", contract=tmp_path / "contract.json", synthetic=True, pg_major=18
    )
    environment, operations = Environment(args.output), Operations()
    return args, environment, operations


def execute(context, document=None):
    args, environment, operations = context
    return validation.run(
        args, environment=environment, operations=operations, profile=document or profile()
    )


def source_query_error():
    try:
        raise RuntimeError("HY000", "synthetic-private-body [Native Code 400]")
    except RuntimeError:
        try:
            raise IngestError(ErrorKind.SOURCE_QUERY, "odbc_call") from None
        except IngestError as error:
            return error


def test_single_run_and_resume_skip_all_completed_source_raw_publish_and_backup(context):
    _, environment, operations = context
    report = execute(context)
    assert len(report["interfaces"]) == 25
    assert sum(call[0] == "capture" for call in operations.calls) == 75
    assert sum(call[0] == "publish" for call in operations.calls) == 50
    assert all(item["status"] == "accepted" for item in report["interfaces"])
    calls = list(operations.calls)
    assert execute(context) == report
    assert operations.calls == calls and environment.backups == 1
    assert not report["automatic_incremental"] and not report["scheduled_task_created"]


def test_hy000_failure_is_local_and_other_interfaces_and_successful_windows_continue(context):
    _, _, operations = context
    operations.faults[("capture", "web.synthetic_0", "2026-10-27")] = source_query_error()
    report = execute(context)
    first = report["interfaces"][0]
    assert first["status"] == "accepted" and not first["source_complete"]
    assert first["snapshot_rows"] == 2 and len(first["failed_windows"]) == 1
    assert report["interfaces"][-1]["status"] == "accepted"
    assert "synthetic-private-body" not in json.dumps(report)
    assert (
        "synthetic-private-body"
        not in (context[0].output / "reports/remaining-progress.json").read_text()
    )


def test_connection_failure_stops_globally_and_uncertain_resume_does_not_repeat_read(context):
    _, environment, operations = context
    operations.faults[("capture", "web.synthetic_0", "2026-10-26")] = IngestError(
        ErrorKind.SOURCE_CONNECT, "odbc_connect"
    )
    with pytest.raises(IngestError):
        execute(context)
    assert len(operations.calls) == 1 and environment.backups == 0
    operations.faults.clear()
    with pytest.raises(IngestError) as error:
        execute(context)
    assert error.value.location == "remaining_resume_reconciliation_required"
    assert len(operations.calls) == 1


def test_schema_drift_preserves_complete_snapshots_without_guessing_mapping(context):
    _, _, operations = context
    operations.changed_schema.add("web.synthetic_0")
    report = execute(context)
    assert report["interfaces"][0]["snapshot_rows"] == 3
    assert report["interfaces"][0]["status"] == "snapshot_only_contract_blocked"
    assert not any(
        call[0] in {"raw", "publish"} and call[1] == "web.synthetic_0" for call in operations.calls
    )
    assert report["interfaces"][1]["status"] == "accepted"


def test_missing_key_contract_stays_snapshot_only(context):
    document, specs = profile()
    del specs["web.synthetic_0"]
    report = execute(context, (document, specs))
    assert report["interfaces"][0]["status"] == "snapshot_only_no_publish_contract"
    assert not any(call[0] == "keys" and call[1] == "web.synthetic_0" for call in context[2].calls)


def test_bounded_zero_sample_fallback_stops_at_first_nonempty_day(context):
    operations = context[2]
    operations.zero.update({"web.synthetic_0", "web.synthetic_1"})
    operations.fallback.add("web.synthetic_0")
    report = execute(context)
    assert report["interfaces"][0]["status"] == "accepted"
    assert report["interfaces"][1]["status"] == "schema_verified_no_sample"
    first = [call[2] for call in operations.calls if call[:2] == ("capture", "web.synthetic_0")]
    assert first == [*validation.DATES, "2026-10-19", "2026-10-20"]
    second = [call[2] for call in operations.calls if call[:2] == ("capture", "web.synthetic_1")]
    assert len(second) == 10 and second[-1] == "2026-10-25"
    assert not any(
        call[0] == "publish" and call[1] == "web.synthetic_1" for call in operations.calls
    )


def test_key_collision_blocks_only_affected_interface_before_raw_write(context):
    context[2].faults[("keys", "web.synthetic_0", None)] = IngestError(
        ErrorKind.KEY, "remaining_target_key_collision"
    )
    report = execute(context)
    assert report["interfaces"][0]["status"] == "snapshot_only_contract_blocked"
    assert not any(call[0] == "raw" and call[1] == "web.synthetic_0" for call in context[2].calls)
    assert report["interfaces"][-1]["status"] == "accepted"


def test_projection_contract_failure_isolated_without_claiming_success(context):
    context[2].faults[("publish", "web.synthetic_0", 1)] = IngestError(
        ErrorKind.PUBLISH_CONTRACT, "synthetic_target_mismatch"
    )
    report = execute(context)
    assert report["interfaces"][0]["status"] == "projection_blocked"
    assert ("publish", "web.synthetic_0", 2) not in context[2].calls
    assert report["interfaces"][-1]["status"] == "accepted"


def test_permissions_and_disk_errors_never_isolated():
    for state in ("42501", "53100", "08006", "28P01", "58030"):
        try:
            original = RuntimeError("private-text")
            original.pgcode = state
            raise original
        except RuntimeError:
            try:
                raise IngestError(ErrorKind.CDM_WRITE, "synthetic_write") from None
            except IngestError as error:
                assert not validation.isolatable(error)


def test_resume_identity_checked_before_any_environment_changes(context):
    execute(context)
    before = context[1].prepares
    changed = profile()
    changed[0]["version"] = "changed-contract"
    with pytest.raises(IngestError) as error:
        execute(context, changed)
    assert error.value.location == "remaining_resume_identity"
    assert context[1].prepares == before


def test_combined_scope_accepts_42_without_calling_old13(context):
    report = execute(context, profile(42))
    assert len(report["interfaces"]) == 42
    assert all("synthetic_" in call[1] for call in context[2].calls)


@pytest.mark.parametrize(
    "value",
    [
        b"synthetic",
        Decimal("1.200"),
        datetime(2026, 10, 28, 8),
        date(2026, 10, 28),
        None,
        "synthetic-text",
    ],
)
def test_snapshot_values_roundtrip_before_formal_engine_replay(value):
    assert validation.restore_value(normalize(value)) == value


def test_unrecognized_snapshot_type_never_silently_becomes_text():
    with pytest.raises(IngestError):
        validation.restore_value({"$type": "unknown", "text": "synthetic"})


def test_native_417_cannot_be_downgraded_to_per_interface_source_failure():
    try:
        raise RuntimeError("HY000", "synthetic-private-body [Native Code 417]")
    except RuntimeError:
        try:
            raise IngestError(ErrorKind.SOURCE_QUERY, "odbc_call") from None
        except IngestError as error:
            assert not validation.isolatable(error)


def test_journal_reconciles_only_proven_terminal_stage_without_reexecuting(tmp_path):
    path = tmp_path / "progress.json"
    journal = validation.Journal(path, {"synthetic": True})
    journal.record("synthetic-stage", {"status": "running", "metadata": {"batch_id": 17}})
    recovered = validation.Journal(path, {"synthetic": True})
    calls = []
    outcome = recovered.stage(
        "synthetic-stage",
        lambda: calls.append("unsafe-reexecution"),
        lambda metadata: {"status": "verified", **metadata},
    )
    assert not calls and outcome == {"status": "verified", "batch_id": 17}
    assert recovered.document["stages"]["synthetic-stage"]["status"] == "done"


def test_journal_refuses_unknown_commit_and_can_repeat_only_readonly_phase(tmp_path):
    journal = validation.Journal(tmp_path / "progress.json", {"synthetic": True})
    journal.record("write", {"status": "running"})
    calls = []
    with pytest.raises(IngestError):
        journal.stage("write", lambda: calls.append("write"), lambda _: None)
    assert not calls
    journal.record("read", {"status": "running"})
    assert journal.stage("read", lambda: {"status": "verified"}, readonly=True) == {
        "status": "verified"
    }


def test_actual_snapshot_capture_preserves_multiple_results_without_fake_business_keys(monkeypatch):
    calls, progress = [], []

    class Repository:
        def __init__(self, _settings):
            pass

        def __getattr__(self, name):
            def operation(*args):
                calls.append((name, args))
                if name == "acquire_lock":
                    return True
                if name == "start_inspection":
                    return 17

            return operation

    class Source:
        def __init__(self):
            self.result, self.sent = 0, False

        def open(self):
            pass

        def query(self, spec, arguments):
            return self

        @property
        def columns(self):
            return ("synthetic_a",) if not self.result else ("synthetic_b", "synthetic_c")

        @property
        def source_types(self):
            return ("str",) * len(self.columns)

        def fetchmany(self, size):
            if self.sent:
                return []
            self.sent = True
            return [("synthetic-value",) * len(self.columns)]

        def nextset(self):
            if self.result:
                return False
            self.result, self.sent = 1, False
            return True

        def close(self):
            pass

    monkeypatch.setattr(validation, "PostgresIngestRepository", Repository)
    environment = SimpleNamespace(settings=lambda _: None)
    operations = validation.Operations(environment, lambda _spec, _day: Source(), chunk_size=1)
    operations.progress = progress.append
    spec = validation.probe_spec({"interface": "web.synthetic", "argument_count": 1})
    result = operations.capture(spec, "2026-10-28")
    assert result["rows"] == 2 and len(result["result_sets"]) == 2 and result["complete"]
    assert progress[0]["source_called"] is False and "inspection_batch_id" not in progress[0]
    assert progress[1]["inspection_batch_id"] == 17
    assert progress[-1]["captured"]["snapshot_fingerprint"] == result["snapshot_fingerprint"]
    written = [args[-1] for name, args in calls if name == "write_snapshot"]
    assert [record.ordinal for chunk in written for record in chunk] == [1, 2]
    assert all(
        record.source_key_hash is None and not record.key_complete
        for chunk in written
        for record in chunk
    )
    assert next(i for i, c in enumerate(calls) if c[0] == "commit_snapshot") < next(
        i for i, c in enumerate(calls) if c[0] == "record_inspection_run"
    )


class SnapshotReader:
    def __init__(self, _environment, snapshot):
        self.snapshot, self.sent = snapshot, False

    def open(self):
        pass

    def query(self, spec, arguments):
        return self

    def fetchmany(self, size):
        if self.sent:
            return []
        self.sent = True
        return self.snapshot["fixture_rows"]

    def close(self):
        pass


def synthetic_payload(spec, **updates):
    payload = dict.fromkeys(spec.source_columns)
    payload.update(institute_id="synthetic", patient_id="synthetic", visit_id="synthetic")
    payload.update(updates)
    return tuple(payload[column] for column in spec.source_columns)


def test_actual_key_guard_catches_two_distinct_source_rows_for_one_target_key(monkeypatch):
    monkeypatch.setattr(validation, "SnapshotSource", SnapshotReader)
    original = resolve_interface("web.mr")
    spec = replace(original, key_fields=(*original.key_fields, "name"))
    snapshot = {
        "columns": list(spec.source_columns),
        "date": "2026-10-28",
        "fixture_rows": [
            synthetic_payload(spec, name="synthetic-a"),
            synthetic_payload(spec, name="synthetic-b"),
        ],
    }
    operations = validation.Operations(None, None)
    with pytest.raises(IngestError) as error:
        operations.validate_keys(spec, [snapshot])
    assert error.value.location == "remaining_target_key_collision"


def test_actual_length_guard_precedes_any_database_promotion(monkeypatch):
    monkeypatch.setattr(validation, "SnapshotSource", SnapshotReader)
    spec = resolve_interface("web.mr")
    snapshot = {
        "columns": list(spec.source_columns),
        "date": "2026-10-28",
        "fixture_rows": [synthetic_payload(spec, name="synthetic-name")],
    }
    operations = validation.Operations(None, None)
    with pytest.raises(IngestError) as error:
        operations.validate_keys(spec, [snapshot], {"maximum_lengths": {"name": 3}})
    assert error.value.location == "target_text_too_long"


def test_actual_multiple_result_guard_blocks_replay_after_snapshot_preservation():
    spec = resolve_interface("web.mr")
    operations = validation.Operations(None, None)
    with pytest.raises(IngestError) as error:
        operations.validate_keys(spec, [{"result_sets": [{}, {}]}])
    assert error.value.location == "remaining_multiple_result_sets"


def test_publish_reconcile_selects_exact_evidence_and_requires_terminal_audit(monkeypatch):
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, parameters):
            statements.append((sql, parameters))

        def fetchall(self):
            return [tuple(audit)]

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    environment = SimpleNamespace(connect=lambda *_args, **_kwargs: Connection())
    operations = validation.Operations(environment, None)
    monkeypatch.setattr(operations, "verify", lambda _spec: {"rows": 3, "all_fields_equal": True})
    spec = replace(resolve_interface("web.mr"), evidence_version="synthetic-stage-one")
    audit = [19, "succeeded", None, None, "a" * 64, 3, 0]
    assert operations.reconcile_engine(spec, "publish")["publish_batch_id"] == 19
    assert "evidence_version=%s" in statements[0][0]
    assert statements[0][1] == ("web.mr", "synthetic-stage-one")
    assert "max(" not in statements[0][0].lower()
    audit[1] = "running"
    assert operations.reconcile_engine(spec, "publish") is None
    audit[1] = "succeeded"
    monkeypatch.setattr(operations, "verify", lambda _spec: {"rows": 2, "all_fields_equal": True})
    assert operations.reconcile_engine(spec, "publish") is None


def test_capture_reconcile_requires_same_batch_schema_count_and_entire_snapshot_digest():
    import hashlib

    from medqc_ingest.domain import canonical_json, schema_signature

    schema_hash = schema_signature(["synthetic_column"])[0]
    payload = {"synthetic_column": "synthetic-value"}
    fingerprint = hashlib.sha256(
        (canonical_json([schema_hash, 1, payload]) + "\n").encode()
    ).hexdigest()
    expected = {
        "status": "captured",
        "rows": 1,
        "schema_hash": schema_hash,
        "result_sets": [
            {"schema_hash": schema_hash, "columns": ["synthetic_column"], "source_types": ["str"]}
        ],
        "snapshot_fingerprint": fingerprint,
    }
    metadata = {
        "interface": "web.synthetic",
        "date": "2026-10-28",
        "inspection_batch_id": 17,
        "captured": expected,
    }

    class Cursor:
        def __init__(self):
            self.step, self.sent = 0, False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement, arguments):
            assert arguments[0] == 17
            assert "inspection_batch_id=%s" in statement
            self.step += 1

        def fetchall(self):
            if self.step == 1:
                return [("succeeded", 1, schema_hash, "succeeded")]
            return [(schema_hash, ["synthetic_column"], ["str"])]

        def fetchmany(self, size):
            if self.sent:
                return []
            self.sent = True
            return [(schema_hash, 1, payload)]

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    operations = validation.Operations(
        SimpleNamespace(connect=lambda *_a, **_k: Connection()), None
    )
    spec = validation.probe_spec({"interface": "web.synthetic", "argument_count": 1})
    assert operations.reconcile_capture(spec, "2026-10-28", metadata) == expected
    expected["snapshot_fingerprint"] = "0" * 64
    assert operations.reconcile_capture(spec, "2026-10-28", metadata) is None


def test_driver_is_fixed_before_environment_or_source_access(context, monkeypatch):
    monkeypatch.setenv("MEDQC_PG_DRIVER", "psycopg")
    original = context[1].prepare

    def prepare():
        assert validation.os.environ["MEDQC_PG_DRIVER"] == "psycopg2"
        original()

    context[1].prepare = prepare
    execute(context)


def test_only_confirmed_local_driver_prequery_failure_can_retry_same_stage(tmp_path):
    operations = validation.Operations(None, None)
    spec = validation.probe_spec({"interface": "web.synthetic", "argument_count": 1})
    metadata = {
        "interface": spec.name,
        "date": "2026-10-28",
        "source_called": False,
        "failure": {"error_kind": "configuration_error", "error_location": "psycopg_not_installed"},
    }
    assert operations.reconcile_capture(spec, "2026-10-28", metadata)["retry_prequery"]
    journal = validation.Journal(tmp_path / "progress.json", {"synthetic": True})
    journal.annotate("capture", metadata)
    calls = []
    result = journal.stage(
        "capture",
        lambda: calls.append("retry") or {"status": "captured"},
        lambda value: operations.reconcile_capture(spec, "2026-10-28", value),
    )
    assert result["status"] == "captured" and calls == ["retry"]
    events = journal.events.read_text(encoding="utf-8")
    assert "retry_prequery_verified" in events
    assert operations.reconcile_capture(spec, "2026-10-28", {}) is None


def test_fixed_readonly_key_failure_resumes_without_repeating_snapshots_or_successful_raw(context):
    operations = context[2]
    context[1].backup_revision = lambda: (
        "synthetic-raw-" + str(sum(call[0] == "raw" for call in operations.calls))
    )
    operations.faults[("keys", "web.synthetic_0", None)] = IngestError(
        ErrorKind.PUBLISH_CONTRACT, "synthetic_software_bug"
    )
    operations.faults[("capture", "web.synthetic_1", "2026-10-27")] = source_query_error()
    first = execute(context)
    assert first["interfaces"][0]["status"] == "snapshot_only_contract_blocked"
    successful_calls = [call for call in operations.calls if call[0] in {"capture", "raw"}]
    del operations.faults[("keys", "web.synthetic_0", None)]
    second = execute(context)
    assert second["interfaces"][0]["status"] == "accepted"
    assert second["interfaces"][1]["failed_windows"] == first["interfaces"][1]["failed_windows"]
    captures = [call for call in operations.calls if call[0] == "capture"]
    assert captures == [call for call in successful_calls if call[0] == "capture"]
    for call in successful_calls:
        if call[0] == "raw":
            assert operations.calls.count(call) == 1
    assert operations.calls.count(("keys", "web.synthetic_0", None)) == 2
    assert context[1].backups == 2


def test_actual_key_projection_uses_aware_time_for_local_timestamptz(monkeypatch):
    monkeypatch.setattr(validation, "SnapshotSource", SnapshotReader)
    spec = resolve_interface("web.mr")
    snapshot = {
        "columns": list(spec.source_columns),
        "date": "2026-10-28",
        "fixture_rows": [synthetic_payload(spec)],
    }
    original = validation.project_record
    times = []

    def project(interface, payload, completed_at):
        times.append(completed_at)
        assert completed_at.tzinfo is not None
        return original(interface, payload, completed_at)

    monkeypatch.setattr(validation, "project_record", project)
    assert validation.Operations(None, None).validate_keys(spec, [snapshot])["status"] == "verified"
    assert len(times) == 1


def test_source_signature_syntax_failure_isolated_but_permission_remains_fatal():
    for state, expected in (("42000", True), ("42883", True), ("42501", False)):
        try:
            raise RuntimeError(state, "synthetic-private-text [Native Code 51]")
        except RuntimeError:
            try:
                raise IngestError(ErrorKind.SOURCE_QUERY, "odbc_call") from None
            except IngestError as error:
                assert validation.isolatable(error) is expected
