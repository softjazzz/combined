"""隔离 PostgreSQL 上强制取消与并发进度的毫秒级交错验收。

本文件只回答一个问题：``cancel_batch_job`` 读取父任务/活跃子任务时是否真正持有
PostgreSQL 行锁，使取消事务不会用**旧摘要**覆盖并发 Worker 已提交的进度 Token，
并在 ``queued→running`` 交错中保守标记“成本未知”。

与既有 ``test_luxian_0609_isolated_postgres_attempts.py`` 相同，只允许连接隔离的
``127.0.0.1:15432``；无该实例时跳过，误指向其它地址时在建立连接前失败。全部数据
都是合成任务与合成 Token，不调用模型、不读取患者资料。

关键点：为了让“修复前应失败”可被独立证伪，而不是仅凭新代码通过，本文件同时提供

* ``disable_row_lock=True``：把 ``Select.with_for_update`` 打成空操作，等价于 3d76e1ae5
  **之前**的 SQL（两个 SELECT 都没有行锁），断言旧摘要确实会覆盖并发进度；
* ``disable_row_lock=False``：现行生产代码，断言同一交错下进度 Token 被保留。

两条腿断言的是同一个不变式，因此任一侧文案漂移都会让另一侧失去意义。
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import traceback
import time
import uuid
from datetime import datetime
from typing import Any, Iterator
from unittest import mock

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace_module


RULE_SET_KEY = workspace_module.LUXIAN_0609_RULE_SET_KEY
ATTEMPT_KEY = workspace_module.LX0609_ATTEMPT_FILTER_KEY
CREATED_BY = "synthetic-tester"


def _isolated_database_url() -> str:
    database_url = os.environ.get("MEDQC_LX0609_ISOLATED_PG_URL", "")
    if not database_url:
        pytest.skip("需显式提供独立本机 PostgreSQL 18 测试实例")
    parsed = sa.engine.make_url(database_url)
    if parsed.get_backend_name() != "postgresql" or parsed.host != "127.0.0.1" or parsed.port != 15432:
        pytest.fail("只允许连接隔离的 127.0.0.1:15432 PostgreSQL 测试实例")
    return database_url


@contextlib.contextmanager
def _without_row_lock() -> Iterator[None]:
    """等价重现 3d76e1ae5 之前：``with_for_update()`` 不产生 ``FOR UPDATE``。"""

    with mock.patch.object(
        sa.sql.selectable.Select, "with_for_update", lambda self, *args, **kwargs: self,
    ):
        yield


@pytest.fixture()
def isolated_storage(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Any, Any]]:
    database_url = _isolated_database_url()
    schema = "lx0609_cancel_" + uuid.uuid4().hex[:12]
    database = sa.create_engine(database_url)
    with database.begin() as connection:
        connection.execute(sa.text(f"CREATE SCHEMA {schema}"))
    monkeypatch.setattr(workspace_module, "engine", database)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: schema)
    monkeypatch.setattr(workspace_module, "_session", sessionmaker(bind=database))
    monkeypatch.setattr(
        workspace_module, "_sync_batch_job_parent_columns", lambda **_kwargs: None,
    )
    workspace_module._drafts_table.cache_clear()
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    service = workspace_module.CustomQCWorkspaceService()
    service._record_result_envelope_table.metadata.create_all(database)
    try:
        yield database, service, service._batch_job_table
    finally:
        with database.begin() as connection:
            connection.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))
        database.dispose()
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()


def _filters(*, attempt: str, record_refs: list[dict[str, str]] | None = None) -> str:
    return json.dumps(
        {
            "rule_set_key": RULE_SET_KEY,
            "rule_set_version": workspace_module.RULE_SET_VERSION,
            "rule_ids": ["LX0609-01-01-01"],
            "record_refs": record_refs or [],
            ATTEMPT_KEY: attempt,
        },
        ensure_ascii=False,
    )


def _summary(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "rule_count": 1,
        "progress": {
            "step_key": "run",
            "rule_index": 1,
            "rule_count": 1,
            "processed_records": 3,
            "total_records": 10,
        },
        "updated_at": "2026-09-25T09:00:00+00:00",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _insert_job(table, *, job_id: str, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "id": job_id,
        "draft_id": "synthetic-draft",
        "created_by": CREATED_BY,
        "rule_code": "LX0609",
        "rule_name": "合成取消竞态",
        "scene": "final",
        "scope": "final",
        "status": "running",
        "total_records": 10,
        "record_ids_json": "[]",
        "filters_json": _filters(attempt="attempt-old"),
        "summary_json": _summary(),
        "total_tokens": 0,
        "job_kind": "leaf",
        "created_at": datetime(2026, 9, 25, 9, 0, 0),
        "updated_at": datetime(2026, 9, 25, 9, 0, 0),
    }
    values.update(overrides)
    with workspace_module.engine.begin() as connection:
        connection.execute(table.insert().values(**values))


def _read_row(table, job_id: str) -> dict[str, Any]:
    with workspace_module.engine.connect() as connection:
        row = connection.execute(
            sa.select(table).where(table.c.id == job_id)
        ).mappings().first()
    assert row is not None
    return dict(row)


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    summary = json.loads(row.get("summary_json") or "{}")
    assert isinstance(summary, dict)
    return summary


class _BlockedStatementWaiter:
    """证明取消语句已经落到数据库并停在行锁上。

    每次探测都新开连接，避免长期连接持有的快照看不到刚刚出现的等待会话。
    """

    def __init__(self, database) -> None:
        self._engine = database
        self.last_rows: list[tuple[Any, ...]] = []

    def close(self) -> None:
        self.last_rows = list(self.last_rows)

    def snapshot(self) -> list[tuple[Any, ...]]:
        with self._engine.connect() as connection:
            return [
                tuple(row)
                for row in connection.execute(sa.text(
                    "select pid, state, coalesce(wait_event_type, '-'), coalesce(wait_event, '-'), "
                    "left(query, 70) from pg_stat_activity "
                    "where datname = current_database() and pid <> pg_backend_pid() "
                    "and query ilike '%custom_qc_batch_jobs%' order by pid"
                )).all()
            ]

    def wait(self, *, timeout: float = 10.0) -> bool:
        """Worker 整段时间持有行锁，因此任何 active 且命中该表的新语句必然是等待者。"""

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.last_rows = self.snapshot()
            for _pid, state, wait_type, wait_event, _query in self.last_rows:
                if state == "active" and (
                    wait_type == "Lock" or wait_event in {"transactionid", "tuple", "pid"}
                ):
                    return True
            time.sleep(0.05)
        return False


class _CancelRunner:
    """在独立连接上执行取消，并在主测试线程可控地交错。"""

    def __init__(self, service, prefix: str) -> None:
        self._service = service
        self._prefix = prefix
        self.result: dict[str, Any] | None = None
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            self.result = self._service.cancel_batch_job(
                job_id=self._prefix, created_by=CREATED_BY,
            )
        except BaseException as exc:  # noqa: BLE001 - 测试需要原样暴露线程内异常
            self.error = exc

    def start(self) -> None:
        self._thread.start()

    def assert_blocked(self, observer: "_BlockedStatementWaiter") -> None:
        if observer.wait():
            return
        frames = sys._current_frames()
        stack = "".join(
            traceback.format_stack(frames[self._thread.ident])
        ) if self._thread.ident in frames else "<no frame>"
        raise AssertionError(
            "取消事务没有停在行锁上，交错未被构造出来；"
            f"thread_alive={self._thread.is_alive()} "
            f"error={self.error!r} result={self.result!r} "
            f"observed={observer.last_rows!r}\n{stack}"
        )

    def join(self, *, timeout: float = 30.0) -> None:
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise AssertionError("取消事务未在超时前结束")
        if self.error is not None:
            raise self.error


def test_parent_cancel_preserves_progress_token_committed_concurrently(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """父任务读取持有行锁：取消不得用旧摘要覆盖并发提交的进度。"""

    database, service, table = isolated_storage
    job_id = "pg-parent-race-" + uuid.uuid4().hex[:12]
    _insert_job(table, job_id=job_id, status="running")

    observer = _BlockedStatementWaiter(database)
    try:
        with database.begin() as worker:
            worker.execute(
                table.update()
                .where(table.c.id == job_id)
                .values(
                    filters_json=_filters(attempt="attempt-new"),
                    summary_json=_summary(
                        progress={
                            "step_key": "run",
                            "rule_index": 2,
                            "rule_count": 79,
                            "processed_records": 17,
                            "total_records": 10,
                        },
                        total_tokens=12,
                    ),
                )
            )
            runner = _CancelRunner(service, job_id)
            runner.start()
            runner.assert_blocked(observer)
            # 退出上下文即提交 Worker 进度；取消随后才可能读到该行。
        runner.join()
    finally:
        observer.close()

    row = _read_row(table, job_id)
    summary = _row_summary(row)
    assert row["status"] == "canceled"
    assert summary.get("user_cancelled") is True
    assert summary["progress"]["step_key"] == "canceled"
    assert summary["progress"]["processed_records"] == 17
    assert summary["progress"]["rule_count"] == 79
    assert summary.get("total_tokens") == 12


def test_parent_cancel_without_row_lock_loses_concurrent_progress(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证伪腿：去掉 ``FOR UPDATE`` 后，同一交错必须暴露旧摘要覆盖。"""

    database, service, table = isolated_storage
    job_id = "pg-parent-stale-" + uuid.uuid4().hex[:12]
    _insert_job(table, job_id=job_id, status="running")

    observer = _BlockedStatementWaiter(database)
    try:
        with _without_row_lock():
            with database.begin() as worker:
                worker.execute(
                    table.update()
                    .where(table.c.id == job_id)
                    .values(
                        filters_json=_filters(attempt="attempt-new"),
                        summary_json=_summary(
                            progress={
                                "step_key": "run",
                                "rule_index": 2,
                                "rule_count": 79,
                                "processed_records": 17,
                                "total_records": 10,
                            },
                            total_tokens=12,
                        ),
                    )
                )
                runner = _CancelRunner(service, job_id)
                runner.start()
                runner.assert_blocked(observer)
            runner.join()
    finally:
        observer.close()

    row = _read_row(table, job_id)
    summary = _row_summary(row)
    assert row["status"] == "canceled"
    # 旧代码在这里用取消事务开始前读到的摘要写回：Worker 已提交的 17 条进度、79 个规则数
    # 和 12 个 Token 全部丢失，只剩取消前那份旧摘要。
    assert summary["progress"]["processed_records"] == 3
    assert summary["progress"]["rule_count"] == 1
    assert summary.get("total_tokens") is None


