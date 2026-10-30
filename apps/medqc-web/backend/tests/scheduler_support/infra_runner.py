from __future__ import annotations

import pytest

from .infra import InfraIsolation, load_spec


def main(manifest: str) -> int:
    spec = load_spec(manifest)
    with InfraIsolation(spec):
        from app.database import connection
        from scripts.run_qc_scheduler_tests import _install_legacy_demo_db_seam
        _install_legacy_demo_db_seam(connection.engine, connection.SessionLocal)
        return pytest.main([
            "--confcutdir=tests/infra", "-q", "--tb=short", "-o", "addopts=",
            "tests/infra/test_qc_m2_real_infra.py",
        ])
