"""定向补全运维入口：合成数据验证备份、事务、幂等和Bundle验收边界。"""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text


scripts = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("verify_report_sync", scripts / "verify_report_sync.py")
check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check
spec.loader.exec_module(check)
spec = importlib.util.spec_from_file_location("apply_report_sync", scripts / "apply_report_sync.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def plan(value="合成正文"):
    return {"table": "death_record", "schema": "main", "field": "record_content",
            "keys": ["institute_id", "patient_id", "visit_id", "document_id"],
            "original_rows": [{"institute_id": "H", "patient_id": "P", "visit_id": "V",
                               "document_id": "D", "record_content": None}],
            "projected_rows": [{"institute_id": "H", "patient_id": "P", "visit_id": "V",
                                "document_id": "D", "record_content": value}],
            "updates": [{"keys": {"institute_id": "H", "patient_id": "P", "visit_id": "V", "document_id": "D"},
                         "value": value}]}


@pytest.fixture
def engine():
    db = create_engine("sqlite://")
    with db.begin() as conn:
        conn.execute(text("CREATE TABLE death_record (institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                          "document_id TEXT, record_content TEXT, untouched TEXT)"))
        conn.execute(text("INSERT INTO death_record VALUES ('H','P','V','D',NULL,'KEEP')"))
    yield db
    db.dispose()


def test_field_update_and_backup_keep_other_columns(engine, tmp_path):
    p = plan()
    with engine.begin() as conn:
        backup = tool.write_backup([p], tmp_path)
        assert backup.exists()
        assert tool.update_fields(conn, [p]) == 1
    assert json.loads(backup.read_text(encoding="utf-8"))["tables"][0]["original_rows"][0]["record_content"] is None
    with engine.connect() as conn:
        assert conn.execute(text("SELECT record_content, untouched FROM death_record")).one() == ("合成正文", "KEEP")


def test_mid_transaction_failure_rolls_back_prior_update(engine):
    p = plan()
    p["updates"].append({"keys": {**p["updates"][0]["keys"], "document_id": "MISSING"}, "value": "合成"})
    with pytest.raises(check.CheckError, match="unexpected_update_count"):
        with engine.begin() as conn:
            tool.update_fields(conn, [p])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT record_content FROM death_record")).scalar_one() is None


@pytest.mark.parametrize("old,expected", [(None, 1), ("", 1), ("合成正文", 0), ("其他内容", None)])
def test_plan_updates_only_missing_fields_and_is_idempotent(monkeypatch, old, expected):
    p = plan()
    local = {**p["original_rows"][0], "record_content": old}
    etl = SimpleNamespace(_get_local_table_meta=lambda *a: ("cdm", [], p["keys"]))
    monkeypatch.setattr(check, "preview_upsert", lambda *a: ("cdm", SimpleNamespace(rows=p["projected_rows"])))

    class Connection:
        def execute(self, sql, params):
            if "character_maximum_length" in str(sql):
                return SimpleNamespace(all=lambda: [])
            assert str(sql).endswith("FOR UPDATE")
            return SimpleNamespace(mappings=lambda: [local])

    if expected is None:
        with pytest.raises(check.CheckError, match="existing_content_conflict"):
            tool.plan_updates(etl, Connection(), "death_record", [], [("H", "P", "V")], [])
    else:
        result = tool.plan_updates(etl, Connection(), "death_record", [], [("H", "P", "V")], [])
        assert len(result["updates"]) == expected


def test_plan_rejects_extra_or_missing_local_records(monkeypatch):
    p = plan()
    etl = SimpleNamespace(_get_local_table_meta=lambda *a: ("cdm", [], p["keys"]))
    monkeypatch.setattr(check, "preview_upsert", lambda *a: ("cdm", SimpleNamespace(rows=p["projected_rows"])))
    conn = SimpleNamespace(execute=lambda sql, params: SimpleNamespace(all=lambda: [], mappings=lambda: []))
    with pytest.raises(check.CheckError, match="local_report_identity_mismatch"):
        tool.plan_updates(etl, conn, "death_record", [], [("H", "P", "V")], [])


def test_bundle_check_requires_exact_saved_content():
    p = plan()
    assembly = SimpleNamespace(load_domain_bundle=lambda **kw: {
        "structured_context": {"documents": {"death_record": p["projected_rows"]}}
    })
    tool.verify_bundles(assembly, [p])
    assembly.load_domain_bundle = lambda **kw: {"structured_context": {"documents": {"death_record": p["original_rows"]}}}
    with pytest.raises(check.CheckError, match="bundle_content_not_updated"):
        tool.verify_bundles(assembly, [p])


@pytest.mark.parametrize("failure", [None, "backup", "refresh"])
def test_cli_reports_commit_boundary_and_never_prints_clinical_text(monkeypatch, tmp_path, engine, capsys, failure):
    from app.database import connection as db
    from app.services import etl_sync as etl
    from app.services import homology_sync
    from app.services.bundles import assembly
    from app.services.case_identity import CaseRef

    p = plan("PRIVATE-CLINICAL-CONTENT")
    scope = {"source_institute_id": "SOURCE", "target_institute_id": "H",
             "pathology_cases": [{"patient_id": "P", "visit_id": "V"}],
             "death_cases": [{"patient_id": f"P{i}", "visit_id": f"V{i}"} for i in range(5)],
             "pathology_reports": [], "death_record_fields": []}
    (tmp_path / "report-sync-scope-private.json").write_text(json.dumps(scope), encoding="utf-8")
    monkeypatch.setattr(tool, "__file__", str(tmp_path / "apply_report_sync.py"))
    monkeypatch.setattr(check, "load_adapter", lambda *a: homology_sync)
    monkeypatch.setattr(check, "compare_pathology", lambda *a: None)
    monkeypatch.setattr(etl, "get_remote_db_url", lambda: "dbname=clinical_data password=PRIVATE-SECRET")
    monkeypatch.setattr(homology_sync, "resolve_homology_source", lambda **kw: SimpleNamespace(
        table="pathology_exam_report", remote_url="dbname=homology", schema="graph3_homology",
        source_case_refs=lambda refs: refs, adapt_rows=lambda rows, refs: rows))

    def fetch(url, schema, table, refs):
        if table == "death_record":
            return [CaseRef("H", f"P{i}", f"V{i}").as_dict() for i in range(5)]
        return [{}] * 5

    monkeypatch.setattr(check, "fetch_source", fetch)
    monkeypatch.setattr(tool, "plan_updates", lambda etl, conn, table, *a: p if table == "death_record" else {
        **p, "original_rows": [], "updates": [], "projected_rows": []})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    for key in ("HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED", "HOMOLOGY_DATABASE", "HOMOLOGY_SCHEMA",
                "HOMOLOGY_SOURCE_INSTITUTE_ID", "HOMOLOGY_TARGET_INSTITUTE_ID"):
        monkeypatch.setenv(key, "before-test")

    class Begin:
        def __enter__(self):
            self.tx = engine.begin()
            self.conn = self.tx.__enter__()
            return self

        def __exit__(self, *args):
            return self.tx.__exit__(*args)

        def execute(self, sql, params=None):
            if str(sql).startswith("SET LOCAL"):
                return None
            return self.conn.execute(sql, params or {})

    monkeypatch.setattr(db, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), begin=Begin))
    refresh_calls = []

    def refresh(**kw):
        refresh_calls.append(kw)
        if failure == "refresh":
            raise RuntimeError("PRIVATE-CLINICAL-CONTENT")
        return {"scenes": {"final": {"updated": 6}}}

    monkeypatch.setattr(etl, "_refresh_all_bundle_variants_after_sync", refresh)
    monkeypatch.setattr(assembly, "load_domain_bundle", lambda **kw: {
        "structured_context": {"documents": {"death_record": p["projected_rows"]}}
    })
    if failure == "backup":
        monkeypatch.setattr(tool, "write_backup", lambda *a: (_ for _ in ()).throw(OSError("PRIVATE-SECRET")))
    output = tmp_path / "result.jsonl"
    monkeypatch.setattr(sys, "argv", ["apply", "--backend", str(tmp_path), "--output", str(output),
                                     "--backup-dir", str(tmp_path / "backups"), "--apply"])
    assert tool.main() == (0 if failure is None else 1)
    console = capsys.readouterr().out
    assert "PRIVATE-" not in console and "PRIVATE-" not in output.read_text(encoding="utf-8")
    last = json.loads(output.read_text(encoding="utf-8").splitlines()[-1])
    assert last["data_committed"] == (failure != "backup")
    assert bool(refresh_calls) == (failure != "backup")
    with engine.connect() as conn:
        value = conn.execute(text("SELECT record_content FROM death_record")).scalar_one()
    assert value == (None if failure == "backup" else p["updates"][0]["value"])


def test_apply_flag_is_required(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["apply", "--backend", "B", "--output", "O", "--backup-dir", "D"])
    with pytest.raises(SystemExit) as exc:
        tool.main()
    assert exc.value.code == 2
