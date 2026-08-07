from app.services.bundles import assembly as assembly_module
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


def test_resync_should_refresh_bundle_projections_while_lx0609_reads_same_cdm_rows_directly(
    monkeypatch,
):
    """Bundle 刷新只更新展示投影；Native MaterialStore 仍直接读取 CDM。"""

    cdm_rows = {
        "daily_course_record": [
            {
                "document_id": "COURSE-1",
                "record_time": "2026-08-01 09:00:00",
                "record_content": "首次病程。",
            }
        ]
    }
    scene_writes: dict[str, list[dict]] = {"running": [], "final": []}
    domain_writes: dict[str, list[dict]] = {"course": []}

    def _select_records(**kwargs):
        return list(cdm_rows.get(kwargs["table"], []))

    def _save_scene(**kwargs):
        scene = kwargs["scene"]
        scene_writes[scene].append(
            {
                "write_sequence": len(scene_writes[scene]) + 1,
                "bundle": kwargs["bundle"],
            }
        )

    def _save_domain(**kwargs):
        domain = kwargs["execution_domain"]
        domain_writes[domain].append(
            {
                "write_sequence": len(domain_writes[domain]) + 1,
                "bundle": kwargs["bundle"],
            }
        )

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "ensure_scene_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "ensure_domain_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "mark_bundle_refresh_success", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "_upsert_scene_bundle", _save_scene)
    monkeypatch.setattr(assembly_module, "_upsert_domain_bundle", _save_domain)

    refresh_kwargs = {
        "rows": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
        "source_schema": "cdm",
        "scenes": ("running", "final"),
        "domains": ("course",),
    }
    first_refresh = assembly_module.refresh_all_bundle_variants_for_rows(**refresh_kwargs)
    cdm_rows["daily_course_record"].append(
        {
            "document_id": "COURSE-2",
            "record_time": "2026-08-01 10:00:00",
            "record_content": "同步后新增病程。",
        }
    )
    second_refresh = assembly_module.refresh_all_bundle_variants_for_rows(**refresh_kwargs)

    assert first_refresh["scenes"]["running"]["updated"] == 1
    assert second_refresh["domains"]["course"]["updated"] == 1
    for scene in ("running", "final"):
        assert [item["write_sequence"] for item in scene_writes[scene]] == [1, 2]
        documents = scene_writes[scene][-1]["bundle"]["structured_context"]["documents"]
        assert [item["text_preview"] for item in documents["daily_course_record"]] == [
            "首次病程。",
            "同步后新增病程。",
        ]
    assert [item["write_sequence"] for item in domain_writes["course"]] == [1, 2]
    assert {
        item["document_id"]
        for item in domain_writes["course"][-1]["bundle"]["source_documents"]
    } >= {"COURSE-1", "COURSE-2"}

    def _read_luxian_source(**kwargs):
        source_key = kwargs["source_key"]
        rows = cdm_rows["daily_course_record"] if source_key == "daily_course_record" else []
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=100,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-009",),
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
        created_at="2026-08-01T10:01:00+08:00",
        evaluation_as_of_date="2026-08-01",
        row_reader=_read_luxian_source,
    )

    assert [item["document_id"] for item in session.materials.rows("daily_course_record")] == [
        "COURSE-1",
        "COURSE-2",
    ]
