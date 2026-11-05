"""仅本轮owned PG16，先建立隔离再导入业务模块。"""

import argparse
from pathlib import Path
import os
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/integration")]
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-directory", required=True)
    args = parser.parse_args()
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    sys.dont_write_bytecode = True
    import joint_pg_support

    joint_pg_support.BASELINE_REFRESH_SOURCE = subprocess.check_output(
        [
            "git",
            "show",
            "fa314c6c2:apps/medqc-web/backend/app/services/bundles/refresh_manager.py",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    from joint_pg_support import isolated_pg

    with isolated_pg(args.data_directory):
        import pytest

        raise SystemExit(
            pytest.main(
                [
                    "-q",
                    "-rs",
                    "--tb=short",
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "addopts=",
                    "--confcutdir=" + str(ROOT / "tests/integration"),
                    str(ROOT / "tests/integration/test_bundle_refresh_storage_pg16.py"),
                ]
            )
        )
