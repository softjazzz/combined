"""TC02：固定正常/取消配对，正式070链；纯合成且尚未执行时先冻结。"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.services.luxian_0609 import native_extended_document_execution as native
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_material import build_material_document_refs
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

RULE = "LX0609-07-01-03"
SCHEMA_VERSION = "lx0609-transfusion-performance-v1"

CASES = [{'id': 'TC02_EXISTING_ACTUAL_C',
  'rows': {'inpat_registration': [{'admission_datetime': '2026-06-01 08:00:00'}],
           'mr_bloodtrans': [],
           'bloodtrans_record': [{'document_id': 'BLOOD-RECORD-1',
                                  'record_time': '2026-06-02 14:00:00',
                                  'record_content': '悬浮红细胞2U输注完毕。'}],
           'labtest_item_report': [{'item_code': 'HBsAg',
                                    'item_name': '乙肝表面抗原',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBsAb',
                                    'item_name': '乙肝表面抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBeAg',
                                    'item_name': '乙肝e抗原',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBeAb',
                                    'item_name': '乙肝e抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBcAb',
                                    'item_name': '乙肝核心抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HIV',
                                    'item_name': '艾滋抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HCV',
                                    'item_name': '丙肝抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'TP',
                                    'item_name': '梅毒抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'ALT',
                                    'item_name': '谷丙转氨酶',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'}]},
  'state': 'performed',
  'expected': 'compliant'},
 {'id': 'TC02_CANCEL_SAME_STRUCTURE',
  'rows': {'inpat_registration': [{'admission_datetime': '2026-06-01 08:00:00'}],
           'mr_bloodtrans': [],
           'bloodtrans_record': [{'document_id': 'BLOOD-RECORD-1',
                                  'record_time': '2026-06-02 14:00:00',
                                  'record_content': '患者原计划输血，经再次评估后取消，本次住院未实施输血。'}],
           'labtest_item_report': [{'item_code': 'HBsAg',
                                    'item_name': '乙肝表面抗原',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBsAb',
                                    'item_name': '乙肝表面抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBeAg',
                                    'item_name': '乙肝e抗原',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBeAb',
                                    'item_name': '乙肝e抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HBcAb',
                                    'item_name': '乙肝核心抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HIV',
                                    'item_name': '艾滋抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'HCV',
                                    'item_name': '丙肝抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'TP',
                                    'item_name': '梅毒抗体',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'},
                                   {'item_code': 'ALT',
                                    'item_name': '谷丙转氨酶',
                                    'result': '阴性',
                                    'report_time': '2026-06-02 10:00:00'}]},
  'state': 'cancel',
  'expected': 'data_gap'},
 {'id': '070_CANCELLED_RECORD_TIME',
  'rows': {'inpat_registration': [{'admission_datetime': '2026-10-08 07:00:00'}],
           'mr_bloodtrans': [],
           'bloodtrans_record': [{'document_id': 'CANCEL1',
                                  'record_time': '2026-10-08 08:00:00',
                                  'record_content': '患者原计划输血，经再次评估后取消，本次住院未实施输血。'}],
           'labtest_item_report': []},
  'state': 'cancel',
  'expected': 'data_gap'}]


class PerformanceFake:
    """状态由冻结场景给定，不通过词表重判正文；仅返回原子事实。"""

    def __init__(self, state, *, time_quote=None, mutation=None, error=None):
        self.state = state
        self.time_quote = time_quote
        self.mutation = mutation
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        assert kwargs["allow_length_retry"] is False
        assert kwargs["max_completion_tokens"] == 2048
        if self.error:
            raise self.error
        inputs = json.loads(prompt.split("INPUT_JSON=", 1)[1])["documents"]
        documents = []
        for index, doc in enumerate(inputs):
            spans = doc["spans"]
            span_id = next(key for key, value in spans.items() if value == doc["body"])
            state = self.state[index] if isinstance(self.state, list) else self.state
            null_atom = {"span_id": None, "start": None, "end": None, "quote": None}
            action = null_atom if state == "unknown" else {
                "span_id": span_id, "start": 0, "end": len(doc["body"]), "quote": doc["body"]}
            event_time = null_atom
            if self.time_quote is not None:
                start = doc["body"].find(self.time_quote)
                event_time = {"span_id": span_id, "start": max(start, 0),
                              "end": max(start, 0) + len(self.time_quote), "quote": self.time_quote}
            documents.append({"document_ref": doc["document_ref"], "state": state, **action,
                              "event_time": event_time})
        payload = {"schema_version": SCHEMA_VERSION, "documents": documents}
        if self.mutation:
            self.mutation(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}



async def run_case(case, reverse=False, *, client_override=None):
    rows = {key: tuple(reversed(value)) if reverse else tuple(value) for key, value in case["rows"].items()}

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, created_at="2026-10-08T10:00:00+08:00", row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("extended_document",), selected_rule_ids=(RULE,)))
    client = client_override if client_override is not None else PerformanceFake(case["state"])
    execution = await native.execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions,
        expected_rule_ids=(RULE,), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    return execution, reduced, final, client


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["original", "reversed"])
@pytest.mark.parametrize("case", CASES, ids=[item["id"] for item in CASES])
async def test_tc02_actual_and_cancelled_same_structure_through_formal_finalizer(case, reverse):
    execution, reduced, final, client = await run_case(case, reverse)
    print(json.dumps({"id": case["id"], "reverse": reverse, "native_reason": execution.decisions[0].reason_code,
        "status": final["status"], "facts": final.get("customer_display_facts"), "calls": execution.llm_call_count}, ensure_ascii=True))
    assert reduced.final_state.value == final["status"] == case["expected"]
    if case["expected"] == "compliant":
        assert reduced.reason_code == final["reason_code"] == "requirement_satisfied"
        assert final["customer_display_facts"]["performed_transfusion_confirmed"] is True
        assert final["customer_display_facts"]["checked_transfusion_times"] == ["2026-06-02 14:00:00"]
        expected_ref = build_material_document_refs("bloodtrans_record", case["rows"]["bloodtrans_record"])[0]
        assert expected_ref in execution.decisions[0].fact_refs
        # 正常C公开链沿既有合同可省略证据卡，但真实资料引用必须存在。
        assert all(item["source_document_id"] == "BLOOD-RECORD-1"
                   for item in final.get("customer_evidence", ()) if item["source_type"] == "bloodtrans_record")
    else:
        assert (final.get("customer_display_facts") or {}).get("performed_transfusion_confirmed") is not True
        assert "输血前九项缺少" not in final["findings"]
        assert "未发现已实施输血" not in final["findings"]
    assert execution.llm_call_count == len(client.calls) == 1
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (10, 5, 15)
    assert execution.results == ()


# 新保留字段必须在正式公开保存校验入口拒绝伪造状态；不经Renderer替代保存门禁。
def mixed_nc_facts(count=1):
    from test_luxian_0609_transfusion_result_mapping import _070_complete_facts

    facts = _070_complete_facts()
    facts.pop("verification_kind")
    facts["failure_kind"] = "pretransfusion_items_incomplete"
    facts["missing_items"] = ["hiv"]
    facts["required_items"] = facts.pop("checked_items")
    facts["event_checks"][0]["missing_items"] = ["hiv"]
    facts["failed_transfusion_times"] = [facts["event_checks"][0]["transfusion_time"]]
    facts["unconfirmed_record_count"] = count
    return facts


@pytest.mark.parametrize("status", ["compliant", "data_gap", "", "invented"])
def test_tc02_published_mixed_count_cannot_bypass_noncompliant_status(status):
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    with pytest.raises(ValueError):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=mixed_nc_facts(), status=status)


@pytest.mark.parametrize("count", [True, False, 0, -1, 101, "1", None])
@pytest.mark.parametrize("status", ["compliant", "non_compliant"])
def test_tc02_published_reserved_count_invalid_is_rejected_before_filtering(count, status):
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    with pytest.raises(ValueError):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=mixed_nc_facts(count), status=status)


@pytest.mark.parametrize("count", [1, 9, 100])
def test_tc02_published_legal_nc_count_and_extra_filter(count):
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    facts = mixed_nc_facts(count)
    facts["unknown_extra"] = "strip_this"
    safe = validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=facts, status="non_compliant")
    assert safe["unconfirmed_record_count"] == count
    assert "unknown_extra" not in safe and "raw_lab_rows" not in safe


def actual_case():
    return deepcopy(CASES[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, 12, "", "  "])
async def test_tc02_missing_or_unreadable_body_cannot_prove_performance(body):
    case = actual_case()
    case["rows"]["bloodtrans_record"][0]["record_content"] = body
    execution, _, final, client = await run_case(case)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 0
    assert "补写" not in final["suggestion"].split("不要据此")[0]
    assert (final.get("customer_display_facts") or {}).get("performed_transfusion_confirmed") is not True


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["plan", "cancel", "unknown"])
async def test_tc02_nonperformed_or_unknown_does_not_claim_entire_stay_no_transfusion(state):
    case = actual_case()
    case["state"] = state
    execution, _, final, client = await run_case(case)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 1
    assert (final.get("customer_display_facts") or {}).get("performed_transfusion_confirmed") is not True
    assert "未发现已实施输血" not in final["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("quote,body,expected", [
    ("14:00", "14:00悬浮红细胞2U输注完毕。", "compliant"),
    ("13:00", "13:00悬浮红细胞2U输注完毕。", "data_gap"),
    ("2026-06-02T06:00:00Z", "2026-06-02T06:00:00Z悬浮红细胞2U输注完毕。", "compliant"),
    ("2026-06-03 14:00:00", "2026-06-03 14:00:00悬浮红细胞2U输注完毕。", "data_gap"),
    ("下午2时", "下午2时悬浮红细胞2U输注完毕。", "data_gap"),
    ("14:00", "13:00及14:00各输注红细胞2U。", "data_gap"),
    ("15:00", "14:00悬浮红细胞2U输注完毕。", "data_gap"),
])
async def test_tc02_event_time_atom_is_same_source_continuous_and_equal_to_legacy_time(quote, body, expected):
    case = actual_case()
    case["rows"]["bloodtrans_record"][0]["record_content"] = body
    execution, _, final, client = await run_case(case, client_override=PerformanceFake("performed", time_quote=quote))
    assert final["status"] == expected
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_tc02_model_bool_range_is_not_integer_coordinate():
    def corrupt(payload):
        payload["documents"][0]["start"] = False

    execution, _, final, client = await run_case(actual_case(), client_override=PerformanceFake("performed", mutation=corrupt))
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_count", [1, 9])
@pytest.mark.parametrize("known_nc", [False, True])
async def test_tc02_known_mr_with_unknown_records_preserves_nc_but_cannot_publish_all_c(unknown_count, known_nc):
    case = actual_case()
    case["rows"]["mr_bloodtrans"] = [{"document_id": "synthetic-actual-MR", "transfution_datetime": "2026-06-02 14:00:00"}]
    case["rows"]["bloodtrans_record"] = [{"document_id": f"synthetic-unknown-{i}", "record_time": "2026-06-02 16:00:00",
                                           "record_content": "本次输血实施信息尚待核实。"} for i in range(unknown_count)]
    if known_nc:
        case["rows"]["labtest_item_report"] = []
    execution, _, final, client = await run_case(case, client_override=PerformanceFake("unknown"))
    assert final["status"] == ("non_compliant" if known_nc else "data_gap")
    assert execution.llm_call_count == len(client.calls) == (0 if unknown_count == 9 else 1)
    if known_nc:
        facts = final["customer_display_facts"]
        assert facts["unconfirmed_record_count"] == unknown_count
        assert facts["transfusion_event_count"] == len(facts["event_checks"]) == 1
        assert facts["checked_transfusion_times"] == ["2026-06-02 14:00:00"]
        assert f"另 {unknown_count} 份输血记录" in final["findings"]
        assert "以下缺陷仅针对已确认实施的事件" in final["findings"]
    else:
        assert not final.get("customer_display_facts")


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_tc02_multiple_dedicated_performed_records_use_one_batch_and_each_time(reverse):
    case = actual_case()
    row = deepcopy(case["rows"]["bloodtrans_record"][0])
    row["document_id"] = "synthetic-second"
    row["record_time"] = "2026-06-04 14:00:00"
    case["rows"]["bloodtrans_record"].append(row)
    execution, _, final, client = await run_case(case, reverse)
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["checked_transfusion_times"] == ["2026-06-02 14:00:00", "2026-06-04 14:00:00"]
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_tc02_model_exception_is_one_call_gap_not_retry_or_doctor_omission():
    execution, _, final, client = await run_case(actual_case(), client_override=PerformanceFake("performed", error=TimeoutError()))
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "semantic_extraction_unresolved"
    assert execution.llm_call_count == len(client.calls) == 1
    assert "不要据此补写或改写记录" in final["suggestion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_tc02_confirmed_event_before_stay_tests_stays_nc_at_public_delivery(reverse):
    case = actual_case()
    case["rows"]["mr_bloodtrans"] = [{"document_id": "synthetic-MR", "transfution_datetime": "2026-06-02 14:00:00"}]
    case["rows"]["bloodtrans_record"] = []
    for row in case["rows"]["labtest_item_report"]:
        row["report_time"] = "2026-05-31 10:00:00"
    execution, reduced, final, client = await run_case(case, reverse)
    print(json.dumps({"case": "confirmed_pre_stay", "native_state": reduced.final_state.value,
        "native_facts": dict(execution.customer_display_facts)[RULE], "public_status": final["status"],
        "public_facts": final.get("customer_display_facts")}, ensure_ascii=True))
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["failure_kind"] == "pretransfusion_tests_outside_current_stay"
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["14:00悬浮红细胞2U输注完毕。", "13:00及14:00各输注红细胞2U。"])
async def test_tc02_null_time_atom_cannot_bypass_unexplained_numeric_times(body):
    case = actual_case()
    case["rows"]["bloodtrans_record"][0]["record_content"] = body
    execution, _, final, client = await run_case(case)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_tc02_normal_non_event_numeric_times_remain_explicit_capability_gap():
    case = actual_case()
    case["rows"]["bloodtrans_record"][0]["record_content"] = "10:00检验报告，14:00悬浮红细胞2U输注完毕。"
    execution, _, final, client = await run_case(case, client_override=PerformanceFake("performed", time_quote="14:00"))
    # 当前schema不能证明多个数值时刻分别属于检验/实施；不是临床真实不合规。
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_tc02_performed_and_cancelled_consumption_refs_do_not_depend_on_row_order():
    case = actual_case()
    cancel = deepcopy(case["rows"]["bloodtrans_record"][0])
    cancel["document_id"] = "synthetic-cancel-other"
    cancel["record_content"] = "另一输血计划已取消未实施。"
    case["rows"]["bloodtrans_record"].append(cancel)
    forward = await run_case(case, client_override=PerformanceFake(["performed", "cancel"]))
    reverse = await run_case(case, True, client_override=PerformanceFake(["cancel", "performed"]))
    assert forward[2]["status"] == reverse[2]["status"] == "compliant"
    assert forward[2]["customer_display_facts"] == reverse[2]["customer_display_facts"]
    assert set(forward[0].decisions[0].fact_refs) == set(reverse[0].decisions[0].fact_refs)
    refs = build_material_document_refs("bloodtrans_record", case["rows"]["bloodtrans_record"])
    assert set(refs).issubset(forward[0].decisions[0].fact_refs)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["duplicate_ref", "wrong_quote", "extra_conclusion", "wrong_version", "missing_document"])
async def test_tc02_invalid_atomic_outputs_cannot_publish_performed(mutation):
    def corrupt(payload):
        if mutation == "duplicate_ref":
            payload["documents"].append(deepcopy(payload["documents"][0]))
        elif mutation == "wrong_quote":
            payload["documents"][0]["quote"] = "fabricated"
        elif mutation == "extra_conclusion":
            payload["documents"][0]["is_compliant"] = True
        elif mutation == "wrong_version":
            payload["schema_version"] = "invented"
        else:
            payload["documents"] = []
    execution, _, final, client = await run_case(actual_case(), client_override=PerformanceFake("performed", mutation=corrupt))
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "semantic_extraction_unresolved"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["x" * 6001, " " * 6001])
async def test_tc02_over_body_limit_is_not_silently_clipped_into_a_performed_event(body):
    case = actual_case()
    case["rows"]["bloodtrans_record"][0]["record_content"] = body
    execution, _, final, client = await run_case(case)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.fixture(autouse=True)
def offline_sqlite_only(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("TC02禁止PG、网络及真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["actual_c", "cancel_gap", "known_nc_unknown"])
async def test_tc02_synthetic_sqlite_new_instance_preserves_status_scope_and_real_source_refs(scenario, tmp_path):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result, keyed_ref

    case = actual_case()
    if scenario == "cancel_gap":
        case = deepcopy(CASES[1])
    elif scenario == "known_nc_unknown":
        case["rows"]["mr_bloodtrans"] = [{"document_id": "synthetic-MR-confirmed", "transfution_datetime": "2026-06-02 14:00:00"}]
        case["rows"]["bloodtrans_record"][0]["record_content"] = "本次实施事实尚待核实。"
        case["rows"]["labtest_item_report"] = []
        case["state"] = "unknown"
    execution, _, final, client = await run_case(case)
    assert final["status"] == {"actual_c": "compliant", "cancel_gap": "data_gap", "known_nc_unknown": "non_compliant"}[scenario]
    expected_raw_ref = build_material_document_refs("bloodtrans_record", case["rows"]["bloodtrans_record"])[0]
    assert expected_raw_ref in execution.decisions[0].fact_refs
    item = {**final, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "tc02.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            CanonicalResultStore(table).replace_for_job(db, job_row={"id": "J", "created_by": "synthetic-reviewer",
                "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key")
            db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as db:
            saved = CanonicalResultStore(table).load_selected(db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
            for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                assert saved.get(key) == item.get(key)
            projected = workspace.project_customer_safe_result_item(saved, hmac_key="test-key")
            evidence = projected["evidence"]
            assert all(e.get("source_ref", "").startswith("src_") and len(e["source_ref"]) == 28 for e in evidence)
            assert all("source_document_id" not in e and "document_id" not in e for e in evidence)
            if scenario == "actual_c":
                # 沿既有C公开合同无精确文书卡，native来源引用确实存在，不能虚称精确卡回读通过。
                assert evidence == []
            else:
                row = case["rows"]["bloodtrans_record"][0]
                dedicated = next(e for e in evidence if e.get("source_ref") == keyed_ref("src", row["document_id"], hmac_key="test-key"))
                assert dedicated["source_type"] == "bloodtrans_record"
                assert dedicated["record_time"] == row["record_time"]
                assert dedicated["field_path"] == "record_content"
                assert dedicated["evidence_excerpt"] == row["record_content"]
                if scenario == "known_nc_unknown":
                    assert projected["customer_display_facts"]["unconfirmed_record_count"] == 1
                    confirmed = next(e for e in evidence if e.get("source_ref") == keyed_ref("src", "synthetic-MR-confirmed", hmac_key="test-key"))
                    assert confirmed["source_type"] == "mr_bloodtrans"
                    assert projected["customer_display_facts"]["checked_transfusion_times"] == ["2026-06-02 14:00:00"]
            assert "event_time" not in projected.get("customer_display_facts", {})
            assert execution.llm_call_count == len(client.calls) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,count", [("compliant", 1), ("data_gap", 1), ("non_compliant", True), ("non_compliant", 0), ("non_compliant", 101)])
async def test_tc02_store_rejects_reserved_count_status_or_type_before_persisting(status, count, tmp_path):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    case = actual_case()
    case["rows"]["mr_bloodtrans"] = [{"document_id": "synthetic-actual-MR", "transfution_datetime": "2026-06-02 14:00:00"}]
    case["rows"]["labtest_item_report"] = []
    case["state"] = "unknown"
    _, _, final, _ = await run_case(case)
    assert final["status"] == "non_compliant"
    item = {**final, "status": status, "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
            "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    item["customer_display_facts"] = {**final["customer_display_facts"], "unconfirmed_record_count": count}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite:///" + (tmp_path / "tc02-reject.sqlite").as_posix())
    table.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            with pytest.raises(ValueError):
                CanonicalResultStore(table).replace_for_job(db,
                    job_row={"id": "J", "created_by": "synthetic-reviewer", "filters_json": json.dumps(
                        {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                    items=[item], now=datetime(2026, 10, 8, 12),
                    projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key")
            db.rollback()
            assert db.execute(table.select()).fetchall() == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["cancel", "plan", "unknown"])
@pytest.mark.parametrize("reverse", [False, True])
async def test_tc02_no_confirmed_event_refs_only_consumed_dedicated_materials(state, reverse):
    case = deepcopy(CASES[1])
    case["state"] = state
    second = deepcopy(case["rows"]["bloodtrans_record"][0])
    second["document_id"] = "synthetic-second-excluded"
    case["rows"]["bloodtrans_record"].append(second)
    execution, _, final, client = await run_case(case, reverse)
    expected = set(build_material_document_refs("bloodtrans_record", case["rows"]["bloodtrans_record"]))
    assert set(execution.decisions[0].fact_refs) == expected
    assert len(expected) == 2
    assert final["status"] == "data_gap"
    assert not final.get("customer_display_facts")
    assert execution.llm_call_count == len(client.calls) == 1
    # 未评价九项，不能选入注册/检验引用，也不能虚构其缺陷。
    assert "输血前九项缺少" not in final["findings"]
    assert {item["source_document_id"] for item in final["customer_evidence"]} == {
        "BLOOD-RECORD-1", "synthetic-second-excluded"}


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["cancel", "unknown"])
@pytest.mark.parametrize("reverse", [False, True])
async def test_tc02_known_mr_keeps_evaluated_registration_and_lab_refs(state, reverse):
    case = actual_case()
    case["state"] = state
    case["rows"]["mr_bloodtrans"] = [{"document_id": "synthetic-actual-MR", "transfution_datetime": "2026-06-02 14:00:00"}]
    execution, _, final, client = await run_case(case, reverse)
    expected = {ref for source, rows in case["rows"].items()
                for ref in build_material_document_refs(source, rows)}
    assert len(expected) == 12
    # 旧已确认实施路径保留四来源快照摘要，独立从冻结材料建立快照计算。
    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=tuple(case["rows"].get(key, ())),
                                         truncated=False, limit_rows=50)

    expected_session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, created_at="2026-10-08T10:00:00+08:00", row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("extended_document",), selected_rule_ids=(RULE,)))
    source_refs = {observation.snapshot_ref.removeprefix("sha256:")
                   for observation in expected_session.snapshot.observations
                   if observation.source_key in case["rows"]}
    assert len(source_refs) == 4
    expected |= source_refs
    assert len(expected) == 16
    assert set(execution.decisions[0].fact_refs) == expected
    assert final["status"] == ("compliant" if state == "cancel" else "data_gap")
    assert execution.llm_call_count == len(client.calls) == 1
