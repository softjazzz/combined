"""C2：受控资料/模型事实经正式 API、detached worker 和 Canonical GET 验收。

不连接医院库或真实模型；不替换规则执行器、归约器、保存或 worker 成功路径。
复用入口测试的 SQLite/认证/样本池设施，不复制另一套 testkit。
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration import test_luxian_0609_consultation_api_entry_flow as entry
from tests.integration import (
    test_luxian_0609_consultation_business_entry_flow as business,
)


_isolated_api_database = entry._isolated_api_database
RULES = [f"LX0609-{number:03d}" for number in range(20, 24)]


def _source_rows(source_key: str, record: dict[str, str], scenario: str):
    if source_key == "inpat_registration":
        return [{"admission_datetime": "2026-07-01 08:00:00"}]
    if source_key == "inpat_registration.discharge_horizon":
        return [{"discharge_datetime": "2026-07-05 08:00:00"}]
    if source_key == "daily_course_record":
        return [
            {
                **record,
                "document_id": "C2-COURSE-1",
                "document_title": "日常病程记录",
                "record_time": "2026-07-04 12:00:00",
                "record_content": "已按感染科意见加强抗感染治疗。",
            }
        ]
    if source_key != "consultation_record":
        return []
    texts = ["因持续发热请感染科协助诊治；考虑感染，建议加强抗感染治疗。"]
    if scenario in {"partial", "unknown"}:
        texts.append("因贫血请血液科协助诊治；建议复查血常规。")
    if scenario == "horizon_gap":
        texts = ["因持续发热请感染科协助诊治；会诊意见：必要时完善检查。"]
    return [
        {
            **record,
            "document_id": f"C2-CONSULT-{index}",
            "document_title": "会诊记录",
            "record_time": f"2026-07-0{index + 1} 09:00:00",
            "record_content": content,
        }
        for index, content in enumerate(texts, start=1)
    ]


def _model_facts(prompt: str, scenario: str) -> dict[str, Any] | str:
    """固定临床事实，只把输入的 opaque ref 原样带回，不计算质控结论。"""
    payload = json.loads(prompt.rsplit("输入：", 1)[1])
    if "consultation_documents" in payload:
        if scenario == "invalid_first":
            return "not-json"
        facts = []
        for index, document in enumerate(payload["consultation_documents"]):
            vague = scenario == "horizon_gap"
            action = "加强抗感染治疗" if index == 0 else "复查血常规"
            facts.append(
                {
                    "ref": document["ref"],
                    "scope": "ordinary",
                    "application_state": "clear",
                    "opinion_state": "vague" if vague else "clear",
                    "confidence": "high",
                    "recommendations": []
                    if vague
                    else [
                        {
                            "source_quote": action,
                            "normalized_action": action,
                            "action_type": "medication" if index == 0 else "test",
                        }
                    ],
                }
            )
        return {"consultation_event_facts": facts}
    if scenario == "invalid_second":
        return "not-json"
    course_ref = next(
        item["ref"]
        for item in payload["candidate_documents"]
        if item["source"] == "daily_course_record"
    )
    executions = []
    for index, recommendation in enumerate(payload["recommendations"]):
        state = "specific_trace" if index == 0 else "no_trace"
        if scenario == "unknown" and index == 1:
            state = "unknown"
        executions.append(
            {
                "recommendation_ref": recommendation["recommendation_ref"],
                "execution_record_state": state,
                "trace_refs": [course_ref] if state == "specific_trace" else [],
                "confidence": "high",
            }
        )
    return {"executions": executions}


@pytest.fixture
def semantic_api(monkeypatch, _isolated_api_database):
    """仅为本矩阵安装外部资料与模型边界，其余设施复用已冻结入口测试。"""
    engine, workspace = _isolated_api_database
    sample_service = entry._install_sample_pool_sqlite(monkeypatch, engine=engine)
    settings = business._formal_settings()
    for module in (entry.batch_worker, entry.sichuan_qc_service, entry.qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        entry.batch_worker,
        "get_product_activation_service",
        lambda: business._ActivationStub(),
    )
    monkeypatch.setattr(
        entry.sichuan_qc_service,
        "build_adjudicator_runtime_config",
        lambda config: dict(config or {}),
    )
    monkeypatch.setattr(
        entry.sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="c2-isolated-secret"),
    )
    monkeypatch.setattr(
        entry.batch_worker,
        "load_running_final_bundle",
        lambda *, visit_id, patient_id, **_: business._bundle_for_record(
            visit_id=visit_id, patient_id=patient_id
        ),
    )
    monkeypatch.setattr(
        entry.qc_sichuan, "_sichuan_workspace_service", lambda: workspace
    )
    monkeypatch.setattr(entry.qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(entry.qc_sample_pools, "_service", lambda: sample_service)
    service = entry.sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated-test",
            "model": "controlled-c2-facts",
            "allow_mock_when_unconfigured": False,
            "source": "c2-api-matrix",
        }
    )

    async def provide_service():
        return service

    monkeypatch.setattr(entry.qc_sichuan, "get_qc_service", provide_service)
    pool_id, sample_id = entry._create_ready_sample_pool(
        engine=engine, service=sample_service
    )
    app = entry._api_app(service=service)
    state: dict[str, Any] = {"scenario": "normal", "prompts": [], "legacy_calls": []}
    original_builder = entry.luxian_execution.build_luxian_0609_evidence_read_session

    def reader(**kwargs):
        record = {
            key: str(kwargs[key]) for key in ("institute_id", "patient_id", "visit_id")
        }
        return entry.SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=_source_rows(kwargs["source_key"], record, state["scenario"]),
            truncated=False,
            limit_rows=50,
        )

    def build_session(**kwargs):
        if state["scenario"] == "horizon_gap":
            kwargs.update(
                evaluation_horizon_policy="disabled",
                horizon_unavailable_reason="authoritative_time_missing",
            )
        return original_builder(**kwargs, row_reader=reader)

    async def generate(_client, prompt, **_kwargs):
        state["prompts"].append(prompt)
        return {
            "content": _model_facts(prompt, state["scenario"]),
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }

    async def reject_legacy(*args, **kwargs):
        state["legacy_calls"].append(True)
        raise AssertionError("C2 不得走旧通用引擎")

    monkeypatch.setattr(
        entry.luxian_execution, "build_luxian_0609_evidence_read_session", build_session
    )
    monkeypatch.setattr(
        entry.sichuan_qc_service.SichuanQCLLMClient, "generate", generate
    )
    monkeypatch.setattr(service.rule_engine, "evaluate", reject_legacy)
    monkeypatch.setattr(service.rule_engine, "evaluate_batch_compact", reject_legacy)
    return app, workspace, pool_id, sample_id, state


def _create_and_wait(api, mode: str):
    app, workspace, pool_id, sample_id, _state = api
    with TestClient(app) as client:
        if mode == "sample":
            response = client.post(
                f"/api/v1/qc/sample-pools/{pool_id}/run",
                json={
                    "validation_mode": "customer",
                    "rule_set_key": "luxian_0609_qc_v1",
                    "selected_rule_ids": RULES,
                    "sample_item_ids": [sample_id],
                    "record_refs": [business._RECORD_A],
                    "group_by_luxian_family": False,
                },
            )
        else:
            records = (
                [business._RECORD_A, business._RECORD_B]
                if mode == "batch"
                else [business._RECORD_A]
            )
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_ids": RULES,
                    "scope": "final",
                    "record_refs": records,
                    "run_mode": "serial",
                },
            )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    job_id = str(data["job_id"] if mode == "sample" else data["id"])
    job = entry._wait_for_terminal_job(workspace=workspace, job_id=job_id)
    if job["status"] == "completed":
        # 包括样本入口与局部 technical_error：计数只属于最终交付项，不得重复累加。
        entry._assert_native_executor_breakdown(job)
    return job


def _get_latest(app):
    with TestClient(app) as client:
        return client.get(
            f"/api/v1/qc/sichuan/workspace/records/{business._RECORD_A['visit_id']}/latest-result",
            params={
                key: business._RECORD_A[key] for key in ("institute_id", "patient_id")
            },
        )


def _assert_semantic_facts(envelope: dict[str, Any], scenario: str) -> None:
    """021/022 的逐次事实以手工夹具期望冻结，不从执行结果反推期望。"""
    rule_id = envelope["rule_id"]
    assert rule_id in {"LX0609-021", "LX0609-022"}
    if scenario == "invalid_first":
        assert not envelope.get("customer_display_facts")
        return
    application = rule_id == "LX0609-021"
    semantic_state = (
        "vague" if scenario == "horizon_gap" and not application else "clear"
    )
    times = ["2026-07-02 09:00:00"]
    if scenario in {"partial", "unknown"}:
        times.append("2026-07-03 09:00:00")
    assert envelope["customer_display_facts"] == {
        "verification_kind": (
            "consultation_application_quality_check"
            if application
            else "consultation_opinion_quality_check"
        ),
        "episode_count": len(times),
        "document_count": len(times),
        "semantic_state": semantic_state,
        "checked_requirement": (
            "说明具体临床问题、会诊理由或明确会诊目的" if application else "给出针对当前病情的明确诊疗意见"
        ),
        "episode_results": [
            {
                "episode_index": index,
                "semantic_state": semantic_state,
                "record_time": record_time,
                "document_title": "会诊申请单" if application else "会诊记录单",
            }
            for index, record_time in enumerate(times, start=1)
        ],
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    "scenario",
    ["normal", "partial", "horizon_gap", "invalid_first", "invalid_second", "unknown"],
)
def test_controlled_semantic_facts_survive_three_api_entries(semantic_api, scenario):
    app, _workspace, _pool, _sample, state = semantic_api
    state["scenario"] = scenario
    projections = []
    for mode in ("single", "batch", "sample"):
        before = len(state["prompts"])
        job = _create_and_wait(semantic_api, mode)
        assert job["status"] == "completed", job.get("error_message")
        expected_calls = 1 if scenario in {"horizon_gap", "invalid_first"} else 2
        assert len(state["prompts"]) - before == expected_calls * (
            2 if mode == "batch" else 1
        )
        assert state["legacy_calls"] == []
        envelopes = []
        for rule_id in RULES:
            item = entry._saved_item(
                job, visit_id=business._RECORD_A["visit_id"], rule_id=rule_id
            )
            expected = ("compliant", "requirement_satisfied")
            if scenario == "partial" and rule_id == "LX0609-020":
                expected = ("non_compliant", "requirement_violated")
            if scenario == "unknown" and rule_id in {"LX0609-020", "LX0609-023"}:
                expected = ("uncertain", "semantic_low_confidence")
            if scenario == "horizon_gap":
                if rule_id in {"LX0609-020", "LX0609-023"}:
                    expected = ("data_gap", "linkage_unresolved")
                elif rule_id == "LX0609-022":
                    expected = ("non_compliant", "requirement_violated")
            if scenario == "invalid_first" or (
                scenario == "invalid_second" and rule_id in {"LX0609-020", "LX0609-023"}
            ):
                expected = ("technical_error", "model_invalid_output")
            assert (item["status"], item["reason_code"]) == expected, item
            entry._assert_native_consultation_item(item)
            envelope = entry._read_saved_envelope(
                app=app,
                job_id=job["id"],
                task_item=item,
                record=business._RECORD_A,
                expected_rule_ids=RULES,
                evidence_required=expected[0] not in {"technical_error", "data_gap"},
            )
            # 会诊族当前通过决策和客户事实交付，准则列表为空是既有合同。
            # 只冻结原样搬运，不为了宣称非空准则验收而补造条目。
            assert envelope["criterion_results"] == []
            if rule_id in {"LX0609-021", "LX0609-022"}:
                _assert_semantic_facts(envelope, scenario)
            if scenario in {"normal", "partial"} and rule_id == "LX0609-020":
                expected_documents = (
                    {"C2-CONSULT-1", "C2-COURSE-1"}
                    if scenario == "normal"
                    else {"C2-CONSULT-2"}
                )
                assert {
                    row["source_document_id"] for row in item["customer_evidence"]
                } == expected_documents
            if scenario == "horizon_gap" and rule_id in {"LX0609-020", "LX0609-023"}:
                assert envelope["customer_display_facts"]["recommendation_count"] == 0
                assert (
                    envelope["customer_display_facts"]["missing_execution_count"] == 0
                )
            if scenario == "invalid_first":
                assert not envelope.get("customer_display_facts")
            if scenario == "invalid_second" and rule_id in {"LX0609-020", "LX0609-023"}:
                # 首轮事实合法，二轮失败只使执行核对未知；它不同于整个事实合同非法。
                facts = envelope["customer_display_facts"]
                assert facts["recommendation_count"] == 1
                assert facts["missing_execution_count"] == 0
                assert facts["specific_execution_count"] == 0
                assert not envelope["evidence"]
                assert all(
                    clinical_claim not in envelope["conclusion"]
                    for clinical_claim in ("合规", "符合要求", "已归纳具体执行情况")
                )
                if rule_id == "LX0609-020":
                    assert [
                        row["execution_state"]
                        for row in facts["recommendation_results"]
                    ] == ["unknown"]
            if rule_id == "LX0609-020" and scenario in {"normal", "partial", "unknown"}:
                facts = envelope["customer_display_facts"]
                assert facts["recommendation_count"] == (
                    1 if scenario == "normal" else 2
                )
                assert facts["specific_execution_count"] == 1
                assert facts["generic_execution_count"] == 0
                assert facts["missing_execution_count"] == (
                    1 if scenario == "partial" else 0
                )
                assert [
                    row["execution_state"] for row in facts["recommendation_results"]
                ] == {
                    "normal": ["specific"],
                    "partial": ["specific", "missing"],
                    "unknown": ["specific", "unknown"],
                }[
                    scenario
                ]
            envelopes.append(
                {
                    **entry._envelope_customer_projection(envelope),
                    "evidence": envelope["evidence"],
                }
            )
        projections.append(envelopes)
    assert projections[0] == projections[1] == projections[2]


@pytest.mark.integration
def test_invalid_customer_counts_are_one_rule_technical_error(
    semantic_api, monkeypatch
):
    """只破坏真实执行后020事实计数，仍由真实 Finalizer 决定失败语义。"""
    app, _workspace, _pool, _sample, state = semantic_api
    state["scenario"] = "partial"
    original = entry.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results
    injections = []

    def inject_invalid_counts(**kwargs):
        context = kwargs["context"]
        facts = []
        for rule_id, value in context.customer_display_facts:
            if rule_id == "LX0609-020":
                assert value["missing_execution_count"] == 1
                value = {**value, "missing_execution_count": 0}
                injections.append(rule_id)
            facts.append((rule_id, value))
        kwargs["context"] = replace(context, customer_display_facts=tuple(facts))
        return original(**kwargs)

    monkeypatch.setattr(
        entry.sichuan_qc_service,
        "aggregate_luxian_0609_orchestrated_results",
        inject_invalid_counts,
    )
    job = _create_and_wait(semantic_api, "single")
    assert job["status"] == "completed", job.get("error_message")
    assert injections == ["LX0609-020"]
    assert len(state["prompts"]) == 2
    assert state["legacy_calls"] == []
    for rule_id in RULES:
        item = entry._saved_item(
            job, visit_id=business._RECORD_A["visit_id"], rule_id=rule_id
        )
        expected = (
            ("technical_error", "model_invalid_output")
            if rule_id == "LX0609-020"
            else ("compliant", "requirement_satisfied")
        )
        assert (item["status"], item["reason_code"]) == expected
        if rule_id == "LX0609-020":
            # 事实合同无效时 Finalizer 清掉旧临床结论，不能使用正常结果的非空文案助手。
            response = _get_latest(app)
            assert response.status_code == 200, response.text
            latest = response.json()["data"]
            assert latest["state"] == "ready"
            assert latest["job_id"] == job["id"]
            assert latest["result_rule_count"] == 4
            envelope = next(row for row in latest["items"] if row["rule_id"] == rule_id)
            assert (envelope["status"], envelope["reason_code"]) == expected
            assert not envelope.get("customer_display_facts")
            assert "criterion_results" not in envelope
            assert not envelope.get("evidence")
            assert not envelope.get("conclusion")
            assert not entry._task_customer_conclusion(item)
        else:
            envelope = entry._read_saved_envelope(
                app=app,
                job_id=job["id"],
                task_item=item,
                record=business._RECORD_A,
                expected_rule_ids=RULES,
            )
            if rule_id in {"LX0609-021", "LX0609-022"}:
                _assert_semantic_facts(envelope, "partial")


@pytest.mark.integration
def test_invalid_usage_attribution_fails_job_without_new_canonical(
    semantic_api, monkeypatch
):
    """归属合同失败属于 worker/job；不得伪装成单规则临床结果。"""
    app, workspace, _pool, _sample, state = semantic_api
    original = entry.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results
    original_write = workspace._write_record_result_envelopes
    writes = []
    injections = []

    def inject_invalid_attribution(**kwargs):
        context = kwargs["context"]
        assert context.native_usage_attributions
        injections.append(True)
        kwargs["context"] = replace(
            context,
            native_usage_attributions=({"executor_key": "consultation_quality"},),
        )
        return original(**kwargs)

    def observe_write(*args, **kwargs):
        writes.append(True)
        return original_write(*args, **kwargs)

    monkeypatch.setattr(
        entry.sichuan_qc_service,
        "aggregate_luxian_0609_orchestrated_results",
        inject_invalid_attribution,
    )
    monkeypatch.setattr(workspace, "_write_record_result_envelopes", observe_write)
    # 每例独立 SQLite，没有历史 Canonical；不能把别的 job 的旧结果当作本次成功。
    assert _get_latest(app).status_code == 404
    job = _create_and_wait(semantic_api, "single")
    assert injections == [True]
    assert len(state["prompts"]) == 2
    assert state["legacy_calls"] == []
    assert job["status"] == "failed"
    assert not job.get("items")
    assert writes == []
    assert "invalid native usage attribution" in str(
        (job.get("summary") or {}).get("failure_diagnostics")
    )
    response = _get_latest(app)
    assert response.status_code == 404, response.text
