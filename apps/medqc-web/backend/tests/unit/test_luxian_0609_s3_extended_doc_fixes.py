"""Stage 3 P1/P2 扩展文书族修复回归测试（全合成无 PHI）。

覆盖：
- P1-1: LX0609-05-01-04 检验主表未同步守卫（labtest_master=0 且医嘱表有检验/培养医嘱）
- P1-3: LX0609-05-01-06 无标题电子会诊单副高意见 & 请会诊执行记录感染科/ICU专项会诊 & 窗内优先
- P1-5: LX0609-10-02-01/02 多次转科无科室标签转出记录前置容差（[-2h, 0)）
- P1-6b: LX0609-04-02-09 death_record 投影 visit_type 与无序 PDF 补录重复行确定性去重
- P1-7: LX0609-06-04-01/02 同分钟整分(:00)截断时间容差（不放行跨分钟或带秒提前）
- P2-3: LX0609-08-02-02 “请示上级医师后医院[予以]办理出院”笔误识别与提示词覆盖
"""

from __future__ import annotations

from datetime import datetime
from itertools import permutations
import json

import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.extended_document import antimicrobial_family as amf
from app.services.luxian_0609 import source_evidence_reader as reader
from app.services.luxian_0609.critical_value_result_mapping import (
    critical_value_customer_fact_status_is_valid,
    validate_published_critical_value_facts,
)
from app.services.luxian_0609.extended_document import (
    discharge_approval_extraction as approval,
)
from app.services.luxian_0609.extended_document_critical_value import (
    effective_disposition_elapsed_seconds,
)
from tests.unit.test_luxian_0609_p0_extended_doc_fixes import _run_rules


# =====================================================================
# P1-1: LX0609-05-01-04 检验主表未同步守卫
# =====================================================================


def _two_key_drug_orders():
    return (
        {
            "order_id": "K1",
            "generic_name": "注射用美罗培南",
            "drug_apply_method": "静脉滴注",
            "order_status": "新开",
            "planned_start_datetime": "2026-04-05 10:00:00+08:00",
        },
        {
            "order_id": "K2",
            "generic_name": "注射用盐酸万古霉素",
            "drug_apply_method": "静脉滴注",
            "order_status": "新开",
            "planned_start_datetime": "2026-04-06 10:00:00+08:00",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nondrug_orders",
    [
        ({"order_id": "L1", "order_type": "检验", "order_status": "新开", "order_name": "全血需氧培养"},),
        ({"order_id": "L2", "order_status": "新开", "order_name": "痰一般细菌培养"},),
        ({"order_id": "L3", "order_class": "检验", "order_status": "核实", "order_name": "血常规"},),
    ],
    ids=["order_type_lab", "culture_name_only", "order_class_lab"],
)
async def test_p1_1_empty_lab_master_with_active_lab_orders_downgrades_05_01_04_to_data_gap(
    nondrug_orders,
):
    rows = {
        "inpat_drug_order": _two_key_drug_orders(),
        "inpat_nondrug_order": nondrug_orders,
        "labtest_master": (),
        "labtest_item_report": (),
    }
    _, finals = await _run_rules(("LX0609-05-01-04",), rows)
    assert finals["LX0609-05-01-04"]["status"] == "data_gap"
    assert finals["LX0609-05-01-04"]["reason_code"] == "source_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nondrug_orders,lab_master_rows",
    [
        # 无任何检验医嘱，仅有护理/监护医嘱 -> 仍按原逻辑判 non_compliant
        (
            ({"order_id": "N1", "order_type": "护理", "order_status": "新开", "order_name": "二级护理"},),
            (),
        ),
        # 培养医嘱已取消/作废 -> 不算有效检验医嘱，仍判 non_compliant
        (
            ({"order_id": "C1", "order_type": "检验", "order_status": "已取消", "order_name": "痰一般细菌培养"},),
            (),
        ),
        # labtest_master 非空（已正常同步，但确实没有病原学检查）-> 仍判 non_compliant
        (
            ({"order_id": "L1", "order_type": "检验", "order_status": "新开", "order_name": "血常规"},),
            ({"test_id": "T1", "labtest_subject": "血常规", "sample_datetime": "2026-04-04 08:00:00"},),
        ),
    ],
    ids=["only_non_lab_orders", "cancelled_lab_order", "synced_lab_master_without_pathogen"],
)
async def test_p1_1_guard_preserves_non_compliant_when_lab_synced_or_no_active_lab_orders(
    nondrug_orders,
    lab_master_rows,
):
    rows = {
        "inpat_drug_order": _two_key_drug_orders(),
        "inpat_nondrug_order": nondrug_orders,
        "labtest_master": lab_master_rows,
        "labtest_item_report": (),
    }
    _, finals = await _run_rules(("LX0609-05-01-04",), rows)
    assert finals["LX0609-05-01-04"]["status"] == "non_compliant"
    assert finals["LX0609-05-01-04"]["reason_code"] == "requirement_violated"


