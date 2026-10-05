"""参考修改草稿的事实投影与校验；模型只起草，Python 校验来源，不写病历、不改保存建议。"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from unicodedata import normalize
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


EXCERPT_LIMIT = 5
EXCERPT_CHARS = 300
CONCLUSION_CHARS = 600
DRAFT_NOTE = "参考草稿：仅依据本次已读取的保存证据摘录起草，不替代正式保存建议；复制或采用草稿不等于整改完成，需医生核对原文后在病历系统中自行书写。"
PLACEHOLDER_PREFIX = "待医生补充"
# 不拆分小数、符号及科学计数；Decimal比较避免浮点舍入。
_NUMBER = re.compile(r"[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?")
_DATE = re.compile(r"(?<!\d)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日|(?!\d))")
_TIME = re.compile(r"(?<!\d)(\d{1,2})[:时](\d{1,2})(?:[:分](\d{1,2})秒?|分)?(?!\d)")
_VALUE = re.compile(f"(?P<date>{_DATE.pattern})|(?P<time>{_TIME.pattern})|(?P<number>{_NUMBER.pattern})")


def _without_dates(text: str) -> tuple[str, set[tuple]]:
    text = normalize("NFKC", text).replace("−", "-")
    dates = set()
    def take(kind):
        def replace(match):
            dates.add((kind, *(int(value) if value is not None else 0 for value in match.groups())))
            return " "
        return replace
    return _TIME.sub(take("time"), _DATE.sub(take("date"), text)), dates


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise HTTPException(422, "草稿含无法核验的数值，请保留来源原文或标为待医生补充") from exc


def _numbers(text: str) -> set:
    remaining, dates = _without_dates(text)
    return dates | {("number", _decimal(value)) for value in _NUMBER.findall(remaining)}


def _source_quote(text: str) -> str:
    """完整摘录比较：值归一化后仍保留其字段、单位与相邻上下文。"""
    text = normalize("NFKC", text).replace("−", "-")
    def replace(match):
        raw = match.group()
        if match.lastgroup == "date":
            return "⟦日期:" + repr(tuple(int(v) for v in _DATE.fullmatch(raw).groups())) + "⟧"
        if match.lastgroup == "time":
            return "⟦时间:" + repr(tuple(int(v or 0) for v in _TIME.fullmatch(raw).groups())) + "⟧"
        # 不用Decimal.normalize()，避免默认精度截断长数值。
        sign, digits, exponent = _decimal(raw).as_tuple()
        digits = list(digits)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        return "⟦数值:" + repr((sign if digits else 0, tuple(digits), exponent if digits else 0)) + "⟧"
    return re.sub(r"\s+", "", _VALUE.sub(replace, text)).strip().rstrip("。")


_PLACEHOLDER_LEAD = re.compile(r"^(?:[\s（(【\[]*待医生补充[\s）)】\]：:，,]*)+")


class DraftSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["fact", "placeholder"]
    text: str = Field(min_length=1, max_length=200)
    evidence_positions: list[int] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def check_kind(self):
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("草稿段落不能为空")
        if self.kind == "fact" and not self.evidence_positions:
            raise ValueError("事实段必须引用已保存证据序号")
        if self.kind == "placeholder" and self.evidence_positions:
            raise ValueError("待补充段不能引用证据")
        return self


class ComposeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_id: str = Field(min_length=1, max_length=200)
    segments: list[DraftSegment] = Field(min_length=1, max_length=6)


def draft_evidence(evidence, conclusion=None) -> list[dict]:
    """序号0为正式保存结论原文，其后为前若干条保存摘录并截断；不读取当前文书全文。"""
    rows = [row for row in evidence if isinstance(row, dict)] if isinstance(evidence, list) else []
    projected = []
    if isinstance(conclusion, str) and conclusion.strip():
        projected.append({"evidence_position": 0, "source_type": "saved_conclusion", "record_time": None,
                          "excerpt": conclusion[:CONCLUSION_CHARS]})
    for position, row in enumerate(rows[:EXCERPT_LIMIT], 1):
        excerpt = row.get("evidence_excerpt")
        projected.append({
            "evidence_position": position,
            "source_type": row.get("source_type") if isinstance(row.get("source_type"), str) else None,
            "record_time": row.get("record_time") if isinstance(row.get("record_time"), str) else None,
            "excerpt": excerpt[:EXCERPT_CHARS] if isinstance(excerpt, str) else None,
        })
    return projected


def require_draftable(issue: dict) -> dict:
    reference = issue["references"][0]
    if reference.get("status") != "non_compliant":
        raise HTTPException(422, "仅已保存为不合规的问题可生成参考草稿；资料不足等状态需先核对资料，不能据此起草补写内容")
    return reference


def validate_segments(segments: list[DraftSegment], evidence: list[dict], suggestion: str | None = None) -> None:
    """事实段的数字（时间、剂量、次数等）须出现在所引来源中；待补充段只可出现正式建议或来源已有的数值（如时限）。"""
    by_position = {row["evidence_position"]: row for row in evidence}
    known = set(_numbers("\n".join(filter(None, [suggestion, *(row.get("excerpt") for row in evidence), *(row.get("record_time") for row in evidence)]))))
    for index, segment in enumerate(segments, 1):
        numbers = _numbers(segment.text)
        if segment.kind == "placeholder":
            if any(number not in known for number in numbers):
                raise HTTPException(422, f"第{index}段待补充内容含正式建议和来源均未出现的时间或数值，应留给医生核实后填写")
            continue
        missing = [position for position in segment.evidence_positions if position not in by_position]
        if missing:
            raise HTTPException(422, f"第{index}段引用了不存在的证据序号")
        source = "\n".join(filter(None, [part for position in segment.evidence_positions
                                          for part in (by_position[position].get("excerpt"), by_position[position].get("record_time"))]))
        source_numbers = set(_numbers(source))
        unsupported = [number for number in numbers if number not in source_numbers]
        if unsupported:
            raise HTTPException(422, f"第{index}段含所引证据未出现的数值，请改为待医生补充")
        if numbers:
            # record_time是文书元数据，不能作为正文中的给药/检查时间。
            quotes = [by_position[position].get("excerpt") for position in segment.evidence_positions]
            if not any(isinstance(quote, str) and _source_quote(segment.text) == _source_quote(quote) for quote in quotes):
                raise HTTPException(422, f"第{index}段含数值或日期时间，须完整引用单条来源摘录（保留字段、单位与上下文），不能拆句拼接；无法确认时请改为待医生补充")



def draft_card_text(reference: dict, segments: list[DraftSegment]) -> str:
    body = []
    for segment in segments:
        if segment.kind == "fact":
            marks = "、".join("保存结论" if position == 0 else f"保存证据{position}" for position in segment.evidence_positions)
            body.append(f"{segment.text}［依据{marks}］")
        else:
            # 模型可能自带“（待医生补充）”等前缀，统一去除后再加一次。
            text = _PLACEHOLDER_LEAD.sub("", segment.text).strip() or segment.text
            body.append(f"【{PLACEHOLDER_PREFIX}：{text}】")
    lines = [DRAFT_NOTE, "", "草稿：", *body, "", "正式保存建议（原文，未改动）：", reference.get("suggestion") or "保存结果未提供建议"]
    return "\n".join(lines)
