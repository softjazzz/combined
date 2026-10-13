"""SCOPE-06：真实样本入口须先验证原选择范围，再分离暂停规则。"""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from tests.integration import test_luxian_0609_release_scope as release
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    get_luxian_0609_customer_delivery_rule_ids,
)

_isolated_database = release._isolated_database
ACTIVE = "LX0609-01-01-01"
PENDING = "LX0609-06-03-01"
KEY = "luxian_0609_qc_v1"


@pytest.fixture
def entry(monkeypatch, _isolated_database):
    engine, workspace, app, pool_id, item_id = release.setup_chain(
        monkeypatch, _isolated_database
    )
    dispatches = []

    async def synthetic_config(*args, **kwargs):
        return {"provider_code": "synthetic", "model": "synthetic", "custom_parameters": {}}

    # 用户模型配置属于外部依赖；范围解析及保存层仍执行真实代码。
    monkeypatch.setattr(
        release.chain.qc_sample_pools.LLMConfigLoader, "load_config", staticmethod(synthetic_config)
    )

    def capture_dispatch(*args, **kwargs):
        # 生产入口传 callable + job_id；仅记录，绝不启动后台任务。
        dispatches.append((args, kwargs))

    monkeypatch.setattr(release.chain.qc_sample_pools, "submit_detached_task", capture_dispatch)
    payload = {
        "rule_set_key": KEY,
        "validation_mode": "customer",
        "sample_item_ids": [item_id],
        "record_refs": [dict(release.chain._RECORD_A)],
        "group_by_luxian_family": False,
    }
    with TestClient(app) as client:
        yield engine, workspace, client, pool_id, payload, dispatches


def _job_count(engine, workspace):
    with engine.connect() as connection:
        return connection.execute(
            sa.select(sa.func.count()).select_from(workspace._batch_job_table)
        ).scalar_one()


def _post(entry, selected=None):
    engine, workspace, client, pool_id, payload, dispatches = entry
    request = dict(payload)
    if selected is not None:
        request["selected_rule_ids"] = selected
    response = client.post(f"/api/v1/qc/sample-pools/{pool_id}/run", json=request)
    return response, engine, workspace, dispatches


def _assert_rejected(entry, selected, *, expected_detail):
    engine, workspace, *_ = entry
    before = _job_count(engine, workspace)
    response, _, _, dispatches = _post(entry, selected)
    after = _job_count(engine, workspace)
    # 失败信息保留实际状态/任务数，保证业务红证据不是导入或支撑错误。
    assert (response.status_code, after - before, len(dispatches)) == (422, 0, 0), (
        response.status_code, response.text, after - before, len(dispatches)
    )
    assert expected_detail in response.json()["detail"]


def _registered_paused():
    delivery = set(get_luxian_0609_customer_delivery_rule_ids())
    inventory = {item.rule_id for item in release.chain.batch_worker.load_luxian_0609_dependency_inventory()}
    paused = release.chain.qc_sample_pools._LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
    candidates = sorted(delivery & inventory & paused)
    assert candidates, "目录必须有真实已注册暂停规则以保护旧路径"
    return candidates[0]


def _filters(response, engine, workspace, dispatches):
    assert response.status_code == 200, response.text
    assert _job_count(engine, workspace) == 1
    assert len(dispatches) == 1
    job_id = response.json()["data"]["job_id"]
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    assert job is not None
    return job["filters"]


def test_unregistered_pending_plus_active_rejected_before_creation(entry):
    assert PENDING in release.chain.qc_sample_pools._LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
    assert PENDING not in get_luxian_0609_customer_delivery_rule_ids()
    with pytest.raises(ValueError, match=PENDING):
        release.chain.batch_worker._assert_luxian_0609_formal_customer_rule_ids(
            rule_set_key=KEY, rule_ids=[PENDING, ACTIVE], context="合成正式入口反例"
        )
    _assert_rejected(entry, [PENDING, ACTIVE], expected_detail=PENDING)


def test_registered_paused_plus_active_preserves_delivery_scope(entry):
    paused = _registered_paused()
    response, engine, workspace, dispatches = _post(entry, [paused, ACTIVE])
    filters = _filters(response, engine, workspace, dispatches)
    assert filters["rule_ids"] == [ACTIVE]
    assert filters["paused_customer_rule_ids"] == [paused]
    assert filters["scoped_customer_rule_ids"] == sorted([paused, ACTIVE])
    assert filters["selected_rule_ids"] == [ACTIVE]
    assert set(release.chain.batch_worker._assert_luxian_0609_formal_customer_rule_ids(
        rule_set_key=KEY, rule_ids=filters["rule_ids"] + filters["paused_customer_rule_ids"],
        context="合成正式入口正常路径",
    )) == {paused, ACTIVE}


def test_only_registered_paused_preserves_existing_422(entry):
    _assert_rejected(entry, [_registered_paused()], expected_detail="当前均暂不执行")


def test_default_scope_preserves_registered_delivery_and_release_freeze(entry):
    response, engine, workspace, dispatches = _post(entry)
    filters = _filters(response, engine, workspace, dispatches)
    expected_delivery = set(get_luxian_0609_customer_delivery_rule_ids()) - release.PILOTS
    expected_paused = expected_delivery & release.chain.qc_sample_pools._LUXIAN_0609_PAUSED_CUSTOMER_RULE_IDS
    assert set(filters["scoped_customer_rule_ids"]) == expected_delivery
    assert set(filters["paused_customer_rule_ids"]) == expected_paused
    assert set(filters["rule_ids"]) == expected_delivery - expected_paused
    assert filters["selected_rule_ids"] == []
    assert PENDING not in filters["scoped_customer_rule_ids"]


def test_customer_excluded_plus_active_cannot_use_master_as_allowlist(entry):
    excluded = sorted(LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS)[0]
    assert excluded not in get_luxian_0609_customer_delivery_rule_ids()
    _assert_rejected(entry, [excluded, ACTIVE], expected_detail=excluded)


def test_unknown_plus_active_still_rejected(entry):
    _assert_rejected(entry, ["LX0609-99-99-99", ACTIVE], expected_detail="LX0609-99-99-99")
