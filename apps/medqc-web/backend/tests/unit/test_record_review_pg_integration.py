"""病历初审/复审的隔离 PostgreSQL 集成验证。

- 仅在显式声明非生产库 medqc_v36_validation_20260924 时运行，否则整体 skip。
- 任务、任务病历、受领运行、批任务、Envelope 与审核决定均为真实 PG 行；
  只替换结果读取器 get_task_qc_run_record_result（其 Canonical 核验另有测试），
  由它按内存中登记的真实运行返回 result_state=available 与对应 job_id。
- 所有合成行带 institute_id='SYN-V36-RR' 与 SYN- 前缀，测试结束在 finally 中清理并断言残留为 0。
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.services import record_review_service as rr
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.task_qc_run_service import TaskQCRunForbidden, TaskQCRunNotFound

TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260926_000057"
INSTITUTE = "SYN-V36-RR"
RULE_VERSION = "SYN-V36-RR-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
            assert conn.execute(text("SELECT to_regclass('qc.qc_record_reviews') IS NOT NULL")).scalar_one()
        yield engine
    finally:
        engine.dispose()


class SynWorld:
    """登记本测试写入的全部合成行，便于精确清理与残留核对。"""

    def __init__(self, engine):
        self.engine = engine
        self.marker = uuid.uuid4().hex[:16]
        self.task_ids: list[str] = []
        self.job_ids: list[str] = []
        # (task_id, run_number) -> (job_id, triggered_by)，供替换后的结果读取器使用
        self.runs: dict[tuple[str, int], tuple[str, str]] = {}

    def actor(self, tag: str) -> str:
        return f"SYN-{tag}-{self.marker[:10]}"

    def add_task(self, *, scene: str = "running", status: str = "in_progress") -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO qc.qc_tasks
                    (id, task_number, task_name, task_type, status, progress, total_records,
                     completed_records, created_at, updated_at, attempt_count,
                     scene, rule_set_key, rule_set_version)
                VALUES (:id, :number, 'SYN-V36-RR 病历审核', 'one_time', :status, 0, 0, 0,
                        :now, :now, 0, :scene, :rule_key, :rule_version)
            """), {"id": task_id, "number": f"SYN-{uuid.uuid4().hex[:24]}", "status": status,
                   "now": now, "scene": scene, "rule_key": LUXIAN_0609_RULE_SET_KEY,
                   "rule_version": RULE_VERSION})
        self.task_ids.append(task_id)
        return task_id

    def add_records(self, task_id: str, assignee: str, count: int = 1,
                    status: str = "in_progress") -> list[tuple[str, tuple[str, str, str]]]:
        now = datetime.now(timezone.utc)
        rows = []
        for _ in range(count):
            record_id = str(uuid.uuid4())
            suffix = uuid.uuid4().hex[:12]
            identity = (INSTITUTE, f"SYN-P-{self.marker}-{suffix}", f"SYN-V-{self.marker}-{suffix}")
            rows.append({"id": record_id, "task_id": task_id, "assignee": assignee, "status": status,
                         "now": now, "inst": identity[0], "pid": identity[1], "vid": identity[2]})
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO qc.qc_task_records
                    (id, task_id, record_id, assignee_id, status, defect_count, created_at,
                     institute_id, patient_id, visit_id)
                VALUES (:id, :task_id, :id, :assignee, :status, 0, :now, :inst, :pid, :vid)
            """), rows)
        return [(row["id"], (row["inst"], row["pid"], row["vid"])) for row in rows]

    def add_record(self, task_id: str, assignee: str) -> tuple[str, tuple[str, str, str]]:
        return self.add_records(task_id, assignee, 1)[0]

    def add_run(self, task_id: str, actor: str, run_number: int) -> str:
        """写入真实 root 批任务与 assigned 运行。"""
        job_id = str(uuid.uuid4())
        now = _now()
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO qc.custom_qc_batch_jobs
                    (id, draft_id, rule_code, rule_name, scene, scope, status, filters_json,
                     record_ids_json, created_by, created_at, updated_at, total_records,
                     success_count, failed_count, issue_records, compliant_records,
                     total_tokens, total_processing_time)
                VALUES (:id, 'SYN-V36-RR-draft', 'SYN-RR', 'SYN-V36-RR 合成任务', 'running',
                        'task', 'completed', '{}', '[]', :actor, :now, :now, 0, 0, 0, 0, 0, 0, 0)
            """), {"id": job_id, "actor": actor, "now": now})
            conn.execute(text("""
                INSERT INTO qc.task_qc_runs (task_id, run_number, job_id, triggered_by, created_at, run_scope)
                VALUES (:task_id, :run_number, :job_id, :actor, :now, 'assigned')
            """), {"task_id": task_id, "run_number": run_number, "job_id": job_id,
                   "actor": actor, "now": now})
        self.job_ids.append(job_id)
        self.runs[(task_id, run_number)] = (job_id, actor)
        return job_id

    def add_envelopes(self, job_id: str, actor: str,
                      records: list[tuple[str, tuple[str, str, str]]]) -> list[str]:
        now = _now()
        rows = [{
            "id": str(uuid.uuid4()), "job_id": job_id, "actor": actor, "record_id": record_id,
            "inst": identity[0], "pid": identity[1], "vid": identity[2],
            "rule_key": LUXIAN_0609_RULE_SET_KEY, "rule_version": RULE_VERSION, "now": now,
        } for record_id, identity in records]
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO qc.luxian_0609_record_result_envelopes
                    (id, job_id, root_job_id, created_by, record_id, institute_id, patient_id,
                     visit_id, rule_set_key, rule_set_version, envelope_json, result_count,
                     created_at, updated_at)
                VALUES (:id, :job_id, :job_id, :actor, :record_id, :inst, :pid, :vid,
                        :rule_key, :rule_version, '{}', 0, :now, :now)
            """), rows)
        return [row["id"] for row in rows]

    def add_envelope(self, job_id: str, actor: str, record: tuple[str, tuple[str, str, str]]) -> str:
        return self.add_envelopes(job_id, actor, [record])[0]

    def rewrite_envelope(self, job_id: str, actor: str, record: tuple[str, tuple[str, str, str]]) -> str:
        """模拟重试/父任务刷新：同 job 先删后插，行 id 变化。"""
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM qc.luxian_0609_record_result_envelopes
                WHERE root_job_id = :job_id AND record_id = :record_id
            """), {"job_id": job_id, "record_id": record[0]})
        return self.add_envelope(job_id, actor, record)

    def reviews(self, identity: tuple[str, str, str]) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(text("""
                SELECT * FROM qc.qc_record_reviews
                WHERE institute_id = :inst AND patient_id = :pid AND visit_id = :vid
                ORDER BY created_at, id
            """), {"inst": identity[0], "pid": identity[1], "vid": identity[2]}).mappings()]

    def fake_reader(self, *, task_id, run_number, task_record_id, actor_id, workspace_factory, run_scope):
        """替代结果读取器：只按已写入 PG 的受领运行返回可用结果，不做 Canonical 核验。"""
        run = self.runs.get((task_id, run_number))
        if run is None:
            raise TaskQCRunNotFound("任务运行不存在")
        job_id, triggered_by = run
        if run_scope != "assigned" or triggered_by != actor_id:
            raise TaskQCRunForbidden("仅运行人可查看当前受领的病历结果")
        return {"task_id": task_id, "task_record_id": task_record_id, "run_number": run_number,
                "result_state": "available", "job_id": job_id, "items": []}

    def cleanup(self) -> None:
        params = {"tasks": self.task_ids or [""], "jobs": self.job_ids or [""],
                  "inst": INSTITUTE, "like": f"SYN-P-{self.marker}-%"}
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM qc.qc_record_reviews
                WHERE task_id = ANY(:tasks) OR (institute_id = :inst AND patient_id LIKE :like)
            """), params)
            conn.execute(text("""
                DELETE FROM qc.luxian_0609_record_result_envelopes
                WHERE root_job_id = ANY(:jobs) OR (institute_id = :inst AND patient_id LIKE :like)
            """), params)
            conn.execute(text("DELETE FROM qc.task_qc_runs WHERE task_id = ANY(:tasks)"), params)
            conn.execute(text("DELETE FROM qc.custom_qc_batch_jobs WHERE id = ANY(:jobs)"), params)
            conn.execute(text("DELETE FROM qc.qc_task_records WHERE task_id = ANY(:tasks)"), params)
            conn.execute(text("DELETE FROM qc.qc_tasks WHERE id = ANY(:tasks)"), params)

    def residual(self) -> dict[str, int]:
        params = {"tasks": self.task_ids or [""], "jobs": self.job_ids or [""],
                  "inst": INSTITUTE, "like": f"SYN-P-{self.marker}-%"}
        queries = {
            "qc_record_reviews": "SELECT count(*) FROM qc.qc_record_reviews WHERE task_id = ANY(:tasks) OR (institute_id = :inst AND patient_id LIKE :like)",
            "envelopes": "SELECT count(*) FROM qc.luxian_0609_record_result_envelopes WHERE root_job_id = ANY(:jobs) OR (institute_id = :inst AND patient_id LIKE :like)",
            "task_qc_runs": "SELECT count(*) FROM qc.task_qc_runs WHERE task_id = ANY(:tasks) OR job_id = ANY(:jobs)",
            "custom_qc_batch_jobs": "SELECT count(*) FROM qc.custom_qc_batch_jobs WHERE id = ANY(:jobs)",
            "qc_task_records": "SELECT count(*) FROM qc.qc_task_records WHERE task_id = ANY(:tasks) OR (institute_id = :inst AND patient_id LIKE :like)",
            "qc_tasks": "SELECT count(*) FROM qc.qc_tasks WHERE id = ANY(:tasks)",
        }
        with self.engine.connect() as conn:
            return {name: conn.execute(text(sql), params).scalar_one() for name, sql in queries.items()}


@pytest.fixture
def world(pg_engine, monkeypatch):
    syn = SynWorld(pg_engine)
    monkeypatch.setattr(rr, "SessionLocal", sessionmaker(bind=pg_engine))
    monkeypatch.setattr(rr, "get_task_qc_run_record_result", syn.fake_reader)
    try:
        yield syn
    finally:
        syn.cleanup()
        residual = syn.residual()
        print(f"\n[清理残留] {residual}")
        assert all(count == 0 for count in residual.values()), residual


def _factory():
    # 读取器已被替换，工作区工厂不会被调用；显式传入避免构造真实服务。
    return None


def _get(task_id, record_id, run_number, actor):
    return rr.get_record_review(task_id=task_id, task_record_id=record_id, run_number=run_number,
                                actor_id=actor, workspace_factory=_factory)


def _submit(task_id, record_id, run_number, actor, envelope_id, decision="approved",
            reason=None, request_id=None):
    return rr.submit_record_review(
        task_id=task_id, task_record_id=record_id, run_number=run_number, decision=decision,
        reason=reason, request_id=request_id or str(uuid.uuid4()), envelope_id=envelope_id,
        actor_id=actor, workspace_factory=_factory,
    )


def _single_case(world, actor):
    task_id = world.add_task()
    record = world.add_record(task_id, actor)
    job_id = world.add_run(task_id, actor, 1)
    envelope_id = world.add_envelope(job_id, actor, record)
    return task_id, record, job_id, envelope_id


# ---------------------------------------------------------------------------
# 场景 1：初审通过
# ---------------------------------------------------------------------------


def test_initial_review_approved(world):
    actor = world.actor("A")
    task_id, (record_id, identity), job_id, envelope_id = _single_case(world, actor)

    view = _get(task_id, record_id, 1, actor)
    assert view["state"] == "pending_review" and view["stage"] == "initial"
    assert view["can_submit"] is True and view["current"] is None
    assert view["result"] == {"job_id": job_id, "envelope_id": envelope_id}

    saved = _submit(task_id, record_id, 1, actor, envelope_id)
    assert saved["stage"] == "initial" and saved["decision"] == "approved" and saved["idempotent"] is False

    view = _get(task_id, record_id, 1, actor)
    assert view["state"] == "approved" and view["stage"] == "initial" and view["can_submit"] is False
    assert view["current"]["id"] == saved["id"]

    rows = world.reviews(identity)
    assert len(rows) == 1
    assert rows[0]["stage"] == "initial" and rows[0]["decision"] == "approved"
    assert (rows[0]["job_id"], rows[0]["envelope_id"], rows[0]["reviewer_id"]) == (job_id, envelope_id, actor)
    assert (rows[0]["task_id"], rows[0]["task_record_id"], rows[0]["run_number"]) == (task_id, record_id, 1)


# ---------------------------------------------------------------------------
# 场景 2：初审存疑 → 重质控 → 待复审 → 复审通过
# ---------------------------------------------------------------------------


def test_doubtful_then_recheck_after_new_run(world):
    actor = world.actor("A")
    task_id, record, job1, env1 = _single_case(world, actor)
    record_id, identity = record

    for blank in (None, "", "   "):
        with pytest.raises(rr.RecordReviewInvalid):
            _submit(task_id, record_id, 1, actor, env1, decision="doubtful", reason=blank)
    assert world.reviews(identity) == []

    first = _submit(task_id, record_id, 1, actor, env1, decision="doubtful", reason="  SYN 诊断依据不足  ")
    assert first["stage"] == "initial" and first["decision"] == "doubtful" and first["reason"] == "SYN 诊断依据不足"
    assert _get(task_id, record_id, 1, actor)["state"] == "doubtful"

    # 同一病例的第二次受领运行：新 job、新 Envelope
    job2 = world.add_run(task_id, actor, 2)
    env2 = world.add_envelope(job2, actor, record)
    view = _get(task_id, record_id, 2, actor)
    assert view["state"] == "pending_recheck" and view["stage"] == "recheck" and view["can_submit"] is True
    assert view["result"] == {"job_id": job2, "envelope_id": env2}
    assert [item["id"] for item in view["history"]] == [first["id"]]

    second = _submit(task_id, record_id, 2, actor, env2, decision="approved")
    assert second["stage"] == "recheck" and second["decision"] == "approved"

    view = _get(task_id, record_id, 2, actor)
    assert view["state"] == "approved" and view["stage"] == "recheck"
    assert [item["id"] for item in view["history"]] == [second["id"], first["id"]]
    # 旧结果对象上的决定不被改写
    assert _get(task_id, record_id, 1, actor)["state"] == "doubtful"

    rows = world.reviews(identity)
    assert [(row["stage"], row["decision"], row["job_id"], row["envelope_id"]) for row in rows] == [
        ("initial", "doubtful", job1, env1), ("recheck", "approved", job2, env2),
    ]


# ---------------------------------------------------------------------------
# 场景 3：Envelope 被替换后用旧 envelope_id 提交
# ---------------------------------------------------------------------------


def test_rewritten_envelope_rejects_stale_envelope_id(world):
    actor = world.actor("A")
    task_id, record, job_id, old_env = _single_case(world, actor)
    record_id, identity = record
    assert _get(task_id, record_id, 1, actor)["result"]["envelope_id"] == old_env

    new_env = world.rewrite_envelope(job_id, actor, record)
    assert new_env != old_env
    with pytest.raises(rr.RecordReviewConflict) as exc:
        _submit(task_id, record_id, 1, actor, old_env)
    assert exc.value.code == "result_changed"
    assert world.reviews(identity) == []

    view = _get(task_id, record_id, 1, actor)
    assert view["state"] == "pending_review" and view["result"]["envelope_id"] == new_env
    assert _submit(task_id, record_id, 1, actor, new_env)["envelope_id"] == new_env
    assert len(world.reviews(identity)) == 1


# ---------------------------------------------------------------------------
# 场景 4：并发提交同一结果对象
# ---------------------------------------------------------------------------


def test_concurrent_submit_only_one_succeeds(world):
    actor = world.actor("A")
    task_id = world.add_task()
    records = world.add_records(task_id, actor, 5)
    job_id = world.add_run(task_id, actor, 1)
    envelopes = world.add_envelopes(job_id, actor, records)

    outcomes_all = []
    for (record_id, identity), envelope_id in zip(records, envelopes):
        barrier = threading.Barrier(2)

        def race(record_id=record_id, envelope_id=envelope_id, barrier=barrier):
            barrier.wait(timeout=5)
            try:
                return ("ok", _submit(task_id, record_id, 1, actor, envelope_id))
            except rr.RecordReviewConflict as exc:
                return ("conflict", exc.code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(race) for _ in range(2)]
            outcomes = [future.result(timeout=30) for future in futures]
        outcomes_all.append(outcomes)
        kinds = sorted(kind for kind, _ in outcomes)
        assert kinds == ["conflict", "ok"], outcomes
        assert [value for kind, value in outcomes if kind == "conflict"] == ["already_decided"]
        rows = world.reviews(identity)
        assert len(rows) == 1 and rows[0]["envelope_id"] == envelope_id
    print(f"\n[并发] 5 轮结果：{[[kind for kind, _ in item] for item in outcomes_all]}")


# ---------------------------------------------------------------------------
# 场景 5：幂等重放与冲突
# ---------------------------------------------------------------------------


def test_idempotent_replay_and_conflict(world):
    actor = world.actor("A")
    task_id, (record_id, identity), _job_id, envelope_id = _single_case(world, actor)
    request_id = str(uuid.uuid4())

    first = _submit(task_id, record_id, 1, actor, envelope_id, request_id=request_id)
    replay = _submit(task_id, record_id, 1, actor, envelope_id, request_id=request_id)
    assert replay["idempotent"] is True and replay["id"] == first["id"]
    assert replay["stage"] == first["stage"] and replay["decision"] == "approved"

    with pytest.raises(rr.RecordReviewConflict) as exc:
        _submit(task_id, record_id, 1, actor, envelope_id, decision="doubtful",
                reason="SYN 改口", request_id=request_id)
    assert exc.value.code == "idempotency_conflict"
    # 新请求 ID 对已有决定的同一结果对象 → already_decided
    with pytest.raises(rr.RecordReviewConflict) as exc:
        _submit(task_id, record_id, 1, actor, envelope_id)
    assert exc.value.code == "already_decided"
    assert len(world.reviews(identity)) == 1


# ---------------------------------------------------------------------------
# 场景 6：非受领人
# ---------------------------------------------------------------------------


def test_non_assignee_forbidden(world):
    actor = world.actor("A")
    outsider = world.actor("X")
    task_id, (record_id, identity), _job_id, envelope_id = _single_case(world, actor)

    with pytest.raises(rr.RecordReviewForbidden):
        _get(task_id, record_id, 1, outsider)
    with pytest.raises(rr.RecordReviewForbidden):
        _submit(task_id, record_id, 1, outsider, envelope_id)
    assert rr.count_my_record_review_todos(outsider, workspace_factory=_factory) == {"initial": 0, "recheck": 0}
    assert world.reviews(identity) == []


# ---------------------------------------------------------------------------
# 场景 7：待办计数与列表共用谓词，scene 过滤生效
# ---------------------------------------------------------------------------


def test_todo_count_and_list_consistent(world):
    actor = world.actor("A")
    # 任务 1（running）：病例 A 无决定
    task_running = world.add_task(scene="running")
    case_a = world.add_record(task_running, actor)
    job_r1 = world.add_run(task_running, actor, 1)
    world.add_envelope(job_r1, actor, case_a)
    # 任务 2（final）：病例 B 已通过；病例 C 存疑后有新结果
    task_final = world.add_task(scene="final")
    case_b = world.add_record(task_final, actor)
    case_c = world.add_record(task_final, actor)
    job_f1 = world.add_run(task_final, actor, 1)
    env_b, env_c1 = world.add_envelopes(job_f1, actor, [case_b, case_c])
    _submit(task_final, case_b[0], 1, actor, env_b)
    _submit(task_final, case_c[0], 1, actor, env_c1, decision="doubtful", reason="SYN 待复核")
    job_f2 = world.add_run(task_final, actor, 2)
    env_c2 = world.add_envelope(job_f2, actor, case_c)

    count = rr.count_my_record_review_todos(actor, workspace_factory=_factory)
    assert count == {"initial": 1, "recheck": 1}
    listing = rr.list_my_record_review_todos(actor_id=actor, workspace_factory=_factory)
    assert listing["total"] == sum(count.values()) == 2
    by_record = {item["task_record_id"]: item for item in listing["items"]}
    assert set(by_record) == {case_a[0], case_c[0]}
    assert by_record[case_a[0]]["stage"] == "initial" and by_record[case_a[0]]["run_number"] == 1
    assert by_record[case_c[0]]["stage"] == "recheck" and by_record[case_c[0]]["run_number"] == 2
    assert by_record[case_c[0]]["envelope_id"] == env_c2

    for stage in ("initial", "recheck"):
        page = rr.list_my_record_review_todos(actor_id=actor, stage=stage, workspace_factory=_factory)
        assert page["total"] == count[stage] == 1

    assert rr.count_my_record_review_todos(actor, scene="running", workspace_factory=_factory) == {"initial": 1, "recheck": 0}
    assert rr.count_my_record_review_todos(actor, scene="final", workspace_factory=_factory) == {"initial": 0, "recheck": 1}
    assert rr.count_my_record_review_todos(actor, scene="outpatient_emergency", workspace_factory=_factory) == {"initial": 0, "recheck": 0}
    running = rr.list_my_record_review_todos(actor_id=actor, scene="running", workspace_factory=_factory)
    assert running["total"] == 1 and running["items"][0]["task_record_id"] == case_a[0]
    final = rr.list_my_record_review_todos(actor_id=actor, scene="final", stage="recheck", workspace_factory=_factory)
    assert final["total"] == 1 and final["items"][0]["task_record_id"] == case_c[0]
    with pytest.raises(rr.RecordReviewInvalid):
        rr.count_my_record_review_todos(actor, scene="bogus", workspace_factory=_factory)

    # 复审通过后，病例 C 离开待办
    _submit(task_final, case_c[0], 2, actor, env_c2)
    assert rr.count_my_record_review_todos(actor, workspace_factory=_factory) == {"initial": 1, "recheck": 0}


# ---------------------------------------------------------------------------
# 场景 8：200 例待办计数耗时（不设硬阈值）
# ---------------------------------------------------------------------------


def test_todo_count_performance_200_cases(world):
    actor = world.actor("P")
    task_id = world.add_task()
    records = world.add_records(task_id, actor, 200)
    job_id = world.add_run(task_id, actor, 1)
    world.add_envelopes(job_id, actor, records)

    timings = []
    for _ in range(3):
        started = time.perf_counter()
        count = rr.count_my_record_review_todos(actor, workspace_factory=_factory)
        timings.append(time.perf_counter() - started)
        assert count == {"initial": 200, "recheck": 0}
    started = time.perf_counter()
    listing = rr.list_my_record_review_todos(actor_id=actor, page_size=100, workspace_factory=_factory)
    list_seconds = time.perf_counter() - started
    assert listing["total"] == 200 and len(listing["items"]) == 100
    print(f"\n[性能] 200 例 count_my_record_review_todos 耗时（秒）：{[round(t, 3) for t in timings]}；"
          f"list 首页：{list_seconds:.3f}（结果读取器已替换，不含其 Canonical 核验开销）")
