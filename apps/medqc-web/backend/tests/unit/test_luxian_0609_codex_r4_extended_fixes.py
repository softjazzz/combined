"""Codex Round-4 复审反例回归单测（全合成无 PHI，含端到端证据绑定与结果生成）：
1. 危急值 06-04-01/02：
   - 1a: 计划/意向/未执行表述（拟复查、计划降钾、准备复查、待行复查、打算补钾、尚未执行/未执行/未实施/未落实）
         绝不得计为已执行临床处置，同时保留真正已执行后附带随访计划（如“已予补钾，拟明日复查电解质”）。
   - 1b: 延迟已执行重置（“血钾 6.7。初报时尚未处理。15:28 已针对本次完成心电图复查及病情评估”）
         在目标话题未切离的情况下正确识别为 1 次已处置，同时严禁无关治疗或跨话题句误替未处置事件。
2. 特殊级抗菌药 05-01-06：
   - 剥离“同意特殊级”出授权专家身份标记，严格区分“说了什么”与“谁说的”；
   - 全量拦截所有药师（含“感染科张三药师”带/不带冒号、副主任药师、主任药师、电子会诊时间戳落款及受邀药师），
     并通过完整端到端证据绑定 + 逐字引文本地桩模型 + 结果聚合/终态化验证。
"""

from __future__ import annotations

import json
import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from tests.unit.test_luxian_0609_p0_extended_doc_fixes import _run_rules


class _VerbatimStubSpecialApprovalClient:
    """本地逐字引文桩模型：凡收到候选文书，直接返回原文中含同意/建议的逐字引文。"""

    def __init__(self, quote_override: str | None = None) -> None:
        self.quote_override = quote_override
        self.calls: list[dict] = []

    async def generate(self, prompt: str, **kwargs):
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        self.calls.append(payload)
        texts = {doc["doc_ref"]: doc["text"] for doc in payload["documents"]}
        events = []
        for ev in payload["events"]:
            chosen_ref = ""
            chosen_quote = ""
            for ref in ev["doc_refs"]:
                text = texts.get(ref, "")
                if self.quote_override and self.quote_override in text:
                    chosen_ref = ref
                    chosen_quote = self.quote_override
                    break
                for line in text.splitlines():
                    part = line.strip()
                    if any(tok in part for tok in ("同意", "建议", "加用", "使用")):
                        chosen_ref = ref
                        chosen_quote = part
                        break
                if chosen_ref:
                    break
            events.append({
                "event_id": ev["event_id"],
                "documented_use": "yes" if chosen_ref else "no",
                "approval_quote": chosen_quote,
                "quote_doc_refs": {"approval": chosen_ref} if chosen_ref else {},
            })
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": "lx0609_special_antimicrobial_approval_v1",
                            "events": events,
                        },
                        ensure_ascii=False,
                    )
                },
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }


async def _run_058_full_pipeline(
    rows: dict[str, tuple[dict, ...]],
    *,
    llm_client: _VerbatimStubSpecialApprovalClient,
):
    """运行完整 LX0609-05-01-06 证据绑定 + 规则执行 + 归约 + 聚合 + 终态化链路。"""

    rule_id = "LX0609-05-01-06"

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=False,
            limit_rows=100,
        )

    horizon_date = rows["evaluation_context.horizon"][0]["horizon_date"]
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="syn-r4-I",
        patient_id="syn-r4-P",
        visit_id="syn-r4-V",
        source_schema=None,
        created_at="2026-07-10T10:00:00+08:00",
        row_reader=read,
        evaluation_as_of_date=horizon_date,
        evaluation_horizon_policy="frozen_task_date",
        evaluation_horizon_snapshot={
            "institute_id": "syn-r4-I",
            "patient_id": "syn-r4-P",
            "visit_id": "syn-r4-V",
            "record_scene": "running",
            "evaluation_basis": "task_frozen_date",
            "resolution_status": "resolved",
            "evaluation_horizon": horizon_date,
        },
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("extended_document",),
            selected_rule_ids=(rule_id,),
        ),
    )
    execution = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule_id,),
        decision_rule_ids=(rule_id,),
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced_list = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = reduced_list[0]
    finalized = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts)[rule_id],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=execution.results,
        reduced_decisions=reduced_list,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    return execution, reduced, finalized, aggregated