def test_parent_cancel_locks_active_child_and_preserves_child_progress(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """活跃子任务读取持有行锁，父任务取消不得覆盖子任务并发进度。"""

    database, service, table = isolated_storage
    parent_id = "pg-parent-child-" + uuid.uuid4().hex[:12]
    child_id = "pg-child-race-" + uuid.uuid4().hex[:12]
    _insert_job(
        table, job_id=parent_id, status="running", job_kind="parent",
        child_job_ids_json=json.dumps([child_id]),
        summary_json=_summary(progress={
            "step_key": "run", "rule_index": 1, "rule_count": 2,
            "processed_records": 1, "total_records": 2,
        }),
    )
    _insert_job(
        table, job_id=child_id, status="running", job_kind="leaf",
        parent_job_id=parent_id,
        summary_json=_summary(progress={
            "step_key": "run", "rule_index": 0, "rule_count": 1,
            "processed_records": 2, "total_records": 10,
        }),
    )

    observer = _BlockedStatementWaiter(database)
    try:
        # 只有子任务行被 Worker 持有；父任务行保持可读，确保卡点在子任务读取上。
        with database.begin() as worker:
            worker.execute(
                table.update()
                .where(table.c.id == child_id)
                .values(
                    filters_json=_filters(attempt="attempt-new"),
                    summary_json=_summary(
                        progress={
                            "step_key": "run",
                            "rule_index": 4,
                            "rule_count": 79,
                            "processed_records": 21,
                            "total_records": 10,
                        },
                        total_tokens=30,
                    ),
                )
            )
            runner = _CancelRunner(service, parent_id)
            runner.start()
            runner.assert_blocked(observer)
        runner.join()
    finally:
        observer.close()

    parent_row = _read_row(table, parent_id)
    child_row = _read_row(table, child_id)
    child_summary = _row_summary(child_row)
    assert parent_row["status"] == "canceled"
    assert child_row["status"] == "canceled"
    assert child_row["error_message"] == "parent_cancelled: 总任务已取消"
    assert child_summary["progress"]["processed_records"] == 21
    assert child_summary["progress"]["rule_count"] == 79
    assert child_summary.get("total_tokens") == 30
    assert child_summary.get("luxian_0609_usage_observation_complete") is False


def test_parent_cancel_without_child_row_lock_loses_child_progress(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证伪腿：去掉子任务 ``FOR UPDATE`` 后必须复现子任务进度被旧摘要覆盖。"""

    database, service, table = isolated_storage
    parent_id = "pg-parent-child-stale-" + uuid.uuid4().hex[:12]
    child_id = "pg-child-stale-" + uuid.uuid4().hex[:12]
    _insert_job(
        table, job_id=parent_id, status="running", job_kind="parent",
        child_job_ids_json=json.dumps([child_id]),
    )
    _insert_job(
        table, job_id=child_id, status="running", job_kind="leaf",
        parent_job_id=parent_id,
    )

    observer = _BlockedStatementWaiter(database)
    try:
        with _without_row_lock():
            with database.begin() as worker:
                worker.execute(
                    table.update()
                    .where(table.c.id == child_id)
                    .values(
                        filters_json=_filters(attempt="attempt-new"),
                        summary_json=_summary(
                            progress={
                                "step_key": "run",
                                "rule_index": 4,
                                "rule_count": 79,
                                "processed_records": 21,
                                "total_records": 10,
                            },
                            total_tokens=30,
                        ),
                    )
                )
                runner = _CancelRunner(service, parent_id)
                runner.start()
                runner.assert_blocked(observer)
            runner.join()
    finally:
        observer.close()

    child_row = _read_row(table, child_id)
    child_summary = _row_summary(child_row)
    assert child_row["status"] == "canceled"
    # 子任务并发进度（21 条 / 79 个规则 / 30 Token）被旧摘要覆盖，只剩插入时的 3 条。
    assert child_summary["progress"]["processed_records"] == 3
    assert child_summary["progress"]["rule_count"] == 1
    assert child_summary.get("total_tokens") is None


def test_cancel_observing_concurrent_queued_to_running_marks_usage_unknown(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``queued→running`` 交错：取消必须先看到 running，再把成本观测标记为未知。"""

    database, service, table = isolated_storage
    job_id = "pg-queued-running-" + uuid.uuid4().hex[:12]
    _insert_job(
        table, job_id=job_id, status="queued",
        summary_json=_summary(total_tokens=12, luxian_0609_usage_observation_complete=True),
    )

    observer = _BlockedStatementWaiter(database)
    try:
        with database.begin() as worker:
            # Worker 的 queued→running 断言同时旋转执行代次，这就是取消可能读到的交错。
            worker.execute(
                table.update()
                .where(table.c.id == job_id)
                .values(
                    status="running",
                    filters_json=_filters(attempt="attempt-running"),
                    summary_json=_summary(
                        progress={
                            "step_key": "prepare",
                            "rule_index": 0,
                            "rule_count": 1,
                            "processed_records": 0,
                            "total_records": 10,
                        },
                        total_tokens=12,
                        luxian_0609_usage_observation_complete=True,
                    ),
                )
            )
            runner = _CancelRunner(service, job_id)
            runner.start()
            runner.assert_blocked(observer)
        runner.join()
    finally:
        observer.close()

    row = _read_row(table, job_id)
    summary = _row_summary(row)
    assert row["status"] == "canceled"
    assert summary.get("luxian_0609_usage_observation_complete") is False
    assert summary.get("total_tokens") == 12


def test_cancel_without_row_lock_misses_queued_to_running_usage_unknown(
    isolated_storage, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证伪腿：无行锁时取消读到 ``queued`` 旧状态，静默保留“用量完整”。"""

    database, service, table = isolated_storage
    job_id = "pg-queued-running-stale-" + uuid.uuid4().hex[:12]
    _insert_job(
        table, job_id=job_id, status="queued",
        summary_json=_summary(total_tokens=12, luxian_0609_usage_observation_complete=True),
    )

    observer = _BlockedStatementWaiter(database)
    try:
        with _without_row_lock():
            with database.begin() as worker:
                worker.execute(
                    table.update()
                    .where(table.c.id == job_id)
                    .values(
                        status="running",
                        filters_json=_filters(attempt="attempt-running"),
                        summary_json=_summary(
                            total_tokens=12,
                            luxian_0609_usage_observation_complete=True,
                        ),
                    )
                )
                runner = _CancelRunner(service, job_id)
                runner.start()
                runner.assert_blocked(observer)
            runner.join()
    finally:
        observer.close()

    row = _read_row(table, job_id)
    summary = _row_summary(row)
    assert row["status"] == "canceled"
    # 取消读到的是 queued 旧快照，于是漏标成本未知，仍对外声称“用量完整”。
    assert summary.get("luxian_0609_usage_observation_complete") is True


def test_late_worker_writes_after_cancel_cannot_resurrect_or_mutate_job(
    isolated_storage,
) -> None:
    """取消提交后的迟到写入被代次/状态边界挡住：进度无法回写，父刷新无法复活。"""

    database, service, table = isolated_storage
    parent_id = "pg-late-parent-" + uuid.uuid4().hex[:12]
    child_id = "pg-late-child-" + uuid.uuid4().hex[:12]
    attempt_json = _filters(attempt="attempt-live")
    _insert_job(
        table, job_id=parent_id, status="running", job_kind="parent",
        child_job_ids_json=json.dumps([child_id]),
    )
    _insert_job(
        table, job_id=child_id, status="running", job_kind="leaf",
        parent_job_id=parent_id, filters_json=attempt_json,
        summary_json=_summary(total_tokens=7),
    )

    canceled = service.cancel_batch_job(job_id=parent_id, created_by=CREATED_BY)
    assert canceled is not None and canceled["status"] == "canceled"
    child_after_cancel = _read_row(table, child_id)
    assert child_after_cancel["status"] == "canceled"

    # 边界一：取消终态下，仍持旧执行代次的 Worker 进度写入不得改动任务行。
    rejected_progress = service.update_batch_job_progress(
        job_id=child_id, step_key="run", rule_index=1, rule_count=1,
        processed_records=9, total_records=10,
        summary_patch={"total_tokens": 999},
        attempt_filters_json=attempt_json,
    )
    assert rejected_progress == {"id": child_id, "status": "canceled"}
    child_row = _read_row(table, child_id)
    assert _row_summary(child_row).get("total_tokens") == 7
    assert child_row["updated_at"] == child_after_cancel["updated_at"]

    # 边界二：执行代次被轮换后，旧代次的进度写入必须返回 None 且不落库。
    rotated_id = "pg-rotated-" + uuid.uuid4().hex[:12]
    _insert_job(table, job_id=rotated_id, status="running", filters_json=attempt_json,
                summary_json=_summary(total_tokens=5))
    with database.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == rotated_id)
            .values(filters_json=_filters(attempt="attempt-rotated"))
        )
    assert service.update_batch_job_progress(
        job_id=rotated_id, step_key="run", rule_index=1, rule_count=1,
        processed_records=4, total_records=10,
        summary_patch={"total_tokens": 77},
        attempt_filters_json=attempt_json,
    ) is None
    rotated_row = _read_row(table, rotated_id)
    assert _row_summary(rotated_row).get("total_tokens") == 5

    # 边界三：迟到的父聚合刷新不得把已取消父任务改成别的终态或覆盖取消摘要。
    service.refresh_parent_batch_job(parent_job_id=parent_id)
    parent_row = _read_row(table, parent_id)
    parent_summary = _row_summary(parent_row)
    assert parent_row["status"] == "canceled"
    assert parent_summary.get("user_cancelled") is True
    assert parent_summary["progress"]["step_key"] == "canceled"

    # 边界四：已取消任务不能被重新领取为新执行代次。
    assert service.mark_batch_job_running(job_id=parent_id) is False
    assert _read_row(table, parent_id)["status"] == "canceled"
