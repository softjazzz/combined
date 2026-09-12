"""027 恶性性质不确定的处置：无明示可疑 ⇒ 不适用；明示未决可疑 ⇒ 资料缺口。

**有意行为变更（2026-09-12，任务 S）**：本文件原先锁定
「恶性性质不确定 → `uncertain/semantic_low_confidence`」。按
`docs/plans/2026-09-12-0910-issue-backlog.md` §15.2/§15.3/§15.4 主协调裁定
（D3 + A 案判别器），该中间态改为两条出口：

* 出院诊断完整可读、无明确恶性证据、且**无**「考虑…Ca/癌/恶性/转移」类明示未决可疑
  ⇒ `not_applicable` + `trigger_absent_complete`（`display_facts=None`、`fact_refs=()`）；
* 出现明示未决可疑（如 C17 的「考虑:Ca伴瘤周转移可能」）
  ⇒ 维持 `data_gap`（不再携带只允许 `uncertain` 终态的
  `malignant_diagnosis_applicability_uncertain` 事实）。

`uncertain` 不在 027 的 catalog 允许状态内（`allowed_result_statuses =
hit; not_hit; data_quality_gap; not_applicable; needs_manual_review`），
故本次变更同时消除了「不可交付状态」。
"""

import json

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver, MalignancySource, build_stage_malignancy_sources
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


