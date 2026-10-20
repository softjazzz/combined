"""050人工全文标签；未知全文即fixture_error，不从生产判定反推答案。"""

import json


def _fact(quote, problem, *, state="unresolved", temporal="current", polarity="affirmed",
          scope="diagnosis", association="explicit"):
    fact = dict(scope=scope, diagnosis_state=state, temporal_scope=temporal,
                polarity=polarity, association=association, quote=quote, problem_quote=problem)
    if state in {"unresolved", "undetermined"} or (state == "explicit" and polarity == "negated"):
        # 既有人工标签提供完整逐字状态依据，不改变原有语义和预期。
        fact["uncertainty_quote"] = quote
    return fact


# 仅以完整正文精确查表。标签由原人工语义/冻结预期标注，不使用子串规则。
MANUAL_DIAGNOSIS_SCOPE_FACTS = {
    "患者发热原因待查，当前诊断为社区获得性肺炎。": (
        _fact("患者发热原因待查", "发热原因", scope="local_problem"),
        _fact("当前诊断为社区获得性肺炎。", "社区获得性肺炎", state="explicit"),
    ),
    "发热原因待查。": (_fact("发热原因待查。", "发热原因", scope="local_problem"),),
    "当前诊断已明确。": (_fact("当前诊断已明确。", "诊断", state="explicit"),),
    "入院第7天，发热原因待查，目前诊断仍不明确。": (
        _fact("发热原因待查", "发热原因", scope="local_problem"),
        _fact("目前诊断仍不明确。", "诊断"),
    ),
    "患者发热原因待查，当前诊断为社区获得性肺炎，继续抗感染治疗。": (
        _fact("患者发热原因待查", "发热原因", scope="local_problem"),
        _fact("当前诊断为社区获得性肺炎", "社区获得性肺炎", state="explicit"),
    ),
    "当前诊断为社区获得性肺炎，继续抗感染治疗。": (
        _fact("当前诊断为社区获得性肺炎", "社区获得性肺炎", state="explicit"),
    ),
    "目前诊断仍不明确。": (_fact("目前诊断仍不明确。", "诊断"),),
    "目前诊断已明确。": (_fact("目前诊断已明确。", "诊断", state="explicit"),),
    "目前不存在诊断不明确的问题。": (
        _fact("目前不存在诊断不明确的问题。", "诊断", polarity="negated"),
    ),
    "如后续诊断不明确，拟进行疑难讨论。": (
        _fact("如后续诊断不明确，拟进行疑难讨论。", "诊断", temporal="future_conditional"),
    ),
    "诊断不明确的问题，目前并不存在。": (
        _fact("诊断不明确的问题，目前并不存在。", "诊断", polarity="negated"),
    ),
    "拟在后续诊断仍不明确时开展疑难病例讨论。": (
        _fact("拟在后续诊断仍不明确时开展疑难病例讨论。", "诊断", temporal="future_conditional"),
    ),
    "入院时发热病因诊断不明确；目前已明确为肺炎，发热病因问题已解决。": (
        _fact("入院时发热病因诊断不明确", "发热病因", temporal="historical"),
        _fact("目前已明确为肺炎，发热病因问题已解决。", "发热病因", state="explicit"),
    ),
    "入院时发热病因诊断不明确；目前该发热病因仍不明确。": (
        _fact("入院时发热病因诊断不明确", "发热病因", temporal="historical"),
        _fact("目前该发热病因仍不明确。", "发热病因"),
    ),
    "肺炎诊断已明确；贫血病因目前仍不明确。": (
        _fact("肺炎诊断已明确", "肺炎", state="explicit"),
        _fact("贫血病因目前仍不明确。", "贫血病因"),
    ),
    "入院时贫血病因诊断不明确，现已明确为缺铁性贫血；目前胸腔积液病因仍不明确。": (
        _fact("入院时贫血病因诊断不明确", "贫血病因", temporal="historical"),
        _fact("现已明确为缺铁性贫血", "缺铁性贫血", state="explicit"),
        _fact("目前胸腔积液病因仍不明确。", "胸腔积液病因"),
    ),
    "肺炎诊断已明确；贫血病因也已明确，目前无诊断不明确问题。": (
        _fact("肺炎诊断已明确", "肺炎", state="explicit"),
        _fact("贫血病因也已明确", "贫血病因", state="explicit"),
        _fact("目前无诊断不明确问题。", "诊断", polarity="negated"),
    ),
    "不能说发热病因不存在诊断不明确的问题；目前发热病因仍待明确。": (
        _fact("不能说发热病因不存在诊断不明确的问题", "发热病因"),
        _fact("目前发热病因仍待明确。", "发热病因"),
    ),
    "目前肺炎诊断明确，但该患者诊疗方案难以确定。": (
        _fact("目前肺炎诊断明确", "肺炎", state="explicit"),
        _fact("但该患者诊疗方案难以确定。", "诊疗方案", state="undetermined", scope="treatment_plan"),
    ),
    # 转科/讨论触发边界用例（test_luxian_0609_transfer_discussion_trigger_boundaries）。
    "入院时诊断不明确，现已明确诊断为细菌性肺炎，诊疗方案已确定。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("现已明确诊断为细菌性肺炎", "细菌性肺炎", state="explicit"),
        _fact("诊疗方案已确定", "诊疗方案", state="explicit", scope="treatment_plan"),
    ),
    "既往诊断不明确，目前诊断已明确。": (
        _fact("既往诊断不明确", "诊断", temporal="historical"),
        _fact("目前诊断已明确", "诊断", state="explicit"),
    ),
    "目前诊断仍不明确，诊疗方案难以确定。": (
        _fact("目前诊断仍不明确", "诊断"),
        _fact("诊疗方案难以确定", "诊疗方案", state="undetermined", scope="treatment_plan"),
    ),
    "入院时诊断不明确，目前诊断仍不明确。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("目前诊断仍不明确", "诊断"),
    ),
    "入院时诊断不明确，现已明确诊断为肺炎。但新的发热诊断仍不明确。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("现已明确诊断为肺炎", "肺炎", state="explicit"),
        _fact("但新的发热诊断仍不明确", "发热"),
    ),
    "入院时诊断不明确，现已明确诊断为肺炎。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("现已明确诊断为肺炎", "肺炎", state="explicit"),
    ),
    "诊断不明确。": (_fact("诊断不明确。", "诊断"),),
    "入院时诊断不明确，至今发热原因未查明，治疗方案仍难以确定。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("至今发热原因未查明", "发热原因"),
        _fact("治疗方案仍难以确定", "治疗方案", state="undetermined", scope="treatment_plan"),
    ),
    "入院时诊断不明确，至今发热原因未查明，治疗方案仍难以确定。另一疾病目前已明确诊断为高血压。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("至今发热原因未查明", "发热原因"),
        _fact("治疗方案仍难以确定", "治疗方案", state="undetermined", scope="treatment_plan"),
        _fact("另一疾病目前已明确诊断为高血压", "高血压", state="explicit"),
    ),
    # 业务已确认：历史未明确问题未写明已解决时延续为当前未明确；另一疾病明确不算解决。
    "入院时诊断不明确，另一疾病目前已明确诊断为高血压。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("入院时诊断不明确", "诊断"),
        _fact("另一疾病目前已明确诊断为高血压", "高血压", state="explicit"),
    ),
    "入院时诊断不明确，目前已明确诊断为另一疾病高血压。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("入院时诊断不明确", "诊断"),
        _fact("目前已明确诊断为另一疾病高血压", "高血压", state="explicit"),
    ),
    "入院时诊断不明确，现已明确诊断为肺炎。但至今发热原因未查明，治疗方案仍难以确定。": (
        _fact("入院时诊断不明确", "诊断", temporal="historical"),
        _fact("现已明确诊断为肺炎", "肺炎", state="explicit"),
        _fact("但至今发热原因未查明", "发热原因"),
        _fact("治疗方案仍难以确定", "治疗方案", state="undetermined", scope="treatment_plan"),
    ),
    "肺炎与胸腔积液曾均待明确。目前其中一项已明确，另一项尚未明确。": (
        _fact("肺炎与胸腔积液曾均待明确。", "肺炎", temporal="historical"),
        _fact("肺炎与胸腔积液曾均待明确。", "胸腔积液", temporal="historical"),
        _fact("目前其中一项已明确，另一项尚未明确。", "", association="ambiguous"),
        _fact("目前其中一项已明确", "", state="explicit", association="ambiguous"),
    ),
}


class FrozenDiagnosisScopeClient:
    def __init__(self, facts=None):
        self.facts = MANUAL_DIAGNOSIS_SCOPE_FACTS if facts is None else facts
        self.calls = []
        self.fixture_error = None

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        try:
            assert len(self.calls) == 1, "050应为单次完整抽取"
            assert kwargs["allow_length_retry"] is False
            assert type(kwargs["max_completion_tokens"]) is int and kwargs["max_completion_tokens"] > 0
            inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
            documents = []
            for document in inputs["documents"]:
                labels = self.facts[document["body"]]
                documents.append(dict(row_index=document["row_index"], coverage="complete",
                                      assertions=[dict(label) for label in labels]))
            return {"finish_reason": "stop", "content": json.dumps({
                "schema_version": "lx0609-diagnosis-scope-facts-v1", "documents": documents},
                ensure_ascii=False),
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        except Exception as error:
            self.fixture_error = repr(error)
            raise
