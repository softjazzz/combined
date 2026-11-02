"""只针对显式指定的本轮一次性PG运行联合保护；不读取.env。"""

from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "tests/integration"),
    str(ROOT / "tests/unit"),
    str(ROOT.parent.parent / "medqc-data-integration/src"),
    str(ROOT.parent.parent / "medqc-data-integration/tests"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-directory", required=True)
    args = parser.parse_args()
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    sys.dont_write_bytecode = True
    from joint_pg_support import isolated_pg

    with isolated_pg(args.data_directory):
        import pytest

        return pytest.main(
            [
                "-q",
                "--capture=sys",
                "--tb=short",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "--confcutdir=" + str(ROOT / "tests/integration"),
                str(ROOT / "tests/integration/test_frontpage_sync_joint_pg.py"),
            ]
        )


if __name__ == "__main__":
    raise SystemExit(main())
