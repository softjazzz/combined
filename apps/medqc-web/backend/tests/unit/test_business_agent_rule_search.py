"""权威目录搜索只读验证，不连接业务库或模型。"""
import asyncio
import httpx
import pytest
from pydantic import ValidationError
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore
from app.services.qc_agent.business_tools import BusinessTools, SearchRules


def test_search_pagination_keywords_empty_and_current_version(tmp_path):
    async def scenario():
        user = {"id": "synthetic-search"}
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(user, BusinessContext(view="manager"))
        def reject_network(request):
            raise AssertionError("不得连接网络")
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(reject_network)) as client:
            tools = BusinessTools(store, client)
            first = await tools.execute("search_rules", {"query": "lx0609", "page_size": 2}, metadata, user)
            second = await tools.execute("search_rules", {"query": "lx0609", "page_size": 2, "page": 2}, metadata, user)
            rows = sorted(load_luxian_0609_rule_master(), key=lambda row: row.rule_id)
            assert first["rule_search"]["total"] == len(rows)
            assert first["rule_search"]["has_more"] is True
            assert first["references"] == []
            assert [r["rule_id"] for r in first["rule_candidates"] + second["rule_candidates"]] == [r.rule_id for r in rows[:4]]
            assert store.get(metadata["session_id"], user)["references"] == {}
            selected = rows[0]
            found = await tools.execute("search_rules", {"query": f"{selected.qc_point} {selected.rule_id.lower()}"}, metadata, user)
            assert [r["rule_id"] for r in found["rule_candidates"]] == [selected.rule_id]
            assert found["rule_candidates"][0]["phase_status"] == selected.phase_status
            detail = await tools.execute("read_rule", {"rule_id": selected.rule_id}, metadata, user)
            assert detail["historical_definition_available"] is False
            assert detail["catalog_version"] == found["catalog_version"]
            assert detail["rule"]["policy_summary"] == selected.policy_summary
            missing = await tools.execute("search_rules", {"query": "不存在的合成检索关键词"}, metadata, user)
            assert missing["rule_candidates"] == []
            assert missing["rule_search"]["total"] == 0
            assert missing["rule_search"]["has_more"] is False
    asyncio.run(scenario())


@pytest.mark.parametrize("args", [{"query": "  "}, {"query": "x" * 101}, {"query": "CT", "page_size": 11}, {"query": "CT", "patient_id": "other"}])
def test_search_input_limits(args):
    with pytest.raises(ValidationError):
        SearchRules.model_validate(args)


def test_partial_release_reference_preserves_catalog_subcriteria(tmp_path, monkeypatch):
    from dataclasses import replace
    from app.services import luxian_0609_rule_master as master
    partial = replace(load_luxian_0609_rule_master()[0], phase_status="phase_1_partial",
                      active_criteria=("synthetic_active",), pending_criteria=("synthetic_pending",),
                      pending_reason_code="")
    monkeypatch.setattr(master, "load_luxian_0609_rule_master", lambda: (partial,))
    async def scenario():
        user = {"id": "synthetic-partial"}
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(user, BusinessContext(view="manager"))
        async with httpx.AsyncClient() as client:
            detail = await BusinessTools(store, client).execute("read_rule", {"rule_id": partial.rule_id}, metadata, user)
            text = detail["references"][0]["text"]
            assert "已发布子项（目录标识）：synthetic_active" in text
            assert "待发布子项（目录标识）：synthetic_pending" in text
            assert "待发布原因（目录代码）：未单列" in text
            assert detail["rule"]["phase_status"] == "phase_1_partial"
            assert detail["rule"]["active_criteria"] == ("synthetic_active",)
    asyncio.run(scenario())
