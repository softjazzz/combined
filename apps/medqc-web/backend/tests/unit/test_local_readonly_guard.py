"""连接前拒绝越界，不读取凭据、不连接任何PG。"""

import importlib.util
from pathlib import Path
import pytest

path = (
    Path(__file__).resolve().parents[1] / "integration/local_pg18_readonly_support.py"
)
spec = importlib.util.spec_from_file_location("local_readonly_guard", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "field,value",
    [
        ("host", "192.168.140.177"),
        ("dbname", "medqc"),
        ("dbname", "postgres"),
        ("port", 62997),
        ("user", "postgres"),
        ("password", "synthetic"),
        ("service", "synthetic"),
        ("hostaddr", "127.0.0.1"),
        ("passfile", "wrong"),
    ],
)
def test_local_guard_rejects_before_connect(field, value):
    roles = [
        {"database": db, "role": role, "passfile": "synthetic-" + role}
        for db, role in module.IDENTITIES.items()
    ]
    guard = module.ReadonlyGuard({"host": "127.0.0.1", "port": 5432, "roles": roles})
    first = roles[0]
    params = dict(
        host="127.0.0.1",
        port=5432,
        dbname=first["database"],
        user=first["role"],
        passfile=first["passfile"],
    )
    assert guard.validate(params) == first
    params[field] = value
    with pytest.raises(module.OfflineIsolationError):
        guard.validate(params)
    assert (
        guard.counts["connections"] == 0 and guard.counts["forbidden_connections"] == 1
    )
