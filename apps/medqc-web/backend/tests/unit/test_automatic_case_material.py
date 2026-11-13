"""自动取材不依赖人工窗口；只使用合成材料。"""

from dataclasses import replace

import pytest

from app.services import case_material_snapshot as material
from app.services.material_admission import preflight_new_task


@pytest.mark.parametrize("window", ["", "bad", "2020-01-01T00:00:00Z"])
def test_normal_case_does_not_require_manual_window(monkeypatch, window):
    monkeypatch.setenv("QC_CDM_CAPTURE_WINDOW_UNTIL", window)
    preflight_new_task({"clinical_source": {"id": "independent_cdm"}})


def test_missing_table_is_a_source_gap_not_case_failure():
    from app.services.automatic_material_scope import validate_read_contract

    report = {
        "read_only": True,
        "account_read_only": True,
        "dependencies": [
            {"table": "surgery_record", "required": True, "status": "table_missing"}
        ],
    }
    assert validate_read_contract(report) == {"surgery_record": "table_missing"}
    for failure in (
        "select_denied",
        "object_ownership_forbidden",
        "write_privilege_forbidden",
    ):
        report["dependencies"][0]["status"] = failure
        with pytest.raises(material.MaterialSnapshotError):
            validate_read_contract(report)


def test_source_scope_enters_material_fingerprint_and_keeps_history():
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
    from app.services.luxian_0609.evidence_material import build_material_snapshot_ref
    from app.services.luxian_0609.source_manifest import QueryStatus
    from app.services.luxian_0609.evidence_snapshot import SourceCompleteness

    arguments = dict(
        source_key="surgery_record", rows=(), truncated=False, limit_rows=1
    )
    original = SnapshotSourceRows.create(**arguments)
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "surgery_record": {
                    "status": "empty_unconfirmed",
                    "coverage": "unknown",
                    "can_judge_clinical_absence": False,
                }
            },
        }
    }
    with material.activate(state):
        current = SnapshotSourceRows.create(**arguments)
    assert original.material_scope is None
    assert current.material_scope["can_judge_clinical_absence"] is False
    kwargs = dict(
        source_key="surgery_record",
        query_version="snapshot-provider-surgery_record-v2",
        query_state=QueryStatus.EMPTY,
        completeness=SourceCompleteness.COMPLETE,
        document_refs=(),
    )
    assert build_material_snapshot_ref(
        **kwargs, material_scope=current.material_scope
    ) != build_material_snapshot_ref(**kwargs)


def test_rule_gap_does_not_poison_independent_rule_or_technical_error():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.decision_model import (
        ApplicabilityState,
        EvidenceState,
        QcDirection,
    )

    snapshot = _snapshot()
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "surgery_record": {
                    "status": "table_missing",
                    "can_judge_clinical_absence": False,
                },
                "daily_course_record": {
                    "status": "available",
                    "can_judge_clinical_absence": False,
                },
            },
        }
    }
    healthy = _decision(snapshot)
    missing = _decision(snapshot, rule_id="LX0609-04-02-02", fact_refs=("c" * 64,))
    with material.activate(state):
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=(healthy, missing),
            expected_rule_ids=(healthy.rule_id, missing.rule_id),
            snapshot=snapshot,
        )
        assert [item.final_state.value for item in reduced] == ["compliant", "data_gap"]
        technical = replace(
            missing,
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_query_error",
            fact_refs=(),
        )
        [result] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=(technical,),
            expected_rule_ids=(technical.rule_id,),
            snapshot=snapshot,
        )
        assert result.final_state.value == "technical_error"


def test_zero_rows_cannot_prove_clinical_absence():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.decision_model import QcDirection

    snapshot = _snapshot()
    decision = replace(
        _decision(snapshot),
        qc_direction=QcDirection.DEFECT,
        reason_code="required_document_missing",
    )
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "daily_course_record": {
                    "status": "available",
                    "can_judge_clinical_absence": False,
                }
            },
        }
    }
    with material.activate(state):
        [result] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=(decision,),
            expected_rule_ids=(decision.rule_id,),
            snapshot=snapshot,
        )
    assert result.final_state.value == "data_gap"


