from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.run_luxian_0609_fixed10_readonly import (
    EXPECTED_LUXIAN_0609_RULE_IDS,
    InMemoryLlmReplay,
    build_safe_rule_states,
    evaluate_formal_source_audit_case,
    evaluate_full_luxian_0609_case,
    evaluate_snapshot_sidecar_ab_case,
    evaluate_unified_engine_ab_case,
    load_course_severity_expected_matrix,
    parse_args,
    resolve_full_luxian_0609_rule_ids,
    validate_full_luxian_0609_results,
)


def _course_severity_matrix(
    *,
    evaluation_as_of_date: str = "2026-01-03",
    state_008: str = "compliant",
    reason_008: str = "unit_test",
    state_009: str = "compliant",
    reason_009: str = "unit_test",
) -> list[dict[str, str]]:
    """只构造安全的固定10例矩阵；不含坐标、正文或原始时间。"""

    as_of_hash = hashlib.sha256(evaluation_as_of_date.encode("utf-8")).hexdigest()
    rows: list[dict[str, str]] = []
    for case_index in range(1, 11):
        case_label = f"case-{case_index:02d}"
        for rule_id, state, reason in (
            ("LX0609-02-01-04", state_008, reason_008),
            ("LX0609-02-01-05", state_009, reason_009),
        ):
            rows.append(
                {
                    "case_label": case_label,
                    "rule_id": rule_id,
                    "expected_state": state,
                    "expected_reason": reason,
                    "manual_fact_basis": "unit_test",
                    "horizon_basis": "evaluation_as_of",
                    "evidence_attestation_hash": "a" * 64,
                    "evaluation_as_of_hash": as_of_hash,
                }
            )
    return rows


def test_full_regression_accepts_explicit_assert_49_cli_contract() -> None:
    args = parse_args(
        [
            "--assert-49",
            "--snapshot-sidecar-ab",
            "--evaluation-as-of-date",
            "2026-01-03",
        ]
    )
    assert args.assert_49 is True
    assert args.snapshot_sidecar_ab is True
    assert args.evaluation_as_of_date == "2026-01-03"

    audit_args = parse_args(
        [
            "--assert-49",
            "--formal-source-audit",
            "--evaluation-as-of-date",
            "2026-01-03",
        ]
    )
    assert audit_args.formal_source_audit is True

    unified_args = parse_args(
        [
            "--assert-49",
            "--unified-engine-ab",
            "--evaluation-as-of-date",
            "2026-01-03",
            "--course-severity-expected-matrix",
            "safe-matrix.json",
        ]
    )
    assert unified_args.assert_49 is True
    assert unified_args.unified_engine_ab is True

    with pytest.raises(SystemExit):
        parse_args(
            [
                "--snapshot-sidecar-ab",
                "--unified-engine-ab",
                "--evaluation-as-of-date",
                "2026-01-03",
            ]
        )

    with pytest.raises(SystemExit):
        parse_args(["--assert-49", "--snapshot-sidecar-ab"])

    with pytest.raises(SystemExit):
        parse_args(
            [
                "--assert-49",
                "--snapshot-sidecar-ab",
                "--evaluation-as-of-date",
                "2026-1-3",
            ]
        )

    with pytest.raises(SystemExit):
        parse_args(
            [
                "--assert-49",
                "--unified-engine-ab",
                "--evaluation-as-of-date",
                "2026-01-03",
            ]
        )


@pytest.mark.asyncio
async def test_snapshot_sidecar_ab_replays_same_model_response_and_counts_one_snapshot(
    monkeypatch,
) -> None:
    from app.services.luxian_0609 import execution as luxian_execution

    original_calls = 0

    async def generate(_prompt):
        nonlocal original_calls
        original_calls += 1
        return {
            "choices": [{"message": {"content": "stable"}}],
            "usage": {"total_tokens": 11},
        }

    settings = SimpleNamespace(
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False
    )
    client = SimpleNamespace(generate=generate)

    class Service:
        adjudicator_client = client

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            response = await self.adjudicator_client.generate("same prompt")
            if settings.LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED:
                luxian_execution.build_luxian_0609_evidence_snapshot()
            assert response["choices"][0]["message"]["content"] == "stable"
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ],
                "token_usage": {"total_tokens": 11},
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        lambda **_kwargs: SimpleNamespace(snapshot_hash="b" * 64),
    )

    comparison = await evaluate_snapshot_sidecar_ab_case(
        service=Service(),
        settings=settings,
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
    )

    assert comparison == {
        "states_match": True,
        "tokens_match": True,
        "logical_llm_call_count": 1,
        "snapshot_build_count": 1,
        "result_count": 49,
    }
    assert original_calls == 1


