"""复用正式三入口合成会诊验收，附加诊断旁路；不连客户库或真实模型。"""

import pytest

from app.services.qc_diagnostics.job_capture import DiagnosticJobCapture
from tests.integration import test_luxian_0609_consultation_business_entry_flow as flow


@pytest.mark.asyncio
async def test_selected_capture_crosses_formal_worker_and_canonical_commit(monkeypatch, tmp_path):
    original_worker = flow.batch_worker.run_sichuan_workspace_batch_job
    delivered = []
    captures = []
    async def run_with_capture(job_id, **kwargs):
        capture = DiagnosticJobCapture(job_id=job_id,
            record_identity=tuple(flow._RECORD_A[key] for key in ("institute_id", "patient_id", "visit_id")),
            consume=lambda data, summary: delivered.append((data, summary)))
        captures.append(capture)
        await original_worker(job_id, diagnostic_capture=capture, **kwargs)
    monkeypatch.setattr(flow.batch_worker, "run_sichuan_workspace_batch_job", run_with_capture)
    try:
        # 原有跨三入口状态、原因、事实、证据与实际 Canonical 保存断言全部保留。
        await flow.test_consultation_quality_formal_worker_is_consistent_across_three_business_entries(monkeypatch, tmp_path)
        assert len(delivered) == 3, [capture.summary() for capture in captures]
        for data, summary in delivered:
            assert data["execution_inputs"]["selected_rule_ids"] == (flow.RULE_ID,)
            assert data["execution_context"]["medical_text"] == "脱敏病历摘要"
            assert data["execution_context"]["runtime_settings"]["LUXIAN_0609_UNIFIED_ENGINE_ENABLED"] is True
            assert data["saved_result"]["record_id"] == flow._RECORD_A["visit_id"]
            assert len(data["saved_result"]["items"]) == 1
            assert data["saved_result"]["items"][0]["status"] == "compliant"
            assert "final_result_not_captured" not in summary["missing_reasons"]
            assert "case_context_mismatch" not in summary["missing_reasons"]
        assert all(capture.summary()["retained_bytes"] == 0 for capture in captures)
    finally:
        flow.workspace_module._drafts_table.cache_clear()
        flow.workspace_module._batch_jobs_table.cache_clear()
        flow.workspace_module._record_result_envelopes_table.cache_clear()