@pytest.mark.asyncio
async def test_p1_1_synced_pre_start_pathogen_sample_remains_compliant():
    rows = {
        "inpat_drug_order": _two_key_drug_orders(),
        "inpat_nondrug_order": (
            {"order_id": "L1", "order_type": "检验", "order_status": "新开", "order_name": "痰一般细菌培养"},
        ),
        "labtest_master": (
            {"test_id": "T-CULT", "labtest_subject": "痰一般细菌培养", "sample_datetime": "2026-04-05 08:00:00"},
        ),
        "labtest_item_report": (),
    }
    _, finals = await _run_rules(("LX0609-05-01-04",), rows)
    assert finals["LX0609-05-01-04"]["status"] == "compliant"
    assert finals["LX0609-05-01-04"]["reason_code"] == "requirement_satisfied"


# =====================================================================
# P1-3: LX0609-05-01-06 特殊级抗菌药会诊识别补全与窗内优先
# =====================================================================


class _TargetedSpecialApprovalClient:
    """只根据收到的 prompt 文档返回对应的合成同意引文，并记录收到的 doc_refs。"""

    def __init__(self, expected_quotes: dict[str, str]):
        self.expected_quotes = expected_quotes
        self.seen_payloads: list[dict] = []

    async def generate(self, prompt: str, **kwargs):
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        self.seen_payloads.append(payload)
        texts = {doc["doc_ref"]: doc["text"] for doc in payload["documents"]}
        events = []
        for ev in payload["events"]:
            quote = self.expected_quotes.get(ev["drug"], "")
            ref = next((r for r in ev["doc_refs"] if quote and quote in texts.get(r, "")), "")
            events.append({
                "event_id": ev["event_id"],
                "documented_use": "yes" if ref else "no",
                "approval_quote": quote if ref else "",
                "quote_doc_refs": {"approval": ref} if ref else {},
            })
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps({
                    "schema_version": "lx0609_special_antimicrobial_approval_v1",
                    "events": events,
                }, ensure_ascii=False)},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


