"""接入差量：owned PG16、合成双库、禁网禁模型；不采集真实材料。"""
import pytest
import sqlalchemy as sa
from test_dual_source_acceptance_pg16 import db as db, dual_factory as dual_factory, no_models as no_models
from joint_pg_support import ISOLATION_ACTIVE

pytestmark = pytest.mark.skipif(not ISOLATION_ACTIVE, reason="owned PG16 guard required")
MISSING = ("admission_record_diagnosis", "discharge_record_diagnosis", "exam_item", "exam_master",
           "first_course_record_diagnosis", "inpat_prescription", "inpat_prescription_item",
           "medical_order", "mr_diagnosis", "physician_change_event")


def make(dual_factory, mode="normal"):
    def seed(business, owner, schema, identity):
        with owner.begin() as c:
            for name in MISSING:
                c.execute(sa.text(f'DROP TABLE IF EXISTS cdm."{name}" CASCADE'))
            if mode == "columns":
                from app.services.clinical_source_contract import read_columns
                columns = {x["name"] for x in sa.inspect(c).get_columns("newborn_record", schema="cdm")}
                _, selected = read_columns("newborn_record", columns)
                c.execute(sa.text("ALTER TABLE cdm.newborn_record ADD COLUMN private_unused text"))
                c.execute(sa.text("REVOKE SELECT ON cdm.newborn_record FROM medqc_job_worker"))
                names = ",".join('"' + s + '"' for s in sorted(selected))
                c.execute(sa.text(f"GRANT SELECT ({names}) ON cdm.newborn_record TO medqc_job_worker"))
            if mode == "denied":
                c.execute(sa.text("REVOKE SELECT ON cdm.daily_course_record FROM medqc_job_worker"))
            if mode == "missing":
                c.execute(sa.text("ALTER TABLE cdm.daily_course_record DROP COLUMN record_content"))
            if mode == "column_write":
                c.execute(sa.text("GRANT UPDATE(record_content) ON cdm.daily_course_record TO medqc_job_worker"))
    return dual_factory("split", extra_seed=seed)


@pytest.mark.parametrize("mode,status", [("normal",None),("columns",None),("denied","select_denied"),
                                         ("missing","columns_missing"),("column_write","write_privilege_forbidden")])
def test_real_permissions_optional_and_errors(dual_factory, mode, status):
    from app.services.clinical_source_contract import inspect_source
    d = make(dual_factory, mode)
    with d["readonly"].connect() as c:
        assert int(c.execute(sa.text("SHOW server_version_num")).scalar_one()) // 10000 == 16
        report = inspect_source(c)
    rows = {x["table"]: x for x in report["dependencies"]}
    assert all(rows[n]["status"] == "table_missing" and not rows[n]["required"] for n in MISSING)
    if status:
        assert not report["ok"] and rows["daily_course_record"]["status"] == status
    else:
        assert report["ok"], report
        assert rows["newborn_record"]["status"] == "zero_rows"
        assert "private_unused" not in rows["newborn_record"].get("read_columns", [])
        from app.services.bundles import assembly
        from app.services.luxian_0609 import source_evidence_reader as reader
        keys = dict(zip(("institute_id", "patient_id", "visit_id"), d["identity"]))
        for name in MISSING:
            assert assembly._select_records(schema="cdm", table=name, **keys) == []
            if name in reader._SNAPSHOT_SOURCE_FIELDS:
                try:
                    observed = reader.read_luxian_0609_snapshot_source_rows(source_key=name, source_schema="cdm", **keys)
                    assert observed.source_key == name
                except reader.SourceEvidenceUnavailable:
                    pass  # Explicit unavailable is valid; raw undefined-table/query errors are not.



def test_directory_real_default_loader_and_export_without_optional_children(dual_factory, monkeypatch):
    from app.database import connection
    from app.services import clinical_case_catalog as catalog
    d = make(dual_factory)
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(connection, "SessionLocal", sessionmaker(bind=d["business"]))
    from app.services.medical_records import query_service, export_service
    # Prove the actual default adapter supplies the business factory; no replacement of catalog loader.
    factory = lambda: None
    monkeypatch.setattr(connection, "SessionLocal", factory)
    seen = []
    def summaries(refs, *, session_factory):
        seen.append((refs, session_factory)); return {}
    monkeypatch.setattr(query_service, "_load_latest_luxian_0609_qc_summaries", summaries)
    result = catalog.workstation()
    assert result["total"] > 0 and seen[0][1] is factory
    # Any legacy engine use is an immediate failure, including missing-child diagnostic fallback.
    monkeypatch.setattr(export_service, "engine", None)
    institute, patient, visit = d["identity"]
    result = export_service.get_frontpage_sheet(patient, visit, institute_id=institute)
    assert result["basic"]["institute_id"] == institute
    assert result["diagnosis_source"] == "diagnosis"
    with pytest.raises(Exception):
        export_service.get_frontpage_sheet(patient, visit, institute_id="wrong-institute")
