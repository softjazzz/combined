"""指定历史任务的部分结果入口：同病例先有部分失败任务 A，后有任务 B。

1026 复盘：单病例部分失败任务没有 Canonical Envelope，任务详情（前端任务历史
“查看”按钮）因而 0 条；latest-result 不接受 job_id、按三坐标取最新任务，B 出现
后 A 的已保存结果在任何受控入口都不可达。

本文件只用合成数据与隔离 SQLite，经正式链路生成 A，再按 A 的持久行复制出更新
的 B（只换任务 ID 与时间）。期望：

- 任务详情按 job_id 只读 A 自身已保存、通过逐条合同校验的成功项，并保留失败规则
  身份与 partial_failed 标记；B 出现前后 A 的详情一致，不切换到 B；
- 不写 Envelope、不改任务状态；
- 越权：其他账号读 A 详情 404；其他机构账号读 latest-result 403。
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

import app.services.saved_result_access as access_module
from app.routers import qc_sichuan
from tests.unit import test_luxian_0609_not_applicable_receipt_chain as receipt_chain
from tests.unit.test_luxian_0609_not_applicable_receipt_chain import (
    test_partial_failed_task_reads_saved_items_with_receipts_through_controlled_contract as _make_partial_a,
)


def _request(trace: str) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(trace_id=trace))


async def _partial_task_a(monkeypatch, tmp_path, request) -> SimpleNamespace:
    """复用既有部分失败场景构造 A，并取回其链路对象。"""

    captured: dict = {}
    original = receipt_chain._run_not_applicable

    async def _capture(*args, **kwargs):
        chain = await original(*args, **kwargs)
        captured["chain"] = chain
        return chain

    monkeypatch.setattr(receipt_chain, "_run_not_applicable", _capture)
    await _make_partial_a(monkeypatch, tmp_path, request)
    return captured["chain"]


def _copy_as_newer_task(chain: SimpleNamespace, new_id: str) -> None:
    """B 与 A 可区分：B 两条规则均技术失败、没有已保存成功项。"""

    table = chain.workspace._batch_job_table
    with chain.engine.begin() as connection:
        row = dict(connection.execute(select(table).where(table.c.id == chain.job_id)).mappings().one())
        [failure] = json.loads(row["failed_records_json"])
        [saved] = json.loads(row["items_json"])
        both_failed = [failure, {**failure, "rule_id": saved["rule_id"], "rule_code": saved["rule_id"]}]
        row.update(items_json="[]", failed_records_json=json.dumps(both_failed, ensure_ascii=False))
        # B 必须严格晚于 A 的真实完成时间（A 的 finished_at 由正式完成入口写入）。
        anchor = max(value for value in (row.get("finished_at"), row.get("created_at")) if value)
        later = anchor + timedelta(hours=1)
        row.update(id=new_id, created_at=later, updated_at=later, finished_at=later + timedelta(minutes=5))
        for key in ("idempotency_key", "dispatch_key"):
            if key in row and row[key]:
                row[key] = f"{row[key]}-b"
        connection.execute(table.insert().values(**row))


def _persisted_state(chain: SimpleNamespace) -> tuple:
    jobs, envelopes = chain.workspace._batch_job_table, chain.envelope_table
    with chain.engine.connect() as connection:
        job_row = connection.execute(
            select(jobs.c.status, jobs.c.items_json, jobs.c.summary_json, jobs.c.updated_at)
            .where(jobs.c.id == chain.job_id)
        ).one()
        envelope_count = connection.execute(select(func.count()).select_from(envelopes)).scalar_one()
    return tuple(job_row), envelope_count


async def _detail(job_id: str, user: str) -> dict:
    return (await qc_sichuan.get_workspace_batch_job(
        request=_request(f"history-{user}"), job_id=job_id, current_user={"id": user},
    ))["data"]


@pytest.mark.asyncio
async def test_history_task_detail_reads_its_own_saved_partial_results_after_newer_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest,
) -> None:
    chain = await _partial_task_a(monkeypatch, tmp_path, request)
    job_a = chain.job_id
    material = chain.material_fingerprints[0]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: chain.workspace)
    persisted_before = _persisted_state(chain)

    # A 的任务详情：A 自身已保存的成功项 + 失败规则身份，标为部分失败。
    data_a = await _detail(job_a, "tester")
    assert data_a["id"] == job_a and data_a["status"] == "failed"
    [item_a] = data_a["items"]
    assert item_a["status"] == "not_applicable"
    assert item_a["audit_evidence_status"] == "retained"
    assert item_a["applicability_receipt"]["material_fingerprint"] == material
    assert not {"patient_id", "visit_id", "institute_id"} & set(item_a)
    assert data_a["summary"]["execution_status"] == "partial_failed"
    assert data_a["summary"]["failed_rule_ids"] == ["LX0609-10-03-01"]
    [failure_a] = list(data_a.get("failed_records") or [])
    assert failure_a["reason_code"] == "model_invalid_output"
    assert not {"patient_id", "visit_id", "institute_id"} & set(failure_a)
    # 导出保持既有合同：只含已交付（有 Envelope）的完整病例，本修复不改变导出。
    raw_a = chain.workspace.get_batch_job(job_id=job_a, created_by="tester")
    assert chain.workspace._load_batch_job_export_items(job=raw_a) == []
    # 只读：不补写 Envelope、不改任务行。
    assert _persisted_state(chain) == persisted_before

    _copy_as_newer_task(chain, "job-b-newer")

    # B 出现后：A 的详情仍只展示 A，内容不变，不静默切换为 B。
    data_a_after = await _detail(job_a, "tester")
    assert data_a_after["id"] == job_a
    assert data_a_after["items"] == data_a["items"]

    # B 自身详情：没有成功项，0 条，两条失败规则；证明 A 的详情读的不是 B。
    data_b = await _detail("job-b-newer", "tester")
    assert data_b["id"] == "job-b-newer" and data_b["items"] == []
    assert len(data_b["failed_records"]) == 2

    # latest-result 语义不变：按三坐标选最新任务（B），并显式带回 job_id。
    latest = chain.workspace.get_latest_luxian_0609_record_result(
        institute_id="I", patient_id="P", visit_id="V",
    )
    assert latest["job_id"] == "job-b-newer"
    assert latest["items"] == []

    # 越权：其他账号读取 A 详情 -> 404，不回显内容。
    with pytest.raises(HTTPException) as denied_detail:
        await _detail(job_a, "intruder")
    assert denied_detail.value.status_code == 404

    # 越权：其他机构的质控管理员读取 latest-result -> 403（函数级替身只替换账号机构来源）。
    monkeypatch.setattr(access_module, "saved_result_institute_scope", lambda actor: "OTHER")
    with pytest.raises(HTTPException) as denied_latest:
        await qc_sichuan.get_latest_workspace_record_result(
            request=_request("latest-intruder"), record_id="V", institute_id="I", patient_id="P",
            current_user={"id": "other-institute-manager"},
        )
    assert denied_latest.value.status_code == 403


@pytest.mark.asyncio
async def test_history_task_detail_rejects_tampered_saved_partial_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest,
) -> None:
    """已保存成功项与失败规则重叠时属完整性错误：明确 409，不静默展示或吞掉。"""

    chain = await _partial_task_a(monkeypatch, tmp_path, request)
    table = chain.workspace._batch_job_table
    job = chain.workspace.get_batch_job_for_processing(job_id=chain.job_id)
    [failure] = job["failed_records"]
    tampered = [{**failure, "rule_id": job["items"][0]["rule_id"], "rule_code": job["items"][0]["rule_id"]}]
    with chain.engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == chain.job_id).values(
            failed_records_json=json.dumps(tampered, ensure_ascii=False)))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: chain.workspace)
    with pytest.raises(HTTPException) as rejected:
        await _detail(chain.job_id, "tester")
    assert rejected.value.status_code == 409
