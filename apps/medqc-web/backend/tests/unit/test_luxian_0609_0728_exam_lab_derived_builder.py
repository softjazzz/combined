from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, insert, select
from sqlalchemy.orm import Session

from scripts import build_luxian_0609_0728_exam_lab_derived_v1 as builder


def _exam_rows(case: builder.SourceCase) -> dict[str, list[dict[str, object]]]:
    admission = datetime(2026, 7, 7, 8, 0)
    ct_order_time = admission + timedelta(hours=4)
    mri_order_time = admission + timedelta(hours=8)
    mri_exam_id = f"{case.target_visit_id}-exam-mri-001"
    return {
        "inpat_registration": [
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "admission_datetime": admission,
                "discharge_datetime": admission + timedelta(days=5),
            }
        ],
        "inpat_nondrug_order": [
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "order_id": f"{case.target_visit_id}-copied-ct-order",
                "order_name": "胸部CT平扫",
                "order_status": "新开",
                "prescribed_datetime": ct_order_time,
            },
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "order_id": f"{case.target_visit_id}-exam-order-001",
                "order_name": "腰椎MRI平扫",
                "order_status": "已执行",
                "prescribed_datetime": mri_order_time,
            },
        ],
        "exam_master": [
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "order_id": f"{case.target_visit_id}-exam-order-001",
                "exam_id": mri_exam_id,
                "exam_type": "MRI",
                "exam_time": mri_order_time + timedelta(hours=1),
                "report_time": mri_order_time + timedelta(hours=2),
            }
        ],
        "exam_item_report": [
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "document_id": f"{case.target_visit_id}-exam-item-report-001",
                "item_id": f"{mri_exam_id}-item-001",
                "exam_id": mri_exam_id,
                "report_time": mri_order_time + timedelta(hours=2),
            }
        ],
        "daily_course_record": [
            {
                "institute_id": builder.TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
                "document_id": f"{case.target_visit_id}-course-exam-before-001",
                "order_id": f"{case.target_visit_id}-exam-order-001",
                "record_time": mri_order_time - timedelta(minutes=30),
            }
        ],
    }


def _discharge_diagnosis_rows(
    case: builder.SourceCase,
) -> dict[str, list[dict[str, object]]]:
    discharge_time = datetime(2026, 7, 12, 9, 0)
    base = {
        "institute_id": builder.TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
    }
    return {
        "inpat_registration": [{
            **base,
            "admission_datetime": datetime(2026, 7, 7, 8, 0),
            "discharge_datetime": discharge_time,
        }],
        "discharge_record": [{
            **base,
            "document_id": f"{case.target_visit_id}-discharge-record",
            "record_time": discharge_time,
        }],
        "discharge_record_diagnosis": [
            {**base, "diagnosis_id": "legacy-1", "diagnosis_name": "重症肺炎", "diagnosis_code": "J18.900"},
            {**base, "diagnosis_id": "legacy-2", "diagnosis_name": "高血压病", "diagnosis_code": "I10.x00"},
            {**base, "diagnosis_id": "legacy-3", "diagnosis_name": "重症肺炎", "diagnosis_code": "J18.900"},
        ],
        "diagnosis": [],
    }


def test_discharge_diagnosis_contract_is_unique_consistent_and_idempotent() -> None:
    case = builder.CASES[0]
    rows = _discharge_diagnosis_rows(case)

    builder._normalize_discharge_diagnosis_contract(rows, case)
    first = deepcopy(rows)
    builder._normalize_discharge_diagnosis_contract(rows, case)

    assert rows == first
    assert [row["diagnosis_no"] for row in rows["diagnosis"]] == [1, 2]
    assert [row["diagnosis_name"] for row in rows["diagnosis"]] == [
        row["diagnosis_name"] for row in rows["discharge_record_diagnosis"]
    ]
    assert len({row["diagnosis_id"] for row in rows["diagnosis"]}) == 2
    builder._validate_discharge_diagnosis_contract(rows, case)


@pytest.mark.parametrize("case", builder.CASES)
def test_complete_ct_mri_associations_is_idempotent_for_each_derived_case(
    case: builder.SourceCase,
) -> None:
    rows = _exam_rows(case)

    builder._complete_ct_mri_associations(rows, case)
    first_counts = {name: len(values) for name, values in rows.items()}
    builder._complete_ct_mri_associations(rows, case)

    assert {name: len(values) for name, values in rows.items()} == first_counts
    builder._validate_ct_mri_associations(rows, case)
    assert len(rows["inpat_nondrug_order"]) == 2
    assert len(rows["exam_master"]) == 2
    assert len(rows["exam_item_report"]) == 2


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    def execute(self, statement: object) -> None:
        self.statements.append(statement)