def test_gap_finalizer_discards_original_defect_facts():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )

    snapshot = _snapshot()
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "daily_course_record": {
                    "status": "table_missing",
                    "can_judge_clinical_absence": False,
                }
            },
        }
    }
    with material.activate(state):
        [decision] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=(_decision(snapshot),),
            expected_rule_ids=("LX0609-02-01-03",),
            snapshot=snapshot,
        )
        result = finalize_luxian_0609_reduced_customer_result(
            decision=decision,
            raw_customer_display_facts={"unexpected_defect": "STALE"},
            evidence_snapshot=snapshot,
            evidence_materials=None,
        )
    assert result["status"] == "data_gap"
    assert "STALE" not in str(result)


def test_receipt_hash_uses_complete_typed_target_key():
    from app.services.cdm_publication_evidence import target_hash
    import hashlib

    assert (
        target_hash({"b": "01", "a": 1})
        == hashlib.sha256(b'{"a":1,"b":"01"}').hexdigest()
    )
    assert target_hash({"b": "01"}) != target_hash({"b": 1})


def test_receipt_and_operation_must_match_current_contract():
    from app.services.cdm_publication_evidence import verified_receipt

    contract = {"source_epoch": "epoch", "mapping_hash": "mapping", "activation": 2}
    receipt = {
        **contract,
        "source_key_hash": "source",
        "generation": 5,
        "target_key_hash": "target",
    }
    from app.services.cdm_publication_evidence import target_hash

    operation = {
        "source_epoch": "epoch",
        "mapping_hash": "mapping",
        "interface_name": "web.surgery_record",
        "queue_hash": target_hash(["mapping", 2]),
        "operation_id": "op",
        "commit_order": 1,
    }
    assert verified_receipt("web.surgery_record", contract, receipt, [operation])
    assert not verified_receipt(
        "web.surgery_record", contract, {**receipt, "generation": 0}, [operation]
    )
    assert not verified_receipt(
        "web.surgery_record", contract, receipt, [{**operation, "queue_hash": "other"}]
    )
    assert not verified_receipt(
        "web.surgery_record", {**contract, "activation": 3}, receipt, [operation]
    )


def test_owner_attested_positive_defect_survives_unrelated_missing_source():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.automatic_material_scope import guard_decision
    from app.services.luxian_0609.decision_model import QcDirection

    decision = replace(
        _decision(_snapshot()),
        qc_direction=QcDirection.DEFECT,
        reason_code="requirement_violated",
        positive_document_refs=("a" * 64,),
    )
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "daily_course_record": {
                    "status": "available",
                    "can_judge_clinical_absence": False,
                },
                "surgery_record": {
                    "status": "table_missing",
                    "can_judge_clinical_absence": False,
                },
            },
        }
    }
    with material.activate(state):
        assert (
            guard_decision(decision, ("daily_course_record", "surgery_record"))
            == decision
        )