@pytest.mark.asyncio
async def test_p1_3_untitled_request_with_deputy_chief_opinion_and_short_title_recognized():
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "(JC)注射用美罗培南(0.25g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2026-07-05 21:54:13+08:00",
            },
            {
                "document_id": "ord-v",
                "order_id": "O-V",
                "generic_name": "(JC)注射用盐酸万古霉素(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2026-07-27 11:34:27+08:00",
            },
        ),
        "consultation_record": (
            # document_title=None，电子申请单 + 副主任医师会诊意见（启用前 1h40m）
            {
                "document_id": "cons-m-early",
                "document_title": None,
                "record_time": "2026-07-05 20:14:04",
                "record_content": (
                    "本病人建议使用【(JC)注射用美罗培南(0.25g)】,使用目的为:治疗-内科-经验,"
                    "指征:急性细菌性下呼吸道感染。合成甲副主任医师会诊意见:患者重症肺炎,"
                    "哌拉西林他唑巴坦抗感染疗效差,同意升级抗生素为美罗培南。遵嘱执行。"
                ),
            },
            # 39 小时后的续用会诊不应挤掉启用前会诊
            {
                "document_id": "cons-m-late",
                "document_title": "请会诊执行记录",
                "record_time": "2026-07-07 12:58:00",
                "record_content": (
                    "感染科合成乙副主任医师：同意继续美罗培南加强抗感染。"
                ),
            },
            # 简写职称“副主任：”
            {
                "document_id": "cons-v-early",
                "document_title": "请会诊执行记录",
                "record_time": "2026-07-27 11:44:00",
                "record_content": (
                    "本病人建议使用【(JC)注射用盐酸万古霉素(0.5g)】，使用目的为：治疗-内科-经验。"
                    "感染性疾病科合成丙副主任：结合患者病史及相关检查检验，同意使用万古霉素，加强抗感染。遵嘱。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-08-01", "basis": "discharge_date"},),
    }
    client = _TargetedSpecialApprovalClient({
        "美罗培南": "同意升级抗生素为美罗培南",
        "万古霉素": "同意使用万古霉素",
    })
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "requirement_satisfied"
    # 窗内已有提及美罗培南的会诊单，39h 后的续用会诊不应送入美罗培南事件候选
    sent_texts = {doc["doc_ref"]: doc["text"] for doc in client.seen_payloads[0]["documents"]}
    m_event = next(ev for ev in client.seen_payloads[0]["events"] if ev["drug"] == "美罗培南")
    assert all("同意继续美罗培南" not in sent_texts[ref] for ref in m_event["doc_refs"])


@pytest.mark.asyncio
async def test_p1_3_invited_icu_and_id_econsult_with_long_imaging_summary_recognized():
    long_ct = "胸部CT提示双肺感染伴少量胸腔积液；双侧胸膜增厚粘连；" * 6
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "(4+7)注射用美罗培南(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2025-12-16 10:43:49+08:00",
            },
            {
                "document_id": "ord-v",
                "order_id": "O-V",
                "generic_name": "(JC)伏立康唑片(50mg*10片)",
                "drug_apply_method": "口服",
                "order_status": "新开",
                "planned_start_datetime": "2025-12-22 11:47:07+08:00",
            },
        ),
        "consultation_record": (
            # 单独临床药学会诊仍不计入授权专家
            {
                "document_id": "cons-pharm",
                "document_title": "请会诊执行记录",
                "record_time": "2025-12-16 10:10:00",
                "record_content": (
                    "2025-12-16 10:10 请会诊执行记录\n"
                    "故邀请临床药学合成甲医生协助诊治：建议可换用美罗培南加强抗感染。"
                ),
            },
            # 重症医学科专项会诊同意使用美罗培南（启用前 23m）
            {
                "document_id": "cons-icu",
                "document_title": "请会诊执行记录",
                "record_time": "2025-12-16 10:20:00",
                "record_content": (
                    "2025-12-16 10:20 请会诊执行记录\n"
                    "临床药学会诊后建议给予美罗培南抗感染，故邀请重症医学科合成乙医生协助诊治："
                    "患者合并重症肺部感染，感染指标升高，同意使用美罗培南加强抗感染。尊会诊意见执行。"
                ),
            },
            # 感染科专项会诊含较长CT描述后建议伏立康唑（启用前 18.6h）
            {
                "document_id": "cons-id",
                "document_title": "请会诊执行记录",
                "record_time": "2025-12-21 17:10:00",
                "record_content": (
                    "2025-12-21 17:10 请会诊执行记录\n"
                    f"G试验升高，故邀请感染科合成丙医生协助诊治：{long_ct}"
                    "目前考虑：肺真菌感染。建议给予伏立康唑抗感染。尊会诊意见执行。"
                ),
            },
            # 18 天后的续用会诊不得覆盖启用前会诊
            {
                "document_id": "cons-late",
                "document_title": "请会诊执行记录",
                "record_time": "2026-01-03 09:14:00",
                "record_content": "感染科合成丁副主任医师：同意使用美罗培南及继续使用伏立康唑。",
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-01-05", "basis": "discharge_date"},),
    }
    client = _TargetedSpecialApprovalClient({
        "美罗培南": "同意使用美罗培南加强抗感染",
        "伏立康唑": "建议给予伏立康唑抗感染",
    })
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "requirement_satisfied"


@pytest.mark.parametrize(
    "text,quote,expected",
    [
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "同意升级抗生素为美罗培南",
            True,
        ),
        (
            "请会诊执行记录\n故邀请感染科合成甲医生协助诊治：患者肺真菌感染，建议给予伏立康唑抗感染。",
            "建议给予伏立康唑抗感染",
            True,
        ),
        # 负向守卫：单独临床药学、申请单文字、主治医师、他科、非请会诊执行记录的无职称文本均拒绝
        (
            "请会诊执行记录\n故邀请临床药学合成甲医生协助诊治：建议换用美罗培南抗感染。",
            "建议换用美罗培南抗感染",
            False,
        ),
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲主治医师会诊意见:同意升级抗生素为美罗培南。",
            "同意升级抗生素为美罗培南",
            False,
        ),
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。呼吸科合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "同意升级抗生素为美罗培南",
            False,
        ),
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "本病人建议使用【注射用美罗培南】",
            False,
        ),
        (
            "请会诊执行记录\n故邀请感染科合成甲主治医师协助诊治：建议给予伏立康唑抗感染。",
            "建议给予伏立康唑抗感染",
            False,
        ),
    ],
)
def test_p1_3_special_approval_helper_boundaries(text: str, quote: str, expected: bool):
    assert amf._special_approval_by_authorized_expert(text, quote) is expected


