"""同步控制复审保护集：固定合成材料，禁止网络、PG及任意子进程。"""

import os
import sys
from pathlib import Path

SUITE = (
    "control_review_fixes", "job_admission", "job_repository", "job_runner",
    "worker_recovery", "sync_scheduler", "control_pipeline", "domain", "service",
    "major_document_contracts", "orders_lab_exam_service", "remaining_contracts",
    "control_api", "control_runtime", "control_profiles", "control_prepare",
    "control_deployment", "control_bootstrap", "control_cli",
)


def main() -> int:
    app = Path(__file__).resolve().parents[1]
    backend = app.parent / "medqc-web/backend"
    sys.path[:0] = [str(backend), str(app / "src"), str(app / "tests")]
    sys.dont_write_bytecode = True
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    from tests.scheduler_support import OfflineIsolation

    with OfflineIsolation():
        import pytest

        os.chdir(app)
        return pytest.main([
            "-q", "--capture=sys", "--tb=short", "-p", "no:cacheprovider", "-o", "addopts=",
            "--confcutdir=" + str(app / "tests"),
            # 该冷导入探针另在CI的OS网络隔离子进程中执行，不放开本护栏的Popen。
            "-k", "not clean_cli_bootstrap_import_does_not_read_secrets_or_change_environment",
            *[str(app / "tests" / ("test_" + name + ".py")) for name in SUITE],
        ])


if __name__ == "__main__":
    raise SystemExit(main())
