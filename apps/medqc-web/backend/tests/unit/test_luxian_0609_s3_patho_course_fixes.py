"""Stage 3 P1-2 & P1-6a 回归单测：病理引文空白还原与重试、06-02-02 空手术表守卫扩展、01-01-02 短主诉纠偏重试。"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.course_quality import rule_018
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.native_tumor_pathology_execution import (
    execute_luxian_0609_native_tumor_pathology_rules,
)
from app.services.luxian_0609.pathology_documentation_extraction import (
    SCHEMA_VERSION as PATHOLOGY_SCHEMA_VERSION,
    PathologyDocument,
    PathologyEvent,
    extract_pathology_documentation_facts,
)
from luxian_0609_pathology_test_facts import (
    PathologyFactsClient,
    default_pathology_facts,
)


class _SequencedClient:
    def __init__(self, responses: Sequence[Any]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.kwargs: list[dict[str, Any]] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.kwargs.append(dict(kwargs))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict) and "choices" in item:
            return item
        content = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
            "_api_time": 0.1,
        }


def _pathology_payload(
    *,
    event: str = "P1",
    state: str = "documented",
    document: str | None = "d1",
    quote: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PATHOLOGY_SCHEMA_VERSION,
        "events": [
            {
                "event": event,
                "state": state,
                "document": document,
                "quote": quote,
            }
        ],
    }


def _scripted_pathology_client(*states: str) -> PathologyFactsClient:
    def script(
        sampling: bool,
        events: list[dict[str, Any]],
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        defaults = default_pathology_facts(sampling, events, documents)
        answers: list[dict[str, Any]] = []
        for event, state, default in zip(events, states, defaults):
            if state == "documented" and default["state"] == "documented":
                answers.append(default)
            elif state == "documented":
                doc = documents[0]
                answers.append(
                    {
                        "event": event["event"],
                        "state": "documented",
                        "document": doc["document"],
                        "quote": doc["body"][:20],
                    }
                )
            else:
                answers.append(
                    {
                        "event": event["event"],
                        "state": state,
                        "document": None,
                        "quote": None,
                    }
                )
        return answers

    return PathologyFactsClient(script)


async def _run_06_02_02(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    client: Any = None,
    additional_source_keys: Sequence[str] = (),
) -> tuple[Any, Any, dict[str, Any]]:
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=False,
            limit_rows=500,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-02-02",),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-09-20T10:00:00+08:00",
        row_reader=reader,
        additional_source_keys=tuple(additional_source_keys),
        evaluation_horizon_snapshot={
            "institute_id": "INST",
            "patient_id": "PAT",
            "visit_id": "VIS",
            "record_scene": "final",
            "evaluation_basis": "discharge_datetime",
            "resolution_status": "resolved",
            "evaluation_horizon": "2026-09-17",
            "admission_datetime": "2026-09-10 11:58:00",
            "discharge_datetime": "2026-09-17 09:00:00",
            "discharge_time_precision": "datetime",
        },
    )
    llm_client = client if client is not None else PathologyFactsClient()
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-06-02-02",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-06-02-02",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-06-02-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(result.customer_display_facts).get(
            "LX0609-06-02-02"
        ),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    return result, reduced, final


# ---------------------------------------------------------------------------
# P1-2a: pathology_documentation_extraction whitespace restoration + 1 retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p1_2a_whitespace_difference_quote_restored_to_exact_source_on_first_attempt() -> None:
    source_body = (
        "今日行电子支气管镜检查， 留取肺泡灌洗液\n"
        "送检脱落细胞学检查，过程顺利。"
    )
    # 模型去掉了 PDF 折行/多余空格
    model_quote = "留取肺泡灌洗液送检脱落细胞学检查"
    client = _SequencedClient([_pathology_payload(quote=model_quote)])

    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "冲洗液")],
        documents=[PathologyDocument("doc-1", "日常病程记录", "2026-08-21 15:09:00", source_body)],
        llm_client=client,
    )

    assert extraction.state == "ready"
    assert extraction.llm_call_count == 1
    assert extraction.events["P1"].state == "documented"
    assert extraction.events["P1"].document_key == "doc-1"
    assert extraction.events["P1"].quote == "留取肺泡灌洗液\n送检脱落细胞学检查"
    assert extraction.events["P1"].quote in source_body


@pytest.mark.asyncio
async def test_p1_2a_whitespace_difference_with_redaction_placeholder_restored() -> None:
    source_body = "患者张三，男，65岁，术中取右肺上叶 组织送病理检查。主刀医师：李四。"

    class _RedactedWhitespaceClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
            self.prompts.append(prompt)
            body = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["documents"][0]["body"]
            # 去掉“右肺上叶 组织”中间的排版空格
            quote = body.split("。")[0].replace("右肺上叶 组织", "右肺上叶组织") + "。"
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                _pathology_payload(quote=quote), ensure_ascii=False
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            }

    client = _RedactedWhitespaceClient()
    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "右肺上叶")],
        documents=[PathologyDocument("doc-1", "手术记录", "2026-08-30 12:00:00", source_body)],
        llm_client=client,
    )

    assert extraction.state == "ready"
    assert extraction.llm_call_count == 1
    assert "张三" not in client.prompts[0]
    assert "右肺上叶 组织" in extraction.events["P1"].quote


@pytest.mark.asyncio
async def test_p1_2a_token_splitting_whitespace_triggers_retry_and_recovers() -> None:
    source_body = "胃镜下于胃窦取活检组织10块送病理检查。"
    client = _SequencedClient(
        [
            # 第1次拆开数字词元（10 -> 1 0），不得直接放行
            _pathology_payload(quote="胃窦取活检组织1 0块送病理检查"),
            # 第2次纠偏后逐字返回
            _pathology_payload(quote="胃窦取活检组织10块送病理检查"),
        ]
    )

    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "胃窦组织")],
        documents=[PathologyDocument("doc-1", "日常病程记录", "2026-07-01 12:00:00", source_body)],
        llm_client=client,
    )

    assert extraction.state == "ready"
    assert extraction.llm_call_count == 2
    assert extraction.total_tokens == 90
    assert extraction.events["P1"].quote == "胃窦取活检组织10块送病理检查"
    assert "上一次输出未通过校验" in client.prompts[1]
    assert "逐字复制" in client.prompts[1]


@pytest.mark.asyncio
async def test_p1_2a_fabricated_quote_retries_once_then_fails_closed() -> None:
    source_body = "术后恢复平稳，继续抗感染治疗。"
    client = _SequencedClient(
        [
            _pathology_payload(quote="术中标本已送病理检查。"),
            _pathology_payload(quote="仍为虚构的取材送检描述。"),
        ]
    )

    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "胃窦组织")],
        documents=[PathologyDocument("doc-1", "日常病程记录", "2026-07-01 12:00:00", source_body)],
        llm_client=client,
    )

    assert (extraction.state, extraction.reason_code) == (
        "technical_error",
        "tumor_llm_invalid_output",
    )
    assert extraction.llm_call_count == 2
    assert extraction.total_tokens == 90


@pytest.mark.asyncio
async def test_p1_2a_invalid_json_recovers_on_second_attempt() -> None:
    source_body = "行胃镜下胃窦黏膜活检，标本送病理检查。"
    client = _SequencedClient(
        [
            "{invalid json",
            _pathology_payload(quote="行胃镜下胃窦黏膜活检，标本送病理检查。"),
        ]
    )

    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "胃窦黏膜")],
        documents=[PathologyDocument("doc-1", "日常病程记录", "2026-07-01 12:00:00", source_body)],
        llm_client=client,
    )

    assert extraction.state == "ready"
    assert extraction.llm_call_count == 2
    assert "合法JSON对象" in client.prompts[1]


@pytest.mark.asyncio
async def test_p1_2a_transport_error_on_first_attempt_does_not_retry() -> None:
    client = _SequencedClient([TimeoutError("synthetic timeout")])

    extraction = await extract_pathology_documentation_facts(
        sampling=True,
        events=[PathologyEvent("P1", "胃窦组织")],
        documents=[PathologyDocument("doc-1", "日常病程记录", "2026-07-01 12:00:00", "已送病理检查。")],
        llm_client=client,
    )

    assert (extraction.state, extraction.reason_code) == ("technical_error", "model_timeout")
    assert extraction.llm_call_count == 1


# ---------------------------------------------------------------------------
# P1-2b: LX0609-06-02-02 empty surgery_record guard expansion (#23 FP fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p1_2b_appendectomy_empty_surgery_record_with_postop_course_is_data_gap() -> None:
    """复现 #23：腹腔镜阑尾切除术 surgery_record=0 行，病理诊断无“切除”二字，应降级 data_gap。"""
    rows = {
        "pathology_exam_master": [
            {
                "document_id": "m1",
                "pathology_exam_id": "P1",
                "specimen_name": "阑尾",
                "surgery_name": "",
            }
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "阑尾",
                "diagnosis": "(阑尾)：急性化脓性阑尾炎。",
                "eye_findings": "阑尾：带系膜阑尾一段，长7.5cm，管径0.8cm。",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-09-10 15:38:00",
                "document_title": "术前术者查看病人记录",
                "record_content": "拟在全麻下行腹腔镜下阑尾切除术，已向家属交代手术风险。",
            }
        ],
        "postsurg_firstcourse_record": [
            {
                "document_id": "pfc1",
                "record_time": "2026-09-10 20:00:00",
                "document_title": "术后首次病程记录",
                "record_content": "患者今日在全麻下行腹腔镜下阑尾切除术，手术顺利，安返病房。",
            }
        ],
        "surgery_application": [
            {
                "document_id": "sa1",
                "surgery_name": "腹腔镜下阑尾切除术",
                "order_status": "已执行",
            }
        ],
    }

    result, reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
        additional_source_keys=("postsurg_firstcourse_record", "surgery_application"),
    )

    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_empty"
    assert "手术记录" in final["findings"]
    # 辅助手术来源的文档引用绝不能越权进入 06-02-02 的客户证据
    evidence_sources = {item["source_type"] for item in final.get("customer_evidence") or []}
    assert "postsurg_firstcourse_record" not in evidence_sources
    assert "surgery_application" not in evidence_sources
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_p1_2b_generic_pathology_with_postsurg_record_in_session_is_data_gap() -> None:
    """即使病理诊断不含切除/阑尾字样，只要会话已有术后首次病程记录且手术记录为空，仍降级 data_gap。"""
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "胆囊"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "胆囊",
                "diagnosis": "慢性胆囊炎",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-09-12 09:00:00",
                "record_content": "患者一般情况可，生命体征平稳。",
            }
        ],
        "postsurg_firstcourse_record": [
            {
                "document_id": "pfc1",
                "record_time": "2026-09-11 16:00:00",
                "record_content": "今日全麻下行腹腔镜下胆囊切除术，术后安返病房。",
            }
        ],
    }

    _result, _reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
        additional_source_keys=("postsurg_firstcourse_record",),
    )

    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_empty"


