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
            if mode in {"owner_direct", "owner_set_role", "owner_inherited", "owner_set_inherited"}:
                from joint_pg_support import connect
                from contextlib import closing
                with closing(connect(owner.url.database)) as admin:
                    admin.autocommit = True
                    with admin.cursor() as cursor:
                        holder = "medqc_job_worker" if mode == "owner_direct" else "medqc_job_api"
                        cursor.execute(f"ALTER TABLE cdm.daily_course_record OWNER TO {holder}")
                        cursor.execute(f"REVOKE ALL ON cdm.daily_course_record FROM {holder}")
                        cursor.execute(f"GRANT SELECT ON cdm.daily_course_record TO {holder}")
                        cursor.execute("GRANT SELECT ON cdm.daily_course_record TO medqc_owner")
                        if mode == "owner_set_role":
                            cursor.execute("GRANT medqc_job_api TO medqc_job_worker WITH INHERIT FALSE, SET TRUE")
                        elif mode == "owner_inherited":
                            cursor.execute("GRANT medqc_job_api TO medqc_job_worker WITH INHERIT TRUE, SET FALSE")
                        elif mode == "owner_set_inherited":
                            cursor.execute("CREATE ROLE medqc_cdm_switch_probe NOLOGIN")
                            cursor.execute("GRANT medqc_cdm_switch_probe TO medqc_job_worker WITH INHERIT FALSE, SET TRUE")
                            cursor.execute("GRANT medqc_job_api TO medqc_cdm_switch_probe WITH INHERIT TRUE, SET FALSE")
            if mode.startswith("patient_"):
                c.execute(sa.text("REVOKE SELECT ON cdm.patient_information FROM medqc_job_worker"))
                columns = "institute_id" if mode == "patient_denied" else "institute_id,patient_id"
                c.execute(sa.text(f"GRANT SELECT ({columns}) ON cdm.patient_information TO medqc_job_worker"))
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


@pytest.mark.parametrize("mode", ["patient_minimal", "patient_denied"])
def test_patient_information_minimal_projection(dual_factory, mode):
    from app.services.clinical_source_contract import inspect_source, read_columns
    from app.services.bundles import assembly
    d = make(dual_factory, mode)
    with d["readonly"].connect() as c:
        report = inspect_source(c)
    row = next(x for x in report["dependencies"] if x["table"] == "patient_information")
    assert row["read_columns"] == ["institute_id", "patient_id"]
    if mode == "patient_denied":
        assert not report["ok"] and row["status"] == "select_denied"
        assert row["denied_columns"] == ["patient_id"]
    else:
        assert report["ok"], report
        # Same actual consumer branch as capture: no visit_id means no source SQL at all.
        assert assembly._select_records(schema="cdm", table="patient_information",
            **dict(zip(("institute_id", "patient_id", "visit_id"), d["identity"]))) == []
    # Future three-key shape must not inherit a permanent permission exemption.
    required, selected = read_columns("patient_information", {"institute_id", "patient_id", "visit_id", "record_content"})
    assert "record_content" in selected and "visit_id" in selected


@pytest.mark.parametrize("mode", ["owner_direct", "owner_set_role", "owner_inherited", "owner_set_inherited"])
def test_readonly_owner_without_acl_writes_is_rejected(dual_factory, mode):
    from app.services.clinical_source_contract import inspect_source
    from joint_pg_support import connect
    from contextlib import closing
    d = None
    try:
        d = make(dual_factory, mode)
        with d["readonly"].connect() as c:
            assert not c.execute(sa.text("SELECT has_table_privilege(current_user,'cdm.daily_course_record','UPDATE')")).scalar_one()
            if mode == "owner_inherited":
                assert not c.execute(sa.text("SELECT pg_has_role(current_user,'medqc_job_api','SET')")).scalar_one()
                assert c.execute(sa.text("SELECT pg_has_role(current_user,'medqc_job_api','USAGE')")).scalar_one()
            if mode == "owner_set_inherited":
                assert not c.execute(sa.text("SELECT pg_has_role(current_user,'medqc_job_api','SET')")).scalar_one()
                assert not c.execute(sa.text("SELECT pg_has_role(current_user,'medqc_job_api','USAGE')")).scalar_one()
                assert c.execute(sa.text("SELECT pg_has_role(current_user,'medqc_cdm_switch_probe','SET')")).scalar_one()
                assert c.execute(sa.text("SELECT pg_has_role('medqc_cdm_switch_probe','medqc_job_api','USAGE')")).scalar_one()
            report = inspect_source(c)
        row = next(x for x in report["dependencies"] if x["table"] == "daily_course_record")
        assert row["owns_object"] and row["status"] == "object_ownership_forbidden"
        assert not report["ok"] and not report["account_read_only"]
    finally:
        if mode in {"owner_set_role", "owner_inherited", "owner_set_inherited"}:
            with closing(connect()) as admin:
                admin.autocommit = True
                with admin.cursor() as cursor:
                    if mode == "owner_set_inherited":
                        cursor.execute("DROP ROLE medqc_cdm_switch_probe")
                    else:
                        cursor.execute("REVOKE medqc_job_api FROM medqc_job_worker")
