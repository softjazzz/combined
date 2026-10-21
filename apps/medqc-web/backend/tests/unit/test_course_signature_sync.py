"""三类病程的源端结构化签名必须穿过真实同步入库投影，且不混淆角色。"""

from datetime import datetime, timezone

import pytest

from app.database.models.cdm import DailyCourseRecord, PostsurgFirstcourseRecord, SeniorCourseRecord
from app.services import etl_sync
from app.services.bundles.assembly import _inventory_entry
from app.services.bundles.emr_view import _normalize_source_document, build_render_view


COMMON = ("physician_sign", "physician_sign_datetime")
FIELDS = {
    "daily_course_record": COMMON,
    "senior_course_record": (*COMMON, "recorder_sign", "attending_physician_sign",
                             "senior_physician_sign", "seniorphy_sign_datetime"),
    "postsurg_firstcourse_record": (*COMMON, "surgeon_sign"),
}
PAIRS = [(table, field) for table, fields in FIELDS.items() for field in fields]
TIME = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)


class CaptureOnlySession:
    def __init__(self):
        self.saved = []

    def execute(self, statement, params):
        assert str(statement).startswith("INSERT INTO")
        self.saved.extend(params if isinstance(params, list) else [params])


def sync(monkeypatch, table, extra, *, missing=()):
    columns = ["institute_id", "patient_id", "visit_id", "document_id", "record_content",
               "record_time", *[f for f in FIELDS[table] if f not in missing]]
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: (
        "cdm", columns, ["institute_id", "patient_id", "visit_id", "document_id"],
    ))
    session = CaptureOnlySession()
    source = {
        "institute_id": "H", "patient_id": "P", "visit_id": "V", "document_id": "D",
        "record_time": "2026-10-20 09:00:00", "record_content": "合成病程正文。", **extra,
    }
    count = etl_sync.upsert_to_local(table, [source], [], session=session)
    assert count == 1
    return session.saved[0]


@pytest.mark.parametrize("table,field", PAIRS)
def test_source_signature_is_preserved_in_actual_insert_params(monkeypatch, table, field):
    value = TIME if field.endswith("_datetime") else "合成签署人"
    saved = sync(monkeypatch, table, {field: value})
    assert saved[field] == value
    assert saved["record_content"] == "合成病程正文。"
    for other in FIELDS[table]:
        if other != field:
            assert other not in saved  # 不用上级、主治或提交人自动补造记录医师签名。


@pytest.mark.parametrize("table,field", PAIRS)
def test_nonempty_signature_cannot_be_silently_filtered_if_database_is_old(monkeypatch, table, field):
    value = TIME if field.endswith("_datetime") else "合成签署人"
    with pytest.raises(ValueError, match=rf"{table}.*{field}.*升级"):
        sync(monkeypatch, table, {field: value}, missing=(field,))


@pytest.mark.parametrize("table", FIELDS)
@pytest.mark.parametrize("alias", ("physician_sign_time", "physician_sign_datetime"))
def test_source_signature_time_alias_keeps_timezone(monkeypatch, table, alias):
    saved = sync(monkeypatch, table, {alias: TIME})
    assert saved["physician_sign_datetime"] == TIME
    assert saved["physician_sign_datetime"].tzinfo is timezone.utc


def test_senior_signature_time_alias_keeps_role(monkeypatch):
    saved = sync(monkeypatch, "senior_course_record", {"seniorphy_sign_time": TIME})
    assert saved["seniorphy_sign_datetime"] == TIME
    assert not saved.get("physician_sign_datetime")


@pytest.mark.parametrize("table", FIELDS)
@pytest.mark.parametrize("value", (None, "", "  "))
def test_empty_source_signature_does_not_invent_a_signature_or_block_old_schema(monkeypatch, table, value):
    saved = sync(monkeypatch, table, {"physician_sign": value, "submitter": "合成录入人"},
                 missing=FIELDS[table])
    assert not saved.get("physician_sign")


@pytest.mark.parametrize("table", FIELDS)
def test_explicit_target_signature_time_is_not_overwritten_by_alias(monkeypatch, table):
    saved = sync(monkeypatch, table, {
        "physician_sign_datetime": TIME, "physician_sign_time": "2026-10-19T09:00:00+08:00",
    })
    assert saved["physician_sign_datetime"] == TIME


@pytest.mark.parametrize("field,role", (
    ("physician_sign", "physician"), ("recorder_sign", "recorder"),
    ("attending_physician_sign", "attending_physician"), ("senior_physician_sign", "senior_physician"),
))
def test_saved_signature_role_reaches_bundle_and_render_metadata(monkeypatch, field, role):
    saved = sync(monkeypatch, "senior_course_record", {field: "合成签署人"})
    entry = _inventory_entry(table_name="senior_course_record", row=saved)
    doc = _normalize_source_document(raw_doc=entry, index=1, execution_domain="course")
    metadata = build_render_view(doc)["document_meta"]
    signatures = metadata["signatures"]
    assert any(s["source_field"] == field and s["role"] == role and s["name"] == "合成签署人"
               for s in signatures)


def test_senior_signature_time_is_attached_only_to_its_own_signature(monkeypatch):
    saved = sync(monkeypatch, "senior_course_record", {
        "senior_physician_sign": "合成上级", "seniorphy_sign_time": TIME,
        "physician_sign": "合成记录医师", "recorder_sign": "合成记录人",
    })
    signatures = _inventory_entry(table_name="senior_course_record", row=saved)["signatures"]
    upper = next(s for s in signatures if s["source_field"] == "senior_physician_sign")
    assert upper["signed_at"] == str(TIME)
    assert all("signed_at" not in s for s in signatures if s["source_field"] != "senior_physician_sign")


def test_postoperative_surgeon_signature_remains_a_separate_role_in_bundle_and_render(monkeypatch):
    saved = sync(monkeypatch, "postsurg_firstcourse_record", {"surgeon_sign": "合成术者"})
    assert "physician_sign" not in saved
    entry = _inventory_entry(table_name="postsurg_firstcourse_record", row=saved)
    doc = _normalize_source_document(raw_doc=entry, index=1, execution_domain="course")
    signatures = build_render_view(doc)["document_meta"]["signatures"]
    assert [(s["role"], s["source_field"]) for s in signatures] == [("surgeon", "surgeon_sign")]


def test_models_define_nullable_signatures_and_timezone_aware_times_without_changing_primary_keys():
    for model in (DailyCourseRecord, SeniorCourseRecord, PostsurgFirstcourseRecord):
        table = model.__table__
        for field in FIELDS[table.name]:
            assert field in table.c
            assert table.c[field].nullable
            if field.endswith("_datetime"):
                assert table.c[field].type.timezone
        assert set(table.primary_key.columns.keys()) == {"institute_id", "patient_id", "visit_id", "document_id"}
