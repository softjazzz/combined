"""当前文书独立验收：真实组装器，只替换本地数据读取边界。"""
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.bundles import assembly, current_view, emr_view


IDENTITY = {"institute_id": "TEST", "patient_id": "TEST-P", "visit_id": "TEST-V"}
REGISTRATION_TIME = "2026-02-02 10:00:00"
ADMISSION_TIME = "2026-02-02 10:01:00"


@pytest.fixture
def local_data(monkeypatch):
    rows = {
        "inpat_registration": [{**IDENTITY, "admission_datetime": REGISTRATION_TIME}],
        "admission_record": [{
            **IDENTITY, "document_id": "TEST-D", "admission_datetime": ADMISSION_TIME,
            "record_time": "2026-02-02 10:07:26", "update_time": "2026-02-02 10:07:26",
            "chief_complaint": "测试正文甲",
        }],
    }
    reads = Mock(side_effect=lambda **kw: deepcopy(rows.get(kw["table"], [])))
    monkeypatch.setattr(assembly, "engine", object())
    monkeypatch.setattr(assembly, "_select_records", reads)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda schema, table: set().union(
        *(r.keys() for r in rows.get(table, []))))
    forbidden = Mock(side_effect=AssertionError("不得读取或写入持久化 Bundle"))
    for module, names in (
        (assembly, ("load_domain_bundle", "load_or_assemble_domain_bundle", "_upsert_domain_bundle")),
        (emr_view, ("load_domain_bundle", "load_or_assemble_domain_bundle", "load_bundle_documents")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    yield rows, reads, forbidden
    assert not current_view._pending


def test_current_assembly_prefers_original_pg_and_removes_pdf_version(local_data, monkeypatch):
    rows, _, _ = local_data
    original = dict(doc_type="pdf_candidate", document_id="PDF-SYN", doc_key="pdf_candidate::PDF-SYN",
                    doc_name="PDF候选", document_title="PDF候选", content="单独保留的PDF正文", has_content=True,
                    _review_reference=dict(target_table="admission_record", target_document_id="TEST-D", original_title="PDF候选", differences=["body_version_difference"]))
    monkeypatch.setattr(current_view, "material_review_documents", lambda **identity: [deepcopy(original)])
    monkeypatch.setattr(current_view, "material_pg_preference_reviews", lambda **identity: {"PDF-SYN": {"decision": "remove_pdf_duplicate", "original_pg_ids": ["TEST-D"]}})
    payload = current_view.load_current_documents(**IDENTITY)
    assert not any(document["document_id"] == "PDF-SYN" for document in payload["documents"])
    assert any(document["document_id"] == "TEST-D" for document in payload["documents"])
    assert original["content"] == "单独保留的PDF正文"
    assert rows["admission_record"][0]["chief_complaint"] == "测试正文甲"


def test_current_body_changes_without_timestamp_or_saved_bundle_update(local_data):
    rows, reads, forbidden = local_data
    before = current_view.load_current_documents(**IDENTITY)
    timestamp = rows["admission_record"][0]["update_time"]
    rows["admission_record"][0]["chief_complaint"] = "测试正文乙"
    after = current_view.load_current_documents(**IDENTITY)
    def body(payload):
        return next(d["content"] for d in payload["documents"] if d["doc_type"] == "admission_record")
    assert "测试正文甲" in body(before)
    assert "测试正文乙" in body(after)
    assert "测试正文甲" not in body(after)
    assert rows["admission_record"][0]["update_time"] == timestamp
    assert sum(c.kwargs["table"] == "admission_record" for c in reads.call_args_list) == 2
    forbidden.assert_not_called()


@pytest.mark.parametrize("registration,admission,expected,source", [
    (REGISTRATION_TIME, ADMISSION_TIME, REGISTRATION_TIME, "inpat_registration"),
    (None, ADMISSION_TIME, ADMISSION_TIME, "admission_record"),
    (None, None, "", ""),
])
def test_current_admission_anchor_priority(local_data, registration, admission, expected, source):
    rows, _, _ = local_data
    rows["inpat_registration"][0]["admission_datetime"] = registration
    rows["admission_record"][0]["admission_datetime"] = admission
    record = current_view.load_current_documents(**IDENTITY)["current_record"]
    assert record["admission_time"].replace("T", " ").removesuffix("+08:00") == expected
    assert record["admission_time_source"] == source


def test_read_failure_raises_without_stale_fallback(local_data):
    _, reads, forbidden = local_data
    reads.side_effect = RuntimeError("synthetic unavailable")
    with pytest.raises(RuntimeError, match="current_document_source_read_failed"):
        current_view.load_current_documents(**IDENTITY)
    forbidden.assert_not_called()


def test_concurrent_requests_share_only_inflight_assembly(local_data, monkeypatch):
    entered, release, follower_waiting = Event(), Event(), Event()
    actual_assemble = current_view._assemble_current_documents
    calls = []

    def blocked_assemble(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return actual_assemble(**kwargs)

    class ObservedFuture(Future):
        def result(self, timeout=None):
            if not self.done():
                follower_waiting.set()
            return super().result(timeout=timeout)

    monkeypatch.setattr(current_view, "Future", ObservedFuture)
    monkeypatch.setattr(current_view, "_assemble_current_documents", blocked_assemble)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(current_view.load_current_documents, **IDENTITY)
        try:
            assert entered.wait(5)
            second = pool.submit(current_view.load_current_documents, **IDENTITY)
            assert follower_waiting.wait(5)
        finally:
            release.set()
        first_result, second_result = first.result(5), second.result(5)
    assert len(calls) == 1
    assert first_result == second_result
    first_result["documents"].clear()
    assert second_result["documents"]
    current_view.load_current_documents(**IDENTITY)
    assert len(calls) == 2


@pytest.fixture
def route_client():
    from app.routers import emr_render
    app = FastAPI()
    app.include_router(emr_render.router)
    for dependency in emr_render.router.dependencies:
        app.dependency_overrides[dependency.dependency] = lambda: {}
    app.dependency_overrides[emr_render.get_current_user] = lambda: {
        "id": "tester",
        "role": "super_admin",
    }
    with TestClient(app) as client:
        yield client, emr_render


def test_cdm_default_browse_assembles_and_renders_without_persistent_bundle(local_data, route_client, monkeypatch):
    from app.database import clinical_connection
    client, _ = route_client
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: object())
    # 真实装配器/目录投影/Renderer，仅临床行读取替换为合成材料。
    response = client.get("/api/v1/emr/TEST-V/documents", params={**IDENTITY,
        "view": "summary", "execution_domain": "admission"})
    assert response.status_code == 200
    document = next(d for d in response.json()["data"]["documents"] if d["document_id"] == "TEST-D")
    assert "content" not in document
    response = client.get("/api/v1/emr/TEST-V/render", params={**IDENTITY,
        "doc_type": document["doc_type"], "doc_id": document["document_id"],
        "execution_domain": document["execution_domain"]})
    assert response.status_code == 200
    assert "测试正文甲" in response.json()["data"]["content"]
    local_data[2].assert_not_called()


def test_current_endpoint_fails_503_instead_of_returning_saved(route_client, monkeypatch):
    client, route = route_client
    monkeypatch.setattr(route, "load_current_documents", Mock(side_effect=RuntimeError("synthetic")))
    saved = Mock(side_effect=AssertionError("旧路径不得使用"))
    monkeypatch.setattr(route, "_load_documents_from_bundle", saved)
    response = client.get("/api/v1/emr/TEST-V/documents", params={**IDENTITY, "source_view": "current"})
    assert response.status_code == 503
    saved.assert_not_called()


def test_default_endpoint_keeps_saved_path(route_client, monkeypatch):
    client, route = route_client
    saved = Mock(return_value={"documents": [], "empty_reason": "saved-marker"})
    current = Mock(side_effect=AssertionError("默认路径不得读取当前资料"))
    monkeypatch.setattr(route, "_load_documents_from_bundle", saved)
    monkeypatch.setattr(route, "load_current_documents", current)
    response = client.get("/api/v1/emr/TEST-V/documents", params=IDENTITY)
    assert response.status_code == 200
    assert response.json()["data"]["empty_reason"] == "saved-marker"
    saved.assert_called_once()
    current.assert_not_called()


@pytest.fixture
def local_order_data(local_data):
    rows, reads, _ = local_data
    # 模拟数据库按请求上限返回，不能让未截断的替身掩盖少取一行的问题。
    reads.side_effect = lambda **kw: deepcopy(rows.get(kw["table"], [])[:kw["limit"]])

    def populate(counts):
        for table, count in counts.items():
            rows[table] = [
                {
                    **IDENTITY,
                    "order_id": f"{table}-{index}",
                    "order_name": f"合成测试医嘱{index}",
                    "start_time": "2026-02-02 11:00:00",
                }
                for index in range(count)
            ]

    return populate, reads


def test_current_orders_include_all_rows_within_relaxed_limits(local_order_data):
    populate, reads = local_order_data
    counts = {"inpat_drug_order": 788, "inpat_nondrug_order": 2156}
    populate(counts)

    documents = current_view.load_current_documents(**IDENTITY)["documents"]

    for table, count in counts.items():
        orders = [doc for doc in documents if doc["doc_type"] == table]
        assert len(orders) == count
        assert all(doc["projection_incomplete"] is False for doc in orders)
        assert all(not doc["projection_notice"] for doc in orders)
        assert [call.kwargs["limit"] for call in reads.call_args_list
                if call.kwargs["table"] == table] == [5001]


@pytest.mark.parametrize("table", ["inpat_drug_order", "inpat_nondrug_order"])
def test_current_orders_over_relaxed_limit_mark_incomplete(local_order_data, table):
    populate, reads = local_order_data
    populate({table: 5001})

    documents = current_view.load_current_documents(**IDENTITY)["documents"]
    orders = [doc for doc in documents if doc["doc_type"] == table]

    assert len(orders) == 5000
    assert all(doc["projection_incomplete"] is True for doc in orders)
    assert all(doc["projection_notice"].strip() for doc in orders)
    assert [call.kwargs["limit"] for call in reads.call_args_list
            if call.kwargs["table"] == table] == [5001]


def test_domain_orders_keep_default_projection_limits(local_order_data):
    populate, reads = local_order_data
    populate({"inpat_drug_order": 788, "inpat_nondrug_order": 2156})

    # 质控调用不传 projection_limits，继续使用原来的展示上限。
    bundle = assembly.assemble_domain_bundle(execution_domain="course", **IDENTITY)

    for table, limit in {"inpat_drug_order": 700, "inpat_nondrug_order": 1500}.items():
        assert len(bundle["structured_context"]["documents"][table]) == limit
        orders = [doc for doc in bundle["source_documents"] if doc["source_table"] == table]
        assert len(orders) == limit
        assert all(doc["projection_incomplete"] is True for doc in orders)
        assert all(doc["projection_notice"].strip() for doc in orders)
        assert [call.kwargs["limit"] for call in reads.call_args_list
                if call.kwargs["table"] == table] == [limit + 1]


def test_current_orders_without_relaxed_limits_reproduce_truncation(local_order_data, monkeypatch):
    populate, reads = local_order_data
    populate({"inpat_drug_order": 788, "inpat_nondrug_order": 2156})
    # 反例：移除当前查看专用上限，必须真实复现 700/1500 条截断。
    monkeypatch.setattr(current_view, "CURRENT_VIEW_PROJECTION_LIMITS", {})

    documents = current_view.load_current_documents(**IDENTITY)["documents"]

    for table, limit in {"inpat_drug_order": 700, "inpat_nondrug_order": 1500}.items():
        orders = [doc for doc in documents if doc["doc_type"] == table]
        assert len(orders) == limit
        assert all(doc["projection_incomplete"] is True for doc in orders)
        assert all(doc["projection_notice"].strip() for doc in orders)
        assert [call.kwargs["limit"] for call in reads.call_args_list
                if call.kwargs["table"] == table] == [limit + 1]
