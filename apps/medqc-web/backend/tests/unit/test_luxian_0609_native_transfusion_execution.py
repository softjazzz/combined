from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
import inspect

import pytest

from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER, FrozenTransfusionProtocolClient
from intraoperative_transfusion_test_support import (
    ABSENT, UNKNOWN, FrozenIntraoperativeClient, item, present,
)

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


# 人工审阅的历史病例协议标签；仅用于冻结模型oracle，不由产品函数推断。
_COURSE_LABELS = {
    "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，结束时间16:10。输血过程中严密观察，未见不良反应。输血后复查血红蛋白提升，治疗有效。": "record",
    "普通病程仅提到拟输血和备血。": "not_record",
    "输血过程及输血后评价记录。": "not_record",
    '16:00输血结束。未记录输血后评价。': 'record',
    '2026-01-01 16:10 输血结束。': 'record',
    '2026-01-01 16:10 输血结束后评价未见异常，生命体征平稳，无输血不良反应。': 'record',
    '2026-06-05 10:00:00输血结束；输血后复查血红蛋白较前改善。': 'record',
    '2026-06-05 10:00输血结束。未记录输血后评价。2026-06-05 16:00输血结束。输血后复查血红蛋白改善。': 'record',
    '2026-06-05 10:00输血结束。输血后复查血红蛋白改善。': 'record',
    '2026-06-05 10:00输血结束。输血后复查血红蛋白改善。2026-06-05 16:00输血结束。未记录输血后评价。': 'record',
    '2026-06-05 10:00输血结束，过程顺利。2026-06-05 16:00输血结束。输血后复查血红蛋白改善。': 'record',
    '2026-06-05 16:00:00输血结束。': 'record',
    '2026-06-05 16:00:00输血结束；未记录输血结束后评价。': 'record',
    '2026-06-05 16:00:00输血结束；输血后复查凝血功能改善。': 'record',
    '2026-06-05 16:00:00输血结束；输血后复查血红蛋白较前改善。': 'record',
    '2026-06-05 16:00:00输血结束；输血后复查血红蛋白较前改善，未见输血不良反应。': 'record',
    '2026-06-05 16:00输血结束。未记录输血后评价。': 'record',
    '2026-06-05 16:10:00+08:00输血结束': 'record',
    '2026-06-05 16:10:00+08输血结束': 'record',
    '2026-06-05 16:10记录：输血结束。生命体征平稳。': 'record',
    '2026-06-05 16:10输血结束。': 'record',
    '2026-06-05 16:10输血结束后': 'record',
    '2026-06-05 16:10输血结束，输注过程顺利。': 'record',
    '2026年6月5日14:20开始输注红细胞2U，2026年6月5日16:10输血结束。输血过程中严密观察，生命体征平稳，未见发热及输血不良反应。': 'record',
    '2026年6月5日15:30观察生命体征平稳，2026年6月5日16:10输注完毕。': 'record',
    '2026年6月5日16:10输注完毕。输血后复查血红蛋白较前改善，未见输血不良反应。': 'record',
    '2026年6月5日16:10输注完毕后': 'record',
    '因血红蛋白65g/L申请输注悬浮红细胞2U。': 'not_record',
    '实际输血记录，输注红细胞2U。': 'record',
    '患者Hb 65g/L，因贫血予悬浮红细胞2U输注，08时开始，10时输毕，输注过程中生命体征平稳，未见不良反应。': 'record',
    '患者冯丽平，输血目的：纠正贫血；2026年07月07日17:53开始输入0231126007830A型Rh(D)阳性2u，于2026年07月07日18:27输注完毕。输血过程顺利，患者无寒战、皮疹、发热、恶心等不适症状，无输血不良反应。': 'record',
    '患者已完成输血治疗，过程资料记录较为简略。': 'record',
    '患者已输血，过程记录不完整。': 'record',
    '患者血红蛋白降低，拟输红细胞；既往无不良反应，生命体征平稳。': 'not_record',
    '患者贫血，血红蛋白降低，具有输血指征及必要性；既往无输血不良反应，已评估输血风险和生命体征。': 'not_record',
    '既往无输血不良反应，已说明风险。': 'not_record',
    '明确未记录输血前评估。': 'not_record',
    '未记录输血病程主要内容。': 'not_record',
    '术中出血约800ml，输注红细胞2U。': 'record',
    '术后记录术中输注红细胞2U。': 'record',
    '术后记录术中输注血浆200ml。': 'record',
    '病程记录：患者贫血，拟输注红细胞。': 'not_record',
    '病程记录：输血结束后继续观察。': 'record',
    '输入A型Rh(D)阳性2U': 'record',
    '输注去白悬浮红细胞2U，开始时间18:00，结束时间19:00。过程顺利，未见皮疹及输血反应。': 'record',
    '输注去白悬浮红细胞2U，过程平稳。': 'record',
    '输注完毕后复查血红蛋白上升，症状改善。': 'record',
    '输注红细胞2U，过程平稳。': 'record',
    '输血前评估及申请资料。': 'not_record',
    '输血前评估完整且风险已说明。': 'not_record',
    '输血前评估记录：患者存在输血指征，其他风险资料待结合判断。': 'not_record',
    '输血前评估：患者具有输血指征。': 'not_record',
    '输血前评估：患者具有输血指征，输血目的为纠正贫血，血红蛋白降低，既往无输血不良反应，生命体征平稳；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。': 'record',
    '输血后复查血红蛋白上升，症状改善。': 'record',
    '输血后复查血红蛋白较前改善，未见输血不良反应。': 'record',
    '输血后继续观察，患者生命体征平稳。': 'record',
    '输血后继续观察，生命体征平稳。': 'record',
    '输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，结束时间19:00。输注过程中严密观察，过程顺利，未见皮疹、胸闷及输血反应。': 'record',
    '输血目的：纠正贫血；17:53开始输入AB型红悬2U，18:27输注完毕。输血过程顺利，生命体征平稳，未见发热及输血不良反应。': 'record',
    '输血目的：纠正贫血；2026年07月07日17:53开始输入红悬2U，2026年07月07日18:27输注完毕。输血过程中严密观察，患者生命体征平稳，未见寒战、皮疹及输血不良反应。': 'record',
    '输血目的：纠正贫血；开始时间14:20，结束时间16:10。输血过程中严密观察，未见寒战及输血不良反应。': 'record',
    '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。': 'record',
    '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见输血不良反应。': 'record',
    '输血目的：纠正贫血；开始时间14:20，输注红细胞2U，结束时间16:10。输血过程中严密观察，未见不良反应。': 'record',
    '输血目的：纠正贫血；开始时间17:53输入A型Rh(D)阳性2U，18:27输注完毕。输血过程顺利，未见输血不良反应。': 'record',
    '输血目的：纠正贫血；开始时间18:00，结束时间19:00。输血过程中严密观察，生命体征平稳，未见输血不良反应。': 'record',
    '输血目的：纠正贫血；患者血红蛋白降低。': 'not_record',
    '输血目的：纠正贫血；患者血红蛋白降低，既往无输血不良反应，输注前生命体征平稳。': 'not_record',
    '输血目的：纠正贫血；输注红细胞，过程平稳。': 'record',
    '输血目的：纠正贫血；输血前评估：患者血红蛋白下降，存在输血指征，已说明输血风险。2026年6月5日14:20开始输注红细胞2U，2026年6月5日16:10输血结束。输血过程中严密观察，生命体征平稳，未见发热及输血不良反应。输血后复查血红蛋白改善。': 'record',
    '输血结束，继续观察，未见输血不良反应。': 'record',
    '输血记录正文，记录实际输注过程及观察情况。': 'record',
    '输血记录：已记录输血指征，输注过程平稳。': 'record',
    '输血记录：患者拟输注红细胞，输血过程中生命体征平稳，记录血红蛋白检查结果，但未形成输血前评估。': 'not_record',
    '输血记录：按医嘱完成输注。': 'record',
    '输血记录：按评估及医嘱完成输注。': 'record',
    '输血记录：过程顺利，无输血不良反应。': 'record',
    '输血过程中患者生命体征平稳。': 'record',
    '预计2026-06-05 16:10输血结束。生命体征平稳。': 'not_record',
    '空模板': 'not_record',
    '输血结束，继续观察。': 'record',
    '输血后继续观察。': 'record',
    # 047 时间/评价用例：均为测试作者写成的实际输注记录。
    **{f'{end_text}，复查血红蛋白较前改善，未见输血不良反应。': 'record' for end_text in (
        '2026-06-05 16:10:00+08输血结束', '2026-06-05 16:10:00+08:00输血结束',
        '2026-06-05 16:10输血结束后', '2026年6月5日16:10输注完毕后')},
    **{f'2026-06-05 16:10输血结束。{text}': 'record' for text in (
        '未见输血后评价异常。', '无输血后评价异常。', '输血后评价未见异常。',
        '未记录输血后评价。', '缺少输血后评价。', '未书写输血后评价。')},
    '输血目的：纠正贫血；开始时间17:53输入A型Rh(D)阳性2U，18:27输注完毕。输血过程顺利，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，结束时间19:00。输注过程中严密观察，过程顺利，未见皮疹、胸闷及输血反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；开始时间18:00，结束时间19:00。输血过程中严密观察，生命体征平稳，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '患者Hb 65g/L，因贫血予悬浮红细胞2U输注，08时开始，10时输毕，输注过程中生命体征平稳，未见不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；开始时间14:20，结束时间16:10。输血过程中严密观察，未见寒战及输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输注去白悬浮红细胞2U，开始时间18:00，结束时间19:00。过程顺利，未见皮疹及输血反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；2026年07月07日17:53开始输入红悬2U，2026年07月07日18:27输注完毕。输血过程中严密观察，患者生命体征平稳，未见寒战、皮疹及输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '患者冯丽平，输血目的：纠正贫血；2026年07月07日17:53开始输入0231126007830A型Rh(D)阳性2u，于2026年07月07日18:27输注完毕。输血过程顺利，患者无寒战、皮疹、发热、恶心等不适症状，无输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
    '输血目的：纠正贫血；17:53开始输入AB型红悬2U，18:27输注完毕。输血过程顺利，生命体征平稳，未见发热及输血不良反应。输血后复查血红蛋白提升，治疗有效。': 'record',
}
# 048 术中文书的人工原子事实标注：只有本次术中实际输注才是 present。
_INTRAOPERATIVE_LABELS = {
    "术中出血约800ml，输注红细胞2U。": present(item("输注红细胞2U", "红细胞", "2U")),
    "术后患者生命体征平稳，切口敷料干燥。": ABSENT,
    "中心静脉置管术，过程顺利。": ABSENT,
    "术中输注红细胞2U。": present(item("术中输注红细胞2U", "红细胞", "2U")),
    "术后记录术中输注红细胞2U。": present(item("术中输注红细胞2U", "红细胞", "2U")),
    "术后记录术中输注血浆200ml。": present(item("术中输注血浆200ml", "血浆", "200ml")),
    "手术记录中的术中输血信息。": UNKNOWN,
    "麻醉记录中的术中输血信息。": UNKNOWN,
    "术后首次病程中的输血信息。": UNKNOWN,
    "手术记录。": ABSENT,
    "首次病程记录。": ABSENT,
}
_protocol_call_counts: dict[int, int] = {}


