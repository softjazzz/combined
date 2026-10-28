"""同一已复核选择必须在Bundle/规则的LIMIT前生效，且不改变原始行。"""
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import Mock

import pytest

from app.database import connection as db
from app.services import dual_source_sync
from app.services import validation_material_source as selection
from app.services.bundles import assembly
from app.services.luxian_0609 import source_evidence_reader as reader


IDENTITY = dict(institute_id="SYN", patient_id="pdfp_syn", visit_id="pdfv_syn")
SCHEMA = "pdfmat_0123456789ab"
REVIEW = dict(decision="remove_pdf_duplicate", original_pg_ids=["PG"], pdf_document_id="PDF")


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.rows


class ReadEngine:
    def __init__(self, rows):
        self.rows, self.calls = rows, []
        self.review_error = False

    @contextmanager
    def connect(self):
        yield self

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        assert sql.lstrip().startswith("SELECT")
        if "qc.validation_material_documents" in sql:
            if self.review_error:
                raise RuntimeError("synthetic review read failure")
            return Result([dict(candidate_id="CANDIDATE", target_document_id="PDF", review=REVIEW,
                                identity_map={"entities": {"old": "PG"}})])
        invalid_statuses = {
            value
            for key, value in params.items()
            if key.startswith("invalid_document_status_")
        }
        if "parent_ids" in params:
            return Result([
                row["document_id"]
                for row in self.rows
                if row["document_id"] in params["parent_ids"]
                and str(row.get("document_status") or "").strip() not in invalid_statuses
            ])
        rows = [
            row
            for row in self.rows
            if row["document_id"] not in params.get("material_excluded_ids", [])
            and str(row.get("document_status") or "").strip() not in invalid_statuses
        ]
        return Result(rows[:params["limit_rows"]])


@pytest.fixture
def source(monkeypatch):
    rows = [
        dict(
            document_id=id_,
            document_title="合成文书",
            record_content="合成正文",
            record_time="2026-10-01 08:00:00",
            document_status=status,
        )
        for id_, status in (
            ("PDF", "Save"),
            ("PG", "已提交"),
            ("VOID", "作废"),
            ("UNIQUE", "待确认"),
        )
    ]
    engine = ReadEngine(rows)
    monkeypatch.setattr(selection, "_registered_schema", lambda *_: SCHEMA)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(assembly, "engine", engine)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *_: set(rows[0]) | set(IDENTITY))
    monkeypatch.setattr(reader, "_source_limit", lambda _: 2)
    return engine


@pytest.mark.parametrize("entry", ["bundle", "snapshot", "native", "runtime", "timeline"])
def test_all_bounded_document_reads_apply_same_selection_before_limit(source, entry):
    before = deepcopy(source.rows)
    if entry == "bundle":
        rows = assembly._select_records(schema=SCHEMA, table="daily_course_record", limit=2, **IDENTITY)
    elif entry == "timeline":
        result = reader.read_luxian_0609_course_round_timeline(source_schema=SCHEMA, **IDENTITY)
        assert sum(len(rows) for rows in result.values()) == 4
        rows = None
    else:
        table = "presurg_summary" if entry == "runtime" else "daily_course_record"
        function = getattr(reader, "read_luxian_0609_" + entry + "_source_rows")
        result = function(source_key=table, source_schema=SCHEMA, **IDENTITY)
        if entry == "snapshot":
            assert not result.truncated
            rows = result.rows
        else:
            rows = result
    if rows is not None:
        assert [row["document_id"] for row in rows] == ["PG", "UNIQUE"]
    for sql, params in source.calls:
        if "limit_rows" in params:
            assert sql.index("material_excluded_ids") < sql.index("LIMIT")
            assert sql.index("invalid_document_status_0") < sql.index("LIMIT")
            assert params["material_excluded_ids"] == ["PDF"]
            assert set(selection.EXPLICITLY_INVALID_DOCUMENT_STATUSES) == {
                value
                for key, value in params.items()
                if key.startswith("invalid_document_status_")
            }
        assert IDENTITY["patient_id"] in params.values()
        assert IDENTITY["visit_id"] in params.values()
        assert IDENTITY["institute_id"] in params.values()
    assert source.rows == before


