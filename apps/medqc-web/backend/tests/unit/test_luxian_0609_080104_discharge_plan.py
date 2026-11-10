"""08-01-04（027）出院后计划：LLM 抽取事实、Python 校验并判定的必要边界。

固定应答只依据实际收到的出院记录作答（见 luxian_0609_discharge_plan_test_facts），未登记材料立即失败；
不代表真实模型质量。冻结目录由 tests/unit/conftest.py 指向每个用例的临时目录。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from luxian_0609_discharge_plan_test_facts import FROZEN_DISCHARGE_PLAN_FACTS, DischargePlanFactsClient
from test_luxian_0609_death_record_timeliness import saved_roundtrip

from app.services.luxian_0609 import discharge_plan_extraction as extraction
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts

RULE = "LX0609-08-01-04"


async def _run(discharge_rows, client):
    rows = {"diagnosis": [{"document_id": "diag", "diagnosis_code": "C18.9"}],
            "discharge_record": list(discharge_rows)}

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-10-07T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=(RULE,)),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(RULE,), wrapper_rules=[{"rule_id": RULE, "custom_prompt": "{medical_text}"}],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(RULE,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return result, final


def _row(treatment="", order="", document_id="discharge-1"):
    return {"document_id": document_id, "treatment_course": treatment, "discharge_order": order}


def _evidence_ids(final):
    return {(e["source_type"], e["source_document_id"]) for e in final.get("customer_evidence", [])}


def _saved_evidence_types(loaded):
    # 保存层只保留来源类型与匿名化引用，不保留原文书编号。
    return sorted(e["source_type"] for e in loaded.get("evidence", []))


# 1–4、6：住院经过、正面对照、历史与未来并存、仅历史/仅条件、完整核验确无计划。
@pytest.mark.asyncio
@pytest.mark.parametrize("treatment,order,status,reason,accepted", [
    ("住院期间先予支持治疗，3天后行化疗，现好转出院。", "注意休息。",
     "non_compliant", "requirement_violated", None),
    ("", "出院医嘱：3周后返院化疗。", "compliant", "requirement_satisfied",
     # 原字段值本身写有“出院医嘱：”，属真实原文，正常采信。
     [{"kind": "tumor_treatment", "quote": "出院医嘱：3周后返院化疗", "time_anchor": "3周后", "document_index": 1,
       "field": "discharge_order"}]),
    ("", "定期门诊随访，每3个月复查。", "compliant", "requirement_satisfied",
     [{"kind": "follow_up", "quote": "定期门诊随访，每3个月复查", "time_anchor": "每3个月", "document_index": 1,
       "field": "discharge_order"}]),
    ("", "昨日返院化疗，出院2周后返院化疗。", "compliant", "requirement_satisfied",
     [{"kind": "tumor_treatment", "quote": "昨日返院化疗，出院2周后返院化疗", "time_anchor": "出院2周后",
       "document_index": 1, "field": "discharge_order"}]),
    ("", "昨日返院化疗，今日好转出院。", "non_compliant", "requirement_violated", None),
    ("", "如有不适随诊。", "non_compliant", "requirement_violated", None),
    ("", "病情好转出院，注意休息。", "non_compliant", "requirement_violated", None),
], ids=["inpatient_history_3_days_later", "planned_treatment", "planned_follow_up", "history_then_future",
        "history_only", "conditional_only", "complete_no_plan"])
async def test_plan_boundaries_through_formal_chain(treatment, order, status, reason, accepted):
    client = DischargePlanFactsClient()
    result, final = await _run([_row(treatment, order)], client)
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == (final["status"], final["reason_code"]) == (status, reason)
    assert loaded["customer_display_facts"] == final["customer_display_facts"]
    facts = loaded["customer_display_facts"]
    assert facts["requirement_met"] is (status == "compliant")
    assert facts.get("accepted_plans") == accepted
    assert _evidence_ids(final) == {("discharge_record", "discharge-1")}
    assert _saved_evidence_types(loaded) == ["discharge_record"]
    assert result.llm_call_count == len(client.prompts) == 1
    if accepted:
        # Renderer 展示被采信的计划原文。
        assert accepted[0]["quote"] in repr(final["findings"])


# 5：合法 unknown 待核；无效引文、错误文书引用经一次补核后仍走技术失败通道；超时为技术失败。
@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["出院后的治疗安排另见专科意见。", "下次返院化疗。"],
                         ids=["document_unknown", "timing_unknown"])
async def test_legal_unknown_is_data_gap_not_missing_plan(order):
    client = DischargePlanFactsClient()
    _result, final = await _run([_row("", order)], client)
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == ("data_gap", "semantic_extraction_unresolved")
    assert not loaded.get("customer_display_facts")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,reason,calls", [
    ("invalid_quote", "model_invalid_output", 2),
    ("wrong_document", "model_invalid_output", 2),
    ("missing_document", "model_invalid_output", 2),
    ("timeout", "model_timeout", 1),
])
async def test_protocol_and_call_failures_are_technical_errors(mode, reason, calls):
    client = DischargePlanFactsClient(mode=mode)
    result, final = await _run([_row("", "出院医嘱：3周后返院化疗。")], client)
    # 技术失败按设计不可交付（Canonical 拒收、进入补跑），不能伪装为“未写计划”或资料不足。
    assert (final["status"], final["reason_code"]) == ("technical_error", reason)
    assert result.llm_call_count == len(client.prompts) == calls
    with pytest.raises(ValueError):
        saved_roundtrip(final)


# 6：输入不完整与完整核验确无计划分开处理。
@pytest.mark.asyncio
async def test_blank_discharge_record_blocks_complete_negative_but_not_found_plan():
    blank = _row("", "", document_id="discharge-blank")
    _result, negative = await _run([_row("", "病情好转出院，注意休息。"), blank], DischargePlanFactsClient())
    assert (negative["status"], negative["reason_code"]) == ("data_gap", "required_field_missing")
    _result, positive = await _run([_row("", "出院医嘱：3周后返院化疗。"), blank], DischargePlanFactsClient())
    assert positive["status"] == "compliant"
    # 证据只指向载有被采信计划的出院记录，不含空白记录。
    assert _evidence_ids(positive) == {("discharge_record", "discharge-1")}
    assert _saved_evidence_types(saved_roundtrip(positive)) == ["discharge_record"]


@pytest.mark.asyncio
async def test_all_documents_and_characters_are_sent_without_count_or_length_refusal():
    """复审二：取消 8 份/16000 字拒收。10 份、超 16000 字时全部送模，末尾文书中的计划被采信。"""

    long_text = "病情平稳。" * 4000  # 20000 字
    rows = [_row(long_text, "注意休息。", document_id="discharge-01")]
    rows += [_row("", "病情好转出院，注意休息。", document_id=f"discharge-{index:02d}") for index in range(2, 10)]
    rows.append(_row("", "3周后返院化疗。", document_id="discharge-10"))
    table = {f"{long_text}\n注意休息。": ("complete", ()), **{
        key: FROZEN_DISCHARGE_PLAN_FACTS[key] for key in ("病情好转出院，注意休息。", "3周后返院化疗。")}}
    client = DischargePlanFactsClient(table)
    result, final = await _run(rows, client)
    [prompt] = client.prompts
    sent = __import__("json").loads(prompt.rsplit("\n", 1)[1])
    assert [item["local_doc_id"] for item in sent] == [f"doc_{index:02d}" for index in range(1, 11)]
    assert sent[0]["fields"][0]["text"] == long_text, "正文不得截断"
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == ("compliant", "requirement_satisfied")
    assert loaded["customer_display_facts"]["accepted_plans"] == [
        {"kind": "tumor_treatment", "quote": "3周后返院化疗", "time_anchor": "3周后", "document_index": 10,
         "field": "discharge_order"}]
    assert _evidence_ids(final) == {("discharge_record", "discharge-10")}
    assert result.llm_call_count == 1


# 复审三：程序生成的字段标签不是原文；引文须绑定所注明字段的原值。
@pytest.mark.asyncio
async def test_generated_field_label_is_not_accepted_as_original_quote():
    labelled = DischargePlanFactsClient(mode="label_quote")
    _result, rejected = await _run([_row("", "3周后返院化疗。")], labelled)
    # 模型回引“出院医嘱：3周后返院化疗”：补核 1 次后仍违规，走技术失败通道，不进入客户证据。
    assert (rejected["status"], rejected["reason_code"]) == ("technical_error", "model_invalid_output")
    assert len(labelled.prompts) == 2
    assert "出院医嘱：3周后返院化疗" not in repr(rejected.get("customer_display_facts"))
    with pytest.raises(ValueError):
        saved_roundtrip(rejected)

    _result, accepted = await _run([_row("", "3周后返院化疗。")], DischargePlanFactsClient())
    loaded = saved_roundtrip(accepted)
    assert loaded["status"] == "compliant"
    assert loaded["customer_display_facts"]["accepted_plans"] == [
        {"kind": "tumor_treatment", "quote": "3周后返院化疗", "time_anchor": "3周后", "document_index": 1,
         "field": "discharge_order"}]


@pytest.mark.asyncio
async def test_quote_cannot_be_borrowed_from_another_field_or_document():
    # 同一文书内：引文注明到另一个字段。
    wrong_field = DischargePlanFactsClient(mode="wrong_field")
    _result, final = await _run([_row("住院期间先予支持治疗，3天后行化疗，现好转出院。", "注意休息。")], wrong_field)
    assert (final["status"], final["reason_code"], len(wrong_field.prompts)) == (
        "technical_error", "model_invalid_output", 2)

    # 两个合法文书 ID：把第二份独有的引文归给第一份。
    class BorrowingClient(DischargePlanFactsClient):
        async def generate(self, prompt, **kwargs):
            import json

            self.prompts.append(prompt)
            documents = json.loads(prompt.rsplit("\n", 1)[1])
            assert [item["local_doc_id"] for item in documents] == ["doc_01", "doc_02"]
            body = {"schema_version": extraction.SCHEMA_VERSION, "documents": [
                {"local_doc_id": "doc_01", "review_state": "complete", "arrangements": [
                    {"field": "discharge_order", "kind": "tumor_treatment", "timing": "post_discharge_planned",
                     "quote": "3周后返院化疗", "time_anchor": "3周后"}]},
                {"local_doc_id": "doc_02", "review_state": "complete", "arrangements": []}]}
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(body, ensure_ascii=False)}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    borrowing = BorrowingClient()
    _result, final = await _run([_row("", "注意休息。", document_id="D1"),
                                 _row("", "3周后返院化疗。", document_id="D2")], borrowing)
    assert (final["status"], final["reason_code"], len(borrowing.prompts)) == (
        "technical_error", "model_invalid_output", 2)


# 复审一：预算/上下文准入失败只影响本规则，同族已完成结果照常返回；取消仍向上传播。
async def _run_family(client):
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision

    selected = ("LX0609-06-02-02", RULE)
    rows = {"diagnosis": [{"document_id": "diag", "diagnosis_code": "C18.9"}],
            "discharge_record": [_row("", "3周后返院化疗。")]}

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-10-07T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=selected),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=selected, wrapper_rules=[{"rule_id": rule, "custom_prompt": "{medical_text}"} for rule in selected],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=selected,
    )
    states = {item.rule_id: (reduce_luxian_0609_rule_decision(item).final_state.value, item.reason_code)
              for item in result.decisions}
    return result, states


@pytest.mark.asyncio
async def test_budget_rejection_is_isolated_to_08_01_04_and_keeps_sibling_result():
    from app.services.llm_token_budget import BudgetError, BudgetVerdict

    class BudgetClient:
        calls = 0

        async def generate(self, prompt, **kwargs):
            assert extraction.SCHEMA_VERSION in prompt
            BudgetClient.calls += 1
            raise BudgetError(BudgetVerdict("BUDGET_EXHAUSTED", "full_request", "synthetic", "synthetic"))

    result, states = await _run_family(BudgetClient())
    assert states["LX0609-06-02-02"] == ("not_applicable", "trigger_absent_complete")
    assert states[RULE] == ("technical_error", "llm_context_budget_exhausted")
    assert [item.rule_id for item in result.decisions].count(RULE) == 1, "本条结果不得重复生成"
    assert BudgetClient.calls == 1, "预算失败不得补核重试"
    assert _freeze_files() == [], "失败不得冻结"


@pytest.mark.asyncio
async def test_cancellation_still_propagates():
    import asyncio

    class CancelledClient:
        async def generate(self, prompt, **kwargs):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await _run_family(CancelledClient())


# 7：新版本不复用旧冻结；完整结果可热复用；旧文件字节不变；未决结果不冻结。
class _IdentifiedClient(DischargePlanFactsClient):
    provider_code = "synthetic"
    model = "synthetic-discharge-plan"


def _freeze_files(namespace="malignant_discharge_plan"):
    import os

    root = Path(os.environ["LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"])
    return sorted(path for path in root.rglob("*.json") if path.parent.name == namespace)


def _read_bytes(path: Path) -> bytes:
    # 冻结存储使用 Windows 长路径前缀写入（分区目录较深），读取时复用同一路径处理。
    from app.services.luxian_0609.exam_analysis_freeze import _windows_storage_path

    return _windows_storage_path(path).read_bytes()


@pytest.mark.asyncio
async def test_freeze_reuses_only_complete_results_of_current_version(monkeypatch):
    row = _row("", "出院医嘱：3周后返院化疗。")
    current_version = extraction.FACT_FREEZE_VERSION
    monkeypatch.setattr(extraction, "FACT_FREEZE_VERSION", "malignant-discharge-plan-older-protocol")
    older = _IdentifiedClient()
    await _run([row], older)
    [older_file] = _freeze_files()
    older_bytes = _read_bytes(older_file)
    # 只恢复协议版本；conftest 设置的冻结目录保持不变。
    monkeypatch.setattr(extraction, "FACT_FREEZE_VERSION", current_version)

    first = _IdentifiedClient()
    _result, first_final = await _run([row], first)
    assert len(first.prompts) == 1, "新版本不得命中旧版本冻结"
    assert len(_freeze_files()) == 2
    second = _IdentifiedClient()
    second_result, second_final = await _run([row], second)
    assert second.prompts == [] and second_result.llm_call_count == 0, "完整结果应热复用"
    assert second_final["customer_display_facts"] == first_final["customer_display_facts"]
    assert _read_bytes(older_file) == older_bytes

    unknown = _IdentifiedClient()
    await _run([_row("", "下次返院化疗。")], unknown)
    assert len(_freeze_files()) == 2, "含 unknown 的结果不得冻结"


# 8 附：旧结果事实读取兼容；新事实字段严格校验。
def test_fact_contract_keeps_legacy_results_and_validates_accepted_plans():
    legacy = {"verification_kind": "malignant_discharge_plan_check", "malignant_diagnosis_present": True,
              "plan_items": {"future_plan": True, "tumor_treatment": True, "follow_up": False}, "requirement_met": True}
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=legacy) == legacy
    plan = {"kind": "tumor_treatment", "quote": "出院医嘱：3周后返院化疗", "time_anchor": "3周后", "document_index": 1}
    current = {**legacy, "accepted_plans": [plan]}
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=current) == current
    for bad in (
        {**current, "requirement_met": False},
        {**current, "accepted_plans": []},
        {**current, "accepted_plans": [{**plan, "time_anchor": "6月20日"}]},
        {**current, "accepted_plans": [{**plan, "kind": "other"}]},
        {**current, "plan_items": {**legacy["plan_items"], "follow_up": True}},
    ):
        assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=bad) is None


# ---- 复审（371623deb）P2：同值的不同真实字段各自保留，不按纯正文去重 ----

def _old_371623deb_documents(rows):
    """371623deb 的 _discharge_plan_documents 原样摘录（按纯正文跨字段去重），仅用于构造旧输入冻结。"""

    documents, kept = [], []
    for row in rows:
        fields, seen_values = [], set()
        for key, label in tumor._DISCHARGE_PLAN_TEXT_FIELDS:
            value = str(row.get(key) or "").strip()
            if value and value not in seen_values:
                seen_values.add(value)
                fields.append(extraction.DischargePlanField(key, label, value))
        if fields:
            kept.append(row)
            documents.append(extraction.DischargePlanDocument(f"doc_{len(documents) + 1:02d}", tuple(fields)))
    return tuple(documents), tuple(kept)


class _FieldCheckingClient:
    """固定应答：先核对实际收到的字段，再按字段身份作答——只在 discharge_order 字段中取出院后计划。"""

    provider_code = "synthetic"
    model = "synthetic-discharge-plan"

    def __init__(self, expected_fields=None):
        self.expected_fields = expected_fields
        self.prompts = []
        self.received = []

    async def generate(self, prompt, **kwargs):
        import json

        self.prompts.append(prompt)
        documents = json.loads(prompt.rsplit("\n", 1)[1])
        self.received.append(documents)
        output = []
        for document in documents:
            fields = {(item["field"], item["label"]): item["text"] for item in document["fields"]}
            if self.expected_fields is not None:
                assert fields == self.expected_fields, fields
            orders = [item for item in document["fields"] if item["field"] == "discharge_order"]
            arrangements = [{"field": "discharge_order", "kind": "tumor_treatment", "timing": "post_discharge_planned",
                             "quote": orders[0]["text"].rstrip("。"), "time_anchor": "3周后"}] if orders else []
            output.append({"local_doc_id": document["local_doc_id"], "review_state": "complete",
                           "arrangements": arrangements})
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
            {"schema_version": extraction.SCHEMA_VERSION, "documents": output}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.mark.asyncio
@pytest.mark.parametrize("earlier_field,earlier_label", [("content", "正文"), ("treatment_course", "诊疗经过")])
async def test_equal_text_in_distinct_fields_keeps_both_field_identities(earlier_field, earlier_label):
    text = "3周后返院化疗。"
    row = {"document_id": "discharge-1", earlier_field: text, "discharge_order": text}
    client = _FieldCheckingClient({(earlier_field, earlier_label): text, ("discharge_order", "出院医嘱"): text})
    _result, final = await _run([row], client)
    # 实际送模保留两个字段及其标签、完整正文，出院医嘱没有被当作正文/诊疗经过合并掉。
    [[document]] = client.received
    assert [item["field"] for item in document["fields"]] == [earlier_field, "discharge_order"]
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == ("compliant", "requirement_satisfied")
    assert loaded["customer_display_facts"]["accepted_plans"] == [
        {"kind": "tumor_treatment", "quote": "3周后返院化疗", "time_anchor": "3周后", "document_index": 1,
         "field": "discharge_order"}]
    assert _evidence_ids(final) == {("discharge_record", "discharge-1")}


@pytest.mark.asyncio
async def test_restored_field_input_does_not_reuse_old_deduplicated_freeze(monkeypatch):
    text = "3周后返院化疗。"
    row = {"document_id": "discharge-1", "content": text, "discharge_order": text}

    # 旧实现（371623deb 去重）经真实执行器与抽取写出冻结；送模只剩 content。
    current_builder = tumor._discharge_plan_documents
    monkeypatch.setattr(tumor, "_discharge_plan_documents", _old_371623deb_documents)
    old_client = _FieldCheckingClient({("content", "正文"): text})
    _result, old_final = await _run([row], old_client)
    assert len(old_client.prompts) == 1 and old_final["status"] == "non_compliant"
    [old_file] = _freeze_files()
    old_bytes = _read_bytes(old_file)
    # 旧实现能读取该冻结：再次执行零调用。
    old_hot = _FieldCheckingClient()
    await _run([row], old_hot)
    assert old_hot.prompts == []

    # 修复后：相同原始材料补回 discharge_order，冻结键不同，重新抽取，不复用丢字段结果。
    monkeypatch.setattr(tumor, "_discharge_plan_documents", current_builder)
    new_client = _FieldCheckingClient({("content", "正文"): text, ("discharge_order", "出院医嘱"): text})
    _result, new_final = await _run([row], new_client)
    assert len(new_client.prompts) == 1
    assert new_final["status"] == "compliant"
    assert _read_bytes(old_file) == old_bytes and len(_freeze_files()) == 2
    # 新的完整结果第二次执行热复用。
    new_hot = _FieldCheckingClient()
    _result, hot_final = await _run([row], new_hot)
    assert new_hot.prompts == [] and hot_final["customer_display_facts"] == new_final["customer_display_facts"]


@pytest.mark.asyncio
async def test_unaffected_input_keeps_hitting_freeze_written_before_the_fix(monkeypatch):
    # 无同值字段的输入，修复前后送模载荷完全一致，旧冻结继续热复用。
    row = {"document_id": "discharge-1", "treatment_course": "住院期间行第2周期化疗。", "discharge_order": "3周后返院化疗。"}
    current_builder = tumor._discharge_plan_documents
    assert _old_371623deb_documents([row])[0] == current_builder([row])[0]
    monkeypatch.setattr(tumor, "_discharge_plan_documents", _old_371623deb_documents)
    await _run([row], _FieldCheckingClient())
    monkeypatch.setattr(tumor, "_discharge_plan_documents", current_builder)
    hot = _FieldCheckingClient()
    _result, final = await _run([row], hot)
    assert hot.prompts == [] and final["status"] == "compliant"
    assert len(_freeze_files()) == 1
