"""任务关键词必须是绑定值，不能扩展为额外 OR 条件。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.supabase_client import _Query
from app.routers.tasks import _apply_task_keyword_scope


@pytest.mark.parametrize(
    "keyword",
    [
        "普通任务",
        "甲,task_number.ilike.%QC-001",
        "100%_抽查*",
    ],
)
def test_task_keyword_is_one_bound_value_for_both_columns(keyword):
    query = _Query(None, "qc_tasks")

    assert _apply_task_keyword_scope(query, keyword) is query
    where, params = query._build_where()

    assert where == '("task_name" ILIKE :p0 OR "task_number" ILIKE :p1)'
    assert params == {"p0": f"%{keyword}%", "p1": f"%{keyword}%"}
    assert where.count(" OR ") == 1
    assert "QC-001" not in where


def test_empty_keyword_keeps_query_and_unsupported_adapter_fails_closed():
    class LegacyQuery:
        def or_(self, _expression):
            raise AssertionError("不得回退到字符串 OR")

    legacy = LegacyQuery()
    assert _apply_task_keyword_scope(legacy, None) is legacy
    assert _apply_task_keyword_scope(legacy, "") is legacy
    with pytest.raises(HTTPException) as captured:
        _apply_task_keyword_scope(legacy, "甲,task_number.ilike.%QC-001")
    assert captured.value.status_code == 503


def test_structured_or_rejects_dynamic_column_names():
    query = _Query(None, "qc_tasks")
    with pytest.raises(ValueError):
        query.or_ilike(("task_name", 'task_number" OR TRUE --'), "%任务%")
