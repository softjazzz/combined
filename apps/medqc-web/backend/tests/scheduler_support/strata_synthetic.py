"""只含合成资料的实际 Prompt 生产者盘点，无网络或临床结果生成。"""


def build_requests():
    from app.services.luxian_0609.exam_lab_fact_extraction import (
        build_exam_lab_fact_prompt, build_exam_lab_text_projection,
    )
    from app.services.luxian_0609 import exam_finding_analysis, exam_result_record_check

    projection = build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "SYNTHETIC-EX-1", "exam_name": "胸部CT平扫",
                         "exam_time": "2026-01-02 10:30:00", "report_time": "2026-01-02 11:30:00",
                         "exam_conclusion": "右肺下叶占位，考虑恶性可能。"},),
        "daily_course_record": (
            {"record_time": "2026-01-02 09:00:00", "record_content": "拟完善胸部CT了解肺部情况。"},
            {"record_time": "2026-01-02 15:00:00", "record_content": "胸部CT示右肺下叶占位，拟进一步检查。"},
            {"record_time": "2026-01-03 09:00:00", "record_content": "一般情况可，继续观察。"},
        ),
    })
    refs = tuple(sorted(projection.course_times))
    targets = {1: ("右肺下叶占位，考虑恶性可能。", refs)}
    original = exam_result_record_check._prompt(projection, targets)
    retry = exam_result_record_check._retry_prompt(original, ValueError("synthetic"), {})
    finding = exam_finding_analysis._prompt(projection, targets)
    partial = exam_result_record_check._prompt(projection, {1: (targets[1][0], refs[:1])})
    primary = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"), projection=projection,
    )
    return (
        ("result_original", "case-a", original),
        ("identical_input_control", "case-a", original),
        ("real_retry_builder", "case-a", retry),
        ("different_finding_projection", "case-a", finding),
        ("different_candidate_scope", "case-a", partial),
        ("native_primary_extraction", "case-a", primary),
        ("same_text_other_case", "case-b", original),
    )
