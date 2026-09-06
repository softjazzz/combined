from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.malignancy_fact import (
    MalignancyFactResolver,
    build_malignancy_sources,
    build_stage_malignancy_sources,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


CREATED_AT = "2026-07-16T12:00:00+08:00"


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "pathology_exam_master": [
            {"specimen_name": "手术标本", "record_content": "病理送检申请资料。"}
        ],
        "pathology_exam_report": [
            {
                "diagnosis": "病理诊断资料。",
                "report_datetime": "2026-04-26 10:00:00",
            }
        ],
        "surgery_record": [{"content": "手术记录中包含本次手术经过。"}],
        "daily_course_record": [{"content": "病程记录中已记录病理结果与处理计划。"}],
        "diagnosis": [{"diagnosis_code": "C18.9"}],
        "inpat_drug_order": [
            {"generic_name": "受控化疗药物", "single_dose": "1", "drug_apply_method": "静滴"}
        ],
        "discharge_record": [{"content": "出院记录中包含后续肿瘤治疗计划。"}],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


class _RawResponseClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0
        self.kwargs: dict = {}

    async def generate(self, _prompt: str, **kwargs) -> dict:
        self.calls += 1
        self.kwargs = dict(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _malignancy_response(names: list[str], *, state: str) -> dict:
    return {
        "schema_version": "lx0609_malignancy_v1",
        "results": [
            {"ref": f"D{index:02d}", "state": state}
            for index, _name in enumerate(names, start=1)
        ],
    }


@pytest.mark.asyncio
async def test_208790_shape_allows_one_complete_32_diagnosis_response() -> None:
    names = [f"明确非恶性诊断{index}" for index in range(1, 33)]
    client = _RawResponseClient(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            _malignancy_response(
                                names, state="explicit_nonmalignant"
                            ),
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 915,
                "completion_tokens": 1500,
                "total_tokens": 2415,
            },
            "_api_time": 0.2,
        }
    )
    resolver = MalignancyFactResolver(client)

    result = await resolver.resolve(
        build_malignancy_sources(
            diagnosis_state="available",
            diagnosis_rows=tuple({"diagnosis_name": name} for name in names),
            pathology_state="empty",
            pathology_rows=(),
        )
    )

    assert result.state == "absent"
    assert resolver.claim_usage().total_tokens == 2415
    assert client.calls == 1
    assert client.kwargs == {
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
    }


@pytest.mark.asyncio
async def test_inpatient_pathology_can_confirm_malignancy_without_discharge_diagnosis() -> None:
    client = _Client(
        [
            {
                "schema_version": "lx0609_malignancy_v1",
                "results": [
                    {"ref": "D01", "state": "explicit_nonmalignant"},
                    {"ref": "P01", "state": "explicit_malignant"},
                ],
            }
        ]
    )
    resolver = MalignancyFactResolver(client)

    result = await resolver.resolve(
        build_stage_malignancy_sources(
            visit_stage="inpatient",
            admission_state="present",
            admission_rows=({"diagnosis_name": "肺部感染"},),
            diagnosis_state="empty",
            diagnosis_rows=(),
            discharge_diagnosis_state="empty",
            discharge_diagnosis_rows=(),
            pathology_state="present",
            pathology_rows=({"diagnosis": "右肺浸润性腺癌"},),
        )
    )

    assert result.state == "confirmed"
    assert len(client.prompts) == 1
    assert "P01" in client.prompts[0]


def _material_session(
    *,
    truncated_master: bool = False,
    surgery_process: str = "术中切取病灶标本并送病理检查。",
    empty_targets: bool = False,
    surgery_rows: tuple[dict, ...] | None = None,
    daily_course_rows: tuple[dict, ...] | None = None,
):
    rows_by_source = {
        "pathology_exam_master": (
            {"specimen_name": "手术标本", "record_content": "病理送检申请资料。"},
        ),
        "pathology_exam_report": (
            ()
            if truncated_master
            else (
                {
                    "diagnosis": "病理诊断资料。",
                    "report_datetime": "2026-04-26 10:00:00",
                },
            )
        ),
        "surgery_record": (
            surgery_rows
            if surgery_rows is not None
            else (() if empty_targets else ({"surgery_process": surgery_process},))
        ),
        "daily_course_record": (
            daily_course_rows
            if daily_course_rows is not None
            else (
                ()
                if empty_targets
                else ({"record_content": "病程记录中已记录病理结果与处理计划。"},)
            )
        ),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=truncated_master and source_key == "pathology_exam_master",
            limit_rows=1 if source_key == "pathology_exam_master" else 50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-013", "LX0609-019"),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-013", "LX0609-019"),
        ),
    )


