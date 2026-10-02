"""科室质量分析报告草稿：模型按节起草并引用本会话统计来源，Python 校验数值来源；不导出、不发布。"""
from __future__ import annotations

import re
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 比较/因果结论属于派生判断；小整数可能偶然命中来源数值，故按措辞单独拒绝。
_DERIVED_CLAIM = re.compile(r"(较|比)(上月|上期|上季|上年|去年|同期|前期|[一二三四五六七八九十\d]+月)|与.{0,10}(相比|比较)|环比|同比|增长率|下降率|改善|恶化|导致|归因于|所致")
_NEGATION = re.compile(r"未|不|无|没有|并非|避免")
_SENTENCE = re.compile(r"[^。；;！!？?\n]+")
REPORT_NOTE = "报告草稿：仅依据本会话已读取的正式统计来源起草，数值逐项核对来源；不是正式质量报告，不含因果结论，导出或发布须走既有报告流程。"


class ComposeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=40)
    # 正文为纯文本，可用换行分段；嵌套对象数组对模型不稳定，故不采用分节对象。
    body: str = Field(min_length=1, max_length=1500)
    source_ids: list[str] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def strip(self):
        self.title, self.body = self.title.strip(), self.body.strip()
        if not self.title or not self.body:
            raise ValueError("标题和正文不能为空")
        return self


def numbers(text: str) -> set[str]:
    """按数值比较：09 与 9、1.50 与 1.5 视为同一数，避免日期等格式差异误拒。"""
    return {str(Decimal(value).normalize()) if "." in value else str(int(value)) for value in _NUMBER.findall(text)}


def validate_report(report: ComposeReport, sources: dict[str, dict]) -> None:
    """正文数值须出现在所引正式来源中；比较/因果措辞一律拒绝。"""
    if not sources:
        raise HTTPException(422, "本会话尚未读取统计或趋势来源，请先读取后再起草报告")
    # 按句判断；含否定的说明（如“未作环比计算”）不视为比较结论。
    if any(_DERIVED_CLAIM.search(sentence) and not _NEGATION.search(sentence) for sentence in _SENTENCE.findall(report.title + "\n" + report.body)):
        raise HTTPException(422, "正文含比较、变化或因果结论；报告草稿只列各来源原值，不计算差值或推断原因")
    unsupported = numbers(report.title + report.body) - numbers("\n".join(source["text"] for source in sources.values()))
    if unsupported:
        listed = "、".join(sorted(unsupported, key=float)[:6])
        raise HTTPException(422, f"正文含来源未出现的数值：{listed}（如自行计算的比例、合计或差值，或病例标识），请删除或改为来源原值")


def report_card_text(report: ComposeReport, sources: dict[str, dict]) -> str:
    lines = [REPORT_NOTE, "", report.title, "", report.body, "", "来源与口径："]
    for index, source in enumerate(sources.values(), 1):
        lines.append(f"{index}. {source['title']}")
        if source.get("locator"):
            lines.append(f"   {source['locator'].splitlines()[0]}")
    lines.extend(["", "数据限制：统计读取当前每份病例最新权威保存结果并按质控完成时间筛选，不是期间历史快照；已评价数量含未执行和不适用，不是执行覆盖率；未验证各期规则版本相同。"])
    return "\n".join(lines)