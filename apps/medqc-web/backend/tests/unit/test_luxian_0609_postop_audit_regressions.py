"""术后三日病程审计反例，经实际执行器和 Reducer 回归。"""
from copy import deepcopy

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate,
    _evaluate_selected,
)

RULE = "LX0609-04-05-01"


def _materials():
    return {
        "surgery_record": ({
            "document_id": "E1", "surgery_code": "01.2400X013",
            "surgery_begin_time": "2026-07-07 16:30:00+08",
            "surgery_end_time": "2026-07-07 18:30:00+08", "surgeon": "李明",
        },),
        "daily_course_record": tuple({
            "document_id": f"C{day}", "record_time": f"2026-07-{day:02d} 08:00:00",
            "record_content": "患者术后恢复中，继续观察。", "author_name": "李明",
        } for day in (8, 9, 10)),
        # 院方口径：术者须在术前24小时内亲自查房（放在上级医师病程，本文件用例只改日常病程）。
        "senior_course_record": ({
            "document_id": "PRE", "record_time": "2026-07-07 09:00:00",
            "record_content": "术前查房，完善术前准备。", "author_name": "李明",
        },),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("time_value", (None, "", "not-a-date"))
@pytest.mark.parametrize("all_missing", (True, False))
async def test_unavailable_course_time_is_data_gap(time_value, all_missing):
    materials = _materials()
    for row in materials["daily_course_record"] if all_missing else materials["daily_course_record"][-1:]:
        row["record_time"] = time_value
    result, reduced = await _evaluate(RULE, materials)
    facts = dict(result.customer_display_facts)[RULE]
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "required_field_missing"
    assert facts["unresolved_course_time_events"] == ["E1"]
    assert facts["unmet_surgery_events"] == []
    assert len(facts["covered_postop_dates"]) == (0 if all_missing else 2)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("variant,expected", (
    ("complete", "compliant"), ("preoperative", "non_compliant"),
    ("absent", "non_compliant"), ("one_missing", "non_compliant"),
    ("empty_body", "data_gap"), ("extra_undated", "compliant"),
))
async def test_time_gap_protection_cases(variant, expected):
    materials = _materials()
    if variant == "preoperative":
        for row in materials["daily_course_record"]:
            row["record_time"] = "2026-07-06 08:00:00"
    elif variant == "absent":
        materials["daily_course_record"] = ()
    elif variant == "one_missing":
        materials["daily_course_record"] = materials["daily_course_record"][:2]
    elif variant == "empty_body":
        materials["daily_course_record"][-1]["record_content"] = ""
    elif variant == "extra_undated":
        materials["daily_course_record"] += ({"record_content": "另份病程", "record_time": None},)
    _, reduced = await _evaluate(RULE, materials)
    assert reduced.final_state.value == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("title,expected", (
    ("王李明主任医师查房记录", False),
    ("王科李明主任医师查房记录", False),
    ("李明主任医师查房记录", True),
    ("李明副主任医师手术后查房记录", True),
    ("石跃主治医师联合神经疾病中心李明副主任医师、眼科曾亚丽主治医师查房记录", True),
    ("李明某主任医师查房记录", False),
    ("赵某主治医师联合胸外科李明副主任医师查房记录", True),
    ("赵某主治医师联合肝胆外科李明主任医师查房记录", True),
    ("王李明主任医师查房记录，术者李明", False),
    ("术者：李明主任医师查房记录", False),
))
async def test_title_matches_whole_physician_identity(title, expected):
    materials = _materials()
    for row in materials["daily_course_record"]:
        row.update(author_name="赵医生", document_title=title, record_content="术者李明完成手术，患者恢复中。")
    snapshot, store, result, reduced = await _evaluate_selected((RULE,), materials)
    assert dict(result.customer_display_facts)[RULE]["surgeon_round_present"] is expected
    assert reduced[0].final_state.value == ("compliant" if expected else "non_compliant")
    final = _canonical_extended_result(
        rule_id=RULE, snapshot=snapshot, materials=store, result=result, reduced=reduced,
    )
    assert final["status"] == ("compliant" if expected else "non_compliant")


@pytest.mark.asyncio
async def test_senior_course_title_recognizes_explicit_matching_primary_surgeon():
    materials = _materials()
    materials["surgery_record"][0]["surgeon"] = "周启航"
    materials["senior_course_record"][0]["author_name"] = "周启航"
    for row in materials["daily_course_record"]:
        row["author_name"] = "赵医生"
    materials["senior_course_record"] += ({
        "document_id": "POST",
        "record_time": "2026-07-08 09:30:00",
        "document_title": "陈立主任医师联合周启航主治医师（主刀医师）查房记录",
        "record_content": "术后第一天，患者恢复平稳，继续观察。",
        "author_name": "赵医生",
    },)

    result, reduced = await _evaluate(RULE, materials)

    assert dict(result.customer_display_facts)[RULE]["surgeon_round_present"] is True
    assert reduced.final_state.value == "compliant"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("title", "record_time", "expected"), (
    ("陈立主任医师联合周启航主刀医师查房记录", "2026-07-08 18:30:00", True),
    ("陈立主任医师联合周启航主刀医师查房记录", "2026-07-08 18:30:01", False),
    ("陈立主任医师联合孙远航主刀医师查房记录", "2026-07-08 09:30:00", False),
    ("陈立主任医师联合王周启航主刀医师查房记录", "2026-07-08 09:30:00", False),
    ("陈立主任医师联合孙远航主治医师（主刀医师）查房记录", "2026-07-08 09:30:00", False),
    ("陈立主任医师联合王周启航主治医师（主刀医师）查房记录", "2026-07-08 09:30:00", False),
    ("陈立主任医师联合周启航第一助手查房记录", "2026-07-08 09:30:00", False),
    ("陈立主任医师查房记录，周启航主刀医师", "2026-07-08 09:30:00", False),
))
async def test_primary_surgeon_title_requires_matching_identity_role_and_window(
    title, record_time, expected,
):
    materials = _materials()
    materials["surgery_record"][0]["surgeon"] = "周启航"
    materials["senior_course_record"][0]["author_name"] = "周启航"
    for row in materials["daily_course_record"]:
        row["author_name"] = "赵医生"
    materials["senior_course_record"] += ({
        "document_id": "POST",
        "record_time": record_time,
        "document_title": title,
        "record_content": "术后病情平稳，继续观察。",
        "author_name": "赵医生",
    },)

    result, reduced = await _evaluate(RULE, materials)

    assert dict(result.customer_display_facts)[RULE]["surgeon_round_present"] is expected
    assert reduced.final_state.value == ("compliant" if expected else "non_compliant")
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_undated_course_does_not_fill_multiple_surgery_windows():
    materials = _materials()
    second = deepcopy(materials["surgery_record"][0])
    second.update(document_id="E2", surgery_end_time="2026-07-11 18:30:00+08")
    materials["surgery_record"] += (second,)
    materials["daily_course_record"] += ({"document_id": "CU", "record_content": "术后恢复中", "author_name": "李明"},)
    result, reduced = await _evaluate(RULE, materials)
    facts = dict(result.customer_display_facts)[RULE]
    assert reduced.final_state.value == "data_gap"
    assert facts["unresolved_course_time_events"] == ["E2"]
    assert facts["surgery_events"][1]["covered_postop_dates"] == []
    assert facts["surgery_events"][1]["surgeon_round_present"] is False


