"""055 人工全文语义标签替身；不调用生产判定或按词表生成答案。"""

import json


# 每项只按完整正文精确查表。两个维度分别标注；regimen 是已完成但未点名
# 药物的对应维度评价，不在这里把它分配给某个医嘱事件。
_REGIMEN_BODIES = (
    "抗菌药物效果评价：抗感染治疗有效，体温下降，白细胞降低。",
    "抗菌药物效果评价：抗感染治疗有效。",
    "抗菌药物效果评价：抗感染治疗有效，体温下降、白细胞下降。",
    "抗菌药物效果评价：抗感染治疗有效，CRP下降。",
    "抗感染治疗效果不佳，拟调整方案。",
    "抗感染治疗有效，继续原方案。",
)
_ABSENT_BODIES = (
    "患者重症感染，已在用药前留取血培养。经验性联合美罗培南和万古霉素覆盖耐药菌，记录启用及联合用药理由。",
    "既往效果评价：体温下降、白细胞下降。",
    "上级医师记录既往效果评价：CRP下降。",
    "复查白细胞、CRP较前下降。",
    "疼痛治疗效果佳，患者一般情况好转。",
    "镇痛治疗效果良好。",
    "拟使用美罗培南经验性抗感染治疗，患者拒绝，未实际给药。",
    "美罗培南未实际使用。",
    "给予美罗培南抗感染治疗。",
    "已予美罗培南静滴抗感染。",
    "拟给予美罗培南抗感染治疗。",
    "计划给予美罗培南抗感染治疗。",
    "建议给予美罗培南抗感染治疗。",
    "应给予美罗培南抗感染治疗。",
    "需给予美罗培南抗感染治疗。",
    "准备给予美罗培南抗感染治疗。",
    "待给予美罗培南抗感染治疗。",
    "计划今日给予美罗培南抗感染治疗。",
    "未给予美罗培南抗感染治疗。",
    "尚未实际给予美罗培南。",
    "并非已予美罗培南静滴。",
    "美罗培南医嘱取消，未实际给药。",
    "既往给予美罗培南抗感染治疗。",
    "拟给予美罗培南，随后已予美罗培南静滴抗感染。",
    "予以美罗培南静滴抗感染。",
    "予以美罗培南输注抗感染。",
    "已予以美罗培南静滴抗感染。",
    "未予以美罗培南静滴。",
    "拟予以美罗培南输注。",
    "未曾给予美罗培南。",
    "美罗培南取消，已使用阿莫西林抗感染。",
    "美罗培南取消后已使用阿莫西林抗感染。",
)


def _dimension(state, quote="", target_quote=""):
    return state, quote, target_quote


def _fact(effect, safety):
    return (*effect, *safety)


