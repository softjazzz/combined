"""迁移82精确预检双schema，不连接数据库或回填历史。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

PATH = Path(__file__).parents[2] / "alembic/versions/20261002_000082_record_review_defect_snapshot.py"
SPEC = importlib.util.spec_from_file_location("snapshot_migration", PATH)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class Inspector:
    def __init__(self, complete=False):
        base = [{"name": name, "type": sa.String(length), "nullable": nullable, "default": None}
                for name, (length, nullable) in migration.BASE_STRINGS.items()]
        next(item for item in base if item["name"] == "review_context")["default"] = "'task'::character varying"
        base += [{"name": name, "type": kind(), "nullable": nullable, "default": None}
                 for name, kind, nullable in (("run_number", sa.Integer, True), ("reason", sa.Text, True),
                                             ("created_at", sa.DateTime, False))]
        if complete:
            base.append({"name": "defect_snapshot", "type": JSONB(), "nullable": True, "default": None})
        self.columns = {schema: [dict(item) for item in base] for schema in migration.SCHEMAS}

    def has_table(self, table, *, schema):
        return schema in self.columns

    def get_columns(self, table, *, schema):
        return self.columns[schema]

    def get_pk_constraint(self, table, *, schema):
        return {"constrained_columns": ["id"]}

    def get_unique_constraints(self, table, *, schema):
        return [{"column_names": ["request_id"]}, {"column_names": [
            "job_id", "envelope_id", "institute_id", "patient_id", "visit_id", "rule_set_key"]}]


@pytest.mark.parametrize("complete", [True, False])
def test_known_dual_schema_contract(complete):
    assert migration.schema_state(Inspector(complete)) == {"qc": complete, "public": complete}
    assert migration.down_revision == "20261001_000081"


@pytest.mark.parametrize("failure", ["missing_table", "unknown_column", "type", "nullable", "mixed", "json_type", "default"])
def test_unknown_or_mixed_baseline_refused(failure):
    inspector = Inspector(failure in {"json_type", "default"})
    if failure == "missing_table":
        inspector.columns.pop("public")
    elif failure == "unknown_column":
        inspector.columns["public"].append({"name": "unknown"})
    elif failure in {"type", "nullable"}:
        inspector.columns["qc"][0]["type" if failure == "type" else "nullable"] = sa.Integer() if failure == "type" else True
    elif failure == "mixed":
        inspector.columns["qc"].append({"name": "defect_snapshot", "type": JSONB(), "nullable": True, "default": None})
    else:
        inspector.columns["public"][-1]["type" if failure == "json_type" else "default"] = sa.JSON() if failure == "json_type" else "'{}'"
    with pytest.raises(RuntimeError):
        migration.schema_state(inspector)
