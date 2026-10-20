"""补核模板只修正合成协议错误，不能改变业务判定或降低引文校验。"""
from copy import deepcopy
from datetime import datetime
import json

import pytest

from app.services.luxian_0609 import transfusion_order_trigger as orders
from app.services.luxian_0609 import intraoperative_transfusion_facts as intra
from app.services.luxian_0609.extended_document import transfusion_performance_extraction as performance
from app.services.luxian_0609 import native_transfusion_execution as native
import test_luxian_0609_native_transfusion_execution as support


class Client:
    def __init__(self, payloads, *, finish="stop"):
        self.payloads = payloads
        self.finish = finish
        self.prompts = []

    async def generate(self, prompt, temperature=None, **kwargs):
        self.prompts.append(prompt)
        payload = self.payloads[min(len(self.prompts) - 1, len(self.payloads) - 1)]
        return {"choices": [{"finish_reason": self.finish if len(self.prompts) == 1 else "stop",
                             "message": {"content": json.dumps(payload, ensure_ascii=True)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "_api_time": 0.25}


def fixture(site):
    if site == "orders":
        good = {"schema_version": orders.SCHEMA_VERSION, "orders": [
            {"index": i, "classification": "transfusion", "cancelled": False,
             "quote": f"输注红细胞{i + 1}U。\n观察。"} for i in range(2)]}
        rows = [("inpat_nondrug_order", {"order_id": f"synthetic-{i}", "order_name": item["quote"]})
                for i, item in enumerate(good["orders"])]
        return good, lambda c: orders.classify_transfusion_orders(rows, c), "orders", "index=0"
    if site == "performance":
        good = {"schema_version": performance.SCHEMA_VERSION, "documents": [
            {"document_ref": f"d{i + 1}", "state": "performed", "quote": "输注红细胞2U。",
             "start_time_quote": "09:00"} for i in range(2)]}
        rows = [{"record_content": "09:00输注红细胞2U。", "record_time": "2026-06-05 10:00:00"}] * 2
        return good, lambda c: performance.extract_transfusion_performance(rows, c), "documents", "d1"
    good = {"schema_version": intra.SCHEMA_VERSION, "documents": [
        {"document_ref": f"d{i + 1}", "state": "present", "items": [
            {"quote": "术中输注红细胞2U。", "component": "红细胞", "dose": "2U", "event_time": None}]}
        for i in range(2)]}
    docs = [intra.IntraoperativeDocument(f"synthetic-{i}", intra.SOURCES[i], "术中输注红细胞2U。")
            for i in range(2)]
    return good, lambda c: intra.extract_intraoperative_transfusion_items(
        docs, c, parse_time=datetime.fromisoformat), "documents", "d1"


def claims(payload, key, site):
    return [entry["items"][0] if site == "intra" else entry for entry in payload[key]]


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["orders", "performance", "intra"])
async def test_quote_retry_lists_all_locations_previous_output_and_usage(site):
    good, run, key, location = fixture(site)
    bad = deepcopy(good)
    for claim in claims(bad, key, site):
        claim["quote"] = "改写后的输注片段"
    client = Client([bad, good])
    result = await run(client)
    assert result.reason_code == ""
    assert result.llm_call_count == len(client.prompts) == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (20, 10, 30, 0.5)
    retry = client.prompts[1]
    assert location in retry and ("index=1" if site == "orders" else "d2") in retry
    assert "quote" in retry and "改写后的输注片段" in retry and "PREVIOUS_OUTPUT=" in retry
    assert "连续" in retry and "上次输出仅作修正参考，不是原文资料" in retry
    assert "PREVIOUS_OUTPUT=" not in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["orders", "performance", "intra"])
async def test_persistent_quote_failure_keeps_failure_contract(site):
    good, run, key, _ = fixture(site)
    for claim in claims(good, key, site):
        claim["quote"] = "未在正文出现"
    client = Client([good])
    result = await run(client)
    assert result.reason_code == "model_invalid_output"
    assert getattr(result, "state", "technical_error") == "technical_error"
    assert result.llm_call_count == len(client.prompts) == 2
    assert result.total_tokens == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("fixed", [False, True])
async def test_performance_missing_start_time_field_is_rechecked_not_assumed(fixed):
    good, run, key, _ = fixture("performance")
    bad = deepcopy(good)
    del bad[key][0]["start_time_quote"]
    client = Client([bad, good if fixed else bad])
    result = await run(client)
    assert result.llm_call_count == len(client.prompts) == 2
    assert result.total_tokens == 30
    assert result.reason_code == ("" if fixed else "model_invalid_output")
    assert result.states == (("performed", "performed") if fixed else ("unknown", "unknown"))
    assert "d1" in client.prompts[1] and "start_time_quote" in client.prompts[1]
    assert "不得省略" in client.prompts[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["orders", "performance", "intra"])
async def test_retry_decodes_unicode_identity_before_redaction(site):
    good, run, key, _ = fixture(site)
    bad = deepcopy(good)
    claims(bad, key, site)[0]["quote"] = "住院号：ZY123456，改写片段"
    client = Client([bad, good])
    result = await run(client)
    assert result.reason_code == ""
    assert "PREVIOUS_OUTPUT=" in client.prompts[1]
    assert "ZY123456" not in client.prompts[1] and "ZY123456" not in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["orders", "performance", "intra"])
