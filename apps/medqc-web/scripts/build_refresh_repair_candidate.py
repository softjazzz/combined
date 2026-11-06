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
VALIDATION = [
    "scripts/run_bundle_refresh_pg_tests.py",
    "scripts/run_bundle_refresh_pg_ci.sh",
    "scripts/validate_local_dual_source_readonly.py",
    "tests/integration/joint_pg_support.py",
    "tests/integration/local_pg18_readonly_support.py",
    "tests/integration/test_bundle_refresh_storage_pg16.py",
    "tests/integration/test_dual_source_acceptance_pg16.py",
    "tests/unit/test_local_readonly_guard.py",
]
SELF_CHECK = """import ast,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
for line in (root/'CHECKSUMS.sha256').read_text().splitlines():
    digest,name=line.split('  ',1)
    path=(root/name).resolve()
    assert path.is_relative_to(root) and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
import importlib.util
for name in ('app/services/bundles/refresh_storage.py','app/services/customer_test_storage.py'):
    path=root/'runtime-overlay/backend'/name
    spec=importlib.util.spec_from_file_location('review_helper_'+path.stem,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
for path in root.rglob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
package=json.loads((root/'PACKAGE.json').read_text())
assert package['database_migrations_required'] is True
assert package['deployable'] is False
print(json.dumps({'checksums':'ok','python_syntax':'ok','review_only':True,'network_calls':0,'database_connections':0}))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--pg18-report", type=Path)
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
        for name in VALIDATION:
            target = package / "validation" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / BACKEND / name).read_bytes())
        for path in (ROOT / "docs/plans").glob(
            "2026-11-05-business-bundle-refresh-repair*.md"
        ):
            (package / path.name).write_bytes(path.read_bytes())
        for path in (ROOT / "docs/plans").glob(
            "2026-11-05-dual-source-local-acceptance*.md"
        ):
            (package / path.name).write_bytes(path.read_bytes())
        if args.pg18_report:
            report = json.loads(args.pg18_report.read_text(encoding="utf-8"))
            assert report["stage"] == "PG18_READONLY"
            assert report["status"] == "PASS_WITH_DOCUMENTED_FIXTURE_LIMITATIONS"
            assert report["existing_data_unchanged"] is True
            assert all(
                report["counts"][key] == 0
                for key in (
                    "forbidden_connections",
                    "write_attempts",
                    "model_attempts",
                    "external_transport_attempts",
                )
            )
            # 仅导出固定字段和计数；不复制原交接、连接配置、正文、患者键或内容哈希。
            evidence = dict(
                stage="PG18_READONLY",
                status=report["status"],
                sample_count=int(report["sample_count"]),
                table_count=len(report["tables"]),
                reader_calls=sum(int(row["calls"]) for row in report["paths"]),
                matched_rows=sum(int(row["matched"]) for row in report["paths"]),
                truncated=sum(int(row["truncated"]) for row in report["paths"]),
                existing_data_unchanged=True,
                forbidden_connections=0,
                write_attempts=0,
                model_attempts=0,
                external_transport_attempts=0,
            )
            (package / "PG18-READONLY-SUMMARY.json").write_text(
                json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
            )
        (package / "DIFF.patch").write_bytes(
            subprocess.check_output(
                [
                    "git",
                    "diff",
                    BASE,
                    head,
                    "--",
                    "apps/medqc-web/backend",
                    "docs/plans/2026-11-05-business-bundle-refresh-repair.md",
                ],
                cwd=ROOT,
            )
        )
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
            validation_base_commit="52fa585c61d0dbbc3df8508308260e46a13b33c8",
            pg18_evidence_included=bool(args.pg18_report),
            validation_requires_owned_pg16=True,
            validation_instructions="Review-only; do not execute against existing databases. PG18 requires original approved handoff, not included.",
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
