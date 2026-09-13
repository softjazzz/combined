"""CT 纯引导操作项目的最窄报告边界。"""

import pytest

from app.services.luxian_0609.imaging_report_scope import is_guidance_only_imaging_rows


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([{"record_content": "CT引导下操作。"}], True),
        ([{"content": "  ct \n引导下操作；", "exam_type": " CT "}], True),
        ([{"exam_result": "CT引导下操作", "exam_name": "CT引导下操作"}], True),
        (
            [
                {"record_content": "", "exam_name": "CT"},
                {"impression": "CT引导下操作", "modality": "CT"},
            ],
            True,
        ),
        ([], False),
        ([{"exam_name": "CT"}], False),
        ([{"record_content": "", "exam_name": "CT引导下操作"}], False),
        ([{"record_content": "CT引导下操作", "impression": "腰椎骨折"}], False),
        ([{"record_content": "CT引导下操作", "abnormal_indicator": "异常"}], False),
        (
            [{"record_content": "CT引导下操作", "diagnose_based_on": "CT见椎体骨折"}],
            False,
        ),
        ([{"record_content": "CT引导下操作，未见异常"}], False),
        ([{"record_content": "CT引导下操作", "exam_name": "MRI"}], False),
        ([{"record_content": "CT引导下操作", "modality": "CT增强"}], False),
        ([{"result": "CT引导下操作", "exam_item_name": "介入操作"}], False),
        ([{"record_content": 123}], False),
        (
            [
                {"record_content": "CT引导下操作"},
                {"description": "右肺结节"},
            ],
            False,
        ),
        ([{"record_content": "   。；  "}], False),
    ],
)
def test_guidance_only_scope_has_a_strict_body_and_identity_boundary(rows, expected):
    assert is_guidance_only_imaging_rows(rows) is expected
