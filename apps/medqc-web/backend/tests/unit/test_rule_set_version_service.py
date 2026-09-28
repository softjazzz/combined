"""规则集版本服务合同：内置版本等价、草稿 CAS、发布校验、下线规则（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRuleSetVersion
from app.services import rule_set_version_service as service
from app.services import sichuan_workspace_batch_prepare as prepare_module
from app.services.qc_rule_sets import SICHUAN_RULE_SETS
from app.services.sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


KEY = "luxian_0609_qc_v1"
BUILTIN = "2026-06-09"
ACTOR = "u-manager"
PENDING_RULE = "LX0609-020"  # phase=pending_definition，不可执行
EXCLUDED_RULE = "LX0609-033"  # 客户排除，但 phase_1_target 可执行


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


# ---------------------------------------------------------------------------
# 内置版本与 prepare 现行计算的等价性
# ---------------------------------------------------------------------------


def _native_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
    )


class _Workspace:
    def collect_records(self, **_: Any) -> list[dict[str, Any]]:
        return [{
            "institute_id": "SYN-HOSP", "patient_id": "SYN-PAT", "record_id": "SYN-VISIT",
            "visit_id": "SYN-VISIT", "scope": "final",
            "admission_datetime": "2026-06-01 08:00:00", "discharge_datetime": "2026-06-05 08:00:00",
        }]


class _QCService:
    def assert_sc_rule_source_ready(self, **_: Any) -> dict[str, Any]:
        return {}


def _prepare_filters(rule_set_key: str) -> dict[str, Any]:
    """现行 prepare 在“全选规则”（不传 rule_ids）输入下生成的 filters。"""
    prepared = prepare_module.prepare_workspace_batch_job(
        prepare_module.SichuanWorkspaceBatchJobCreateRequest(rule_set_key=rule_set_key, scope="final"),
        qc_service=_QCService(),  # type: ignore[arg-type]
        workspace=_Workspace(),  # type: ignore[arg-type]
        settings_provider=_native_settings,
    )
    return prepared.create_kwargs["filters"]


@pytest.mark.parametrize("rule_set_key", sorted(SICHUAN_RULE_SETS))
def test_builtin_resolution_equals_current_prepare_computation(rule_set_key, monkeypatch):
    rule_set = SICHUAN_RULE_SETS[rule_set_key]
    # prepare 按 current_version 取版本，需读版本表（conftest 提供空表，即只有内置版本）。
    filters = _prepare_filters(rule_set_key)
    # 内置版本解析不得读数据库：会话工厂置空仍可解析。
    monkeypatch.setattr(service, "SessionLocal", None)
    resolved = service.resolve_rule_set_version(rule_set_key, rule_set.version)

    assert resolved["source"] == "builtin"
    assert resolved["version"] == filters["rule_set_version"] == rule_set.version
    # 顺序与集合都与 prepare 一致。
    assert resolved["active_rule_ids"] == list(filters["rule_ids"])
    assert resolved["paused_rule_ids"] == list(filters["paused_customer_rule_ids"])
    prepared_excluded = (
        set(rule_set.rule_ids) - set(filters["rule_ids"]) - set(filters["paused_customer_rule_ids"])
    )
    assert set(resolved["excluded_rule_ids"]) == prepared_excluded
    if rule_set_key == KEY:
        assert set(resolved["excluded_rule_ids"]) == set(LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS)
        assert set(resolved["active_rule_ids"]) == set(filters["active_customer_rule_ids"])
        assert set(resolved["paused_rule_ids"]) == set(filters["pending_customer_rule_ids"])
    else:
        assert resolved["excluded_rule_ids"] == [] and resolved["paused_rule_ids"] == []


def test_builtin_digest_is_canonical_sha256_of_equivalent_entries(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    resolved = service.resolve_rule_set_version(KEY, BUILTIN)
    entries = sorted(
        [{"rule_id": r, "state": "active"} for r in resolved["active_rule_ids"]]
        + [{"rule_id": r, "state": "paused"} for r in resolved["paused_rule_ids"]]
        + [{"rule_id": r, "state": "offline"} for r in resolved["excluded_rule_ids"]],
        key=lambda item: item["rule_id"],
    )
    expected = hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert resolved["content_digest"] == expected
    # 输入顺序不影响摘要。
    assert service.compute_entries_digest(list(reversed(entries))) == expected
    assert service.resolve_rule_set_version(KEY, BUILTIN)["content_digest"] == expected


def test_empty_table_current_version_is_builtin(sessions):
    assert service.current_version(KEY) == BUILTIN
    assert service.current_version("luxian_0916_qc_v1") == "2026-09-16"
    listed = service.list_versions(KEY)
    assert listed["current_version"] == BUILTIN and listed["draft"] is None
    assert [(item["version"], item["source"], item["is_current"]) for item in listed["items"]] == [
        (BUILTIN, "builtin", True),
    ]


def test_unknown_rule_set_or_version_raises_not_found(sessions):
    with pytest.raises(service.RuleSetVersionNotFound):
        service.resolve_rule_set_version("no_such_key", BUILTIN)
    with pytest.raises(service.RuleSetVersionNotFound):
        service.resolve_rule_set_version(KEY, "2099-01-01")
    with pytest.raises(service.RuleSetVersionNotFound):
        service.resolve_rule_set_version("luxian_0916_qc_v1", "2099-01-01")


# ---------------------------------------------------------------------------
# 草稿
# ---------------------------------------------------------------------------


def _builtin_entries() -> list[dict[str, str]]:
    return service.get_version_detail(KEY, BUILTIN)["entries"]


def _with_state(entries, rule_id, state):
    return [{**item, "state": state} if item["rule_id"] == rule_id else dict(item) for item in entries]


def test_create_draft_copies_base_and_rejects_second_draft(sessions):
    draft = service.create_draft(KEY, actor=ACTOR, note="试运行")
    assert draft["status"] == "draft" and draft["version"] is None
    assert draft["base_version"] == BUILTIN and draft["version_seq"] == 1
    assert draft["entries"] == _builtin_entries()
    assert draft["content_digest"] is None
    with pytest.raises(service.RuleSetVersionConflict) as error:
        service.create_draft(KEY, actor=ACTOR)
    assert error.value.code == "draft_exists"
    assert service.get_draft(KEY)["id"] == draft["id"]


def test_draft_update_cas_and_delete(sessions):
    service.create_draft(KEY, actor=ACTOR)
    entries = _with_state(_builtin_entries(), EXCLUDED_RULE, "active")
    updated = service.update_draft(KEY, actor=ACTOR, version_seq=1, entries=entries)
    assert updated["version_seq"] == 2
    assert {"rule_id": EXCLUDED_RULE, "state": "active"} in updated["entries"]
    with pytest.raises(service.RuleSetVersionConflict) as stale:
        service.update_draft(KEY, actor=ACTOR, version_seq=1, note="旧版本")
    assert stale.value.code == "version_conflict"
    with pytest.raises(service.RuleSetVersionConflict):
        service.delete_draft(KEY, actor=ACTOR, version_seq=1)
    assert service.delete_draft(KEY, actor=ACTOR, version_seq=2) == {"rule_set_key": KEY, "deleted": True}
    with pytest.raises(service.RuleSetVersionNotFound):
        service.get_draft(KEY)


@pytest.mark.parametrize("entries", [
    "not-a-list",
    [{"rule_id": "LX0609-001"}],
    [{"rule_id": "LX0609-001", "state": "enabled"}],
    [{"rule_id": "LX0609-001", "state": "active", "extra": 1}],
    [{"rule_id": "LX0609-001", "state": "active"}, {"rule_id": "lx0609-001 ", "state": "paused"}],
])
def test_draft_entries_structure_validated(sessions, entries):
    with pytest.raises(service.RuleSetVersionInvalid):
        service.create_draft(KEY, actor=ACTOR, entries=entries)


def test_0916_and_other_builtin_only_rule_sets_reject_draft(sessions):
    for key in ("luxian_0916_qc_v1", "sc_content_v1"):
        with pytest.raises(service.RuleSetVersionConflict) as error:
            service.create_draft(key, actor=ACTOR)
        assert error.value.code == "unsupported_rule_set"
        assert service.resolve_rule_set_version(key, SICHUAN_RULE_SETS[key].version)["source"] == "builtin"


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------


def _publish_with(entries, version="2026-09-27.1", **kwargs):
    service.create_draft(KEY, actor=ACTOR, entries=entries)
    return service.publish_draft(KEY, actor=ACTOR, version=version, **kwargs)


def test_publish_writes_digest_and_becomes_current(sessions):
    entries = _with_state(_builtin_entries(), EXCLUDED_RULE, "active")
    published = _publish_with(entries, note="上线 033")
    assert published["status"] == "published" and published["version"] == "2026-09-27.1"
    assert published["content_digest"] == service.compute_entries_digest(entries)
    assert published["published_by"] == ACTOR and published["is_current"] is True
    assert published["note"] == "上线 033"
    assert service.current_version(KEY) == "2026-09-27.1"

    resolved = service.resolve_rule_set_version(KEY, "2026-09-27.1")
    builtin = service.resolve_rule_set_version(KEY, BUILTIN)
    assert resolved["source"] == "published"
    assert resolved["content_digest"] == published["content_digest"]
    assert set(resolved["active_rule_ids"]) == set(builtin["active_rule_ids"]) | {EXCLUDED_RULE}
    assert resolved["paused_rule_ids"] == builtin["paused_rule_ids"]
    assert set(resolved["excluded_rule_ids"]) == set(builtin["excluded_rule_ids"]) - {EXCLUDED_RULE}
    # 目录顺序输出，稳定可重复。
    assert resolved == service.resolve_rule_set_version(KEY, "2026-09-27.1")
    assert service.get_version_detail(KEY, "2026-09-27.1")["resolution"] == resolved


def test_deleted_tombstone_requires_nonactive_current_and_cannot_be_revived(sessions):
    active_rule = next(item["rule_id"] for item in _builtin_entries() if item["state"] == "active")
    with pytest.raises(service.RuleSetVersionInvalid) as active_delete:
        service.create_draft(
            KEY,
            actor=ACTOR,
            entries=_with_state(_builtin_entries(), active_rule, "deleted"),
        )
    assert active_delete.value.code == "delete_validation_failed"

    deleted_entries = _with_state(_builtin_entries(), EXCLUDED_RULE, "deleted")
    published = _publish_with(deleted_entries, version="deleted-v1")
    assert published["deleted_count"] == 1
    resolved = service.resolve_rule_set_version(KEY, "deleted-v1")
    assert resolved["deleted_rule_ids"] == [EXCLUDED_RULE]
    assert EXCLUDED_RULE in resolved["excluded_rule_ids"]
    assert EXCLUDED_RULE not in resolved["offline_rule_ids"]

    draft = service.create_draft(KEY, actor=ACTOR, base_version=BUILTIN)
    assert {item["rule_id"]: item["state"] for item in draft["entries"]}[EXCLUDED_RULE] == "deleted"
    with pytest.raises(service.RuleSetVersionInvalid) as revive:
        service.update_draft(
            KEY,
            actor=ACTOR,
            version_seq=draft["version_seq"],
            entries=_with_state(draft["entries"], EXCLUDED_RULE, "offline"),
        )
    assert revive.value.code == "delete_validation_failed"


def test_publish_requires_full_coverage(sessions):
    entries = [item for item in _builtin_entries() if item["rule_id"] != "LX0609-001"]
    with pytest.raises(service.RuleSetVersionInvalid) as error:
        _publish_with(entries)
    assert error.value.code == "publish_validation_failed"
    assert any("LX0609-001" in problem for problem in error.value.problems)


def test_publish_rejects_rules_outside_master(sessions):
    entries = [*_builtin_entries(), {"rule_id": "LX0609-999", "state": "paused"}]
    with pytest.raises(service.RuleSetVersionInvalid) as error:
        _publish_with(entries)
    assert any("LX0609-999" in problem for problem in error.value.problems)


def test_publish_active_only_for_executable_rules(sessions):
    entries = _with_state(_builtin_entries(), PENDING_RULE, "active")
    with pytest.raises(service.RuleSetVersionInvalid) as error:
        _publish_with(entries)
    assert any(PENDING_RULE in problem and "不可执行" in problem for problem in error.value.problems)
    assert PENDING_RULE not in service.executable_rule_ids(KEY)
    assert EXCLUDED_RULE in service.executable_rule_ids(KEY)


def test_publish_requires_at_least_one_active(sessions):
    entries = [{**item, "state": "paused"} for item in _builtin_entries()]
    with pytest.raises(service.RuleSetVersionInvalid) as error:
        _publish_with(entries)
    assert any("至少需要 1 条 active" in problem for problem in error.value.problems)


def test_publish_duplicate_version_is_409(sessions):
    _publish_with(_builtin_entries(), version="v2")
    for version in ("v2", BUILTIN):
        service.create_draft(KEY, actor=ACTOR)
        with pytest.raises(service.RuleSetVersionConflict) as error:
            service.publish_draft(KEY, actor=ACTOR, version=version)
        assert error.value.code == "version_exists"
        draft = service.get_draft(KEY)
        service.delete_draft(KEY, actor=ACTOR, version_seq=draft["version_seq"])


@pytest.mark.parametrize("version", ["", " ", "-x", "a/b", "__draft__x", "x" * 65])
def test_publish_invalid_version_is_rejected(sessions, version):
    service.create_draft(KEY, actor=ACTOR)
    with pytest.raises(service.RuleSetVersionInvalid):
        service.publish_draft(KEY, actor=ACTOR, version=version)


def test_publish_with_stale_version_seq_is_409(sessions):
    service.create_draft(KEY, actor=ACTOR)
    service.update_draft(KEY, actor=ACTOR, version_seq=1, note="改过")
    with pytest.raises(service.RuleSetVersionConflict) as error:
        service.publish_draft(KEY, actor=ACTOR, version="v3", version_seq=1)
    assert error.value.code == "version_conflict"


def test_published_version_is_immutable(sessions):
    _publish_with(_builtin_entries(), version="v1")
    # 发布后已无草稿，草稿接口不能触达已发布行。
    with pytest.raises(service.RuleSetVersionNotFound):
        service.update_draft(KEY, actor=ACTOR, version_seq=2, note="改已发布")
    with pytest.raises(service.RuleSetVersionNotFound):
        service.delete_draft(KEY, actor=ACTOR, version_seq=2)
    with pytest.raises(service.RuleSetVersionNotFound):
        service.publish_draft(KEY, actor=ACTOR, version="v9")
    # 新草稿不影响已发布内容。
    service.create_draft(KEY, actor=ACTOR, base_version="v1")
    service.update_draft(KEY, actor=ACTOR, version_seq=1, entries=_with_state(_builtin_entries(), "LX0609-001", "offline"))
    assert service.resolve_rule_set_version(KEY, "v1")["content_digest"] == service.compute_entries_digest(
        _builtin_entries()
    )


def test_tampered_published_content_fails_closed(sessions):
    _publish_with(_builtin_entries(), version="v1")
    table = QCRuleSetVersion.__table__
    with sessions() as session, session.begin():
        session.execute(
            table.update().where(table.c.version == "v1").values(
                entries_json=json.dumps(_with_state(_builtin_entries(), "LX0609-001", "offline"),
                                        ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        )
    with pytest.raises(service.RuleSetVersionUnavailable):
        service.resolve_rule_set_version(KEY, "v1")


# ---------------------------------------------------------------------------
# 下线
# ---------------------------------------------------------------------------


def test_retire_rules(sessions):
    _publish_with(_builtin_entries(), version="v1")
    with pytest.raises(service.RuleSetVersionConflict) as current:
        service.retire_version(KEY, "v1", actor=ACTOR)
    assert current.value.code == "current_version"
    with pytest.raises(service.RuleSetVersionConflict) as builtin:
        service.retire_version(KEY, BUILTIN, actor=ACTOR)
    assert builtin.value.code == "builtin_version"
    with pytest.raises(service.RuleSetVersionNotFound):
        service.retire_version(KEY, "v404", actor=ACTOR)

    _publish_with(_with_state(_builtin_entries(), EXCLUDED_RULE, "active"), version="v2")
    assert service.current_version(KEY) == "v2"
    retired = service.retire_version(KEY, "v1", actor=ACTOR)
    assert retired["status"] == "retired" and retired["retired_by"] == ACTOR
    with pytest.raises(service.RuleSetVersionConflict) as again:
        service.retire_version(KEY, "v1", actor=ACTOR)
    assert again.value.code == "already_retired"
    # 已下线版本仍可解析（已建任务继续使用冻结版本），但不再是当前版本。
    assert service.resolve_rule_set_version(KEY, "v1")["source"] == "retired"
    assert service.current_version(KEY) == "v2"
    listed = service.list_versions(KEY)
    assert [(item["version"], item["status"], item["is_current"]) for item in listed["items"]] == [
        ("v2", "published", True), ("v1", "retired", False), (BUILTIN, "builtin", False),
    ]


def test_retire_rejected_for_builtin_only_rule_set(sessions):
    with pytest.raises(service.RuleSetVersionConflict) as error:
        service.retire_version("luxian_0916_qc_v1", "2026-09-16", actor=ACTOR)
    assert error.value.code == "unsupported_rule_set"


def test_database_failure_is_unavailable(monkeypatch):
    def broken():
        raise sa.exc.OperationalError("select", {}, Exception("password=secret host=db"))

    monkeypatch.setattr(service, "SessionLocal", broken)
    with pytest.raises(service.RuleSetVersionUnavailable):
        service.current_version(KEY)
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.RuleSetVersionUnavailable):
        service.create_draft(KEY, actor=ACTOR)