@pytest.mark.asyncio
async def test_undated_course_gap_survives_canonical_finalizer_and_fact_validation():
    rows = _materials()
    for row in rows["daily_course_record"]:
        row["record_time"] = None
    snapshot, materials, result, reduced = await _evaluate_selected((RULE,), rows)
    canonical = _canonical_extended_result(
        rule_id=RULE, snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "required_field_missing"
    facts = canonical["customer_display_facts"]
    assert facts["surgery_events"][0]["course_time_unresolved"] is True
    assert "unresolved_course_time_events" not in facts  # 内部事件ID不投影
    assert facts["covered_postop_dates"] == []
    assert "暂无法" in canonical["findings"]
    assert "缺少 2026" not in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_flag", ("true", 1, None, {}))
async def test_course_time_gap_fact_rejects_non_boolean_values(invalid_flag):
    from app.services.luxian_0609.postoperative_result_mapping import (
        safe_postoperative_customer_display_facts,
    )

    result, _ = await _evaluate(RULE, _materials())
    raw = deepcopy(dict(result.customer_display_facts)[RULE])
    raw["surgery_events"][0]["course_time_unresolved"] = invalid_flag
    assert safe_postoperative_customer_display_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("submitter", ("李明", "赵医生", None))
async def test_explicit_body_signature_identifies_surgeon_without_submitter_requirement(submitter):
    """正文明确签名可确认术者，提交人为空或不同不影响身份读取。"""
    materials = _materials()
    for row in (*materials["daily_course_record"], *materials["senior_course_record"]):
        row.pop("author_name")
        row["record_content"] += "医师签名：李明"
        row["submitter"] = submitter
    result, reduced = await _evaluate(RULE, materials)
    facts = dict(result.customer_display_facts)[RULE]
    assert facts["surgeon_round_present"] is True
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("time_value,signer,expected", (
    ("2026-07-07 19:00:00", "李明", True),
    ("2026-07-08 18:30:00", "李明", True),
    ("2026-07-08 18:30:01", "李明", False),
    ("2026-07-07 19:00:00", "张甲", False),
))
async def test_surgeon_signed_first_postoperative_course_counts_within_24_hours(
    time_value, signer, expected,
):
    materials = _materials()
    for row in materials["daily_course_record"]:
        row["author_name"] = "赵医生"
    materials["postsurg_firstcourse_record"] = ({
        "document_id": "FIRST-POST", "record_time": time_value,
        "record_content": f"术后查房，患者恢复平稳。\n医师签名：{signer}",
        "submitter": "代录人",
    },)
    result, reduced = await _evaluate(RULE, materials)
    assert dict(result.customer_display_facts)[RULE]["surgeon_round_present"] is expected
    assert reduced.final_state.value == ("compliant" if expected else "non_compliant")


@pytest.mark.asyncio
@pytest.mark.parametrize("pre_time,post_time,expected_pre,expected_post", (
    # 只有首页手术日期：术前认前一日及当日，术后24小时认当日及次日。
    ("2026-07-07 07:30:00", "2026-07-08 09:00:00", True, True),
    ("2026-07-06 10:00:00", "2026-07-08 23:00:00", True, True),
    ("2026-07-05 10:00:00", "2026-07-09 08:00:00", False, False),
))
async def test_date_only_surgery_time_uses_calendar_day_windows(pre_time, post_time, expected_pre, expected_post):
    from datetime import datetime

    materials = _materials()
    materials["surgery_record"] = ()
    materials["mr_surgery"] = ({
        "document_id": "M1", "surgery_code": "47.0100", "surgery_name": "腹腔镜下阑尾切除术",
        "surgery_begin_datetime": datetime(2026, 7, 7), "surgeon": "李明",
    },)
    for row in materials["daily_course_record"]:
        row["author_name"] = "赵医生"
    materials["senior_course_record"] = (
        {"document_id": "PRE", "record_time": pre_time, "record_content": "术前查房，完善术前准备。",
         "author_name": "李明"},
        {"document_id": "POST", "record_time": post_time, "record_content": "术后查房，患者恢复平稳。",
         "author_name": "李明"},
    )
    result, _ = await _evaluate(RULE, materials)
    facts = dict(result.customer_display_facts)[RULE]
    assert facts["preop_surgeon_round_present"] is expected_pre
    assert facts["surgeon_round_present"] is expected_post


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", (
    # 用户口径（2026-10-22）：正文明确写“术者/主刀医师××查看患者”也算术者查房。
    ("术前李明主刀医师查看患者，术前准备已完善，待术。", True),
    ("主刀医师李明查看患者后指出：术前准备已完善。", True),
    ("手术由李明完成，术前准备已完善。", False),
    ("术前张伟主刀医师查看患者，术前准备已完善。", False),
))
async def test_preop_round_recognized_from_explicit_surgeon_mention_in_body(body, expected):
    materials = _materials()
    materials["senior_course_record"][0].update(author_name="赵医生", record_content=body)
    result, _ = await _evaluate(RULE, materials)
    assert dict(result.customer_display_facts)[RULE]["preop_surgeon_round_present"] is expected
