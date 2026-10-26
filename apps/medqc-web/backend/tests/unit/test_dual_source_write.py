"""双源真实写入控制流的离线测试，全部连接为替身，不改业务库。"""

from copy import deepcopy
import hashlib
import json
from unittest.mock import MagicMock, Mock

import pytest

from app.services import dual_source_sync as policy
from app.services import dual_source_write as store
from app.services.dual_source_write_policy import approval_digest, build_write_batch, cast_cell


CASE = {"sample": "C01", "institute_id": "H", "patient_id": "P", "visit_id": "V"}
INSTITUTES = {"clinical_data": "H", "homology": "UP", "local": "H"}
DOC = "discharge_record"
DRUG = "inpat_drug_order"


def row(**values):
    return {**{k: CASE[k] for k in policy.IDENTITY_FIELDS}, "document_id": "D1", "order_id": "O1", "drug_code": "CODE1", **values}


def metadata(table=DOC, **overrides):
    fields = {*policy.IDENTITY_FIELDS, "document_id", "order_id", "drug_code", "record_content",
              "v2_schema", "chief_physician_sign_datetime", "record_datetime", "submit_datetime",
              "planned_end_datetime", "order_status", "quantity", "quantity_unit", "single_dose",
              "single_dose_unit", "drug_frequency", "drug_apply_method", "medication_duration", "eye_findings"}
    pks = [*policy.IDENTITY_FIELDS, "order_id" if table == DRUG else "document_id"]
    cols = {f: {"data_type": "text", "is_nullable": "NO" if f in pks else "YES",
                "is_identity": "NO", "is_generated": "NEVER", "column_default": None} for f in fields}
    for f in fields:
        if f.endswith("_datetime"):
            cols[f]["data_type"] = "timestamp with time zone"
    cols.update(overrides)
    return {"columns": cols, "primary_keys": pks}


def plan(table=DOC, *, clinical=(), homology=(), local=(), **kwargs):
    return policy.plan_table(table, CASE, policy.SourceSnapshot("clinical_data", tuple(clinical)),
                             policy.SourceSnapshot("homology", tuple(homology)),
                             policy.SourceSnapshot("local", tuple(local)), source_institutes=INSTITUTES, **kwargs)


def batch(table=DOC, clinical=(), homology=(), local=(), meta=None, approved=()):
    result = plan(table, clinical=clinical, homology=homology, local=local)
    meta = meta or metadata(table)
    return build_write_batch(table, result, CASE, meta["columns"], meta["primary_keys"], local, approved_records=approved)


def test_new_clinical_document_inserted_without_replacing_existing():
    result = batch(clinical=[row(record_content="完整正文")])
    assert len(result.operations) == 1
    assert result.operations[0]["before"] is None
    assert result.operations[0]["values"]["record_content"] == "完整正文"


def test_conflicting_body_preserved_while_confirmed_empty_time_filled():
    before = row(record_content="本地原文", order_status="新开")
    source = row(record_content="另一版本", order_status="停止", planned_end_datetime="2026-01-02T10:00:00")
    result = batch(clinical=[source], local=[before])
    assert set(result.operations[0]["values"]) == {"planned_end_datetime"}
    assert set(result.records[0]["conflicts"]) >= {"record_content", "order_status"}
    assert before["record_content"] == "本地原文"


def test_two_sources_disagree_on_empty_target_field_do_not_fill_it():
    result = batch(clinical=[row(record_content="A")],
                   homology=[row(institute_id="UP", record_content="B")], local=[row()])
    assert not result.operations
    assert "record_content" in result.records[0]["conflicts"]


