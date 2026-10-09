"""055 人工全文语义标签替身；不调用生产判定或按词表生成答案。"""

import json


# 每项只按完整正文精确查表。regimen 是已完成但未点名药物的抗菌疗效评价，
# 不在这里把它分配给某个医嘱事件；单/多事件归属由程序合同决定。
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
    "已给予美罗培南抗感染，未出现不良反应。",
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
# None键表示人工标注该全文对任意目标均无评价/均是未点名方案评价，
# 并非未知全文或未知目标的默认答案。
MANUAL_EFFECT_FACTS = {
    **{body: {None: ("regimen", body, "")} for body in _REGIMEN_BODIES},
    **{body: {None: ("absent", "", "")} for body in _ABSENT_BODIES},
    "美罗培南疗效评价：抗感染治疗有效，体温下降。": {
        "美罗培南": ("present", "美罗培南疗效评价：抗感染治疗有效，体温下降。", "美罗培南"),
        "青霉素": ("absent", "", ""),
        "万古霉素": ("absent", "", ""),
    },
    "美罗培南疗效评价：抗感染治疗有效。": {
        "美罗培南": ("present", "美罗培南疗效评价：抗感染治疗有效。", "美罗培南"),
        "万古霉素": ("absent", "", ""),
    },
    "美罗培南抗感染治疗效果评价：有效。": {
        "美罗培南": ("present", "美罗培南抗感染治疗效果评价：有效。", "美罗培南"),
    },
    "美罗培南抗感染治疗效果评价：体温下降。": {
        "美罗培南": ("present", "美罗培南抗感染治疗效果评价：体温下降。", "美罗培南"),
    },
    "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。": {
        "美罗培南": ("present", "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。", "美罗培南"),
        "万古霉素": ("present", "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。", "万古霉素"),
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
            assert len(self.calls) == 1, "055应为单次完整抽取"
            assert kwargs["allow_length_retry"] is False
            assert type(kwargs["max_completion_tokens"]) is int
            assert kwargs["max_completion_tokens"] > 0
            inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
            assertions = []
            for document in inputs["documents"]:
                labels = self.facts[document["content"]]
                for target in inputs["targets"]:
                    fact = labels[None] if None in labels else labels[target["name"]]
                    state, quote, target_quote = fact
                    assertions.append({"row_index": document["row_index"],
                        "target_index": target["target_index"], "state": state,
                        "quote": quote, "target_quote": target_quote})
            return {"finish_reason": "stop", "content": json.dumps({
                "schema_version": "lx0609-antimicrobial-effect-facts-v1",
                "assertions": assertions}, ensure_ascii=False),
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        except Exception as error:
            self.fixture_error = repr(error)
            raise
