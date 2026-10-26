"""样本卡片必须与 Bundle 使用同一个临床库，不被旧 public 表遮挡。"""

from datetime import datetime

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, text
from sqlalchemy.orm import Session

from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
    PatientInformation,
)
from app.services import custom_qc_sample_pool_service as pools
from app.services.bundles import assembly


IDENTITY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        for schema in ("cdm", "qc"):
            connection.execute(text(f"ATTACH DATABASE ':memory:' AS {schema}"))
    for model in (AdmissionRecord, DischargeRecord, InpatRegistration, MedicalRecordFrontpage, PatientInformation):
        model.__table__.create(engine)
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    item = Table(
        "manual_problem_sample_pool_items", MetaData(),
        Column("id", String, primary_key=True), Column("pool_id", String),
        Column("row_no", Integer), Column("matched_institute_id", String),
        Column("matched_patient_id", String), Column("matched_visit_id", String),
        Column("sync_status", String), Column("bundle_status", String), schema="qc",
    )
    item.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(item), {
            "id": "item-1", "pool_id": "pool-1", "row_no": 1,
            **{f"matched_{key}": value for key, value in IDENTITY.items()},
            "sync_status": "synced", "bundle_status": "ready",
        })
    service = pools.CustomQCSamplePoolService.__new__(pools.CustomQCSamplePoolService)
    service._item_table = item
    monkeypatch.setattr(pools, "_session", lambda: Session(engine))
    # 文书目录不是本次科室/住院状态的来源；临床 SQL 和分组投影都走真实实现。
    monkeypatch.setattr(service, "_load_bundle_source_table_map", lambda **kwargs: {})
    yield engine, service
    engine.dispose()


def seed(engine, schema, identity=None):
    identity = identity or IDENTITY
    for model in (MedicalRecordFrontpage, DischargeRecord, InpatRegistration):
        table = model.__table__.to_metadata(MetaData(), schema=schema)
        values = {**identity, "name": "合成病历"}
        if model is MedicalRecordFrontpage:
            values.update(admission_dept_name="入院科", discharge_dept_name=schema + "出院科",
                          discharge_datetime=datetime(2026, 1, 5))
        elif model is InpatRegistration:
            values.update(admission_datetime=datetime(2026, 1, 1),
                          discharge_datetime=datetime(2026, 1, 5))
        else:
            values.update(document_id="D1", discharge_date=datetime(2026, 1, 5).date())
        with engine.begin() as connection:
            connection.execute(insert(table), values)


@pytest.mark.parametrize(("mode", "expected"), [("split", "cdm"), ("single", "main")])
def test_sample_cards_use_configured_clinical_owner_and_keep_qc_items(database, monkeypatch, mode, expected):
    engine, service = database
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", mode)
    seed(engine, "main")
    seed(engine, "cdm")
    if mode == "split":
        # 对齐真实故障：旧 public/main 出院表未升级，不能整行读取它。
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE main.discharge_record DROP COLUMN v2_schema"))
    result = service.list_pool_records(pool_id="pool-1")
    assert result.total == 1
    row = result.items[0]
    assert row["department"] == expected + "出院科"
    assert row["hospitalization_status"] == "discharged"
    assert row["admission_time"].startswith("2026-01-01")
    assert row["sync_status"] == "synced" and row["bundle_status"] == "ready"
    # 配置临床会话不能污染普通样本/写入会话。
    with pools._session() as session:
        assert not session.connection().get_execution_options().get("schema_translate_map")


def test_split_missing_evidence_stays_unknown_without_public_fallback(database, monkeypatch):
    engine, service = database
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    seed(engine, "main")
    seed(engine, "cdm", {**IDENTITY, "institute_id": "H2"})
    states = pools._load_previous_hospitalization_states([
        {f"matched_{key}": value for key, value in IDENTITY.items()}
    ])
    assert states == {}


def test_sample_cards_keep_cross_institute_and_patient_identity(database, monkeypatch):
    engine, service = database
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    identities = [IDENTITY, {**IDENTITY, "institute_id": "H2"},
                  {**IDENTITY, "patient_id": "P2"}]
    for index, identity in enumerate(identities):
        seed(engine, "cdm", identity)
        # 不同患者人口信息也必须在本机构内回查。
        with engine.begin() as connection:
            for model in (MedicalRecordFrontpage, InpatRegistration, DischargeRecord):
                table = model.__table__.to_metadata(MetaData(), schema="cdm")
                connection.execute(table.update().where(*[
                    table.c[field] == value for field, value in identity.items()
                ]).values(name=f"合成病例{index}"))
            if index:
                connection.execute(insert(service._item_table), {
                    "id": f"item-{index + 1}", "pool_id": "pool-1", "row_no": index + 1,
                    **{f"matched_{key}": value for key, value in identity.items()},
                    "sync_status": "synced", "bundle_status": "ready",
                })
    result = service.list_pool_records(pool_id="pool-1")
    assert result.total == 3
    assert len({row["id"] for row in result.items}) == 3
    names = {(row["matched_institute_id"], row["matched_patient_id"]): row["patient_name"]
             for row in result.items}
    assert names == {("H1", "P1"): "合成病例0", ("H2", "P1"): "合成病例1",
                     ("H1", "P2"): "合成病例2"}
    assert all(row["issue_count"] == 1 for row in result.items)
