"""QC 调度器 M0/M1 测试入口；默认严格离线且不读取业务配置。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from types import ModuleType

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SUITES: dict[str, tuple[str, ...]] = {
    "m0-isolation": (
        "tests/unit/test_qc_scheduler_isolation.py",
    ),
    "m1-admission": (
        "tests/unit/test_llm_gateway_admission.py",
        "tests/unit/test_llm_gateway_cancellation.py",
        "tests/unit/test_llm_gateway_api.py",
        "tests/unit/test_qc_scheduler_execution_policy.py",
        "tests/unit/test_llm_dispatch_routing.py",
        "tests/unit/test_llm_dispatch_runtime_identity.py",
    ),
    "compatibility": (
        "tests/unit/test_shared_http_client.py",
        "tests/unit/test_luxian_0609_task_runtime_identity.py",
        "tests/unit/test_failed_rule_retry.py",
        "tests/unit/test_qc_sichuan_batch_cancel.py",
        "tests/unit/test_latest_full_record_result.py",
        "tests/unit/test_luxian_0609_record_result_read_model.py",
        "tests/unit/test_qc_sichuan_record_result_exports.py",
        "tests/unit/test_qc_execution_timing.py",
        "tests/unit/test_record_execution_timing.py",
        "tests/unit/test_luxian_0609_canonical_result_finalizer.py",
        "tests/unit/test_luxian_0609_execution_privacy_identity.py",
    ),
    "compatibility-restart": (
        "tests/unit/test_luxian_0609_task_restart_persistence.py",
    ),
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default="offline",
        choices=("offline", "isolated-infra"),
        help="isolated-infra 尚未实现，当前会明确拒绝",
    )
    parser.add_argument("--suite", choices=tuple(SUITES))
    parser.add_argument(
        "--allow-reviewed-restart-probe",
        action="store_true",
        help="仅允许固定 hash 的合成跨进程重启 probe；默认严格禁止子进程",
    )
    parser.add_argument("tests", nargs="*", help="附加的显式 pytest node id")
    return parser.parse_args(argv)


def _selected_tests(args: argparse.Namespace) -> list[str]:
    selected = list(SUITES.get(args.suite, ()))
    selected.extend(args.tests)
    if not selected:
        raise SystemExit("请通过 --suite 或位置参数显式选择测试，拒绝默认运行全仓")
    restart_test = "tests/unit/test_luxian_0609_task_restart_persistence.py"
    selects_restart = any(
        node_id.split("::", 1)[0].replace("\\", "/") == restart_test
        for node_id in selected
    )
    if selects_restart and not args.allow_reviewed_restart_probe:
        raise SystemExit(
            "跨进程重启保护集默认禁用；必须显式传入 "
            "--allow-reviewed-restart-probe"
        )
    missing = sorted(
        {
            node_id.split("::", 1)[0]
            for node_id in selected
            if not Path(node_id.split("::", 1)[0]).is_file()
        }
    )
    if missing:
        raise SystemExit("测试清单包含尚不存在的文件：" + ", ".join(missing))
    return selected


def _install_legacy_demo_db_seam(engine, sessions) -> None:
    """隔离无关 demo import 的磁盘建库副作用，不替换 QC workspace owner。"""

    module_name = "app.database.demo_db"
    demo_db = ModuleType(module_name)
    demo_db.DATABASE_URL = "sqlite:///:memory:"
    demo_db.engine = engine
    demo_db.SessionLocal = sessions

    def get_db():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def get_db_context():
        session = sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    demo_db.get_db = get_db
    demo_db.get_db_context = get_db_context
    demo_db.init_db = lambda: None
    sys.modules[module_name] = demo_db

    import app.database as database_package

    database_package.demo_db = demo_db


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.profile != "offline":
        raise SystemExit(
            "isolated-infra profile 尚未实施；拒绝连接本机 PG、RabbitMQ 或 Provider 端口"
        )

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))

    from tests.scheduler_support import OfflineIsolation

    selected = _selected_tests(args)
    with OfflineIsolation(
        allow_reviewed_restart_probe=args.allow_reviewed_restart_probe
    ):
        # 某些旧 persistence 模块要求导入后存在 SessionLocal；这里只绑定无表的内存库。
        from app.database import connection
        import app.database as database_package

        engine = create_engine("sqlite://")
        synthetic_sessions = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        # 旧 workspace 模块会在导入时复制 connection.engine/SessionLocal；两者必须
        # 同时指向同一个合成内存库，不能只替换会话工厂后让只读表元数据看到 None。
        connection.engine = engine
        connection.SessionLocal = synthetic_sessions
        database_package.engine = engine
        database_package.SessionLocal = synthetic_sessions
        _install_legacy_demo_db_seam(engine, synthetic_sessions)
        try:
            return pytest.main(
                [
                    "--confcutdir=tests/unit",
                    "-p",
                    "tests.scheduler_support.pytest_plugin",
                    "-q",
                    "--tb=short",
                    "-o",
                    "addopts=",
                    *selected,
                ]
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
