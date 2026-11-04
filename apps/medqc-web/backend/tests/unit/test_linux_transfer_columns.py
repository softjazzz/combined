"""导入工具按命名字段工作，物理列序不是兼容合同。"""

import importlib.util
from pathlib import Path

import pytest


def load_tool():
    path = (
        Path(__file__).resolve().parents[3]
        / "scripts/linux_offline/deploy/sample_set_transfer.py"
    )
    spec = importlib.util.spec_from_file_location("linux_transfer_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def columns():
    return [
        {"name": "id", "type": "text", "notnull": True},
        {"name": "execution_mode", "type": "character varying(20)", "notnull": True},
        {"name": "draft_ids_json", "type": "text", "notnull": True},
        {"name": "rule_count", "type": "integer", "notnull": True},
    ]


def test_same_named_definitions_accept_different_physical_order():
    load_tool().compatible_columns(columns(), list(reversed(columns())))


@pytest.mark.parametrize(
    "change", ["missing", "extra", "duplicate", "type", "nullability"]
)
def test_column_order_fix_keeps_structural_rejections(change):
    expected = columns()
    actual = [dict(c) for c in expected]
    if change == "missing":
        actual.pop()
    elif change == "extra":
        actual.append({"name": "unexpected", "type": "text", "notnull": False})
    elif change == "duplicate":
        actual.append(dict(actual[0]))
    elif change == "type":
        actual[0]["type"] = "integer"
    else:
        actual[0]["notnull"] = False
    with pytest.raises(ValueError):
        load_tool().compatible_columns(expected, actual)


def test_json_nullability_differences_are_still_rejected():
    transfer = load_tool()
    source = [{"name": "items_json", "type": "text", "notnull": True}]
    target = [{**source[0], "notnull": False}]
    for expected, actual in [(source, target), (target, source)]:
        with pytest.raises(ValueError):
            transfer.compatible_columns(expected, actual)


def test_required_source_values_checked_before_any_insert(tmp_path):
    transfer = load_tool()
    table = {
        "schema": "qc",
        "name": "custom_qc_batch_jobs",
        "primary": ["id"],
        "columns": columns(),
        "file": "rows.jsonl",
    }
    (tmp_path / "rows.jsonl").write_text(
        '{"id":"synthetic","execution_mode":null}\n', encoding="utf-8"
    )

    class Cursor:
        def execute(self, *args):
            pytest.fail(
                "missing source required values must fail before any database statement"
            )

    with pytest.raises(ValueError, match="source_required_column_missing_or_null"):
        transfer.compare_shared(Cursor(), tmp_path, table, "owner", require_all=False)
