"""特殊分类的字段与事件反例，不连接真实数据库。"""

from datetime import datetime

import pytest
from app.services import special_record_report_source_service as source
from sqlalchemy import Column, MetaData, String, Table, create_engine, insert
from sqlalchemy.orm import Session

RECORD = {
    "admission_time": datetime(2026, 9, 1),
    "discharge_time": datetime(2026, 9, 15),
}


def config():
    value = source.empty_config()
    for key in ("critical", "difficult"):
        value[key] = {"positive_codes": ["Y"], "negative_codes": ["N"]}
    value["surgery_level_codes"] = {"1": ["I"], "2": ["II"], "3": ["III"], "4": ["IV"]}
    return value


def classify(rows):
    return source.classify(rows, config(), RECORD)


def test_overlapping_death_critical_difficult_and_fourth_level():
    result = classify(
        {
            "death_record": [{"death_datetime": "2026-09-15T00:00:00"}],
            "mr_customize": [
                {"criticalcare_record_sign": "Y", "difficult_record_sign": "Y"}
            ],
            "surgery_record": [
                {"surgery_begin_time": "2026-09-02T10:00:00", "surgery_level": "IV"}
            ],
        }
    )
    for key in (
        "death",
        "critical",
        "difficult",
        "surgery",
        "surgery_ge3",
        "surgery_ge4",
    ):
        assert result[key]["state"] == "positive"


def test_missing_flags_and_unmapped_codes_are_unknown_not_ordinary():
    result = classify(
        {
            "mr_customize": [
                {
                    "criticalcare_record_sign": None,
                    "difficult_record_sign": "unexpected",
                }
            ]
        }
    )
    assert result["critical"]["state"] == result["difficult"]["state"] == "unknown"
    known = classify(
        {
            "mr_customize": [
                {"criticalcare_record_sign": "N", "difficult_record_sign": "N"}
            ]
        }
    )
    assert known["critical"]["state"] == known["difficult"]["state"] == "negative"


@pytest.mark.parametrize(
    "day", ["2099-01-01T00:00:00", "2026-09-16T00:00:00", "2026-08-31T23:59:00"]
)
def test_events_outside_current_visit_cannot_be_positive(day):
    result = classify(
        {
            "death_record": [{"death_datetime": day}],
            "consultation_record": [{"consultation_time": day}],
            "bloodtrans_record": [
                {"transfution_datetime": day, "blood_transfusion_volume": "200"}
            ],
            "surgery_record": [{"surgery_begin_time": day, "surgery_level": "IV"}],
        }
    )
    assert all(item["state"] == "unknown" for item in result.values())


def test_alias_time_conflict_and_unverified_extra_surgery_prevent_negative_level():
    result = classify(
        {
            "surgery_record": [
                {"surgery_begin_time": "2026-09-02T10:00:00", "surgery_level": "II"},
                {
                    "surgery_begin_time": "2026-09-03T10:00:00",
                    "surgery_begin_datetime": "2026-09-04T10:00:00",
                    "surgery_level": "IV",
                },
            ]
        }
    )
    assert result["surgery"]["state"] == "positive"
    assert result["surgery_ge3"]["state"] == result["surgery_ge4"]["state"] == "unknown"
    result = classify(
        {
            "consultation_record": [
                {
                    "consultation_time": "2026-09-02T10:00:00",
                    "consultation_datetime": "2026-09-03T10:00:00",
                }
            ]
        }
    )
    assert result["consultation"]["state"] == "unknown"


def test_actual_surgery_with_unmapped_level_keeps_only_surgery_positive():
    result = classify(
        {
            "surgery_record": [
                {"surgery_begin_time": "2026-09-02T10:00:00", "surgery_level": "4"}
            ]
        }
    )
    assert result["surgery"]["state"] == "positive"
    assert result["surgery_ge3"]["state"] == result["surgery_ge4"]["state"] == "unknown"


def test_application_title_and_homepage_issue_time_are_ignored():
    result = classify(
        {
            "surgery_application": [
                {"surgery_level": "IV", "request_surgery_datetime": "2026-09-02"}
            ],
            "mr_bloodtrans": [
                {
                    "transfution_datetime": "2026-09-02",
                    "blood_transfusion_volume": "200",
                }
            ],
            "mr_customize": [{"discharge_condition": "死亡"}],
            "death_record": [{"document_title": "死亡记录"}],
        }
    )
    assert all(item["state"] == "unknown" for item in result.values())


@pytest.mark.parametrize("volume", [None, "", "0", "-1", "NaN", "Infinity", "200ml"])
def test_transfusion_requires_positive_finite_structured_volume(volume):
    result = classify(
        {
            "bloodtrans_record": [
                {
                    "transfution_datetime": "2026-09-02",
                    "blood_transfusion_volume": volume,
                }
            ]
        }
    )
    assert result["transfusion"]["state"] == "unknown"


def test_reflection_reads_only_same_three_coordinates_and_missing_columns_unknown():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    table = Table(
        "death_record",
        metadata,
        *(Column(key, String) for key in source.COORDINATES),
        Column("death_datetime", String),
    )
    metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.execute(
            insert(table),
            [
                dict(
                    institute_id="H1",
                    patient_id="P",
                    visit_id="V",
                    death_datetime="2026-09-02",
                ),
                dict(
                    institute_id="H2",
                    patient_id="P",
                    visit_id="V",
                    death_datetime="2026-09-03",
                ),
            ],
        )
    with Session(engine) as session:
        rows = source.load_sources(session, {("H1", "P", "V")})
        assert len(rows[("H1", "P", "V")]["death_record"]) == 1
        assert rows[("H1", "P", "V")]["bloodtrans_record"] is None
        assert classify(rows[("H1", "P", "V")])["death"]["state"] == "positive"
    engine.dispose()


def test_overlapping_or_unapproved_source_configuration_is_rejected():
    value = config()
    value["critical"]["negative_codes"] = ["Y"]
    with pytest.raises(source.SpecialReportInvalid):
        source.validate_config(value)
    value = config()
    value["source"] = "mr_customize.discharge_condition"
    with pytest.raises(source.SpecialReportInvalid):
        source.validate_config(value)