_ABSENT = _dimension("absent")
# None键表示人工标注该全文对任意目标均无评价/均是未点名方案评价，
# 并非未知全文或未知目标的默认答案。
MANUAL_EFFECT_FACTS = {
    **{body: {None: _fact(_dimension("regimen", body), _ABSENT)} for body in _REGIMEN_BODIES},
    **{body: {None: _fact(_ABSENT, _ABSENT)} for body in _ABSENT_BODIES},
    "已给予美罗培南抗感染，未出现不良反应。": {
        "美罗培南": _fact(
            _ABSENT,
            _dimension("present", "美罗培南抗感染，未出现不良反应", "美罗培南"),
        ),
    },
    "美罗培南疗效评价：抗感染治疗有效，体温下降。": {
        "美罗培南": _fact(_dimension("present", "美罗培南疗效评价：抗感染治疗有效，体温下降。", "美罗培南"), _ABSENT),
        "青霉素": _fact(_ABSENT, _ABSENT),
        "万古霉素": _fact(_ABSENT, _ABSENT),
    },
    "美罗培南疗效评价：抗感染治疗有效。": {
        "美罗培南": _fact(_dimension("present", "美罗培南疗效评价：抗感染治疗有效。", "美罗培南"), _ABSENT),
        "万古霉素": _fact(_ABSENT, _ABSENT),
    },
    "美罗培南抗感染治疗效果评价：有效。": {
        "美罗培南": _fact(_dimension("present", "美罗培南抗感染治疗效果评价：有效。", "美罗培南"), _ABSENT),
    },
    "美罗培南抗感染治疗效果评价：体温下降。": {
        "美罗培南": _fact(_dimension("present", "美罗培南抗感染治疗效果评价：体温下降。", "美罗培南"), _ABSENT),
    },
    "美罗培南疗效评价：有效；未记录用药安全性评价。": {
        "美罗培南": _fact(_dimension("present", "美罗培南疗效评价：有效", "美罗培南"), _ABSENT),
    },
    "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。": {
        "美罗培南": _fact(_dimension("present", "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。", "美罗培南"), _ABSENT),
        "万古霉素": _fact(_dimension("present", "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。", "万古霉素"), _ABSENT),
    },
    "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。": {
        "美罗培南": _fact(
            _dimension("present", "美罗培南疗效评价：有效", "美罗培南"),
            _dimension("present", "美罗培南疗效评价：有效；安全性评价：未见药物不良反应", "美罗培南"),
        ),
        "万古霉素": _fact(_ABSENT, _ABSENT),
    },
    "万古霉素疗效评价：有效；安全性评价：未见药物不良反应。": {
        "美罗培南": _fact(_ABSENT, _ABSENT),
        "万古霉素": _fact(
            _dimension("present", "万古霉素疗效评价：有效", "万古霉素"),
            _dimension("present", "万古霉素疗效评价：有效；安全性评价：未见药物不良反应", "万古霉素"),
        ),
    },
    "抗菌药物效果评价：抗感染治疗有效，体温下降，白细胞降低；安全性评价：未见药物不良反应。": {
        None: _fact(
            _dimension("regimen", "抗菌药物效果评价：抗感染治疗有效，体温下降，白细胞降低"),
            _dimension("regimen", "安全性评价：未见药物不良反应"),
        ),
    },
    "抗菌药物效果评价：抗感染治疗有效；安全性评价：未见药物不良反应。": {
        None: _fact(
            _dimension("regimen", "抗菌药物效果评价：抗感染治疗有效"),
            _dimension("regimen", "安全性评价：未见药物不良反应"),
        ),
    },
    "美罗培南疗效评价：抗感染治疗有效，体温下降；安全性评价：未见药物不良反应。": {
        "美罗培南": _fact(
            _dimension("present", "美罗培南疗效评价：抗感染治疗有效，体温下降", "美罗培南"),
            _dimension("present", "美罗培南疗效评价：抗感染治疗有效，体温下降；安全性评价：未见药物不良反应", "美罗培南"),
        ),
        "青霉素": _fact(_ABSENT, _ABSENT),
        "万古霉素": _fact(_ABSENT, _ABSENT),
    },
    "抗菌药物效果评价：抗感染治疗有效，体温下降、白细胞下降；安全性评价：未见药物不良反应。": {
        None: _fact(
            _dimension("regimen", "抗菌药物效果评价：抗感染治疗有效，体温下降、白细胞下降"),
            _dimension("regimen", "安全性评价：未见药物不良反应"),
        ),
    },
    "抗感染治疗效果不佳，拟调整方案；安全性评价未见药物不良反应。": {
        None: _fact(
            _dimension("regimen", "抗感染治疗效果不佳，拟调整方案"),
            _dimension("regimen", "安全性评价未见药物不良反应"),
        ),
    },
    "抗感染治疗有效，继续原方案；安全性评价未见药物不良反应。": {
        None: _fact(
            _dimension("regimen", "抗感染治疗有效，继续原方案"),
            _dimension("regimen", "安全性评价未见药物不良反应"),
        ),
    },
    "美罗培南抗感染治疗效果评价：有效；安全性评价未见药物不良反应。": {
        "美罗培南": _fact(
            _dimension("present", "美罗培南抗感染治疗效果评价：有效", "美罗培南"),
            _dimension("present", "美罗培南抗感染治疗效果评价：有效；安全性评价未见药物不良反应", "美罗培南"),
        ),
    },
    "美罗培南安全性评价：未见药物不良反应；未记录疗效评价。": {
        "美罗培南": _fact(
            _ABSENT,
            _dimension("present", "美罗培南安全性评价：未见药物不良反应", "美罗培南"),
        ),
    },
    "美罗培南疗效评价：有效；该药安全性评价归属不明确。": {
        "美罗培南": _fact(
            _dimension("present", "美罗培南疗效评价：有效", "美罗培南"),
            _dimension("unknown", "该药安全性评价归属不明确"),
        ),
    },
    "美罗培南安全性评价归属不明确。": {
        "美罗培南": _fact(
            _ABSENT,
            _dimension("unknown", "美罗培南安全性评价归属不明确", "美罗培南"),
        ),
    },
}


class FrozenAntimicrobialEffectClient:
    def __init__(self, facts=None):
        self.facts = MANUAL_EFFECT_FACTS if facts is None else facts
        self.calls = []
        self.fixture_error = None

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        try:
            assert len(self.calls) <= 2, "055最多首轮抽取和一次定向补查"
            assert kwargs["allow_length_retry"] is False
            assert kwargs["max_completion_tokens"] == 16384
            inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
            requested = {(item["row_index"], item["target_index"])
                         for item in inputs["requested_pairs"]}
            assertions = []
            for document in inputs["documents"]:
                labels = self.facts[document["content"]]
                for target in inputs["targets"]:
                    if (document["row_index"], target["target_index"]) not in requested:
                        continue
                    fact = labels[None] if None in labels else labels[target["name"]]
                    (effect_state, effect_quote, effect_target_quote,
                     safety_state, safety_quote, safety_target_quote) = fact
                    quotes = [quote for quote in (effect_quote, safety_quote) if quote]
                    if quotes:
                        start = min(document["content"].index(quote) for quote in quotes)
                        end = max(
                            document["content"].index(quote) + len(quote)
                            for quote in quotes
                        )
                        quote = document["content"][start:end]
                    else:
                        quote = ""
                    target_quote = (
                        target["name"]
                        if "present" in {effect_state, safety_state}
                        else effect_target_quote or safety_target_quote
                    )
                    assertions.append({"row_index": document["row_index"],
                        "target_index": target["target_index"],
                        "effect_state": effect_state, "safety_state": safety_state,
                        "quote": quote, "target_quote": target_quote})
            return {"finish_reason": "stop", "content": json.dumps({
                "schema_version": "lx0609-antimicrobial-effect-safety-facts-v2",
                "assertions": assertions}, ensure_ascii=False),
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        except Exception as error:
            self.fixture_error = repr(error)
            raise