def test_missing_original_preserves_pdf_and_independent_document(source):
    source.rows = [row for row in source.rows if row["document_id"] != "PG"]
    result = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema=SCHEMA, **IDENTITY)
    assert [row["document_id"] for row in result.rows] == ["PDF", "UNIQUE"]
    assert not result.truncated


def test_invalid_original_does_not_hide_active_pdf_copy(source):
    next(row for row in source.rows if row["document_id"] == "PG")["document_status"] = "作废"
    result = reader.read_luxian_0609_snapshot_source_rows(
        source_key="daily_course_record", source_schema=SCHEMA, **IDENTITY,
    )
    assert [row["document_id"] for row in result.rows] == ["PDF", "UNIQUE"]
    assert not result.truncated


@pytest.mark.parametrize("source_key,physical_table", [
    ("summary_record", "summary_record"),
    ("death_record", "death_record"),
    (reader.ROUTINE_LAB_ITEM_SOURCE_KEY, "labtest_item_report"),
])
def test_timeliness_sources_keep_pdf_selection_on_physical_table(source, source_key, physical_table):
    result = reader.read_luxian_0609_snapshot_source_rows(
        source_key=source_key, source_schema=SCHEMA, **IDENTITY,
    )
    assert result.source_key == source_key
    assert [row["document_id"] for row in result.rows] == ["PG", "UNIQUE"]
    assert not result.truncated
    queries = [(sql, params) for sql, params in source.calls if "limit_rows" in params]
    assert len(queries) == 1
    sql, params = queries[0]
    assert f'FROM "{SCHEMA}"."{physical_table}"' in sql
    assert sql.index("material_excluded_ids") < sql.index("LIMIT")
    assert params["material_excluded_ids"] == ["PDF"]


def test_review_read_failure_blocks_rule_instead_of_returning_duplicate_material(source):
    source.review_error = True
    with pytest.raises(reader.SourceEvidenceQueryError):
        reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema=SCHEMA, **IDENTITY)


def test_real_case_has_no_material_registry_query(monkeypatch):
    monkeypatch.setattr(selection, "_registered_schema", lambda *_: pytest.fail("must not query registry"))
    assert selection.material_document_sql_filter(source_schema="cdm", source_table="daily_course_record",
        institute_id="SYN", patient_id="patient", visit_id="visit") == ("", {})


@pytest.mark.parametrize("parents,originals,available", [([], {"PG"}, {"PG"}), (["PG"], set(), {"PG"}),
    (["PG"], {"PG"}, set()), (["PG", "OTHER"], {"PG", "OTHER"}, {"PG"})])
def test_unproven_parent_cannot_remove_pdf(parents, originals, available):
    assert not selection.reviewed_pdf_document_exclusions(
        reviews={"C": {**REVIEW, "original_pg_ids": parents}}, original_document_ids=originals,
        available_document_ids=available)


class DocumentReadEngine:
    """只模拟参数化SELECT；不连接真实数据库。"""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    @contextmanager
    def connect(self):
        yield self

    def execute(self, statement, params):
        sql = str(statement)
        bound = dict(params)
        self.calls.append((sql, bound))
        invalid = {
            value
            for key, value in bound.items()
            if key.startswith("invalid_document_status_")
        }
        status_key = "documentstatus" if '"documentstatus"' in sql else "document_status"
        rows = [
            dict(row)
            for row in self.rows
            if str(row.get(status_key) or "").strip() not in invalid
        ]
        if '"documentstatus" AS "document_status"' in sql:
            for row in rows:
                row["document_status"] = row.pop("documentstatus", None)
        return Result(rows[: bound["limit_rows"]])


