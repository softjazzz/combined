"""人工冻结的037测试事实；不读取生产判定、不作文本语义分类。

字段按业务基线 037：术前访视一般情况、简要病史、相关检查、拟行手术和麻醉方式、
适应证、注意事项、术前医嘱；术后访视恢复、清醒、拔管、术后医嘱、特殊情况。
"""
import json

PRE_SOURCE = "preane_surveil_record"
POST_SOURCE = "postane_surveil_record"
SCHEMA_VERSION = "lx0609-anesthesia-visit-facts-v2"
PRE_TEXT = (
    "一般情况：神志清，生命体征平稳；简要病史：胆囊结石2年，否认麻醉史；相关检查：血常规、凝血功能未见异常；"
    "拟行手术及麻醉：腹腔镜胆囊切除术，全身麻醉；适应证：ASA II级，可耐受全麻；注意事项：防误吸；"
    "术前医嘱：禁食8小时禁饮2小时。"
)
POST_TEXT = "神志清醒；恢复良好，呼吸循环稳定；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。"
GOLD_QUOTES = {
    PRE_SOURCE: {
        "general_condition": "神志清，生命体征平稳",
        "brief_history": "胆囊结石2年，否认麻醉史",
        "relevant_examinations": "血常规、凝血功能未见异常",
        "planned_procedure_and_anesthesia": "腹腔镜胆囊切除术，全身麻醉",
        "anesthesia_indication": "ASA II级，可耐受全麻",
        "precautions": "防误吸",
        "preoperative_orders": "禁食8小时禁饮2小时",
        "anesthetist_signature": "医师签名",
        "record_time": "记录时间",
    },
    POST_SOURCE: {
        "recovery_status": "恢复良好，呼吸循环稳定",
        "consciousness_status": "神志清醒",
        "extubation_status": "已拔除气管导管",
        "postoperative_orders": "继续监护6小时",
        "special_situations": "无麻醉并发症",
        "anesthetist_signature": "医师签名",
        "record_time": "记录时间",
    },
}


def _absent(*pairs):
    return frozenset(pairs)


_ALL_PRE = tuple((PRE_SOURCE, name) for name in GOLD_QUOTES[PRE_SOURCE] if name not in {"anesthetist_signature", "record_time"})
_ALL_POST = tuple((POST_SOURCE, name) for name in GOLD_QUOTES[POST_SOURCE] if name not in {"anesthetist_signature", "record_time"})
_CONSCIOUSNESS = _absent((POST_SOURCE, "consciousness_status"))
_RECOVERY = _absent((POST_SOURCE, "recovery_status"))
_SPECIAL = _absent((POST_SOURCE, "special_situations"))

