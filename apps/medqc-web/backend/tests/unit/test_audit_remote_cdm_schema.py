"""源库CDM盘点必须只读，且不能把任何患者原始数据写入报告。"""

from __future__ import annotations

import os

from scripts import audit_remote_cdm_schema as audit


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self._rows: list[tuple[object, ...]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement, params=None) -> None:
        sql = str(statement)
        self.executed.append((sql, params))
        if sql.startswith("SELECT COUNT("):
            self._rows = [(0, 0, "2026-08-19T00:00:00+00:00")]
        elif "information_schema.tables" in sql:
            self._rows = [
                ("bloodtrans_inform_consent", "BASE TABLE"),
                ("inpat_nondrug_order", "BASE TABLE"),
            ]
        elif "information_schema.columns" in sql:
            self._rows = [
                ("bloodtrans_inform_consent", "patient_id", "character varying", 1, "NO"),
                ("bloodtrans_inform_consent", "visit_id", "character varying", 2, "NO"),
                ("bloodtrans_inform_consent", "document_id", "character varying", 3, "NO"),
                ("bloodtrans_inform_consent", "record_time", "timestamp with time zone", 4, "YES"),
                ("inpat_nondrug_order", "patient_id", "character varying", 1, "NO"),
                ("inpat_nondrug_order", "visit_id", "character varying", 2, "NO"),
            ]
        elif "table_constraints" in sql:
            self._rows = [
                ("bloodtrans_inform_consent", "patient_id", 1),
                ("bloodtrans_inform_consent", "visit_id", 2),
                ("bloodtrans_inform_consent", "document_id", 3),
            ]
        elif "pg_indexes" in sql:
            self._rows = [
                ("bloodtrans_inform_consent", "bloodtrans_inform_consent_pkey", "CREATE UNIQUE INDEX"),
            ]
        elif "pg_stat_user_tables" in sql:
            self._rows = [("bloodtrans_inform_consent", 0)]
        else:
            self._rows = []

    def fetchall(self):
        return list(self._rows)


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeCursor()
        self.rollback_called = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self) -> None:
        self.rollback_called = True

    def close(self) -> None:
        return None


def test_metadata_audit_uses_read_only_transaction_and_never_reads_patient_rows():
    connection = _FakeConnection()

    report = audit.audit_remote_schema(
        remote_url="postgresql://audit-user:secret@127.0.0.1:5432/source",
        remote_schema="public",
        mode="metadata",
        sync_tables=[],
        connector=lambda _url: connection,
    )

    executed_sql = "\n".join(sql for sql, _params in connection.cursor_instance.executed)
    assert report["read_only"] is True
    assert report["patient_data_returned"] is False
    assert "BEGIN TRANSACTION READ ONLY" in executed_sql
    assert "information_schema.columns" in executed_sql
    assert "SELECT *" not in executed_sql.upper()
    assert "secret" not in audit.render_markdown(report)
    assert connection.rollback_called is True


def test_coverage_reports_missing_configured_source_and_identity_field_gap():
    connection = _FakeConnection()

    report = audit.audit_remote_schema(
        remote_url="postgresql://audit-user:secret@127.0.0.1:5432/source",
        remote_schema="public",
        mode="coverage",
        sync_tables=[
            {
                "name": "consent_form",
                "source_table": "bloodtrans_inform_consent",
                "key_fields": ["patient_id", "visit_id", "document_id"],
                "enabled": True,
            },
            {
                "name": "physician_change_event",
                "source_table": "physician_change_event",
                "key_fields": ["patient_id", "visit_id", "document_id"],
                "enabled": True,
            },
        ],
        connector=lambda _url: connection,
    )

    rows = {item["name"]: item for item in report["sync_table_coverage"]}
    assert rows["consent_form"]["status"] == "ready"
    assert rows["consent_form"]["missing_identity_fields"] == []
    assert rows["physician_change_event"]["status"] == "source_table_missing"


def test_report_writer_emits_json_and_markdown_without_connection_secret(tmp_path):
    report = {
        "generated_at": "2026-08-19T00:00:00+00:00",
        "remote_schema": "public",
        "read_only": True,
        "patient_data_returned": False,
        "connection": {"host": "127.0.0.1", "database": "source", "password": "[REDACTED]"},
        "summary": {"configured_tables": 1, "ready_tables": 1},
        "sync_table_coverage": [],
        "formal_source_coverage": [],
        "source_tables": [],
    }

    paths = audit.write_report(report, output_dir=tmp_path, stamp="20260819-000000")

    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert "secret" not in paths["markdown"].read_text(encoding="utf-8")
    assert "patient_name" not in paths["markdown"].read_text(encoding="utf-8")


def test_profile_mode_returns_only_aggregate_counts_and_time_watermark():
    connection = _FakeConnection()

    report = audit.audit_remote_schema(
        remote_url="postgresql://audit-user:secret@127.0.0.1:5432/source",
        remote_schema="public",
        mode="profile",
        exact_count=True,
        sync_tables=[
            {
                "name": "consent_form",
                "source_table": "bloodtrans_inform_consent",
                "key_fields": ["patient_id", "visit_id", "document_id"],
                "date_field": "record_time",
                "enabled": True,
            }
        ],
        connector=lambda _url: connection,
    )

    assert report["profile"] == [
        {
            "name": "consent_form",
            "source_table": "bloodtrans_inform_consent",
            "exact_count": 0,
            "identity_complete_count": 0,
            "latest_business_time": "2026-08-19T00:00:00+00:00",
            "candidate_time_column": "record_time",
        }
    ]
    executed_sql = "\n".join(sql for sql, _params in connection.cursor_instance.executed)
    assert "SELECT *" not in executed_sql.upper()


def test_load_backend_env_reads_nearest_env_without_overriding_existing_value(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    script_dir = backend_dir / "app" / "scripts"
    script_dir.mkdir(parents=True)
    (backend_dir / ".env").write_text(
        "REMOTE_DB_URL=postgresql://audit-user:secret@127.0.0.1:5432/source\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("REMOTE_DB_URL", raising=False)

    loaded = audit.load_backend_env(search_start=script_dir)

    assert loaded == backend_dir / ".env"
    assert os.environ["REMOTE_DB_URL"].endswith("/source")
    monkeypatch.setenv("REMOTE_DB_URL", "postgresql://already-set")
    audit.load_backend_env(search_start=script_dir)
    assert os.environ["REMOTE_DB_URL"] == "postgresql://already-set"


def test_resolve_backend_root_supports_script_under_app_scripts(tmp_path):
    backend_dir = tmp_path / "backend"
    script_path = backend_dir / "app" / "scripts" / "audit_remote_cdm_schema.py"
    script_path.parent.mkdir(parents=True)
    script_path.touch()

    assert audit.resolve_backend_root(search_start=script_path) == backend_dir