def _protocol_calls(result) -> int:
    return _protocol_call_counts.get(id(result), 0)


async def _execute_order_contract(**kwargs):
    # 其他输血族规则仍使用原legacy资料合同，医嘱协议只给044/045/046新增来源状态。
    order_rules = {"LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"}
    if not order_rules.intersection(kwargs["rule_ids"]) and kwargs.get("evidence_payload"):
        payload = kwargs["evidence_payload"]
        documents = dict(payload["programmatic_timeline"]["documents"])
        documents.pop("__logical_source_states__", None)
        kwargs["evidence_payload"] = {"programmatic_timeline": {"documents": documents}}
    client = FrozenTransfusionProtocolClient(
        kwargs.get("llm_client"), course_labels=_COURSE_LABELS,
        intraoperative=FrozenIntraoperativeClient(_INTRAOPERATIVE_LABELS),
    )
    kwargs["llm_client"] = client
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(**kwargs)
    _protocol_call_counts[id(result)] = client.protocol_calls
    return result


def _documents(**overrides: list[dict]) -> dict:
    documents = {
        "bloodtrans_record": [{"content": "输血记录正文，记录实际输注过程及观察情况。"}],
        "consent_form": [{"content": "输血治疗知情同意书，已完成风险告知及签名。"}],
        "labtest_master": [{"content": "输血前常规检查资料。"}],
        "labtest_item_report": [],
        "blood_application": [{"content": "输血前评估及申请资料。"}],
        "daily_course_record": [{"content": "输血过程及输血后评价记录。"}],
        "surgery_record": [{"content": "手术记录中的术中输血信息。"}],
        "anesthesia_record": [{"content": "麻醉记录中的术中输血信息。"}],
        "postsurg_firstcourse_record": [{"content": "术后首次病程中的输血信息。"}],
        "inpat_nondrug_order": [{**OPEN_TRANSFUSION_ORDER, "content": "输血医嘱中的成分和数量。"}],
        "inpat_drug_order": [],
        "inpat_bill_item": [{"content": "输血收费中的成分和数量。"}],
    }
    documents.update(overrides)
    for index, row in enumerate(documents["bloodtrans_record"]):
        row.setdefault("document_id", f"fixture-course-{index}")
    documents["__logical_source_states__"] = {key: "available" if documents[key] else "empty" for key in ("bloodtrans_record", "surgery_record", "anesthesia_record")}
    return {"programmatic_timeline": {"documents": documents}}


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


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _reader(*, source_key: str, **_: object) -> list[dict]:
    if source_key == "inpat_nondrug_order":
        return [dict(OPEN_TRANSFUSION_ORDER)]
    if source_key == "inpat_drug_order":
        return []
    if source_key == "mr_bloodtrans":
        return []
    if source_key == "bloodtrans_record":
        return [{"record_content": "输血记录正文，记录实际输注过程及观察情况。"}]
    raise AssertionError(source_key)


def _typed_decision_session(
    *,
    selected_rule_ids: tuple[str, ...],
    performed: bool = True,
    bloodtrans_content: str | None = None,
    daily_content: str | None = None,
    source_rows: dict[str, list[dict]] | None = None,
):
    bloodtrans_material = (
        "输血前评估：患者具有输血指征，输血目的为纠正贫血，血红蛋白降低，"
        "既往无输血不良反应，生命体征平稳；"
        "开始时间14:20，输注去白悬浮红细胞2U，"
        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
        "未见寒战、发热及其他输血不良反应。"
        if bloodtrans_content is None
        else bloodtrans_content
    )
    daily_material = (
        "输血后继续观察，患者生命体征平稳。"
        if daily_content is None
        else daily_content
    )

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)] if performed else [],
            "inpat_drug_order": [],
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ] if performed else [],
            "bloodtrans_record": [
                {
                    "document_id": "typed-transfusion-document",
                    "record_content": bloodtrans_material,
                    "record_time": "2026-01-01 16:20:00",
                }
            ] if performed else [],
            "daily_course_record": [
                {
                    "document_id": "typed-daily-document",
                    "record_content": daily_material,
                    "record_time": "2026-01-01 17:00:00",
                }
            ] if performed else [],
        }
        rows_by_source.update(source_rows or {})
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )


def _typed_044_llm_session():
    return _typed_decision_session(
        selected_rule_ids=("LX0609-07-01-02",),
        bloodtrans_content="输血记录正文，记录实际输注过程及观察情况。",
        source_rows={
            "blood_application": [
                {
                    "application_id": "typed-application-044",
                    "request_datetime": "2026-01-01 09:00:00",
                    "reason_for_blood": "",
                    "hemoglobin": "",
                    "record_content": "因血红蛋白65g/L申请输注悬浮红细胞2U。",
                }
            ]
        },
    )


def _typed_046_llm_session():
    return _typed_decision_session(
        selected_rule_ids=("LX0609-07-02-02",),
        bloodtrans_content=(
            '输血目的：纠正贫血；开始时间17:53输入A型Rh(D)阳性2U，18:27输注完毕。输血过程顺利，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。'
        ),
    )


def test_typed_transfusion_core_does_not_reverse_engineer_customer_result_dto():
    execution_source = inspect.getsource(
        transfusion.execute_luxian_0609_native_transfusion_rules
    )
    decision_source = inspect.getsource(transfusion._typed_decision_from_outcome)

    assert "_typed_decision_from_result" not in execution_source
    assert "result.get" not in decision_source
    assert "metadata" not in decision_source
    assert "emit_outcome" in execution_source
    assert "_typed_documents_from_evidence_session" in execution_source
    assert "typed_material_by_rule[rule_id]" in execution_source
    assert "documents = legacy_documents" in execution_source


@pytest.mark.parametrize(
    ("status", "raw_reason", "canonical_reason", "expected_final_state"),
    (
        ("technical_error", "source_query_error", "source_query_error", "technical_error"),
        ("technical_error", "snapshot_mismatch", "snapshot_mismatch", "technical_error"),
        ("technical_error", "model_transport_error", "model_transport_error", "technical_error"),
        ("technical_error", "model_invalid_output", "model_invalid_output", "technical_error"),
        ("technical_error", "unexpected_internal_failure", "executor_exception", "technical_error"),
        ("evaluation_unknown", "semantic_output_unknown", "semantic_output_unknown", "evaluation_unknown"),
        ("data_gap", "transfusion_source_unavailable", "source_unavailable", "data_gap"),
    ),
)
def test_typed_transfusion_preserves_only_approved_canonical_reasons(
    status,
    raw_reason,
    canonical_reason,
    expected_final_state,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-07-02-01",))

    decision = transfusion._typed_decision_from_outcome(
        outcome=transfusion._TransfusionRuleOutcome(
            rule_id="LX0609-07-02-01",
            status=status,
            reason_code=raw_reason,
            executor_type="program",
        ),
        snapshot=session.snapshot,
    )

    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-07-02-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]

    assert decision.reason_code == canonical_reason
    assert canonical.final_state.value == expected_final_state
    assert canonical.reason_code == canonical_reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_final_state", "expected_reason", "expected_calls", "expected_tokens"),
    (
        (RuntimeError("transport failed"), "technical_error", "model_transport_error", 1, 0),
        ("not-json", "technical_error", "model_invalid_output", 1, 110),
        (
            {
                "reason_state": "present",
                "evidence_quote": "因血红蛋白65g/L申请输注",
                "application_ref": "wrong-application-ref",
            },
            "technical_error",
            "model_invalid_output",
            1,
            110,
        ),
        (
            {
                "reason_state": "uncertain",
                "evidence_quote": "",
                "application_ref": "typed-application-044",
            },
            "evaluation_unknown",
            "semantic_output_unknown",
            1,
            110,
        ),
        (None, "technical_error", "model_transport_error", 0, 0),
    ),
)
async def test_typed_044_llm_failure_semantics_bind_and_reduce(
    monkeypatch,
    model_output,
    expected_final_state,
    expected_reason,
    expected_calls,
    expected_tokens,
):
    session = _typed_044_llm_session()
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = None if model_output is None else _Client([model_output])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-01-02",),
    )
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-07-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert result.customer_display_facts == ()
    assert result.llm_call_count == (1 if model_output is None else expected_calls) + _protocol_calls(result)
    assert result.total_tokens == expected_tokens
    assert canonical[0].final_state.value == expected_final_state
    assert canonical[0].reason_code == expected_reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_final_state", "expected_reason", "expected_tokens"),
    (
        (RuntimeError("transport failed"), "technical_error", "model_transport_error", 0),
        ("not-json", "technical_error", "model_invalid_output", 110),
        (
            {
                "assertion": "explicit",
                "component_text": "红悬",
                "quote": "输入A型Rh(D)阳性2U",
                "document_ref": "wrong-document-ref",
            },
            "technical_error",
            "model_invalid_output",
            110,
        ),
        (
            {
                "assertion": "unclear",
                "component_text": "",
                "quote": "输入A型Rh(D)阳性2U",
                "document_ref": "typed-transfusion-document",
            },
            "evaluation_unknown",
            "semantic_output_unknown",
            110,
        ),
        (None, "technical_error", "model_transport_error", 0),
    ),
)
async def test_typed_046_llm_failure_semantics_bind_and_reduce(
    monkeypatch,
    model_output,
    expected_final_state,
    expected_reason,
    expected_tokens,
):
    session = _typed_046_llm_session()
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = None if model_output is None else _Client([model_output])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-02-02",),
    )
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-07-02-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert result.customer_display_facts == ()
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == expected_tokens
    assert canonical[0].final_state.value == expected_final_state
    assert canonical[0].reason_code == expected_reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_reason", "expected_tokens"),
    (
        (RuntimeError("transport failed"), "model_transport_error", 0),
        ("not-json", "model_invalid_output", 110),
    ),
)
async def test_typed_045_generic_bool_model_failures_bind_and_reduce(
    monkeypatch,
    model_output,
    expected_reason,
    expected_tokens,
):
    # 新合同：本例已明确记载完成输血，generic bool模型不再决定045记录存在。
    session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-02-01",),
        bloodtrans_content="患者已完成输血治疗，过程资料记录较为简略。",
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = _Client([model_output])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-02-01",),
    )
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-07-02-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert dict(result.customer_display_facts)["LX0609-07-02-01"]["record_count"] == 1
    assert result.llm_call_count == 2
    assert result.total_tokens == 0
    assert client.prompts == []
    assert canonical[0].final_state.value == "compliant"
    assert canonical[0].reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_typed_045_uses_snapshot_material_not_conflicting_legacy_payload(
    monkeypatch,
):
    complete_session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-02-01",),
    )
    incomplete_session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-02-01",),
        bloodtrans_content="输血过程中患者生命体征平稳。",
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must use the supplied evidence session")
        ),
    )
    common = {
        "rule_ids": ("LX0609-07-02-01",),
        "wrapper_rules": [_wrapper("LX0609-07-02-01")],
        # 旧 payload 故意始终给出强合规材料；typed 结果必须随 snapshot material 改变。
        "evidence_payload": _documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ]
        ),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": None,
        "decision_rule_ids": ("LX0609-07-02-01",),
    }

    complete = await _execute_order_contract(
        **common,
        evidence_snapshot=complete_session.snapshot,
        evidence_materials=complete_session.materials,
    )
    incomplete = await _execute_order_contract(
        **common,
        evidence_snapshot=incomplete_session.snapshot,
        evidence_materials=incomplete_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        complete.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        incomplete.decisions[0]
    ).final_state.value == "compliant"
    assert incomplete.decisions[0].reason_code == "requirement_satisfied"
    # 045存在性合同接受简短实际过程，完整字段由046单独判定。
    assert complete_session.snapshot.snapshot_hash != incomplete_session.snapshot.snapshot_hash
    assert complete.decisions[0].snapshot_hash == complete_session.snapshot.snapshot_hash
    assert incomplete.decisions[0].snapshot_hash == incomplete_session.snapshot.snapshot_hash
    assert complete.decisions[0].fact_refs != incomplete.decisions[0].fact_refs
    complete_source_refs = {
        item.snapshot_ref.removeprefix("sha256:")
        for item in complete_session.snapshot.observations
    }
    incomplete_source_refs = {
        item.snapshot_ref.removeprefix("sha256:")
        for item in incomplete_session.snapshot.observations
    }
    # typed 045 既保留来源观察引用供审计，也新增同一 snapshot 的精确文书引用。
    assert complete_source_refs.issubset(set(complete.decisions[0].fact_refs))
    assert incomplete_source_refs.issubset(set(incomplete.decisions[0].fact_refs))
    assert set(complete.decisions[0].fact_refs).issubset(
        complete_source_refs.union(complete_session.snapshot.document_refs)
    )
    assert set(incomplete.decisions[0].fact_refs).issubset(
        incomplete_source_refs.union(incomplete_session.snapshot.document_refs)
    )


