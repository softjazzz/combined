"""规则集版本读取侧版本化（合同第 8 节，P1-E1c）的金样等价性与发布后端到端场景。

- 金样参考：tests/fixtures/legacy_record_result_read_side.py、legacy_worklist_analytics_events.py
  为读取侧版本化前（7faa55e80）各入口的逐字冻结副本。版本表为空（只有内置版本）时，
  病历池摘要、单病历 DTO、批量导出 DTO、终末复评候选、分析事件与客户安全任务投影
  在同一合成数据上新旧输出逐键相等。
- 端到端：发布“暂停一条规则”的新版本后，新 job 在病历池摘要、单病历 DTO 与导出 DTO 可见，
  该规则为 not_executed；历史 job 仍可见；跨版本按代次取最新。
- 全部使用内存 SQLite 同构表与合成数据，不连真实库。
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.custom_qc_workspace_service as workspace_module
from app.services import rule_set_version_service as version_service
from app.services import sichuan_workspace_batch_prepare as prepare_module
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
    project_customer_safe_batch_job,
)
from app.services.luxian_0609.phase_scope import build_luxian_0609_paused_rule_result
from app.services.qc_rule_sets import SICHUAN_RULE_SETS
from app.services.rule_set_version_read_scope import (
    current_excluded_rule_ids,
    excluded_rule_ids_for_job,
    read_rule_set_versions,
)
from app.services.sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
from app.services.workstation.worklist_service import WorkstationAggregationService
from tests.fixtures import legacy_record_result_read_side as legacy
from tests.fixtures import legacy_worklist_analytics_events as legacy_worklist
from tests.unit.test_rule_set_version_run_chain import _run_prepare

KEY = "luxian_0609_qc_v1"
BUILTIN = SICHUAN_RULE_SETS[KEY].version
NEW_VERSION = "2026-09-27.1"
ACTOR = "u-manager"
ACTIVE_RULE = "LX0609-001"  # 内置版本 active，新版本暂停
EXCLUDED_RULE = "LX0609-033"  # 静态客户排除；新版本改为暂停（不再排除）
OTHER_RULE = "LX0609-002"
ENVELOPE_SCHEMA = "lx0609-record-result-envelope-v1"
DELIVERY_MODE = "canonical_straight_through"


# ---------------------------------------------------------------------------
# SQLite 同构表与服务
# ---------------------------------------------------------------------------


def _tables() -> tuple[sa.Table, sa.Table, sa.MetaData]:
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False, default=""),
        sa.Column("rule_code", sa.String(32), nullable=False, default="LX0609"),
        sa.Column("rule_name", sa.String(200), nullable=False, default="泸县0609质控"),
        sa.Column("scene", sa.String(20), nullable=False, default="final"),
        sa.Column("scope", sa.String(20), nullable=False, default="final"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False, default="{}"),
        sa.Column("record_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False, default="u-syn"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("job_kind", sa.String(20), nullable=False, default="leaf"),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("child_job_ids_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
        sa.Column("family_key", sa.String(64)),
        sa.Column("family_name", sa.String(64)),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("rule_set_key", sa.String(96), nullable=False),
        sa.Column("rule_set_version", sa.String(96), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    return jobs, envelopes, metadata


class _Store:
    def __init__(self, monkeypatch):
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        self.jobs, self.envelopes, metadata = _tables()
        metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        service = object.__new__(CustomQCWorkspaceService)
        service._draft_table = None
        service._batch_job_table = self.jobs
        service._record_result_envelope_table = self.envelopes
        self.service = service
        # 新旧实现都经各自命名空间里的 _session 取会话，两处同时替换。
        monkeypatch.setattr(workspace_module, "_session", self.factory)
        monkeypatch.setattr(legacy, "_session", self.factory)
        monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", lambda: service)

    def add_job(
        self, job_id: str, *, visits: list[str], finished: str | None, created: str,
        status: str = "completed", filters: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None, scope: str = "final",
    ) -> None:
        with self.factory() as session:
            session.execute(self.jobs.insert().values(
                id=job_id, status=status, scope=scope,
                filters_json=json.dumps(filters or {}, ensure_ascii=False),
                record_ids_json=json.dumps(visits),
                summary_json=json.dumps(summary) if summary is not None else None,
                created_at=datetime.fromisoformat(created),
                finished_at=datetime.fromisoformat(finished) if finished else None,
                updated_at=datetime.fromisoformat(finished or created),
            ))
            session.commit()

    def add_envelope(
        self, env_id: str, job_id: str, identity: tuple[str, str, str], items: list[dict[str, Any]],
        *, version: str = BUILTIN, schema: str = ENVELOPE_SCHEMA, updated: str = "2026-09-20T10:00:00",
    ) -> None:
        with self.factory() as session:
            session.execute(self.envelopes.insert().values(
                id=env_id, job_id=job_id, root_job_id=job_id, created_by="u-syn",
                record_id=identity[2], institute_id=identity[0], patient_id=identity[1],
                visit_id=identity[2], rule_set_key=KEY, rule_set_version=version,
                envelope_json=json.dumps({
                    "schema_version": schema, "delivery_mode": DELIVERY_MODE,
                    "record_ref": f"rec_{env_id}", "items": items,
                }, ensure_ascii=False),
                result_count=len(items),
                created_at=datetime.fromisoformat(updated), updated_at=datetime.fromisoformat(updated),
            ))
            session.commit()


def _item(rule_id: str, status: str = "compliant") -> dict[str, Any]:
    return {
        "rule_id": rule_id, "rule_code": rule_id, "status": status, "result_status": status,
        "display_status": status,
        "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
        "conclusion": f"{rule_id} 合成结论",
    }


def _builtin_filters(**extra: Any) -> dict[str, Any]:
    return {"rule_set_key": KEY, "rule_set_version": BUILTIN, **extra}


def _ref(identity: tuple[str, str, str]) -> dict[str, str]:
    return {"institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2]}


# ---------------------------------------------------------------------------
# 等价性：版本表为空时新旧实现逐键相等
# ---------------------------------------------------------------------------

ID_SINGLE = ("SYN-H", "SYN-P1", "SYN-V1")  # 单任务，含静态排除条目
ID_TWO_GEN = ("SYN-H", "SYN-P2", "SYN-V2")  # 两代任务，取较新
ID_OTHER_VERSION = ("SYN-H", "SYN-P3", "SYN-V3")  # 更新的任务属于未知版本，应忽略
ID_RUNNING = ("SYN-H", "SYN-P4", "SYN-V4")  # 任务未完成但 Envelope 已交付
ID_MISSING_ENV = ("SYN-H", "SYN-P5", "SYN-V5")  # 更新的任务缺 Envelope
ID_LEGACY_SUMMARY = ("SYN-H", "SYN-P6", "SYN-V6")  # filters 为空，身份只在 summary
ID_NOT_RUN = ("SYN-H", "SYN-P7", "SYN-V7")
ID_CONFLICT = ("SYN-H", "SYN-P8", "SYN-V8")  # 同代次冲突
ID_INVALID_ENV = ("SYN-H", "SYN-P9", "SYN-V9")  # Envelope 结构非法
ALL_IDS = [
    ID_SINGLE, ID_TWO_GEN, ID_OTHER_VERSION, ID_RUNNING, ID_MISSING_ENV,
    ID_LEGACY_SUMMARY, ID_NOT_RUN, ID_CONFLICT, ID_INVALID_ENV,
]


def _seed_equivalence(store: _Store) -> None:
    snapshot = lambda identity, scene: [  # noqa: E731
        {**_ref(identity), "resolved_scene": scene}
    ]
    store.add_job("job-single", visits=[ID_SINGLE[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00",
                  filters=_builtin_filters(record_scene_snapshot=snapshot(ID_SINGLE, "running")),
                  scope="running")
    store.add_envelope("env-single", "job-single", ID_SINGLE,
                       [_item(ACTIVE_RULE), _item(EXCLUDED_RULE, "not_executed"), _item(OTHER_RULE, "non_compliant")])

    store.add_job("job-gen-old", visits=[ID_TWO_GEN[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-gen-old", "job-gen-old", ID_TWO_GEN, [_item(ACTIVE_RULE, "non_compliant")])
    store.add_job("job-gen-new", visits=[ID_TWO_GEN[2]], finished="2026-09-02T10:00:00",
                  created="2026-09-02T09:00:00",
                  filters=_builtin_filters(record_scene_snapshot=snapshot(ID_TWO_GEN, "final")))
    store.add_envelope("env-gen-new", "job-gen-new", ID_TWO_GEN, [_item(ACTIVE_RULE)])

    store.add_job("job-ov-builtin", visits=[ID_OTHER_VERSION[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters(), scope="running")
    store.add_envelope("env-ov-builtin", "job-ov-builtin", ID_OTHER_VERSION, [_item(OTHER_RULE)])
    store.add_job("job-ov-other", visits=[ID_OTHER_VERSION[2]], finished="2026-09-05T10:00:00",
                  created="2026-09-05T09:00:00",
                  filters={"rule_set_key": KEY, "rule_set_version": "2025-01-01"})
    store.add_envelope("env-ov-other", "job-ov-other", ID_OTHER_VERSION, [_item(OTHER_RULE, "non_compliant")],
                       version="2025-01-01")

    store.add_job("job-running", visits=[ID_RUNNING[2]], finished=None, created="2026-09-03T09:00:00",
                  status="running", filters=_builtin_filters())
    store.add_envelope("env-running", "job-running", ID_RUNNING, [_item(ACTIVE_RULE)],
                       updated="2026-09-03T09:30:00")
    # 仍在排队的终末任务：影响终末复评候选
    store.add_job("job-queued-final", visits=[ID_RUNNING[2]], finished=None, created="2026-09-04T09:00:00",
                  status="queued",
                  filters=_builtin_filters(record_refs=[_ref(ID_RUNNING)],
                                           record_scene_snapshot=snapshot(ID_RUNNING, "final")))

    store.add_job("job-me-old", visits=[ID_MISSING_ENV[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-me-old", "job-me-old", ID_MISSING_ENV, [_item(ACTIVE_RULE)])
    store.add_job("job-me-new", visits=[ID_MISSING_ENV[2]], finished="2026-09-02T10:00:00",
                  created="2026-09-02T09:00:00", filters=_builtin_filters())

    store.add_job("job-legacy", visits=[ID_LEGACY_SUMMARY[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters={},
                  summary={"rule_set_key": KEY, "rule_set_version": BUILTIN})
    store.add_envelope("env-legacy", "job-legacy", ID_LEGACY_SUMMARY,
                       [_item(ACTIVE_RULE), _item(EXCLUDED_RULE, "not_executed")])

    for suffix in ("a", "b"):
        store.add_job(f"job-conflict-{suffix}", visits=[ID_CONFLICT[2]], finished="2026-09-01T10:00:00",
                      created="2026-09-01T09:00:00", filters=_builtin_filters())
        store.add_envelope(f"env-conflict-{suffix}", f"job-conflict-{suffix}", ID_CONFLICT, [_item(ACTIVE_RULE)])

    store.add_job("job-invalid", visits=[ID_INVALID_ENV[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-invalid", "job-invalid", ID_INVALID_ENV, [_item(ACTIVE_RULE)], schema="bad")


@pytest.fixture
def store(monkeypatch):
    s = _Store(monkeypatch)
    yield s
    s.engine.dispose()


@pytest.fixture
def seeded(store):
    _seed_equivalence(store)
    return store


@pytest.mark.parametrize("include_items", [False, True])
@pytest.mark.parametrize("explicit_version", [None, BUILTIN, "2025-01-01"])
def test_pool_summaries_equal_legacy_with_builtin_only(seeded, include_items, explicit_version):
    refs = [_ref(identity) for identity in ALL_IDS]
    kwargs: dict[str, Any] = {"record_refs": refs, "include_items": include_items}
    legacy_kwargs = dict(kwargs)
    if explicit_version is not None:
        kwargs["rule_set_version"] = explicit_version
        legacy_kwargs["rule_set_version"] = explicit_version
    new = seeded.service.build_luxian_0609_completed_record_result_summaries(**kwargs)
    old = legacy.build_luxian_0609_completed_record_result_summaries(seeded.service, **legacy_kwargs)
    assert new == old
    states = {value["status"] for value in new.values()}
    if explicit_version != "2025-01-01":
        # 数据集覆盖 ready / not_run / technical_error 各分支
        assert {"ready", "not_run", "technical_error"} <= states
    else:
        assert states == {"ready", "not_run"}


def test_pool_summaries_empty_refs_do_not_read_version_store(seeded, monkeypatch):
    def _fail(_key):
        raise AssertionError("空病历范围不应读取版本表")

    monkeypatch.setattr(version_service, "known_versions", _fail)
    import app.services.rule_set_version_read_scope as scope_module

    monkeypatch.setattr(scope_module, "known_versions", _fail)
    assert seeded.service.build_luxian_0609_completed_record_result_summaries(record_refs=[]) == {}


@pytest.mark.parametrize("explicit_version", [None, BUILTIN])
def test_bulk_record_dtos_equal_legacy_with_builtin_only(seeded, explicit_version):
    refs = [_ref(identity) for identity in ALL_IDS]
    kwargs: dict[str, Any] = {"record_refs": refs}
    if explicit_version is not None:
        kwargs["rule_set_version"] = explicit_version
    new = seeded.service.build_latest_luxian_0609_record_result_dtos(**kwargs)
    old = legacy.build_latest_luxian_0609_record_result_dtos(seeded.service, **kwargs)
    assert new == old
    assert new[ID_SINGLE]["state"] == "ready"
    assert [item["rule_id"] for item in new[ID_SINGLE]["items"]] == [ACTIVE_RULE, OTHER_RULE]


@pytest.mark.parametrize("identity", ALL_IDS)
@pytest.mark.parametrize("expected_rule_ids", [None, [ACTIVE_RULE, EXCLUDED_RULE, OTHER_RULE]])
def test_single_record_dto_equal_legacy_with_builtin_only(seeded, identity, expected_rule_ids):
    kwargs = {
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "expected_rule_ids": expected_rule_ids,
    }
    new = seeded.service.build_latest_single_record_result_dto(**kwargs)
    old = legacy.build_latest_single_record_result_dto(seeded.service, **kwargs)
    assert new == old


def test_single_record_dto_rejects_missing_identity_like_legacy(seeded):
    kwargs = {"institute_id": "", "patient_id": "p", "visit_id": "v"}
    with pytest.raises(ValueError) as new_error:
        seeded.service.build_latest_single_record_result_dto(**kwargs)
    with pytest.raises(ValueError) as old_error:
        legacy.build_latest_single_record_result_dto(seeded.service, **kwargs)
    assert str(new_error.value) == str(old_error.value)


def test_terminal_reevaluation_candidates_equal_legacy_with_builtin_only(seeded):
    refs = [_ref(identity) for identity in ALL_IDS]
    new = seeded.service.find_terminal_reevaluation_candidates(record_refs=refs)
    old = legacy.find_terminal_reevaluation_candidates(seeded.service, record_refs=refs)
    assert new == old
    assert [ref.visit_id for ref in new] == [ID_SINGLE[2], ID_OTHER_VERSION[2]]


@pytest.mark.parametrize("job_id", [None, "job-single"])
def test_analytics_events_equal_legacy_with_builtin_only(seeded, job_id):
    service = WorkstationAggregationService(session_factory=seeded.factory)
    records = {
        identity: {"department": "合成科室", "attending_physician": "合成医生"} for identity in ALL_IDS
    }
    kwargs = {
        "records_by_identity": records, "completed_from": None, "completed_to": None, "job_id": job_id,
    }
    with seeded.factory() as session:
        new = service._load_luxian_0609_analytics_events(session, **kwargs)
    with seeded.factory() as session:
        old = legacy_worklist._load_luxian_0609_analytics_events(service, session, **kwargs)
    assert new == old
    assert new[0]


def _customer_job(filters: dict[str, Any], *items: dict[str, Any], review: bool = False) -> dict[str, Any]:
    summary: dict[str, Any] = {"total_records": 1}
    if review:
        summary["review_report"] = {"findings": [
            {"rule_id": rule_id, "record_id": "record-1", "original_status": "compliant"}
            for rule_id in (ACTIVE_RULE, EXCLUDED_RULE)
        ]}
    return {
        "id": "job-lx-customer", "status": "completed", "filters": filters, "summary": summary,
        "items": list(items),
        "rule_results": [{"rule_code": EXCLUDED_RULE, "items": []}, {"rule_code": ACTIVE_RULE, "items": []}],
    }


def _customer_item(rule_id: str) -> dict[str, Any]:
    return {
        "record_id": "record-1", "rule_id": rule_id, "status": "compliant",
        "is_compliant": True, "reason_code": "within_deadline",
    }


@pytest.mark.parametrize("review", [False, True])
@pytest.mark.parametrize("with_children", [False, True])
def test_customer_safe_batch_projection_equal_legacy_for_historical_job(review, with_children):
    job = _customer_job(
        _builtin_filters(), _customer_item(ACTIVE_RULE), _customer_item(EXCLUDED_RULE), review=review,
    )
    if with_children:
        child = copy.deepcopy(job)
        child["id"] = "job-lx-child"
        job["child_jobs"] = [child]
    key = customer_safe_projection_key()
    new = project_customer_safe_batch_job(copy.deepcopy(job), hmac_key=key)
    old = legacy.project_customer_safe_batch_job(copy.deepcopy(job), hmac_key=key)
    assert new == old
    assert [item["rule_id"] for item in new["items"]] == [ACTIVE_RULE]


def test_read_versions_and_exclusion_defaults_with_empty_store():
    assert read_rule_set_versions(KEY) == frozenset({BUILTIN})
    assert read_rule_set_versions(KEY, "x") == frozenset({"x"})
    assert read_rule_set_versions(KEY, "") == frozenset()
    assert version_service.known_versions("luxian_0916_qc_v1") == frozenset(
        {SICHUAN_RULE_SETS["luxian_0916_qc_v1"].version}
    )
    assert excluded_rule_ids_for_job({"filters": _builtin_filters()}) == LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    assert excluded_rule_ids_for_job({}) == LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    assert excluded_rule_ids_for_job(
        {"rule_set_content_digest": "d" * 64, "excluded_customer_rule_ids": ["lx0609-002"]}
    ) == frozenset({"LX0609-002"})
    assert current_excluded_rule_ids(KEY) == LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


def test_known_versions_store_failure_fails_closed(monkeypatch):
    class _Broken:
        def __enter__(self):
            raise sa.exc.OperationalError("select", {}, Exception("down"))

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(version_service, "SessionLocal", lambda: _Broken())
    with pytest.raises(version_service.RuleSetVersionUnavailable):
        version_service.known_versions(KEY)
    # 非版本化规则集不读库
    assert version_service.known_versions("sc_content_v1") == frozenset(
        {SICHUAN_RULE_SETS["sc_content_v1"].version}
    )


# ---------------------------------------------------------------------------
# 端到端（合成）：发布暂停一条规则的新版本
# ---------------------------------------------------------------------------


def _publish_new_version() -> dict[str, Any]:
    """新版本：暂停 ACTIVE_RULE，并把静态排除的 EXCLUDED_RULE 改为暂停（不再排除）。"""
    draft = version_service.create_draft(KEY, actor=ACTOR)
    entries = [
        {**item, "state": "paused"} if item["rule_id"] in {ACTIVE_RULE, EXCLUDED_RULE} else item
        for item in draft["entries"]
    ]
    version_service.update_draft(KEY, actor=ACTOR, version_seq=draft["version_seq"], entries=entries)
    return version_service.publish_draft(KEY, actor=ACTOR, version=NEW_VERSION)


ID_E2E_NEW = ("SYN-H", "SYN-E1", "SYN-EV1")  # 历史 job 较旧，新版本 job 较新
ID_E2E_HIST = ("SYN-H", "SYN-E2", "SYN-EV2")  # 只有历史 job
ID_E2E_BACK = ("SYN-H", "SYN-E3", "SYN-EV3")  # 新版本 job 较旧，内置版本 job 较新


def test_published_version_results_visible_across_read_side(store):
    published = _publish_new_version()
    assert version_service.known_versions(KEY) == frozenset({BUILTIN, NEW_VERSION})

    # 新 job 的 filters 取自真实 prepare（冻结新版本号、摘要、排除与暂停集合）。
    new_filters = _run_prepare(
        prepare_module, {"rule_set_key": KEY, "scope": "running"}, None, "running",
    ).create_kwargs["filters"]
    assert new_filters["rule_set_version"] == NEW_VERSION
    assert new_filters["rule_set_content_digest"] == published["content_digest"]
    assert ACTIVE_RULE in new_filters["paused_customer_rule_ids"]
    assert EXCLUDED_RULE not in new_filters["excluded_customer_rule_ids"]

    paused_item = build_luxian_0609_paused_rule_result(ACTIVE_RULE)
    excluded_now_paused = {
        "rule_id": EXCLUDED_RULE, "rule_code": EXCLUDED_RULE, "status": "not_executed",
        "result_status": "not_executed", "display_status": "not_executed", "is_compliant": None,
    }
    new_items = [paused_item, excluded_now_paused, _item(OTHER_RULE, "non_compliant")]
    hist_items = [_item(ACTIVE_RULE), _item(EXCLUDED_RULE, "not_executed"), _item(OTHER_RULE)]

    store.add_job("hist-1", visits=[ID_E2E_NEW[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-hist-1", "hist-1", ID_E2E_NEW, hist_items)
    store.add_job("new-1", visits=[ID_E2E_NEW[2]], finished="2026-09-28T10:00:00",
                  created="2026-09-28T09:00:00", filters=new_filters)
    store.add_envelope("env-new-1", "new-1", ID_E2E_NEW, new_items, version=NEW_VERSION)

    store.add_job("hist-2", visits=[ID_E2E_HIST[2]], finished="2026-09-01T10:00:00",
                  created="2026-09-01T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-hist-2", "hist-2", ID_E2E_HIST, hist_items)

    store.add_job("new-3", visits=[ID_E2E_BACK[2]], finished="2026-09-28T10:00:00",
                  created="2026-09-28T09:00:00", filters=new_filters)
    store.add_envelope("env-new-3", "new-3", ID_E2E_BACK, new_items, version=NEW_VERSION)
    store.add_job("hist-3", visits=[ID_E2E_BACK[2]], finished="2026-09-29T10:00:00",
                  created="2026-09-29T09:00:00", filters=_builtin_filters())
    store.add_envelope("env-hist-3", "hist-3", ID_E2E_BACK, hist_items)

    refs = [_ref(identity) for identity in (ID_E2E_NEW, ID_E2E_HIST, ID_E2E_BACK)]
    service = store.service

    # 病历池摘要：新 job 被选中；历史 job 仍可见；跨版本按代次取最新。
    summaries = service.build_luxian_0609_completed_record_result_summaries(
        record_refs=refs, include_items=True,
    )
    assert summaries[ID_E2E_NEW]["status"] == "ready"
    assert summaries[ID_E2E_NEW]["root_job_id"] == "new-1"
    new_statuses = {item["rule_id"]: item["status"] for item in summaries[ID_E2E_NEW]["items"]}
    assert new_statuses[ACTIVE_RULE] == "not_executed"
    assert new_statuses[EXCLUDED_RULE] == "not_executed"  # 新版本不再排除：以 job filters 为准
    assert summaries[ID_E2E_HIST]["root_job_id"] == "hist-2"
    assert EXCLUDED_RULE not in {item["rule_id"] for item in summaries[ID_E2E_HIST]["items"]}
    assert summaries[ID_E2E_BACK]["root_job_id"] == "hist-3"

    # 单病历 DTO
    single_new = service.build_latest_single_record_result_dto(
        institute_id=ID_E2E_NEW[0], patient_id=ID_E2E_NEW[1], visit_id=ID_E2E_NEW[2],
    )
    assert single_new["state"] == "ready"
    assert single_new["job_id"] == "new-1"
    assert single_new["rule_set_version"] == NEW_VERSION
    single_statuses = {item["rule_id"]: item["status"] for item in single_new["items"]}
    assert single_statuses[ACTIVE_RULE] == "not_executed"
    assert EXCLUDED_RULE in single_statuses
    single_hist = service.build_latest_single_record_result_dto(
        institute_id=ID_E2E_HIST[0], patient_id=ID_E2E_HIST[1], visit_id=ID_E2E_HIST[2],
    )
    assert single_hist["job_id"] == "hist-2"
    assert single_hist["rule_set_version"] == BUILTIN
    assert EXCLUDED_RULE not in {item["rule_id"] for item in single_hist["items"]}
    assert single_hist["expected_rule_count"] == single_new["expected_rule_count"] - 1
    single_back = service.build_latest_single_record_result_dto(
        institute_id=ID_E2E_BACK[0], patient_id=ID_E2E_BACK[1], visit_id=ID_E2E_BACK[2],
    )
    assert single_back["job_id"] == "hist-3"
    # 显式版本参数保留兼容：只在该版本内选择。
    pinned = service.build_latest_single_record_result_dto(
        institute_id=ID_E2E_NEW[0], patient_id=ID_E2E_NEW[1], visit_id=ID_E2E_NEW[2],
        rule_set_version=BUILTIN,
    )
    assert pinned["job_id"] == "hist-1"
    assert pinned["rule_set_version"] == BUILTIN

    # 批量导出 DTO
    dtos = service.build_latest_luxian_0609_record_result_dtos(record_refs=refs)
    assert dtos[ID_E2E_NEW]["root_job_id"] == "new-1"
    assert dtos[ID_E2E_NEW]["rule_set_version"] == NEW_VERSION
    dto_statuses = {item["rule_id"]: item["status"] for item in dtos[ID_E2E_NEW]["items"]}
    assert dto_statuses[ACTIVE_RULE] == "not_executed"
    assert EXCLUDED_RULE in dto_statuses
    assert dtos[ID_E2E_HIST]["rule_set_version"] == BUILTIN
    assert EXCLUDED_RULE not in {item["rule_id"] for item in dtos[ID_E2E_HIST]["items"]}
    assert dtos[ID_E2E_BACK]["root_job_id"] == "hist-3"
    assert dtos[ID_E2E_NEW]["expected_rule_count"] == single_new["expected_rule_count"]

    # 分析事件包含新版本 job
    analytics = WorkstationAggregationService(session_factory=store.factory)
    with store.factory() as session:
        events, _ = analytics._load_luxian_0609_analytics_events(
            session,
            records_by_identity={identity: {"department": "合成科室"} for identity in (ID_E2E_NEW,)},
            completed_from=None, completed_to=None, job_id=None,
        )
    assert {event["root_job_id"] for event in events} == {"hist-1", "new-1"}

    # 客户安全任务投影：新 job 以 filters 冻结的排除集合为准。
    key = customer_safe_projection_key()
    projected_new = project_customer_safe_batch_job(
        _customer_job(new_filters, _customer_item(ACTIVE_RULE), _customer_item(EXCLUDED_RULE)), hmac_key=key,
    )
    assert {item["rule_id"] for item in projected_new["items"]} == {ACTIVE_RULE, EXCLUDED_RULE}
    assert projected_new["rule_set_version"] == NEW_VERSION

    # 规则目录按当前版本隐藏排除条目：新版本不再排除 EXCLUDED_RULE。
    assert EXCLUDED_RULE not in current_excluded_rule_ids(KEY)