@pytest.mark.asyncio
async def test_p1_2b_standalone_session_detects_daily_course_surgery_evidence() -> None:
    """单规则运行（会话无 postsurg_firstcourse_record）时，日常病程明确写明术后/切除术也能降级 data_gap。"""
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "肿物"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "肿物",
                "diagnosis": "脂肪瘤",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-09-12 09:00:00",
                "record_content": "患者全麻下行腹腔镜下肿物切除术，术后第1天切口敷料干燥。",
            }
        ],
    }

    _result, _reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
    )

    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_empty"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("daily_text", "extra_rows", "extra_keys"),
    [
        ("胃镜检查顺利，患者无不适。", {}, ()),
        ("超声引导下经皮穿刺活检过程顺利，无明显出血。", {}, ()),
        ("患者既往3年前因阑尾炎行阑尾切除术后，本次行电子胃镜检查顺利。", {}, ()),
        (
            "电子肠镜检查顺利，嘱清淡饮食。",
            {
                "surgery_application": [
                    {
                        "document_id": "sa-cancel",
                        "surgery_name": "腹腔镜下胆囊切除术",
                        "order_status": "取消",
                    }
                ],
                "anesthesia_record": [
                    {
                        "document_id": "an-endo",
                        "record_content": "行无痛胃镜检查静脉麻醉，过程顺利。",
                    }
                ],
            },
            ("surgery_application", "anesthesia_record"),
        ),
    ],
)
async def test_p1_2b_non_surgical_biopsy_with_empty_surgery_record_stays_non_compliant(
    daily_text: str,
    extra_rows: dict[str, list[dict[str, Any]]],
    extra_keys: tuple[str, ...],
) -> None:
    """非手术活检/内镜病例（含既往手术史、已取消手术申请、无痛内镜麻醉）空手术表不得误降级。"""
    rows: dict[str, Any] = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "胃窦黏膜"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "胃窦黏膜",
                "diagnosis": "慢性浅表性胃炎",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-09-12 09:00:00",
                "record_content": daily_text,
            }
        ],
        **extra_rows,
    }

    _result, _reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
        additional_source_keys=extra_keys,
    )

    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"


