"""由 run_pr8_disposable_pg_tests 启动的专属合成 PG；拒绝普通连接配置。"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.services import case_material_snapshot as material
from app.services.cdm_publication_evidence import read_publication, target_hash

IDENTITY = ("SYNTHETIC-I", "SYNTHETIC-P", "SYNTHETIC-V")


@pytest.fixture
def database():
    url = os.environ.get("PR8_DISPOSABLE_PG_URL")
    if not url:
        pytest.skip("需要专属一次性PG运行器")
    engine = create_engine(url)
    epoch, operation = str(uuid4()), str(uuid4())
    row = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))
    row.update(document_id="D1", surgery_process="SYNTHETIC-V1", record_content=None)
    key = target_hash(
        {
            k: row[k]
            for k in (
                *dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)),
                "document_id",
            )
        }
    )
    with engine.begin() as c:
        c.execute(text("CREATE SCHEMA cdm"))
        c.execute(text("CREATE SCHEMA sync_delivery"))
        for statement in (
            "CREATE TABLE cdm.surgery_record(institute_id text,patient_id text,visit_id text,document_id text,surgery_process text,record_content text)",
            "CREATE TABLE sync_delivery.identity(epoch uuid)",
            "CREATE TABLE sync_delivery.contract(interface_name text,source_epoch uuid,mapping_hash text,activation bigint,bootstrap_required boolean)",
            "CREATE TABLE sync_delivery.receipt(source_epoch uuid,interface_name text,source_key_hash text,generation bigint,mapping_hash text,activation bigint,target_key_hash text)",
            "CREATE TABLE sync_delivery.operation(operation_id uuid,source_epoch uuid,interface_name text,mapping_hash text,queue_hash text,scope_hash text,commit_order bigint)",
            "CREATE TABLE sync_delivery.operation_item(operation_id uuid,source_key_hash text,generation bigint)",
        ):
            c.execute(text(statement))
        c.execute(
            text(
                "INSERT INTO cdm.surgery_record VALUES(:institute_id,:patient_id,:visit_id,:document_id,:surgery_process,:record_content)"
            ),
            row,
        )
        c.execute(
            text("INSERT INTO sync_delivery.identity VALUES(:epoch)"), {"epoch": epoch}
        )
        c.execute(
            text(
                "INSERT INTO sync_delivery.contract VALUES('web.surgery_record',:epoch,'mapping',1,false)"
            ),
            {"epoch": epoch},
        )
        c.execute(
            text(
                "INSERT INTO sync_delivery.receipt VALUES(:epoch,'web.surgery_record','source',1,'mapping',1,:key)"
            ),
            {"epoch": epoch, "key": key},
        )
        c.execute(
            text(
                "INSERT INTO sync_delivery.operation VALUES(:op,:epoch,'web.surgery_record','mapping',:queue,'scope',1)"
            ),
            {"op": operation, "epoch": epoch, "queue": target_hash(["mapping", 1])},
        )
        c.execute(
            text("INSERT INTO sync_delivery.operation_item VALUES(:op,'source',1)"),
            {"op": operation},
        )
    # 原40接口交接没有新手术接口；测试明确注入其合成主键合同，不假装已在生产启用。
    from app.services import cdm_publication_evidence as publication

    original = publication.KEYS.get("surgery_record")
    publication.KEYS["surgery_record"] = {
        "interface": "web.surgery_record",
        "keys": ["institute_id", "patient_id", "visit_id", "document_id"],
    }
    try:
        yield engine, row
    finally:
        if original is None:
            publication.KEYS.pop("surgery_record")
        else:
            publication.KEYS["surgery_record"] = original
        # 本夹具只用于运行器新建的专属合成集群；保留集群，由运行器停库。
        with engine.begin() as c:
            c.execute(text("DROP SCHEMA sync_delivery CASCADE"))
            c.execute(text("DROP SCHEMA cdm CASCADE"))
        engine.dispose()


def test_repeatable_read_keeps_body_and_receipt_version_together(
    database, monkeypatch, tmp_path
):
    engine, row = database
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    from app.database import clinical_connection as clinical

    with clinical.selected({"id": "legacy_pg", "binding": ""}):
        with (
            engine.connect().execution_options(isolation_level="REPEATABLE READ") as c,
            c.begin(),
        ):
            c.execute(text("SET TRANSACTION READ ONLY"))
            rows = [
                dict(r)
                for r in c.execute(text("SELECT * FROM cdm.surgery_record")).mappings()
            ]
            with engine.begin() as writer:
                writer.execute(
                    text("UPDATE cdm.surgery_record SET surgery_process='SYNTHETIC-V2'")
                )
                writer.execute(text("UPDATE sync_delivery.receipt SET generation=2"))
                writer.execute(
                    text("UPDATE sync_delivery.operation_item SET generation=2")
                )
            publication = read_publication(c, {"surgery_record": rows})
            [evidence] = publication["rows"]["surgery_record"]
            assert rows[0]["surgery_process"] == "SYNTHETIC-V1"
            assert evidence["receipt"]["generation"] == 1
            assert evidence["status"] == "receipt_verified"
            assert c.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        value = {
            "protocol": material.PROTOCOL,
            "binding": "",
            "identity": list(IDENTITY),
            "schema": "cdm",
            "tables": {"surgery_record": rows},
            "automatic_material": {"publication": publication},
        }
        frozen = material.persist("original", value)
        assert (
            material.load("original", IDENTITY)["fingerprint"] == frozen["fingerprint"]
        )
        with engine.connect() as c:
            new_rows = [
                dict(r)
                for r in c.execute(text("SELECT * FROM cdm.surgery_record")).mappings()
            ]
            current = read_publication(c, {"surgery_record": new_rows})
        assert current["rows"]["surgery_record"][0]["receipt"]["generation"] == 2
        assert (
            material.load("original", IDENTITY)["tables"]["surgery_record"][0][
                "surgery_process"
            ]
            == "SYNTHETIC-V1"
        )


def test_conflicting_receipt_is_not_silently_accepted(database):
    engine, row = database
    with engine.begin() as c:
        c.execute(text("UPDATE sync_delivery.contract SET activation=2"))
    with engine.connect() as c:
        with pytest.raises(
            material.MaterialSnapshotError, match="publication_version_conflict"
        ):
            read_publication(c, {"surgery_record": [row]})


def test_metadata_without_schema_permission_does_not_abort_clinical_read(database):
    engine, row = database
    with engine.begin() as c:
        c.execute(text("CREATE ROLE synthetic_metadata_reader"))
        c.execute(text("GRANT USAGE ON SCHEMA cdm TO synthetic_metadata_reader"))
        c.execute(
            text("GRANT SELECT ON cdm.surgery_record TO synthetic_metadata_reader")
        )
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as c,
        c.begin(),
    ):
        c.execute(text("SET TRANSACTION READ ONLY"))
        c.execute(text("SET LOCAL ROLE synthetic_metadata_reader"))
        assert (
            read_publication(c, {"surgery_record": [row]})["status"]
            == "metadata_permission_unconfirmed"
        )
        assert (
            c.execute(text("SELECT count(*) FROM cdm.surgery_record")).scalar_one() == 1
        )


@pytest.mark.parametrize("missing", ["table_missing", "columns_missing"])
def test_automatic_capture_without_window_keeps_missing_domains(
    database, monkeypatch, missing
):
    engine, _ = database
    from app.database import clinical_connection as clinical
    from app.services import case_material_capture as capture, clinical_source_contract
    from app.services.bundles import assembly

    if missing == "columns_missing":
        with engine.begin() as c:
            c.execute(
                text(
                    "CREATE TABLE cdm.daily_course_record(institute_id text,patient_id text,visit_id text,document_id text)"
                )
            )
            c.execute(
                text(
                    "INSERT INTO cdm.daily_course_record VALUES('SYNTHETIC-I','SYNTHETIC-P','SYNTHETIC-V','C1')"
                )
            )
    monkeypatch.delenv("QC_CDM_CAPTURE_WINDOW_UNTIL", raising=False)
    monkeypatch.delenv("QC_DAILY_MATERIAL_ENABLED", raising=False)
    monkeypatch.setattr(assembly, "_source_engine", lambda _: engine)
    monkeypatch.setattr(clinical, "get_engine", lambda: engine)
    # 集群初始化角色仅用于造数；这里隔离已有独立账号权限检查，验证真实捕获事务。
    monkeypatch.setattr(
        clinical_source_contract,
        "inspect_source",
        lambda *a, **kw: {
            "read_only": True,
            "account_read_only": True,
            "dependencies": [
                {
                    "table": "daily_course_record",
                    "status": missing,
                    "missing_columns": ["record_content"],
                },
                {"table": "surgery_record", "status": "structure_ready"},
            ],
        },
    )
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic"}):
        state = capture.capture(identity=IDENTITY)
    assert state["tables"]["surgery_record"][0]["surgery_process"] == "SYNTHETIC-V1"
    assert (
        state["automatic_material"]["sources"]["daily_course_record"]["status"]
        == missing
    )
    assert (
        state["automatic_material"]["publication"]["rows"]["surgery_record"][0][
            "status"
        ]
        == "receipt_verified"
    )