@pytest.mark.asyncio
async def test_013_019_use_request_materials_without_family_live_query(monkeypatch):
    session = _material_session()

    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得由病理族自行查库")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden_reader)
    client = _Client([{"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            surgery_record=[{"record_content": "旧投影没有手术过程字段。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert "术中切取病灶标本" not in repr(result)


@pytest.mark.asyncio
async def test_typed_013_019_missing_semantic_client_is_technical_error_without_request():
    """模型执行能力未配置是技术失败，不能伪装为临床资料不足。"""

    session = _material_session(
        surgery_rows=({"record_content": "术后一般情况平稳。"},),
        daily_course_rows=({"record_content": "继续观察病情变化。"},),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013", "LX0609-019"),
    )

    assert result.results == ()
    assert result.llm_call_count == 0
    assert result.prompt_tokens == result.completion_tokens == result.total_tokens == 0
    assert [
        reduce_luxian_0609_rule_decision(decision).final_state.value
        for decision in result.decisions
    ] == ["technical_error", "technical_error"]
    assert [decision.reason_code for decision in result.decisions] == [
        "model_transport_error",
        "model_transport_error",
    ]


@pytest.mark.asyncio
async def test_direct_013_019_missing_semantic_client_is_llm_technical_error_without_request():
    """兼容直出结果也必须把模型能力缺失标记为 llm 执行失败。"""

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            surgery_record=[{"content": "术后一般情况平稳。"}],
            daily_course_record=[{"content": "继续观察病情变化。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=None,
    )

    assert result.decisions == ()
    assert result.llm_call_count == 0
    assert result.prompt_tokens == result.completion_tokens == result.total_tokens == 0
    assert [item["status"] for item in result.results] == [
        "technical_error",
        "technical_error",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "tumor_llm_failure",
        "tumor_llm_failure",
    ]
    assert [item["metadata"]["executor_type"] for item in result.results] == [
        "llm",
        "llm",
    ]


@pytest.mark.asyncio
async def test_typed_013_complete_empty_target_sources_are_non_compliant_without_model():
    session = _material_session(empty_targets=True)
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "non_compliant"
    assert dict(result.customer_display_facts)["LX0609-013"] == {
        "verification_kind": "pathology_result_documentation_check",
        "pathology_trigger_sources": [
            "pathology_exam_master",
            "pathology_exam_report",
        ],
        "checked_target_sources": [
            {"source": "surgery_record", "state": "empty"},
            {"source": "daily_course_record", "state": "empty"},
        ],
        "requirement_met": False,
        "report_time": "2026-04-26 10:00:00",
    }
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("surgery_rows", "daily_course_rows"),
    (
        (
            ({"record_content": "手术记录：病理检查结果提示病理诊断资料。"},),
            (),
        ),
        (
            (),
            ({"record_content": "病程记录：病理检查结果提示病理诊断资料。"},),
        ),
    ),
)
async def test_typed_013_accepts_documentation_from_either_complete_target_source(
    surgery_rows: tuple[dict, ...],
    daily_course_rows: tuple[dict, ...],
):
    """013 只要求任一完整目标文书记录已完成的病理结果。"""

    session = _material_session(
        surgery_rows=surgery_rows,
        daily_course_rows=daily_course_rows,
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "compliant"
    assert dict(result.customer_display_facts)["LX0609-013"]["requirement_met"] is True
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_019_uses_same_session_surgery_process_not_stale_payload(
    monkeypatch,
):
    session = _material_session()
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            surgery_record=[{"content": "旧投影明确未记录术中取材或送检。"}],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )

    assert result.results == ()
    assert result.llm_call_count == 0
    assert [item.rule_id for item in result.decisions] == ["LX0609-019"]
    assert (
        reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value
        == "compliant"
    )
    assert result.decisions[0].snapshot_hash == session.snapshot.snapshot_hash
    assert "旧投影明确未记录" not in repr(result)
    assert dict(result.customer_display_facts)["LX0609-019"] == {
        "verification_kind": "pathology_sampling_documentation_check",
        "pathology_trigger_sources": [
            "pathology_exam_master",
            "pathology_exam_report",
        ],
        "checked_target_sources": [
            {"source": "surgery_record", "state": "present"},
            {"source": "daily_course_record", "state": "present"},
        ],
        "documented_sources": ["surgery_record"],
        "requirement_met": True,
    }


@pytest.mark.asyncio
async def test_typed_019_material_change_updates_state_snapshot_and_refs(monkeypatch):
    positive_session = _material_session()
    negative_session = _material_session(
        surgery_process="术中未取材，暂不送病理检查。"
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-019",),
        "wrapper_rules": [_wrapper("LX0609-019")],
        "evidence_payload": _payload(
            surgery_record=[{"surgery_process": "旧投影始终称已送病理。"}]
        ),
        "institute_id": "safe-institute",
        "patient_id": "safe-patient",
        "visit_id": "safe-visit",
        "source_schema": None,
        "llm_client": None,
        "decision_rule_ids": ("LX0609-019",),
    }

    positive = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        evidence_snapshot=positive_session.snapshot,
        evidence_materials=positive_session.materials,
    )
    negative = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        evidence_snapshot=negative_session.snapshot,
        evidence_materials=negative_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        positive.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        negative.decisions[0]
    ).final_state.value == "technical_error"
    assert negative.decisions[0].reason_code == "model_transport_error"
    assert positive.decisions[0].snapshot_hash != negative.decisions[0].snapshot_hash
    assert positive.decisions[0].fact_refs != negative.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_typed_019_optional_llm_matches_raw_state_calls_tokens_and_prompt(
    monkeypatch,
):
    process = "术中未取材，暂不送病理检查。"
    session = _material_session(surgery_process=process)
    payload = _payload(surgery_record=[{"surgery_process": process}])
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    raw_client = _Client([{"is_compliant": False}])
    typed_client = _Client([{"is_compliant": False}])
    common = {
        "rule_ids": ("LX0609-019",),
        "wrapper_rules": [_wrapper("LX0609-019")],
        "evidence_payload": payload,
        "institute_id": "safe-institute",
        "patient_id": "safe-patient",
        "visit_id": "safe-visit",
        "source_schema": None,
    }

    raw = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=raw_client,
    )
    typed = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=typed_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )

    assert raw.results[0]["status"] == "non_compliant"
    assert reduce_luxian_0609_rule_decision(
        typed.decisions[0]
    ).final_state.value == "non_compliant"
    assert typed.results == ()
    assert raw.llm_call_count == typed.llm_call_count == 1
    assert raw.total_tokens == typed.total_tokens == 110
    assert raw_client.prompts == typed_client.prompts


@pytest.mark.asyncio
async def test_typed_019_complete_empty_surgery_keeps_present_daily_for_review():
    rows_by_source = {
        "pathology_exam_master": ({"specimen_name": "手术标本"},),
        "pathology_exam_report": ({"specimen_name": "手术标本"},),
        "surgery_record": (),
        "daily_course_record": (
            {"record_content": "病程记录未说明取材情况。SAFE_PRIVATE_TARGET"},
        ),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-019",),
        ),
    )
    client = _Client([{"is_compliant": False}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )

    decision = result.decisions[0]
    assert reduce_luxian_0609_rule_decision(decision).final_state.value == "non_compliant"
    assert decision.reason_code == "requirement_violated"
    assert decision.snapshot_hash == session.snapshot.snapshot_hash
    assert decision.fact_refs
    assert result.customer_display_facts == ((
        "LX0609-019",
        {
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": [
                "pathology_exam_master",
                "pathology_exam_report",
            ],
            "checked_target_sources": [
                {"source": "surgery_record", "state": "empty"},
                {"source": "daily_course_record", "state": "present"},
            ],
        },
    ),)
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "SAFE_PRIVATE_TARGET" not in repr(result)


