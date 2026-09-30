"""出院诊疗经过待验收：正式入口拒绝，样本显式执行/保存/读取及导出。"""
import json
from io import BytesIO

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain
from tests.unit.test_luxian_0609_discharge_course_content import TEXT, payload
from app.services.luxian_0609.extended_document.discharge_course_content import RULE_ID
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows

_isolated_database = chain._isolated_database


@pytest.mark.parametrize("missing,event_state,failed", [
    (None, None, None), ("treatment", None, None), (None, "present", None),
    (None, "missing", None), (None, "uncertain", None), ("treatment", "present", "B"),
])
def test_discharge_course_acceptance_entry_storage_and_read(monkeypatch, _isolated_database, missing, event_state, failed):
    engine, workspace = _isolated_database
    pools = chain._install_sample_pool_sqlite(monkeypatch, engine)
    original = chain.luxian_execution.build_luxian_0609_evidence_read_session

    def read_rows(**kwargs):
        source = kwargs["source_key"]
        rows = [{"document_id": "discharge-chain", "treatment_course": TEXT}] if source == "discharge_record" else []
        if event_state and source == "discharge_record":
            rows[0]["treatment_course"] += "腹腔镜胆囊切除术。"
        if event_state and source == "surgery_record":
            rows = [{"document_id": "surgery-chain", "surgery_name": "腹腔镜胆囊切除术。"}]
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)

    monkeypatch.setattr(chain.luxian_execution, "build_luxian_0609_evidence_read_session",
                        lambda **kwargs: original(**kwargs, row_reader=read_rows))
    calls = []

    async def generate(_self, prompt, **kwargs):
        calls.append(prompt)
        assert "lx0609-discharge-course-v4" in prompt
        stage = prompt.splitlines()[0][-1]
        if stage == failed:
            raise TimeoutError()
        return {"content": json.dumps(payload(missing=missing, surgery=bool(event_state), event_state=event_state)[stage], ensure_ascii=False),
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}

    monkeypatch.setattr(chain.sichuan_qc_service.SichuanQCLLMClient, "generate", generate)
    service = chain.sichuan_qc_service.SichuanQCService({
        "provider_code": "isolated", "model": "stub", "allow_mock_when_unconfigured": True,
    })
    chain._wire_production_entry(monkeypatch, workspace, pools, chain._settings(), service)
    app = chain._api_app(service)
    pool_id, sample_id = chain._create_ready_sample_pool(engine, pools)
    checked = []

    def verify(job_id, job, _ids):
        assert job["status"] == "completed", job.get("error_message")
        item = chain._items_for_visit(job, chain._RECORD_A["visit_id"])[RULE_ID]
        expected = "non_compliant" if missing or event_state == "missing" else "data_gap" if event_state == "uncertain" or failed else "compliant"
        assert item["status"] == expected
        latest = chain._read_canonical(app, job_id, chain._RECORD_A, [RULE_ID])[RULE_ID]
        assert chain._business_content(latest) == chain._business_content(item)
        table = workspace._record_result_envelope_table
        with engine.connect() as connection:
            rows = connection.execute(sa.select(table).where(table.c.job_id == job_id)).mappings().all()
        for row in rows:
            saved = json.loads(row["envelope_json"])["items"][0]
            assert saved["customer_display_facts"] == item["customer_display_facts"]
            assert saved["status"] == item["status"]
            assert saved["suggestion"] == item["suggestion"]
        with TestClient(app) as client:
            response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
            assert response.status_code == 200, response.text
            for detail in response.json()["data"]["items"]:
                assert detail["customer_display_facts"] == item["customer_display_facts"]
            base = f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/export"
            exported = [client.get(base, params={"format": fmt}) for fmt in ("html", "csv", "xlsx")]
            assert all(response.status_code == 200 for response in exported)
            workbook = load_workbook(BytesIO(exported[2].content), read_only=True)
            workbook_text = "\n".join(str(value) for sheet in workbook.worksheets
                                      for row in sheet.iter_rows(values_only=True)
                                      for value in row if value is not None)
            workbook.close()
            for text in (latest["conclusion"], latest["suggestion"]):
                assert all(line in exported[0].text for line in text.split("\n"))
                assert text in exported[1].text and text in workbook_text
        checked.append(job_id)

    with TestClient(app) as client:
        for records in ([chain._RECORD_A], [chain._RECORD_A, chain._RECORD_B]):
            rejected = client.post("/api/v1/qc/sichuan/workspace/batch-jobs", json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "rule_ids": [RULE_ID], "scope": "final", "record_refs": records,
            })
            assert rejected.status_code == 422
        assert calls == []
        response = client.post(f"/api/v1/qc/sample-pools/{pool_id}/run", json={
            "validation_mode": "customer", "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
            "selected_rule_ids": [RULE_ID], "sample_item_ids": [sample_id],
            "record_refs": [chain._RECORD_A], "group_by_luxian_family": False,
        })
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["job_id"]
    verify(job_id, chain._wait_for_terminal_job(workspace, job_id), (RULE_ID,))
    assert len(checked) == 1
    assert len(calls) == (3 if event_state and failed != "B" else 2)
