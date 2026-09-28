"""编码质控目录、版本启停、执行范围与旧调用兼容合同。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.routers.qc import _build_coding_qc_persistence_result
from app.services import rule_set_version_service as versions
from app.services.coding_qc_service import CodingQCEngine
from app.services.coding_rule_catalog import (
    CODING_RULE_IDS,
    CODING_RULE_SET_KEY,
    CODING_RULE_SET_VERSION,
    get_coding_rule_set,
    load_coding_rule_catalog,
)
from app.services.sichuan_workspace_batch_prepare import (
    SichuanWorkspaceBatchJobCreateRequest,
    prepare_workspace_batch_job,
)


def _complete_frontpage() -> dict:
    return {
        "diagnoses": [
            {"code": "K35.9", "name": "急性阑尾炎"},
            {"code": "K65.0", "name": "急性腹膜炎"},
        ],
        "surgeries": [],
    }


def test_builtin_catalog_has_stable_metadata_and_pauses_unimplemented_rules(monkeypatch):
    rows = load_coding_rule_catalog()
    assert tuple(row["rule_id"] for row in rows) == CODING_RULE_IDS
    assert all(row["qc_point"] if "qc_point" in row else row["name"] for row in rows)
    assert all(row["category"] and row["category_name"] for row in rows)
    assert {row["rule_id"] for row in rows if not row["executable"]} == {"CR-011", "CR-018"}

    monkeypatch.setattr(versions, "SessionLocal", None)
    resolved = versions.resolve_rule_set_version(CODING_RULE_SET_KEY, CODING_RULE_SET_VERSION)
    assert set(resolved["paused_rule_ids"]) == {"CR-011", "CR-018"}
    assert not ({"CR-011", "CR-018"} & set(resolved["active_rule_ids"]))


def test_pending_coding_rule_cannot_be_published_as_active(monkeypatch):
    monkeypatch.setattr(versions, "SessionLocal", None)
    base = versions.resolve_rule_set_version(CODING_RULE_SET_KEY, CODING_RULE_SET_VERSION)
    entries = [
        {"rule_id": rule_id, "state": "active"}
        for rule_id in CODING_RULE_IDS
    ]
    with pytest.raises(versions.RuleSetVersionInvalid) as exc_info:
        versions.validate_publish_entries(get_coding_rule_set(CODING_RULE_SET_KEY), base, entries)
    assert "CR-011" in str(exc_info.value.problems)
    assert "CR-018" in str(exc_info.value.problems)


def test_generic_sichuan_prepare_rejects_coding_rule_set_before_collection():
    class _Workspace:
        called = False

        def collect_records(self, **_):
            self.called = True
            return []

    workspace = _Workspace()
    with pytest.raises(HTTPException) as exc_info:
        prepare_workspace_batch_job(
            SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=CODING_RULE_SET_KEY,
                scope="final",
            ),
            qc_service=object(),
            workspace=workspace,
        )
    assert exc_info.value.status_code == 422
    assert workspace.called is False


@pytest.mark.asyncio
async def test_versioned_deterministic_selection_freezes_identity_and_exact_scope():
    report = await CodingQCEngine(llm_client=None).run_all(
        {"diagnoses": [{"code": "123", "name": "坏编码"}], "surgeries": []},
        rule_set_version="v-coding-2",
        rule_set_content_digest="a" * 64,
        active_rule_ids=["CR-001"],
    )
    assert {item.rule_id for item in report.rule_issues} == {"CR-001"}
    assert report.rule_set_key == CODING_RULE_SET_KEY
    assert report.rule_set_version == "v-coding-2"
    assert report.rule_set_content_digest == "a" * 64
    assert report.active_rule_ids == ["CR-001"]
    assert report.executed_rule_ids == ["CR-001"]

    persisted = _build_coding_qc_persistence_result({}, report.to_dict())
    assert persisted["metadata"]["executed_defect_scope"] == {
        "kind": "rule_codes",
        "values": ["CR-001"],
    }
    assert persisted["metadata"]["rule_set_content_digest"] == "a" * 64


@pytest.mark.asyncio
async def test_semantic_prompt_only_contains_enabled_section_and_accepts_enabled_id():
    llm = AsyncMock()
    llm.generate.return_value = {
        "choices": [{"message": {"content": (
            '{"issues": ['
            '{"rule_id":"CR-009","dimension":"merge","severity":"warning",'
            '"code":"K35.9","description":"应核对合并编码","suggestion":"复核"}'
            ']}'
        )}}]
    }
    report = await CodingQCEngine(llm_client=llm).run_all(
        _complete_frontpage(),
        rule_set_version="v-coding-2",
        active_rule_ids=["CR-009"],
    )
    prompt = llm.generate.await_args.args[0]
    assert "## 1. 编码合并" in prompt
    assert "## 2. 编码互斥" not in prompt
    assert [issue.rule_id for issue in report.llm_issues] == ["CR-009"]
    assert report.executed_rule_ids == ["CR-009"]


@pytest.mark.asyncio
async def test_semantic_output_outside_enabled_whitelist_is_incomplete():
    llm = AsyncMock()
    llm.generate.return_value = {
        "choices": [{"message": {"content": (
            '{"issues":[{"rule_id":"CR-010","dimension":"exclusion",'
            '"severity":"warning","description":"未启用项","suggestion":"忽略"}]}'
        )}}]
    }
    report = await CodingQCEngine(llm_client=llm).run_all(
        _complete_frontpage(),
        rule_set_version="v-coding-2",
        active_rule_ids=["CR-009"],
    )
    assert report.llm_issues == []
    assert report.semantic_completed is False
    assert report.executed_rule_ids == []


@pytest.mark.asyncio
async def test_semantic_failure_does_not_claim_completed_scope_or_clear_old_defects():
    llm = AsyncMock()
    llm.generate.side_effect = RuntimeError("synthetic unavailable")
    report = await CodingQCEngine(llm_client=llm).run_all(
        _complete_frontpage(),
        rule_set_version="v-coding-2",
        active_rule_ids=["CR-001", "CR-009"],
    )
    assert any(issue.rule_id == "CR-009" for issue in report.rule_issues)
    assert report.semantic_completed is False
    assert report.executed_rule_ids == []
    persisted = _build_coding_qc_persistence_result({}, report.to_dict())
    assert "executed_defect_scope" not in persisted["metadata"]


def test_legacy_direct_bidding_call_preserves_cq_tender_identity():
    issues = CodingQCEngine(llm_client=None).check_bidding_scenarios({
        "diagnoses": [{"code": "C50.9", "name": "乳腺恶性肿瘤"}],
        "surgeries": [],
        "pathology_diagnosis_fee": 1,
    })
    assert issues
    assert issues[0].rule_id == "CQ-TENDER-001"
    assert issues[0].legacy_rule_id == ""
