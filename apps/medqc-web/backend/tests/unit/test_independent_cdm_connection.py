"""双库路由、缓存归属和错误边界；仅虚构数据和fake连接。"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.database import clinical_connection as clinical
from app.services.bundles import assembly
from app.services import case_material_snapshot as material
from app.services.luxian_0609 import source_evidence_reader as reader

IDENTITY = dict(institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V")
URL = "postgresql+psycopg2://reader@localhost:62994/synthetic_cdm"


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    monkeypatch.delenv("CDM_DATABASE_URL", raising=False)
    monkeypatch.delenv("CDM_PGPASSFILE", raising=False)
    clinical._engine.cache_clear()
    assembly._columns_for_engine.cache_clear()
    yield
    clinical._engine.cache_clear()
    assembly._columns_for_engine.cache_clear()


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeEngine:
    def __init__(self, rows=(), *, readonly=False):
        self.rows, self.readonly, self.calls = list(rows), readonly, []

    @contextmanager
    def connect(self):
        yield self

    @contextmanager
    def begin(self):
        assert not self.readonly, "write reached CDM"
        yield self

    def execute(self, statement, params=None):
        sql = str(statement)
        if self.readonly:
            assert sql.lstrip().upper().startswith("SELECT")
        self.calls.append((sql, params))
        return Result(self.rows)


def install(monkeypatch):
    business = FakeEngine([{"document_id": "BUSINESS", "record_content": "old content"}])
    cdm = FakeEngine([{"document_id": "CDM", "record_content": "new content"} for _ in range(1)], readonly=True)
    monkeypatch.setenv("CDM_DATABASE_URL", URL)
    monkeypatch.setattr(clinical, "get_engine", lambda: cdm)
    monkeypatch.setattr(assembly, "engine", business)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *_: tuple(IDENTITY) + ("document_id", "record_content"))
    return business, cdm


def test_unconfigured_mode_preserves_business_connection(monkeypatch):
    business = object()
    monkeypatch.setattr(assembly, "engine", business)
    assert assembly._source_engine("public") is business
    assert clinical.get_engine() is None


def test_factory_uses_readonly_options_and_never_changes_business_engine(monkeypatch):
    from app.database import connection
    original = connection.engine, connection.SessionLocal
    calls = []
    fake = object()
    monkeypatch.setattr(clinical, "create_engine", lambda url, **kw: calls.append((url, kw)) or fake)
    monkeypatch.setenv("CDM_DATABASE_URL", URL)
    assert clinical.get_engine() is fake
    assert clinical.get_engine() is fake and len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs["connect_args"]["options"] == "-c default_transaction_read_only=on"
    assert kwargs["echo"] is False and kwargs["hide_parameters"] is True
    assert (connection.engine, connection.SessionLocal) == original


@pytest.mark.parametrize("url", ["sqlite:///private", "not_a_url", "postgresql://reader@host/", URL + "?options=-cdefault_transaction_read_only=off", URL + "?host=other"])
def test_invalid_or_connection_overriding_configuration_is_sanitized(monkeypatch, url):
    monkeypatch.setenv("CDM_DATABASE_URL", url)
    with pytest.raises(clinical.ClinicalSourceConfigurationError) as caught:
        clinical.get_engine()
    assert str(caught.value) == "invalid_independent_cdm_configuration"


def test_orphan_passfile_is_not_silent_single_database_fallback(monkeypatch):
    monkeypatch.setenv("CDM_PGPASSFILE", "/private/passfile")
    assert clinical.configured()
    with pytest.raises(clinical.ClinicalSourceConfigurationError):
        assembly._source_engine("cdm")


def test_passfile_is_passed_by_path_and_not_in_source_cache_binding(monkeypatch, tmp_path):
    secret = tmp_path / "runtime.pgpass"
    secret.write_text("fictional-content", encoding="utf-8")
    secret.chmod(0o600)
    captured = []
    monkeypatch.setenv("CDM_DATABASE_URL", URL)
    monkeypatch.setenv("CDM_PGPASSFILE", str(secret))
    monkeypatch.setattr(clinical, "create_engine", lambda *a, **kw: captured.append(kw) or object())
    clinical.get_engine()
    assert captured[0]["connect_args"]["passfile"] == str(secret)
    assert str(secret) not in clinical.source_binding() and "fictional-content" not in str(captured)


def test_bundle_and_formal_rule_sources_read_new_cdm_and_keep_three_keys(monkeypatch):
    business, cdm = install(monkeypatch)
    assert assembly._default_source_schema() == "cdm"
    rows = assembly._select_records(schema="cdm", table="daily_course_record", **IDENTITY)
    formal = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema="cdm", **IDENTITY)
    assert rows[0]["document_id"] == formal.rows[0]["document_id"] == "CDM"
    assert not business.calls and len(cdm.calls) == 2
    for sql, params in cdm.calls:
        assert all(params[k] == value for k, value in IDENTITY.items())
        assert all(f'"{k}" = :{k}' in sql for k in IDENTITY)


def test_failed_cdm_does_not_read_lookalike_business_clinical_table(monkeypatch):
    business, cdm = install(monkeypatch)
    def failed(*_):
        raise RuntimeError("private-dsn-or-driver-error")
    monkeypatch.setattr(cdm, "execute", failed)
    with pytest.raises(reader.SourceEvidenceQueryError):
        reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema="cdm", **IDENTITY)
    assert not business.calls


def test_external_schema_cannot_be_selected_arbitrarily_and_pdf_keeps_business_route(monkeypatch):
    business, cdm = install(monkeypatch)
    assert assembly._source_engine("pdfmat_012345abcdef") is business
    with pytest.raises(ValueError, match="untrusted_independent_cdm_schema"):
        assembly._source_engine("public")
    assert not business.calls and not cdm.calls


def test_ordinary_case_cannot_use_pdf_schema_as_business_database_escape(monkeypatch):
    business, cdm = install(monkeypatch)
    with pytest.raises(ValueError, match="untrusted_clinical_source_schema"):
        assembly.assemble_domain_bundle(execution_domain="admission", source_schema="pdfmat_012345abcdef", **IDENTITY)
    assert not business.calls and not cdm.calls


def test_independent_source_disallows_visit_only_cross_institute_lookup(monkeypatch):
    business, cdm = install(monkeypatch)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *_: ("visit_id", "record_content"))
    with pytest.raises(ValueError, match="independent_cdm_visit_keys_missing"):
        assembly._select_records(schema="cdm", table="daily_course_record", **IDENTITY)
    assert not business.calls and not cdm.calls


def test_bundle_persistence_and_task_store_keep_business_connection(monkeypatch):
    business, cdm = install(monkeypatch)
    monkeypatch.setattr(assembly, "ensure_domain_bundle_tables", lambda **_: None)
    assembly._upsert_domain_bundle(execution_domain="admission", bundle={**IDENTITY, "structured_context": {}}, bundle_schema="public")
    assert business.calls and "INSERT INTO" in business.calls[0][0]
    assert not cdm.calls


def test_external_bundle_assembly_can_read_without_any_business_database(monkeypatch):
    _, cdm = install(monkeypatch)
    monkeypatch.setattr(assembly, "engine", None)
    bundle = assembly.assemble_domain_bundle(execution_domain="admission", source_schema="cdm", **IDENTITY)
    assert bundle["structured_context"]["clinical_source_binding"] == clinical.source_binding()
    assert bundle["structured_context"]["documents"]["admission_record"][0]["document_id"] == "CDM"
    assert cdm.calls


@pytest.mark.parametrize("loader,extra", [
    ("load_domain_bundle", {}),
    ("load_domain_bundle_document_index", {}),
    ("load_domain_bundle_for_emr_render", {"doc_type": "admission_record", "doc_id": "D"}),
])
def test_cdm_cache_needs_both_source_binding_and_fixed_material(monkeypatch, loader, extra):
    business, cdm = install(monkeypatch)
    business.rows = [{**IDENTITY, "structured_context": {}, "source_documents": []}]
    method = getattr(assembly, loader)
    assert method(execution_domain="admission", **IDENTITY, **extra) is None
    binding = clinical.source_binding()
    business.rows[0].update(structured_context={"clinical_source_binding": binding}, clinical_source_binding=binding)
    assert method(execution_domain="admission", **IDENTITY, **extra) is None
    business.rows[0]["structured_context"]["case_material_fingerprint"] = "fixed-content"
    business.rows[0]["case_material_fingerprint"] = "fixed-content"
    context = {"identity": [IDENTITY[key] for key in ("institute_id", "patient_id", "visit_id")], "binding": binding}
    with material.activate({**context, "fingerprint": "different-content"}):
        assert method(execution_domain="admission", **IDENTITY, **extra) is None
    with material.activate({**context, "fingerprint": "fixed-content"}):
        assert method(execution_domain="admission", **IDENTITY, **extra) is not None
    for mismatch in ({"identity": ["OTHER", "P", "V"]}, {"binding": "other-source"}):
        with material.activate({**context, "fingerprint": "fixed-content", **mismatch}):
            with pytest.raises(material.MaterialSnapshotError, match="material_identity_or_source_mismatch"):
                method(execution_domain="admission", **IDENTITY, **extra)
    assert not cdm.calls


def test_cache_binding_changes_by_database_not_password_and_is_not_used_for_pdf(monkeypatch):
    monkeypatch.setenv("CDM_DATABASE_URL", URL)
    one = clinical.source_binding()
    monkeypatch.setenv("CDM_DATABASE_URL", URL.replace('reader@', 'reader:secret@'))
    assert clinical.source_binding() == one
    monkeypatch.setenv("CDM_DATABASE_URL", URL + "_other")
    assert clinical.source_binding() != one
    assert assembly._cache_binding("pdfp_case", "pdfv_visit") == ""


def test_reflection_cache_is_partitioned_by_connection(monkeypatch):
    first, second = object(), object()
    active = [first]
    monkeypatch.setattr(assembly, "_source_engine", lambda _: active[0])
    monkeypatch.setattr(assembly, "inspect", lambda engine: SimpleNamespace(
        has_table=lambda **_: True, get_columns=lambda **_: [{"name": "first" if engine is first else "second"}],
    ))
    assert assembly._get_table_columns("cdm", "mr") == ("first",)
    active[0] = second
    assert assembly._get_table_columns("cdm", "mr") == ("second",)


def test_scene_cache_is_bound_to_cdm_and_rejected_after_rolling_back_to_single_database(monkeypatch):
    business, _ = install(monkeypatch)
    business.rows = [{**IDENTITY, "structured_context": {}, "document_hits": {}}]
    args = dict(scene="running", schema="public", **IDENTITY)
    assert assembly._load_scene_bundle(**args) is None
    business.rows[0]["structured_context"]["clinical_source_binding"] = clinical.source_binding()
    assert assembly._load_scene_bundle(**args) is None
    business.rows[0]["structured_context"]["case_material_fingerprint"] = "fixed-content"
    with material.activate({"fingerprint": "different-content"}):
        assert assembly._load_scene_bundle(**args) is None
    with material.activate({"fingerprint": "fixed-content"}):
        assert assembly._load_scene_bundle(**args) is not None
    monkeypatch.delenv("CDM_DATABASE_URL")
    assert assembly._load_scene_bundle(**args) is None


@pytest.mark.parametrize("loader", ["load_frontpage_payload_from_bundle", "load_coding_payload_from_bundle", "load_settlement_payload_from_bundle"])
def test_legacy_payload_readers_cannot_return_other_source_cached_data(monkeypatch, loader):
    business, _ = install(monkeypatch)
    context = {"frontpage_coding": {"frontpage_formal_payload": {"synthetic": True},
                                    "coding_payload": {"synthetic": True}},
               "settlement_payload": {"synthetic": True}}
    business.rows = [{"structured_context": context}]
    assert getattr(assembly, loader)(**IDENTITY) is None
    context["clinical_source_binding"] = clinical.source_binding()
    assert getattr(assembly, loader)(**IDENTITY) is None
    context["case_material_fingerprint"] = "fixed-content"
    with material.activate({"fingerprint": "different-content"}):
        assert getattr(assembly, loader)(**IDENTITY) is None
    with material.activate({"fingerprint": "fixed-content"}):
        assert getattr(assembly, loader)(**IDENTITY) is not None