def test_replace_target_rows_deletes_only_the_complete_derived_coordinate_before_insert() -> None:
    case = builder.CASES[0]
    table = Table(
        "exam_master",
        MetaData(),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
        Column("exam_id", String),
        Column("order_id", String),
    )
    session = _RecordingSession()
    row = {
        "institute_id": builder.TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
        "exam_id": "exam-1",
        "order_id": "order-1",
    }

    inserted = builder._replace_target_rows(session, table, [row])

    assert inserted == 1
    assert len(session.statements) == 2
    delete_statement = session.statements[0]
    assert delete_statement.__class__.__name__ == "Delete"
    compiled = delete_statement.compile()
    assert set(compiled.params.values()) == {
        builder.TARGET_INSTITUTE_ID,
        case.target_patient_id,
        case.target_visit_id,
    }


def test_replace_target_rows_rejects_any_row_outside_the_dedicated_coordinates() -> None:
    table = Table(
        "exam_master",
        MetaData(),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
        Column("exam_id", String),
    )
    session = _RecordingSession()

    with pytest.raises(ValueError, match="专用三坐标之外"):
        builder._replace_target_rows(
            session,
            table,
            [
                {
                    "institute_id": "source-hospital",
                    "patient_id": "source-patient",
                    "visit_id": "source-visit",
                    "exam_id": "source-exam",
                }
            ],
        )

    assert session.statements == []


def test_replace_target_rows_is_repeatable_without_touching_another_coordinate() -> None:
    case = builder.CASES[0]
    engine = create_engine("sqlite+pysqlite:///:memory:")
    table = Table(
        "exam_master",
        MetaData(),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
        Column("exam_id", String),
        Column("order_id", String),
    )
    table.metadata.create_all(engine)
    target_row = {
        "institute_id": builder.TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
        "exam_id": "target-exam",
        "order_id": "target-order",
    }
    source_row = {
        "institute_id": "source-hospital",
        "patient_id": "source-patient",
        "visit_id": "source-visit",
        "exam_id": "source-exam",
        "order_id": "source-order",
    }

    with Session(engine) as session:
        session.execute(insert(table).values(source_row))
        builder._replace_target_rows(session, table, [target_row])
        builder._replace_target_rows(session, table, [target_row])
        session.commit()
        stored_rows = [dict(row) for row in session.execute(select(table)).mappings().all()]

    assert stored_rows == [source_row, target_row]


def test_validate_ct_mri_associations_rejects_one_order_without_master() -> None:
    case = builder.CASES[0]
    rows = _exam_rows(case)
    builder._complete_ct_mri_associations(rows, case)
    rows["exam_master"] = rows["exam_master"][:-1]

    with pytest.raises(ValueError, match="医嘱与检查主记录未形成一一对应"):
        builder._validate_ct_mri_associations(rows, case)


def test_validate_ct_mri_associations_rejects_duplicate_master_natural_key() -> None:
    case = builder.CASES[0]
    rows = _exam_rows(case)
    builder._complete_ct_mri_associations(rows, case)
    rows["exam_master"].append(deepcopy(rows["exam_master"][0]))

    with pytest.raises(ValueError, match="检查主记录自然键重复"):
        builder._validate_ct_mri_associations(rows, case)


def test_validate_ct_mri_associations_rejects_master_without_report() -> None:
    case = builder.CASES[0]
    rows = _exam_rows(case)
    builder._complete_ct_mri_associations(rows, case)
    missing_exam_id = str(rows["exam_master"][-1]["exam_id"])
    rows["exam_item_report"] = [
        row for row in rows["exam_item_report"] if row.get("exam_id") != missing_exam_id
    ]

    with pytest.raises(ValueError, match="检查主记录与报告未形成一一对应"):
        builder._validate_ct_mri_associations(rows, case)


def test_validate_ct_mri_associations_rejects_duplicate_report_natural_key() -> None:
    case = builder.CASES[0]
    rows = _exam_rows(case)
    builder._complete_ct_mri_associations(rows, case)
    rows["exam_item_report"].append(deepcopy(rows["exam_item_report"][0]))

    with pytest.raises(ValueError, match="报告自然键缺失或重复"):
        builder._validate_ct_mri_associations(rows, case)