def test_same_body_signature_supplement_fills_only_blank_name_list():
    table = "senior_course_record"
    before = row(record_content="合成病程。 医师签名：")
    source = row(institute_id="UP", record_content="合成病程。 医师签名：甲医生 乙医生")
    meta = metadata(table)
    meta["columns"]["physician_sign"] = {"data_type": "text", "is_nullable": "YES", "is_identity": "NO", "is_generated": "NEVER", "column_default": None}
    result = batch(table, homology=[source], local=[before], meta=meta)
    assert len(result.operations) == 1
    assert result.operations[0]["values"] == {"physician_sign": "甲医生 乙医生"}
    assert "record_content" in result.records[0]["conflicts"]
    assert before["record_content"] == "合成病程。 医师签名："


def test_local_only_never_deleted_or_rewritten():
    result = batch(local=[row(record_content="仍保留")])
    assert not result.operations


def test_source_only_homology_document_needs_exact_reviewed_digest():
    source = row(institute_id="UP", record_content="正文", documentstatus="Save")
    assert not batch(homology=[source]).operations
    normalized = policy.normalize_row(source)[0]
    digest = approval_digest(normalized)
    assert batch(homology=[source], approved={('D1',): digest}).operations
    assert not batch(homology=[{**source, "record_content": "已改变"}], approved={('D1',): digest}).operations


def test_homology_only_order_is_not_treated_as_unconfirmed_save_document():
    assert batch(DRUG, homology=[row(institute_id="UP", order_status="核实")]).operations


@pytest.mark.parametrize("values", [{"is_deleted": "1"}, {"drug_code": "OTHER"}])
def test_deleted_or_identity_conflict_not_written(values):
    source = row(institute_id="UP", planned_end_datetime="2026-01-02", **values)
    assert not batch(DRUG, homology=[source], local=[row()]).operations


def test_same_source_duplicate_id_quarantined():
    result = plan(clinical=[row(), row()])
    assert result.quarantined_rows == 2 and not result.candidates


def test_cross_drug_nondrug_id_never_inserted():
    first = plan(DRUG, clinical=[row()])
    second = plan("inpat_nondrug_order", clinical=[row()])
    policy.mark_cross_table_order_ids([first, second])
    assert all("cross_table_order_identity" in p.candidates[0].blockers for p in [first, second])


def test_signature_and_json_preserved_without_promoting_document_clocks():
    source = row(chief_physician_sign_datetime="2026-01-02T00:00:00", v2_schema='{"text":"' + "甲" * 10000 + '"}')
    values = batch(clinical=[source], local=[row()]).operations[0]["values"]
    assert len(values["v2_schema"]) > 10000
    assert "record_datetime" not in values and "submit_datetime" not in values
    assert values["chief_physician_sign_datetime"].utcoffset().total_seconds() == 28800


def test_regimen_conflict_cannot_mix_new_dose_with_old_frequency():
    source = row(single_dose="2", single_dose_unit="mg", drug_frequency="每日两次", planned_end_datetime="2026-01-02")
    result = batch(DRUG, clinical=[source], local=[row(drug_frequency="每日一次")])
    assert set(result.operations[0]["values"]) == {"planned_end_datetime"}


def test_overlong_optional_field_skipped_without_truncation():
    meta = metadata(eye_findings={"data_type": "character varying", "character_maximum_length": 100, "is_nullable": "YES"})
    result = batch(clinical=[row(eye_findings="甲" * 378, record_content="正文")], local=[row()], meta=meta)
    assert "eye_findings" not in result.operations[0]["values"]
    assert "invalid_target_value:eye_findings" in result.records[0]["skipped"]


def test_zero_is_not_empty_and_is_not_overwritten():
    result = batch(clinical=[row(quantity="2", record_content="正文")], local=[row(quantity="0")])
    assert "quantity" not in result.operations[0]["values"]


def test_old_lab_identity_cannot_create_duplicate_source_rows():
    table = "labtest_item_report"
    local = row()
    source = row(document_id="NEW", test_id="T", print_order_id="1")
    assert not batch(table, clinical=[source], local=[local]).operations


def test_clinical_only_primary_table_uses_real_primary_key_scope():
    result = plan("mr", clinical=[row()], stable_keys=())
    assert len(result.candidates) == 1