class OfflineClient:
    def __init__(self, state="uncertain"):
        self.state = state
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        payload = {"schema_version": "lx0609_malignancy_v1", "results": [
            {"ref": "D01", "state": "explicit_nonmalignant"},
            {"ref": "D02", "state": self.state},
        ]}
        return {"choices": [{"message": {"content": json.dumps(payload)}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}


@pytest.mark.parametrize("source", ["admission_record_diagnosis", "diagnosis", "discharge_record_diagnosis"])
@pytest.mark.asyncio
async def test_uncertain_resolution_retains_exact_source_row_without_prompt_coordinates(source):
    rows = ({"document_id": "private-normal", "diagnosis_name": "合成普通诊断"}, {"document_id": "private-uncertain", "diagnosis_name": "合成性质待定诊断"})
    sources = build_stage_malignancy_sources(
        visit_stage="inpatient" if source == "admission_record_diagnosis" else "discharged",
        admission_state="available", admission_rows=rows if source == "admission_record_diagnosis" else (),
        diagnosis_state="available" if source == "diagnosis" else "empty", diagnosis_rows=rows if source == "diagnosis" else (),
        discharge_diagnosis_state="available", discharge_diagnosis_rows=rows if source == "discharge_record_diagnosis" else (),
        pathology_state="empty", pathology_rows=(),
    )
    client = OfflineClient()
    resolver = MalignancyFactResolver(client)
    resolution = await resolver.resolve(sources)
    assert resolution.uncertain_rows == ((source, rows[1]),)
    assert resolution.uncertain_rows[0][1] is rows[1]
    assert await resolver.resolve(sources) is resolution
    assert resolver.claim_usage().llm_call_count == 1
    assert resolver.claim_usage().llm_call_count == 0
    assert len(client.prompts) == 1
    assert "private-" not in client.prompts[0]
    assert "source_key" not in client.prompts[0]


@pytest.mark.parametrize("source", ["diagnosis", "discharge_record_diagnosis"])
@pytest.mark.parametrize("prewarmed", [False, True])
@pytest.mark.asyncio
async def test_027_uncertainty_without_suspicion_is_not_applicable(source, prewarmed):
    rows = [{"document_id": "normal", "diagnosis_name": "合成普通诊断"}, {"document_id": "uncertain", "diagnosis_name": "合成性质待定诊断"}]
    def reader(**kwargs):
        key = kwargs["source_key"]
        material = rows if key == source else [{"document_id": "discharge", "record_content": "出院后复诊。"}] if key == "discharge_record" else []
        return SnapshotSourceRows.create(source_key=key, rows=material, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=("LX0609-027",)),
    )
    client = OfflineClient()
    resolver = MalignancyFactResolver(client)
    if prewarmed:
        # 模拟同请求内先由其他规则消费共享恶性事实，并已经认领模型用量。
        await resolver.resolve((MalignancySource(source, "available", session.materials.rows(source)),))
        assert resolver.claim_usage().llm_call_count == 1
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",), wrapper_rules=[{"rule_id": "LX0609-027", "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=("LX0609-027",),
        malignancy_resolver=resolver,
    )
    assert result.decisions[0].applicability.value == "not_applicable"
    assert result.decisions[0].reason_code == "trigger_absent_complete"
    assert result.customer_display_facts == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=("LX0609-027",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get("LX0609-027"), evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert reduced.final_state.value == "not_applicable"
    assert final["status"] == "not_applicable"
    assert final["reason_code"] == "trigger_absent_complete"
    assert final.get("customer_display_facts") is None
    assert not final.get("missing_fields")
    assert "未触发恶性肿瘤治疗计划规则" in final["findings"]
    assert len(client.prompts) == 1
    assert result.llm_call_count == (0 if prewarmed else 1)


def test_027_explicit_suspicion_discriminator_hits_only_explicit_wording():
    """A 案判别器：只有出院记录叙事列/不确定诊断名出现明示未决可疑措辞才命中。"""

    def material(**columns):
        return tumor.SourceMaterial("present", (columns,))

    uncertain = (("discharge_record_diagnosis", {"diagnosis_name": "肺占位性病变"}),)
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(treatment_course="左肺下叶团块影伴灶周结节,考虑:Ca伴瘤周转移可能,请结合临床。"),
        uncertain_rows=uncertain,
    ) is True
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(treatment_course="扫及:肝脏多发结节影,考虑:转移可能,请结合临床、随诊。"),
        uncertain_rows=uncertain,
    ) is True
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(discharge_order="考虑恶性可能,建议进一步检查。"),
        uncertain_rows=uncertain,
    ) is True
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(discharge_medications="影像提示Ca?待排,建议随访。"),
        uncertain_rows=uncertain,
    ) is True
    # 非加载白名单内的列（如 admission_condition）不参与取文：避免「扫了但读不到」的假安全感
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(admission_condition="影像提示Ca?待排,建议随访。"),
        uncertain_rows=uncertain,
    ) is False
    # 不确定诊断名本身出现明示未决可疑措辞同样命中
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(treatment_course="出院后复诊。"),
        uncertain_rows=(("discharge_record_diagnosis", {"diagnosis_name": "考虑转移可能"}),),
    ) is True
    # 非特异影像描述与良性考虑（真实 6 例 uncertain 的输入形态）一律不命中
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(
            treatment_course="胸部螺旋CT平扫:双肺少许慢性炎症可能;右肺水平裂区小结节,建议随诊复查。",
            discharge_order="每年复查胸部CT,胸外科门诊随访。",
        ),
        uncertain_rows=(("discharge_record_diagnosis", {"diagnosis_name": "肺部阴影"}),),
    ) is False
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=material(treatment_course="扫及左肾小结节,考虑:错构瘤?其他?"),
        uncertain_rows=(("discharge_record_diagnosis", {"diagnosis_name": "孤立性肺结节"}),),
    ) is False
    assert tumor._has_explicit_malignancy_suspicion(
        discharge_material=tumor.SourceMaterial("empty", ()),
        uncertain_rows=(("discharge_record_diagnosis", {"diagnosis_name": "胸腔积液"}),),
    ) is False


