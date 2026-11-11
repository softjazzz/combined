"""027 出院后计划抽取的固定应答替身：只依据实际收到的出院记录作答，未登记材料立即失败。

FROZEN_DISCHARGE_PLAN_FACTS 由测试作者逐条人工标注（键为出院记录送模字段值，多字段以换行相接），
不调用产品分类器，也不从关键词推导答案。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.services.luxian_0609.discharge_plan_extraction import SCHEMA_VERSION

T, F, O = "tumor_treatment", "follow_up", "other"
DONE, PLANNED, COND, NOT, UNKNOWN = "inpatient_completed", "post_discharge_planned", "conditional", "not_planned", "unknown"

# 值：(review_state, ((kind, timing, quote, time_anchor), ...))
FROZEN_DISCHARGE_PLAN_FACTS: dict[str, tuple[str, tuple[tuple[str, str, str, str], ...]]] = {
    "出院记录中包含后续肿瘤治疗计划。": ("complete", ((T, PLANNED, "出院记录中包含后续肿瘤治疗计划", ""),)),
    "出院后继续肿瘤专科治疗计划。": ("complete", ((T, PLANNED, "出院后继续肿瘤专科治疗计划", "出院后"),)),
    "既往已完成化疗。建议门诊复查血常规。": ("complete", (
        (T, DONE, "既往已完成化疗", ""), (O, PLANNED, "建议门诊复查血常规", ""))),
    "出院后暂不化疗。": ("complete", ((T, NOT, "出院后暂不化疗", "出院后"),)),
    "出院后不建议化疗。": ("complete", ((T, NOT, "出院后不建议化疗", "出院后"),)),
    "出院后计划化疗，待病理明确后决定。": ("complete", ((T, COND, "出院后计划化疗，待病理明确后决定", "出院后"),)),
    "出院后无不适，建议化疗。": ("complete", ((T, PLANNED, "出院后无不适，建议化疗", "出院后"),)),
    "建议出院后辅助化疗，必要时根据耐受性调整剂量。": ("complete", (
        (T, PLANNED, "建议出院后辅助化疗", "出院后"),)),
    "出院后必要时化疗。": ("complete", ((T, COND, "出院后必要时化疗", "出院后"),)),
    "1.1周后电话咨询基因检测结果。随访方式:门诊随访周期:每1个月。": ("complete", (
        (F, PLANNED, "随访方式:门诊随访周期:每1个月", "每1个月"),)),
    "出院后暂不化疗，定期复查。": ("complete", (
        (T, NOT, "出院后暂不化疗", "出院后"), (F, PLANNED, "定期复查", ""))),
    "建议门诊复查血常规。": ("complete", ((O, PLANNED, "建议门诊复查血常规", ""),)),
    "如有不适门诊随访。": ("complete", ((F, COND, "如有不适门诊随访", ""),)),
    # test_round2_tumor_dose_discharge_boundaries：诊疗经过 + 出院医嘱
    "出院后继续化疗。": ("complete", ((T, PLANNED, "出院后继续化疗", "出院后"),)),
    "入院后继续化疗，治疗结束后病情好转出院。\n注意休息，加强营养。": ("complete", (
        (T, DONE, "入院后继续化疗，治疗结束后病情好转出院", ""),)),
    "住院期间继续化疗。\n注意休息。": ("complete", ((T, DONE, "住院期间继续化疗", ""),)),
    "既往曾建议化疗，本次已完成。\n注意休息。": ("complete", ((T, DONE, "既往曾建议化疗，本次已完成", ""),)),
    "入院后继续化疗。出院后继续化疗。\n定期随访。": ("complete", (
        (T, DONE, "入院后继续化疗", ""), (T, PLANNED, "出院后继续化疗", "出院后"), (F, PLANNED, "定期随访", ""))),
    "继续化疗，定期复查。": ("complete", ((T, PLANNED, "继续化疗", ""), (F, PLANNED, "定期复查", ""))),
    # test_luxian_0609_tumor_pathology_freeze：“出院后继续肿瘤专科治疗”是出院后肿瘤治疗安排；
    # “两周后门诊复查”未说明随访，属单次复查（other）。
    "出院后继续肿瘤专科治疗，并于两周后门诊复查。": ("complete", (
        (T, PLANNED, "出院后继续肿瘤专科治疗", "出院后"), (O, PLANNED, "并于两周后门诊复查", "两周后"))),
    # Codex 复审探针中的整段正文（单字段）
    "昨日返院化疗，今日好转出院。出院医嘱：注意休息。": ("complete", (
        (T, DONE, "昨日返院化疗，今日好转出院", "昨日"),)),
    "住院期间先予支持治疗，3天后行化疗，现好转出院。出院医嘱：注意休息。": ("complete", (
        (T, DONE, "住院期间先予支持治疗，3天后行化疗，现好转出院", "3天后"),)),
    # 台账 08-01-04 必要边界
    "住院期间先予支持治疗，3天后行化疗，现好转出院。\n注意休息。": ("complete", (
        (T, DONE, "住院期间先予支持治疗，3天后行化疗，现好转出院", "3天后"),)),
    "出院医嘱：3周后返院化疗。": ("complete", ((T, PLANNED, "出院医嘱：3周后返院化疗", "3周后"),)),
    # 原字段值不含“出院医嘱：”；程序仅以字段名称作上下文，引文只能取字段原值。
    "3周后返院化疗。": ("complete", ((T, PLANNED, "3周后返院化疗", "3周后"),)),
    "定期门诊随访，每3个月复查。": ("complete", ((F, PLANNED, "定期门诊随访，每3个月复查", "每3个月"),)),
    "昨日返院化疗，出院2周后返院化疗。": ("complete", (
        (T, DONE, "昨日返院化疗，出院2周后返院化疗", "昨日"),
        (T, PLANNED, "昨日返院化疗，出院2周后返院化疗", "出院2周后"))),
    "昨日返院化疗，今日好转出院。": ("complete", ((T, DONE, "昨日返院化疗，今日好转出院", "昨日"),)),
    "如有不适随诊。": ("complete", ((F, COND, "如有不适随诊", ""),)),
    "病情好转出院，注意休息。": ("complete", ()),
    "出院后的治疗安排另见专科意见。": ("unknown", ()),
    "下次返院化疗。": ("complete", ((T, UNKNOWN, "下次返院化疗", "下次"),)),
}


def discharge_plan_document_key(document: Mapping[str, Any]) -> str:
    """v2 送模文书按真实字段分列；替身以字段原值（换行相接）查冻结表，字段名称不参与。"""

    return "\n".join(item["text"] for item in document["fields"])


def _field_of(document: Mapping[str, Any], quote: str) -> str:
    """依据实际收到的材料定位引文所在字段；找不到时回第一个字段，交由产品校验拒收。"""

    return next((item["field"] for item in document["fields"] if quote in item["text"]),
                document["fields"][0]["field"])


class DischargePlanFactsClient:
    """mode: valid / invalid_quote / label_quote / wrong_field / wrong_document / missing_document / timeout。

    label_quote：把程序生成的字段名称拼进引文（如“出院医嘱：…”），模拟模型回引合成标签。
    wrong_field：引文注明到同一文书的另一个字段。
    """

    def __init__(self, table: Mapping[str, Any] | None = None, *, mode: str = "valid") -> None:
        self.table = dict(FROZEN_DISCHARGE_PLAN_FACTS if table is None else table)
        self.mode = mode
        self.prompts: list[str] = []
        self.fixture_error: str | None = None

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        if SCHEMA_VERSION not in prompt:
            raise AssertionError("discharge plan fixture received an unrelated prompt")
        self.prompts.append(prompt)
        if self.mode == "timeout":
            raise TimeoutError("synthetic discharge plan timeout")
        documents = json.loads(prompt.rsplit("\n", 1)[1])
        output = []
        for document in documents:
            key = discharge_plan_document_key(document)
            if key not in self.table:
                self.fixture_error = key
                raise AssertionError(f"unfrozen discharge plan material: {key!r}")
            review_state, arrangements = self.table[key]
            items = [{"field": _field_of(document, quote), "kind": kind, "timing": timing, "quote": quote,
                      "time_anchor": anchor}
                     for kind, timing, quote, anchor in arrangements]
            if self.mode == "invalid_quote" and items:
                items[0]["quote"] = items[0]["quote"] + "（改写）"
            if self.mode == "label_quote" and items:
                label = next(item["label"] for item in document["fields"] if item["field"] == items[0]["field"])
                items[0]["quote"] = f"{label}：{items[0]['quote']}"
            if self.mode == "wrong_field" and items:
                other = [item["field"] for item in document["fields"] if item["field"] != items[0]["field"]]
                if other:
                    items[0]["field"] = other[0]
            output.append({"local_doc_id": document["local_doc_id"], "review_state": review_state,
                           "arrangements": items})
        if self.mode == "wrong_document" and output:
            output[0]["local_doc_id"] = "doc_99"
        if self.mode == "missing_document":
            output = output[:-1]
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
                {"schema_version": SCHEMA_VERSION, "documents": output}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            "_api_time": 0.1,
        }


def frozen_documents(texts: Sequence[str]) -> list[str]:
    missing = [text for text in texts if text not in FROZEN_DISCHARGE_PLAN_FACTS]
    if missing:
        raise AssertionError(f"unfrozen discharge plan materials: {missing}")
    return list(texts)