@pytest.mark.asyncio
async def test_p1_2b_present_surgery_record_omitting_sampling_stays_non_compliant() -> None:
    """已有手术记录但遗漏病理取材描述的手术病例必须维持 non_compliant。"""
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "阑尾"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "阑尾",
                "diagnosis": "(阑尾)：急性化脓性阑尾炎。",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [
            {
                "document_id": "s1",
                "record_time": "2026-09-10 18:00:00",
                "surgery_process": "行腹腔镜下阑尾切除术，止血彻底，关闭切口，手术顺利。",
            }
        ],
        "daily_course_record": [],
        "postsurg_firstcourse_record": [
            {
                "document_id": "pfc1",
                "record_time": "2026-09-10 20:00:00",
                "record_content": "患者行腹腔镜下阑尾切除术后安返病房。",
            }
        ],
    }

    _result, _reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
        additional_source_keys=("postsurg_firstcourse_record",),
    )

    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"


@pytest.mark.asyncio
async def test_p1_2b_all_empty_targets_with_postsurg_record_downgrades_to_data_gap() -> None:
    """手术记录与日常病程均为空，但会话已有术后首次病程记录时也降级为 data_gap(source_empty)。"""
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "肿物"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "肿物",
                "diagnosis": "良性病变",
                "report_datetime": "2026-09-14 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [],
        "postsurg_firstcourse_record": [
            {
                "document_id": "pfc1",
                "record_time": "2026-09-11 16:00:00",
                "record_content": "今日行腹腔镜下肿物切除术，手术顺利。",
            }
        ],
    }

    _result, _reduced, final = await _run_06_02_02(
        rows,
        client=_scripted_pathology_client("not_documented"),
        additional_source_keys=("postsurg_firstcourse_record",),
    )

    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_empty"