# =====================================================================
# P1-5: LX0609-10-02-01 & LX0609-10-02-02 多次转科前置转出容差
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ("LX0609-10-02-02", "LX0609-10-02-01"))
async def test_p1_5_multi_transfer_unlabelled_out_81s_before_order_is_compliant(rule):
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-06-22 08:00:00", "discharge_datetime": "2026-07-10 10:00:00"},),
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-22 08:48:35"},
            {"order_id": "O2", "order_name": "转入ICU", "order_status": "核实", "prescribed_datetime": "2026-06-23 16:32:26"},
            {"order_id": "O3", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 09:52:21"},
            {"order_id": "O4", "order_name": "转入ICU", "order_status": "新开", "prescribed_datetime": "2026-07-04 12:38:06"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-22 10:37:00"},
            {"document_id": "I2", "record_time": "2026-06-23 17:03:00"},
            {"document_id": "I3", "record_time": "2026-06-27 10:28:16"},
            {"document_id": "I4", "record_time": "2026-07-04 13:20:00"},
        ),
        "transfer_out_record": (
            {"document_id": "U1", "record_time": "2026-06-22 09:30:00"},
            {"document_id": "U2", "record_time": "2026-06-23 16:33:00"},
            # 早于 O3 (09:52:21) 仅 81 秒，且未填科室字段
            {"document_id": "U3", "record_time": "2026-06-27 09:51:00"},
            {"document_id": "U4", "record_time": "2026-07-04 12:38:44"},
        ),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-07-10",
            "horizon_datetime": "2026-07-10 10:00:00",
            "basis": "discharge_date",
            "task_frozen_date": "2026-07-15",
        },),
    }
    _, finals = await _run_rules((rule,), rows)
    assert finals[rule]["status"] == "compliant"
    events = finals[rule]["customer_display_facts"]["event_checks"]
    assert len(events) == 4
    assert all(ev["status"] == "compliant" for ev in events)


