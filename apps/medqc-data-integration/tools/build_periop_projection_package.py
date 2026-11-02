"""从当前已提交源码生成第二批独立投影验收包；不连接数据库。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BACKEND = REPO / "apps/medqc-web/backend"


def build(output):
    if output.exists():
        raise RuntimeError("refuse_existing_package")
    data = {}
    files = [
        "contracts/periop-acceptance-contracts.json",
        "tools/major_document_transform.py",
        "tools/periop_transform.py",
        "tools/preflight_periop_projection.py",
        "tools/accept_periop_projection.py",
        "tests/test_periop_transform.py",
        "tests/test_periop_preflight.py",
        "tests/test_periop_projection.py",
        "deploy/windows/accept-periop-projection.ps1",
    ]
    for name in files:
        data[name] = (ROOT / name).read_bytes()
    data["DSH_START.txt"] = (ROOT / "docs/DSH_PERIOP_PROJECTION.txt").read_bytes()
    data["README.md"] = (ROOT / "docs/2026-10-31-periop-projection-acceptance.md").read_bytes()
    helpers = [
        "alembic/env.py",
        "alembic/report_schema_v1.py",
        "alembic/report_schema_v1.json",
        "app/__init__.py",
        "app/database/__init__.py",
        "app/database/connection.py",
        "app/database/models/__init__.py",
        "app/database/models/cdm.py",
        "app/database/models/qc.py",
        "app/database/models/sync.py",
        "app/database/sql/qc_views.sql",
        "scripts/bootstrap_cache_sync_database.py",
        "requirements-cache-bootstrap.txt",
    ]
    for name in helpers:
        data["backend/" + name] = (BACKEND / name).read_bytes()
    for file in sorted((BACKEND / "alembic/versions").glob("*.py")):
        if file.name != "__init__.py":
            data["backend/alembic/versions/" + file.name] = file.read_bytes()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    data["manifest.json"] = (
        json.dumps(
            {
                "package_kind": "periop-projection-acceptance-v2",
                "base_commit": commit,
                "revision": "20261031_000057",
                "source_database": "medqc_periop_acceptance_20261031104123",
                "interfaces": 17,
                "new_columns": 22,
                "source_rows": 9365,
                "inventory_count": len(data) + 1,
                "contains_phi": False,
                "contains_raw_values": False,
                "contains_credentials": False,
                "production_service_modified": False,
            },
            indent=2,
        )
        + "\n"
    ).encode()
    data["CHECKSUMS.txt"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in sorted(data.items())
    ).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(data.items()):
            archive.writestr(name, content)
    print(
        json.dumps(
            {
                "path": str(output),
                "bytes": output.stat().st_size,
                "files": len(data),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args().output)
