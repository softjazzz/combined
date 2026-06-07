from __future__ import annotations

import pytest

from app.services.unified_rule_engine import UnifiedRuleEngine


def _engine() -> UnifiedRuleEngine:
    async def _unused_llm_generate(_prompt: str):
        return {}

    return UnifiedRuleEngine(_unused_llm_generate)


def test_parse_batch_llm_response_accepts_fenced_json_results():
    raw = """```json
{
  "results": [
    {"rule_id": "SC-036", "status": "compliant", "is_compliant": true, "findings": "已分析", "evidence": "病程已记录处理意见", "confidence": 0.88}
  ]
}
```"""

    parsed = _engine()._parse_batch_llm_response(raw)

    assert parsed["parse_error"] is False
    assert parsed["items"][0]["rule_id"] == "SC-036"
    assert parsed["items"][0]["status"] == "compliant"


def test_parse_batch_llm_response_accepts_explanatory_text_with_json_array():
    raw = """以下是结果：
[
  {"rule_id": "SC-097", "status": "uncertain", "is_compliant": false, "findings": "缺完整手术记录上下文", "evidence": "", "confidence": 0.3}
]
请查收。"""

    parsed = _engine()._parse_batch_llm_response(raw)

    assert parsed["parse_error"] is False
    assert parsed["items"][0]["rule_id"] == "SC-097"
    assert parsed["items"][0]["status"] == "uncertain"


def test_parse_batch_llm_response_accepts_items_wrapper():
    raw = """{"items": [{"rule_code": "SC-123", "status": "non_compliant", "is_compliant": false, "findings": "出院带药缺给药途径", "evidence": "出院带药：某药 bid*7天", "confidence": 0.7}]}"""

    parsed = _engine()._parse_batch_llm_response(raw)

    assert parsed["parse_error"] is False
    assert parsed["items"][0]["rule_id"] == "SC-123"
    assert parsed["items"][0]["status"] == "non_compliant"


def test_parse_batch_llm_response_rejects_truncated_json():
    raw = """{"results": [{"rule_id": "SC-118", "status": "non_compliant", "is_compliant": false"""

    parsed = _engine()._parse_batch_llm_response(raw)

    assert parsed["parse_error"] is True
    assert parsed["items"] == []
