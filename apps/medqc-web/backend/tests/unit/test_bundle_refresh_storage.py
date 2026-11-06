"""纯内存owner计划；运行PG矩阵另有独占PG16护栏。"""

from types import SimpleNamespace
import pytest
from app.services.bundles.refresh_storage import (
    owner_plan,
    qualified,
    RefreshStorageError,
)


class Connection:
    def __init__(self, objects):
        self.objects = objects

    def execute(self, statement, params):
        rows = self.objects.get(params["name"], [])
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))


@pytest.mark.parametrize("split,expected", [(True, "qc"), (False, "public")])
def test_missing_plan_does_not_create_or_guess_search_path(split, expected):
    owners, preferred = owner_plan(Connection({}), allow_missing=True, split=split)
    assert all(v is None for v in owners.values()) and preferred == expected
    with pytest.raises(RefreshStorageError, match="missing"):
        owner_plan(Connection({}))


@pytest.mark.parametrize("schema", ["public", "qc"])
def test_one_owner_is_reused_for_missing_partner(schema):
    owners, preferred = owner_plan(
        Connection({"bundle_refresh_jobs": [{"schema_name": schema, "relkind": "r"}]}),
        allow_missing=True,
    )
    assert preferred == schema
    assert owners["bundle_refresh_jobs"] == schema


def test_duplicate_even_empty_owner_refuses():
    c = Connection(
        {
            "bundle_refresh_jobs": [
                {"schema_name": s, "relkind": "r"} for s in ("public", "qc")
            ]
        }
    )
    with pytest.raises(RefreshStorageError, match="ambiguous"):
        owner_plan(c, allow_missing=True)


def test_view_cannot_impersonate_audit_table():
    c = Connection({"bundle_refresh_jobs": [{"schema_name": "public", "relkind": "v"}]})
    with pytest.raises(RefreshStorageError, match="not_physical"):
        owner_plan(c, allow_missing=True)


def test_identifier_is_code_allowlist_only():
    with pytest.raises(RefreshStorageError):
        qualified("cdm", "bundle_refresh_jobs")
    with pytest.raises(RefreshStorageError):
        qualified("qc", "sys_users")


def test_frozen_migration_v1_matches_runtime_contract_without_importing_it():
    import ast
    from pathlib import Path
    from app.services.bundles import refresh_storage

    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20261105_000063_bundle_refresh_storage.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert "services.bundles" not in path.read_text(encoding="utf-8")
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name)
            and t.id in {"TABLES", "SCHEMAS", "JOBS", "FAILURES"}
            for t in node.targets
        )
    ]
    namespace = {}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    for key in ("TABLES", "SCHEMAS", "JOBS", "FAILURES"):
        assert namespace[key] == getattr(refresh_storage, key)
