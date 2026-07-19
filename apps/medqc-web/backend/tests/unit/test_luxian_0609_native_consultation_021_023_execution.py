from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609 import source_registry
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


def _rows(**overrides):
    values = {
        "consultation_record": [
            {
                "record_time": "2026-01-01 09:00:00",
                "record_content": "会诊材料。",
            }
        ],
        "daily_course_record": [],
        "senior_course_record": [
            {
                "record_time": "2026-01-02 10:00:00",
                "record_content": "达到读取上限的上级查房材料",
            }
            for _ in range(48)
        ],
        "inpat_drug_order": [
            {"prescribed_datetime": "2026-01-02 10:00:00", "generic_name": "辅助医嘱"}
            for _ in range(64)
        ],
        # 辅助佐证时区格式不同只应丢弃该佐证，不得阻断完整病程判断。
        "exam_item_report": [
            {
                "report_time": "2026-01-02 10:00:00+08:00",
                "exam_name": "辅助检查",
            }
        ],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    values.update(overrides)
    return values


def _stage1(*, application="clear", opinion="clear", confidence="high", recommendations=None, ref="consultation_record-1"):
    return {
        "episodes": [
            {
                "episode_ref": ref,
                "application_state": application,
                "opinion_state": opinion,
                "normalized_recommendations": list(recommendations or []),
                "confidence": confidence,
                "input_refs": [ref],
            }
        ]
    }


def _recommendation():
    return {
        "type": "treatment",
        "item": "调整治疗方案",
    }


class _QueueClient:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.prompts = []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        value = self.payloads.pop(0)
        if isinstance(value, Exception):
            raise value
        return {"content": json.dumps(value, ensure_ascii=False), "usage": {}}


async def _execute(monkeypatch, *, rows, client, rule_ids=("LX0609-021", "LX0609-022")):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_kwargs: rows[source_key],
    )
    return await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=rule_ids,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )


def _typed_session(monkeypatch, *, rows, source_states=None, omit_material=()):
    source_states = dict(source_states or {})
    source_keys = (
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
        "exam_item_report",
        "labtest_item_report",
        "surgery_record",
    )
    original_registered = source_registry.is_registered_luxian_0609_source_key
    original_accepts = source_registry.source_key_accepts_query_version
    original_complete = source_registry.source_key_supports_proven_completeness
    monkeypatch.setattr(
        source_registry,
        "is_registered_luxian_0609_source_key",
        lambda key: key in source_keys or original_registered(key),
    )
    monkeypatch.setattr(
        source_registry,
        "source_key_accepts_query_version",
        lambda key, version: key in source_keys or original_accepts(key, version),
    )
    monkeypatch.setattr(
        source_registry,
        "source_key_supports_proven_completeness",
        lambda key, version: key in source_keys or original_complete(key, version),
    )
    observations = []
    materials = {}
    all_document_refs = []
    for source_key in source_keys:
        state = source_states.get(source_key, "available")
        source_rows = tuple(dict(item) for item in rows.get(source_key, ()))
        query_version = (
            "snapshot-provider-surgery_record-v2"
            if source_key == "surgery_record"
            else f"snapshot-provider-{source_key}-v1"
        )
        refs = ()
        if state in {"unavailable", "error"}:
            query_state = QueryStatus(state)
            completeness = SourceCompleteness.UNPROVEN
            record_count = None
        else:
            material = SnapshotSourceRows(
                source_key=source_key,
                rows=source_rows,
                truncated=state == "truncated",
                limit_rows=64,
            )
            refs = build_material_document_refs(source_key, source_rows)
            query_state = QueryStatus.AVAILABLE if source_rows else QueryStatus.EMPTY
            completeness = (
                SourceCompleteness.TRUNCATED
                if state == "truncated"
                else SourceCompleteness.COMPLETE
            )
            record_count = len(source_rows)
            if source_key not in omit_material:
                materials[source_key] = material
            all_document_refs.extend(refs)
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=record_count,
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=refs,
                ),
                error_code="QUERY_ERROR" if state == "error" else "",
                reason_code="SOURCE_UNAVAILABLE" if state == "unavailable" else "",
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=all_document_refs,
        created_at="2026-07-18T10:00:00+08:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=materials,
    )