@pytest.mark.asyncio
async def test_p1_5_multi_transfer_far_before_order_6h_is_not_reassigned():
    rows = {
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入ICU", "order_status": "核实", "prescribed_datetime": "2026-06-23 16:32:26"},
            {"order_id": "O2", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 09:52:21"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-23 17:03:00"},
            {"document_id": "I2", "record_time": "2026-06-27 10:28:16"},
        ),
        "transfer_out_record": (
            {"document_id": "U1", "record_time": "2026-06-23 16:33:00"},
            # 早于 O2 达 6 小时（超过 2 小时前置容差）
            {"document_id": "U2", "record_time": "2026-06-27 03:50:00"},
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "non_compliant"


# =====================================================================
# P1-6b: LX0609-04-02-09 visit_type 投影与行序无关去重
# =====================================================================


def test_p1_6b_source_evidence_reader_projects_visit_type_for_death_record():
    assert "visit_type" in reader._NATIVE_SOURCE_FIELDS["death_record"]
    assert "visit_type" in reader._SNAPSHOT_SOURCE_FIELDS["death_record"]


@pytest.mark.asyncio
async def test_p1_6b_death_record_with_pdf_visit_type_i_duplicate_is_order_independent_compliant():
    emr_row = {
        "document_id": "death-emr-01",
        "visit_type": "住院",
        "document_title": "死亡记录",
        "document_status": "Save",
        "death_datetime": "2026-01-29 09:26:00+08:00",
        "record_time": "2026-01-29 09:51:26",
        "submit_datetime": "2026-01-29 09:51:26",
        "record_content": "结构化死亡记录正文。死亡时间：2026-01-29 09:26。",
        "treatment_course": "住院诊疗与抢救经过。",
    }
    pdf_dup_row = {
        "document_id": "death-pdf-02",
        "visit_type": "I",
        "document_title": "死亡记录",
        "document_status": None,
        "death_datetime": None,
        "death_time": None,
        "record_time": None,
        "submit_datetime": None,
        "treatment_course": None,
        "record_content": "死亡时间：2026年01月29日 09:26。PDF 补录完整死亡记录正文。",
    }
    for ordered_pair in permutations((emr_row, pdf_dup_row)):
        rows = {
            "inpat_registration": ({"admission_datetime": "2025-10-05 08:00:00"},),
            "death_record": tuple(ordered_pair),
            "discharge_record": (),
        }
        _, finals = await _run_rules(("LX0609-04-02-09",), rows)
        assert finals["LX0609-04-02-09"]["status"] == "compliant"
        assert finals["LX0609-04-02-09"]["reason_code"] == "requirement_within_threshold"
        assert finals["LX0609-04-02-09"]["customer_display_facts"]["elapsed_seconds"] == 1526.0


# =====================================================================
# P1-7: LX0609-06-04-01 & LX0609-06-04-02 同分钟整分(:00)精度容差
# =====================================================================


@pytest.mark.parametrize(
    "disp,rep,expected",
    [
        # 同分钟且处置时间为整分 :00 -> 视为 0.0 秒同步处置
        (datetime(2026, 7, 31, 15, 28, 0), datetime(2026, 7, 31, 15, 28, 16), 0.0),
        (datetime(2026, 8, 1, 9, 17, 0), datetime(2026, 8, 1, 9, 17, 47), 0.0),
        # 正常晚于报告
        (datetime(2026, 7, 31, 15, 29, 0), datetime(2026, 7, 31, 15, 28, 16), 44.0),
        # 跨分钟提前（如 13:59:00 vs 14:00:00，或 15:27:00 vs 15:28:16）-> 严格拒绝
        (datetime(2026, 6, 1, 13, 59, 0), datetime(2026, 6, 1, 14, 0, 0), None),
        (datetime(2026, 7, 31, 15, 27, 0), datetime(2026, 7, 31, 15, 28, 16), None),
        # 同分钟但处置时间带非零秒且早于报告 -> 严格拒绝
        (datetime(2026, 7, 31, 15, 28, 10), datetime(2026, 7, 31, 15, 28, 16), None),
    ],
)
def test_p1_7_effective_disposition_elapsed_seconds_boundaries(disp, rep, expected):
    assert effective_disposition_elapsed_seconds(disp, rep) == expected


@pytest.mark.asyncio
async def test_p1_7_same_minute_truncated_daily_course_crisis_note_satisfies_both_rules():
    rows = {
        "labtest_master": (
            {"test_id": "t-1", "labtest_subject": "血气分析"},
            {"test_id": "t-2", "labtest_subject": "血气分析"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "二氧化碳分压",
                "result": "71.00",
                "abnormal_indicator": "PH",
                "report_time": "2026-07-31 15:28:16",
            },
            {
                "document_id": "li-2",
                "test_id": "t-2",
                "item_name": "二氧化碳分压",
                "result": "79.00",
                "abnormal_indicator": "PH",
                "report_time": "2026-08-01 09:17:47",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-1",
                "document_title": "危急值处理记录",
                "record_time": "2026-07-31 15:28:00",
                "record_content": "接危急值报告：血气分析 pCO2 71.00mmHg，已调整呼吸机参数并复查。",
            },
            {
                "document_id": "dc-2",
                "document_title": "危急值处理记录",
                "record_time": "2026-08-01 09:17:00",
                "record_content": "接危急值报告：血气分析 pCO2 79.00mmHg，已调整无创通气参数并监测。",
            },
        ),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-08-05",
            "horizon_datetime": "2026-08-05 10:00:00",
            "basis": "discharge_date",
        },),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
        assert finals[rule_id]["status"] == "compliant"
        facts = json.loads(json.dumps(finals[rule_id]["customer_display_facts"]))
        valid, published = validate_published_critical_value_facts(rule_id=rule_id, raw=facts)
        assert valid and published == facts
        assert critical_value_customer_fact_status_is_valid(
            rule_id=rule_id, status=finals[rule_id]["status"], safe_facts=facts
        )
    assert all(
        ev["interval_hours"] == 0.0
        for ev in finals["LX0609-06-04-01"]["customer_display_facts"]["event_results"]
    )


