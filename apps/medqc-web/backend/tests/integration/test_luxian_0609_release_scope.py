"""发布范围只影响新任务，保存计划独立于运行时默认配置。"""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from dataclasses import replace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain
from app.services.luxian_0609.phase_scope import (
    frozen_luxian_0609_delivery_scope,
    get_luxian_0609_acceptance_only_rule_ids,
)
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
)

_isolated_database = chain._isolated_database

PILOTS = {
    "LX0609-06-01-01",
    "LX0609-06-01-03",
    "LX0609-06-02-01",
    "LX0609-06-03-02",
    "LX0609-09-01-02",
}


def test_master_and_recovery():
    assert get_luxian_0609_acceptance_only_rule_ids() == PILOTS
    entry = next(e for e in load_luxian_0609_rule_master() if e.rule_id in PILOTS)
    for changes in (
        {"release_scope": "unknown"},
        {"phase_status": "pending_definition", "pending_reason_code": "pending"},
    ):
        with pytest.raises(ValueError):
            replace(entry, **changes)
    assert frozen_luxian_0609_delivery_scope({"rule_ids": [entry.rule_id]}) == [
        entry.rule_id
    ]
    for invalid in (
        {},
        {"rule_ids": []},
        {"rule_ids": ["SC-001"]},
        {"rule_ids": "LX0609-01-01-01"},
    ):
        with pytest.raises(ValueError, match="新建质控任务"):
            frozen_luxian_0609_delivery_scope(invalid)


def setup_chain(monkeypatch, isolated):
    engine, workspace = isolated
    pools = chain._install_sample_pool_sqlite(monkeypatch, engine)
    chain._install_evidence_fixture(monkeypatch, consultation_row=False)
    service = chain.sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated",
            "model": "stub",
            "allow_mock_when_unconfigured": True,
        }
    )
    chain._wire_production_entry(
        monkeypatch, workspace, pools, chain._settings(), service
    )

    async def no_llm(*args, **kwargs):
        raise AssertionError("空资料不可调用模型")

    monkeypatch.setattr(chain.sichuan_qc_service.SichuanQCLLMClient, "generate", no_llm)
    pool_id, item_id = chain._create_ready_sample_pool(engine, pools)
    return engine, workspace, chain._api_app(service), pool_id, item_id


@pytest.mark.parametrize("entry", ["single", "batch", "sample"])
def test_defaults_freeze_scope(monkeypatch, _isolated_database, entry):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    for router in (chain.qc_sichuan, chain.qc_sample_pools):
        monkeypatch.setattr(
            router, "submit_detached_task", lambda *args, **kwargs: None
        )
    payload = {"rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY}
    if entry == "sample":
        url = f"/api/v1/qc/sample-pools/{pool_id}/run"
        payload.update(
            validation_mode="customer",
            sample_item_ids=[item_id],
            record_refs=[chain._RECORD_A],
            group_by_luxian_family=False,
        )
    else:
        url = "/api/v1/qc/sichuan/workspace/batch-jobs"
        payload.update(
            scope="final",
            record_refs=[chain._RECORD_A]
            if entry == "single"
            else [chain._RECORD_A, chain._RECORD_B],
        )
    with TestClient(app) as client:
        response = client.post(url, json=payload)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    job_id = data.get("job_id") or data["id"]
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    expected = set(get_luxian_0609_customer_delivery_rule_ids()) - PILOTS
    assert set(job["filters"]["scoped_customer_rule_ids"]) == expected
    assert not job["filters"].get("acceptance_only_rule_ids")
    assert not set(job["filters"]["rule_ids"]) & PILOTS
    monkeypatch.setattr(
        chain.qc_sichuan,
        "get_luxian_0609_acceptance_only_rule_ids",
        lambda: frozenset(),
    )
    asyncio.run(chain.qc_sichuan._run_sichuan_workspace_batch_job(job_id))
    job = chain._wait_for_terminal_job(workspace, job_id)
    assert job["status"] == "completed", job.get("error_message")
    assert set(chain._items_for_visit(job, chain._RECORD_A["visit_id"])) == expected
    chain._read_canonical(app, job_id, chain._RECORD_A, expected)


def test_acceptance_explicit_and_legacy_retry(monkeypatch, _isolated_database):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    selected = "LX0609-06-02-01"
    with TestClient(app) as client:
        for pilot in PILOTS:
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                    "rule_ids": [pilot],
                    "scope": "final",
                    "record_refs": [chain._RECORD_A],
                },
            )
            assert response.status_code == 422
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "validation_mode": "customer",
                "selected_rule_ids": [selected],
                "sample_item_ids": [item_id],
                "record_refs": [chain._RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["job_id"]
    job = chain._wait_for_terminal_job(workspace, job_id)
    assert job["status"] == "completed", job.get("error_message")
    assert set(chain._items_for_visit(job, chain._RECORD_A["visit_id"])) == {selected}
    chain._read_canonical(app, job_id, chain._RECORD_A, [selected])
    assert job["filters"]["acceptance_only_rule_ids"] == [selected]
    filters = dict(job["filters"])
    filters.pop("scoped_customer_rule_ids", None)
    with Session(engine) as session:
        session.execute(
            sa.update(workspace._batch_job_table)
            .where(workspace._batch_job_table.c.id == job_id)
            .values(filters_json=json.dumps(filters))
        )
        session.commit()
    retried = workspace.retry_batch_job(job_id=job_id, created_by="lx075-test-user")
    assert retried["filters"]["scoped_customer_rule_ids"] == [selected]
    assert retried["filters"]["rule_ids"] == [selected]
    filters.update(
        rule_ids=[], paused_customer_rule_ids=[], gate_only_customer_rule_ids=[]
    )
    with Session(engine) as session:
        session.execute(
            sa.update(workspace._batch_job_table)
            .where(workspace._batch_job_table.c.id == job_id)
            .values(status="failed", filters_json=json.dumps(filters))
        )
        session.commit()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/retry"
        )
    assert response.status_code == 409
    assert "新建质控任务" in response.text


