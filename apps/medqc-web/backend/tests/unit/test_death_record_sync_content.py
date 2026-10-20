"""死亡记录结构化正文须穿过真实同步投影到达展示与质控。"""

from copy import deepcopy
from datetime import datetime

import pytest

from app.services import etl_sync
from app.services.document_assembly.assembler import assemble_document
from app.services.luxian_0609.extended_document.death_discussion import (
    evaluate_death_discussion_timeliness,
)
from app.services.luxian_0609.native_extended_document_execution import _death_context


@pytest.fixture
def saved_rows(monkeypatch):
    saved = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            if str(statement).startswith("INSERT INTO"):
                saved.append(dict(params))

        def commit(self):
            pass

    monkeypatch.setattr(etl_sync, "engine", object())
    monkeypatch.setattr(etl_sync, "Session", lambda _engine: Session())
    # 与客户归档相同：目标表没有诊疗经过等结构化列。
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_args: (
        "cdm",
        ["institute_id", "patient_id", "visit_id", "document_id", "record_content",
         "record_time", "submit_datetime"],
        ["institute_id", "patient_id", "visit_id", "document_id"],
    ))
    return saved


def sync_record(record):
    assert etl_sync.upsert_to_local(
        table_name="death_record", records=[record],
        primary_keys=["institute_id", "patient_id", "visit_id", "document_id"],
    ) == 1


def source_record(**overrides):
    return {
        "institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
        "document_id": "D1", "record_content": None,
        "admission_time": "2026-01-01 01:00:00+00:00",
        "death_time": "2026-01-29 01:26:59+00:00",
        "record_time": "2026-01-29 02:00:00+00:00",
        **overrides,
    }


@pytest.mark.parametrize("admission_length,course_length,cause_length", [
    (134, 940, 6), (274, 3264, 4), (380, 1624, 4),
])
def test_actual_source_field_shapes_survive_upsert_and_display(
    saved_rows, admission_length, course_length, cause_length
):
    record = source_record(
        admission_condition="甲" * admission_length,
        treatment_course="乙" * course_length,
        death_reason="丙" * cause_length,
        v2_schema="不进入临床正文的模板数据",
    )
    original = deepcopy(record)
    sync_record(record)
    saved = saved_rows[0]
    body = saved["record_content"]
    assert body == (
        f"入院时间：{record['admission_time']}\n"
        f"入院情况：{record['admission_condition']}\n"
        f"诊疗经过：{record['treatment_course']}\n"
        f"死亡时间：{record['death_time']}\n"
        f"死亡原因：{record['death_reason']}"
    )
    assert assemble_document("death_record", saved).assembled_text == body
    assert saved["record_time"] == record["record_time"]
    assert "v2_schema" not in saved
    assert "模板数据" not in body
    assert record == original


def test_preserves_source_body_and_sections_across_repeated_syncs(saved_rows):
    record = source_record(
        record_content="原始补充正文。", treatment_course="合成诊疗经过。",
        death_reason="合成原因",
    )
    sync_record(record)
    sync_record(record)
    bodies = [row["record_content"] for row in saved_rows]
    assert bodies[0] == bodies[1]
    assert "诊疗经过：合成诊疗经过。" in bodies[0]
    assert bodies[0].endswith("记录内容：原始补充正文。")
    assert bodies[0].count("原始补充正文。") == 1


def test_source_timezone_survives_to_death_discussion_rule(saved_rows):
    sync_record(source_record(treatment_course="合成诊疗经过。"))
    state, death_time = _death_context(
        registration_rows=[], death_rows=saved_rows, discharge_rows=[]
    )
    assert state == "present"
    # 医院时区上午09:26:59；不能采用完成记录的10:00。
    assert death_time == datetime(2026, 1, 29, 9, 26, 59)
    outcome = evaluate_death_discussion_timeliness(
        death_time=death_time, death_rows=saved_rows,
        discussion_rows=[{
            "document_id": "T1", "record_time": "2026-01-30 09:26:59+08:00",
        }], discussion_error="", horizon_rows=[], horizon_error="",
    )
    assert outcome.final_state == "compliant"
    assert outcome.display_facts["actual_interval_hours"] == 24


def test_empty_source_does_not_create_invented_death_body(saved_rows):
    sync_record(source_record(
        admission_time=None, death_time=None,
        admission_condition="", treatment_course=None, death_reason="",
    ))
    assert saved_rows[0].get("record_content") is None


def test_source_with_only_existing_body_is_unchanged(saved_rows):
    sync_record(source_record(
        admission_time=None, death_time=None, record_content="完整既有死亡正文。"
    ))
    assert saved_rows[0]["record_content"] == "完整既有死亡正文。"
