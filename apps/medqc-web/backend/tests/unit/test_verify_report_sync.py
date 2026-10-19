"""客户机只读演练工具合同；全部使用合成内容。"""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.database.models.cdm import DeathRecord, PathologyExamReport
from app.services import etl_sync
from app.services.case_identity import CaseRef


spec = importlib.util.spec_from_file_location(
    "report_sync_check", Path(__file__).resolve().parents[2] / "scripts" / "verify_report_sync.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ReadConnection:
    def __init__(self):
        self.executed = []

    def execute(self, statement, params):
        assert str(statement).lstrip().startswith("SELECT")
        self.executed.append((str(statement), params))
        return "metadata"


def test_preview_session_never_executes_writes():
    connection = ReadConnection()
    preview = tool.PreviewSession(connection)
    assert preview.execute(text("SELECT 1")) == "metadata"
    preview.execute(text("INSERT INTO cdm.pathology_exam_report VALUES (:diagnosis)"), {"diagnosis": "合成"})
    preview.execute(text("DELETE FROM cdm.pathology_exam_report WHERE visit_id=:v"), [{"v": "V1"}, {"v": "V2"}])
    assert len(connection.executed) == 1
    assert preview.rows == [{"diagnosis": "合成"}]
    assert preview.replacements == 2
    with pytest.raises(tool.CheckError, match="unexpected_sql"):
        preview.execute(text("UPDATE cdm.pathology_exam_report SET diagnosis=NULL"))


@pytest.mark.parametrize("legacy_api", [False, True])
@pytest.mark.parametrize("table", ["pathology_exam_report", "death_record"])
def test_real_upsert_is_intercepted_and_preserves_fixed_fields(monkeypatch, table, legacy_api):
    model = {"death_record": DeathRecord, "pathology_exam_report": PathologyExamReport}[table].__table__
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: (
        "cdm", list(model.c.keys()), list(model.primary_key.columns.keys())
    ))
    fields = etl_sync._STRUCTURED_DOCUMENT_CONTENT_FIELDS["death_record"]
    # 模拟客户旧代码没有死亡章节配置；本进程演练后必须恢复原状。
    mapping = dict(etl_sync._STRUCTURED_DOCUMENT_CONTENT_FIELDS)
    mapping.pop("death_record")
    monkeypatch.setattr(etl_sync, "_STRUCTURED_DOCUMENT_CONTENT_FIELDS", mapping)
    if legacy_api:
        real_upsert = etl_sync.upsert_to_local

        def old_upsert(table_name, records, primary_keys, *, session, replace_case_refs):
            return real_upsert(table_name, records, primary_keys, session=session, replace_case_refs=replace_case_refs)

        monkeypatch.setattr(etl_sync, "upsert_to_local", old_upsert)
    refs, rows = [], []
    for i in range(5):
        ref = CaseRef("H1", f"P{i}", f"V{i}")
        refs.append(ref)
        row = {**ref.as_dict(), "document_id": f"DOC-{i}", "pathology_exam_id": f"EXAM-{i}",
               "diagnosis": "合" * (14, 268, 6, 48, 37)[i],
               "admission_time": datetime(2026, 1, 1, 10), "record_time": datetime(2026, 1, 2, 10),
               "admission_condition": "合成入院情况", "treatment_course": "合成诊疗经过",
               "death_time": datetime(2026, 1, 2, 9, tzinfo=timezone.utc), "death_reason": "合成原因",
               "record_content": "合成已有正文" if i == 0 else None}
        rows.append(row)
    conn = ReadConnection()
    schema, preview = tool.preview_upsert(etl_sync, table, rows, refs, conn, fields)
    assert schema == "cdm" and conn.executed == []
    assert len(preview.rows) == 5 and preview.replacements == 5
    assert "death_record" not in mapping
    if table == "death_record":
        assert all("诊疗经过：合成诊疗经过" in r["record_content"] for r in preview.rows)
        assert "合成已有正文" in preview.rows[0]["record_content"]
    else:
        assert [len(r["diagnosis"]) for r in preview.rows] == [14, 268, 6, 48, 37]


def test_lengths_find_actual_target_truncation_without_printing_content():
    with pytest.raises(tool.CheckError) as exc:
        tool.validate_lengths([{"diagnosis": "合" * 268}], {"diagnosis": 100}, "pathology_exam_report")
    assert exc.value.code == "target_value_too_long"
    assert exc.value.details == {"table": "pathology_exam_report", "field": "diagnosis", "allowed": 100, "actual": 268}
    assert "合" not in str(exc.value.details)


def pathology_pair():
    row = {"patient_id": "P1", "visit_id": "V1", "pathology_exam_id": "A1", "pathology_id": "B1",
           "report_status": "审核", "diagnosis": "合成诊断", "report_datetime": datetime(2026, 1, 1, 10)}
    baseline = {**row, "report_time": datetime(2026, 1, 1, 2, tzinfo=timezone.utc)}
    return row, baseline


def test_pathology_identity_compares_same_hospital_time():
    row, baseline = pathology_pair()
    tool.compare_pathology([row], [baseline], [row])


