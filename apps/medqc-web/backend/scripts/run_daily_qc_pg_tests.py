"""复用owned PG16护栏，只运行新增计划迁移闭环。"""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/integration")]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-directory", required=True)
    args = parser.parse_args()
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    sys.dont_write_bytecode = True
    from joint_pg_support import isolated_pg

    with isolated_pg(args.data_directory):
        import pytest
        raise SystemExit(pytest.main(["-q", "-rs", "--tb=short", "-p", "no:cacheprovider", "-o", "addopts=",
            "--confcutdir=" + str(ROOT / "tests/integration"),
            str(ROOT / "tests/integration/test_daily_qc_migration_pg16.py")]))