@pytest.mark.parametrize("kind,value", [("integer", "1.1"), ("smallint", "40000"), ("numeric", "NaN"), ("boolean", "maybe")])
def test_invalid_types_rejected(kind, value):
    with pytest.raises(ValueError):
        cast_cell(value, {"data_type": kind})


def test_backup_roundtrip_and_scope_only(tmp_path):
    path = tmp_path / "before-private.json"
    digest = store.save_backup(path, cases=[CASE], metadata={DOC: metadata()}, originals={DOC: [row()]})
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert json.loads(path.read_text(encoding="utf-8"))["rows"][DOC] == [row()]


def test_verify_unrelated_field_change_and_row_deletion_rejected():
    with pytest.raises(store.DualSourceWriteError):
        store.verify_rows([row(record_content="A")], [row(record_content="B")], [], metadata()["primary_keys"])
    with pytest.raises(store.DualSourceWriteError):
        store.verify_rows([row()], [], [], metadata()["primary_keys"])


def test_sql_is_guarded_and_never_delete_or_ddl():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    operation = {"table": DOC, "primary_keys": metadata()["primary_keys"], "before": row(), "values": {"record_content": "正文"}}
    store.apply_operations(conn, "cdm", [operation], {DOC: metadata()})
    query = str(cursor.execute.call_args.args[0])
    assert "IS NOT DISTINCT FROM" in query
    assert "DELETE" not in query and "ALTER" not in query
    cursor.rowcount = 0
    with pytest.raises(store.DualSourceWriteError, match="concurrent_target_change"):
        store.apply_operations(conn, "cdm", [operation], {DOC: metadata()})


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    connections = {key: Mock(name=key) for key in ("local", "clinical_data", "homology")}
    rows = {"local": [], "clinical_data": [row(record_content="正文")], "homology": []}
    monkeypatch.setattr(store, "_connect", lambda dsn, **_: connections[dsn])
    monkeypatch.setattr(store, "table_meta", lambda *args: metadata())
    monkeypatch.setattr(store, "related_rows", lambda *args: {})
    def read(conn, *args, **kwargs):
        return deepcopy(rows[next(key for key, value in connections.items() if value is conn)])
    monkeypatch.setattr(store, "read_rows", read)
    def write(conn, schema, operations, meta):
        rows["local"].extend(dict(op["values"]) for op in operations)
    write_mock = Mock(side_effect=write)
    monkeypatch.setattr(store, "apply_operations", write_mock)
    kwargs = dict(local_dsn="local", source_dsns={"clinical_data": "clinical_data", "homology": "homology"},
                  cases=[CASE], tables=[DOC], source_institutes=INSTITUTES,
                  backup_dir=tmp_path / "backups", report_dir=tmp_path / "reports")
    return kwargs, connections, rows, write_mock


def test_preview_never_writes_or_backs_up(runtime):
    kwargs, conns, _, write = runtime
    result = store.run_sync(**kwargs)
    assert result["report"]["inserts"] == 1
    write.assert_not_called()
    conns["local"].commit.assert_not_called()
    assert not kwargs["backup_dir"].exists()


def test_backup_failure_stops_before_write(runtime, monkeypatch):
    kwargs, conns, _, write = runtime
    monkeypatch.setattr(store, "save_backup", Mock(side_effect=OSError("private credential")))
    with pytest.raises(store.DualSourceWriteError) as error:
        store.run_sync(**kwargs, apply=True)
    write.assert_not_called()
    conns["local"].commit.assert_not_called()
    assert error.value.data_committed is False
    assert "credential" not in open(error.value.report_path, encoding="utf-8").read()


def test_apply_backups_then_writes_once_and_repeat_is_noop(runtime):
    kwargs, conns, _, write = runtime
    result = store.run_sync(**kwargs, apply=True)
    assert result["report"]["data_committed"] is True
    assert result["report"]["inserts"] == 1
    conns["local"].commit.assert_called_once()
    assert json.loads(open(result["report"]["backup_path"], encoding="utf-8").read())["rows"][DOC] == []
    repeated = store.run_sync(**kwargs, apply=True)
    assert repeated["report"]["inserts"] == repeated["report"]["updated_rows"] == 0
    assert write.call_count == 2