# ---------------------------------------------------------------------------
# P1-6a: LX0609-01-01-02 short-complaint prompt clarity + 1 corrective retry
# ---------------------------------------------------------------------------


def _build_018_session(
    *,
    chief_complaint: str = "呼之不应 3天。",
    diagnosis_name: str = "1、肺结核涂阳2、脑梗死",
) -> Any:
    rows = {
        "admission_record": [
            {
                "document_id": "adm-1",
                "chief_complaint": chief_complaint,
                "history_of_present_illness": "3天前无明显诱因出现呼之不应，伴发热。",
                "record_content": f"主诉：{chief_complaint}",
            }
        ],
        "admission_record_diagnosis": [
            {
                "document_id": "ard-1",
                "diagnosis_type": "初步诊断",
                "diagnosis_name": diagnosis_name,
            }
        ],
    }

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-02",),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-09-20T10:00:00+08:00",
        row_reader=reader,
    )


def test_p1_6a_prompt_emphasizes_verbatim_short_complaint_extraction() -> None:
    prompt = rule_018._lx018_prompt(context="[主诉原文] 呼之不应 3天。\n[第一诊断] 肺结核涂阳")
    assert "呼之不应" in prompt
    assert "意识不清" in prompt
    assert "昏迷" in prompt
    assert "不得改写或替换为同义术语" in prompt


@pytest.mark.asyncio
async def test_p1_6a_short_complaint_paraphrase_recovers_on_corrective_retry() -> None:
    """复现 #03：极短主诉“呼之不应 3天。”首次被模型改写为“意识障碍”，纠偏重试1次后恢复有效临床判定。"""
    session = _build_018_session()
    client = _SequencedClient(
        [
            # 第1次：将“呼之不应”改写为同义词“意识障碍”，触发原子事实校验失败
            {
                "chief_signal_kind": "localized_symptom_or_sign",
                "chief_complaint_signals": ["意识障碍"],
                "anatomic_relation": "conflicts",
                "laterality_relation": "not_applicable",
                "symptom_relation": "conflicts",
                "disease_course_relation": "not_applicable",
                "disease_direction_relation": "conflicts",
                "medical_analysis": "主诉表现为意识障碍，无法导出第一诊断肺结核涂阳。",
            },
            # 第2次：纠偏后逐字摘取“呼之不应”
            {
                "chief_signal_kind": "localized_symptom_or_sign",
                "chief_complaint_signals": ["呼之不应"],
                "anatomic_relation": "conflicts",
                "laterality_relation": "not_applicable",
                "symptom_relation": "conflicts",
                "disease_course_relation": "not_applicable",
                "disease_direction_relation": "conflicts",
                "medical_analysis": "主诉“呼之不应”指向中枢神经系统急症，不能导出第一诊断肺结核涂阳。",
            },
        ]
    )

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        decision_rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "custom_prompt": "stub"}],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-01-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    assert execution.llm_call_count == 2
    assert execution.total_tokens == 90
    assert len(client.prompts) == 2
    assert "上一次输出未通过校验" in client.prompts[1]
    assert "未逐字命中[主诉原文]" in client.prompts[1]
    assert '["呼之不应"]' in client.prompts[1]