@pytest.mark.asyncio
async def test_typed_044_uses_same_session_material_and_ignores_stale_payload(
    monkeypatch,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-07-01-02",))
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must use the supplied evidence session")
        ),
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        # 与同一 session 材料冲突：旧 payload 明确声称缺少输血前评估。
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "明确未记录输血前评估。"}],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-01-02",),
    )

    assert result.results == ()
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert [item.rule_id for item in result.decisions] == ["LX0609-07-01-02"]
    assert (
        reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value
        == "compliant"
    )
    assert result.decisions[0].snapshot_hash == session.snapshot.snapshot_hash
    assert "明确未记录输血前评估" not in repr(result)


@pytest.mark.asyncio
async def test_typed_044_material_change_changes_state_snapshot_and_refs(monkeypatch):
    complete_session = _typed_decision_session(selected_rule_ids=("LX0609-07-01-02",))
    missing_session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-01-02",),
        bloodtrans_content="输血过程中患者生命体征平稳。",
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-07-01-02",),
        "wrapper_rules": [_wrapper("LX0609-07-01-02")],
        "evidence_payload": _documents(
            bloodtrans_record=[{"content": "输血前评估完整且风险已说明。"}]
        ),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": None,
        "decision_rule_ids": ("LX0609-07-01-02",),
    }

    complete = await _execute_order_contract(
        **common,
        evidence_snapshot=complete_session.snapshot,
        evidence_materials=complete_session.materials,
    )
    missing = await _execute_order_contract(
        **common,
        evidence_snapshot=missing_session.snapshot,
        evidence_materials=missing_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        complete.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        missing.decisions[0]
    ).final_state.value == "non_compliant"
    assert complete.decisions[0].snapshot_hash != missing.decisions[0].snapshot_hash
    assert complete.decisions[0].fact_refs != missing.decisions[0].fact_refs


@pytest.mark.parametrize(
    ("source_mode", "expected_state", "expected_reason"),
    (
        ("available", "non_compliant", "requirement_violated"),
        ("empty", "not_applicable", "trigger_absent_complete"),
        ("unavailable", "data_gap", "source_unavailable"),
        ("error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_044_dedicated_fact_precedes_auxiliary_source_four_states(
    monkeypatch,
    source_mode,
    expected_state,
    expected_reason,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "daily_course_record" and source_mode == "unavailable":
            raise SourceEvidenceUnavailable("private unavailable detail")
        if source_key == "daily_course_record" and source_mode == "error":
            raise SourceEvidenceQueryError("private query detail")
        if source_mode == "empty" and source_key in {
            "mr_bloodtrans",
            "bloodtrans_record",
        }:
            rows = []
        else:
            rows = {
                "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)] if source_mode != "empty" else [],
                "inpat_drug_order": [],
                "mr_bloodtrans": [
                    {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
                ],
                "bloodtrans_record": [
                    {
                        "record_content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。"
                        )
                    }
                ],
                "daily_course_record": [
                    {"record_content": "输血后继续观察，生命体征平稳。"}
                ],
            }.get(source_key, [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-07-01-02",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no fallback")),
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-01-02",),
    )
    decision = result.decisions[0]

    assert reduce_luxian_0609_rule_decision(decision).final_state.value == expected_state
    assert decision.reason_code == expected_reason
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert "private unavailable detail" not in repr(result)
    assert "private query detail" not in repr(result)


@pytest.mark.asyncio
async def test_typed_044_optional_llm_keeps_raw_call_token_and_state_semantics(
    monkeypatch,
):
    grey_content = "输血前评估记录：患者存在输血指征，其他风险资料待结合判断。"
    session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-01-02",),
        bloodtrans_content=grey_content,
        daily_content="输血后继续观察。",
    )
    payload = _documents(
        bloodtrans_record=[{"content": grey_content}],
        blood_application=[],
        daily_course_record=[{"content": "输血后继续观察。"}],
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    raw_client = _Client([{"is_compliant": False}])
    typed_client = _Client([{"is_compliant": False}])
    common = {
        "rule_ids": ("LX0609-07-01-02",),
        "wrapper_rules": [_wrapper("LX0609-07-01-02")],
        "evidence_payload": payload,
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
    }

    raw = await _execute_order_contract(
        **common,
        llm_client=raw_client,
    )
    typed = await _execute_order_contract(
        **common,
        llm_client=typed_client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-01-02",),
    )

    assert raw.results[0]["status"] == "non_compliant"
    assert reduce_luxian_0609_rule_decision(
        typed.decisions[0]
    ).final_state.value == "non_compliant"
    assert typed.results == ()
    assert raw.llm_call_count == typed.llm_call_count == 1 + _protocol_calls(raw)
    assert raw.total_tokens == typed.total_tokens == 110
    assert raw_client.prompts == typed_client.prompts


@pytest.mark.asyncio
async def test_remaining_transfusion_typed_scope_is_ordered_and_fails_closed(
    monkeypatch,
):
    selected = (
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-01-02",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
    )

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = {
            "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
            "inpat_drug_order": [],
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "record_content": (
                        "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，未见不良反应。"
                    )
                }
            ],
            "daily_course_record": [
                {"record_content": "输血后继续观察，生命体征平稳。"}
            ],
        }.get(source_key, [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no legacy read")),
    )

    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([{"is_compliant": True}] * len(selected)),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert result.planned_rule_ids == selected
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    states = {
        item.rule_id: reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    }
    assert states == {
        "LX0609-11-03-01": "non_compliant",
        "LX0609-11-03-02": "not_applicable",
        "LX0609-07-01-01": "data_gap",
        "LX0609-07-01-02": "non_compliant",
        "LX0609-07-04-01": "not_applicable",
        "LX0609-07-04-02": "data_gap",
    }
    decision_by_rule = {item.rule_id: item for item in result.decisions}
    assert decision_by_rule["LX0609-11-03-02"].reason_code == "eligibility_not_met"
    bound = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert all(item.final_state.value != "technical_error" for item in bound)
    assert "输血目的" not in repr(result)


@pytest.mark.asyncio
async def test_remaining_typed_rules_do_not_promote_proxy_sources_or_call_model():
    selected = (
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
    )
    private_marker = "PRIVATE_TRANSFUSION_PROXY_MARKER"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
            "inpat_drug_order": [],
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "record_content": (
                        "输注去白悬浮红细胞2U，过程平稳。"
                        f"{private_marker}"
                    )
                }
            ],
            # 该条是手术同意书代理来源，不得当作输血同意书。
            "consent_form": [
                {"record_content": "手术治疗知情同意书，患者已签字。"}
            ],
            "exam_item_report": [
                {"record_content": "检验结果摘要，无版本化输血九项清单。"}
            ],
            "daily_course_record": [
                {"record_content": "病程中记录了输血后观察。"}
            ],
            "postsurg_firstcourse_record": [{"record_content": "首次病程记录。"}],
            "mr_surgery": [{"record_content": "手术结构化摘要。"}],
            "first_course_record": [
                {"record_content": "术后首次病程记录。"}
            ],
            "presurg_discussion": [{"record_content": "术前讨论。"}],
            "presurg_summary": [{"record_content": "术前小结。"}],
            "senior_course_record": [{"record_content": "上级医师查房。"}],
            "surgery_record": [{"record_content": "手术记录。"}],
            "medical_order": [{"record_content": "通用医嘱投影。"}],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": True}] * len(selected))

    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["non_compliant", "not_applicable", "data_gap", "not_applicable", "data_gap"]
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []
    assert private_marker not in repr(result)