# =====================================================================
# Finding #1: 危急值 06-04-01/02 计划未执行拦截 & 延迟已执行重置修复
# =====================================================================


@pytest.mark.parametrize(
    "body,expected",
    [
        # Codex Round-4 精确反例 1：计划/意向/未执行必须判 False
        ("血钾 6.7，拟复查，尚未执行", False),
        ("血钾 6.7，拟行心电图复查，未执行", False),
        ("血钾 6.7，拟予降钾治疗，暂未执行", False),
        ("血钾 6.7，计划降钾，尚未执行", False),
        ("血钾 6.7，准备复查电解质", False),
        ("血钾 6.7，打算补钾", False),
        ("血钾 6.7，待行复查", False),
        ("血钾 6.7，待予补钾", False),
        ("血钾 6.7，将予补钾", False),
        ("血钾 6.7，准备予降钾处理", False),
        ("血钾 6.7，复查血钾，尚未执行", False),
        ("血钾 6.7，予降钾治疗，尚未实施", False),
        ("血钾 6.7，予补钾，暂未落实", False),
        # Codex Round-4 精确反例 2：延迟已执行重置必须判 True
        ("血钾 6.7。初报时尚未处理。15:28 已针对本次完成心电图复查及病情评估", True),
        ("血钾 6.7。初报时尚未处理。随后已予对症处理", True),
        ("血钾 6.7。初报时尚未处理。现已完成心电图复查", True),
        ("血钾 6.7，拟复查，尚未执行，15:28 已完成复查", True),
        # 真实 EMR 正向保护：已执行 + 后续随访计划（含 PDF 折行“积极抗感\n染”）
        ("已予补钾，拟明日复查电解质", True),
        ("血钾 6.7，已予降钾治疗，拟明日复查电解质，尚未执行", True),
        ("血钾 2.8，已予补钾，尚未复查", True),
        ("血钾：6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。", True),
        ("血钾 2.8，当时尚未处理；10:20 已静脉补钾", True),
        (
            "今于09:15接到检验科危急值报告：血常规 PLT 5×10^9/L。查看患者全身皮肤多处瘀斑，血小板减少考虑与重症感染有关，积极抗感\n染，拟输注血小板。",
            True,
        ),
    ],
)
def test_codex_r4_1_affirmative_critical_value_handling_helper(
    body: str, expected: bool
) -> None:
    assert ned._has_affirmative_critical_value_handling(body) is expected


