"""正式prepare至native执行器的发送边界；全为合成材料，委托仅捕获。"""
from __future__ import annotations

import asyncio

import pytest

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.luxian_0609.privacy_identity_context import (
    PrivacyIdentityContextUnavailable, build_luxian_0609_identity_provider,
)
from test_luxian_0609_execution_failure_semantics import _all_native_settings


# 使用仍启用的首次病程鉴别诊断规则，经过同一 prepare → native → 隐私发送边界。
RULE = "LX0609-01-02-02"


class Capture:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {"content": "{}", "usage": {}}


def session_for(rows, patient="PAT-A", visit="VIS-A"):
    def reader(**kw):
        return SnapshotSourceRows.create(source_key=kw["source_key"], rows=rows.get(kw["source_key"], ()), truncated=False, limit_rows=50)
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="INST-A", patient_id=patient,
        visit_id=visit, source_schema=None, created_at="2026-10-08T00:00:00+00:00", row_reader=reader,
    )


def prepare(monkeypatch, text, *, name="合成患者甲", payload=None, patient="PAT-A", visit="VIS-A", delegate=None):
    rows = {"first_course_record": [{
        "document_id": "DOC-A", "name": name, "record_content": text,
        "first_diagnosis": "合成疾病", "differential_diagnosis": text,
    }]}
    session = session_for(rows, patient, visit)
    monkeypatch.setattr(execution_module, "build_luxian_0609_evidence_read_session", lambda **kwargs: session)
    client = delegate or Capture()
    _, ctx = asyncio.run(execution_module.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id=visit,
        medical_text="", evidence_payload=payload, llm_client=client,
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True, LUXIAN_0609_FAMILY_MAX_CONCURRENCY=1),
        institute_id="INST-A", patient_id=patient, selected_customer_rule_ids=(RULE,),
    ))
    assert ctx.unified_engine_used is True
    return client, ctx


def test_snapshot_known_name_missed_by_regex_stops_before_delegate(monkeypatch):
    client, _ = prepare(monkeypatch, "档案别称【合成患者甲】。需鉴别合成疾病。")
    assert client.prompts == []


def test_formal_native_executor_still_sends_safe_prompt(monkeypatch):
    client, _ = prepare(monkeypatch, "患者姓名：合成患者甲；需鉴别合成疾病。")
    assert len(client.prompts) == 1
    assert "合成患者甲" not in client.prompts[0]
    assert "需鉴别合成疾病" in client.prompts[0]


def test_explicit_payload_patient_identity_is_also_bound(monkeypatch):
    client, _ = prepare(monkeypatch, "档案别称【载荷患者乙】。需鉴别合成疾病。", payload={"patient_name": "载荷患者乙"})
    assert client.prompts == []


def test_short_coordinate_does_not_match_clinical_number_substring(monkeypatch):
    client, _ = prepare(monkeypatch, "需鉴别合成疾病，剂量130mg，复查间隔1.5小时。", patient="1", visit="2")
    assert len(client.prompts) == 1
    assert "130mg" in client.prompts[0] and "1.5小时" in client.prompts[0]


def test_cases_do_not_share_names_when_reusing_delegate(monkeypatch):
    delegate = Capture()
    prepare(monkeypatch, "档案别称【合成患者甲】。需鉴别合成疾病。", name="合成患者甲", delegate=delegate)
    assert delegate.prompts == []
    # 第二病例已知姓名不同：不得残留第一病例的上下文而误拦。
    prepare(monkeypatch, "档案别称【合成患者甲】。需鉴别合成疾病。", name="合成患者乙", patient="PAT-B", visit="VIS-B", delegate=delegate)
    assert len(delegate.prompts) == 1
    assert "合成患者甲" in delegate.prompts[0]
    assert "合成患者乙" not in delegate.prompts[0]


def test_provider_reads_only_explicit_patient_fields_not_nested_names():
    payload = {"patient_name": "明确患者", "age": 45, "programmatic_timeline": {
        "visit_id": "VIS-A", "structured_source_rows": {
            "first_course_record": [{"name": "文书患者", "physician_name": "保留医师", "items": [{"name": "药品甲"}]}],
            "inpat_drug_order": [{"name": "药品乙", "patient_name": "医嘱患者"}],
        },
    }}
    provider = build_luxian_0609_identity_provider(visit_id="VIS-A", evidence_payload=payload)
    assert set(provider()) == {"VIS-A", "明确患者", "文书患者", "医嘱患者"}
    payload["patient_name"] = "更新患者"
    assert "更新患者" in provider() and "明确患者" not in provider()


@pytest.mark.parametrize("kwargs", [{"snapshot_build_failed": True}, {"evidence_payload": {"patient_name": {"bad": "private"}}}])
def test_context_failure_is_fixed_and_fail_closed(kwargs):
    provider = build_luxian_0609_identity_provider(**kwargs)
    with pytest.raises(PrivacyIdentityContextUnavailable, match="^LX0609 privacy identity context unavailable$"):
        provider()


def test_material_read_failure_suppresses_private_exception(monkeypatch):
    session = session_for({"first_course_record": [{"document_id": "DOC-A", "name": "私密姓名", "record_content": "需鉴别合成疾病。"}]})
    provider = build_luxian_0609_identity_provider(institute_id="INST-A", patient_id="PAT-A", visit_id="VIS-A", snapshot=session.snapshot, materials=session.materials)
    assert "私密姓名" in provider()
    def broken(*args, **kwargs):
        raise RuntimeError("私密姓名 database-secret")
    monkeypatch.setattr(Luxian0609EvidenceMaterialStore, "document_rows", broken)
    client = Capture()
    wrapped = wrap_luxian_0609_llm_client(client, identity_provider=provider)
    with pytest.raises(Exception) as caught:
        asyncio.run(wrapped.generate("已脱敏的需鉴别合成疾病材料。"))
    assert "私密姓名" not in str(caught.value) and "database-secret" not in str(caught.value)
    assert client.prompts == []


def test_wrong_case_snapshot_cannot_supply_other_patient_identity():
    session = session_for({"first_course_record": [{"document_id": "DOC-A", "name": "其他患者", "record_content": "需鉴别合成疾病。"}]})
    provider = build_luxian_0609_identity_provider(institute_id="INST-A", patient_id="PAT-B", visit_id="VIS-B", snapshot=session.snapshot, materials=session.materials)
    with pytest.raises(PrivacyIdentityContextUnavailable):
        provider()


def test_snapshot_without_materials_does_not_silently_drop_known_names():
    session = session_for({"first_course_record": [{"document_id": "DOC-A", "name": "私密姓名", "record_content": "需鉴别合成疾病。"}]})
    provider = build_luxian_0609_identity_provider(snapshot=session.snapshot)
    with pytest.raises(PrivacyIdentityContextUnavailable):
        provider()


def test_empty_context_does_not_claim_identity_check_passed():
    with pytest.raises(PrivacyIdentityContextUnavailable):
        build_luxian_0609_identity_provider()()


def test_legacy_no_snapshot_still_has_explicit_case_identity():
    assert set(build_luxian_0609_identity_provider(institute_id="I", patient_id="P", visit_id="V")()) == {"I", "P", "V"}