# =====================================================================
# P2-3: LX0609-08-02-02 “请示上级医师后医院[予以]办理出院”笔误容错
# =====================================================================


@pytest.mark.asyncio
async def test_p2_3_discharge_approval_prompt_and_extraction_cover_senior_typo():
    sentence = "患者家属拒绝继续治疗，要求出院并签字，请示上级医师后医院办理出院，建议院外继续治疗。"
    doc = approval.DischargeApprovalInput("doc_01", "daily_course_record", sentence)
    prompts_seen: list[str] = []

    class _TypoPassageClient:
        def supports_strict_json_schema(self):
            return True

        async def generate(self, prompt: str, **kwargs):
            prompts_seen.append(prompt)
            payload = {
                "schema_version": approval.PASSAGE_SCHEMA_VERSION,
                "items": [{
                    "local_doc_id": "doc_01",
                    "opinion": "approved",
                    "role": "senior",
                    "passage_id": "doc_01:1",
                }],
            }
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    assert "请示上级医师后医院办理出院" in approval._prompt((doc,))
    rows = {
        "inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-01-28 16:00:00"},),
        "daily_course_record": ({
            "document_id": "dc-10",
            "source_version_key": "dc-10-v1",
            "record_time": "2026-01-28 14:30:00",
            "record_content": sentence,
        },),
    }
    _, finals = await _run_rules(("LX0609-08-02-02",), rows, llm_client=_TypoPassageClient())
    assert finals["LX0609-08-02-02"]["status"] == "compliant"
    assert finals["LX0609-08-02-02"]["reason_code"] == "requirement_satisfied"
    assert any("请示上级医师后医院办理出院" in p for p in prompts_seen)
