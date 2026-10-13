"""013/019 病理记录事实抽取的测试用模型客户端（合成正文）。

默认按简单规则模拟模型：019 找写有送检/取材动作且非计划/否定的句子；013 找写有
“病理”且含报告诊断片段、非待回报的句子。语义口径由真实模型验证，这里只为
执行器管线提供协议正确的事实；需要精确控制时传 script。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.services.luxian_0609.pathology_documentation_extraction import SCHEMA_VERSION

_SENTENCE = re.compile(r"[^。；;！？!?\n]+")
_SAMPLING_ACTION = re.compile(r"送病理|送检|送冰冻|送快速|取材")
_SAMPLING_NOT_DONE = re.compile(r"拟|建议|待|未|拒")
_RESULT_PENDING = re.compile(r"待回报|未回|尚未")


def pathology_inputs(prompt: str) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
    return "取材或送检" in prompt, payload["pathology_events"], payload["documents"]


def _diagnosis_terms(diagnosis: str) -> list[str]:
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", diagnosis)
    return [term for term in re.split(r"[，,；;。\s]+", cleaned) if len(term) >= 2]


def default_pathology_facts(sampling: bool, events: list[dict], documents: list[dict]) -> list[dict]:
    answers = []
    for event in events:
        found = None
        for doc in documents:
            for match in _SENTENCE.finditer(doc["body"]):
                sentence = match.group().strip()
                if sampling:
                    hit = bool(_SAMPLING_ACTION.search(sentence)) and not _SAMPLING_NOT_DONE.search(sentence)
                else:
                    hit = "病理" in sentence and not _RESULT_PENDING.search(sentence) and any(
                        term in sentence for term in _diagnosis_terms(event.get("diagnosis", ""))
                    )
                if hit:
                    found = (doc["document"], sentence)
                    break
            if found:
                break
        answers.append(
            {"event": event["event"], "state": "documented", "document": found[0], "quote": found[1]}
            if found else {"event": event["event"], "state": "not_documented", "document": None, "quote": None}
        )
    return answers


class PathologyFactsClient:
    def __init__(self, script: Callable[[bool, list, list], list] | None = None, *, tokens: int = 120):
        self.script = script or default_pathology_facts
        self.prompts: list[str] = []
        self.tokens = tokens

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        sampling, events, documents = pathology_inputs(prompt)
        content = json.dumps(
            {"schema_version": SCHEMA_VERSION, "events": self.script(sampling, events, documents)},
            ensure_ascii=False,
        )
        return {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": self.tokens - 20, "completion_tokens": 20, "total_tokens": self.tokens},
            "_api_time": 0.1,
        }
