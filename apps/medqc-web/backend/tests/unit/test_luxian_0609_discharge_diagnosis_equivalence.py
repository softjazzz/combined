"""063 出院诊断同义判定协议：模型只返回编号配对，违规整体技术错误。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.luxian_0609.extended_document.discharge_diagnosis_equivalence import (
    SCHEMA_VERSION,
    extract_discharge_diagnosis_equivalence,
    map_equivalent_diagnoses,
    valid_equivalent_pairs,
)


class _Client:
    def __init__(self, items, *, kwargs_sink=None):
        self.items = items
        self.kwargs_sink = kwargs_sink
        self.calls = 0

    def supports_strict_json_schema(self):
        return True

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        if self.kwargs_sink is not None:
            self.kwargs_sink.update(kwargs)
        return {
            "content": json.dumps({"schema_version": SCHEMA_VERSION, "items": self.items}),
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }


def _run(authoritative, written, client):
    return asyncio.run(extract_discharge_diagnosis_equivalence(authoritative, written, client))


def test_same_pairs_are_returned_with_names_and_thinking_disabled():
    kwargs = {}
    client = _Client([{"id": "A1", "match": "W1", "relation": "same"}], kwargs_sink=kwargs)
    result = _run(["原发性高血压"], ["高血压病"], client)
    assert result.state == "ready"
    assert result.pairs == (("原发性高血压", "高血压病"),)
    assert result.llm_call_count == 1
    assert kwargs["enable_thinking"] is False
    assert kwargs["allow_length_retry"] is False


def test_uncertain_relation_is_unresolved():
    client = _Client([{"id": "A1", "match": None, "relation": "uncertain"}])
    result = _run(["诊断甲"], ["诊断乙"], client)
    assert result.state == "unresolved"
    assert result.reason_code == "semantic_extraction_unresolved"


@pytest.mark.parametrize("items", [
    [],
    [{"id": "A9", "match": None, "relation": "absent"}],
    [{"id": "A1", "match": "W9", "relation": "same"}],
    [{"id": "A1", "match": "W1", "relation": "absent"}],
    [{"id": "A1", "match": "W1", "relation": "same"}, {"id": "A2", "match": "W1", "relation": "same"}],
    [{"id": "A1", "match": None, "relation": "absent"}, {"id": "A1", "match": None, "relation": "absent"}],
    [{"id": "A1", "match": None, "relation": "maybe"}],
    [{"id": "A1", "match": None}],
])
def test_protocol_violations_are_technical_errors(items):
    result = _run(["诊断甲", "诊断乙"], ["诊断丙", "诊断丁"], _Client(items))
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


def test_one_sided_remainder_needs_no_model():
    client = _Client([])
    result = _run(["诊断甲"], [], client)
    assert result.state == "ready" and result.pairs == () and client.calls == 0


def test_missing_client_fails_closed():
    assert _run(["诊断甲"], ["诊断乙"], None).state == "technical_error"


def test_mapping_and_public_pair_validation():
    assert map_equivalent_diagnoses(["肺炎", "高血压"], [("高血压病", "高血压")]) == ["肺炎", "高血压病"]
    assert valid_equivalent_pairs([["高血压病", "高血压"]], authoritative=["高血压病"], written=["高血压"]) == [
        ["高血压病", "高血压"]
    ]
    assert valid_equivalent_pairs([["高血压病", "糖尿病"]], authoritative=["高血压病"], written=["高血压"]) is None
    assert valid_equivalent_pairs([["高血压", "高血压"]], authoritative=["高血压"], written=["高血压"]) is None


def test_numbered_diagnosis_list_in_one_name_is_split_in_order():
    from app.services.luxian_0609.extended_document.discharge_diagnosis_equivalence import (
        split_numbered_diagnoses,
    )

    assert split_numbered_diagnoses(["1.椎体压缩性骨折2.骨质疏松症3.高脂血症"]) == [
        "椎体压缩性骨折", "骨质疏松症", "高脂血症",
    ]
    assert split_numbered_diagnoses(["1.T12椎体骨折 2.S2-3椎体骨折"]) == ["T12椎体骨折", "S2-3椎体骨折"]
    # 名称内数字、单条编号与不连续编号都不拆分。
    assert split_numbered_diagnoses(["2型糖尿病", "高血压3级", "1.肺炎", "1.甲 3.乙"]) == [
        "2型糖尿病", "高血压3级", "1.肺炎", "1.甲 3.乙",
    ]


def test_written_name_contained_in_concatenated_authority_pairs_without_model():
    # 用户口径（2026-10-19）：首页“标准名+补充描述”相连，出院记录只写其中诊断名视为同一诊断。
    client = _Client([])
    result = _run(
        ["慢性浅表性胃炎胆汁反流", "胃溃疡胃窦溃疡（H2-S1期）", "抽动障碍肢体抽动原因待查"],
        ["胆汁反流", "抽动障碍", "胃溃疡"], client,
    )
    assert result.state == "ready"
    assert client.calls == 0
    assert set(result.pairs) == {
        ("慢性浅表性胃炎胆汁反流", "胆汁反流"),
        ("胃溃疡胃窦溃疡（H2-S1期）", "胃溃疡"),
        ("抽动障碍肢体抽动原因待查", "抽动障碍"),
    }


def test_contained_pairs_are_kept_and_only_rest_goes_to_model():
    client = _Client([{"id": "A1", "match": "W1", "relation": "same"}])
    result = _run(["慢性浅表性胃炎胆汁反流", "原发性高血压"], ["高血压病", "胆汁反流"], client)
    assert result.state == "ready"
    assert client.calls == 1
    assert set(result.pairs) == {("慢性浅表性胃炎胆汁反流", "胆汁反流"), ("原发性高血压", "高血压病")}


def test_ambiguous_containment_still_goes_to_model():
    # 一条书写名称落入两条权威名称时不由程序配对。
    client = _Client([
        {"id": "A1", "match": "W1", "relation": "same"},
        {"id": "A2", "match": None, "relation": "absent"},
    ])
    result = _run(["胃溃疡出血", "胃溃疡穿孔"], ["胃溃疡", "胃炎"], client)
    assert client.calls == 1
    assert result.pairs == (("胃溃疡出血", "胃溃疡"),)


class _SequenceClient:
    def __init__(self, *item_lists):
        self.item_lists = list(item_lists)
        self.prompts = []

    def supports_strict_json_schema(self):
        return True

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        items = self.item_lists[min(len(self.prompts), len(self.item_lists)) - 1]
        return {
            "content": json.dumps({"schema_version": SCHEMA_VERSION, "items": items}),
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }


def test_uncertain_with_match_gets_one_targeted_recheck():
    # C25 类：relation=uncertain 却填了 match，补核指明条目并附上次输出，修正后按无法判定处理。
    client = _SequenceClient(
        [{"id": "A1", "match": "W1", "relation": "uncertain"}],
        [{"id": "A1", "match": None, "relation": "uncertain"}],
    )
    result = _run(["孤立性肺结节"], ["双肺小结节"], client)
    assert result.state == "unresolved"
    assert result.llm_call_count == 2
    assert result.total_tokens == 20
    assert "A1的relation为uncertain，match必须为null" in client.prompts[1]
    assert '"relation": "uncertain"' in client.prompts[1]


def test_repeated_protocol_violation_after_recheck_is_technical_error():
    client = _SequenceClient([{"id": "A1", "match": "W1", "relation": "absent"}])
    result = _run(["孤立性肺结节"], ["双肺小结节"], client)
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.llm_call_count == 2
