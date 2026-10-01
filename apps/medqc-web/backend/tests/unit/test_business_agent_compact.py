"""状态完整性、稳定分页与精简投影输入仍由正式保存事实决定。"""
import asyncio
from collections import Counter

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore
from app.services.qc_agent.business_tools import BusinessTools, ReadResults, tool_specs


def test_filtered_page_keeps_full_cards_counts_and_exact_second_binding(tmp_path):
    async def scenario():
        user = {"id": "synthetic"}
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(user, BusinessContext(view="doctor", institute_id="H", patient_id="P", visit_id="V"))
        statuses = ["compliant", "non_compliant", "data_gap", "not_executed", "needs_review", "not_applicable"]
        items = [{"rule_id": f"LX0609-01-01-{i + 1:02}", "qc_point": f"质控点{i + 1}", "status": statuses[i % 6], "conclusion": f"完整结论{i}", "suggestion": f"完整建议{i}"} for i in range(24)]
        payload = {"state": "ready", "job_id": "saved-a", "record_ref": "record-a", "items": items, "is_complete": True}
        async with httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": payload}))) as client:
            tools = BusinessTools(store, client)
            first = await tools.execute("read_saved_results", {"statuses": ["non_compliant"], "page_size": 3, "detail": "saved_text"}, metadata, user)
            assert first["result_page"]["status_counts"] == dict(Counter(row["status"] for row in items))
            assert first["result_page"]["matched_total"] == 4
            assert first["result_page"]["total"] == 24
            assert first["result_page"]["has_more"] is True
            expected = [row for row in items if row["status"] == "non_compliant"]
            assert [r["rule_id"] for r in first["references"]] == [r["rule_id"] for r in expected[:3]]
            assert first["references"][1]["conclusion"] == expected[1]["conclusion"]
            second_id = first["references"][1]["id"]
            current = store.get(metadata["session_id"], user)
            issue = await tools.issue(current, second_id)
            assert issue["references"][0]["rule_id"] == expected[1]["rule_id"]
            later = await tools.execute("read_saved_results", {"statuses": ["non_compliant"], "page_size": 3, "page": 2, "expected_job_id": "saved-a"}, current, user)
            assert later["references"][0]["position"] == 4
            assert later["result_page"]["has_more"] is False
            assert [r["rule_id"] for r in first["references"] + later["references"]] == [r["rule_id"] for r in expected]
            payload["job_id"] = "saved-b"
            with pytest.raises(HTTPException) as changed:
                await tools.execute("read_saved_results", {"page": 2, "expected_job_id": "saved-a"}, current, user)
            assert changed.value.status_code == 409
            # 全类别均能分页访问；空匹配不把其他状态说成不存在。
            payload["job_id"] = "saved-a"
            payload["record_ref"] = "changed-record"
            with pytest.raises(HTTPException) as record_changed:
                await tools.execute("read_saved_results", {"page": 2, "expected_job_id": "saved-a"}, current, user)
            assert record_changed.value.status_code == 409
            payload["record_ref"] = "record-a"
            pages = [await tools.execute("read_saved_results", {"page": page, "expected_job_id": "saved-a"}, current, user) for page in (1, 2, 3)]
            assert [r["rule_id"] for page in pages for r in page["references"]] == [item["rule_id"] for item in items]
            for status in statuses:
                result = await tools.execute("read_saved_results", {"statuses": [status]}, current, user)
                assert len(result["references"]) == 4
            result = await tools.execute("read_saved_results", {"statuses": ["uncertain"]}, current, user)
            assert result["references"] == [] and result["result_page"]["total"] == 24
    asyncio.run(scenario())


def test_subsequent_page_requires_seen_version_and_rejects_large_page():
    schema = next(spec["parameters"] for spec in tool_specs() if spec["name"] == "read_saved_results")
    assert schema["properties"]["statuses"]["type"] == "array"
    assert ReadResults(statuses=[]).statuses == []
    with pytest.raises(ValidationError):
        ReadResults(statuses='["non_compliant"]')
    with pytest.raises(ValidationError):
        ReadResults(page=2)
    with pytest.raises(ValidationError):
        ReadResults(page_size=75)