@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_consultation_is_not_applicable_without_model(monkeypatch):
    client = _QueueClient(AssertionError("model must not be called"))
    result = await _execute(
        monkeypatch,
        rows=_rows(consultation_record=[]),
        client=client,
        rule_ids=("LX0609-021", "LX0609-022", "LX0609-023"),
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 3
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application", "opinion", "confidence", "expected"),
    [
        ("clear", "clear", "high", ("compliant", "compliant")),
        ("vague", "missing", "high", ("non_compliant", "non_compliant")),
        ("absent", "absent", "high", ("not_applicable", "not_applicable")),
        ("unknown", "unknown", "high", ("uncertain", "uncertain")),
        ("clear", "clear", "low", ("uncertain", "uncertain")),
    ],
)
async def test_021_022_controlled_state_mapping(
    monkeypatch, application, opinion, confidence, expected
):
    client = _QueueClient(
        _stage1(application=application, opinion=opinion, confidence=confidence)
    )
    result = await _execute(monkeypatch, rows=_rows(), client=client)

    assert tuple(item["status"] for item in result.results) == expected
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_021_specific_problem_with_tail_request_is_modelled_as_clear(monkeypatch):
    client = _QueueClient(_stage1(application="clear", opinion="absent"))
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": "患者胸痛反复发作，申请心内科明确诊疗方案，请会诊。",
                }
            ]
        ),
        client=client,
        rule_ids=("LX0609-021",),
    )

    assert result.results[0]["status"] == "compliant"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stage_one_requires_exact_episode_coverage_and_refs(monkeypatch):
    client = _QueueClient(_stage1(ref="consultation_record-2"))
    result = await _execute(monkeypatch, rows=_rows(), client=client)

    assert [item["status"] for item in result.results] == [
        "uncertain",
        "uncertain",
    ]
    assert "会诊材料" not in repr(result)


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_field",
    (
        "input_refs",
        "application_state",
        "confidence",
        "normalized_recommendations",
    ),
)
def test_stage_one_invalid_episode_is_isolated_without_inventing_missing_or_vague(
    invalid_field,
):
    from app.services.luxian_0609 import (
        native_consultation_021_023_execution as module,
    )

    valid = _stage1(ref="consultation_record-1")["episodes"][0]
    invalid = _stage1(ref="consultation_record-2")["episodes"][0]
    invalid_values = {
        "input_refs": ["consultation_record-1"],
        "application_state": "unsupported",
        "confidence": "unsupported",
        "normalized_recommendations": [
            {"type": "unsupported", "item": "调整方案"}
        ],
    }
    invalid[invalid_field] = invalid_values[invalid_field]

    episodes = module._parse_stage1(
        {"episodes": [valid, invalid]},
        ("consultation_record-1", "consultation_record-2"),
    )

    assert episodes[0].application_state == "clear"
    assert episodes[0].opinion_state == "clear"
    assert episodes[1].application_state == "unknown"
    assert episodes[1].opinion_state == "unknown"
    assert episodes[1].confidence < 0.8
    assert episodes[1].recommendations == ()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rule_id", "valid_state", "expected_status"),
    (
        ("LX0609-021", "vague", "non_compliant"),
        ("LX0609-022", "vague", "non_compliant"),
        ("LX0609-021", "clear", "evaluation_unknown"),
        ("LX0609-022", "clear", "evaluation_unknown"),
    ),
)
def test_021_022_reducer_prioritizes_valid_defect_before_invalid_episode(
    rule_id,
    valid_state,
    expected_status,
):
    from app.services.luxian_0609 import (
        native_consultation_021_023_execution as module,
    )

    valid = _stage1(
        application=valid_state,
        opinion=valid_state,
        ref="consultation_record-1",
    )["episodes"][0]
    invalid = _stage1(ref="consultation_record-2")["episodes"][0]
    invalid["confidence"] = "unsupported"
    episodes = module._parse_stage1(
        {"episodes": [valid, invalid]},
        ("consultation_record-1", "consultation_record-2"),
    )

    assert module._state_outcome(rule_id, episodes).status == expected_status