@pytest.mark.asyncio
async def test_typed_019_strong_surgery_sampling_overrides_complete_empty_daily():
    rows_by_source = {
        "pathology_exam_master": ({"specimen_name": "手术标本"},),
        "pathology_exam_report": ({"specimen_name": "手术标本"},),
        "surgery_record": ({"surgery_process": "术中切取标本并送病理检查。"},),
        "daily_course_record": (),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-019",),
        ),
    )
    client = _Client([])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )

    decision = result.decisions[0]
    assert reduce_luxian_0609_rule_decision(decision).final_state.value == "compliant"
    assert decision.reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_019_complete_empty_targets_are_programmatic_defect():
    rows_by_source = {
        "pathology_exam_master": ({"specimen_name": "手术标本"},),
        "pathology_exam_report": ({"specimen_name": "手术标本"},),
        "surgery_record": (),
        "daily_course_record": (),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-019",),
        ),
    )
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )
    decision = result.decisions[0]
    assert reduce_luxian_0609_rule_decision(decision).final_state.value == "non_compliant"
    assert decision.reason_code == "requirement_violated"
    assert result.customer_display_facts == (("LX0609-019", {
        "failure_kind": "pathology_sampling_not_documented",
        "pathology_trigger_sources": [
            "pathology_exam_master",
            "pathology_exam_report",
        ],
        "checked_target_sources": [
            {"source": "surgery_record", "state": "empty"},
            {"source": "daily_course_record", "state": "empty"},
        ],
    }),)
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_reason"),
    (
        ("available", "compliant", "requirement_satisfied"),
        ("empty", "not_applicable", "trigger_absent_complete"),
        ("unavailable", "data_gap", "source_unavailable"),
        ("error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_019_preserves_pathology_source_four_states(
    monkeypatch,
    mode,
    expected_state,
    expected_reason,
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key in {"pathology_exam_master", "pathology_exam_report"}:
            if mode == "unavailable":
                raise SourceEvidenceUnavailable("private unavailable detail")
            if mode == "error":
                raise SourceEvidenceQueryError("private query detail")
            rows = (
                []
                if mode == "empty"
                else [{"record_content": "病理送检资料。"}]
            )
        elif source_key == "surgery_record":
            rows = [{"surgery_process": "术中切取标本并送病理检查。"}]
        elif source_key == "daily_course_record":
            rows = [{"record_content": "病程已记录病理送检。"}]
        else:
            rows = []
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-019",),
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )
    decision = result.decisions[0]

    assert reduce_luxian_0609_rule_decision(decision).final_state.value == expected_state
    assert decision.reason_code == expected_reason
    assert result.llm_call_count == 0
    assert "private unavailable detail" not in repr(result)
    assert "private query detail" not in repr(result)


@pytest.mark.asyncio
async def test_typed_019_target_query_error_is_technical_and_never_calls_model(
    monkeypatch,
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            raise SourceEvidenceQueryError("private target query detail")
        rows = (
            [{"record_content": "病理送检资料。"}]
            if source_key in {"pathology_exam_master", "pathology_exam_report"}
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-019",),
        ),
    )
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )

    decision = result.decisions[0]
    assert reduce_luxian_0609_rule_decision(decision).final_state.value == "technical_error"
    assert decision.reason_code == "source_query_error"
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "private target query detail" not in repr(result)


@pytest.mark.asyncio
async def test_typed_027_late_malignant_code_is_not_lost_by_prompt_row_limit() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "diagnosis":
            rows = [
                {"diagnosis_code": f"D{index:02d}"}
                for index in range(8)
            ] + [{"diagnosis_code": "C18.9"}]
        elif source_key == "discharge_record":
            rows = [{"record_content": "出院后继续肿瘤专科治疗计划。"}]
        else:
            rows = []
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-027",),
        ),
    )
    client = _Client([{"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",),
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-027",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "compliant"
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert dict(result.customer_display_facts)["LX0609-027"] == {
        "verification_kind": "malignant_discharge_plan_check",
        "malignant_diagnosis_present": True,
        "plan_items": {
            "future_plan": True,
            "tumor_treatment": True,
            "follow_up": False,
        },
        "requirement_met": True,
    }


@pytest.mark.asyncio
async def test_truncated_pathology_material_fails_closed_without_model_or_live_query(
    monkeypatch,
):
    session = _material_session(truncated_master=True)

    def forbidden_reader(**_kwargs):
        raise AssertionError("截断材料不得回退族内查库")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden_reader)
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        ("empty", "not_applicable"),
        ("unavailable", "data_gap"),
        ("error", "data_gap"),
    ],
)
async def test_snapshot_pathology_source_state_never_replays_family_reader(
    monkeypatch,
    mode: str,
    expected_status: str,
):
    def row_reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key in {"pathology_exam_master", "pathology_exam_report"}:
            if mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if mode == "error":
                raise SourceEvidenceQueryError()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-013", "LX0609-019"),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=row_reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=("LX0609-013", "LX0609-019"),
        ),
    )

    def forbidden_reader(**_kwargs):
        raise AssertionError("快照已声明来源四态时不得重放族内查询")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden_reader)
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            surgery_record=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        expected_status,
        expected_status,
    ]
    assert result.llm_call_count == 0


def _chemo_discharge_material_session(
    *,
    truncated_drug: bool = False,
    course_text: str = "2026-04-26 使用奥沙利铂 130mg 静滴，记录化疗经过。",
    course_record_time: str | None = None,
    chemotherapy_orders: tuple[dict, ...] | None = None,
    course_rows: tuple[dict, ...] | None = None,
):
    rows_by_source = {
        "diagnosis": ({"diagnosis_code": "C18.9"},),
        "inpat_drug_order": chemotherapy_orders
        or (
            {
                "drug_code": "safe-drug",
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        "daily_course_record": course_rows
        or (
            {
                "record_content": course_text,
                "record_time": course_record_time,
            },
        ),
        "discharge_record": (
            {"treatment_course": "出院记录中包含后续治疗计划。"},
        ),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=truncated_drug and source_key == "inpat_drug_order",
            limit_rows=1 if truncated_drug and source_key == "inpat_drug_order" else 50,
        )

    selected = ("LX0609-026",) if truncated_drug else ("LX0609-026", "LX0609-027")
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=selected,
        ),
    )


def _typed_013_027_session(
    *,
    diagnosis_code: str = "C18.9",
    discharge_text: str = "出院记录中包含后续肿瘤治疗计划。",
):
    rows_by_source = {
        "pathology_exam_master": (
            {"specimen_name": "手术标本", "record_content": "病理送检申请资料。"},
        ),
        "pathology_exam_report": (
            {
                "diagnosis": "病理诊断资料。",
                "report_datetime": "2026-04-26 10:00:00",
            },
        ),
        "surgery_record": (
            {"surgery_process": "术中切取病灶标本并送病理检查。"},
        ),
        "daily_course_record": (
            {"record_content": "病程记录中已记录病理结果与处理计划。"},
        ),
        "diagnosis": ({"diagnosis_code": diagnosis_code},),
        "discharge_record": ({"treatment_course": discharge_text},),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    selected = ("LX0609-013", "LX0609-027")
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=selected,
        ),
    )


