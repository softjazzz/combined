"""编码质控点目录与版本生命周期合同（SQLite 合成库，不访问真实数据库）。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRuleSetVersion
from app.services import rule_set_version_service as service
from app.services import rule_set_version_excel_service as excel
from app.services.coding_rule_catalog import (
    CODING_EXECUTABLE_RULE_IDS,
    CODING_PENDING_RULE_IDS,
    CODING_RULE_IDS,
    CODING_RULE_SET_KEY,
    CODING_RULE_SET_VERSION,
    coding_rule_metadata,
    get_coding_rule_set,
    load_coding_rule_catalog,
)
from app.services.qc_rule_sets import get_sichuan_rule_set


ACTOR = "coding-manager"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _write_entries(entries):
    return [
        {
            "rule_id": item["rule_id"], "state": item["state"],
            # 发布须已配置科室范围与医生端开关；本组只验证状态语义，统一取“全院、不对医生可见”。
            "department_scope_mode": "all", "department_refs": [], "doctor_visible": False,
        }
        for item in entries
    ]


def _with_state(entries, rule_id: str, state: str):
    return [
        {**item, "state": state} if item["rule_id"] == rule_id else dict(item)
        for item in entries
    ]


def test_coding_catalog_is_complete_and_isolated_from_sichuan_rule_sets():
    catalog = load_coding_rule_catalog()

    assert tuple(item["rule_id"] for item in catalog) == CODING_RULE_IDS
    assert len(catalog) == 18
    assert get_coding_rule_set(CODING_RULE_SET_KEY) is not None
    assert get_sichuan_rule_set(CODING_RULE_SET_KEY) is None
    assert set(CODING_RULE_IDS).isdisjoint(
        rule_id
        for rule_set_key in ("luxian_0609_qc_v1", "luxian_0916_qc_v1")
        for rule_id in get_sichuan_rule_set(rule_set_key).rule_ids
    )


def test_coding_builtin_metadata_and_executable_flags_match_all_18_catalog_ids(sessions):
    detail = service.with_executable_flags(
        CODING_RULE_SET_KEY,
        service.get_version_detail(CODING_RULE_SET_KEY, CODING_RULE_SET_VERSION),
    )
    metadata = coding_rule_metadata()
    by_id = {item["rule_id"]: item for item in detail["entries"]}

    assert set(by_id) == set(metadata) == set(CODING_RULE_IDS)
    assert set(detail["resolution"]["active_rule_ids"]) == set(CODING_EXECUTABLE_RULE_IDS)
    assert set(detail["resolution"]["paused_rule_ids"]) == set(CODING_PENDING_RULE_IDS)
    for rule_id, entry in by_id.items():
        assert {
            "qc_point": entry["qc_point"],
            "category": entry["category"],
            "category_name": entry["category_name"],
        } == metadata[rule_id]
        assert entry["source_document"] is None
        assert entry["executable"] is (rule_id in CODING_EXECUTABLE_RULE_IDS)


@pytest.mark.parametrize("pending_rule_id", sorted(CODING_PENDING_RULE_IDS))
def test_pending_coding_rules_cannot_be_published_active(sessions, pending_rule_id):
    draft = service.create_draft(CODING_RULE_SET_KEY, actor=ACTOR)
    entries = _with_state(_write_entries(draft["entries"]), pending_rule_id, "active")
    updated = service.update_draft(
        CODING_RULE_SET_KEY,
        actor=ACTOR,
        version_seq=draft["version_seq"],
        entries=entries,
    )

    with pytest.raises(service.RuleSetVersionInvalid) as error:
        service.publish_draft(
            CODING_RULE_SET_KEY,
            actor=ACTOR,
            version=f"reject-{pending_rule_id.lower()}",
            version_seq=updated["version_seq"],
        )

    assert error.value.code == "publish_validation_failed"
    assert any(
        pending_rule_id in problem and "不可执行" in problem
        for problem in error.value.problems
    )


def test_retired_coding_version_resolves_its_frozen_rule_sets(sessions):
    builtin = service.get_version_detail(CODING_RULE_SET_KEY, CODING_RULE_SET_VERSION)
    first_entries = _with_state(_write_entries(builtin["entries"]), "CR-001", "paused")
    service.create_draft(CODING_RULE_SET_KEY, actor=ACTOR, entries=first_entries)
    service.publish_draft(CODING_RULE_SET_KEY, actor=ACTOR, version="coding-v1")

    second = service.create_draft(CODING_RULE_SET_KEY, actor=ACTOR)
    second_entries = _with_state(_write_entries(second["entries"]), "CR-002", "offline")
    updated = service.update_draft(
        CODING_RULE_SET_KEY,
        actor=ACTOR,
        version_seq=second["version_seq"],
        entries=second_entries,
    )
    service.publish_draft(
        CODING_RULE_SET_KEY,
        actor=ACTOR,
        version="coding-v2",
        version_seq=updated["version_seq"],
    )

    retired = service.retire_version(CODING_RULE_SET_KEY, "coding-v1", actor=ACTOR)
    resolved = service.resolve_rule_set_version(CODING_RULE_SET_KEY, "coding-v1")

    assert retired["status"] == "retired"
    assert service.current_version(CODING_RULE_SET_KEY) == "coding-v2"
    assert resolved["source"] == "retired"
    assert set(resolved["active_rule_ids"]) == set(CODING_EXECUTABLE_RULE_IDS) - {"CR-001"}
    assert set(resolved["paused_rule_ids"]) == set(CODING_PENDING_RULE_IDS) | {"CR-001"}
    assert resolved["offline_rule_ids"] == []
    assert resolved["deleted_rule_ids"] == []
    assert resolved["excluded_rule_ids"] == []


def test_coding_excel_roundtrip_preserves_deleted_and_disabled_rules(sessions):
    draft = service.create_draft(CODING_RULE_SET_KEY, actor=ACTOR)
    entries = _with_state(_write_entries(draft["entries"]), "CR-001", "paused")
    entries = _with_state(entries, "CR-002", "offline")
    updated = service.update_draft(
        CODING_RULE_SET_KEY, actor=ACTOR,
        version_seq=draft["version_seq"], entries=entries,
    )
    service.publish_draft(
        CODING_RULE_SET_KEY, actor=ACTOR, version="coding-disabled",
        version_seq=updated["version_seq"],
    )
    draft = service.create_draft(CODING_RULE_SET_KEY, actor=ACTOR)
    updated = service.update_draft(
        CODING_RULE_SET_KEY, actor=ACTOR, version_seq=draft["version_seq"],
        entries=_with_state(_write_entries(draft["entries"]), "CR-002", "deleted"),
    )
    service.publish_draft(
        CODING_RULE_SET_KEY, actor=ACTOR, version="coding-deleted",
        version_seq=updated["version_seq"],
    )
    detail = service.get_version_detail(CODING_RULE_SET_KEY, "coding-deleted")
    content = excel.build_workbook(
        detail, base_version=detail["version"],
        base_content_digest=detail["content_digest"],
    )
    parsed = excel.parse_workbook(content, expected_rule_set_key=CODING_RULE_SET_KEY)
    imported = service.import_draft_snapshot(
        CODING_RULE_SET_KEY, actor=ACTOR, base_version=parsed.base_version,
        base_content_digest=parsed.base_content_digest, entries=parsed.entries,
    )
    assert imported["entries"] == detail["entries"]
    service.publish_draft(CODING_RULE_SET_KEY, actor=ACTOR, version="coding-roundtrip")
    resolved = service.resolve_rule_set_version(CODING_RULE_SET_KEY, "coding-roundtrip")
    assert resolved["deleted_rule_ids"] == ["CR-002"]
    assert "CR-001" in resolved["paused_rule_ids"]
    assert not {"CR-001", "CR-002"}.intersection(resolved["active_rule_ids"])