@pytest.mark.asyncio
async def test_unified_engine_ab_replays_same_model_response_and_counts_one_snapshot(
    monkeypatch,
) -> None:
    from app.services.luxian_0609 import execution as luxian_execution

    original_calls = 0

    async def generate(_prompt):
        nonlocal original_calls
        original_calls += 1
        return {
            "choices": [{"message": {"content": "stable"}}],
            "usage": {"total_tokens": 11},
        }

    settings = SimpleNamespace(
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
    )
    client = SimpleNamespace(generate=generate)

    class Service:
        adjudicator_client = client

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            response = await self.adjudicator_client.generate("same prompt")
            if settings.LUXIAN_0609_UNIFIED_ENGINE_ENABLED:
                luxian_execution.build_luxian_0609_evidence_snapshot()
                luxian_execution.bind_and_reduce_luxian_0609_rule_decisions()
            assert response["choices"][0]["message"]["content"] == "stable"
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ],
                "token_usage": {"total_tokens": 11},
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        lambda **_kwargs: SimpleNamespace(snapshot_hash="c" * 64),
    )
    monkeypatch.setattr(
        luxian_execution,
        "bind_and_reduce_luxian_0609_rule_decisions",
        lambda **_kwargs: tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value="compliant"),
                reason_code="unit_test",
                fact_refs=("d" * 64,),
            )
            for rule_id in (
                "LX0609-01-01-01",
                "LX0609-01-02-01",
                "LX0609-09-01-01",
                "LX0609-02-01-01",
                "LX0609-02-01-02",
                "LX0609-02-01-03",
                "LX0609-02-01-04",
                "LX0609-02-01-05",
            )
        ),
    )

    comparison = await evaluate_unified_engine_ab_case(
        service=Service(),
        settings=settings,
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
        case_label="case-01",
        evaluation_as_of_date="2026-01-03",
        course_severity_expected_matrix=_course_severity_matrix(),
    )

    assert comparison == {
        "states_match": True,
        "states_accepted": True,
        "tokens_match": True,
        "logical_llm_call_count": 1,
        "snapshot_build_count": 1,
        "result_count": 49,
        "baseline_family_reader_calls": 0,
        "candidate_family_reader_calls": 0,
        "typed_decision_count": 8,
        "typed_decision_min_fact_ref_count": 1,
        "typed_model_call_count": 0,
        "typed_007_decision_count": 1,
        "typed_007_fact_ref_count": 1,
        "typed_007_model_call_count": 0,
        "typed_008_model_call_count": 0,
        "typed_009_model_call_count": 0,
        "course_severity_matrix_accepted": True,
    }
    assert original_calls == 1


def test_full_regression_scope_rejects_empty_rule_ids() -> None:
    with pytest.raises(RuntimeError, match="冻结首49条客户规则ID"):
        resolve_full_luxian_0609_rule_ids([])


def test_full_regression_scope_requires_exact_customer_rule_order() -> None:
    inventory = [type("Dependency", (), {"rule_id": rule_id})() for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS]
    assert resolve_full_luxian_0609_rule_ids(inventory) == list(EXPECTED_LUXIAN_0609_RULE_IDS)

    with pytest.raises(RuntimeError, match="冻结首49条客户规则ID"):
        resolve_full_luxian_0609_rule_ids(list(reversed(inventory)))


def test_full_regression_results_require_exact_customer_rule_order() -> None:
    rows = [{"rule_id": rule_id} for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS]
    validate_full_luxian_0609_results({"evaluation_results": rows})

    with pytest.raises(RuntimeError, match="结果范围异常"):
        validate_full_luxian_0609_results({"evaluation_results": rows[:-1]})


def test_full_regression_safe_rows_only_keep_customer_rule_states() -> None:
    safe_rows = build_safe_rule_states(
        [
            {
                "rule_id": "LX0609-01-01-01",
                "status": "compliant",
                "evidence": "不应由回归摘要输出",
            }
        ]
    )
    assert safe_rows == [{"rule_id": "LX0609-01-01-01", "status": "compliant"}]