@pytest.mark.asyncio
async def test_typed_013_027_emit_ordered_decisions_from_same_session(monkeypatch):
    session = _typed_013_027_session()
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-027")],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            surgery_record=[],
            daily_course_record=[],
            diagnosis=[],
            discharge_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client(
            [{"is_compliant": True}, {"is_compliant": False}]
        ),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013", "LX0609-027"),
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == [
        "LX0609-013",
        "LX0609-027",
    ]
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["compliant", "compliant"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110


@pytest.mark.asyncio
async def test_typed_027_uses_deterministic_plan_facts_while_legacy_stays_unchanged(
    monkeypatch,
):
    session = _typed_013_027_session()
    payload = _payload(
        surgery_record=[
            {"surgery_process": "术中切取病灶标本并送病理检查。"}
        ],
        discharge_record=[
            {"treatment_course": "出院记录中包含后续肿瘤治疗计划。"}
        ],
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    raw_client = _Client([{"is_compliant": True}, {"is_compliant": False}])
    typed_client = _Client([{"is_compliant": True}, {"is_compliant": False}])
    common = {
        "rule_ids": ("LX0609-013", "LX0609-027"),
        "wrapper_rules": [_wrapper("LX0609-013"), _wrapper("LX0609-027")],
        "evidence_payload": payload,
        "institute_id": "safe-institute",
        "patient_id": "safe-patient",
        "visit_id": "safe-visit",
        "source_schema": None,
    }

    raw = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=raw_client,
    )
    typed = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=typed_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013", "LX0609-027"),
    )

    assert [item["status"] for item in raw.results] == [
        "compliant",
        "non_compliant",
    ]
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in typed.decisions
    ] == ["compliant", "compliant"]
    assert typed.results == ()
    assert raw.llm_call_count == 2
    assert typed.llm_call_count == 1
    assert raw.total_tokens == 220
    assert typed.total_tokens == 110
    assert len(raw_client.prompts) == 2
    assert len(typed_client.prompts) == 1


