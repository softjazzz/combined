"""首页质控 V2：加载器（SQLite 合成表，不连接业务数据库）。"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.frontpage_qc_v2 import FrontpageRef, build_frontpage_doc, evaluate_frontpage, load_frontpage_raw
from app.services.frontpage_qc_v2.loader import _table
from tests.unit.frontpage_qc_v2_support import (
    REF,
    compliant_cost,
    compliant_diagnoses,
    compliant_mr,
    diagnosis_row,
    surgery_row,
)

_KEYS = {"institute_id": REF.institute_id, "patient_id": REF.patient_id, "visit_id": REF.visit_id}


def _create(session, table: str, rows: List[Dict[str, Any]], extra_columns: tuple = ()) -> None:
    columns = sorted({key for row in rows for key in row} | set(_KEYS) | set(extra_columns))
    session.execute(text(f'CREATE TABLE "{table}" ({", ".join(f"{c} TEXT" for c in columns)})'))
    for row in rows:
        payload = {**_KEYS, **row}
        session.execute(
            text(f'INSERT INTO "{table}" ({", ".join(payload)}) VALUES ({", ".join(":" + k for k in payload)})'),
            payload,
        )


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    with sessionmaker(bind=engine)() as s:
        yield s


def _seed(session, *, mr_diagnoses, diagnoses=(), surgeries=None, cost=True):
    _create(session, "mr", [compliant_mr()])
    _create(session, "mr_diagnosis", list(mr_diagnoses), extra_columns=("diagnosis_type", "is_deleted"))
    _create(session, "diagnosis", list(diagnoses), extra_columns=("diagnosis_type",))
    _create(session, "mr_surgery", surgeries if surgeries is not None else [surgery_row(1)], extra_columns=("surgery_id",))
    _create(session, "mr_cost", [compliant_cost()] if cost else [], extra_columns=("total_cost",))


def test_loads_compliant_frontpage_and_scores_full_marks(session):
    _seed(session, mr_diagnoses=compliant_diagnoses())

    raw = load_frontpage_raw(session, REF, schema=None)
    outcome = evaluate_frontpage(build_frontpage_doc(raw))

    assert raw.diagnosis_source == "mr_diagnosis"
    assert outcome.score == 100
    assert outcome.findings == []


def test_returns_none_when_frontpage_missing(session):
    _seed(session, mr_diagnoses=compliant_diagnoses())
    assert load_frontpage_raw(session, FrontpageRef("INST-SYN", "C02", "C02-V1"), schema=None) is None


def test_deleted_diagnosis_rows_are_ignored(session):
    rows = compliant_diagnoses()
    deleted = diagnosis_row(9, "已删除诊断", "", main=True)
    deleted["is_deleted"] = "1"
    _seed(session, mr_diagnoses=rows + [deleted])

    doc = build_frontpage_doc(load_frontpage_raw(session, REF, schema=None))
    assert [item.name for item in doc.main_diagnoses] == ["急性阑尾炎"]


def test_falls_back_to_diagnosis_table_for_discharge_diagnoses(session):
    outpatient = [d for d in compliant_diagnoses() if d["diagnosis_type"] == "门诊诊断"]
    fallback = [
        {k: v for k, v in diagnosis_row(1, "急性阑尾炎", "K35.800", main=True, diagnosis_type="主要诊断").items() if k != "diagnosis_main"},
        {k: v for k, v in diagnosis_row(2, "高血压", "I10.x00", diagnosis_type="其他诊断").items() if k != "diagnosis_main"},
    ]
    _seed(session, mr_diagnoses=outpatient, diagnoses=fallback)

    raw = load_frontpage_raw(session, REF, schema=None)
    doc = build_frontpage_doc(raw)

    assert raw.diagnosis_source == "diagnosis"
    assert doc.main_diagnosis.name == "急性阑尾炎"
    assert [item.name for item in doc.outpatient_diagnoses] == ["急性阑尾炎"]
    assert raw.notes


def test_main_surgery_sign_orders_surgeries(session):
    surgeries = [
        surgery_row(1, name="气管内插管", code="96.0400"),
        surgery_row(2, main_surgery_sign="是"),
    ]
    _seed(session, mr_diagnoses=compliant_diagnoses(), surgeries=surgeries)

    doc = build_frontpage_doc(load_frontpage_raw(session, REF, schema=None))
    assert doc.main_surgery.name == "腹腔镜下阑尾切除术"


def test_schema_qualified_table_names():
    assert _table("mr", "cdm") == '"cdm"."mr"'
    assert _table("mr", None) == '"mr"'
