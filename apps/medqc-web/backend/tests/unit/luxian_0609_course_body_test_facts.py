"""人工冻结病程正文事实的机械回执；不导入生产或按关键词判语义。"""
import json


def read_course_body_documents(prompt):
    """读实际发送的 INPUT_JSON 正文；正文即模型可引用的原文。"""
    return json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["documents"]


class FrozenCourseBodyClient:
    def __init__(self, facts, *, mode="valid", max_calls=1):
        # 每个body的state/quote由测试显式人工给定，不读取生产结论。
        self.facts, self.mode, self.max_calls = dict(facts), mode, max_calls
        self.calls, self.payloads = [], []
        self.fixture_error = None

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        try:
            assert len(self.calls) <= self.max_calls
            assert kwargs == {"max_completion_tokens": 4096, "allow_length_retry": False}
            documents = read_course_body_documents(prompt)
            items = []
            for doc in documents:
                state, quote = self.facts[doc["body"]]
                if state == "present":
                    assert quote in doc["body"]
                    atom = {"state": state, "quote": quote}
                else:
                    assert state in {"absent", "unknown"} and quote is None
                    atom = {"state": state, "quote": None}
                items.append({"document_ref": doc["document_ref"], "clinical_body": atom})
            if self.mode == "invalid_batch":
                assert len(items) == 2
                items[1]["clinical_body"]["unregistered_key"] = True
            payload = {"schema_version": "lx0609-course-body-facts-v2", "documents": items}
            self.payloads.append(payload)
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        except Exception as error:
            self.fixture_error = type(error).__name__
            raise


# 原正文逐项人工冻结事实；精确字符串查表，不按关键词/期望C分类。
LEGACY_MANUAL_COURSE_BODY_FACTS = {'查房记录：\n医生签名：张医生': ('absent', None),
 '主任医师查房记录': ('absent', None),
 '病程记录：\n医师签名：李某 主治医师': ('absent', None),
 '查房记录：医生签名：张医生': ('absent', None),
 '病程记录： 医师签名：李某 主治医师': ('absent', None),
 '术后首次病程记录': ('absent', None),
 '病情稳定。': ('present', '病情稳定'),
 '主任医师查房，病情稳定。\n医生签名：张医生': ('present', '病情稳定'),
 '病程记录：患者病情稳定。': ('present', '患者病情稳定'),
 '医生签名:继续观察。': ('present', '继续观察'),
 '医生签名：张医生': ('absent', None),
 '医师签名：李某 主治医师': ('absent', None),
 '医生签名：': ('absent', None),
 '医生签名：张三\n医师签名：李四': ('absent', None),
 '患者病情稳定，明日出院。': ('present', '患者病情稳定'),
 '患者病情稳定，明日出院。\n医生签名：张医生': ('present', '患者病情稳定'),
 '主任医师查房，伤口愈合良好，继续观察。': ('present', '伤口愈合良好'),
 '查房，病情稳定。': ('present', '病情稳定'),
 '稳定': ('present', '稳定'),
 '医生签名:': ('absent', None),
 '医师签名：': ('absent', None),
 ' 医生 签名 : \n': ('absent', None),
 '病情稳定。医生签名:': ('present', '病情稳定'),
 '上级医师查看患者，同意今日出院。': ('present', '同意今日出院'),
 '上级医师查看患者，同意明日出院。': ('present', '同意明日出院'),
 '一般病程。': ('unknown', None),
 '上级医师查房，病情稳定，继续观察。': ('present', '病情稳定'),
 '上级医师查房后同意患者出院。': ('present', '同意患者出院'),
 '病情稳定': ('present', '病情稳定'),
 '缺少权威记录时间': ('unknown', None)}
