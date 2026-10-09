"""026 化疗给药原子事实协议的冻结替身；每段病程正文的事实由测试作者人工标注。"""
from __future__ import annotations

import json
import re

from app.services.luxian_0609.chemotherapy_administration_facts import DOSE_TOKEN_PATTERN

SCHEMA_VERSION = "lx0609-chemotherapy-administration-v1"


def fact(quote, *, action="administered", drug="奥沙利铂", dose=None, route=None, date=None, target=0):
    return {"target": target, "action": action, "quote": quote, "drug_quote": drug,
            "dose_quote": dose, "route_quote": route, "date_quote": date}


def given(date, dose, *, drug="奥沙利铂", route="静滴", lead="使用", sep=" ", action="administered"):
    """“{date} {lead}{drug}{sep}{dose} {route}” 形式的单次给药标注。"""
    quote = f"{date} {lead}{drug}{sep}{dose} {route}" if date else f"{lead}{drug}{sep}{dose} {route}"
    return fact(quote, action=action, drug=drug, dose=dose, route=route, date=date or None)


# 自动标注只用于直白的实际给药陈述；出现任何非实施/计划/否定/改量语义的字样一律拒绝，
# 必须由测试作者人工标注。它只替代机械抄写，不替代语义判断。
_NON_ADMINISTERED_WORDING = re.compile(
    r"拟|计划|准备|预计|下次|改为|改用|调整为|未|没有|无法|暂停|暂缓|停用|停止|取消|撤销|作废|拒绝|延期|推迟|若|如|待|考虑"
)
_SENTENCE = re.compile(r"[^。；;！？\n]+")
_DATE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?|今日|当日")


def auto_administered_facts(body, target_names, routes=("静滴", "静推", "口服", "皮下注射", "肌注", "静脉滴注")):
    facts = []
    for match in _SENTENCE.finditer(body):
        sentence = match.group().strip()
        names = [(index, name) for index, name in enumerate(target_names) if name in sentence]
        if not names:
            continue
        doses = DOSE_TOKEN_PATTERN.findall(sentence)
        if len(names) != 1 or len(doses) > 1 or re.search(r"昨日|前日|明日|次日|后日", sentence) or _NON_ADMINISTERED_WORDING.search(
            _DATE.sub("", sentence).replace("未见", "").replace("无不良", "")
        ):
            raise AssertionError("需人工标注的化疗病程句：" + sentence)
        index, name = names[0]
        if sentence.count(name) != 1 or body.count(sentence) != 1:
            raise AssertionError("需人工标注的化疗病程句：" + sentence)
        dates = _DATE.findall(sentence)
        route = next((item for item in routes if sentence.count(item) == 1), None)
        dose = None
        if doses:
            dose_match = DOSE_TOKEN_PATTERN.search(sentence)
            start = dose_match.start()
            # 保留紧贴剂量前的正负号，供程序核对完整剂量。
            while start > 0 and sentence[start - 1] in "+- ":
                start -= 1
            dose = sentence[start:dose_match.end()].strip()
            if sentence.count(dose) != 1:
                raise AssertionError("需人工标注的化疗病程句：" + sentence)
        facts.append(fact(sentence, drug=name, dose=dose, route=route,
                          date=dates[0] if len(dates) == 1 and sentence.count(dates[0]) == 1 else None,
                          target=index))
    return tuple(facts)


class FrozenChemotherapyAdministrationClient:
    """按正文精确查人工标注；未标注正文仅在 auto=True 时尝试受限自动标注，否则报错。"""

    def __init__(self, annotations=None, *, coverage=None, auto=False, delegate=None):
        self.annotations = dict(annotations or {})
        self.coverage = dict(coverage or {})
        self.auto = auto
        # 其他规则的提示词交给原测试客户端处理。
        self.delegate = delegate
        self.calls = []

    async def generate(self, prompt, **kwargs):
        if f"schema_version={SCHEMA_VERSION}" not in prompt and self.delegate is not None:
            return await self.delegate.generate(prompt)
        self.calls.append(kwargs)
        assert f"schema_version={SCHEMA_VERSION}" in prompt
        assert kwargs == {"max_completion_tokens": 3072, "allow_length_retry": False}
        targets = [item["drug_name"] for item in json.loads(prompt.split("TARGET_DRUGS=", 1)[1].split("\n", 1)[0])]
        documents = json.loads(prompt.split("INPUT_JSON=", 1)[1])["documents"]
        output = []
        for doc in documents:
            if doc["body"] in self.annotations:
                facts = list(self.annotations[doc["body"]])
            else:
                assert self.auto, "未人工标注的化疗病程正文：" + doc["body"]
                facts = list(auto_administered_facts(doc["body"], targets))
            output.append({"document_ref": doc["document_ref"],
                           "coverage": self.coverage.get(doc["body"], "complete"),
                           "facts": facts})
        content = json.dumps({"schema_version": SCHEMA_VERSION, "documents": output}, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


D = "2026-04-26"
# 原始冻结 26 例中的全部病程正文。
FROZEN_026_ANNOTATIONS = {
    f"{D} 使用奥沙利铂 {dose} 静滴。": (given(D, dose),)
    for dose in ("130mg", "+130mg", "0.13g", "1,130mg", "1130mg", "130.0mg", "130毫克",
                 "130mg·m⁻²", "130mg/m²", "130mg／m²")
}
FROZEN_026_ANNOTATIONS.update({
    f"{D} 使用奥沙利铂130mg 静滴。": (given(D, "130mg", sep=""),),
    f"{D} 使用奥沙利铂 130mg d1 静滴。": (
        fact(f"{D} 使用奥沙利铂 130mg d1 静滴", dose="130mg", route="静滴", date=D),),
    f"{D} 使用奥沙利铂 体表面积1.7，130mg 静滴。": (
        fact(f"{D} 使用奥沙利铂 体表面积1.7，130mg 静滴", dose="130mg", route="静滴", date=D),),
    f"{D} 使用奥沙利铂 d1，130mg 静滴。": (
        fact(f"{D} 使用奥沙利铂 d1，130mg 静滴", dose="130mg", route="静滴", date=D),),
    f"{D} 使用奥沙利铂 L-OHP130mg 静滴。": (
        fact(f"{D} 使用奥沙利铂 L-OHP130mg 静滴", dose="130mg", route="静滴", date=D),),
    "今日使用奥沙利铂130mg 静滴。": (
        fact("今日使用奥沙利铂130mg 静滴", dose="130mg", route="静滴", date="今日"),),
    # 仅计划：不能证明已实施。
    f"{D} 拟给予奥沙利铂130mg 静滴。": (given(D, "130mg", lead="拟给予", sep="", action="planned"),),
    # 明确未给。
    f"{D} 未给予奥沙利铂130mg 静滴。": (given(D, "130mg", lead="未给予", sep="", action="withheld"),),
    # 只抽目标化疗药；昂丹司琼不是目标药，其剂量不得借用。
    f"{D} 使用奥沙利铂120mg 静滴。另予昂丹司琼130mg 静滴。": (given(D, "120mg", sep=""),),
    # 同篇实际 120mg 与计划改为 130mg 分为两条事实。
    f"{D} 使用奥沙利铂120mg 静滴。计划改为奥沙利铂130mg 静滴。": (
        given(D, "120mg", sep=""),
        fact("计划改为奥沙利铂130mg 静滴", action="planned", dose="130mg", route="静滴"),
    ),
})