def test_post_write_validation_failure_does_not_commit(runtime, monkeypatch):
    kwargs, conns, _, _ = runtime
    monkeypatch.setattr(store, "verify_rows", Mock(side_effect=store.DualSourceWriteError("bad_verification")))
    with pytest.raises(store.DualSourceWriteError) as error:
        store.run_sync(**kwargs, apply=True)
    conns["local"].commit.assert_not_called()
    assert error.value.data_committed is False


def test_commit_connection_loss_reports_unknown(runtime):
    kwargs, conns, _, _ = runtime
    conns["local"].commit.side_effect = OSError("lost")
    with pytest.raises(store.DualSourceWriteError) as error:
        store.run_sync(**kwargs, apply=True)
    assert error.value.data_committed is None


def test_wrong_institution_fails_before_connection(runtime, monkeypatch):
    kwargs, _, _, _ = runtime
    connect = Mock()
    monkeypatch.setattr(store, "_connect", connect)
    with pytest.raises(store.DualSourceWriteError, match="target_institution_mismatch"):
        store.run_sync(**{**kwargs, "cases": [{**CASE, "institute_id": "OTHER"}]}, apply=True)
    connect.assert_not_called()


def test_json_formal_document_id_beats_governance_id():
    source = {**row(record_content="正文"), "document_id": None,
              "sys_index_id": 123, "v2_schema": '{"document_id":"FORMAL"}'}
    result = batch(clinical=[source])
    assert result.operations[0]["values"]["document_id"] == "FORMAL"


def test_review_hash_not_affected_by_nonclinical_date_serialization():
    source = row(institute_id="UP", record_content="已核对正文", record_datetime="2026-01-02T08:00:00",
                 admission_date="2026-01-01T10:00:00")
    first = policy.normalize_row(source)[0]
    second = {**first, "admission_date": "2026-01-01 10:00:00"}
    assert approval_digest(first) == approval_digest(second)
    assert approval_digest(first) != approval_digest({**second, "record_content": "改变正文"})


def test_source_read_error_never_reaches_target_write(runtime, monkeypatch):
    kwargs, conns, _, write = runtime
    def fail(dsn, **kw):
        assert kw["readonly"] is True
        raise OSError("do not expose connection credentials")
    monkeypatch.setattr(store, "_connect", fail)
    with pytest.raises(store.DualSourceWriteError) as error:
        store.run_sync(**kwargs, apply=True)
    write.assert_not_called()
    conns["local"].commit.assert_not_called()
    assert error.value.data_committed is False
    assert "credentials" not in open(error.value.report_path, encoding="utf-8").read()


def test_connection_readonly_is_enforced_and_failed_mode_closes():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = ("on",)
    assert store._connect("synthetic", readonly=True, factory=Mock(return_value=conn)) is conn
    assert conn.set_session.call_args.kwargs["readonly"] is True
    cur.fetchone.return_value = ("off",)
    with pytest.raises(store.DualSourceWriteError, match="transaction_mode_mismatch"):
        store._connect("synthetic", readonly=True, factory=Mock(return_value=conn))
    conn.close.assert_called_once()



def test_floating_target_uses_driver_compatible_value():
    assert isinstance(cast_cell("1.2", {"data_type": "double precision"}), float)


def test_invalid_regimen_value_cannot_insert_partial_dose_group():
    meta = metadata(DRUG, single_dose={"data_type": "numeric", "is_nullable": "YES"})
    result = batch(DRUG, clinical=[row(single_dose="invalid", single_dose_unit="mg", drug_frequency="每日一次")], meta=meta)
    values = result.operations[0]["values"]
    assert not {"single_dose", "single_dose_unit", "drug_frequency"}.intersection(values)
    assert "invalid_target_value:single_dose" in result.records[0]["skipped"]
