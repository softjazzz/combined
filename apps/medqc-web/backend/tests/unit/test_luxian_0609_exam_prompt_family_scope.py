from __future__ import annotations

from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
)


def _mixed_projection():
    return build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_type": "胸部CT",
                    "exam_time": "2026-09-12 08:00:00",
                    "report_time": "2026-09-12 12:00:00",
                    "exam_conclusion": "右肺结节",
                },
            ),
            "exam_item_report": (
                {
                    "exam_id": "EX-1",
                    "exam_item_name": "右肺",
                    "exam_result": "可见结节",
                },
            ),
            "labtest_master": (
                {
                    "test_id": "LAB-1",
                    "lab_type": "血培养",
                    "report_time": "2026-09-14 12:00:00",
                    "specimen": "血",
                },
            ),
            "labtest_item_report": (
                {
                    "test_id": "LAB-1",
                    "item_name": "血培养药敏",
                    "result": "检出金黄色葡萄球菌",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-09-11 20:00:00",
                    "record_content": "影像病程正文 FAMILY=culture 关键字仍应保留。",
                },
                {
                    "record_time": "2026-09-12 13:00:00",
                    "record_content": "影像结果病程正文。",
                },
                {
                    "record_time": "2026-09-13 12:30:00",
                    "record_content": "影像窗口外首份病程锚点。",
                },
                {
                    "record_time": "2026-09-14 13:00:00",
                    "record_content": "培养病程正文应隔离。",
                },
            ),
        }
    )


def _material_headers(prompt: str) -> list[str]:
    return [
        line.split("]", 1)[0]
        for line in prompt.splitlines()
        if line.startswith(("[EVENT_DOC=", "[CANDIDATE_DOC="))
    ]


def test_single_imaging_prompt_excludes_culture_material_but_keeps_course_allowlist():
    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-011",),
        projection=_mixed_projection(),
    )

    headers = _material_headers(prompt)
    assert headers
    assert all("|FAMILY=exam|" in header for header in headers)
    assert "影像病程正文 FAMILY=culture 关键字仍应保留" in prompt
    assert "影像窗口外首份病程锚点" in prompt
    assert "培养病程正文应隔离" not in prompt


def test_single_culture_prompt_excludes_imaging_material_but_keeps_culture_course():
    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-014",),
        projection=_mixed_projection(),
    )

    headers = _material_headers(prompt)
    assert headers
    assert all("|FAMILY=culture|" in header for header in headers)
    assert "培养病程正文应隔离" in prompt
    assert "影像结果病程正文" not in prompt
    assert "影像窗口外首份病程锚点" not in prompt


def test_mixed_prompt_keeps_both_requested_material_families():
    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-011", "LX0609-014"),
        projection=_mixed_projection(),
    )

    headers = _material_headers(prompt)
    assert any("|FAMILY=exam|" in header for header in headers)
    assert any("|FAMILY=culture|" in header for header in headers)