@pytest.mark.asyncio
async def test_remaining_typed_rules_are_not_applicable_only_after_complete_no_transfusion():
    selected = (
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
    )

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )

    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["not_applicable"] * len(selected)
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_remaining_typed_rules_surface_shared_trigger_query_error_without_echo():
    selected = (
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
    )
    private_error = "PRIVATE SQL Bearer_secret 13800138000"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_bloodtrans":
            raise SourceEvidenceQueryError(private_error)
        rows = (
            [{"record_content": "实际输血记录，输注红细胞2U。"}]
            if source_key == "bloodtrans_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["technical_error"] * len(selected)
    assert all(item.reason_code == "source_query_error" for item in result.decisions)
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0
    assert private_error not in repr(result)


@pytest.mark.parametrize(
    ("failure_mode", "expected_state", "expected_reason"),
    (
        ("truncated", "data_gap", "source_unavailable"),
        ("query_error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_transfusion_material_failures_do_not_fallback_to_payload(
    monkeypatch,
    failure_mode,
    expected_state,
    expected_reason,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "bloodtrans_record" and failure_mode == "query_error":
            raise SourceEvidenceQueryError("private query failure")
        rows_by_source = {
            "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
            "inpat_drug_order": [],
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {"record_content": "输血过程中患者生命体征平稳。"}
            ],
            "daily_course_record": [
                {"record_content": "输血后继续观察，患者生命体征平稳。"}
            ],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=(
                failure_mode == "truncated" and source_key == "bloodtrans_record"
            ),
            limit_rows=1,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-07-02-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no fallback read")),
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-02-01",),
    )
    reduced = reduce_luxian_0609_rule_decision(result.decisions[0])

    assert reduced.final_state.value == expected_state
    assert result.decisions[0].reason_code == expected_reason
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert "private query failure" not in repr(result)


@pytest.mark.asyncio
async def test_transfusion_trigger_consumes_shared_material_without_live_reader(
    monkeypatch,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {
                    "document_id": "private-transfusion-id",
                    "record_content": "输血记录正文，记录实际输注过程及观察情况。",
                    "record_time": "2026-01-01 10:00:00",
                }
            ]
            if source_key == "bloodtrans_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-11-03-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("mr_bloodtrans", "bloodtrans_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-11-03-01",),
        wrapper_rules=[_wrapper("LX0609-11-03-01")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "consent_source_unavailable"
    )


@pytest.mark.asyncio
async def test_transfusion_truncated_shared_trigger_source_is_data_gap(monkeypatch):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        truncated = source_key == "mr_bloodtrans"
        rows = ([{"transfution_datetime": None}] if truncated else [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=truncated,
            limit_rows=1 if truncated else 50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-11-03-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("mr_bloodtrans", "bloodtrans_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-11-03-01",),
        wrapper_rules=[_wrapper("LX0609-11-03-01")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
    )

    assert result.results[0]["status"] == "data_gap"
    # 截断与来源未接入区分开，客户看到的是“资料不完整”。
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "transfusion_source_truncated"
    )
    assert result.llm_call_count == 0 + _protocol_calls(result)


@pytest.mark.asyncio
async def test_no_dedicated_transfusion_source_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await _execute_order_contract(
        rule_ids=transfusion.TRANSFUSION_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            inpat_nondrug_order=[],
            inpat_drug_order=[],
            bloodtrans_record=[],
            daily_course_record=[{"document_id": "synthetic-plan-only", "content": "普通病程仅提到拟输血和备血。"}],
            # 048 只看本次手术文书；无手术文书即无术中输血事实。
            surgery_record=[],
            anesthesia_record=[],
            postsurg_firstcourse_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 9
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_keeps_customer_order_and_only_semantic_rules_call_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [
            {"is_compliant": True},
            {"is_compliant": False},
            {"is_compliant": True},
            {"is_compliant": True},
            {"is_compliant": False},
            {"is_compliant": True},
        ]
    )

    result = await _execute_order_contract(
        rule_ids=tuple(reversed(transfusion.TRANSFUSION_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    ),
                    "record_time": "2026-06-05 16:20:00",
                }
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(transfusion.TRANSFUSION_RULE_IDS)
    assert [item["status"] for item in result.results] == [
        "data_gap",
        "data_gap",
        "data_gap",
        "compliant",
        "compliant",
        "non_compliant",
        "compliant",
        # 默认夹具的手术/麻醉/术后正文只是“含术中输血信息”的占位，无法判断是否实施。
        "data_gap",
        "data_gap",
    ]
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == 110
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_typed_transfusion_event_triggers_but_shell_record_fails_closed(monkeypatch):
    def _typed_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "mr_bloodtrans":
            return [{"transfution_datetime": datetime(2026, 6, 5, 14, 20)}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _typed_reader)
    client = _Client([{"is_compliant": True}])
    typed = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(bloodtrans_record=[{"content": "空模板"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )
    assert typed.results[0]["status"] == "non_compliant"
    assert client.prompts == []
    assert typed.llm_call_count == 2

    def _shell_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "bloodtrans_record":
            return [{"record_content": "空模板"}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _shell_reader)
    shell = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(bloodtrans_record=[], daily_course_record=[{"document_id": "synthetic-course-shell", "content": "输血过程及输血后评价记录。"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert shell.results[0]["status"] == "non_compliant"
    assert shell.llm_call_count == 0 + _protocol_calls(shell)


@pytest.mark.asyncio
async def test_045_substantive_dedicated_course_record_is_compliant_without_model(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_present"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_045_projects_the_checked_transfusion_document_ids_for_evidence(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "document_id": "bloodtrans-045-1",
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    ),
                },
                {
                    "document_id": "bloodtrans-045-2",
                    "content": "输血记录：过程顺利，无输血不良反应。",
                },
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=None,
    )

    facts = dict(result.customer_display_facts)["LX0609-07-02-01"]
    assert facts["source_document_ids"] == [
        "bloodtrans-045-1",
        "bloodtrans-045-2",
    ]


@pytest.mark.asyncio
async def test_045_typed_shadow_returns_bound_decision_instead_of_raw_result(
    monkeypatch,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-07-02-01",))
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must reuse the evidence session")
        ),
    )
    client = _Client([])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-01",),
        wrapper_rules=[_wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ]
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-07-02-01",),
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == ["LX0609-07-02-01"]
    assert result.decisions[0].snapshot_hash == session.snapshot.snapshot_hash
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert result.decisions[0].fact_refs
    assert set(result.decisions[0].fact_refs).intersection(
        session.snapshot.document_refs
    )
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.parametrize(
    ("rule_id", "payload", "outputs", "performed", "expected_status"),
    (
        (
            "LX0609-07-02-01",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。"
                        )
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-07-02-01",
            _documents(
                bloodtrans_record=[
                    {"content": "患者已完成输血治疗，过程资料记录较为简略。"}
                ]
            ),
            [{"is_compliant": False}],
            True,
            "compliant",
        ),
        (
            "LX0609-07-02-01",
            _documents(daily_course_record=[]),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-07-02-02",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。输血后复查血红蛋白提升，治疗有效。"
                        )
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-07-02-02",
            _documents(
                bloodtrans_record=[
                    {"content": "输血目的：纠正贫血；输注红细胞，过程平稳。"}
                ]
            ),
            [{"is_compliant": False}],
            True,
            "non_compliant",
        ),
        (
            "LX0609-07-02-02",
            _documents(daily_course_record=[]),
            [],
            True,
            "non_compliant",
        ),
        (
            "LX0609-07-03-01",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "2026-01-01 16:10 输血结束后评价未见异常，"
                            "生命体征平稳，无输血不良反应。"
                        ),
                        "record_time": "2026-01-01 16:20:00",
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-07-03-01",
            _documents(
                bloodtrans_record=[
                    {"content": "2026-01-01 16:10 输血结束。"}
                ],
                daily_course_record=[{"content": "患者继续观察治疗。"}],
            ),
            [],
            True,
            "data_gap",
        ),
        (
            "LX0609-07-03-01",
            _documents(
                bloodtrans_record=[{"content": "输血结束，继续观察。"}],
            ),
            [],
            True,
            "data_gap",
        ),
        (
            "LX0609-07-03-01",
            _documents(bloodtrans_record=[], daily_course_record=[]),
            [],
            False,
            "not_applicable",
        ),
    ),
)
@pytest.mark.asyncio
async def test_typed_045_047_preserves_raw_state_order_and_model_usage(
    monkeypatch,
    rule_id,
    payload,
    outputs,
    performed,
    expected_status,
):
    payload_documents = payload["programmatic_timeline"]["documents"]

    def first_content(source_key: str) -> str:
        rows = payload_documents.get(source_key) or ()
        return str(rows[0].get("content") or "") if rows else ""

    session = _typed_decision_session(
        selected_rule_ids=(rule_id,),
        performed=performed,
        bloodtrans_content=first_content("bloodtrans_record"),
        daily_content=first_content("daily_course_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("same evidence session must serve both paths")
        ),
    )
    raw_client = _Client(list(outputs))
    typed_client = _Client(list(outputs))
    common = {
        "rule_ids": (rule_id,),
        "wrapper_rules": [_wrapper(rule_id)],
        "evidence_payload": payload,
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "evidence_materials": session.materials,
    }

    raw = await _execute_order_contract(
        **common,
        llm_client=raw_client,
    )
    typed = await _execute_order_contract(
        **common,
        llm_client=typed_client,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(rule_id,),
    )
    reduced = reduce_luxian_0609_rule_decision(typed.decisions[0])

    assert [item["status"] for item in raw.results] == [expected_status]
    assert typed.results == ()
    assert [item.rule_id for item in typed.decisions] == [rule_id]
    assert reduced.final_state.value == expected_status
    assert typed.planned_rule_ids == raw.planned_rule_ids == (rule_id,)
    assert typed.llm_call_count == raw.llm_call_count
    assert typed.prompt_tokens == raw.prompt_tokens
    assert typed.completion_tokens == raw.completion_tokens
    assert typed.total_tokens == raw.total_tokens
    assert typed.api_time == raw.api_time
    assert typed_client.prompts == raw_client.prompts
    assert "private" not in repr(typed.decisions).lower()
    assert "输血目的" not in repr(typed.decisions)


@pytest.mark.asyncio
async def test_typed_transfusion_session_and_refs_fail_closed(monkeypatch):
    session = _typed_decision_session(selected_rule_ids=("LX0609-07-02-01",))
    other_session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-07-02-01",),
        institute_id="OTHER-I",
        patient_id="OTHER-P",
        visit_id="OTHER-V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=lambda **kwargs: SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        ),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-07-02-01",),
        "wrapper_rules": [_wrapper("LX0609-07-02-01")],
        "evidence_payload": _documents(),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": _Client([]),
        "decision_rule_ids": ("LX0609-07-02-01",),
    }

    with pytest.raises(ValueError, match="one evidence session"):
        await _execute_order_contract(
            **common,
            evidence_snapshot=session.snapshot,
            evidence_materials=other_session.materials,
        )

    typed = await _execute_order_contract(
        **common,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    forged = replace(typed.decisions[0], fact_refs=("f" * 64,))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(forged,),
        expected_rule_ids=("LX0609-07-02-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "technical_error"
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_046_each_complete_dedicated_record_is_compliant_without_model(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    complete_rows = [
        {
            "content": (
                '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。输血后复查血红蛋白提升，治疗有效。'
            )
        },
        {
            "content": (
                '输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，结束时间19:00。输注过程中严密观察，过程顺利，未见皮疹、胸闷及输血反应。输血后复查血红蛋白提升，治疗有效。'
            )
        },
    ]
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=complete_rows,
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_complete"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_046_checks_every_transfusion_record_beyond_prompt_projection_limit(
    monkeypatch,
):
    """确定性完整性核对必须覆盖全部记录，不能静默忽略第九份。"""

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    complete_content = (
        '输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，结束时间16:10。输血过程中严密观察，生命体征平稳，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。'
    )
    rows = [
        {"document_id": f"blood-046-complete-{index}", "content": complete_content}
        for index in range(1, 9)
    ]
    rows.append(
        {
            "document_id": "blood-046-incomplete-9",
            "content": (
                '输血目的：纠正贫血；开始时间18:00，结束时间19:00。输血过程中严密观察，生命体征平稳，未见输血不良反应。输血后复查血红蛋白提升，治疗有效。'
            ),
        }
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(bloodtrans_record=rows),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_incomplete"
    )
    facts = dict(result.customer_display_facts)["LX0609-07-02-02"]
    assert facts["record_count"] == 9
    assert facts["incomplete_record_count"] == 1
    assert facts["missing_fields"] == ["component", "dose"]
    assert facts["missing_field_record_counts"] == {"component": 1, "dose": 1}
    assert facts["source_document_ids"] == ["blood-046-incomplete-9"]
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_046_recognizes_complete_customer_narrative_wording(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        '患者Hb 65g/L，因贫血予悬浮红细胞2U输注，08时开始，10时输毕，输注过程中生命体征平稳，未见不良反应。输血后复查血红蛋白提升，治疗有效。'
                    )
                }
            ],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_complete"
    )
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert client.prompts == []


@pytest.mark.asyncio
async def test_046_incomplete_or_cross_record_fields_are_deterministic_defect(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        '输血目的：纠正贫血；开始时间14:20，结束时间16:10。输血过程中严密观察，未见寒战及输血不良反应。输血后复查血红蛋白提升，治疗有效。'
                    )
                },
                {
                    "content": (
                        '输注去白悬浮红细胞2U，开始时间18:00，结束时间19:00。过程顺利，未见皮疹及输血反应。输血后复查血红蛋白提升，治疗有效。'
                    )
                },
            ],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_incomplete"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    facts = dict(result.customer_display_facts)["LX0609-07-02-02"]
    assert facts["missing_fields"] == [
        "component",
        "dose",
        "reason_or_indication",
    ]
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_046_llm_confirms_explicit_component_from_same_record_and_preserves_typed_decision(
    monkeypatch,
):
    """词典未覆盖的“红悬”只能由同一输血记录的受控 LLM 事实补齐。"""

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    record = (
        '输血目的：纠正贫血；2026年07月07日17:53开始输入红悬2U，2026年07月07日18:27输注完毕。输血过程中严密观察，患者生命体征平稳，未见寒战、皮疹及输血不良反应。输血后复查血红蛋白提升，治疗有效。'
    )
    session = _typed_decision_session(
        selected_rule_ids=("LX0609-07-02-02",),
        bloodtrans_content=record,
    )
    client = _Client([
        {
            "assertion": "explicit",
            "component_text": "红悬",
            "quote": "开始输入红悬2U",
            "document_ref": "typed-transfusion-document",
        }
    ])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"document_id": "typed-transfusion-document", "content": record}],
            daily_course_record=[{"content": "不得进入046成分识别提示词。"}],
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-02-02",),
    )

    assert result.results == ()
    assert reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value == "compliant"
    canonical = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-07-02-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert canonical[0].final_state.value == "compliant"
    assert canonical[0].reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-07-02-02"]
    assert facts["missing_fields"] == []
    assert facts["source_document_ids"] == ["typed-transfusion-document"]
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    assert record in client.prompts[0]
    assert "不得进入046成分识别提示词" not in client.prompts[0]
    assert "SHOULD_NOT_LEAK" not in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_status", "expected_reason"),
    (
        (
            RuntimeError("model transport unavailable"),
            "technical_error",
            "model_transport_error",
        ),
        (
            {
                "assertion": "explicit",
                "component_text": "A型Rh(D)阳性",
                "quote": "A型Rh(D)阳性2u",
                "document_ref": "blood-046-type-only",
            },
            "technical_error",
            "model_invalid_output",
        ),
        (
            {
                "assertion": "unclear",
                "component_text": "",
                "quote": "A型Rh(D)阳性2u",
                "document_ref": "blood-046-type-only",
            },
            "uncertain",
            "semantic_output_unknown",
        ),
        (
            {
                "assertion": "not_explicit",
                "component_text": "",
                "quote": "A型Rh(D)阳性2u",
                "document_ref": "blood-046-type-only",
            },
            "non_compliant",
            "transfusion_course_record_incomplete",
        ),
        (
            {
                "assertion": "explicit",
                "component_text": "红悬",
                "quote": "并不存在的原文",
                "document_ref": "blood-046-type-only",
            },
            "technical_error",
            "model_invalid_output",
        ),
    ),
)
async def test_046_llm_rejects_inferred_component_or_invalid_quote(
    monkeypatch,
    model_output,
    expected_status,
    expected_reason,
):
    """血型、Rh、产品编号和剂量均不能被模型升级为输血成分。"""

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    record = (
        '患者冯丽平，输血目的：纠正贫血；2026年07月07日17:53开始输入0231126007830A型Rh(D)阳性2u，于2026年07月07日18:27输注完毕。输血过程顺利，患者无寒战、皮疹、发热、恶心等不适症状，无输血不良反应。输血后复查血红蛋白提升，治疗有效。'
    )
    client = _Client([model_output])
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"document_id": "blood-046-type-only", "content": record}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == expected_status
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == (0 if isinstance(model_output, Exception) else 110)
    if expected_status == "non_compliant":
        assert dict(result.customer_display_facts)["LX0609-07-02-02"]["missing_fields"] == ["component"]