async def test_structure_error_keeps_existing_call_limit(site):
    good, run, key, _ = fixture(site)
    good[key][-1]["unexpected"] = True
    # 前项引文错误不能遮蔽后项结构错误，从而新增一次调用。
    claims(good, key, site)[0]["quote"] = "改写片段"
    client = Client([good])
    result = await run(client)
    assert result.reason_code == "model_invalid_output"
    assert result.llm_call_count == len(client.prompts) == (2 if site == "orders" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["orders", "performance", "intra"])
async def test_length_keeps_call_limit_and_never_echoes_truncated_output(site):
    good, run, _, _ = fixture(site)
    client = Client([good], finish="length")
    result = await run(client)
    if site == "orders":
        assert result.reason_code == ""
        assert "截断" in client.prompts[1] and "最短" in client.prompts[1]
        assert "PREVIOUS_OUTPUT=" not in client.prompts[1]
    else:
        assert result.reason_code == "model_invalid_output"
    assert len(client.prompts) == (2 if site == "orders" else 1)


@pytest.mark.asyncio
async def test_order_missing_coverage_retry_stays_narrow_and_explains_missing_rows():
    good, run, _, _ = fixture("orders")
    first = deepcopy(good)
    first["orders"].pop()
    second = deepcopy(good)
    second["orders"].pop(0)
    client = Client([first, second])
    result = await run(client)
    assert result.state == "present"
    retry = client.prompts[1]
    assert "index=1" in retry and "遗漏" in retry and "PREVIOUS_OUTPUT=" in retry
    assert [item["index"] for item in json.loads(retry.split("INPUT_JSON=", 1)[1])["orders"]] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["application", "course", "component"])
@pytest.mark.parametrize("mode", ["repair", "persistent", "privacy", "structure"])
async def test_native_semantic_recheck_preserves_source_and_contract(monkeypatch, source, mode, caplog):
    monkeypatch.setattr(native, "read_luxian_0609_native_source_rows", support._reader)
    if source == "component":
        rule = "LX0609-07-02-02"
        body = ("输血目的：纠正贫血；开始时间14:20，输入红悬2U，结束时间16:10。"
                "输血过程中严密观察，未见不良反应。输血后复查血红蛋白提升，治疗有效。")
        monkeypatch.setitem(support._COURSE_LABELS, body, "record")
        documents = support._documents(bloodtrans_record=[{"document_id": "synthetic-component", "content": body}])
        good = {"assertion": "explicit", "component_text": "红悬", "quote": "输入红悬2U",
                "document_ref": "synthetic-component"}
        field = "quote"
    else:
        rule = "LX0609-07-01-02"
        body = "因血红蛋白65g/L申请输注悬浮红细胞2U。"
        app = {"application_id": "synthetic-application", "request_datetime": "2026-08-20 09:00:00",
               "reason_for_blood": "", "hemoglobin": "58", "record_content": body if source == "application" else ""}
        documents = support._documents(
            mr_bloodtrans=[{"transfution_datetime": "2026-08-20 14:00:00"}], blood_application=[app],
            daily_course_record=[], senior_course_record=[
                {"document_id": "synthetic-course", "record_time": "2026-08-20 09:40:00", "content": body}])
        good = {"reason_state": "present", "evidence_quote": "因血红蛋白65g/L申请输注", "application_ref": "synthetic-application"}
        field = "evidence_quote"
    bad = deepcopy(good)
    bad[field] = "住院号：ZY123456，改写片段" if mode == "privacy" else "改写后的理由或成分"
    if mode == "structure":
        bad["unexpected"] = True
    client = Client([bad, bad if mode in {"persistent", "structure"} else good])
    result = await support._execute_order_contract(
        rule_ids=(rule,), wrapper_rules=[support._wrapper(rule)], evidence_payload=documents,
        institute_id="safe-institute", patient_id="safe-patient", visit_id="safe-visit",
        source_schema=None, llm_client=client)
    assert len(client.prompts) == (1 if mode == "structure" else 2)
    expected = "technical_error" if mode in {"persistent", "structure"} else "compliant"
    assert result.results[0]["status"] == expected
    if expected == "technical_error":
        assert result.results[0]["metadata"]["reason_code"] == "model_invalid_output"
    assert result.llm_call_count == len(client.prompts) + support._protocol_calls(result)
    assert result.total_tokens == 15 * len(client.prompts)
    if mode == "privacy":
        assert "transfusion_recheck_invalid" in caplog.text
        assert "ZY123456" not in caplog.text and "改写片段" not in caplog.text
    if len(client.prompts) == 2:
        retry = client.prompts[1]
        assert field in retry and "PREVIOUS_OUTPUT=" in retry and "连续" in retry
        assert ("synthetic-component" if source == "component" else "synthetic-application") in retry
        assert "ZY123456" not in retry
        assert ("输血前病程" in retry) == (source == "course")


def test_empty_recheck_violation_keeps_generic_reason():
    from app.services.luxian_0609.transfusion_order_trigger import _RecheckViolation
    error = _RecheckViolation([])
    assert str(error) == "invalid row binding" and error.issues == ()