@pytest.mark.parametrize("outside", [False, True])
def test_failed_retry_cannot_expand_frozen_scope(
    monkeypatch, _isolated_database, outside
):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    selected = "LX0609-06-02-01"
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "validation_mode": "customer",
                "selected_rule_ids": [selected],
                "sample_item_ids": [item_id],
                "record_refs": [chain._RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["job_id"]
    chain._wait_for_terminal_job(workspace, job_id)
    failure_id = "LX0609-06-01-01" if outside else selected
    with Session(engine) as session:
        session.execute(
            sa.update(workspace._batch_job_table)
            .where(workspace._batch_job_table.c.id == job_id)
            .values(
                status="failed",
                summary_json=json.dumps({"execution_status": "partial_failed"}),
                failed_records_json=json.dumps(
                    [
                        {
                            **chain._RECORD_A,
                            "rule_id": failure_id,
                            "error_phase": "result_status",
                        }
                    ]
                ),
            )
        )
        session.commit()
    if outside:
        with pytest.raises(ValueError, match="超出原任务冻结范围"):
            workspace.retry_batch_job(job_id=job_id, created_by="lx075-test-user")
        assert (
            workspace.get_batch_job_for_processing(job_id=job_id)["status"] == "failed"
        )
    else:
        retried = workspace.retry_batch_job(job_id=job_id, created_by="lx075-test-user")
        assert retried["filters"]["failed_rule_retry"]["rule_ids"] == [selected]
        assert retried["filters"]["scoped_customer_rule_ids"] == [selected]


def test_grouped_default_freezes_parent_and_children(monkeypatch, _isolated_database):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    monkeypatch.setattr(
        chain.qc_sample_pools, "submit_detached_task", lambda *args, **kwargs: None
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "validation_mode": "customer",
                "sample_item_ids": [item_id],
                "record_refs": [chain._RECORD_A],
                "group_by_luxian_family": True,
            },
        )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    parent = workspace.get_batch_job_for_processing(job_id=data["job_id"])
    expected = set(get_luxian_0609_customer_delivery_rule_ids()) - PILOTS
    assert set(parent["filters"]["scoped_customer_rule_ids"]) == expected
    delivered, executed = set(), set()
    for child_id in data["child_job_ids"]:
        child = workspace.get_batch_job_for_processing(job_id=child_id)
        delivered.update(child["filters"]["scoped_customer_rule_ids"])
        executed.update(child["filters"]["rule_ids"])
        assert not set(child["filters"]["rule_ids"]) & PILOTS
    assert delivered == expected
    assert len(delivered) == 74
    assert len(executed) == 64


