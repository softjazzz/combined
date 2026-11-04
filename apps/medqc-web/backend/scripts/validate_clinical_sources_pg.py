"""新建一次性原生PG双库验收；不复用任何既有集群、配置或患者材料。

--source-backend 指向独立同步服务交付的正式060迁移/初始化源码。
产物与集群保留供复核，退出时只停止本脚本新建且身份已核实的PG。
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

import dotenv
import psycopg2
from psycopg2.extensions import parse_dsn
import sqlalchemy as sa

BACKEND = Path(__file__).resolve().parents[1]


def denied(*args, **kwargs):
    raise RuntimeError("synthetic_dual_database_network_denied")


def bootstrap(source: Path, url: str, passfile: Path):
    """在独立进程中加载正式同步迁移，拒绝读取它旁边的.env。"""
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location("synthetic_cdm_bootstrap", source / "scripts/bootstrap_cache_sync_database.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parsed = sa.engine.make_url(url)
    real_connect = psycopg2.connect
    def connect(dsn=None, **kwargs):
        values = {**(parse_dsn(dsn) if dsn else {}), **kwargs}
        assert values.get("host") == "127.0.0.1" and int(values.get("port", 0)) == parsed.port
        assert values.get("dbname") == parsed.database
        return real_connect(dsn, **kwargs)
    with patch.object(dotenv, "load_dotenv", return_value=False), patch.object(psycopg2, "connect", connect), patch.object(socket.socket, "connect", denied), patch.dict(os.environ, {
        "DATABASE_URL": "", "MEDQC_BOOTSTRAP_DATABASE_URL": url, "PGPASSFILE": str(passfile),
        "PGPASSWORD": "", "DB_SCHEMA_MODE": "split", "REMOTE_DB_URL": "",
    }):
        return module.initialize(parsed.database, owner_role="synthetic_cdm_owner")


def run(args):
    directory = args.output_dir.resolve()
    if directory.exists():
        raise RuntimeError("fresh_output_directory_required")
    if args.port < 60000 or args.port > 65000:
        raise RuntimeError("dedicated_synthetic_port_required")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    directory.mkdir(parents=True)
    cluster = directory / "data"
    cluster_name = "medqc_dual_sources_synthetic"
    pg = args.pg_bin.resolve()
    logs = directory / "commands.log"
    def command(name, *arguments, env=None):
        with logs.open("ab") as output:
            subprocess.run([str(pg / (name + (".exe" if os.name == "nt" else ""))), *map(str, arguments)],
                           stdout=output, stderr=output, check=True, env=env,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    command("initdb", "-D", cluster, "-U", "postgres", "--auth=trust", "--encoding=UTF8", "--no-locale")
    with (cluster / "postgresql.conf").open("a", encoding="utf-8", newline="\n") as file:
        file.write(f"\nport={args.port}\nlisten_addresses='127.0.0.1'\ncluster_name='{cluster_name}'\nshared_buffers='16MB'\nmax_connections=16\njit=off\n")
    command("pg_ctl", "-D", cluster, "-l", directory / "postgres.log", "-w", "start")
    engines = []
    try:
        admin = psycopg2.connect(host="127.0.0.1", port=args.port, user="postgres", dbname="postgres")
        with admin.cursor() as cursor:
            cursor.execute("SELECT current_setting('cluster_name'), current_setting('data_directory')")
            name, actual_directory = cursor.fetchone()
            assert name == cluster_name and Path(actual_directory).resolve() == cluster
        admin.rollback()
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute("CREATE ROLE synthetic_cdm_owner NOLOGIN")
            cursor.execute("CREATE ROLE synthetic_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
            cursor.execute("CREATE DATABASE synthetic_cdm OWNER synthetic_cdm_owner")
            cursor.execute("CREATE DATABASE synthetic_business")
        admin.close()
        url = f"postgresql+psycopg2://postgres@127.0.0.1:{args.port}/synthetic_cdm"
        passfile = directory / "synthetic.pgpass"
        passfile.write_text(f"127.0.0.1:{args.port}:*:synthetic_reader:synthetic-only\n127.0.0.1:{args.port}:*:postgres:synthetic-only\n", encoding="utf-8")
        passfile.chmod(0o600)
        # 使用正式同步060迁移，不把同步分支迁移移入业务062链。
        environment = {key: value for key, value in os.environ.items() if not any(part in key.upper() for part in ("DATABASE", "DSN", "API_KEY", "PGPASS", "CDM_", "PYTHONPATH"))}
        with logs.open("ab") as output:
            subprocess.run([sys.executable, "-B", __file__, "--bootstrap-source", str(args.source_backend.resolve()),
                "--bootstrap-url", url, "--bootstrap-passfile", str(passfile)], check=True, env=environment,
                stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        # 相同临床结构镜像到一次性业务库，只为构造同键不同内容；不导出任何现存数据。
        schema_file = directory / "synthetic-schema.sql"
        command("pg_dump", "-h", "127.0.0.1", "-p", args.port, "-U", "postgres", "-d", "synthetic_cdm",
                "--schema-only", "--schema=cdm", "--no-owner", "--no-privileges", "-f", schema_file)
        command("psql", "-X", "-h", "127.0.0.1", "-p", args.port, "-U", "postgres", "-d", "synthetic_business",
                "--set=ON_ERROR_STOP=1", "-f", schema_file)
        source = sa.create_engine(url)
        business = sa.create_engine(url.replace("synthetic_cdm", "synthetic_business"), connect_args={"options": "-csearch_path=public,qc,sys,cdm"})
        engines.extend([source, business])
        for engine, marker in ((source, "SYNTHETIC-CDM"), (business, "SYNTHETIC-LEGACY")):
            with engine.begin() as connection:
                connection.execute(sa.text("INSERT INTO cdm.mr(institute_id,patient_id,visit_id,name,admission_datetime,attending_physician_sign,admission_dept_name,record_content) VALUES('I','P','V',:name,'2026-10-01 08:00','合成医生','合成科室',:name)"), {"name": marker})
                connection.execute(sa.text("INSERT INTO cdm.admission_record(institute_id,patient_id,visit_id,document_id,name,admission_datetime,record_datetime,record_content) VALUES('I','P','V','D',:name,'2026-10-01 08:00','2026-10-01 09:00',:name)"), {"name": marker})
                connection.execute(sa.text("INSERT INTO cdm.diagnosis(institute_id,patient_id,visit_id,diagnosis_id,diagnosis_type,diagnosis_no,diagnosis_name,diagnosis_code) VALUES('I','P','V','DX','出院主要诊断','1',:name,'SYNTHETIC')"), {"name": marker})
                connection.execute(sa.text("INSERT INTO cdm.daily_course_record(institute_id,patient_id,visit_id,document_id,record_content,record_datetime,submit_datetime) VALUES('I','P','V','D',:name,'2026-10-02 09:00','2026-10-02 10:00')"), {"name": marker})
        with source.begin() as connection:
            connection.execute(sa.text("INSERT INTO cdm.inpat_registration(institute_id,patient_id,visit_id,name,admission_datetime) VALUES('I','P2','V2','SYNTHETIC-NO-FRONTPAGE','2026-10-03 08:00')"))
            connection.execute(sa.text("INSERT INTO cdm.discharge_record(institute_id,patient_id,visit_id,document_id,discharge_time,record_content) VALUES('I','P','V','EXIT','2026-10-04 11:00','SYNTHETIC-DISCHARGE')"))
            connection.execute(sa.text("GRANT CONNECT ON DATABASE synthetic_cdm TO synthetic_reader"))
            connection.execute(sa.text("GRANT USAGE ON SCHEMA cdm TO synthetic_reader"))
            connection.execute(sa.text("GRANT SELECT ON ALL TABLES IN SCHEMA cdm TO synthetic_reader"))
        def fingerprint():
            with source.connect() as connection:
                tables = sa.inspect(connection).get_table_names(schema="cdm")
                columns = connection.execute(sa.text("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='cdm' ORDER BY table_name,ordinal_position")).all()
                values = [(table, connection.execute(sa.text(f'SELECT md5(coalesce(string_agg(row_to_json(t)::text,\'|\' ORDER BY row_to_json(t)::text),\'\')) FROM cdm."{table}" t')).scalar_one()) for table in tables]
                return hashlib.sha256(repr((columns, values)).encode()).hexdigest(), len(tables)
        before, table_count = fingerprint()
        sys.path.insert(0, str(BACKEND))
        with ExitStack() as stack:
            stack.enter_context(patch.object(dotenv, "load_dotenv", return_value=False))
            stack.enter_context(patch.dict(os.environ, {"DATABASE_URL": "", "DB_SCHEMA_MODE": "split", "CDM_DATABASE_URL": "", "CDM_PGPASSFILE": str(passfile), "MEDQC_ALLOW_REAL_LLM": "0"}))
            stack.enter_context(patch.object(socket.socket, "connect", denied))
            real_connect = psycopg2.connect
            def connect(dsn=None, **kwargs):
                values = {**(parse_dsn(dsn) if dsn else {}), **kwargs}
                assert values.get("host") == "127.0.0.1" and int(values.get("port", 0)) == args.port
                assert values.get("dbname") in {"synthetic_business", "synthetic_cdm"}
                return real_connect(dsn, **kwargs)
            stack.enter_context(patch.object(psycopg2, "connect", connect))
            from app.database import connection as owner, clinical_connection as clinical
            from app.services import clinical_sources as settings, validation_material_source as material
            from app.services.bundles import assembly, current_view, frontpage_view
            from app.services.clinical_case_catalog import workstation
            from app.services.medical_records import detail_service
            from app.services.luxian_0609 import source_evidence_reader as reader
            from app.services.qc_workspace.record_repository import RecordRepository
            stack.enter_context(patch.object(owner, "engine", business))
            from sqlalchemy.orm import sessionmaker
            stack.enter_context(patch.object(owner, "SessionLocal", sessionmaker(bind=business)))
            stack.enter_context(patch.object(assembly, "engine", business))
            stack.enter_context(patch.object(frontpage_view, "engine", business))
            stack.enter_context(patch.object(detail_service, "engine", business))
            profile = settings.SourceSettings()
            profile.cdm.enabled = True
            profile.cdm.port = args.port
            profile.cdm.database = "synthetic_cdm"
            profile.cdm.username = "synthetic_reader"
            selected = settings.snapshot(profile, "independent_cdm")
            engines.append(clinical._engine(selected["url"], str(passfile)))
            from app.routers import clinical_sources as source_api
            assert source_api.check(profile, _actor={"id": "synthetic-admin"})["data"]["read_only"] is True
            identity = dict(institute_id="I", patient_id="P", visit_id="V")
            with business.begin() as connection:
                for name in assembly._DOMAIN_BUNDLE_TABLE.values():
                    connection.execute(sa.text(f"CREATE TABLE IF NOT EXISTS public.{name}(institute_id text,patient_id text,visit_id text,execution_domain text,policy_version text,bundle_schema_version text,document_hits jsonb,data_quality_flags jsonb,timeline_facts jsonb,source_documents jsonb,structured_context jsonb,bundle_updated_at timestamp,PRIMARY KEY(institute_id,patient_id,visit_id))"))
                connection.execute(sa.text("CREATE SCHEMA qc"))
                connection.execute(sa.text("CREATE TABLE qc.sync_config_registry(namespace text,config_key text,payload_json text,updated_by text,source text,change_reason text,updated_at timestamp,PRIMARY KEY(namespace,config_key))"))
                connection.execute(sa.text("CREATE SCHEMA pdfmat_012345abcdef"))
                connection.execute(sa.text("CREATE TABLE pdfmat_012345abcdef.daily_course_record (LIKE cdm.daily_course_record)"))
                connection.execute(sa.text("INSERT INTO pdfmat_012345abcdef.daily_course_record(institute_id,patient_id,visit_id,document_id,record_content) VALUES('I','pdfp_P','pdfv_V','PDF-D','SYNTHETIC-PDF-BUSINESS')"))
                connection.execute(sa.text("CREATE TABLE qc.validation_material_batches(id text,storage_schema text,state text)"))
                connection.execute(sa.text("CREATE TABLE qc.validation_material_copies(id text,batch_id text,institute_id text,patient_id text,visit_id text,identity_map jsonb)"))
                connection.execute(sa.text("CREATE TABLE qc.validation_material_documents(candidate_id text,target_document_id text,target_table text,state text,copy_id text,provenance jsonb)"))
                connection.execute(sa.text("INSERT INTO qc.validation_material_batches VALUES('B','pdfmat_012345abcdef','ready')"))
                connection.execute(sa.text("INSERT INTO qc.validation_material_copies VALUES('C','B','I','pdfp_P','pdfv_V','{}')"))
            from sqlalchemy.orm import Session
            with Session(business) as session:
                saved = settings.save(session, profile, "synthetic-admin")
                assert settings.load(session)[0] == saved
            with clinical.selected(settings.legacy_snapshot()):
                old = assembly.assemble_domain_bundle(execution_domain="admission", **identity)
                assert "SYNTHETIC-LEGACY" in str(old)
                assembly._upsert_domain_bundle(execution_domain="admission", bundle=old, bundle_schema="public")
            with clinical.selected(selected):
                assert assembly.load_domain_bundle(execution_domain="admission", **identity) is None
                page = workstation(qc_projection_loader=lambda _: {})
                assert page["total"] == 2 and {row["name"] for row in page["records"]} == {"SYNTHETIC-CDM", "SYNTHETIC-NO-FRONTPAGE"}
                assert workstation(hospital_status="discharged", qc_projection_loader=lambda _: {})["total"] == 1
                assert workstation(hospital_status="inpatient", qc_projection_loader=lambda _: {})["total"] == 1
                assert workstation(doctor="合成医生", qc_projection_loader=lambda _: {})["total"] == 1
                assert detail_service.get_frontpage(**identity)["name"] == "SYNTHETIC-CDM"
                repository = RecordRepository(session_factory=lambda: Session(business))
                collected = repository.collect_records(scope="all", department=None, doctor=None, date_field="admission", start_date=None,end_date=None,keyword=None,record_refs=[identity])
                assert len(collected) == 1 and collected[0]["patient_name"] == "SYNTHETIC-CDM"
                all_cases = repository.collect_records(scope="all", department=None, doctor=None, date_field="admission", start_date=None,end_date=None,keyword=None)
                assert {row["visit_id"] for row in all_cases} == {"V", "V2"}
                assert repository.count_records(scope="all", department=None, doctor=None, date_field="admission", start_date=None,end_date=None,keyword=None) == 2
                listing = repository.list_records(scope="all", department=None, doctor=None, date_field="admission", start_date=None,end_date=None,keyword=None, page=2, page_size=1)
                assert listing.total == 2 and [item["visit_id"] for item in listing.items] == ["V2"]

                new = assembly.load_or_assemble_domain_bundle(execution_domain="admission", **identity)
                assert "SYNTHETIC-CDM" in str(new) and "SYNTHETIC-LEGACY" not in str(new)
                documents = current_view.load_current_documents(**identity)
                assert "SYNTHETIC-CDM" in str(documents) and "SYNTHETIC-LEGACY" not in str(documents)
                formal = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema="cdm", **identity)
                assert formal.rows[0]["record_content"] == "SYNTHETIC-CDM"
                assert formal.rows[0]["record_datetime"] != formal.rows[0]["submit_datetime"]
                from app.services.sichuan_qc_service import SichuanQCService
                assert SichuanQCService._resolve_primary_diagnosis_context(**identity)["diagnosis_name"] == "SYNTHETIC-CDM"

                material._registered_schema.cache_clear()
                pdf = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", source_schema=None, institute_id="I", patient_id="pdfp_P", visit_id="pdfv_V")
                assert pdf.rows[0]["record_content"] == "SYNTHETIC-PDF-BUSINESS"
                with clinical.get_engine().connect() as connection:
                    assert connection.execute(sa.text("SHOW transaction_read_only")).scalar_one() == "on"
                    connection.rollback()
                    try:
                        connection.execute(sa.text("INSERT INTO cdm.daily_course_record(document_id) VALUES('FORBIDDEN')"))
                    except sa.exc.DBAPIError as error:
                        assert error.orig.pgcode == "25006"
                        connection.rollback()
                    else:
                        raise AssertionError("source transaction unexpectedly writable")
                    connection.execute(sa.text("SET transaction_read_only=off"))
                    try:
                        connection.execute(sa.text("DELETE FROM cdm.daily_course_record"))
                    except sa.exc.DBAPIError as error:
                        assert error.orig.pgcode == "42501"
                    else:
                        raise AssertionError("source role unexpectedly writable")
            # 使用正式Canonical保存/选轮链，同坐标的两个源不能互相覆盖“最新结果”。
            from datetime import datetime
            from app.services import custom_qc_workspace_service as workspace
            from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
            from tests.unit.test_luxian_0609_canonical_result_delivery import _published_pilot_item_for_read_boundary
            metadata = sa.MetaData()
            jobs = workspace._batch_jobs_table(readonly=True).to_metadata(metadata, schema="qc")
            envelopes = workspace._record_result_envelopes_table().to_metadata(metadata, schema="qc")
            metadata.create_all(business)
            service = object.__new__(workspace.CustomQCWorkspaceService)
            service._batch_job_table, service._record_result_envelope_table = jobs, envelopes
            stack.enter_context(patch.object(workspace, "_session", lambda: Session(business)))
            stack.enter_context(patch.object(workspace, "customer_safe_projection_key", lambda: "synthetic-source-key"))
            rule_id = "LX0609-01-01-01"
            item = _published_pilot_item_for_read_boundary(rule_id)
            item.update(identity, record_id="V")
            for number, selection in enumerate((settings.legacy_snapshot(), selected)):
                with clinical.selected(selection):
                    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                        "scoped_customer_rule_ids": [rule_id], "rule_ids": [rule_id], "selected_rule_ids": [], "record_refs": [identity]}
                    settings.freeze(filters)
                    now = datetime(2026,11,4,10+number)
                    row = {"id": "synthetic-job-"+str(number), "draft_id": "synthetic-draft", "rule_code": "LX0609",
                        "rule_name": "合成保存验收", "status": "completed", "created_by": "synthetic-admin",
                        "filters_json": json.dumps(filters), "record_ids_json": '["V"]', "items_json": json.dumps([item]),
                        "summary_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}),
                        "created_at": now, "updated_at": now, "finished_at": now}
                    with Session(business) as session:
                        session.execute(jobs.insert().values(**row))
                        CanonicalResultStore(envelopes).replace_for_job(session, job_row=row, items=[item], now=now,
                            projector=lambda data: envelope_item_from_rule_result(data, hmac_key="synthetic-source-key"),
                            projection_key="synthetic-source-key")
                        session.commit()
            for number, selection in enumerate((settings.legacy_snapshot(), selected)):
                with clinical.selected(selection):
                    result = service.build_latest_single_record_result_dto(**identity)
                    assert result["state"] == "ready" and result["job_id"] == "synthetic-job-"+str(number)
                    assert result["result_rule_count"] == 1 and result["items"][0]["status"] == item["status"]
                    assert result["items"][0]["rule_id"] == rule_id
                    assert result["items"][0]["reason_code"] == item["reason_code"]

            with business.connect() as connection:
                assert connection.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar_one() == 2
            # 业务账号资料仍归业务库，医生范围只接受当前源的首页主治医师。
            from app.database.models.v36_reports import SysUser
            from app.services.doctor_case_scope import resolve_doctor_case_scope
            SysUser.__table__.create(business)
            with Session(business) as session:
                session.add(SysUser(id="synthetic-doctor", username="synthetic-doctor", display_name="合成医生",
                    institute_id="I", department="合成科室", role="doctor", roles_json='["doctor"]', is_active=True))
                session.commit()
            with clinical.selected(selected):
                own_scope = resolve_doctor_case_scope("synthetic-doctor", session_factory=lambda: Session(business))
                assert own_scope.case_refs == (("I","P","V"),)
                assert workstation(case_scope=own_scope, qc_projection_loader=lambda _: {})["total"] == 1
            with clinical.selected(settings.legacy_snapshot()):
                assert assembly.load_domain_bundle(execution_domain="admission", **identity) is None
                back = assembly.load_or_assemble_domain_bundle(execution_domain="admission", **identity)
                assert "SYNTHETIC-LEGACY" in str(back) and "SYNTHETIC-CDM" not in str(back)
            after, _ = fingerprint()
            assert before == after
        result = {"ok": True, "postgres_version": source.dialect.server_version_info, "source_revision": "20261104_000060",
            "source_tables": table_count, "source_data_and_schema_unchanged": True,
            "source_role_write_denied": True, "business_cache_write_verified": True, "same_keys_isolated": True, "canonical_source_selection_verified": True, "doctor_scope_verified": True,
            "pdf_business_route_verified": True, "models_called": 0, "real_databases_connected": False,
            "source_bootstrap_sha256": hashlib.sha256((args.source_backend / "scripts/bootstrap_cache_sync_database.py").read_bytes()).hexdigest()}
        (directory / "result.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        for engine in engines:
            engine.dispose()
        command("pg_ctl", "-D", cluster, "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--source-backend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--port", type=int, default=62996)
    parser.add_argument("--bootstrap-source", type=Path)
    parser.add_argument("--bootstrap-url")
    parser.add_argument("--bootstrap-passfile", type=Path)
    args = parser.parse_args()
    if args.bootstrap_source:
        bootstrap(args.bootstrap_source, args.bootstrap_url, args.bootstrap_passfile)
    elif all((args.pg_bin, args.source_backend, args.output_dir)):
        run(args)
    else:
        parser.error("pg-bin, source-backend and a fresh output-dir are required")