def _install_document_source(monkeypatch, rows, *, status_column="document_status", limit=20):
    engine = DocumentReadEngine(rows)
    columns = set(rows[0]) | set(IDENTITY) if rows else {
        *IDENTITY,
        "document_id",
        "document_title",
        "record_content",
        "record_time",
        status_column,
    }
    monkeypatch.setattr(assembly, "engine", engine)
    monkeypatch.setattr(assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *_: columns)
    monkeypatch.setattr(reader, "_source_limit", lambda _: limit)
    return engine


def _document(document_id, status, record_time):
    return {
        **{key: "SYN" for key in IDENTITY},
        "document_id": document_id,
        "document_title": "合成入院记录",
        "record_content": "同一合成正文",
        "record_time": record_time,
        "document_status": status,
    }


def _execute_sqlite_document_selection(
    *, status_column, rows, limit,
):
    columns = {
        "institute_id",
        "patient_id",
        "visit_id",
        "document_id",
        "record_time",
        status_column,
    }
    private_filter = selection._document_validity_sql_filter(
        source_table="admission_record",
        source_columns=columns,
    )
    public_filter = selection.material_document_sql_filter(
        source_schema="main",
        source_table="admission_record",
        source_columns=columns,
        institute_id="SYN",
        patient_id="patient",
        visit_id="visit",
    )
    assert public_filter == private_filter
    document_filter, document_params = public_filter
    sql = (
        f'SELECT "document_id", "{status_column}" '
        'FROM "admission_record" '
        'WHERE "institute_id"=:institute_id '
        'AND "patient_id"=:patient_id '
        'AND "visit_id"=:visit_id '
        f'{document_filter} ORDER BY "record_time" ASC LIMIT :limit_rows'
    )
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            f'CREATE TABLE "admission_record" ('
            '"institute_id" TEXT NOT NULL, '
            '"patient_id" TEXT NOT NULL, '
            '"visit_id" TEXT NOT NULL, '
            '"document_id" TEXT NOT NULL, '
            '"record_time" TEXT NOT NULL, '
            f'"{status_column}" TEXT)'
        )
        connection.executemany(
            f'INSERT INTO "admission_record" '
            f'("institute_id", "patient_id", "visit_id", "document_id", "record_time", "{status_column}") '
            'VALUES (:institute_id, :patient_id, :visit_id, :document_id, :record_time, :status)',
            [
                {
                    "institute_id": "SYN",
                    "patient_id": "patient",
                    "visit_id": "visit",
                    **row,
                }
                for row in rows
            ],
        )
        selected = connection.execute(
            sql,
            {
                "institute_id": "SYN",
                "patient_id": "patient",
                "visit_id": "visit",
                **document_params,
                "limit_rows": limit,
            },
        ).fetchall()
    finally:
        connection.close()
    return selected, sql


@pytest.mark.parametrize("status_column", ["document_status", "documentstatus"])
def test_real_sql_filters_invalid_document_before_order_and_limit(status_column):
    selected, sql = _execute_sqlite_document_selection(
        status_column=status_column,
        limit=1,
        rows=[
            {
                "document_id": "VOID-EARLY",
                "record_time": "2026-10-01 08:00:00",
                "status": "作废",
            },
            {
                "document_id": "VALID-LATE",
                "record_time": "2026-10-02 08:00:00",
                "status": "已提交",
            },
        ],
    )
    assert selected == [("VALID-LATE", "已提交")]
    assert sql.index("invalid_document_status_0") < sql.index("ORDER BY") < sql.index("LIMIT")


@pytest.mark.parametrize("status_column", ["document_status", "documentstatus"])
def test_real_sql_preserves_save_unknown_and_null_statuses(status_column):
    selected, _sql = _execute_sqlite_document_selection(
        status_column=status_column,
        limit=10,
        rows=[
            {"document_id": "SAVE", "record_time": "2026-10-01 08:00:00", "status": "Save"},
            {"document_id": "UNKNOWN", "record_time": "2026-10-02 08:00:00", "status": "待确认"},
            {"document_id": "NULL", "record_time": "2026-10-03 08:00:00", "status": None},
            {"document_id": "DELETED", "record_time": "2026-10-04 08:00:00", "status": "已删除"},
        ],
    )
    assert selected == [("SAVE", "Save"), ("UNKNOWN", "待确认"), ("NULL", None)]