@pytest.mark.parametrize("source", ["diagnosis", "discharge_record_diagnosis"])
@pytest.mark.asyncio
async def test_027_explicit_suspicion_stays_data_gap_without_uncertain_facts(source):
    """C17 类「明示未决可疑」维持 data_gap，且不携带只允许 uncertain 终态的事实。"""

    rows = [
        {"document_id": "suspicious", "diagnosis_name": "合成占位性病变"},
        {"document_id": "suspicious", "diagnosis_name": "合成普通诊断"},
    ]
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key == source:
            material = rows
        elif key == "discharge_record":
            material = [{"document_id": "discharge", "treatment_course": "考虑:Ca伴瘤周转移可能,请结合临床。"}]
        else:
            material = []
        return SnapshotSourceRows.create(source_key=key, rows=material, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=("LX0609-027",)),
    )
    client = OfflineClient()
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",), wrapper_rules=[{"rule_id": "LX0609-027", "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=("LX0609-027",),
    )
    decision = result.decisions[0]
    assert (decision.applicability.value, decision.reason_code) == ("applicable", "required_field_missing")
    # `malignant_diagnosis_applicability_uncertain` 事实只允许 `uncertain` 终态（027 契约不含），
    # 携带它会被 finalizer 降级为 technical_error（本用例即防回归）。
    assert result.customer_display_facts == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=("LX0609-027",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get("LX0609-027"),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"
    assert final["reason_code"] in {
        "source_unavailable",
        "source_empty",
        "source_truncated",
        "source_readiness_unproven",
        "required_field_missing",
    }
    assert final["status"] != "technical_error"


@pytest.mark.parametrize("count", [True, 0, -1, "1"])
def test_uncertainty_display_rejects_invalid_count(count):
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    assert safe_tumor_pathology_customer_display_facts(rule_id="LX0609-027", raw={
        "verification_kind": "malignant_diagnosis_applicability_uncertain",
        "malignancy_state": "unknown", "uncertain_diagnosis_count": count,
    }) is None


@pytest.mark.parametrize("parent_count", [0, 1, 2, 3])
@pytest.mark.asyncio
async def test_027_not_applicable_uses_source_level_refs_and_projects_no_evidence(parent_count, monkeypatch):
    """`not_applicable` 不带逐条文书引用：事实回落到来源级快照引用，客户证据为空。

    原先该用例锁定「逐条不确定诊断行 → 精确父文书」的定位行为；按任务 S 的方案①，
    该出口不再携带 `uncertain_rows` 的行级引用（`fact_refs=()`），由
    `_typed_decision_from_outcome` 用来源级快照引用兜底（与既有 21 条
    `not_applicable` 同路径），因此客户证据不再投影任何单条诊断行。
    父文书容错场景仍保留为边界用例：即使 `discharge_record` 的文档材料不可用，
    也不得抛错或泄漏文书级证据。
    """
    if parent_count == 3:
        from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
        original = Luxian0609EvidenceMaterialStore.document_rows
        def reject_parent(self, source_key, *, snapshot):
            if source_key == "discharge_record":
                raise ValueError("parent snapshot mismatch")
            return original(self, source_key, snapshot=snapshot)
        monkeypatch.setattr(Luxian0609EvidenceMaterialStore, "document_rows", reject_parent)
    diagnosis_rows = [
        {"document_id": "parent", "diagnosis_id": "diagnosis-1", "diagnosis_name": "合成普通诊断"},
        {"document_id": "parent", "diagnosis_id": "diagnosis-2", "diagnosis_name": "合成性质待定诊断"},
    ]
    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = diagnosis_rows if source == "discharge_record_diagnosis" else [
            {"document_id": "parent" if parent_count else "other", "record_content": "合成出院记录"}
            for _ in range(1 if parent_count == 3 else max(1, parent_count))
        ] if source == "discharge_record" else []
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=("LX0609-027",)),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",), wrapper_rules=[{"rule_id": "LX0609-027", "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=OfflineClient(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=("LX0609-027",),
    )
    # 事实引用回落到 027 的来源级快照引用（5 个观察来源），不含单条诊断行定位。
    expected_source_refs = {
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in session.snapshot.observations
        if observation.source_key in tumor._TYPED_RULE_SOURCE_KEYS["LX0609-027"]
    }
    assert set(result.decisions[0].fact_refs) == expected_source_refs
    selected_rows = [row for ref, row in session.materials.document_rows("discharge_record_diagnosis", snapshot=session.snapshot) if ref in result.decisions[0].fact_refs]
    assert selected_rows == []
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=("LX0609-027",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get("LX0609-027"), evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == "not_applicable"
    assert final["reason_code"] == "trigger_absent_complete"
    assert not final.get("customer_evidence")
