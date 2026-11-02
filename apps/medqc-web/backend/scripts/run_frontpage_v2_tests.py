"""首页V2隔离验收入口：禁止真实网络/.env/业务库，SQLite仅内存或本次临时目录。"""

from __future__ import annotations
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def main() -> int:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    sys.dont_write_bytecode = True
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tests.scheduler_support import OfflineIsolation
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url

    with TemporaryDirectory(prefix="medqc-frontpage-test-") as temp:
        base = Path(temp).resolve()
        guard = OfflineIsolation()
        with guard:
            os.environ["DB_SCHEMA_MODE"] = "single"
            original = sa.create_engine

            def create(url, *args, **kwargs):
                parsed = make_url(url)
                if parsed.drivername.startswith("sqlite") and parsed.database not in (
                    None,
                    "",
                    ":memory:",
                ):
                    path = Path(parsed.database).resolve()
                    if not path.is_relative_to(base):
                        raise AssertionError("unexpected SQLite path")
                    guard._allowed_sqlite_paths.add(path)
                return original(url, *args, **kwargs)

            sa.create_engine = create
            try:
                import pytest

                files = sorted((root / "tests/unit").glob("test_frontpage_qc_v2_*.py"))
                return pytest.main(
                    [
                        "-q",
                        "--capture=sys",
                        "--tb=short",
                        "-p",
                        "no:cacheprovider",
                        "-o",
                        "addopts=",
                        "--basetemp=" + str(base / "pytest"),
                        "--confcutdir=" + str(root / "tests/unit"),
                        *[str(p) for p in files],
                    ]
                )
            finally:
                sa.create_engine = original


if __name__ == "__main__":
    raise SystemExit(main())
