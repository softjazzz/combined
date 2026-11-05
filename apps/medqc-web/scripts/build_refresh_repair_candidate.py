"""仅复审源码候选：显式白名单，无安装/部署/数据库/网络操作。"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE = "fa314c6c251fc5dd02eda96a7d30d70642cc1eb0"
BACKEND = "apps/medqc-web/backend/"
FILES = [
    "app/core/acceptance_startup.py",
    "app/core/server_startup.py",
    "app/routers/qc_sample_pools.py",
    "app/services/bundles/refresh_manager.py",
    "app/services/bundles/refresh_storage.py",
    "app/services/customer_test_storage.py",
    "app/services/custom_qc_sample_pool_service.py",
    "app/services/visit_index_service.py",
    "alembic/versions/20261105_000063_bundle_refresh_storage.py",
]
SELF_CHECK = """import ast,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
for line in (root/'CHECKSUMS.sha256').read_text().splitlines():
    digest,name=line.split('  ',1)
    path=(root/name).resolve()
    assert path.is_relative_to(root) and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
for path in (root/'runtime-overlay').rglob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
package=json.loads((root/'PACKAGE.json').read_text())
assert package['database_migrations_required'] is True
assert package['deployable'] is False
print(json.dumps({'checksums':'ok','python_syntax':'ok','review_only':True,'network_calls':0,'database_connections':0}))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    )
    if status:
        raise RuntimeError("candidate_requires_committed_source")
    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary)
        for name in FILES:
            target = package / "runtime-overlay/backend" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / BACKEND / name).read_bytes())
        for path in (ROOT / "docs/plans").glob(
            "2026-11-05-business-bundle-refresh-repair*.md"
        ):
            (package / path.name).write_bytes(path.read_bytes())
        metadata = dict(
            kind="review-only-source-overlay",
            deployable=False,
            base_commit=BASE,
            git_commit=head,
            database_migrations_required=True,
            previous_revision="20261102_000062",
            target_revision="20261105_000063",
            database="business only; no independent CDM",
            required_runtime_permissions=[
                "owner schema USAGE",
                "two refresh tables SELECT/INSERT/UPDATE",
                "actual ID sequence USAGE",
            ],
            model_calls=0,
            clinical_data_included=False,
        )
        (package / "PACKAGE.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (package / "self-check.py").write_text(SELF_CHECK, encoding="utf-8")
        checksums = []
        for path in sorted(package.rglob("*")):
            if path.is_file():
                checksums.append(
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    + "  "
                    + path.relative_to(package).as_posix()
                )
        (package / "CHECKSUMS.sha256").write_text(
            "\n".join(checksums) + "\n", encoding="utf-8"
        )
        subprocess.run(
            ["python", "-B", str(package / "self-check.py")], cwd=package, check=True
        )
        archive = output / ("MedQC-business-refresh-review-" + head[:9] + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    handle.write(path, path.relative_to(package).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(
        digest + "  " + archive.name + "\n", encoding="utf-8"
    )
    print(json.dumps({"file": str(archive), "sha256": digest, "commit": head}))


if __name__ == "__main__":
    main()
