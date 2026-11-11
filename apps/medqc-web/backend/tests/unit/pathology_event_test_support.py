"""从622054815抽取的合成夹具；不引入未整合台账规则的测试。"""
from test_luxian_0609_death_record_timeliness import saved_roundtrip


RUNNING = {"institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "running",
           "evaluation_horizon": "2026-06-10", "evaluation_basis": "task_frozen_date", "resolution_status": "resolved"}


def _session(rule, rows, *, day="2026-06-10", executor="extended_document"):
    from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=tuple(rows.get(key, ())), truncated=False, limit_rows=50)

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at=day + "T12:00:00+08:00", row_reader=reader, evaluation_as_of_date=day,
        evaluation_horizon_policy="frozen_task_date", evaluation_horizon_snapshot={**RUNNING, "evaluation_horizon": day},
        additional_source_keys=resolve_legacy_executor_material_source_keys((executor,), selected_rule_ids=(rule,)),
    )


def _loaded(final):
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == (final["status"], final["reason_code"])
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    assert loaded.get("findings") == final.get("findings")
    return loaded


def _pathology_master(pid, day, specimen="胃窦组织"):
    return {"pathology_exam_id": pid, "specimen_name": specimen, "request_datetime": f"2026-06-{day:02d} 08:00:00"}


def _pathology_report(pid, day, specimen="胃窦"):
    return {"pathology_exam_id": pid, "diagnosis": f"（{specimen}）慢性炎", "report_datetime": f"2026-06-{day:02d} 10:00:00"}
