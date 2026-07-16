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

    async def generate(self, prompt: str) -> dict:
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


def _material_session(*, truncated_master: bool = False):
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
            {"surgery_process": "术中切取病灶标本并送病理检查。"},
        ),
        "daily_course_record": (
            {"record_content": "病程记录中已记录病理结果与处理计划。"},
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