# 原用例逐项答案：值为模型应判 absent 的 (来源, 字段)。旧字段按语义并入基线字段：
# 意识→清醒情况，呼吸/循环→恢复情况，麻醉并发症→特殊情况，麻醉史→简要病史。
CASE_FACTS = {
    "round2_complete": _absent(),
    "round2_empty_labels": _absent(*_ALL_PRE, *_ALL_POST),
    "round2_invalid_time": _absent(),
    "round2_without_event_keys": _absent(),
    "n08_filled_heart_label": _absent(),
    "n08_filled_followup_label": _absent(),
    "n08_filled_heart_placeholder": _absent(),
    "n08_filled_heart_value": _absent(),
    "n08_missing_consciousness": _CONSCIOUSNESS,
    "n08_missing_respiratory": _RECOVERY,
    "n08_missing_complication": _SPECIAL,
    "n08_adjacent_missing_consciousness": _CONSCIOUSNESS,
    "n04_missing_history": _absent((PRE_SOURCE, "brief_history")),
    "n04_missing_complication": _SPECIAL,
    "n04_missing_consciousness": _CONSCIOUSNESS,
    "n04_missing_respiratory": _RECOVERY,
    "n04_missing_signature": _absent((PRE_SOURCE, "anesthetist_signature")),
    "n04_negative_none": _absent(),
    "n04_negative_no_abnormality": _absent(),
    "n04_adjacent_space_missing_consciousness": _CONSCIOUSNESS,
    "n04_adjacent_missing_consciousness": _CONSCIOUSNESS,
    "n04_adjacent_missing_respiratory": _RECOVERY,
    "n04_adjacent_missing_complication": _SPECIAL,
    "n04_filled_no_separator": _absent(),
    "n04_filled_space_separator": _absent(),
    "native_negated_assessments": _absent((PRE_SOURCE, "anesthesia_indication"), (PRE_SOURCE, "precautions")),
    "freeze_complete": _absent(),
    "precise_complete": _absent(),
}
N08_FILLED_CASES = {"心率：": "n08_filled_heart_label", "后续项目：": "n08_filled_followup_label", "心率：___": "n08_filled_heart_placeholder", "心率：80次/分": "n08_filled_heart_value"}
N08_EMPTY_CASES = {
    "术后意识：；恢复良好，呼吸循环稳定；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。": "n08_missing_consciousness",
    "神志清醒；恢复情况：；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。": "n08_missing_respiratory",
    "神志清醒；恢复良好，呼吸循环稳定；已拔除气管导管；医嘱：继续监护6小时；特殊情况：": "n08_missing_complication",
    "术后意识：恢复情况：良好；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。": "n08_adjacent_missing_consciousness",
}
N04_BLANK_CASES = {"brief_history": "n04_missing_history", "special_situations": "n04_missing_complication", "consciousness_status": "n04_missing_consciousness", "recovery_status": "n04_missing_respiratory"}
N04_NEGATIVE_CASES = {"无": "n04_negative_none", "未见异常": "n04_negative_no_abnormality"}
N04_ADJACENT_CASES = {
    "术后意识： 恢复情况：良好；拔管：已拔除；医嘱：继续监护；特殊情况：无": "n04_adjacent_space_missing_consciousness",
    "术后意识：恢复情况：良好；拔管：已拔除；医嘱：继续监护；特殊情况：无": "n04_adjacent_missing_consciousness",
    "术后意识清醒 恢复情况：；拔管：已拔除；医嘱：继续监护；特殊情况：无": "n04_adjacent_missing_respiratory",
    "神志清醒；恢复良好；已拔管；医嘱：继续监护；特殊情况： 备注：已访视": "n04_adjacent_missing_complication",
}
N04_FILLED_CASES = {"": "n04_filled_no_separator", " ": "n04_filled_space_separator"}


def read_sent_anesthesia_documents(prompt):
    """读实际发送的 INPUT_JSON 正文；正文即模型可引用的原文。"""
    return json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["documents"]


def anesthesia_fact_atom(doc, field, *, absent=frozenset(), unknown=frozenset(), not_applicable=frozenset(), overrides=None):
    key = (doc["source_type"], field)
    if key in unknown:
        return {"state": "unknown", "quote": None}
    if key in absent:
        return {"state": "absent", "quote": None}
    quote = (overrides or {}).get(key, GOLD_QUOTES.get(doc["source_type"], {}).get(field))
    if not quote or quote not in doc["body"]:
        # 冻结答案只决定状态；正文不含人工摘录时以整段送检正文作为同文书引用。
        quote = doc["body"]
    return {"state": "not_applicable" if key in not_applicable else "present", "quote": quote}


def anesthesia_fact_response(payload):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


class ExplicitAnesthesiaFactClient:
    def __init__(self, case):
        self.absent = CASE_FACTS[case]
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        assert len(self.calls) == 1
        assert kwargs["allow_length_retry"] is False
        assert 0 < kwargs["max_completion_tokens"] <= 4096
        documents = read_sent_anesthesia_documents(prompt)
        assert len(documents) == 2
        assert {doc["source_type"] for doc in documents} == {PRE_SOURCE, POST_SOURCE}
        items = [{"document_ref": doc["document_ref"],
                  "fields": {name: anesthesia_fact_atom(doc, name, absent=self.absent) for name in doc["required_fields"]}}
                 for doc in documents]
        return anesthesia_fact_response({"schema_version": SCHEMA_VERSION, "documents": items})
