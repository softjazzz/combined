"""LX0609 质控结果反馈演示版 DTO。

该模块只描述页面反馈的输入合同，不承载 Canonical 结果解释逻辑。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


FeedbackType = Literal["correct", "incorrect", "note"]
ExpectedStatus = Literal[
    "non_compliant",
    "compliant",
    "data_gap",
    "not_applicable",
    "evaluation_unknown",
    "not_executed",
]
FeedbackErrorCategory = Literal[
    "wrong_status",
    "wrong_reason",
    "wrong_evidence",
    "missing_data_read",
    "wrong_suggestion",
    "rule_definition",
    "other",
]


class QcResultFeedbackRequest(BaseModel):
    """演示账号对一条 Canonical 规则结果的当前反馈。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    root_job_id: str = Field(..., min_length=1, max_length=64)
    record_ref: str = Field(..., min_length=1, max_length=96)
    feedback_type: FeedbackType
    expected_status: Optional[ExpectedStatus] = None
    error_category: Optional[FeedbackErrorCategory] = None
    comment: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_feedback_contract(self) -> "QcResultFeedbackRequest":
        comment = (self.comment or "").strip()
        if self.feedback_type == "incorrect":
            if self.expected_status is None:
                raise ValueError("有误反馈必须选择期望结果")
            if self.error_category is None:
                raise ValueError("有误反馈必须选择错误类别")
            if not comment:
                raise ValueError("有误反馈必须填写说明")
        elif self.feedback_type == "note":
            if not comment:
                raise ValueError("补充说明必须填写内容")
            if self.expected_status is not None or self.error_category is not None:
                raise ValueError("补充说明不需要填写期望结果或错误类别")
        elif self.expected_status is not None or self.error_category is not None:
            raise ValueError("准确反馈不需要填写期望结果或错误类别")
        self.comment = comment or None
        return self


class QcResultFeedbackQuery(BaseModel):
    """按一份病历加载当前演示反馈。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    root_job_id: str = Field(..., min_length=1, max_length=64)
    record_ref: str = Field(..., min_length=1, max_length=96)