@pytest.mark.asyncio
async def test_046_llm_accepts_component_that_includes_blood_type_but_not_type_only(
    monkeypatch,
):
    """“AB型红悬”仍含制品名；不能因前缀血型而被错误拒绝。"""

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    record = (
        '输血目的：纠正贫血；17:53开始输入AB型红悬2U，18:27输注完毕。输血过程顺利，生命体征平稳，未见发热及输血不良反应。输血后复查血红蛋白提升，治疗有效。'
    )
    client = _Client([
        {
            "assertion": "explicit",
            "component_text": "AB型红悬",
            "quote": "输入AB型红悬2U",
            "document_ref": "blood-046-ab-red-suspension",
        }
    ])
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-02-02",),
        wrapper_rules=[_wrapper("LX0609-07-02-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"document_id": "blood-046-ab-red-suspension", "content": record}
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == 110


@pytest.mark.asyncio
async def test_missing_consent_projection_is_data_gap_and_other_rules_are_not_blocked(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-02-01"),
        wrapper_rules=[_wrapper("LX0609-11-03-01"), _wrapper("LX0609-11-03-02"), _wrapper("LX0609-07-02-01")],
        evidence_payload=_documents(consent_form=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_dedicated_record_precedes_missing_daily_projection_for_044_047(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    complete_record = {
        "content": (
            "输血目的：纠正贫血；输血前评估：患者血红蛋白下降，存在输血指征，"
            "已说明输血风险。2026年6月5日14:20开始输注红细胞2U，"
            "2026年6月5日16:10输血结束。输血过程中严密观察，生命体征平稳，"
            "未见发热及输血不良反应。输血后复查血红蛋白改善。"
        ),
        "record_time": "2026-06-05 16:20:00",
    }

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01"),
        wrapper_rules=[
            _wrapper("LX0609-07-01-02"),
            _wrapper("LX0609-07-02-01"),
            _wrapper("LX0609-07-02-02"),
            _wrapper("LX0609-07-03-01"),
        ],
        evidence_payload=_documents(
            bloodtrans_record=[complete_record],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"] * 4
    display_facts = dict(result.customer_display_facts)
    assert display_facts["LX0609-07-01-02"]["checked_fields"] == [
        "indication",
        "laboratory_indicator",
        "risk_history_or_status",
    ]
    assert display_facts["LX0609-07-01-02"]["missing_fields"] == []
    assert display_facts["LX0609-07-02-02"]["checked_fields"] == [
        "clinical_effect",
        "component",
        "dose",
        "process_observation",
        "reaction_and_handling",
        "reason_or_indication",
        "start_and_end_time",
    ]
    assert display_facts["LX0609-07-02-02"]["missing_fields"] == []
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_proves_044_046_defects_before_daily_projection(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])
    record_without_purpose = {
        "document_id": "blood-record-1",
        "content": (
            "2026年6月5日14:20开始输注红细胞2U，"
            "2026年6月5日16:10输血结束。"
            "输血过程中严密观察，生命体征平稳，未见发热及输血不良反应。"
        )
    }

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02", "LX0609-07-02-02", "LX0609-07-03-01"),
        wrapper_rules=[
            _wrapper("LX0609-07-01-02"),
            _wrapper("LX0609-07-02-02"),
            _wrapper("LX0609-07-03-01"),
        ],
        evidence_payload=_documents(
            bloodtrans_record=[record_without_purpose],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results[:2]] == [
        "non_compliant",
        "non_compliant",
    ]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.results[1]["metadata"]["reason_code"] == (
        "transfusion_purpose_or_indication_missing"
    )
    assert result.results[2]["status"] == "data_gap"
    assert result.results[2]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_time_unavailable"
    )
    assert dict(result.customer_display_facts) == {
        "LX0609-07-01-02": {
            "transfusion_order_present": True,
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": "pretransfusion_assessment",
            "checked_sources": [
                "bloodtrans_record",
                "blood_application",
                "course_record",
            ],
            "source_document_refs": [
                {
                    "source_type": "bloodtrans_record",
                    "source_document_id": "blood-record-1",
                }
            ],
        },
        "LX0609-07-02-02": {
            "failure_kind": "transfusion_course_record_incomplete",
            "transfusion_order_present": True,
            "record_count": 1,
            "incomplete_record_count": 1,
            "checked_fields": [
                "clinical_effect",
                "component",
                "dose",
                "process_observation",
                "reaction_and_handling",
                "reason_or_indication",
                "start_and_end_time",
            ],
            "missing_fields": ["clinical_effect", "reason_or_indication"],
            "missing_field_record_counts": {"clinical_effect": 1, "reason_or_indication": 1},
            "source_document_ids": ["blood-record-1"],
        },
    }
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


def test_041_missing_consent_keeps_transfusion_trigger_reference() -> None:
    status, reason, facts = transfusion._programmatic_041_status(
        {
            "bloodtrans_record": [
                {
                    "document_id": "blood-record-1",
                    "record_content": "输注红细胞2U，过程平稳。",
                }
            ],
            "consent_form": [],
            "__logical_source_states__": {
                "bloodtrans_record": "available",
                "consent_form": "empty",
            },
        }
    )

    assert (status, reason) == ("non_compliant", "transfusion_consent_missing")
    assert facts is not None
    assert facts["source_document_refs"] == [
        {
            "source_type": "bloodtrans_record",
            "source_document_id": "blood-record-1",
        }
    ]


def test_045_explicit_missing_course_and_complete_empty_source_are_non_compliant():
    explicit = transfusion._programmatic_045_status(
        {
            "bloodtrans_record": [
                {"record_content": "未记录输血病程主要内容。"}
            ],
            "__logical_source_states__": {"bloodtrans_record": "available"},
        }
    )
    empty = transfusion._programmatic_045_status(
        {
            "bloodtrans_record": [],
            "__logical_source_states__": {"bloodtrans_record": "empty"},
        }
    )

    assert explicit == ("non_compliant", "transfusion_course_record_missing")
    assert empty == ("non_compliant", "transfusion_course_record_missing")


def test_046_explicit_incomplete_course_is_non_compliant_without_model():
    assert transfusion._programmatic_046_status(
        {
            # 此内部字段检查的前置条件是course协议已确认实际记录。
            "__course_presence_verified__": True,
            "bloodtrans_record": [
                {"record_content": "患者已输血，过程记录不完整。"}
            ]
        }
    ) == ("non_compliant", "transfusion_course_record_incomplete")


def test_047_explicit_missing_evaluation_uses_authoritative_end_time():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": (
                        "2026-06-05 16:00:00输血结束；"
                        "未记录输血结束后评价。"
                    )
                }
            ],
            "daily_course_record": [],
        }
    ) == ("data_gap", "posttransfusion_evaluation_time_unavailable")