@pytest.mark.parametrize(
    "grouped,extra", [(True, []), (False, []), (True, ["LX0609-03-01-04"])]
)
def test_explicit_paused_family_completes_parent(
    monkeypatch, _isolated_database, grouped, extra
):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    selected = ["LX0609-01-01-01", "LX0609-06-01-03", "LX0609-03-01-01", *extra]
    monkeypatch.setattr(
        chain.qc_sample_pools, "submit_detached_task", lambda *args, **kwargs: None
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "validation_mode": "customer",
                "selected_rule_ids": selected,
                "sample_item_ids": [item_id],
                "record_refs": [chain._RECORD_A],
                "group_by_luxian_family": grouped,
            },
        )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    job_id = data["job_id"]
    children = data.get("child_job_ids") or []
    if children:
        scopes = [
            workspace.get_batch_job_for_processing(job_id=cid)["filters"][
                "scoped_customer_rule_ids"
            ]
            for cid in children
        ]
        assert {rid for scope in scopes for rid in scope} == set(selected)
        assert sum(len(scope) for scope in scopes) == len(selected)
    for target in children or [job_id]:
        asyncio.run(chain.qc_sichuan._run_sichuan_workspace_batch_job(target))
    if children:
        workspace.refresh_parent_batch_job(parent_job_id=job_id)
    result = workspace.get_batch_job_for_processing(job_id=job_id)
    assert result["status"] == "completed", result.get("error_message")
    items = chain._read_canonical(app, job_id, chain._RECORD_A, selected)
    assert items["LX0609-03-01-01"]["status"] == "not_executed"
    with TestClient(app) as client:
        public = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}").json()[
            "data"
        ]
    assert "filters" not in public
    assert public["acceptance_only_rule_ids"] == ["LX0609-06-01-03"]
    _assert_frontend_scope(public, ["LX0609-06-01-03"])
    for child in public.get("child_jobs", []):
        assert "filters" not in child
        _assert_frontend_scope(child, child["acceptance_only_rule_ids"])


def _assert_frontend_scope(public, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("正式DTO到前端摘要验证需要Node")
    app_root = Path(__file__).resolve().parents[3]
    script = """
import { buildBatchJobPresentation } from './src/views/workstation-v4/customer-sample-validation/batchJobPresentation.ts';
let input = ''; for await (const chunk of process.stdin) input += chunk;
process.stdout.write(JSON.stringify(buildBatchJobPresentation(JSON.parse(input)).scopeText));
"""
    result = subprocess.run(
        [node, "--import", "tsx", "--input-type=module", "-e", script],
        cwd=app_root,
        input=json.dumps(public),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=True,
    )
    text = json.loads(result.stdout)
    assert ("待验收" in text) == bool(expected), text
    if expected:
        assert f"待验收 {len(expected)} 条" in text


@pytest.mark.parametrize(
    "snapshot,expected",
    [(None, []), ([], []), (["LX0609-06-02-01"], ["LX0609-06-02-01"])],
)
def test_public_task_snapshot_reaches_frontend(
    monkeypatch, _isolated_database, snapshot, expected
):
    engine, workspace, app, pool_id, item_id = setup_chain(
        monkeypatch, _isolated_database
    )
    monkeypatch.setattr(
        chain.qc_sample_pools, "submit_detached_task", lambda *args, **kwargs: None
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "rule_set_key": chain.LUXIAN_0609_RULE_SET_KEY,
                "validation_mode": "customer",
                "selected_rule_ids": expected or ["LX0609-01-01-01"],
                "sample_item_ids": [item_id],
                "record_refs": [chain._RECORD_A],
                "group_by_luxian_family": False,
            },
        )
        assert response.status_code == 200, response.text
        job_id = response.json()["data"]["job_id"]
        if snapshot is None:
            filters = workspace.get_batch_job_for_processing(job_id=job_id)["filters"]
            filters.pop("acceptance_only_rule_ids", None)
            with Session(engine) as session:
                session.execute(
                    sa.update(workspace._batch_job_table)
                    .where(workspace._batch_job_table.c.id == job_id)
                    .values(filters_json=json.dumps(filters))
                )
                session.commit()
        public = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}").json()[
            "data"
        ]
    assert "filters" not in public
    assert public["acceptance_only_rule_ids"] == expected
    _assert_frontend_scope(public, expected)