@pytest.mark.asyncio
async def test_positive_consultation_defect_reaches_real_finalizer_and_store(
    monkeypatch, tmp_path
):
    import json
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services.luxian_0609 import (
        native_consultation_episode_execution as episode,
    )
    from app.services.luxian_0609.evidence_snapshot_provider import (
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
    from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore,
        envelope_item_from_rule_result,
    )

    rule = "LX0609-03-01-03"
    rows = (
        {
            "document_id": "D1",
            "record_content": "会诊意见：酌情处理。",
            "record_time": "2026-11-01 09:00:00",
        },
    )
    from test_luxian_0609_native_consultation_episode_execution import (
        _Client,
        _payload,
        _episode,
    )

    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1"],
                    application="absent",
                    opinion="vague",
                    application_refs=[],
                    opinion_refs=["consultation_record-1"],
                    recommendations=[],
                )
            ]
        )
    )
    state = {
        "automatic_material": {
            "protocol": "cdm-auto-v1",
            "sources": {
                "consultation_record": {
                    "status": "available",
                    "can_judge_clinical_absence": False,
                },
                "daily_course_record": {
                    "status": "table_missing",
                    "can_judge_clinical_absence": False,
                },
            },
        }
    }
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    with material.activate(state):
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=(rule,),
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            created_at="2026-11-02T00:00:00+08:00",
            row_reader=lambda **kw: SnapshotSourceRows.create(
                source_key=kw["source_key"],
                rows=rows if kw["source_key"] == "consultation_record" else (),
                truncated=False,
                limit_rows=50,
            ),
        )
        execution = await episode.execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=(rule,),
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=(rule,),
            llm_client=client,
            opinion_freeze_dir=tmp_path / "freeze",
            opinion_freeze_rebuild=True,
        )
        assert len(client.prompts) == 1  # 固定应答，禁网运行器拦截真实调用
        assert execution.decisions[0].positive_document_refs, execution.decisions[
            0
        ].reason_code
        [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=(rule,),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        final = finalize_luxian_0609_reduced_customer_result(
            decision=reduced,
            raw_customer_display_facts=dict(execution.customer_display_facts)[rule],
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
    assert final["status"] == "non_compliant"
    [published] = aggregate_luxian_0609_results(
        wrapper_rules=[get_luxian_0609_rule(rule)],
        execution_results=[],
        canonical_results=(final,),
        delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
    )
    table = workspace._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    ref = {"institute_id": "I", "patient_id": "P", "visit_id": "V"}
    with Session(engine) as db:
        store.replace_for_job(
            db,
            job_row={
                "id": "synthetic-auto",
                "created_by": "synthetic",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                        "scoped_customer_rule_ids": [rule],
                        "record_refs": [ref],
                    }
                ),
            },
            items=[{**published, **ref, "record_id": "V"}],
            now=datetime(2026, 11, 2),
            projector=lambda raw: envelope_item_from_rule_result(
                raw, hmac_key="synthetic-ref-key"
            ),
            projection_key="synthetic-ref-key",
        )
        db.commit()
        saved = store.load_selected(
            db,
            root_job_id="synthetic-auto",
            **ref,
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
        )["items"][0]
    engine.dispose()
    assert saved["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_existing_chief_complaint_length_defect_survives_missing_diagnosis():
    from test_luxian_0609_native_course_quality_execution import (
        course,
        _Client,
        _wrapper,
    )
    from app.services.luxian_0609.evidence_snapshot_provider import (
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )

    rule = "LX0609-01-01-02"
    state = {
        "automatic_material": {
            "sources": {
                "admission_record": {
                    "status": "available",
                    "can_judge_clinical_absence": False,
                },
                "diagnosis": {
                    "status": "empty_unconfirmed",
                    "can_judge_clinical_absence": False,
                },
                "admission_record_diagnosis": {
                    "status": "table_missing",
                    "can_judge_clinical_absence": False,
                },
            }
        }
    }
    with material.activate(state):
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=(rule,),
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            created_at="2026-11-02T00:00:00+08:00",
            row_reader=lambda **kw: SnapshotSourceRows.create(
                source_key=kw["source_key"],
                rows=[{"document_id": "A1", "chief_complaint": "胸痛" * 11}]
                if kw["source_key"] == "admission_record"
                else [],
                truncated=False,
                limit_rows=50,
            ),
        )
        client = _Client([])
        execution = await course.execute_luxian_0609_native_course_quality_rules(
            rule_ids=(rule,),
            decision_rule_ids=(rule,),
            wrapper_rules=[_wrapper(rule)],
            evidence_payload=None,
            llm_client=client,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=(rule,),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
    assert reduced.final_state.value == "non_compliant"
    assert execution.decisions[0].positive_document_refs
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,expected",
    [
        ("2026-04-26 使用奥沙利铂120mg 静滴。", "non_compliant"),
        ("2026-04-26 患者一般情况可。", "data_gap"),
    ],
)
async def test_chemotherapy_positive_difference_and_missing_record_are_separated(
    body, expected
):
    from test_luxian_0609_chemo_closure import _course, _run
    from test_026_association_contract import assert_sqlite_roundtrip

    state = {
        "automatic_material": {
            "sources": {
                key: {"status": "available", "can_judge_clinical_absence": False}
                for key in ("inpat_drug_order", "daily_course_record")
            }
        }
    }
    with material.activate(state):
        execution, _, final = await _run(_course(body))
    assert final["status"] == expected
    assert bool(execution.decisions[0].positive_document_refs) == (
        expected == "non_compliant"
    )
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
async def test_copy_defect_survives_unknown_upstream_coverage(monkeypatch):
    from test_luxian_0609_native_course_quality_execution import (
        test_typed_017_strong_copy_emits_bound_decision_without_customer_dto,
    )

    state = {
        "automatic_material": {
            "sources": {
                key: {"status": "available", "can_judge_clinical_absence": False}
                for key in ("daily_course_record", "senior_course_record")
            }
        }
    }
    with material.activate(state):
        await test_typed_017_strong_copy_emits_bound_decision_without_customer_dto(
            monkeypatch
        )