@pytest.mark.asyncio
async def test_p1_6a_unknown_supports_enum_conflict_recovers_on_corrective_retry() -> None:
    session = _build_018_session(
        chief_complaint="意识不清2小时。",
        diagnosis_name="1、急性脑梗死",
    )
    client = _SequencedClient(
        [
            # 第1次：unknown 与 supports 枚举冲突
            {
                "chief_signal_kind": "unknown",
                "chief_complaint_signals": [],
                "anatomic_relation": "not_applicable",
                "laterality_relation": "not_applicable",
                "symptom_relation": "supports",
                "disease_course_relation": "not_applicable",
                "disease_direction_relation": "not_applicable",
                "medical_analysis": "主诉较短。",
            },
            # 第2次：修正为有效原子事实
            {
                "chief_signal_kind": "localized_symptom_or_sign",
                "chief_complaint_signals": ["意识不清"],
                "anatomic_relation": "not_applicable",
                "laterality_relation": "not_applicable",
                "symptom_relation": "supports",
                "disease_course_relation": "supports",
                "disease_direction_relation": "supports",
                "medical_analysis": "急性意识不清指向颅内急症，支持急性脑梗死方向。",
            },
        ]
    )

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        decision_rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "custom_prompt": "stub"}],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-01-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert execution.llm_call_count == 2
    assert "unknown时同时在关系字段给出了supports或conflicts" in client.prompts[1]


@pytest.mark.asyncio
async def test_p1_6a_persistent_invalid_output_fails_closed_after_one_retry() -> None:
    session = _build_018_session()
    bad = {
        "chief_signal_kind": "localized_symptom_or_sign",
        "chief_complaint_signals": ["意识障碍"],
        "anatomic_relation": "conflicts",
        "laterality_relation": "not_applicable",
        "symptom_relation": "conflicts",
        "disease_course_relation": "not_applicable",
        "disease_direction_relation": "conflicts",
    }
    client = _SequencedClient([bad, bad])

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        decision_rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "custom_prompt": "stub"}],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-01-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == "model_invalid_output"
    assert execution.llm_call_count == 2
    assert execution.total_tokens == 90


@pytest.mark.asyncio
async def test_p1_6a_retry_transport_error_preserves_failure_reason() -> None:
    session = _build_018_session()
    client = _SequencedClient(
        [
            {"chief_signal_kind": "invalid_enum", "chief_complaint_signals": ["呼之不应"]},
            TimeoutError("synthetic retry timeout"),
        ]
    )

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        decision_rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "custom_prompt": "stub"}],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-01-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == "model_transport_error"
    assert execution.llm_call_count == 2


@pytest.mark.asyncio
async def test_p1_6a_legacy_path_also_recovers_on_corrective_retry() -> None:
    client = _SequencedClient(
        [
            {
                "chief_signal_kind": "localized_symptom_or_sign",
                "chief_complaint_signals": ["意识障碍"],
                "anatomic_relation": "not_applicable",
                "laterality_relation": "not_applicable",
                "symptom_relation": "supports",
                "disease_course_relation": "not_applicable",
                "disease_direction_relation": "supports",
            },
            {
                "chief_signal_kind": "localized_symptom_or_sign",
                "chief_complaint_signals": ["呼之不应"],
                "anatomic_relation": "not_applicable",
                "laterality_relation": "not_applicable",
                "symptom_relation": "supports",
                "disease_course_relation": "not_applicable",
                "disease_direction_relation": "supports",
            },
        ]
    )
    payload = {
        "programmatic_timeline": {
            "documents": {
                "admission_record": [
                    {
                        "document_id": "adm-1",
                        "chief_complaint": "呼之不应 3天。",
                        "record_content": "主诉：呼之不应 3天。",
                    }
                ],
                "admission_record_diagnosis": [
                    {
                        "document_id": "ard-1",
                        "diagnosis_type": "初步诊断",
                        "diagnosis_name": "1、急性脑梗死",
                    }
                ],
            }
        }
    }

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "custom_prompt": "stub"}],
        evidence_payload=payload,
        llm_client=client,
    )

    assert execution.llm_call_count == 2
    assert execution.results[0]["status"] == "compliant"