@pytest.mark.unit
@pytest.mark.parametrize(
    "episodes",
    (
        [],
        [
            _stage1(ref="consultation_record-1")["episodes"][0],
            _stage1(ref="consultation_record-1")["episodes"][0],
        ],
    ),
)
def test_stage_one_top_level_coverage_or_duplicate_is_whole_payload_invalid(
    episodes,
):
    from app.services.luxian_0609 import (
        native_consultation_021_023_execution as module,
    )

    with pytest.raises(module._SemanticInvalid):
        module._parse_stage1(
            {"episodes": episodes},
            ("consultation_record-1", "consultation_record-2"),
        )


@pytest.mark.unit
def test_stage_one_prompt_keeps_clinical_clear_vague_and_action_rubric():
    from app.services.luxian_0609 import (
        native_consultation_021_023_execution as module,
    )

    prompt = module._stage1_prompt(
        ({"ref": "consultation_record-1", "text": "会诊材料"},)
    )

    assert "具体症状、检查、诊断或评估" in prompt
    assert "具体诊断、检查、治疗、用药、复查或处置" in prompt
    assert "泛化原则判为vague" in prompt
    assert "每个可执行动作" in prompt
    assert "application_state只评申请段" in prompt
    assert "opinion_state只评意见段" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_clear_opinion_without_recommendations_is_unknown_not_na(
    monkeypatch,
):
    client = _QueueClient(_stage1(opinion="clear", recommendations=[]))
    result = await _execute(
        monkeypatch,
        rows=_rows(),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "uncertain"
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("quality", "expected_status"),
    (
        ("specific", "uncertain"),
        ("vague_or_copied", "non_compliant"),
    ),
)
async def test_023_valid_defect_precedes_invalid_episode_otherwise_unknown(
    monkeypatch,
    quality,
    expected_status,
):
    stage1 = _stage1(
        ref="consultation_record-1",
        recommendations=[_recommendation()],
    )
    invalid = _stage1(ref="consultation_record-2")["episodes"][0]
    invalid["confidence"] = "unsupported"
    stage1["episodes"].append(invalid)
    stage2 = {
        "executions": [
            {
                "episode_ref": "consultation_record-1",
                "recommendation_ref": "consultation_record-1-recommendation-1",
                "execution_record_quality": quality,
                "implementation_match": "supported",
                "association_state": "contextual",
                "evidence_refs": ["daily_course_record-1"],
                "confidence": "high",
            }
        ]
    }
    client = _QueueClient(stage1, stage2)
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": "第一份会诊材料。",
                },
                {
                    "record_time": "2026-01-01 10:00:00",
                    "record_content": "第二份会诊材料。",
                },
            ],
            daily_course_record=[
                {
                    "record_time": "2026-01-02 09:00:00",
                    "record_content": "会诊后的病程记录。",
                }
            ],
            senior_course_record=[],
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_invalid_episode_without_other_action_is_unknown_not_na(
    monkeypatch,
):
    stage1 = _stage1(
        application="absent",
        opinion="absent",
        ref="consultation_record-1",
    )
    invalid = _stage1(ref="consultation_record-2")["episodes"][0]
    invalid["confidence"] = "unsupported"
    stage1["episodes"].append(invalid)
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": "第一份会诊材料。",
                },
                {
                    "record_time": "2026-01-01 10:00:00",
                    "record_content": "第二份会诊材料。",
                },
            ]
        ),
        client=_QueueClient(stage1),
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "uncertain"
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stage_one_transport_error_is_technical(monkeypatch):
    result = await _execute(
        monkeypatch,
        rows=_rows(),
        client=_QueueClient(RuntimeError("PRIVATE_MARKER")),
    )

    assert [item["status"] for item in result.results] == ["technical_error"] * 2
    assert "PRIVATE_MARKER" not in repr(result)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_support_sources_cannot_replace_course_execution_record(monkeypatch):
    client = _QueueClient(_stage1(recommendations=[_recommendation()]))
    result = await _execute(
        monkeypatch,
        rows=_rows(
            senior_course_record=[],
            inpat_drug_order=[
                {
                    "prescribed_datetime": "2026-01-02 09:00:00",
                    "generic_name": "支持性医嘱",
                }
            ]
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_execution_before_opinion_is_data_gap(monkeypatch):
    client = _QueueClient(_stage1(recommendations=[_recommendation()]))
    result = await _execute(
        monkeypatch,
        rows=_rows(
            senior_course_record=[],
            daily_course_record=[
                {
                    "record_time": "2025-12-31 09:00:00",
                    "record_content": "早于会诊的执行记录。",
                }
            ]
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("quality", "match", "refs", "expected"),
    [
        ("specific", "supported", ["daily_course_record-1"], "compliant"),
        ("specific", "contradicted", ["daily_course_record-1"], "non_compliant"),
        ("vague_or_copied", "supported", ["daily_course_record-1"], "non_compliant"),
        ("vague_or_copied", "unknown", ["daily_course_record-1"], "non_compliant"),
        ("absent", "unknown", [], "not_applicable"),
        ("unknown", "unknown", [], "uncertain"),
        ("specific", "supported", ["inpat_drug_order-1"], "uncertain"),
    ],
)
async def test_023_execution_quality_mapping(
    monkeypatch, quality, match, refs, expected
):
    stage2 = {
        "executions": [
            {
                "episode_ref": "consultation_record-1",
                "recommendation_ref": "consultation_record-1-recommendation-1",
                "execution_record_quality": quality,
                "implementation_match": match,
                "association_state": (
                    "contextual" if quality in {"specific", "vague_or_copied"} else "none"
                ),
                "evidence_refs": refs,
                "confidence": "high",
            }
        ]
    }
    client = _QueueClient(
        _stage1(recommendations=[_recommendation()]),
        stage2,
    )
    result = await _execute(
        monkeypatch,
        rows=_rows(
            senior_course_record=[],
            daily_course_record=[
                {
                    "record_time": "2026-01-02 09:00:00",
                    "record_content": "执行记录。",
                }
            ],
            inpat_drug_order=[
                {
                    "prescribed_datetime": "2026-01-02 10:00:00",
                    "generic_name": "佐证医嘱",
                }
            ],
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == expected
    assert result.llm_call_count == 2


@pytest.mark.unit
def test_023_ambiguous_association_is_unknown_even_when_quality_is_specific():
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    episodes = module._parse_stage1(
        _stage1(recommendations=[_recommendation()]),
        ("consultation_record-1",),
    )
    states = module._parse_stage2(
        {
            "executions": [
                {
                    "episode_ref": "consultation_record-1",
                    "recommendation_ref": "consultation_record-1-recommendation-1",
                    "execution_record_quality": "specific",
                    "implementation_match": "supported",
                    "association_state": "ambiguous",
                    "evidence_refs": ["daily_course_record-1"],
                    "confidence": "high",
                }
            ]
        },
        episodes,
        frozenset({"daily_course_record-1"}),
        frozenset({"daily_course_record-1"}),
        {"consultation_record-1": frozenset({"daily_course_record-1"})},
    )

    assert states == (("unknown", "semantic_low_confidence"),)


@pytest.mark.unit
@pytest.mark.parametrize("association_state", ("contextual", "explicit"))
def test_023_evidence_cannot_be_reused_across_consultation_episodes(
    association_state,
):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    first = _stage1(
        ref="consultation_record-1",
        recommendations=[{"type": "treatment", "item": "调整方案一"}],
    )["episodes"][0]
    second = _stage1(
        ref="consultation_record-2",
        recommendations=[{"type": "monitoring", "item": "复查指标二"}],
    )["episodes"][0]
    episodes = module._parse_stage1(
        {"episodes": [first, second]},
        ("consultation_record-1", "consultation_record-2"),
    )
    executions = [
        {
            "episode_ref": episode.episode_ref,
            "recommendation_ref": episode.recommendations[0][0],
            "execution_record_quality": "specific",
            "implementation_match": "supported",
            "association_state": association_state,
            "evidence_refs": ["daily_course_record-1"],
            "confidence": "high",
        }
        for episode in episodes
    ]

    states = module._parse_stage2(
        {"executions": executions},
        episodes,
        frozenset({"daily_course_record-1"}),
        frozenset({"daily_course_record-1"}),
        {
            "consultation_record-1": frozenset({"daily_course_record-1"}),
            "consultation_record-2": frozenset({"daily_course_record-1"}),
        },
    )

    assert states == (
        ("unknown", "semantic_low_confidence"),
        ("unknown", "semantic_low_confidence"),
    )


@pytest.mark.unit
def test_stage_one_recommendation_refs_are_python_assigned_and_duplicate_facts_deduplicated():
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    payload = _stage1(
        recommendations=[
            {"recommendation_ref": "duplicate", "type": "treatment", "item": "调整方案"},
            {"recommendation_ref": "duplicate", "type": "monitoring", "item": "复查指标"},
            {"recommendation_ref": "duplicate", "type": "treatment", "item": "调整方案"},
        ]
    )

    episodes = module._parse_stage1(payload, ("consultation_record-1",))

    assert episodes[0].recommendations == (
        ("consultation_record-1-recommendation-1", "treatment", "调整方案"),
        ("consultation_record-1-recommendation-2", "monitoring", "复查指标"),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_mixed_timezone_fails_closed_before_stage_two(monkeypatch):
    client = _QueueClient(_stage1(recommendations=[_recommendation()]))
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {
                    "record_time": "2026-01-01 09:00:00+08:00",
                    "record_content": "会诊材料。",
                }
            ],
            daily_course_record=[
                {
                    "record_time": "2026-01-02 09:00:00",
                    "record_content": "病程材料。",
                }
            ],
            senior_course_record=[],
            inpat_drug_order=[],
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_partial_execution_missing_is_non_compliant(monkeypatch):
    stage1 = _stage1(
        recommendations=[
            {"type": "treatment", "item": "事项一"},
            {"type": "monitoring", "item": "事项二"},
        ]
    )
    stage2 = {
        "executions": [
            {
                "episode_ref": "consultation_record-1",
                "recommendation_ref": "consultation_record-1-recommendation-1",
                "execution_record_quality": "specific",
                "implementation_match": "supported",
                "association_state": "contextual",
                "evidence_refs": ["daily_course_record-1"],
                "confidence": "high",
            },
            {
                "episode_ref": "consultation_record-1",
                "recommendation_ref": "consultation_record-1-recommendation-2",
                "execution_record_quality": "absent",
                "implementation_match": "unknown",
                "association_state": "none",
                "evidence_refs": [],
                "confidence": "high",
            },
        ]
    }
    client = _QueueClient(stage1, stage2)
    result = await _execute(
        monkeypatch,
        rows=_rows(
            daily_course_record=[
                {"record_time": "2026-01-02 09:00:00", "record_content": "执行记录"}
            ],
            senior_course_record=[],
            inpat_drug_order=[],
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.llm_call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_live_reader_limit_is_fail_closed_without_model(monkeypatch):
    client = _QueueClient(AssertionError("model must not be called"))
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {"record_time": "2026-01-01 09:00:00", "record_content": "会诊"}
                for _ in range(48)
            ]
        ),
        client=client,
        rule_ids=("LX0609-021",),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_typed_021_reuses_one_session_and_refs_only_consultation(monkeypatch):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    rows = _rows()
    rows["daily_course_record"] = [
        {"record_time": "2026-01-01 08:00:00", "record_content": "无关材料"}
    ]
    snapshot, materials = _typed_session(monkeypatch, rows=rows)
    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must reuse session")),
    )
    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_QueueClient(_stage1()),
        evidence_materials=materials,
        evidence_snapshot=snapshot,
        decision_rule_ids=("LX0609-021",),
    )

    consultation_ref = next(
        item.snapshot_ref.removeprefix("sha256:")
        for item in snapshot.observations
        if item.source_key == "consultation_record"
    )
    assert result.results == ()
    assert len(result.decisions) == 1
    assert result.decisions[0].fact_refs == (consultation_ref,)
    assert "无关材料" not in repr(result)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_evidence"),
    [
        ("truncated", "data_gap"),
        ("unavailable", "data_gap"),
        ("error", "technical_error"),
    ],
)
async def test_typed_source_states_fail_closed_without_db_or_model(
    monkeypatch, state, expected_evidence
):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    snapshot, materials = _typed_session(
        monkeypatch,
        rows=_rows(),
        source_states={"consultation_record": state},
    )
    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must reuse session")),
    )
    client = _QueueClient(AssertionError("model must not be called"))
    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
        evidence_materials=materials,
        evidence_snapshot=snapshot,
        decision_rule_ids=("LX0609-021",),
    )

    assert result.results == ()
    assert result.decisions[0].evidence_state.value == expected_evidence
    assert result.llm_call_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_typed_available_snapshot_missing_material_fails_closed(monkeypatch):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    snapshot, materials = _typed_session(
        monkeypatch,
        rows=_rows(),
        omit_material=("consultation_record",),
    )
    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not query DB")),
    )
    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_QueueClient(AssertionError("model must not be called")),
        evidence_materials=materials,
        evidence_snapshot=snapshot,
        decision_rule_ids=("LX0609-021",),
    )

    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_stage_two_consumes_stage_one_recommendation(monkeypatch):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    rows = {
        "consultation_record": [
            {
                "record_time": "2026-01-01 09:00:00",
                "record_content": "申请目的和会诊意见正文仅作为裁剪输入。",
            }
        ],
        "daily_course_record": [
            {
                "record_time": "2026-01-02 09:00:00",
                "record_content": "后续执行记录正文仅作为裁剪输入。",
            },
            {
                "record_time": "2026-01-02 11:00:00",
                "record_content": "时间合法但语义无关的病程也必须交给模型判断关联。",
            },
            {
                "record_time": None,
                "record_content": "缺时间的病程不得阻断同来源有效记录。",
            },
        ],
        # 一个权威病程来源和一个辅助来源达到读取上限，不得拖死完整的日常病程来源。
        "senior_course_record": [
            {
                "record_time": "2026-01-02 10:00:00",
                "record_content": "达到读取上限的上级查房材料",
            }
            for _ in range(48)
        ],
        "inpat_drug_order": [
            {"prescribed_datetime": "2026-01-02 10:00:00", "generic_name": "辅助医嘱"}
            for _ in range(64)
        ],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }

    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_kwargs: rows[source_key],
    )

    class FakeClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate(self, prompt: str):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                payload = {
                    "episodes": [
                        {
                            "episode_ref": "consultation_record-1",
                            "application_state": "clear",
                            "opinion_state": "clear",
                            "normalized_recommendations": [
                                {
                                    "type": "medication",
                                    "item": "受控归一化事项A",
                                }
                            ],
                            "confidence": "high",
                            "input_refs": ["consultation_record-1"],
                        }
                    ]
                }
            else:
                assert "受控归一化事项A" in prompt
                assert "consultation_record-1-recommendation-1" in prompt
                assert "allowed_evidence_refs" in prompt
                assert "时间合法但语义无关的病程也必须交给模型判断关联" in prompt
                assert "association_state" in prompt
                payload = {
                    "executions": [
                        {
                            "episode_ref": "consultation_record-1",
                            "recommendation_ref": "consultation_record-1-recommendation-1",
                            "execution_record_quality": "specific",
                            "implementation_match": "supported",
                            "association_state": "contextual",
                            "evidence_refs": ["daily_course_record-1"],
                            "confidence": "high",
                        }
                    ]
                }
            return {
                "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
                "usage": {},
                "_api_time": 0.25,
            }

    client = FakeClient()
    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-023",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert result.llm_call_count == 2
    assert result.api_time == 0.5
    assert tuple(item["rule_id"] for item in result.results) == ("LX0609-023",)
    assert result.results[0]["status"] == "compliant"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_023_both_course_sources_truncated_fail_closed_before_stage_two(monkeypatch):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    rows = _rows(
        daily_course_record=[
            {
                "record_time": "2026-01-02 09:00:00",
                "record_content": "达到读取上限的日常病程材料",
            }
            for _ in range(48)
        ]
    )
    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_kwargs: rows[source_key],
    )
    client = _QueueClient(_stage1(recommendations=[_recommendation()]))

    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-023",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert result.llm_call_count == 1
    assert result.results[0]["status"] == "data_gap"
    assert len(client.prompts) == 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first_quality", "expected_status"),
    [
        ("specific", "uncertain"),
        ("vague_or_copied", "non_compliant"),
    ],
)
async def test_023_rejects_course_evidence_before_its_own_consultation(
    monkeypatch, first_quality, expected_status
):
    stage1 = {
        "episodes": [
            {
                "episode_ref": "consultation_record-1",
                "application_state": "clear",
                "opinion_state": "clear",
                "normalized_recommendations": [
                    {"type": "treatment", "item": "事项一"}
                ],
                "confidence": "high",
                "input_refs": ["consultation_record-1"],
            },
            {
                "episode_ref": "consultation_record-2",
                "application_state": "clear",
                "opinion_state": "clear",
                "normalized_recommendations": [
                    {"type": "monitoring", "item": "事项二"}
                ],
                "confidence": "high",
                "input_refs": ["consultation_record-2"],
            },
        ]
    }
    stage2 = {
        "executions": [
            {
                "episode_ref": "consultation_record-1",
                "recommendation_ref": "consultation_record-1-recommendation-1",
                "execution_record_quality": first_quality,
                "implementation_match": "supported",
                "association_state": "explicit",
                "evidence_refs": ["daily_course_record-1"],
                "confidence": "high",
            },
            {
                "episode_ref": "consultation_record-2",
                "recommendation_ref": "consultation_record-2-recommendation-1",
                "execution_record_quality": "specific",
                "implementation_match": "supported",
                "association_state": "explicit",
                "evidence_refs": ["daily_course_record-1"],
                "confidence": "high",
            },
        ]
    }
    client = _QueueClient(stage1, stage2)
    result = await _execute(
        monkeypatch,
        rows=_rows(
            consultation_record=[
                {"record_time": "2026-01-01 09:00:00", "record_content": "会诊一"},
                {"record_time": "2026-01-03 09:00:00", "record_content": "会诊二"},
            ],
            daily_course_record=[
                {"record_time": "2026-01-02 09:00:00", "record_content": "仅位于两次会诊之间"}
            ],
            senior_course_record=[],
            inpat_drug_order=[],
            exam_item_report=[],
        ),
        client=client,
        rule_ids=("LX0609-023",),
    )

    stage2_payload = json.loads(client.prompts[1].split("输入：", 1)[1])
    allowed_by_episode = {
        item["episode_ref"]: item["allowed_evidence_refs"]
        for item in stage2_payload["consultation_facts"]
    }
    assert allowed_by_episode == {
        "consultation_record-1": ["daily_course_record-1"],
        "consultation_record-2": [],
    }
    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_typed_material_row_budget_matches_live_reader_fail_closed(monkeypatch):
    from app.services.luxian_0609 import native_consultation_021_023_execution as module

    rows = _rows(
        consultation_record=[
            {"record_time": "2026-01-01 09:00:00", "record_content": "会诊材料"}
            for _ in range(48)
        ]
    )
    snapshot, materials = _typed_session(monkeypatch, rows=rows)
    monkeypatch.setattr(
        module,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must reuse session")),
    )

    result = await module.execute_luxian_0609_native_consultation_021_023_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_QueueClient(AssertionError("model must not be called")),
        evidence_materials=materials,
        evidence_snapshot=snapshot,
        decision_rule_ids=("LX0609-021",),
    )

    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.llm_call_count == 0