def test_ct_positive_proof_excludes_missing_event():
    from test_luxian_0609_ct_order_course_consistency import (
        _review,
        _event,
        _payload,
        HandbookFinding,
        evaluate_ct_review,
    )

    review = _review(
        "EXAM-001医嘱为左膝CT，实际右膝CT。",
        events=(_event(), _event("EXAM-002")),
        initial={2: HandbookFinding("data_gap", "execution_unconfirmed", ("order:2",))},
    )
    outcome = evaluate_ct_review(review, _payload("contradictory_description"))
    assert outcome.positive_document_refs
    assert "order:2" not in outcome.positive_document_refs


def test_controlled_fact_consumption_does_not_include_unused_sources():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from test_luxian_0609_evidence_snapshot import _fact
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
        _allowed_source_keys,
    )

    snapshot = _snapshot()
    fact = _fact(visit_ref=snapshot.visit_ref, source_key="daily_course_record")
    snapshot = type(snapshot).create(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        snapshot_schema_version=snapshot.snapshot_schema_version,
        source_registry_version=snapshot.source_registry_version,
        observations=snapshot.observations,
        facts=(fact,),
        document_refs=(),
        created_at=snapshot.created_at,
    )
    decision = _decision(snapshot, fact_refs=(fact.fact_id,))
    scopes = {
        key: {"status": "table_missing", "can_judge_clinical_absence": False}
        for key in _allowed_source_keys(decision.rule_id)
    }
    scopes["daily_course_record"]["status"] = "available"
    with material.activate({"automatic_material": {"sources": scopes}}):
        [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=(decision,),
            expected_rule_ids=(decision.rule_id,),
            snapshot=snapshot,
        )
    assert reduced.final_state.value == "compliant"


def test_empty_generic_body_does_not_erase_valid_structured_field_result():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.automatic_material_scope import guard_decision, describe_source

    scope = describe_source(
        ("record_content", "chief_complaint"),
        [{"record_content": None, "chief_complaint": "胸痛三天"}],
    )
    assert scope["status"] == "body_empty"
    decision = _decision(_snapshot())
    with material.activate(
        {"automatic_material": {"sources": {"admission_record": scope}}}
    ):
        assert guard_decision(decision, ("admission_record",)) == decision


@pytest.mark.asyncio
async def test_main_diagnosis_positive_conflict_with_unknown_publication_coverage():
    from test_luxian_0609_discharge_diagnosis_order import (
        test_unordered_written_diagnoses_check_main_selection_only,
    )

    scopes = {
        key: {"status": "available", "can_judge_clinical_absence": False}
        for key in ("diagnosis", "discharge_record", "discharge_record_diagnosis")
    }
    with material.activate({"automatic_material": {"sources": scopes}}):
        await test_unordered_written_diagnoses_check_main_selection_only(
            "高血压", "non_compliant"
        )


def test_source_observation_cannot_impersonate_positive_document_proof():
    from test_luxian_0609_decision_binding import _snapshot, _decision
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

    snapshot = _snapshot()
    decision = replace(_decision(snapshot), positive_document_refs=("a" * 64,))
    [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=(decision.rule_id,), snapshot=snapshot
    )
    assert reduced.final_state.value == "technical_error"
    assert reduced.reason_code == "snapshot_mismatch"
