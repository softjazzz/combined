"""人工冻结的037测试事实；不读取生产判定、不作文本语义分类。"""
import json

PRE_SOURCE = "preane_surveil_record"
POST_SOURCE = "postane_surveil_record"
_PRE = {"asa_level": "ASA II级", "airway_assessment": "气道评估正常", "fasting_status": "禁食禁饮已核对", "anesthesia_history": "否认麻醉史", "risk_discussion": "已完成麻醉风险告知"}
_POST = {"consciousness_status": "神志清醒", "respiratory_status": "呼吸平稳", "circulatory_status": "循环稳定", "complication_assessment": "无麻醉并发症"}


def _case(*, pre=None, post=None):
    return {PRE_SOURCE: {**_PRE, **(pre or {})}, POST_SOURCE: {**_POST, **(post or {})}}


# 25原用例逐项答案，None明确表示absent。相同答案只复用人工常量。
CASE_FACTS = {
    "round2_complete": _case(),
    "round2_empty_labels": _case(pre={name: None for name in _PRE}, post={name: None for name in _POST}),
    "round2_invalid_time": _case(),
    "round2_without_event_keys": _case(),
    "n08_filled_heart_label": _case(),
    "n08_filled_followup_label": _case(),
    "n08_filled_heart_placeholder": _case(),
    "n08_filled_heart_value": _case(),
    "n08_missing_consciousness": _case(post={"consciousness_status": None}),
    "n08_missing_respiratory": _case(post={"respiratory_status": None}),
    "n08_missing_complication": _case(post={"complication_assessment": None}),
    "n08_adjacent_missing_consciousness": _case(post={"consciousness_status": None, "respiratory_status": "平稳"}),
    "n04_missing_history": _case(pre={"anesthesia_history": None}),
    "n04_missing_complication": _case(post={"complication_assessment": None}),
    "n04_missing_consciousness": _case(post={"consciousness_status": None}),
    "n04_missing_respiratory": _case(post={"respiratory_status": None}),
    "n04_missing_signature": _case(pre={"anesthetist_signature": None}),
    "n04_negative_none": _case(post={"consciousness_status": "清醒", "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "无"}),
    "n04_negative_no_abnormality": _case(post={"consciousness_status": "清醒", "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "未见异常"}),
    "n04_adjacent_space_missing_consciousness": _case(post={"consciousness_status": None, "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "无"}),
    "n04_adjacent_missing_consciousness": _case(post={"consciousness_status": None, "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "无"}),
    "n04_adjacent_missing_respiratory": _case(post={"consciousness_status": "清醒", "respiratory_status": None, "circulatory_status": "稳定", "complication_assessment": "无"}),
    "n04_adjacent_missing_complication": _case(post={"complication_assessment": None}),
    "n04_filled_no_separator": _case(post={"consciousness_status": "清醒", "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "未见异常"}),
    "n04_filled_space_separator": _case(post={"consciousness_status": "清醒", "respiratory_status": "平稳", "circulatory_status": "稳定", "complication_assessment": "未见异常"}),
    # 另三既有正式链用例的独立人工答案，明确联合呼吸循环片段可支持两项。
    "native_negated_assessments": _case(pre={"asa_level": None, "airway_assessment": None, "fasting_status": "已核对禁食禁饮", "risk_discussion": None}),
    "freeze_complete": _case(pre={"fasting_status": "禁食已确认", "anesthesia_history": "无麻醉史", "risk_discussion": "已评估麻醉风险"}, post={"consciousness_status": "神志清楚", "respiratory_status": "呼吸循环稳定", "circulatory_status": "呼吸循环稳定", "complication_assessment": "无恶心呕吐及麻醉并发症"}),
    "precise_complete": _case(pre={"fasting_status": "禁食已确认", "anesthesia_history": "无麻醉史", "risk_discussion": "已评估麻醉风险"}, post={"consciousness_status": "神志清楚", "respiratory_status": "呼吸循环稳定", "circulatory_status": "呼吸循环稳定"}),
}
N08_FILLED_CASES = {"心率：": "n08_filled_heart_label", "后续项目：": "n08_filled_followup_label", "心率：___": "n08_filled_heart_placeholder", "心率：80次/分": "n08_filled_heart_value"}
N08_EMPTY_CASES = {
    "术后意识：；呼吸平稳；循环稳定；无麻醉并发症。": "n08_missing_consciousness",
    "神志清醒；呼吸系统：；循环稳定；无麻醉并发症。": "n08_missing_respiratory",
    "神志清醒；呼吸平稳；循环稳定；术后并发症：": "n08_missing_complication",
    "术后意识：呼吸系统：平稳；循环稳定；无麻醉并发症。": "n08_adjacent_missing_consciousness",
}
N04_BLANK_CASES = {"anesthesia_history": "n04_missing_history", "complication_assessment": "n04_missing_complication", "consciousness_status": "n04_missing_consciousness", "respiratory_status": "n04_missing_respiratory"}
N04_NEGATIVE_CASES = {"无": "n04_negative_none", "未见异常": "n04_negative_no_abnormality"}
N04_ADJACENT_CASES = {
    "术后意识： 呼吸系统：平稳；循环：稳定；术后并发症：无": "n04_adjacent_space_missing_consciousness",
    "术后意识：呼吸系统：平稳；循环：稳定；术后并发症：无": "n04_adjacent_missing_consciousness",
    "术后意识清醒 呼吸系统：；循环：稳定；术后并发症：无": "n04_adjacent_missing_respiratory",
    "神志清醒；呼吸平稳；循环稳定；术后并发症： 备注：已访视": "n04_adjacent_missing_complication",
}
N04_FILLED_CASES = {"": "n04_filled_no_separator", " ": "n04_filled_space_separator"}


def read_sent_anesthesia_documents(prompt):
    """只按受控元数据/字符数读实际发送正文；旧JSON用于固定原版红对照。"""
    tail = prompt.split("\nINPUT_JSON=", 1)[1]
    encoded = tail.split("\n", 1)[0]
    documents = json.loads(encoded)["documents"]
    if all("body" in doc for doc in documents):
        return documents
    cursor = len(encoded)
    for doc in documents:
        spans = {}
        for span_id, count in doc["span_char_counts"].items():
            begin = f"\nSPAN_BEGIN {span_id}\n"
            end = f"\nSPAN_END {span_id}\n"
            assert tail.startswith(begin, cursor)
            start = cursor + len(begin)
            assert type(count) is int and count >= 0
            stop = start + count
            assert tail.startswith(end, stop)
            spans[span_id] = tail[start:stop]
            cursor = stop + len(end)
        body = "".join(spans.values())
        assert type(doc["body_char_count"]) is int and doc["body_char_count"] == len(body)
        doc["body"], doc["spans"] = body, spans
    assert cursor == len(tail)
    return documents


class ExplicitAnesthesiaFactClient:
    def __init__(self, case):
        self.facts = CASE_FACTS[case]
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        assert len(self.calls) == 1
        assert kwargs["allow_length_retry"] is False
        assert 0 < kwargs["max_completion_tokens"] <= 4096
        documents = read_sent_anesthesia_documents(prompt)
        assert len(documents) == 2
        assert {doc["source_type"] for doc in documents} == {PRE_SOURCE, POST_SOURCE}
        items = []
        for doc in documents:
            fields = {}
            for name in doc["required_fields"]:
                quote = self.facts[doc["source_type"]][name]
                if quote is None:
                    atom = {"state": "absent", "span_id": None, "start": 0, "end": len(doc["body"]), "quote": None}
                else:
                    start = doc["body"].index(quote)
                    sid = next(sid for sid, text in doc["spans"].items() if quote in text)
                    atom = {"state": "present", "span_id": sid, "start": start, "end": start + len(quote), "quote": quote}
                fields[name] = atom
            items.append({"document_ref": doc["document_ref"], "fields": fields})
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"schema_version": "lx0609-anesthesia-visit-facts-v1", "documents": items}, ensure_ascii=False)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
