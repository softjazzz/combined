"""人工缺陷审核的隔离 PostgreSQL 集成验证。

- 仅在显式声明非生产库 medqc_v36_validation_20260924 时运行，否则整体 skip。
- qc_defects 与 qc_defect_history 为真实 PG 行，字段参照 task_manual_defect_service 的写入。
- 所有合成行带 institute_id='SYN-V36-RR' 与 SYN- 前缀，测试结束在 finally 中清理并断言残留为 0。
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.services import manual_defect_review_service as mds

TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260926_000057"
INSTITUTE = "SYN-V36-RR"


@pytest.fixture
def pg_engine():
    if os.getenv("MEDQC_PG_RACE_NONPROD_DB") != TARGET_DB:
        pytest.skip("explicit non-production database opt-in required")
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next(
        (line.split("=", 1)[1].strip().strip("\"'") for line in env_path.read_text(encoding="utf-8").splitlines()
         if line.startswith("DATABASE_URL=")),
        "",
    )
    if not raw_url:
        pytest.skip("backend/.env has no PostgreSQL connection")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL is required")
    engine = create_engine(
        url.set(database=TARGET_DB),
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=qc,sys,cdm,public,legacy"},
    )
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == TARGET_DB
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == TARGET_REVISION
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == "qc"
        yield engine
    finally:
        engine.dispose()


class DefectWorld:
    """登记本测试写入的缺陷与历史，便于精确清理与残留核对。"""

    def __init__(self, engine):
        self.engine = engine
        self.marker = uuid.uuid4().hex[:16]
        self.defect_ids: list[str] = []
        self._seq = 0

    def actor(self, tag: str) -> str:
        return f"SYN-{tag}-{self.marker[:10]}"

    def add_defect(self, *, created_by: str, origin: str = "manual",
                   source_key: str | None = "task_assigned_qc", identity_version: int | None = 1,
                   manual_review_status: str | None = "pending") -> str:
        """按人工缺陷创建的字段写入缺陷与 manual_create 历史（自动缺陷不写历史）。"""
        defect_id = str(uuid.uuid4())
        task_id, task_record_id, job_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        suffix = uuid.uuid4().hex[:12]
        # 递增时间，保证列表排序稳定且本测试行位于最新
        self._seq += 1
        now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(microseconds=self._seq)
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO qc.qc_defects
                    (id, record_id, identity_version, source_key, institute_id, patient_id, visit_id,
                     rule_name, description, severity, suggestion, evidence, category, status,
                     origin, manual_review_status, manual_created_by, deduct_score,
                     created_at, updated_at)
                VALUES (:id, :record_id, :iv, :source_key, :inst, :pid, :vid,
                        'SYN 人工缺陷', 'SYN-V36-RR 合成描述', 'warning', 'SYN 建议', 'SYN 证据',
                        :category, 'pending', :origin, :mrs, :created_by, 0, :now, :now)
            """), {"id": defect_id, "record_id": task_record_id, "iv": identity_version,
                   "source_key": source_key, "inst": INSTITUTE,
                   "pid": f"SYN-P-{self.marker}-{suffix}", "vid": f"SYN-V-{self.marker}-{suffix}",
                   "category": "manual" if origin == "manual" else "auto", "origin": origin,
                   "mrs": manual_review_status, "created_by": created_by if origin == "manual" else None,
                   "now": now})
            if origin == "manual":
                conn.execute(text("""
                    INSERT INTO qc.qc_defect_history (id, defect_id, action, actor_id, details, created_at)
                    VALUES (:id, :defect_id, 'manual_create', :actor, :details, :now)
                """), {"id": str(uuid.uuid4()), "defect_id": defect_id, "actor": created_by,
                       "details": json.dumps({"task_id": task_id, "task_record_id": task_record_id,
                                              "run_number": 1, "job_id": job_id},
                                             ensure_ascii=False, sort_keys=True),
                       "now": now})
        self.defect_ids.append(defect_id)
        return defect_id

    def defect(self, defect_id: str) -> dict:
        with self.engine.connect() as conn:
            return dict(conn.execute(text("SELECT * FROM qc.qc_defects WHERE id = :id"),
                                     {"id": defect_id}).mappings().one())

    def history(self, defect_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(text("""
                SELECT * FROM qc.qc_defect_history WHERE defect_id = :id ORDER BY created_at, id
            """), {"id": defect_id}).mappings()]

    def cleanup(self) -> None:
        params = {"ids": self.defect_ids or [""], "inst": INSTITUTE, "like": f"SYN-P-{self.marker}-%"}
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM qc.qc_defect_history
                WHERE defect_id = ANY(:ids)
                   OR defect_id IN (SELECT id FROM qc.qc_defects WHERE institute_id = :inst AND patient_id LIKE :like)
            """), params)
            conn.execute(text("""
                DELETE FROM qc.qc_defects
                WHERE id = ANY(:ids) OR (institute_id = :inst AND patient_id LIKE :like)
            """), params)

    def residual(self) -> dict[str, int]:
        params = {"ids": self.defect_ids or [""], "inst": INSTITUTE, "like": f"SYN-P-{self.marker}-%"}
        with self.engine.connect() as conn:
            return {
                "qc_defects": conn.execute(text("""
                    SELECT count(*) FROM qc.qc_defects
                    WHERE id = ANY(:ids) OR (institute_id = :inst AND patient_id LIKE :like)
                """), params).scalar_one(),
                "qc_defect_history": conn.execute(text(
                    "SELECT count(*) FROM qc.qc_defect_history WHERE defect_id = ANY(:ids)"
                ), params).scalar_one(),
            }


@pytest.fixture
def world(pg_engine, monkeypatch):
    syn = DefectWorld(pg_engine)
    monkeypatch.setattr(mds, "SessionLocal", sessionmaker(bind=pg_engine))
    try:
        yield syn
    finally:
        syn.cleanup()
        residual = syn.residual()
        print(f"\n[清理残留] {residual}")
        assert all(count == 0 for count in residual.values()), residual


def _review_actions(history: list[dict]) -> list[str]:
    return [row["action"] for row in history if row["action"].startswith("manual_review_")]


# ---------------------------------------------------------------------------
# 场景 1：通过/驳回，历史同事务写入
# ---------------------------------------------------------------------------


def test_approve_and_reject_write_history(world):
    creator, reviewer = world.actor("C"), world.actor("R")
    approve_id = world.add_defect(created_by=creator)
    reject_id = world.add_defect(created_by=creator)

    result = mds.review_manual_defect(defect_id=approve_id, reviewer_id=reviewer, decision="approved")
    assert result["manual_review_status"] == "approved" and result["previous_status"] == "pending"
    row = world.defect(approve_id)
    assert row["manual_review_status"] == "approved"
    # 不改整改状态，不写整改审核旧列
    assert row["status"] == "pending" and row["approved_at"] is None and row["approved_by"] is None
    history = world.history(approve_id)
    assert [item["action"] for item in history] == ["manual_create", "manual_review_approved"]
    review = history[-1]
    assert review["id"] == result["history_id"] and review["actor_id"] == reviewer
    assert json.loads(review["details"]) == {"reason": None, "reviewer": reviewer,
                                             "from_status": "pending", "to_status": "approved"}

    for blank in (None, "", "   "):
        with pytest.raises(mds.ManualDefectReviewInvalid):
            mds.review_manual_defect(defect_id=reject_id, reviewer_id=reviewer, decision="rejected", reason=blank)
    assert world.defect(reject_id)["manual_review_status"] == "pending"
    assert _review_actions(world.history(reject_id)) == []

    rejected = mds.review_manual_defect(defect_id=reject_id, reviewer_id=reviewer,
                                        decision="rejected", reason="  SYN 证据不足  ")
    assert rejected["manual_review_status"] == "rejected" and rejected["reason"] == "SYN 证据不足"
    row = world.defect(reject_id)
    assert row["manual_review_status"] == "rejected"
    assert row["rejected_at"] is None and row["rejected_by"] is None and row["reject_reason"] is None
    history = world.history(reject_id)
    assert _review_actions(history) == ["manual_review_rejected"]
    assert json.loads(history[-1]["details"])["reason"] == "SYN 证据不足"

    # 已审核后再次审核 → not_pending，且不追加历史
    with pytest.raises(mds.ManualDefectReviewConflict) as exc:
        mds.review_manual_defect(defect_id=approve_id, reviewer_id=reviewer, decision="rejected", reason="SYN")
    assert exc.value.code == "not_pending"
    assert _review_actions(world.history(approve_id)) == ["manual_review_approved"]


def test_history_failure_rolls_back_status(world, monkeypatch):
    """历史写入失败时状态更新整笔回滚（同事务）。"""
    creator, reviewer = world.actor("C"), world.actor("R")
    defect_id = world.add_defect(created_by=creator)

    def broken_history(*args, **kwargs):
        raise OperationalError("SYN 注入历史写入失败", {}, Exception("synthetic"))

    monkeypatch.setattr(mds, "_append_review_history", broken_history)
    with pytest.raises(mds.ManualDefectReviewUnavailable):
        mds.review_manual_defect(defect_id=defect_id, reviewer_id=reviewer, decision="approved")
    assert world.defect(defect_id)["manual_review_status"] == "pending"
    assert _review_actions(world.history(defect_id)) == []


# ---------------------------------------------------------------------------
# 场景 2：两个审核人并发审核同一 pending 缺陷
# ---------------------------------------------------------------------------


def test_concurrent_reviewers_only_one_wins(world):
    creator = world.actor("C")
    reviewers = [world.actor("RA"), world.actor("RB")]
    rounds = []
    for _ in range(5):
        defect_id = world.add_defect(created_by=creator)
        barrier = threading.Barrier(2)

        def race(reviewer, defect_id=defect_id, barrier=barrier):
            barrier.wait(timeout=5)
            try:
                return ("ok", mds.review_manual_defect(defect_id=defect_id, reviewer_id=reviewer,
                                                       decision="approved"))
            except mds.ManualDefectReviewConflict as exc:
                return ("conflict", exc.code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(race, reviewer) for reviewer in reviewers]
            outcomes = [future.result(timeout=30) for future in futures]
        rounds.append([kind for kind, _ in outcomes])
        assert sorted(kind for kind, _ in outcomes) == ["conflict", "ok"], outcomes
        assert [value for kind, value in outcomes if kind == "conflict"] == ["not_pending"]
        winner = next(value for kind, value in outcomes if kind == "ok")
        history = world.history(defect_id)
        assert _review_actions(history) == ["manual_review_approved"]
        assert history[-1]["actor_id"] == winner["reviewer_id"]
        assert world.defect(defect_id)["manual_review_status"] == "approved"
    print(f"\n[并发] 5 轮结果：{rounds}")


# ---------------------------------------------------------------------------
# 场景 3：自审拒绝；自动缺陷与旧行 404
# ---------------------------------------------------------------------------


def test_self_review_auto_and_legacy_rejected(world):
    creator, reviewer = world.actor("C"), world.actor("R")
    manual_id = world.add_defect(created_by=creator)
    auto_id = world.add_defect(created_by=creator, origin="auto", source_key="luxian_0609",
                               manual_review_status=None)
    legacy_id = world.add_defect(created_by=creator, source_key=None, identity_version=None)

    with pytest.raises(mds.ManualDefectReviewForbidden):
        mds.review_manual_defect(defect_id=manual_id, reviewer_id=creator, decision="approved")
    for defect_id in (auto_id, legacy_id, str(uuid.uuid4())):
        with pytest.raises(mds.ManualDefectReviewNotFound):
            mds.review_manual_defect(defect_id=defect_id, reviewer_id=reviewer, decision="approved")

    assert world.defect(manual_id)["manual_review_status"] == "pending"
    assert world.defect(auto_id)["manual_review_status"] is None
    assert world.defect(legacy_id)["manual_review_status"] == "pending"
    for defect_id in (manual_id, auto_id, legacy_id):
        assert _review_actions(world.history(defect_id)) == []


# ---------------------------------------------------------------------------
# 场景 4：pending 计数与列表 total 一致
# ---------------------------------------------------------------------------


def _all_items(review_status: str) -> tuple[int, list[dict]]:
    first = mds.list_manual_defects(review_status=review_status, page=1, page_size=100)
    items = list(first["items"])
    page = 2
    while len(items) < first["total"]:
        items.extend(mds.list_manual_defects(review_status=review_status, page=page, page_size=100)["items"])
        page += 1
    return first["total"], items


def test_pending_count_matches_list_total(world):
    creator, reviewer = world.actor("C"), world.actor("R")
    base_count = mds.count_pending_manual_defects()
    base_total, _ = _all_items("pending")
    base_approved, _ = _all_items("approved")
    assert base_count == base_total

    pending_ids = [world.add_defect(created_by=creator) for _ in range(3)]
    approved_id = world.add_defect(created_by=creator, manual_review_status="approved")
    world.add_defect(created_by=creator, origin="auto", source_key="luxian_0609", manual_review_status=None)
    world.add_defect(created_by=creator, source_key=None, identity_version=None)  # 旧行不计入

    count = mds.count_pending_manual_defects()
    total, items = _all_items("pending")
    assert count == total == base_count + 3
    mine = [item for item in items if item["institute_id"] == INSTITUTE
            and item["patient_id"].startswith(f"SYN-P-{world.marker}-")]
    assert sorted(item["id"] for item in mine) == sorted(pending_ids)
    for item in mine:
        assert item["manual_created_by"] == creator and item["run_number"] == 1
        assert item["task_id"] and item["task_record_id"]
        assert "evidence" not in item
    approved_total, approved_items = _all_items("approved")
    assert approved_total == base_approved + 1
    assert approved_id in {item["id"] for item in approved_items}

    mds.review_manual_defect(defect_id=pending_ids[0], reviewer_id=reviewer, decision="approved")
    count = mds.count_pending_manual_defects()
    total, _ = _all_items("pending")
    assert count == total == base_count + 2
    print(f"\n[计数] 基线 pending={base_count}，写入后={base_count + 3}，审核一条后={count}")