@pytest.mark.parametrize(
    "record_time",
    (
        None,
        "2026-06-05 15:59:59",
    ),
)
def test_047_textual_evaluation_without_usable_completion_time_is_data_gap(
    record_time,
):
    """正文评价不能代替输血结束后的权威完成时间。"""

    row = {
        "record_content": (
            "2026-06-05 16:00:00输血结束；"
            "输血后复查血红蛋白较前改善，未见输血不良反应。"
        )
    }
    if record_time is not None:
        row["record_time"] = record_time

    assert transfusion._programmatic_047_status(
        {"bloodtrans_record": [row], "daily_course_record": []}
    ) == ("data_gap", "posttransfusion_evaluation_time_unavailable")


def test_047_daily_course_authored_at_with_record_time_basis_is_compliant():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": "2026-06-05 16:00:00输血结束。",
                }
            ],
            "daily_course_record": [
                {
                    "record_content": "输血后复查血红蛋白较前改善，未见输血不良反应。",
                    "authored_at": "2026-06-05 16:20:00",
                    "time_basis": "record_time",
                }
            ],
        }
    ) == ("compliant", "posttransfusion_evaluation_complete")


@pytest.mark.parametrize(
    "time_basis",
    ("submit_time_fallback", "update_time_fallback", "content_text"),
)
def test_047_daily_course_non_authoritative_authored_at_stays_data_gap(time_basis):
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": "2026-06-05 16:00:00输血结束。",
                }
            ],
            "daily_course_record": [
                {
                    "record_content": "输血后复查血红蛋白较前改善，未见输血不良反应。",
                    "authored_at": "2026-06-05 16:20:00",
                    "time_basis": time_basis,
                }
            ],
        }
    ) == ("data_gap", "posttransfusion_evaluation_time_unavailable")


def test_047_late_authoritative_evaluation_is_non_compliant():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": (
                        "2026-06-05 16:00:00输血结束；"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    ),
                    "record_time": "2026-06-06 16:00:01",
                }
            ],
            "daily_course_record": [],
        }
    ) == ("non_compliant", "posttransfusion_evaluation_late")


def test_047_multiple_transfusions_do_not_use_earlier_evaluation_for_later_end():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": (
                        "2026-06-05 10:00:00输血结束；"
                        "输血后复查血红蛋白较前改善。"
                    ),
                    "record_time": "2026-06-05 10:20:00",
                },
                {
                    "record_content": (
                        "2026-06-05 16:00:00输血结束；"
                        "输血后复查凝血功能改善。"
                    ),
                    "record_time": "2026-06-05 15:59:59",
                },
            ],
            "daily_course_record": [],
        }
    ) == ("data_gap", "posttransfusion_evaluation_time_unavailable")


def test_047_multiple_transfusions_with_same_end_time_require_each_evaluation():
    assert transfusion._programmatic_047_status(
        {
            "bloodtrans_record": [
                {
                    "record_content": (
                        "2026-06-05 16:00:00输血结束；"
                        "输血后复查血红蛋白较前改善。"
                    ),
                    "record_time": "2026-06-05 16:20:00",
                },
                {
                    "record_content": (
                        "2026-06-05 16:00:00输血结束；"
                        "输血后复查凝血功能改善。"
                    ),
                    "record_time": "2026-06-05 16:30:00",
                },
            ],
            "daily_course_record": [],
        }
    ) == ("compliant", "posttransfusion_evaluation_complete")