@pytest.mark.parametrize(
    "item_name,tokens,body,expected",
    [
        # Codex Round-4 反例 1
        ("钾离子", ("6.7",), "血钾 6.7，拟复查，尚未执行", False),
        ("钾离子", ("6.7",), "血钾 6.7，计划降钾，尚未执行", False),
        ("钾离子", ("6.7",), "血钾 6.7，准备复查电解质", False),
        ("钾离子", ("6.7",), "血钾 6.7，复查血钾，尚未执行", False),
        # Codex Round-4 反例 2：三句结构延迟已执行
        (
            "钾离子",
            ("6.7",),
            "血钾 6.7。初报时尚未处理。15:28 已针对本次完成心电图复查及病情评估",
            True,
        ),
        (
            "钾离子",
            ("6.7",),
            "血钾 6.7。初报时尚未处理。随后已予对症处理。",
            True,
        ),
        (
            "钾离子",
            ("6.7",),
            "血钾 6.7。初报时尚未处理。后已完成心电图复查。",
            True,
        ),
        (
            "钾离子",
            ("6.7",),
            "血钾 6.7。拟复查，尚未执行。15:28 已针对本次完成心电图复查。",
            True,
        ),
        # 严禁跨无关主题或无关查体借用后续处置
        ("钾离子", ("2.8",), "血钾危急值 2.8，未予补钾。另因发热予以退热治疗", False),
        ("钾离子", ("2.8",), "血钾危急值 2.8，未予补钾。查体：双肺湿啰音。已予抗感染治疗。", False),
        ("钾离子", ("2.8",), "血钾危急值 2.8。初报时尚未处理。另因发热已予退热治疗。", False),
        ("钾离子", ("2.8",), "血钾危急值 2.8。初报时尚未处理。血糖 2.5 mmol/L，15:28 已予高糖静推。", False),
        # 正向保护
        ("钾离子", ("2.8",), "血钾 2.8，已予补钾，拟明日复查电解质", True),
        ("钾离子", ("6.7",), "血钾：6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。", True),
        ("钾离子", ("2.8",), "血钾 2.8，当时尚未处理；10:20 已静脉补钾", True),
    ],
)
def test_codex_r4_1_event_bound_critical_value_handling_helper(
    item_name: str, tokens: tuple[str, ...], body: str, expected: bool
) -> None:
    keywords = ned._critical_value_item_keywords(item_name)
    assert (
        ned._has_affirmative_handling_for_critical_event(
            body,
            body.lower(),
            keywords,
            tokens,
            is_crisis_doc=True,
            single_event=True,
            title="危急值处理记录",
        )
        is expected
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["日常病程记录", "危急值处理记录"])
@pytest.mark.parametrize(
    "result_val,abnormal_flag,content,expected_status,expected_outcome",
    [
        # Codex Round-4 精确反例 1：计划未执行 -> 0 处置 non_compliant
        ("6.7", "PH", "血钾 6.7，拟复查，尚未执行", "non_compliant", "unhandled"),
        ("6.7", "PH", "血钾 6.7，计划降钾，尚未执行", "non_compliant", "unhandled"),
        ("6.7", "PH", "血钾 6.7，准备复查电解质", "non_compliant", "unhandled"),
        ("6.7", "PH", "血钾 6.7，复查血钾，尚未执行", "non_compliant", "unhandled"),
        # Codex Round-4 精确反例 2：延迟已执行 -> 1 处置 compliant
        (
            "6.7",
            "PH",
            "血钾 6.7。初报时尚未处理。15:28 已针对本次完成心电图复查及病情评估",
            "compliant",
            "handled",
        ),
        (
            "6.7",
            "PH",
            "血钾 6.7。初报时尚未处理。随后已予对症处理并复查心电图",
            "compliant",
            "handled",
        ),
        # R1/R2/R3 关键案例全量回归保护
        ("2.8", "PL", "血钾危急值 2.8，未予补钾。另因发热予以退热治疗", "non_compliant", "unhandled"),
        ("2.8", "PL", "血钾危急值 2.8，未予补钾", "non_compliant", "unhandled"),
        ("2.8", "PL", "血钾危急值 2.8，若再次下降再予补钾", "non_compliant", "unhandled"),
        ("2.8", "PL", "血钾 2.8，当时尚未处理；10:20 已静脉补钾", "compliant", "handled"),
        ("6.7", "PH", "血钾：6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。", "compliant", "handled"),
        ("2.8", "PL", "血钾 2.8，已予补钾，拟明日复查电解质", "compliant", "handled"),
        ("2.8", "PL", "血钾 2.8，已予补钾，拟明日复查电解质，尚未执行", "compliant", "handled"),
    ],
)
async def test_codex_r4_1_crisis_rules_end_to_end(
    title: str,
    result_val: str,
    abnormal_flag: str,
    content: str,
    expected_status: str,
    expected_outcome: str,
) -> None:
    rows = {
        "labtest_master": ({"test_id": "t-k-r4", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {
                "document_id": "li-k-r4",
                "test_id": "t-k-r4",
                "item_name": "钾离子",
                "result": result_val,
                "abnormal_indicator": abnormal_flag,
                "report_time": "2026-06-01 15:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-k-r4",
                "document_title": title,
                "record_time": "2026-06-01 15:30:00",
                "record_content": content,
            },
        ),
        "evaluation_context.horizon": (
            {
                "horizon_date": "2026-06-03",
                "horizon_datetime": "2026-06-03 10:00:00",
                "basis": "discharge_date",
            },
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == expected_status
    assert finals["LX0609-06-04-02"]["status"] == expected_status
    assert (
        finals["LX0609-06-04-02"]["customer_display_facts"]["event_results"][0]["outcome"]
        == expected_outcome
    )


# =====================================================================
# Finding #2: 特殊级抗菌药 05-01-06 身份/内容分离 & 药师全量拦截
# =====================================================================


@pytest.mark.parametrize(
    "text,expected",
    [
        # Codex Round-4 精确反例 2a：无署名裸“同意特殊级”不得识别为授权专家
        ("同意特殊级抗菌药物美罗培南", False),
        ("同意特殊级抗菌药物方案。", False),
        # Codex Round-4 精确反例 2b：各类药师（含感染科药师、无冒号、副主任/主任药师、电子落款、受邀药师）
        ("感染科张三药师：同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师同意特殊级抗菌药物美罗培南", False),
        ("会诊意见：感染科张三药师 同意使用美罗培南", False),
        ("感染科副主任药师：同意特殊级抗菌药物美罗培南", False),
        ("感染科主任药师：同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师,2026-04-07,09:59:00同意使用美罗培南", False),
        ("请会诊执行记录\n故邀请感染科张三药师协助诊治：同意使用美罗培南", False),
        # 正向对照：授权专家身份继续识别
        ("感染科李四副主任医师：同意特殊级抗菌药物美罗培南", True),
        ("感染性疾病科王五副主任：同意使用美罗培南", True),
        ("感染专家会诊同意特殊级抗菌药物方案。", True),
        ("感染性疾病科合成乙,2026-04-07,09:59:00病史敬悉同意使用，美罗培南加强抗感染。", True),
        ("请会诊执行记录\n故邀请感染科合成丙医生协助诊治：同意使用美罗培南。", True),
    ],
)
def test_codex_r4_2_has_authorized_special_antimicrobial_expert_helper(
    text: str, expected: bool
) -> None:
    assert ned._has_authorized_special_antimicrobial_expert(text) is expected


@pytest.mark.parametrize(
    "text,quote,expected",
    [
        # Codex Round-4 反例 2a
        ("同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", False),
        # Codex Round-4 反例 2b（各种药师写法，无论引文是否包含药师名）
        ("感染科张三药师：同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师：同意特殊级抗菌药物美罗培南", "感染科张三药师：同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师同意特殊级抗菌药物美罗培南", "感染科张三药师同意特殊级抗菌药物美罗培南", False),
        ("会诊意见：感染科张三药师 同意使用美罗培南", "同意使用美罗培南", False),
        ("感染科副主任药师：同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", False),
        ("感染科主任药师：同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", False),
        ("感染科张三药师,2026-04-07,09:59:00同意使用美罗培南", "同意使用美罗培南", False),
        ("请会诊执行记录\n故邀请感染科张三药师协助诊治：同意使用美罗培南", "同意使用美罗培南", False),
        # 混合发言人：先感染科主任医师，后感染科张三药师（带/不带冒号）
        (
            "感染科主任医师：病情待查。\n感染科张三药师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任医师：病情待查。\n感染科张三药师：同意特殊级抗菌药物美罗培南",
            "感染科张三药师：同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任医师：病情待查。\n感染科张三药师同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任医师：病情待查。\n感染科张三药师同意特殊级抗菌药物美罗培南",
            "感染科张三药师同意特殊级抗菌药物美罗培南",
            False,
        ),
        # 正向对照
        ("感染科李四副主任医师：同意特殊级抗菌药物美罗培南", "同意特殊级抗菌药物美罗培南", True),
        ("感染科李四副主任医师：同意特殊级抗菌药物美罗培南", "感染科李四副主任医师：同意特殊级抗菌药物美罗培南", True),
        (
            "感染科张某副主任医师会诊意见：抗感染效果不佳，请临床药学会诊后同意加用万古霉素联合抗感染。",
            "请临床药学会诊后同意加用万古霉素联合抗感染",
            True,
        ),
        ("感染专家会诊同意特殊级抗菌药物方案。", "同意特殊级抗菌药物方案", True),
    ],
)
def test_codex_r4_2_special_approval_by_authorized_expert_helper(
    text: str, quote: str, expected: bool
) -> None:
    assert ned._special_approval_by_authorized_expert(text, quote) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id,consult_text,quote_override,expected_status,expected_reason",
    [
        # ① 整份会诊只写“同意特殊级抗菌药物美罗培南”，无专家署名 -> non_compliant
        (
            "bare_agree_special_no_signature",
            "同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        # ② 唯一发言人为感染科药师/副主任药师/主任药师/电子时间戳药师 -> non_compliant
        (
            "id_pharmacist_with_colon",
            "感染科张三药师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "id_pharmacist_without_colon",
            "感染科张三药师同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "id_pharmacist_after_opinion_label",
            "会诊意见：感染科张三药师 同意使用美罗培南",
            "同意使用美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "id_deputy_chief_pharmacist",
            "感染科副主任药师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "id_chief_pharmacist",
            "感染科主任药师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "id_econsult_timestamp_pharmacist",
            "感染科张三药师,2026-04-07,09:59:00同意使用美罗培南",
            "同意使用美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "invited_id_pharmacist",
            "请会诊执行记录\n故邀请感染科张三药师协助诊治：同意使用美罗培南",
            "同意使用美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        # ④ 混合发言人：先感染科主任医师待查，后感染科张三药师同意（带/不带冒号） -> non_compliant
        (
            "mixed_chief_then_id_pharmacist_colon",
            "感染科主任医师：病情待查。\n感染科张三药师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        (
            "mixed_chief_then_id_pharmacist_no_colon",
            "感染科主任医师：病情待查。\n感染科张三药师同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "non_compliant",
            "required_document_missing",
        ),
        # ③ 正向对照：感染科副主任医师同意 -> compliant
        (
            "positive_id_deputy_chief_physician",
            "感染科李四副主任医师：同意特殊级抗菌药物美罗培南",
            "同意特殊级抗菌药物美罗培南",
            "compliant",
            "requirement_satisfied",
        ),
        (
            "positive_id_expert_consult_marker",
            "感染专家会诊同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            "compliant",
            "requirement_satisfied",
        ),
    ],
)
async def test_codex_r4_2_special_antimicrobial_full_end_to_end_pipeline(
    case_id: str,
    consult_text: str,
    quote_override: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    rows = {
        "inpat_drug_order": (
            {
                "document_id": f"ord-{case_id}",
                "order_id": f"O-{case_id}",
                "generic_name": "注射用美罗培南",
                "drug_apply_method": "静脉滴注",
                "order_status": "已执行",
                "planned_start_datetime": "2026-07-05 12:00:00+08:00",
                "prescribed_datetime": "2026-07-05 12:00:00+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": f"cons-{case_id}",
                "document_title": "请会诊执行记录",
                "record_time": "2026-07-05 10:00:00",
                "record_content": consult_text,
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-07-10", "basis": "discharge_date"},
        ),
    }
    client = _VerbatimStubSpecialApprovalClient(quote_override=quote_override)
    execution, reduced, finalized, aggregated = await _run_058_full_pipeline(
        rows, llm_client=client
    )
    assert execution.decisions[0].reason_code == reduced.reason_code == expected_reason
    assert reduced.final_state.value == finalized["status"] == aggregated["status"] == expected_status
    if expected_status == "compliant":
        assert finalized["customer_display_facts"]["support_before_use"] is True
        assert finalized["customer_display_facts"]["unmatched_special_antimicrobials"] == []
        evidence_doc_ids = {ref["source_document_id"] for ref in finalized["customer_evidence"]}
        assert f"cons-{case_id}" in evidence_doc_ids
    else:
        assert finalized["customer_display_facts"]["support_before_use"] is False
        assert finalized["customer_display_facts"]["unmatched_special_antimicrobials"] == ["美罗培南"]
        evidence_doc_ids = {ref["source_document_id"] for ref in finalized["customer_evidence"]}
        assert f"cons-{case_id}" not in evidence_doc_ids