@pytest.mark.parametrize("kind", ["identity", "duplicate", "time", "status", "diagnosis"])
def test_changed_source_reports_fail_without_exporting_text(kind):
    row, baseline = pathology_pair()
    expected = dict(row)
    rows = [row]
    if kind == "identity":
        row["pathology_id"] = "OTHER"
    elif kind == "duplicate":
        rows.append(dict(row))
    elif kind == "time":
        row["report_datetime"] = datetime(2026, 1, 2, 10)
    elif kind == "status":
        row["report_status"] = "待报告"
    else:
        row["diagnosis"] = None
    with pytest.raises(tool.CheckError) as exc:
        tool.compare_pathology(rows, [baseline], [expected])
    assert "合成" not in str(exc.value)


def test_source_connection_is_readonly_and_scope_is_bound(monkeypatch):
    import psycopg2

    events = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            events.append((sql, params))

        def fetchall(self):
            return []

    class Connection:
        def set_session(self, **kw):
            events.append(kw)

        def cursor(self, **kw):
            assert events == [{"readonly": True}]
            return Cursor()

        def close(self):
            events.append("closed")

    monkeypatch.setattr(psycopg2, "connect", lambda *a, **kw: Connection())
    tool.fetch_source("dbname=synthetic", "public", "death_record", [CaseRef("H1", "P1", "V1")])
    assert events[2][1] == ["H1", "P1", "V1"]
    assert "P1" not in events[2][0]
    assert events[-1] == "closed"


def test_packaged_cli_is_readonly_and_only_outputs_metadata(monkeypatch, tmp_path, capsys):
    from app.database import connection as db
    from app.services import homology_sync

    fields = etl_sync._STRUCTURED_DOCUMENT_CONTENT_FIELDS["death_record"]
    target = CaseRef("H1", "P1", "V1")
    death_target = CaseRef("H1", "P2", "V2")
    report, baseline = pathology_pair()
    report.update(institute_id="SOURCE-H1", diagnosis="NEVER-PRINT-CLINICAL")
    baseline.update(institute_id="H1")
    death = {**death_target.as_dict(), "document_id": "D1", "record_time": datetime(2026, 1, 1, 10),
             "admission_condition": "NEVER-PRINT-DEATH", "treatment_course": "合成诊疗经过",
             "death_time": datetime(2026, 1, 1, 9), "death_reason": "合成原因", "record_content": None}
    scope = {"source_institute_id": "SOURCE-H1", "target_institute_id": "H1",
             "pathology_cases": [{**target.as_dict(), "sample": "C23"}],
             "death_cases": [{**death_target.as_dict(), "sample": "C02"}],
             "pathology_reports": [report], "death_record_fields": fields}
    # 范围文件不需要诊断正文、日期或状态。
    scope["pathology_reports"] = [{k: report[k] for k in (
        "patient_id", "visit_id", "pathology_exam_id", "pathology_id"
    )}]
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(json.dumps(scope), encoding="utf-8")
    shutil.copyfile(homology_sync.__file__, tmp_path / "homology_sync.py")
    monkeypatch.setattr(tool, "__file__", str(tmp_path / "verify_report_sync.py"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in ("HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED", "HOMOLOGY_DATABASE", "HOMOLOGY_SCHEMA",
                 "HOMOLOGY_SOURCE_INSTITUTE_ID", "HOMOLOGY_TARGET_INSTITUTE_ID"):
        monkeypatch.setenv(name, "before-test")
    output = tmp_path / "result.jsonl"
    monkeypatch.setattr(sys, "argv", ["verify", "--backend", str(tmp_path), "--scope", str(scope_path),
                                      "--output", str(output)])
    models = {"pathology_exam_report": PathologyExamReport.__table__, "death_record": DeathRecord.__table__}
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda _, table: (
        "cdm", list(models[table].c.keys()), list(models[table].primary_key.columns.keys())
    ))
    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "dbname=clinical_data password=NEVER-PRINT-PASSWORD")
    source_calls, database_commands = [], []

    def fetch(url, schema, table, refs):
        source_calls.append((schema, table))
        if table == "death_record":
            return [death]
        return [report] if schema == "graph3_homology" else [baseline]

    monkeypatch.setattr(tool, "fetch_source", fetch)

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

        def mappings(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            statement = str(sql)
            database_commands.append(statement)
            assert statement.startswith(("SET TRANSACTION READ ONLY", "SELECT"))
            if "character_maximum_length" in statement:
                return Result([])
            if "SELECT *" in statement:
                row = {**target.as_dict(), "diagnosis": None} if "pathology" in statement else {
                    **death_target.as_dict(), "record_content": None
                }
                return Result([row])
            return Result([])

    monkeypatch.setattr(db, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=Connection))
    assert tool.main() == 0
    lines = capsys.readouterr().out
    assert "NEVER-PRINT" not in lines and "NEVER-PRINT" not in output.read_text(encoding="utf-8")
    events = [json.loads(line) for line in lines.splitlines()]
    assert events[-1]["check_passed"] is True
    assert events[-1]["database_writes"] == events[-1]["model_calls"] == 0
    assert len([e for e in events if e["event"] == "case_preview"]) == 2
    assert len(source_calls) == 3 and len(database_commands) == 6