@pytest.mark.asyncio
async def test_047_missing_authoritative_end_stays_data_gap_without_daily_projection(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血结束，继续观察，未见输血不良反应。"}],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )
    assert result.llm_call_count == 0 + _protocol_calls(result)


@pytest.mark.asyncio
async def test_043_incomplete_test_contract_is_data_gap_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    for lab_documents in (
        {
            "labtest_master": [
                {"content": "仅有检验主单和检验科室，缺少项目、结果和报告时间。"}
            ],
            "labtest_item_report": [],
        },
        {
            "labtest_master": [{"content": "输血前检验主单。"}],
            "labtest_item_report": [
                {
                    "content": (
                        "叙述声称输血前九项齐全，但没有版本化项目清单、"
                        "结构化结果和可比报告时间。"
                    )
                }
            ],
        },
    ):
        result = await _execute_order_contract(
            rule_ids=("LX0609-07-01-01",),
            wrapper_rules=[_wrapper("LX0609-07-01-01")],
            evidence_payload=_documents(**lab_documents),
            institute_id="safe-institute",
            patient_id="safe-patient",
            visit_id="safe-visit",
            source_schema=None,
            llm_client=client,
        )

        assert result.results[0]["status"] == "data_gap"
        assert (
            result.results[0]["metadata"]["reason_code"]
            == "pretransfusion_item_contract_unavailable"
        )
        assert result.results[0]["metadata"]["executor_type"] == "program"
        assert result.llm_call_count == 0 + _protocol_calls(result)
        assert result.total_tokens == 0

    assert client.prompts == []


@pytest.mark.asyncio
async def test_047_posttransfusion_evaluation_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    same_record = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    ),
                    "record_time": datetime(2026, 6, 5, 16, 20),
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：继续观察一般情况。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert same_record.results[0]["status"] == "compliant"
    assert same_record.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_complete"
    )
    assert same_record.results[0]["metadata"]["executor_type"] == "program"
    assert same_record.llm_call_count == 0 + _protocol_calls(same_record)
    same_record_facts = dict(same_record.customer_display_facts)["LX0609-07-03-01"]
    assert same_record_facts["transfusion_end_time"] == "2026-06-05 16:10:00"
    assert same_record_facts["evaluation_time"] == "2026-06-05 16:20:00"
    assert same_record_facts["elapsed_hours"] == 0.17

    later_course = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "2026-06-05 16:10输血结束，输注过程顺利。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert later_course.results[0]["status"] == "compliant"
    assert later_course.llm_call_count == 0 + _protocol_calls(later_course)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "end_text",
    [
        "2026-06-05 16:10:00+08输血结束",
        "2026-06-05 16:10:00+08:00输血结束",
        "2026-06-05 16:10输血结束后",
        "2026年6月5日16:10输注完毕后",
    ],
)
async def test_047_accepts_controlled_timezone_and_postposition_forms(
    monkeypatch, end_text
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        f"{end_text}，复查血红蛋白较前改善，"
                        "未见输血不良反应。"
                    ),
                    "record_time": datetime(2026, 6, 5, 16, 20),
                }
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "compliant"
    assert result.llm_call_count == 0 + _protocol_calls(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_status"),
    [
        (
            (
                "2026-06-05 10:00输血结束。未记录输血后评价。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "data_gap",
        ),
        (
            (
                "2026-06-05 10:00输血结束。输血后复查血红蛋白改善。"
                "2026-06-05 16:00输血结束。未记录输血后评价。"
            ),
            "data_gap",
        ),
        (
            (
                "2026-06-05 10:00输血结束，过程顺利。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "compliant",
        ),
    ],
)
async def test_047_allows_final_summary_but_preserves_explicit_missing_statement(
    monkeypatch, content, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": content, "record_time": datetime(2026, 6, 5, 16, 20)}
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0 + _protocol_calls(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_text", "expected_status"),
    [
        ("未见输血后评价异常。", "compliant"),
        ("无输血后评价异常。", "compliant"),
        ("输血后评价未见异常。", "compliant"),
        ("未记录输血后评价。", "data_gap"),
        ("缺少输血后评价。", "data_gap"),
        ("未书写输血后评价。", "data_gap"),
    ],
)
async def test_047_distinguishes_normal_evaluation_from_missing_documentation(
    monkeypatch, evaluation_text, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": f"2026-06-05 16:10输血结束。{evaluation_text}",
                    "record_time": datetime(2026, 6, 5, 16, 20),
                }
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0 + _protocol_calls(result)


@pytest.mark.asyncio
async def test_047_rejects_pre_end_or_unrelated_observation_and_requires_end_time(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    no_post_evaluation = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日15:30观察生命体征平稳，"
                        "2026年6月5日16:10输注完毕。"
                    )
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：生命体征平稳，继续观察。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert no_post_evaluation.results[0]["status"] == "data_gap"
    assert no_post_evaluation.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_time_unavailable"
    )
    assert no_post_evaluation.llm_call_count == 0 + _protocol_calls(no_post_evaluation)

    missing_end_time = await _execute_order_contract(
        rule_ids=("LX0609-07-03-01",),
        wrapper_rules=[_wrapper("LX0609-07-03-01")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "输注完毕后复查血红蛋白上升，症状改善。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing_end_time.results[0]["status"] == "data_gap"
    assert missing_end_time.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )
    assert missing_end_time.llm_call_count == 0 + _protocol_calls(missing_end_time)


@pytest.mark.asyncio
async def test_047_rejects_planned_time_weak_context_and_unresolved_end_rows(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    async def _execute(
        *, blood_rows: list[dict], daily_rows: list[dict]
    ) -> transfusion.NativeTransfusionExecutionResult:
        return await _execute_order_contract(
            rule_ids=("LX0609-07-03-01",),
            wrapper_rules=[_wrapper("LX0609-07-03-01")],
            evidence_payload=_documents(
                bloodtrans_record=blood_rows,
                daily_course_record=daily_rows,
            ),
            institute_id="safe-institute",
            patient_id="safe-patient",
            visit_id="safe-visit",
            source_schema=None,
            llm_client=_Client([]),
        )

    planned = await _execute(
        blood_rows=[
            {"content": "预计2026-06-05 16:10输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    # 只有计划记录、没有结构化实施时间：停在实施门控，不进入结束时间判定。
    assert planned.results[0]["status"] == "data_gap"
    assert planned.results[0]["metadata"]["reason_code"] == (
        "transfusion_source_unavailable"
    )

    document_time = await _execute(
        blood_rows=[
            {"content": "2026-06-05 16:10记录：输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert document_time.results[0]["status"] == "data_gap"

    weak_context = await _execute(
        blood_rows=[{"content": "2026-06-05 16:10输血结束，输注过程顺利。"}],
        daily_rows=[
            {
                "record_time": datetime(2026, 6, 5, 18, 40),
                "content": "复查血小板正常，生命体征平稳。",
            }
        ],
    )
    assert weak_context.results[0]["status"] == "data_gap"

    unresolved_row = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {"content": "16:00输血结束。未记录输血后评价。"},
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert unresolved_row.results[0]["status"] == "data_gap"
    assert unresolved_row.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )

    one_of_two_missing = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {
                "content": (
                    "2026-06-05 16:00输血结束。"
                    "未记录输血后评价。"
                )
            },
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert one_of_two_missing.results[0]["status"] == "data_gap"
    # 每次只有一次专用记录实施核验，047 时间判定本身不调用模型。
    for result in (planned, weak_context, document_time, unresolved_row, one_of_two_missing):
        assert result.llm_call_count == _protocol_calls(result) == 1


@pytest.mark.asyncio
async def test_044_clear_pretransfusion_assessment_truth_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    missing = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血记录：患者拟输注红细胞，输血过程中生命体征平稳，"
                        "记录血红蛋白检查结果，但未形成输血前评估。"
                    )
                }
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：输血结束后继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing.results[0]["status"] == "non_compliant"
    assert missing.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_missing"
    assert missing.results[0]["metadata"]["executor_type"] == "program"
    assert missing.llm_call_count == 0 + _protocol_calls(missing)

    complete = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按评估及医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血前评估记录",
                    "content": (
                        "患者贫血，血红蛋白降低，具有输血指征及必要性；"
                        "既往无输血不良反应，已评估输血风险和生命体征。"
                    )
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert complete.results[0]["status"] == "compliant"
    assert complete.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_complete"
    assert complete.results[0]["metadata"]["executor_type"] == "program"
    assert complete.llm_call_count == 0 + _protocol_calls(complete)

    gray_client = _Client([{"is_compliant": True}])
    gray = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：已记录输血指征，输注过程平稳。"}],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：患者贫血，拟输注红细胞。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=gray_client,
    )
    assert gray.results[0]["status"] == "non_compliant"
    assert gray.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert gray.llm_call_count == 0 + _protocol_calls(gray)
    assert gray_client.prompts == []

    split_client = _Client([{"is_compliant": False}])
    split = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血前评估：患者具有输血指征。"}],
            blood_application=[{"content": "患者贫血，血红蛋白降低。"}],
            daily_course_record=[{"content": "既往无输血不良反应，已说明风险。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=split_client,
    )
    assert split.results[0]["status"] == "non_compliant"
    assert split.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert split.llm_call_count == 1 + _protocol_calls(split)

    application_client = _Client([{"is_compliant": True}])
    application_gray = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血申请单",
                    "content": (
                        "患者血红蛋白降低，拟输红细胞；既往无不良反应，生命体征平稳。"
                    ),
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=application_client,
    )
    assert application_gray.results[0]["status"] == "non_compliant"
    assert application_gray.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_incomplete"
    )
    assert application_gray.llm_call_count == 0 + _protocol_calls(application_gray)
    assert application_client.prompts == []


@pytest.mark.asyncio
async def test_044_same_record_purpose_without_assessment_marker_is_non_compliant(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；患者血红蛋白降低，"
                        "既往无输血不良反应，输注前生命体征平稳。"
                    )
                }
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_044_transfusion_purpose_without_preassessment_is_non_compliant_without_llm(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "输血目的：纠正贫血；患者血红蛋白降低。"}
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.llm_call_count == 0 + _protocol_calls(result)
    assert client.prompts == []


@pytest.mark.asyncio
async def test_044_uses_one_bounded_llm_call_for_legacy_application_reason(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    application_text = "因血红蛋白65g/L申请输注悬浮红细胞2U。"
    client = _Client(
        [{
            "reason_state": "present",
            "evidence_quote": "因血红蛋白65g/L申请输注",
            "application_ref": "BA-001",
        }]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[
                {"transfution_datetime": "2026-08-20 14:00:00"}
            ],
            blood_application=[{
                "application_id": "BA-001",
                "request_datetime": "2026-08-20 09:00:00",
                "reason_for_blood": "",
                "hemoglobin": "",
                "record_content": application_text,
            }],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_complete"
    )
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    assert application_text in client.prompts[0]
    assert "daily_course_record" not in client.prompts[0]


@pytest.mark.asyncio
async def test_044_llm_uncertain_is_evaluation_unknown_not_model_error(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    application_text = "因血红蛋白65g/L申请输注悬浮红细胞2U。"
    client = _Client(
        [{
            "reason_state": "uncertain",
            "evidence_quote": "",
            "application_ref": "BA-UNKNOWN",
        }]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}],
            blood_application=[{
                "application_id": "BA-UNKNOWN",
                "request_datetime": "2026-08-20 09:00:00",
                "reason_for_blood": "",
                "hemoglobin": "",
                "record_content": application_text,
            }],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "uncertain"
    assert result.results[0]["metadata"]["reason_code"] == "semantic_output_unknown"
    assert result.llm_call_count == 1 + _protocol_calls(result)
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    assert application_text in client.prompts[0]


@pytest.mark.asyncio
async def test_044_rejects_llm_reason_quote_outside_application_text(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [{
            "reason_state": "present",
            "evidence_quote": "原文中不存在的理由",
            "application_ref": "BA-001",
        }]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[
                {"transfution_datetime": "2026-08-20 14:00:00"}
            ],
            blood_application=[{
                "application_id": "BA-001",
                "request_datetime": "2026-08-20 09:00:00",
                "reason_for_blood": "",
                "hemoglobin": "",
                "record_content": "因血红蛋白65g/L申请输注悬浮红细胞2U。",
            }],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "technical_error"
    assert result.results[0]["metadata"]["reason_code"] == (
        "model_invalid_output"
    )
    assert result.llm_call_count == 1 + _protocol_calls(result)


@pytest.mark.asyncio
async def test_048_does_not_claim_three_document_mismatch_before_comparison_contract(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-04-01",),
        wrapper_rules=[_wrapper("LX0609-07-04-01")],
        evidence_payload=_documents(
            surgery_record=[
                {"surgery_process": "术中出血约800ml，输注红细胞2U。"}
            ],
            anesthesia_record=[{"record_content": ""}],
            postsurg_firstcourse_record=[
                {"record_content": "术后患者生命体征平稳，切口敷料干燥。"}
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_comparison_fields_unavailable"
    )
    # 麻醉记录只有空正文，视同缺失；不能据此宣称三份文书不一致。
    assert result.customer_display_facts == ((
        "LX0609-07-04-01",
        {
            "failure_kind": "transfusion_comparison_material_missing",
            "missing_sources": ["anesthesia_record"],
        },
    ),)
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_048_without_credible_intraoperative_transfusion_is_not_applicable(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-04-01",),
        wrapper_rules=[_wrapper("LX0609-07-04-01")],
        evidence_payload=_documents(
            surgery_record=[{"record_content": "中心静脉置管术，过程顺利。"}],
            anesthesia_record=[],
            postsurg_firstcourse_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.results[0]["metadata"]["reason_code"] == (
        "intraoperative_transfusion_fact_absent"
    )
    assert result.results[0]["findings"] == "未发现可信的术中输血事实，本规则不适用。"
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_041_042_use_dedicated_consent_and_return_controlled_facts() -> None:
    selected = ("LX0609-11-03-01", "LX0609-11-03-02")

    def read(**kwargs):
        rows = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 6, 5, 14, 20)}
            ],
            "bloodtrans_record": [
                {"record_content": "输注红细胞2U，过程平稳。"}
            ],
            "consent_form": [
                {
                    "document_title": "输血知情同意书",
                    "consent_type": "blood_transfusion",
                    "patient_name": "测试患者",
                    "diagnosis": "贫血",
                    "transfusion_reason": "纠正贫血",
                    "blood_component": "红细胞",
                    "risk_description": "已告知输血风险",
                    "alternative_plan": "已告知替代方案",
                    "patient_sign": "患者签名",
                    "physician_sign": "医师签名",
                    "sign_datetime": "2026-06-05 13:00:00",
                }
            ],
        }.get(kwargs["source_key"], [])
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows, truncated=False, limit_rows=50
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["compliant", "compliant"]
    facts = dict(result.customer_display_facts)
    assert facts["LX0609-11-03-01"]["consent_count"] == 1
    assert facts["LX0609-11-03-02"]["checked_fields"] == [
        "patient_information",
        "diagnosis",
        "indication",
        "component",
        "risks",
        "alternatives",
        "patient_or_agent_signature",
        "physician_signature",
        "signed_time",
    ]


def test_042_requires_signature_time_precise_to_minute() -> None:
    status, reason, facts = transfusion._programmatic_042_status(
        {
            "consent_form": [
                {
                    "document_title": "输血知情同意书",
                    "consent_type": "blood_transfusion",
                    "patient_name": "测试患者",
                    "diagnosis": "贫血",
                    "transfusion_reason": "纠正贫血",
                    "blood_component": "红细胞",
                    "risk_description": "已告知风险",
                    "alternative_plan": "已告知替代方案",
                    "patient_sign": "患者签名",
                    "physician_sign": "医师签名",
                    "patient_sign_datetime": "2026-06-05",
                }
            ],
            "__logical_source_states__": {"consent_form": "available"},
        }
    )

    assert (status, reason) == (
        "non_compliant",
        "transfusion_consent_incomplete",
    )
    assert facts is not None
    assert facts["missing_fields"] == ["signed_time"]


def test_043_short_lab_codes_require_token_boundaries() -> None:
    assert transfusion._lab_item_alias_matches("梅毒螺旋体抗体(tp)", "tp")
    assert not transfusion._lab_item_alias_matches("tpo antibody", "tp")


def test_043_public_pretransfusion_row_resolvers_preserve_item_and_admission_contract() -> None:
    assert transfusion.resolve_pretransfusion_required_item(
        {"item_name": "乙肝表面抗原"}
    ) == "hbsag"
    assert transfusion.resolve_pretransfusion_required_item(
        {"item_name": "梅毒螺旋体抗体(tp)"}
    ) == "syphilis"
    assert transfusion.resolve_pretransfusion_required_item(
        {"item_name": "葡萄糖"}
    ) is None
    assert transfusion.resolve_pretransfusion_admission_time(
        {"admission_datetime": "2026-06-01 08:00:00"}
    ) == datetime(2026, 6, 1, 8, 0)
    assert transfusion.resolve_pretransfusion_admission_time(
        {"admission_datetime": "not-a-datetime"}
    ) is None


@pytest.mark.asyncio
async def test_043_checks_regular_items_before_transfusion_and_returns_times() -> None:
    selected = ("LX0609-07-01-01",)
    names = [
        "乙肝表面抗原",
        "乙肝表面抗体",
        "乙肝e抗原",
        "乙肝e抗体",
        "乙肝核心抗体",
        "丙肝抗体",
        "HIV抗体",
        "梅毒抗体",
        "*ABO血型鉴定",
        "*Rh血型鉴定",
        "不规则抗体筛查",
    ]

    def read(**kwargs):
        rows = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 6, 5, 14, 20)}
            ],
            "bloodtrans_record": [
                {"record_content": "输注红细胞2U，过程平稳。"}
            ],
            "blood_application": [
                {"patient_bloodtype_abo": "O", "patient_bloodtype_rhd": "阳性"}
            ],
            "labtest_item_report": [
                {
                    "item_name": name,
                    "result": "阴性" if name != "谷丙转氨酶" else "12",
                    "report_datetime": "2026-06-05 10:00:00",
                }
                for name in names
            ],
        }.get(kwargs["source_key"], [])
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows, truncated=False, limit_rows=50
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper("LX0609-07-01-01")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value == "compliant"
    facts = dict(result.customer_display_facts)["LX0609-07-01-01"]
    assert len(facts["checked_items"]) == 11
    assert facts["latest_test_time"] == "2026-06-05 10:00:00"
    assert facts["transfusion_time"] == "2026-06-05 14:20:00"
    assert facts["abo_present"] is True
    assert facts["rh_present"] is True
    assert facts["antibody_screen_present"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("postop_text", "expected_status", "expected_kind"),
    [
        ("术后记录术中输注红细胞2U。", "compliant", "transfusion_records_consistent"),
        ("术后记录术中输注血浆200ml。", "non_compliant", "transfusion_records_inconsistent"),
    ],
)
async def test_048_compares_component_and_dose_across_three_documents(
    monkeypatch, postop_text: str, expected_status: str, expected_kind: str
) -> None:
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    result = await _execute_order_contract(
        rule_ids=("LX0609-07-04-01",),
        wrapper_rules=[_wrapper("LX0609-07-04-01")],
        evidence_payload=_documents(
            surgery_record=[{"record_content": "术中输注红细胞2U。"}],
            anesthesia_record=[{"record_content": "术中输注红细胞2U。"}],
            postsurg_firstcourse_record=[{"record_content": postop_text}],
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
    )

    assert result.results[0]["status"] == expected_status
    facts = dict(result.customer_display_facts)["LX0609-07-04-01"]
    assert (facts.get("verification_kind") or facts.get("failure_kind")) == expected_kind
    assert set(facts["comparison_matrix"]) == {
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    }


@pytest.mark.asyncio
async def test_conservative_transfusion_gaps_explain_missing_material_not_patient_defect(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    selected = ("LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-01-01", "LX0609-07-04-02")
    result = await _execute_order_contract(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 4
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "consent_source_unavailable",
        "consent_signature_contract_unavailable",
        "pretransfusion_item_contract_unavailable",
        "billing_linkage_source_unavailable",
    ]
    assert all(
        item["metadata"]["data_gap_kind"] == "system_data_contract_gap"
        and item["metadata"]["gap_owner"] == "system_integration"
        for item in result.results
    )
    customer_copy = " ".join(
        str(item[field])
        for item in result.results
        for field in ("findings", "suggestion")
    )
    assert "请补充患者资料" not in customer_copy
    assert "数据源" not in customer_copy
    assert "字段映射" not in customer_copy
    assert "契约" not in customer_copy
    assert result.llm_call_count == _protocol_calls(result)
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_source_error_and_invalid_model_output_fail_closed_without_echo(monkeypatch):
    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _failed_reader)
    result = await _execute_order_contract(
        rule_ids=("LX0609-11-03-01", "LX0609-07-04-02"),
        wrapper_rules=[_wrapper("LX0609-11-03-01"), _wrapper("LX0609-07-04-02")],
        evidence_payload=_documents(bloodtrans_record=[], daily_course_record=[{"document_id": "synthetic-course-shell", "content": "输血过程及输血后评价记录。"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert secret not in repr(result)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    invalid = await _execute_order_contract(
        rule_ids=("LX0609-07-04-02",),
        wrapper_rules=[_wrapper("LX0609-07-04-02")],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )
    assert invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(invalid)


def test_transfusion_consent_sources_never_alias_surgery_consent() -> None:
    for rule_id in ("LX0609-11-03-01", "LX0609-11-03-02"):
        assert "surgery_inform_consent" not in transfusion._typed_rule_source_keys(
            rule_id
        )

    rows = transfusion._transfusion_consent_rows(
        {
            "consent_form": [
                {
                    "document_title": "麻醉知情同意书",
                    "consent_type": "anesthesia",
                    "record_content": "患者已签名。",
                },
                {
                    "document_title": "输血知情同意书",
                    "consent_type": "blood_transfusion",
                    "record_content": "患者已签名。",
                },
            ]
        }
    )
    assert len(rows) == 1
    assert rows[0]["consent_type"] == "blood_transfusion"


def _empty_reason_application(application_id="BA-EMPTY"):
    # 接口未提供申请理由与正文，仅有申请时间与客观指标。
    return {
        "application_id": application_id,
        "request_datetime": "2026-08-20 09:00:00",
        "reason_for_blood": "",
        "hemoglobin": "58",
        "record_content": "",
    }


_PRE_COURSE = "患者贫血貌，血红蛋白较前下降，HGB 58g/L，有输血指征，拟输注红细胞悬液2u纠正贫血。"
_POST_COURSE = "昨日输注红细胞后复查血红蛋白较前上升。"


@pytest.mark.asyncio
async def test_044_empty_application_reason_checks_pretransfusion_course(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [{
            "reason_state": "present",
            "evidence_quote": "有输血指征，拟输注红细胞悬液2u纠正贫血",
            "application_ref": "BA-EMPTY",
        }]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}],
            blood_application=[_empty_reason_application()],
            daily_course_record=[],
            senior_course_record=[
                {"document_id": "SC-1", "record_time": "2026-08-20 09:40:00", "content": _PRE_COURSE},
                {"document_id": "SC-2", "record_time": "2026-08-21 10:00:00", "content": _POST_COURSE},
                {"document_id": "SC-0", "record_time": "2026-08-17 10:00:00", "content": "三日前病程，必要时输血。"},
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_complete"
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "输血前病程" in prompt and "必要时输血" in prompt and _PRE_COURSE in prompt
    assert _POST_COURSE not in prompt and "三日前病程" not in prompt


@pytest.mark.asyncio
async def test_044_empty_application_reason_without_pretransfusion_course_stays_incomplete(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"reason_state": "present", "evidence_quote": "x", "application_ref": "BA-EMPTY"}])

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}],
            blood_application=[_empty_reason_application()],
            daily_course_record=[],
            senior_course_record=[
                {"document_id": "SC-2", "record_time": "2026-08-21 10:00:00", "content": _POST_COURSE},
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_incomplete"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_044_course_reason_quote_must_be_in_pretransfusion_course(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [{
            "reason_state": "present",
            "evidence_quote": "昨日输注红细胞后复查血红蛋白较前上升",
            "application_ref": "BA-EMPTY",
        }]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}],
            blood_application=[_empty_reason_application()],
            daily_course_record=[],
            senior_course_record=[
                {"document_id": "SC-1", "record_time": "2026-08-20 09:40:00", "content": _PRE_COURSE},
                {"document_id": "SC-2", "record_time": "2026-08-21 10:00:00", "content": _POST_COURSE},
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "technical_error"
    assert result.results[0]["metadata"]["reason_code"] == "model_invalid_output"


@pytest.mark.asyncio
async def test_044_application_text_keeps_application_reason_prompt_even_with_course(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    application_text = "因血红蛋白65g/L申请输注悬浮红细胞2U。"
    client = _Client(
        [{"reason_state": "present", "evidence_quote": "因血红蛋白65g/L申请输注", "application_ref": "BA-001"}]
    )

    result = await _execute_order_contract(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[_wrapper("LX0609-07-01-02")],
        evidence_payload=_documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}],
            blood_application=[{**_empty_reason_application("BA-001"), "record_content": application_text}],
            daily_course_record=[],
            senior_course_record=[
                {"document_id": "SC-1", "record_time": "2026-08-20 09:40:00", "content": _PRE_COURSE},
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert "输血申请单正文" in client.prompts[0] and _PRE_COURSE not in client.prompts[0]
