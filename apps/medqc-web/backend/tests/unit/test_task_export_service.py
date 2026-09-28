"""全部任务导出的筛选、上限、白名单与 CSV 安全合同。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCTask
from app.services import task_export_service as service


def _environment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    QCTask.__table__.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _task(index: int, **overrides):
    values = {
        "id": f"task-{index:05d}",
        "task_number": f"NO-{index:05d}",
        "task_name": f"任务-{index}",
        "task_type": "one_time",
        "scene": "running",
        "rule_set_key": "sc_content_full_v1",
        "rule_set_version": "v1",
        "sampling_method": "all",
        "assign_method": "by_ratio",
        "status": "draft",
        "progress": 0,
        "total_records": 10,
        "completed_records": 0,
        "creator_id": "private-user-id",
        "creator_name": "创建人",
        "deadline": None,
        "created_at": datetime(2026, 9, 27) + timedelta(seconds=index),
    }
    values.update(overrides)
    return QCTask(**values)


def _rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))


def test_export_uses_one_stable_select_and_real_list_filters():
    engine, factory = _environment()
    with factory.begin() as session:
        session.add_all([
            _task(1, task_name="目标运行任务", status="completed"),
            _task(2, task_name="其他运行任务", status="completed"),
            _task(3, task_name="目标终末任务", scene="final", status="completed"),
            _task(4, task_name="目标草稿任务", status="draft"),
        ])
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda _c, _cu, sql, *_a: statements.append(sql))

    result = service.export_all_tasks(
        scene="running", status="completed", keyword="目标", session_factory=factory,
    )

    assert result.row_count == 1
    assert _rows(result.content)[0]["任务名称"] == "目标运行任务"
    assert len(statements) == 1
    assert "ORDER BY" in statements[0] and "LIMIT" in statements[0]


def test_unclassified_scene_is_null_only_and_order_is_stable():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add_all([
            _task(1, scene=None, created_at=datetime(2026, 9, 27)),
            _task(2, scene=None, created_at=datetime(2026, 9, 27)),
            _task(3, scene="running"),
        ])

    result = service.export_all_tasks(scene="unclassified", session_factory=factory)

    rows = _rows(result.content)
    assert [row["任务编号"] for row in rows] == ["NO-00002", "NO-00001"]
    assert {row["场景"] for row in rows} == {"未知"}


def test_more_than_fixed_limit_is_rejected_without_partial_csv():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add_all([_task(index) for index in range(service.MAX_EXPORT_ROWS + 1)])

    with pytest.raises(service.TaskExportTooLarge) as captured:
        service.export_all_tasks(session_factory=factory)

    assert captured.value.limit == 5_000
    assert captured.value.matched_at_least == 5_001


def test_csv_has_bom_fixed_whitelist_and_formula_protection():
    content = service.render_task_export_csv([{
        "task_number": "=1+1",
        "task_name": "+SUM(A1:A2)",
        "scene": "running",
        "task_type": "one_time",
        "status": "draft",
        "progress": 12.5,
        "total_records": 2,
        "completed_records": 1,
        "creator_name": "\n=危险",
        "created_at": datetime(2026, 9, 27, 8, 30),
        "deadline": None,
        "rule_set_key": "\tcmd",
        "rule_set_version": "-1",
        "sampling_method": "all",
        "assign_method": "by_ratio",
        "creator_id": "must-not-export",
        "record_refs": [{"patient_id": "P001"}],
        "raw_response": "private",
    }])

    assert content.startswith(b"\xef\xbb\xbf")
    rows = _rows(content)
    assert list(rows[0]) == [label for _key, label in service._HEADERS]
    assert rows[0]["任务编号"] == "'=1+1"
    assert rows[0]["任务名称"] == "'+SUM(A1:A2)"
    assert rows[0]["创建人"] == "'\n=危险"
    assert rows[0]["规则集"] == "'\tcmd"
    assert rows[0]["规则版本"] == "'-1"
    assert rows[0]["截止时间"] == "未知"
    decoded = content.decode("utf-8-sig")
    assert "must-not-export" not in decoded
    assert "P001" not in decoded
    assert "private" not in decoded


@pytest.mark.parametrize(
    "kwargs",
    [
        {"scene": "emergency"},
        {"scene": 123},
    ],
)
def test_invalid_filters_fail_before_database_access(kwargs):
    called = False

    def factory():
        nonlocal called
        called = True
        raise AssertionError("不应连接数据库")

    with pytest.raises(service.TaskExportInvalid):
        service.export_all_tasks(session_factory=factory, **kwargs)
    assert called is False


def test_status_and_keyword_keep_list_endpoint_matching_semantics():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add_all([
            _task(1, task_name="空 格任务", status="legacy-state"),
            _task(2, task_name="其他任务", status="draft"),
        ])

    result = service.export_all_tasks(
        status="legacy-state", keyword="空 格", session_factory=factory,
    )
    assert result.row_count == 1
    assert _rows(result.content)[0]["任务编号"] == "NO-00001"


def test_database_errors_are_wrapped_without_private_details():
    def factory():
        raise RuntimeError("patient P001 private SQL")

    with pytest.raises(service.TaskExportUnavailable) as captured:
        service.export_all_tasks(session_factory=factory)
    assert "P001" not in str(captured.value)
    assert "private SQL" not in str(captured.value)