@pytest.mark.asyncio
async def test_typed_027_material_change_updates_state_snapshot_and_refs(monkeypatch):
    malignant_session = _typed_013_027_session(diagnosis_code="C18.9")
    benign_session = _typed_013_027_session(diagnosis_code="D12.6")
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-027",),
        "wrapper_rules": [_wrapper("LX0609-027")],
        # 旧 payload 始终给出恶性事实；typed 结果必须只随材料变化。
        "evidence_payload": _payload(
            facts=[
                {
                    "fact_type": "current_visit_malignant_tumor",
                    "state": "present",
                    "source_key": "pathology_exam_report",
                    "current_visit_bound": True,
                }
            ]
        ),
        "institute_id": "safe-institute",
        "patient_id": "safe-patient",
        "visit_id": "safe-visit",
        "source_schema": None,
        "decision_rule_ids": ("LX0609-027",),
    }

    malignant = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=_Client([{"is_compliant": True}]),
        evidence_snapshot=malignant_session.snapshot,
        evidence_materials=malignant_session.materials,
    )
    benign = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        **common,
        llm_client=_Client([]),
        evidence_snapshot=benign_session.snapshot,
        evidence_materials=benign_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        malignant.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        benign.decisions[0]
    ).final_state.value == "not_applicable"
    assert malignant.decisions[0].snapshot_hash != benign.decisions[0].snapshot_hash
    assert malignant.decisions[0].fact_refs != benign.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_typed_026_is_explicit_data_gap_without_legacy_chemotherapy_fact(
    monkeypatch,
):
    session = _chemo_discharge_material_session(truncated_drug=True)
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = _Client([{"is_compliant": True}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload=_payload(
            facts=[
                {
                    "fact_type": "current_visit_chemotherapy_order",
                    "state": "present",
                    "source_key": "inpat_drug_order",
                    "current_visit_bound": True,
                }
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert result.results == ()
    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "data_gap"
    assert result.decisions[0].reason_code == "source_unavailable"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("course_text", "expected_state", "dose_state"),
    [
        (
            "2026-04-26 使用奥沙利铂 130mg 静滴，记录化疗经过。",
            "compliant",
            "matched",
        ),
        (
            "2026-04-26 使用奥沙利铂 100mg 静滴，记录化疗经过。",
            "non_compliant",
            "mismatched",
        ),
    ],
)
async def test_typed_026_compares_four_structured_order_fields_without_model(
    monkeypatch,
    course_text,
    expected_state,
    dose_state,
):
    session = _chemo_discharge_material_session(course_text=course_text)
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == expected_state
    facts = dict(result.customer_display_facts)["LX0609-026"]
    assert facts["field_results"] == {
        "drug_name": "matched",
        "dose": dose_state,
        "route": "matched",
        "time": "matched",
    }
    assert facts["missing_order_fields"] == []
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_026_does_not_borrow_fields_between_chemotherapy_events(
    monkeypatch,
):
    """两份医嘱的药名、剂量、用法不能跨不同病程条目拼成合规。"""

    session = _chemo_discharge_material_session(
        chemotherapy_orders=(
            {
                "drug_code": "safe-a",
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
            {
                "drug_code": "safe-b",
                "generic_name": "紫杉醇",
                "single_dose": "80",
                "single_dose_unit": "mg",
                "drug_apply_method": "滴注",
                "prescribed_datetime": "2026-04-27 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        course_rows=(
            {
                "record_content": "2026-04-26 使用奥沙利铂80mg滴注。",
                "record_time": "2026-04-26 10:00:00",
            },
            {
                "record_content": "2026-04-27 使用紫杉醇130mg静滴。",
                "record_time": "2026-04-27 10:00:00",
            },
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "non_compliant"
    assert result.decisions[0].reason_code == "requirement_violated"
    assert dict(result.customer_display_facts)["LX0609-026"]["field_results"] == {
        "drug_name": "matched",
        "dose": "mismatched",
        "route": "mismatched",
        "time": "matched",
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_026_fails_closed_when_two_orders_share_one_course_clause(
    monkeypatch,
):
    """同一病程片段不能臆断为两份独立化疗医嘱均已执行。"""

    duplicated_order = {
        "generic_name": "奥沙利铂",
        "single_dose": "130",
        "single_dose_unit": "mg",
        "drug_apply_method": "静滴",
        "prescribed_datetime": "2026-04-26 09:00:00",
        "drug_type": "抗肿瘤化疗药物",
        "order_status": "执行",
    }
    session = _chemo_discharge_material_session(
        chemotherapy_orders=(
            {**duplicated_order, "drug_code": "safe-a"},
            {**duplicated_order, "drug_code": "safe-b"},
        ),
        course_rows=(
            {
                "record_content": "2026-04-26 使用奥沙利铂130mg静滴。",
                "record_time": "2026-04-26 10:00:00",
            },
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "data_gap"
    assert result.decisions[0].reason_code == "required_field_missing"
    facts = dict(result.customer_display_facts)["LX0609-026"]
    assert facts["unresolved_event_count"] == 1
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_026_keeps_one_event_fields_together_within_one_course_record(
    monkeypatch,
):
    """单一化疗事件可在同篇病程的相邻句中记录，不能被拆成跨事件串值。"""

    session = _chemo_discharge_material_session(
        chemotherapy_orders=(
            {
                "drug_code": "safe-cisplatin",
                "generic_name": "顺铂",
                "single_dose": "100",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        course_rows=(
            {
                "record_content": "2026-04-26 予顺铂化疗。剂量100mg，静滴。",
                "record_time": "2026-04-26 10:00:00",
            },
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "compliant"
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_026_keeps_each_multi_drug_event_with_its_following_detail_clauses(
    monkeypatch,
):
    """同篇多药时，每个药名后的相邻剂量/用法仍属于该药，不能误报资料不足。"""

    session = _chemo_discharge_material_session(
        chemotherapy_orders=(
            {
                "drug_code": "safe-oxaliplatin",
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
            {
                "drug_code": "safe-paclitaxel",
                "generic_name": "紫杉醇",
                "single_dose": "80",
                "single_dose_unit": "mg",
                "drug_apply_method": "滴注",
                "prescribed_datetime": "2026-04-26 10:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        course_rows=(
            {
                "record_content": (
                    "2026-04-26 予奥沙利铂化疗。剂量130mg，静滴。"
                    "2026-04-26 予紫杉醇化疗。剂量80mg，滴注。"
                ),
                "record_time": "2026-04-26 11:00:00",
            },
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "compliant"
    assert dict(result.customer_display_facts)["LX0609-026"]["field_results"] == {
        "drug_name": "matched",
        "dose": "matched",
        "route": "matched",
        "time": "matched",
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_026_does_not_take_detail_clauses_past_the_next_drug_name(
    monkeypatch,
):
    """后一种药的剂量和用法不能回填到前一种药。"""

    session = _chemo_discharge_material_session(
        chemotherapy_orders=(
            {
                "drug_code": "safe-oxaliplatin",
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
            {
                "drug_code": "safe-paclitaxel",
                "generic_name": "紫杉醇",
                "single_dose": "80",
                "single_dose_unit": "mg",
                "drug_apply_method": "滴注",
                "prescribed_datetime": "2026-04-26 10:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        course_rows=(
            {
                "record_content": (
                    "2026-04-26 予奥沙利铂化疗。"
                    "2026-04-26 予紫杉醇化疗，剂量80mg，滴注。"
                ),
                "record_time": "2026-04-26 11:00:00",
            },
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "non_compliant"
    assert dict(result.customer_display_facts)["LX0609-026"]["field_results"] == {
        "drug_name": "matched",
        "dose": "mismatched",
        "route": "mismatched",
        "time": "matched",
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_027_requires_future_tumor_treatment_in_one_plan_clause(
    monkeypatch,
):
    """既往化疗与普通门诊复查不能拼成出院后肿瘤治疗计划。"""

    session = _typed_013_027_session(
        discharge_text="既往已完成化疗。建议门诊复查血常规。"
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",),
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-027",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == "non_compliant"
    assert result.decisions[0].reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-027"]
    assert facts["plan_items"] == {
        "future_plan": True,
        "tumor_treatment": False,
        "follow_up": True,
    }
    assert facts["requirement_met"] is False
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("discharge_text", "expected_state", "expected_treatment"),
    (
        ("出院后暂不化疗，定期复查。", "non_compliant", False),
        ("出院后不建议化疗，定期复查。", "non_compliant", False),
        ("出院后计划化疗，待病理明确后决定。", "non_compliant", False),
        ("出院后无不适，建议化疗。", "compliant", True),
        (
            "建议出院后辅助化疗，必要时根据耐受性调整剂量。",
            "compliant",
            True,
        ),
        ("出院后必要时化疗。", "non_compliant", False),
    ),
)
async def test_typed_027_does_not_treat_negative_or_pending_treatment_as_plan(
    monkeypatch,
    discharge_text,
    expected_state,
    expected_treatment,
):
    """治疗否定/待定无效，但与治疗无关的否定不影响明确计划。"""

    session = _typed_013_027_session(discharge_text=discharge_text)
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",),
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-027",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == expected_state
    facts = dict(result.customer_display_facts)["LX0609-027"]
    assert facts["plan_items"]["tumor_treatment"] is expected_treatment
    assert facts["requirement_met"] is expected_treatment
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("course_text", "course_record_time", "expected_state", "time_state"),
    [
        (
            "今日给予奥沙利铂130mg静滴，第1天。",
            "2026-04-26 10:00:00",
            "compliant",
            "matched",
        ),
        (
            "今日给予奥沙利铂130mg静滴，第1天。",
            "2026-04-27 10:00:00",
            "non_compliant",
            "mismatched",
        ),
        (
            "2026-04-27给予奥沙利铂130mg静滴，第1天。",
            "2026-04-26 10:00:00",
            "non_compliant",
            "mismatched",
        ),
        (
            "当日给予奥沙利铂130mg静滴，第1天。",
            None,
            "data_gap",
            "unknown",
        ),
        (
            "给予奥沙利铂130mg静滴，第1天。",
            "2026-04-26 10:00:00",
            "data_gap",
            "unknown",
        ),
    ],
)
async def test_typed_026_binds_course_time_semantics_to_record_date(
    monkeypatch,
    course_text,
    course_record_time,
    expected_state,
    time_state,
):
    session = _chemo_discharge_material_session(
        course_text=course_text,
        course_record_time=course_record_time,
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-026",),
    )

    assert reduce_luxian_0609_rule_decision(
        result.decisions[0]
    ).final_state.value == expected_state
    facts = dict(result.customer_display_facts)["LX0609-026"]
    assert facts["field_results"]["time"] == time_state
    assert result.llm_call_count == 0


@pytest.mark.parametrize(
    ("rule_id", "failure_scope", "mode", "expected_state", "expected_reason"),
    (
        ("LX0609-013", "pathology", "empty", "not_applicable", "trigger_absent_complete"),
        ("LX0609-013", "pathology", "unavailable", "data_gap", "source_unavailable"),
        ("LX0609-013", "pathology", "error", "technical_error", "source_query_error"),
        ("LX0609-013", "pathology", "truncated", "data_gap", "source_unavailable"),
        ("LX0609-013", "surgery", "error", "technical_error", "source_query_error"),
        ("LX0609-019", "surgery", "unavailable", "data_gap", "source_unavailable"),
        ("LX0609-019", "surgery", "error", "technical_error", "source_query_error"),
        ("LX0609-019", "surgery", "truncated", "data_gap", "source_unavailable"),
        ("LX0609-027", "diagnosis", "empty", "data_gap", "required_field_missing"),
        ("LX0609-027", "diagnosis", "unavailable", "data_gap", "source_unavailable"),
        ("LX0609-027", "diagnosis", "error", "technical_error", "source_query_error"),
        ("LX0609-027", "diagnosis", "truncated", "data_gap", "source_unavailable"),
        ("LX0609-027", "discharge", "error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_013_027_fail_closed_source_matrix(
    monkeypatch,
    rule_id,
    failure_scope,
    mode,
    expected_state,
    expected_reason,
):
    pathology_sources = {"pathology_exam_master", "pathology_exam_report"}

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        affected = (
            (failure_scope == "pathology" and source_key in pathology_sources)
            or (failure_scope == "diagnosis" and source_key == "diagnosis")
            or (failure_scope == "surgery" and source_key == "surgery_record")
            or (failure_scope == "discharge" and source_key == "discharge_record")
        )
        if affected and mode == "unavailable":
            raise SourceEvidenceUnavailable("private unavailable detail")
        if affected and mode == "error":
            raise SourceEvidenceQueryError("private query detail")
        rows = {
            "pathology_exam_master": [{"record_content": "病理送检资料。"}],
            "pathology_exam_report": [
                {
                    "diagnosis": "病理诊断资料。",
                    "report_datetime": "2026-04-26 10:00:00",
                }
            ],
            "surgery_record": [
                {"surgery_process": "术中切取标本并送病理检查。"}
            ],
            "daily_course_record": [{"record_content": "病程已记录病理处理。"}],
            "diagnosis": [{"diagnosis_code": "C18.9"}],
            "discharge_record": [{"treatment_course": "出院后继续专科治疗。"}],
        }.get(source_key, [])
        if affected and mode == "empty":
            rows = []
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=affected and mode == "truncated",
            limit_rows=max(1, len(rows)),
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=(rule_id,),
        ),
    )
    monkeypatch.setattr(
        tumor,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = _Client([{"is_compliant": True}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule_id,),
        wrapper_rules=[_wrapper(rule_id)],
        evidence_payload=_payload(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=(rule_id,),
    )
    decision = result.decisions[0]

    assert reduce_luxian_0609_rule_decision(decision).final_state.value == expected_state
    assert decision.reason_code == expected_reason
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "private unavailable detail" not in repr(result)
    assert "private query detail" not in repr(result)


@pytest.mark.asyncio
async def test_026_027_use_request_materials_without_family_live_query(monkeypatch):
    session = _chemo_discharge_material_session()

    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得由肿瘤族自行查库")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden_reader)
    client = _Client([{"is_compliant": False}, {"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-026"), _wrapper("LX0609-027")],
        evidence_payload=_payload(
            facts=[
                {
                    "fact_type": "current_visit_chemotherapy_order",
                    "state": "present",
                    "source_key": "inpat_drug_order",
                    "current_visit_bound": True,
                }
            ],
            diagnosis=[],
            inpat_drug_order=[],
            daily_course_record=[],
            discharge_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
    ]
    assert result.llm_call_count == 2
    assert result.total_tokens == 220


@pytest.mark.asyncio
async def test_026_truncated_drug_material_is_data_gap_without_reader_or_model(
    monkeypatch,
):
    session = _chemo_discharge_material_session(truncated_drug=True)

    def forbidden_reader(**_kwargs):
        raise AssertionError("截断医嘱材料不得回退族内查库")

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", forbidden_reader)
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload=_payload(
            facts=[
                {
                    "fact_type": "current_visit_chemotherapy_order",
                    "state": "present",
                    "source_key": "inpat_drug_order",
                    "current_visit_bound": True,
                }
            ],
            diagnosis=[],
            inpat_drug_order=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_pathology_source_triggers_013_019_once_each_and_keeps_customer_order():
    client = _Client([{"is_compliant": True}, {"is_compliant": False}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019", "LX0609-013"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == ["LX0609-013", "LX0609-019"]
    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert result.llm_call_count == 2
    assert result.total_tokens == 220
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_no_pathology_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(pathology_exam_master=[], pathology_exam_report=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "not_applicable",
        "not_applicable",
    ]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_pathology_report_without_result_is_data_gap_but_sampling_rule_can_run():
    client = _Client([{"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(pathology_exam_report=[{"report_status": "完成"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_row",
    [
        {"report_status": "完成"},
        {"eye_findings": "肉眼所见材料", "microscope_findings": "镜下所见材料"},
        {"diagnosis": "病理诊断资料。"},
        {"report_datetime": "2026-04-26 10:00:00"},
        {"diagnosis": "病理诊断资料。", "report_datetime": "待补录"},
        {
            "record_content": "本报告尚在审核中，最终病理诊断待补充，请结合后续正式报告。",
            "report_datetime": "2026-04-26 10:00:00",
        },
        {"diagnosis": "病理诊断资料。", "report_datetime": "2026-04-26"},
        {"diagnosis": "待诊断", "report_datetime": "2026-04-26 10:00:00"},
        {"diagnosis": "诊断待定", "report_datetime": "2026-04-26 10:00:00"},
        {
            "record_content": "病理结果待定。",
            "report_datetime": "2026-04-26 10:00:00",
        },
        {
            "record_content": "病理诊断待完善。",
            "report_datetime": "2026-04-26 10:00:00",
        },
    ],
)
async def test_013_requires_final_result_and_report_time_before_model(
    report_row: dict,
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload=_payload(pathology_exam_report=[report_row]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "pathology_final_result_or_report_time_unavailable"
    )
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_key", "content"),
    [
        ("surgery_record", "切除阑尾后向家属展示，标本送病检。"),
        ("surgery_record", "术中取材并送病理检查。"),
        ("daily_course_record", "术中切取组织标本，已送病理检查。"),
    ],
)
async def test_019_documented_sampling_is_programmatic_compliant_without_model(
    source_key: str, content: str
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(**{source_key: [{"content": content}]}),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.results[0]["metadata"]["reason_code"] == "pathology_sampling_recorded"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_019_reads_documented_sampling_from_live_surgery_process_without_model(
    monkeypatch,
):
    raw_process = "术中切取病灶标本并送病理检查。SAFE_RAW_SURGERY_PROCESS"

    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [
                {
                    "record_content": "",
                    "surgery_process": raw_process,
                }
            ]
        return []

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(
            surgery_record=[
                {
                    "record_content": "手术记录已组装，但旧投影尚无手术过程字段。",
                }
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.results[0]["metadata"]["reason_code"] == "pathology_sampling_recorded"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []
    assert "SAFE_RAW_SURGERY_PROCESS" not in repr(result)


@pytest.mark.asyncio
async def test_013_does_not_read_live_surgery_process_projection(monkeypatch):
    calls: list[str] = []

    def _reader(**kwargs):
        calls.append(kwargs["source_key"])
        return []

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])
    payload = _payload(
        pathology_exam_master=[{"content": "病理申请"}],
        pathology_exam_report=[
            {
                "diagnosis": "病理诊断已完成",
                "report_datetime": "2026-06-02 08:00:00",
            }
        ],
        surgery_record=[{"record_content": "既有手术记录投影"}],
        daily_course_record=[{"record_content": "既有日常病程投影"}],
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload=payload,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert calls == []


def test_native_surgery_record_reader_projects_surgery_process(monkeypatch):
    captured: dict[str, object] = {}

    class _Rows:
        def mappings(self):
            return self

        def all(self):
            return [{"surgery_process": "safe-internal-material"}]

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = dict(params)
            return _Rows()

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _Engine())
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm"
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda *_: {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "surgery_process",
            "record_content",
        },
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_qualified_table",
        lambda *_: '"cdm"."surgery_record"',
    )

    rows = source_evidence_reader.read_luxian_0609_native_source_rows(
        source_key="surgery_record",
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert rows == [{"surgery_process": "safe-internal-material"}]
    assert '"surgery_process"' in str(captured["sql"])
    assert captured["params"]["limit_rows"] == source_evidence_reader._source_limit(
        "surgery_record"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "拟将标本送病理检查。",
        "建议术中取材送病检。",
        "未送病理，待术后结合结果。",
        "手术记录未记录术中取材及送检情况。",
        "术中取材：    ",
        "标本送检情况：无。",
        "切除阑尾后，家属拒绝标本送病检。",
        "切除阑尾，标本不送病检。",
        "标本送检已取消。",
        "暂缓取材送病理检查。",
        "已填写标本送检申请资料。",
        "病理送检单已打印。",
        "标本送检单已打印。",
        "送检。",
    ],
)
async def test_019_prospective_negative_or_empty_sampling_text_does_not_short_circuit(
    content: str,
):
    client = _Client([{"is_compliant": False}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(surgery_record=[{"content": content}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "术前未取材，术中切取阑尾标本并送病检。",
        "拟术中取材，实际术中取材并送病理检查。",
    ],
)
async def test_019_local_completed_action_is_not_blocked_by_earlier_negative_clause(
    content: str,
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(surgery_record=[{"content": content}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_019_sampling_override_does_not_change_013_or_its_model_call():
    client = _Client([{"is_compliant": False}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            surgery_record=[{"content": "术中切取病灶标本并送病理检查。"}]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
    ]
    assert [item["metadata"]["executor_type"] for item in result.results] == [
        "llm",
        "program",
    ]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_malignant_and_chemo_facts_gate_026_027_without_keyword_fallback():
    facts = [
        {
            "fact_type": "current_visit_chemotherapy_order",
            "state": "present",
            "source_key": "inpat_drug_order",
            "current_visit_bound": True,
        }
    ]
    client = _Client([{"is_compliant": False}, {"is_compliant": True}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-026"), _wrapper("LX0609-027")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "compliant"]
    assert result.llm_call_count == 2

    no_strong_fact = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload=_payload(
            facts=[],
            daily_course_record=[{"content": "病程自由文本仅写拟行化疗。"}],
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert no_strong_fact.results[0]["status"] == "data_gap"
    assert no_strong_fact.llm_call_count == 0


@pytest.mark.asyncio
async def test_nonmalignant_diagnosis_is_not_applicable_and_source_error_is_sanitized(
    monkeypatch,
):
    nonmalignant = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-026"), _wrapper("LX0609-027")],
        evidence_payload=_payload(diagnosis=[{"diagnosis_code": "K35.9"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in nonmalignant.results] == [
        "not_applicable",
        "not_applicable",
    ]

    uncoded = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",),
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload=_payload(diagnosis=[{"diagnosis_type": "出院诊断"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert uncoded.results[0]["status"] == "data_gap"

    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", _failed_reader)
    failed = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=tumor.TUMOR_PATHOLOGY_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in tumor.TUMOR_PATHOLOGY_RULE_IDS],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            diagnosis=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in failed.results] == ["data_gap"] * 4
    assert secret not in repr(failed)


@pytest.mark.asyncio
async def test_complete_uncoded_nonmalignant_diagnoses_are_classified_once_for_026_027():
    diagnosis_names = [
        "功能性消化不良",
        "便秘",
        "吸入性肺炎",
        "低蛋白血症",
        "上颌骨骨折",
        "急性胃黏膜病变",
        "闭合性颅脑损伤重型",
        "中度贫血",
        "结膜炎",
        "创伤性脑疝",
        "颧骨骨折",
        "低钙血症",
        "发热",
        "眼球破裂伤",
        "营养风险",
        "颅骨骨折",
        "眉弓裂伤",
        "心律失常",
        "创伤性急性硬膜下出血",
        "脑挫伤",
        "蛛网膜下腔出血",
        "大脑镰下疝",
        "面部裂伤",
        "视神经损伤",
        "脑水肿",
        "脑出血",
        "脑疝",
        "下颌骨骨折",
        "肋骨骨折",
        "尺骨骨折",
        "细菌性肺炎",
        "低钾血症",
    ]
    rows_by_source = {
        "diagnosis": tuple(
            {"diagnosis_name": name, "diagnosis_type": "出院诊断"}
            for name in diagnosis_names
        ),
        "inpat_drug_order": (),
        "daily_course_record": (),
        "inpat_registration.discharge_horizon": (
            {"discharge_datetime": "2026-07-08 10:00:00+08:00"},
        ),
        "discharge_record": ({"treatment_course": "出院后定期复查。"},),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    selected = ("LX0609-026", "LX0609-027")
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",),
            selected_rule_ids=selected,
        ),
    )
    client = _Client(
        [_malignancy_response(diagnosis_names, state="explicit_nonmalignant")]
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=selected,
    )

    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "safe-institute" not in prompt
    assert "safe-patient" not in prompt
    assert "safe-visit" not in prompt
    assert "D01" in prompt and "低钾血症" in prompt
    assert "只能输出一个JSON对象" in prompt
    assert '"schema_version":"lx0609_malignancy_v1","results":[' in prompt


@pytest.mark.asyncio
async def test_inpatient_uses_admission_diagnosis_for_026_and_skips_027() -> None:
    rows_by_source = {
        "admission_record_diagnosis": (
            {"diagnosis_name": "右肺腺癌", "diagnosis_code": ""},
        ),
        # 在院病例不应因首页/出院诊断尚未形成而失败关闭，也不能读取其陈旧值。
        "diagnosis": (),
        "discharge_record_diagnosis": (
            {"diagnosis_name": "陈旧的非恶性出院诊断", "diagnosis_code": ""},
        ),
        "inpat_registration.discharge_horizon": ({"discharge_datetime": None},),
        "inpat_drug_order": (
            {
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        "daily_course_record": (
            {
                "record_content": "2026-04-26 使用奥沙利铂130mg静滴，记录化疗经过。",
                "record_time": "2026-04-26 10:00:00",
            },
        ),
        "discharge_record": (),
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    selected = ("LX0609-026", "LX0609-027")
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=selected
        ),
    )
    client = _Client(
        [
            {
                "schema_version": "lx0609_malignancy_v1",
                "results": [
                    {"ref": "D01", "state": "explicit_malignant"},
                ],
            }
        ]
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=selected,
    )

    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["compliant", "not_applicable"]
    assert [item.reason_code for item in result.decisions] == [
        "requirement_satisfied",
        "trigger_absent_complete",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "右肺腺癌" in client.prompts[0]
    assert "陈旧的非恶性出院诊断" not in client.prompts[0]


@pytest.mark.asyncio
async def test_inpatient_incomplete_admission_diagnosis_cannot_be_absent() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = {
            "admission_record_diagnosis": (
                {"diagnosis_name": "明确非恶性疾病", "diagnosis_code": ""},
            ),
            "diagnosis": ({"diagnosis_name": "陈旧出院诊断"},),
            "inpat_registration.discharge_horizon": ({"discharge_datetime": None},),
            "inpat_drug_order": (
                {
                    "generic_name": "奥沙利铂",
                    "drug_type": "抗肿瘤化疗药物",
                },
            ),
        }.get(source_key, ())
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=source_key == "admission_record_diagnosis",
            limit_rows=1 if source_key == "admission_record_diagnosis" else 50,
        )

    selected = ("LX0609-026",)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=selected
        ),
    )
    client = _Client(
        [
            {
                "schema_version": "lx0609_malignancy_v1",
                "results": [
                    {"ref": "D01", "state": "explicit_nonmalignant"},
                ],
            }
        ]
    )

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=selected,
    )

    reduced = reduce_luxian_0609_rule_decision(result.decisions[0])
    assert reduced.final_state.value == "data_gap"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {
            "choices": [{"message": {"content": "not-json"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "lx0609_malignancy_v1",
                                "results": [
                                    {"ref": "FORGED", "state": "explicit_malignant"}
                                ],
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "lx0609_malignancy_v1",
                                "results": [
                                    {"ref": "D01", "state": "explicit_malignant"}
                                ],
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": "1", "completion_tokens": 1, "total_tokens": 2},
        },
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "lx0609_malignancy_v1",
                                "results": [
                                    {"ref": "D01", "state": "explicit_malignant"}
                                ],
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3},
        },
        RuntimeError("model unavailable"),
    ],
)
async def test_027_malignancy_llm_contract_failure_is_technical_error(response):
    selected = ("LX0609-027",)

    def reader(**kwargs):
        rows = {
            "diagnosis": ({"diagnosis_name": "肺部占位性质待定"},),
            "inpat_registration.discharge_horizon": (
                {"discharge_datetime": "2026-07-08 10:00:00+08:00"},
            ),
            "discharge_record": ({"treatment_course": "出院后定期复查。"},),
        }.get(kwargs["source_key"], ())
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=selected
        ),
    )
    client = _RawResponseClient(response)
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=selected,
    )

    reduced = reduce_luxian_0609_rule_decision(result.decisions[0])
    assert reduced.final_state.value == "technical_error"
    assert client.calls == 1
    assert "FORGED" not in repr(result)


def test_pathology_result_and_explicit_missing_facts_are_programmatic() -> None:
    report = tumor.SourceMaterial(
        "present", ({"diagnosis": "胃腺癌，淋巴结2/18枚转移"},)
    )
    recorded_course = tumor.SourceMaterial(
        "present", ({"record_content": "病理报告胃腺癌，结合分期制定方案。"},)
    )
    missing_surgery = tumor.SourceMaterial(
        "present", ({"record_content": "手术记录未记录病理取材及送检情况，未记录病理结果。"},)
    )
    missing_course = tumor.SourceMaterial(
        "present", ({"record_content": "病程记录未记录病理取材及送检情况，未记录病理结果。"},)
    )

    assert tumor._has_documented_pathology_result(report, recorded_course)
    pending_course = tumor.SourceMaterial(
        "present", ({"record_content": "病理报告尚待回报。"},)
    )
    report_without_diagnosis = tumor.SourceMaterial(
        "present", ({"diagnosis": "", "record_content": ""},)
    )
    assert not tumor._has_documented_pathology_result(
        report_without_diagnosis,
        pending_course,
    )
    assert tumor._all_targets_explicitly_missing(
        tumor._PATHOLOGY_RESULT_MISSING_PATTERN,
        missing_surgery,
        missing_course,
    )
    assert tumor._all_targets_explicitly_missing(
        tumor._PATHOLOGY_SAMPLING_MISSING_PATTERN,
        missing_surgery,
        missing_course,
    )