@pytest.mark.parametrize("status", selection.EXPLICITLY_INVALID_DOCUMENT_STATUSES)
def test_only_frozen_exact_document_statuses_are_invalid(status):
    assert selection.is_explicitly_invalid_document_status(status)


@pytest.mark.parametrize("status", [None, "", "Save", "已提交", "待确认", "作废待核", "草稿"])
def test_save_blank_and_unknown_document_statuses_keep_previous_behavior(status):
    assert not selection.is_explicitly_invalid_document_status(status)


def test_bundle_and_snapshot_choose_valid_row_when_body_is_identical(monkeypatch):
    rows = [
        _document("VOID-EARLY", "作废", "2026-10-01 08:00:00"),
        _document("VALID-LATE", "已提交", "2026-10-02 08:00:00"),
    ]
    engine = _install_document_source(monkeypatch, rows, limit=1)

    bundle_rows = assembly._select_records(
        schema="cdm", table="admission_record", limit=1,
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )
    snapshot = reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record", source_schema="cdm",
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )

    assert [row["document_id"] for row in bundle_rows] == ["VALID-LATE"]
    assert [row["document_id"] for row in snapshot.rows] == ["VALID-LATE"]
    assert snapshot.rows[0]["document_status"] == "已提交"
    inventory = assembly._build_document_inventory(
        {"admission_record": bundle_rows},
        "cdm",
    )
    assert inventory[0]["document_status"] == "已提交"
    assert not snapshot.truncated
    for sql, params in engine.calls:
        assert sql.index("invalid_document_status_0") < sql.index("LIMIT")
        assert params["invalid_document_status_0"] == "作废"


def test_controlled_source_whitelists_preserve_document_validity_field():
    for source_key in ("admission_record", "daily_course_record", "bloodtrans_record"):
        assert "document_status" in reader._NATIVE_SOURCE_FIELDS[source_key]
        assert "document_status" in reader._SNAPSHOT_SOURCE_FIELDS[source_key]


def test_sync_normalization_preserves_explicit_invalid_status_and_alias():
    for raw in ({"document_status": "已作废"}, {"documentstatus": "已撤销"}):
        normalized, issues = dual_source_sync.normalize_row(raw)
        assert normalized["document_status"] in {"已作废", "已撤销"}
        assert not issues


def test_only_invalid_document_produces_complete_empty_selection(monkeypatch):
    rows = [_document("VOID", "已作废", "2026-10-01 08:00:00")]
    _install_document_source(monkeypatch, rows, limit=1)

    assert assembly._select_records(
        schema="cdm", table="admission_record", limit=1,
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    ) == []
    snapshot = reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record", source_schema="cdm",
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )
    assert snapshot.rows == ()
    assert not snapshot.truncated


def test_save_unknown_and_blank_status_rows_are_not_filtered(monkeypatch):
    rows = [
        _document("SAVE", "Save", "2026-10-01 08:00:00"),
        _document("UNKNOWN", "待确认", "2026-10-02 08:00:00"),
        _document("BLANK", "", "2026-10-03 08:00:00"),
    ]
    _install_document_source(monkeypatch, rows, limit=3)

    snapshot = reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record", source_schema="cdm",
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )
    assert [row["document_id"] for row in snapshot.rows] == ["SAVE", "UNKNOWN", "BLANK"]


def test_missing_document_status_column_is_backward_compatible(monkeypatch):
    row = _document("LEGACY", None, "2026-10-01 08:00:00")
    row.pop("document_status")
    engine = _install_document_source(monkeypatch, [row], limit=1)

    snapshot = reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record", source_schema="cdm",
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )
    assert [item["document_id"] for item in snapshot.rows] == ["LEGACY"]
    assert all("invalid_document_status_" not in sql for sql, _ in engine.calls)