@pytest.mark.asyncio
async def test_formal_source_audit_captures_one_snapshot_and_safe_rule_sources(
    monkeypatch,
) -> None:
    """审计必须复用正式请求，不得再查库或把内部快照带回客户结果。"""

    from app.services.luxian_0609 import execution as luxian_execution
    from app.services.luxian_0609.evidence_snapshot import (
        Luxian0609EvidenceSnapshot,
        SourceCompleteness,
        SourceObservation,
    )
    from app.services.luxian_0609.source_manifest import QueryStatus
    from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION

    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="unit-institute",
        patient_id="unit-patient",
        visit_id="unit-visit",
        snapshot_schema_version="lx0609-evidence-snapshot-v1",
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="presurg_summary",
                query_state=QueryStatus.UNAVAILABLE,
                completeness=SourceCompleteness.UNPROVEN,
                record_count=None,
                query_version="snapshot-provider-presurg_summary-v1",
                snapshot_ref="sha256:" + "a" * 64,
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-01-03T00:00:00+08:00",
    )

    async def generate(prompt: str):
        if "LX0609-04-01-01" in prompt and "LX0609-04-03-01" not in prompt:
            return {"usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}
        if "LX0609-04-01-01" in prompt and "LX0609-04-03-01" in prompt:
            return {"usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}
        return {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}

    class Service:
        client = SimpleNamespace(generate=generate)
        adjudicator_client = SimpleNamespace(generate=generate)
        rule_engine = SimpleNamespace(_llm_generate=generate)

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            await self.rule_engine._llm_generate("LX0609-04-01-03")
            await self.adjudicator_client.generate("LX0609-04-01-01")
            await self.adjudicator_client.generate("LX0609-04-01-01 LX0609-04-03-01")
            await self.adjudicator_client.generate("SAFE_SECRET_MARKER")
            luxian_execution.build_luxian_0609_evidence_read_session()
            luxian_execution.bind_and_reduce_luxian_0609_rule_decisions()
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ],
                "token_usage": {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 21},
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: SimpleNamespace(snapshot=snapshot),
    )
    monkeypatch.setattr(
        luxian_execution,
        "bind_and_reduce_luxian_0609_rule_decisions",
        lambda **_kwargs: tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value="data_gap"),
                reason_code="unit_test",
                fact_refs=("a" * 64,),
            )
            for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
        ),
    )

    result, audit, performance = await evaluate_formal_source_audit_case(
        service=Service(),
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
        evaluation_as_of_date="2026-01-03",
    )

    assert len(result["evaluation_results"]) == 49
    assert "evidence_snapshot" not in repr(result)
    row_029 = audit[28]
    assert {
        key: row_029[key]
        for key in (
            "rule_id",
            "status",
            "execution_source",
            "typed_final_state",
            "typed_reason_code",
            "typed_fact_ref_count",
        )
    } == {
        "rule_id": "LX0609-04-01-01",
        "status": "compliant",
        "execution_source": "unknown",
        "typed_final_state": "data_gap",
        "typed_reason_code": "unit_test",
        "typed_fact_ref_count": 1,
    }
    assert {
        "source_key": "presurg_summary",
        "query_state": "unavailable",
        "completeness": "unproven",
        "record_count_bucket": "unknown",
    } in row_029["sources"]
    serialized_audit = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    assert "a" * 64 not in serialized_audit
    assert "b" * 64 not in serialized_audit
    assert "unit-institute" not in serialized_audit
    assert "SAFE_SECRET_MARKER" not in json.dumps(performance, ensure_ascii=False)
    assert performance == {
        "llm_call_count": 4,
        "prompt_tokens": 7,
        "completion_tokens": 11,
        "total_tokens": 21,
        "unattributed_tokens": 3,
        "model_error_call_count": 0,
        "usage_mismatch": True,
        "token_analysis": [
            {
                "rule_id": rule_id,
                "llm_call_count": 1 if rule_id in {"LX0609-04-01-01", "LX0609-04-01-03"} else 0,
                "prompt_tokens": 2 if rule_id == "LX0609-04-01-01" else (1 if rule_id == "LX0609-04-01-03" else 0),
                "completion_tokens": 3 if rule_id == "LX0609-04-01-01" else (2 if rule_id == "LX0609-04-01-03" else 0),
                "total_tokens": 5 if rule_id == "LX0609-04-01-01" else (3 if rule_id == "LX0609-04-01-03" else 0),
            }
            for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
        ],
        "shared_or_unattributed": {
            "llm_call_count": 2,
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
            "model_error_call_count": 0,
        },
    }


