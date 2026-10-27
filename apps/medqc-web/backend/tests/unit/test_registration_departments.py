"""只在内存 SQLite 核对临床 owner 和目录边界。"""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services import registration_departments as owner


def test_split_clinical_owner_ignores_public_shadow_and_preserves_institutes(
    monkeypatch,
):
    monkeypatch.delenv("REGISTRATION_INSTITUTE_ID", raising=False)
    monkeypatch.delenv("HOMOLOGY_TARGET_INSTITUTE_ID", raising=False)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
        connection.exec_driver_sql(
            "CREATE TABLE discharge_record (institute_id TEXT, dept_name TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO discharge_record VALUES ('old', '旧表科室')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE cdm.discharge_record (institute_id TEXT, dept_name TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO cdm.discharge_record VALUES ('A', '内科'), ('B', '内科'), ('A', '内科')"
        )
    monkeypatch.setattr(owner, "clinical_read_schema", lambda: "cdm")
    with Session(engine) as session:
        result = owner.registration_departments(session)
    assert {row["label"] for row in result} == {"内科（A）", "内科（B）"}
    assert len({row["key"] for row in result}) == 2
    monkeypatch.setenv("REGISTRATION_INSTITUTE_ID", "A")
    with Session(engine) as session:
        scoped = owner.registration_departments(session)
    assert len(scoped) == 1 and scoped[0]["label"] == "内科"
    assert scoped[0]["institute_id"] == "A"
    engine.dispose()
