"""两条剩余真实抽取入口的重复运行、失效及失败保护；全部使用固定应答。"""

from dataclasses import replace
import json

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as ct
from app.services.luxian_0609.extended_document import diagnosis_change_extraction as diagnosis
from test_luxian_0609_ct_order_course_consistency import _Client as CtClient, _rows, _session, RULE_ID
from test_luxian_0609_diagnosis_change_extraction import _Client as DiagnosisClient, _document, _payload, _item


def identified(client, model="fixed-model"):
    client.provider_code, client.model = "fixed-provider", model
    client.api_endpoint = "https://synthetic.invalid/v1"
    return client


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(tmp_path))


async def ct_execute(client, rows=None):
    snapshot, material = _session(rows or _rows())
    return await ct.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), wrapper_rules=(),
        evidence_payload=None, llm_client=client, evidence_snapshot=snapshot, evidence_materials=material,
    )


@pytest.mark.asyncio
async def test_ct_real_family_second_run_reuses_validated_facts_without_token_charge():
    client = identified(CtClient())
    first = await ct_execute(client)
    second = await ct_execute(client)
    assert first.decisions == second.decisions
    assert first.customer_display_facts == second.customer_display_facts
    assert client.calls == 1 and second.llm_call_count == second.total_tokens == 0


@pytest.mark.asyncio
async def test_ct_model_change_invalidates_freeze():
    client = identified(CtClient())
    await ct_execute(client)
    client.model = "changed-model"
    await ct_execute(client)
    assert client.calls == 2


@pytest.mark.asyncio
async def test_ct_invalid_output_is_not_frozen():
    client = identified(CtClient({"bad": True}))
    await ct_execute(client)
    await ct_execute(client)
    assert client.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["material", "prompt"])
async def test_ct_source_or_prompt_change_invalidates(monkeypatch, change):
    client = identified(CtClient())
    await ct_execute(client)
    rows = _rows()
    if change == "material":
        rows["daily_course_record"][0]["record_content"] += "新增合成材料。"
    else:
        prompt = ct.build_ct_fact_prompt
        monkeypatch.setattr(ct, "build_ct_fact_prompt", lambda review: prompt(review) + "新版提取说明")
    await ct_execute(client, rows)
    assert client.calls == 2


@pytest.mark.asyncio
async def test_privacy_wrapper_configuration_is_used_and_unknown_ct_facts_are_not_frozen():
    from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
    from test_luxian_0609_ct_order_course_consistency import _payload as ct_payload
    client = identified(CtClient(ct_payload("unknown")))
    for _ in range(2):
        await ct_execute(wrap_luxian_0609_llm_client(client))
    assert client.calls == 2


@pytest.mark.asyncio
async def test_diagnosis_second_run_revalidates_quotes_and_does_not_charge_tokens():
    client = identified(DiagnosisClient(_payload(_item())))
    first = await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
    second = await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
    assert first.assertions == second.assertions
    assert len(client.calls) == 1 and second.llm_call_count == second.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["text", "model", "scope", "protocol", "prompt"])
async def test_diagnosis_material_configuration_or_protocol_change_invalidates(monkeypatch, change):
    client = identified(DiagnosisClient(_payload(_item())))
    documents = (_document(),)
    await diagnosis.extract_diagnosis_change_documentation(documents, client, freeze_scope="synthetic-case-a")
    scope = "synthetic-case-a"
    if change == "text":
        documents = (replace(documents[0], text=documents[0].text + "新增合成材料。"),)
    elif change == "model":
        client.model = "changed-model"
    elif change == "scope":
        scope = "synthetic-case-b"
    elif change == "protocol":
        monkeypatch.setattr(diagnosis, "FACT_FREEZE_VERSION", "changed-protocol")
    else:
        old_prompt = diagnosis._prompt
        monkeypatch.setattr(diagnosis, "_prompt", lambda docs: old_prompt(docs) + "新协议说明")
    await diagnosis.extract_diagnosis_change_documentation(documents, client, freeze_scope=scope)
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_unknown_diagnosis_facts_and_invalid_quotes_are_not_frozen():
    client = identified(DiagnosisClient(_payload(_item(reason_state="unknown", reason_quote=""))))
    for _ in range(2):
        await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_invalid_diagnosis_quotes_keep_retry_budget_and_do_not_freeze():
    client = identified(DiagnosisClient(_payload(_item(reason_quote="不在原文的内容"))))
    for _ in range(2):
        result = await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
        assert result.state == "technical_error" and result.llm_call_count == 2
    assert len(client.calls) == 4


@pytest.mark.asyncio
async def test_corrupt_or_wrong_quote_cache_is_not_trusted(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(tmp_path))
    client = identified(DiagnosisClient(_payload(_item())))
    await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    artifact = json.loads(files[0].read_text(encoding="utf8"))
    artifact["payload"]["items"][0]["reason_quote"] = "并不在本文中的伪造引文"
    files[0].write_text(json.dumps(artifact), encoding="utf8")
    result = await diagnosis.extract_diagnosis_change_documentation((_document(),), client)
    assert len(client.calls) == 2 and result.assertions[0].reason_quote != "并不在本文中的伪造引文"