@pytest.mark.asyncio
async def test_formal_source_audit_rejects_non_single_snapshot_capture(
    monkeypatch,
) -> None:
    from app.services.luxian_0609 import execution as luxian_execution

    async def generate(_prompt):
        return {"usage": {"total_tokens": 0}}

    class Service:
        adjudicator_client = SimpleNamespace(generate=generate)

        async def evaluate_running_final_bundle_input(self, **_kwargs):
            luxian_execution.build_luxian_0609_evidence_read_session()
            luxian_execution.build_luxian_0609_evidence_read_session()
            return {
                "evaluation_results": [
                    {"rule_id": rule_id, "status": "compliant"}
                    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ]
            }

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: SimpleNamespace(snapshot=SimpleNamespace(observations=())),
    )
    monkeypatch.setattr(
        luxian_execution,
        "bind_and_reduce_luxian_0609_rule_decisions",
        lambda **_kwargs: (),
    )

    with pytest.raises(RuntimeError, match="同源证据审计快照捕获次数异常"):
        await evaluate_formal_source_audit_case(
            service=Service(),
            bundle={"scene": "running"},
            rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
            timeout_seconds=1.0,
            evaluation_as_of_date="2026-01-03",
        )


def test_course_severity_matrix_rejects_raw_date_and_as_of_mismatch(
    tmp_path,
) -> None:
    matrix = _course_severity_matrix()
    matrix[0]["horizon_basis"] = "2026-01-03"
    matrix_path = tmp_path / "course-matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(RuntimeError, match="008/009固定病例事实矩阵"):
        load_course_severity_expected_matrix(
            matrix_path,
            evaluation_as_of_date="2026-01-03",
        )


@pytest.mark.asyncio
async def test_prompt_hash_replay_allows_unused_baseline_records() -> None:
    async def generate(prompt: str):
        return {"prompt": prompt}

    replay = InMemoryLlmReplay(generate)
    await replay.record("legacy-unused")
    await replay.record("candidate-matched")

    assert await replay.replay("candidate-matched") == {"prompt": "candidate-matched"}
    assert replay.call_count == 2
    assert replay.replay_count == 1


@pytest.mark.asyncio
async def test_full_regression_passes_explicit_customer_ids_to_public_entry() -> None:
    captured = {}

    class Service:
        async def evaluate_running_final_bundle_input(self, **kwargs):
            captured.update(kwargs)
            return {
                "evaluation_results": [
                    {"rule_id": rule_id} for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
                ]
            }

    result = await evaluate_full_luxian_0609_case(
        service=Service(),
        bundle={"scene": "running"},
        rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
        timeout_seconds=1.0,
        evaluation_as_of_date="2026-01-03",
    )

    assert captured["rule_ids"] == list(EXPECTED_LUXIAN_0609_RULE_IDS)
    assert captured["evaluation_as_of_date"] == "2026-01-03"
    assert captured["rule_ids"]
    assert len(result["evaluation_results"]) == 49


@pytest.mark.asyncio
async def test_full_regression_rejects_empty_scope_before_public_entry() -> None:
    called = False

    class Service:
        async def evaluate_running_final_bundle_input(self, **_):
            nonlocal called
            called = True
            return {}

    with pytest.raises(RuntimeError, match="禁止使用空列表"):
        await evaluate_full_luxian_0609_case(
            service=Service(),
            bundle={"scene": "running"},
            rule_ids=[],
            timeout_seconds=1.0,
        )

    assert called is False


@pytest.mark.asyncio
async def test_unified_engine_requires_complete_attested_008_009_matrix() -> None:
    settings = SimpleNamespace(
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
    )

    class Service:
        adjudicator_client = SimpleNamespace(generate=None)

    with pytest.raises(RuntimeError, match="008/009固定病例事实矩阵"):
        await evaluate_unified_engine_ab_case(
            service=Service(),
            settings=settings,
            bundle={"scene": "running"},
            rule_ids=EXPECTED_LUXIAN_0609_RULE_IDS,
            timeout_seconds=1.0,
            case_label="case-01",
            evaluation_as_of_date="2026-01-03",
            course_severity_expected_matrix=(),
        )