def test_documentstatus_alias_is_filtered_and_projected_as_canonical(monkeypatch):
    rows = [
        {**_document("ALIAS-VOID", None, "2026-10-01 08:00:00"), "documentstatus": "撤销"},
        {**_document("ALIAS-SAVE", None, "2026-10-02 08:00:00"), "documentstatus": "Save"},
    ]
    for row in rows:
        row.pop("document_status")
    engine = _install_document_source(monkeypatch, rows, status_column="documentstatus", limit=2)

    snapshot = reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record", source_schema="cdm",
        institute_id="SYN", patient_id="SYN", visit_id="SYN",
    )
    assert [item["document_id"] for item in snapshot.rows] == ["ALIAS-SAVE"]
    assert snapshot.rows[0]["document_status"] == "Save"
    assert '"documentstatus" AS "document_status"' in engine.calls[0][0]


def test_non_document_table_does_not_reuse_document_status_semantics():
    sql, params = selection.material_document_sql_filter(
        source_schema="cdm",
        source_table="inpat_nondrug_order",
        source_columns={"document_status", "order_id"},
        institute_id="SYN",
        patient_id="SYN",
        visit_id="SYN",
    )
    assert sql == ""
    assert params == {}


@pytest.mark.parametrize("kind", ["domain", "scene"])
def test_bundle_v6_cache_is_rebuilt_for_document_selection_v7(monkeypatch, kind):
    identity = {**IDENTITY, "patient_id": "patient", "visit_id": "visit"}
    stale = {"bundle_schema_version": "bundle-v6", "stale_selection": True}
    fresh = {
        "bundle_schema_version": assembly.BUNDLE_SCHEMA_VERSION_CURRENT,
        "stale_selection": False,
    }
    load = Mock(return_value=stale)
    build = Mock(return_value=fresh)
    save = Mock()
    monkeypatch.setattr(assembly, "ensure_" + kind + "_bundle_tables", Mock())
    monkeypatch.setattr(
        assembly,
        "load_domain_bundle" if kind == "domain" else "_load_scene_bundle",
        load,
    )
    monkeypatch.setattr(
        assembly,
        "assemble_domain_bundle" if kind == "domain" else "_assemble_scene_bundle",
        build,
    )
    monkeypatch.setattr(assembly, "_upsert_" + kind + "_bundle", save)
    args = {"execution_domain": "course"} if kind == "domain" else {"scene": "running"}

    result = getattr(assembly, "load_or_assemble_" + kind + "_bundle")(
        **identity,
        **args,
    )

    assert result == fresh
    load.assert_called_once()
    build.assert_called_once()
    save.assert_called_once()


@pytest.mark.parametrize("kind", ["domain", "scene"])
@pytest.mark.parametrize("copy", [True, False])
def test_new_copy_task_does_not_reuse_old_bundle_but_normal_case_keeps_cache(monkeypatch, kind, copy):
    identity = IDENTITY if copy else {**IDENTITY, "patient_id": "patient", "visit_id": "visit"}
    old = {"bundle_schema_version": assembly.BUNDLE_SCHEMA_VERSION_CURRENT}
    fresh = {"fresh_materials": True}
    load, build, save = Mock(return_value=old), Mock(return_value=fresh), Mock()
    monkeypatch.setattr(assembly, "ensure_" + kind + "_bundle_tables", Mock())
    monkeypatch.setattr(assembly, "load_domain_bundle" if kind == "domain" else "_load_scene_bundle", load)
    monkeypatch.setattr(assembly, "assemble_domain_bundle" if kind == "domain" else "_assemble_scene_bundle", build)
    monkeypatch.setattr(assembly, "_upsert_" + kind + "_bundle", save)
    args = {"execution_domain": "course"} if kind == "domain" else {"scene": "running", "force_refresh_if_empty": False}
    result = getattr(assembly, "load_or_assemble_" + kind + "_bundle")(**identity, **args)
    assert result == (fresh if copy else old)
    assert build.call_count == save.call_count == int(copy)
    assert load.call_count == int(not copy)
