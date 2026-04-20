from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    classify_manual_issue_text,
)


def test_classify_first_course_intrinsic_issue():
    result = classify_manual_issue_text("首次病程记录鉴别诊断不全面")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "first_course_reasoning"
    assert "SC-026" in result["candidate_rule_ids"]
    assert result["include_in_batch_1"] is True


def test_classify_programmatic_issue():
    result = classify_manual_issue_text("未及时书写日常病程记录及上级医师查房记录")
    assert result["coverage_type"] == "programmatic"
    assert result["include_in_batch_1"] is False
    assert result["candidate_rule_ids"] == []


def test_classify_consultation_execution_issue():
    result = classify_manual_issue_text("会诊意见未在病程中落实")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consultation_execution"
    assert result["candidate_rule_ids"] == ["SC-070"]


def test_resolve_sync_table_names_defaults_cover_core_groups():
    result = CustomQCSamplePoolService.resolve_sync_table_names()
    assert "core_8" in result["group_ids"]
    assert "document_extended" in result["group_ids"]
    assert "mr" in result["table_names"]
    assert "admission_record" in result["table_names"]
    assert result["missing_group_ids"] == []


def test_sync_pool_records_aggregates_rows_and_refreshes_running_bundle(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)

    monkeypatch.setattr(
        service,
        "_list_sync_candidate_items",
        lambda **_: [
            {"id": "item-1", "mr_no": "ZY001", "patient_name": "张三", "department": "普外科", "qc_date": "2026-04-20"},
        ],
    )
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "visit_keys": [("P001", "V001")],
        },
    )
    monkeypatch.setattr(
        service,
        "match_pool_items",
        lambda **_: {
            "pool": {"id": "pool-1", "matched_items": 1, "ready_items": 1},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        },
    )

    monkeypatch.setattr(
        sample_pool_module,
        "list_sync_tables",
        lambda: [
            {"name": "mr", "source_table": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "admission_record", "source_table": "admission_record", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "daily_course_record", "source_table": "daily_course_record", "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"]},
        ],
    )
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(sample_pool_module, "load_db_config", lambda: {"remote_schema": "public"})

    rows_by_table = {
        "mr": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}],
        "admission_record": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}],
        "daily_course_record": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001", "document_id": "D1"}],
    }
    monkeypatch.setattr(
        sample_pool_module,
        "fetch_remote_rows_by_visit_keys",
        lambda **kwargs: list(rows_by_table.get(kwargs["source_table"], [])),
    )
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))

    ingest_calls = []
    refresh_calls = []
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: ingest_calls.append(kwargs))
    monkeypatch.setattr(sample_pool_module, "refresh_scene_bundles_for_rows", lambda **kwargs: refresh_calls.append(kwargs))

    result = service.sync_pool_records(
        pool_id="pool-1",
        only_intrinsic=True,
        include_in_batch_1=True,
        table_groups=["core_8"],
    )

    assert result["eligible_visits"] == 1
    assert result["matched"] == 1
    assert result["total_rows_pulled"] == 3
    assert result["total_rows_upserted"] == 3
    assert [item["table_name"] for item in result["synced_tables"]] == ["mr", "admission_record", "daily_course_record"]
    assert len(ingest_calls) == 2
    assert len(refresh_calls) == 2
