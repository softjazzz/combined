"""同一已复核选择必须在Bundle/规则的LIMIT前生效，且不改变原始行。"""
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import Mock

import pytest

from app.database import connection as db
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
        if "parent_ids" in params:
            return Result([row["document_id"] for row in self.rows if row["document_id"] in params["parent_ids"]])
        rows = [row for row in self.rows if row["document_id"] not in params.get("material_excluded_ids", [])]
        return Result(rows[:params["limit_rows"]])


@pytest.fixture
def source(monkeypatch):
    rows = [dict(document_id=id_, document_title="合成文书", record_content="合成正文",
                 record_time="2026-10-01 08:00:00") for id_ in ("PDF", "PG", "UNIQUE")]
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
            assert params["material_excluded_ids"] == ["PDF"]
        assert IDENTITY["patient_id"] in params.values()
        assert IDENTITY["visit_id"] in params.values()
        assert IDENTITY["institute_id"] in params.values()
    assert source.rows == before


def test_missing_original_preserves_pdf_and_independent_document(source):
    source.rows = [row for row in source.rows if row["document_id"] != "PG"]
    result = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema=SCHEMA, **IDENTITY)
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
