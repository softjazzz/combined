"""从已提交Git对象生成单源复审候选；不打包配置秘密，不执行部署。"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
APP = "apps/medqc-web/"
BE = APP + "backend/"
BASE = "60afbc49fbc92cad3b5234a2c7031d6261fcdf1e"
PUBLIC_DATA = {
    "coding_rules.json",
    "custom_rules_33.json",
    "customer_rules_luxian_v1.json",
    "department_rules_oncology_icu.json",
    "drg_weights.json",
    "frontpage_settings.json",
    "luzhou_dip_groups.json",
    "product_activation_public_key.pem",
    "sc_rule_family_map.json",
    "sc146_intrinsic_launch_tiers.json",
    "sichuan_rules_146.json",
    "surgery_procedure_catalog_2025.csv",
}
UNIT = {
    "test_single_donghua_source.py",
    "test_clinical_sources.py",
    "test_latest_full_record_result.py",
    "test_luxian_0609_canonical_result_delivery.py",
    "test_case_material_snapshot.py",
    "test_data_pipelines.py",
    "test_bundle_refresh_storage.py",
    "test_validation_material_selection.py",
    "test_validation_material_display.py",
}
SELF_CHECK = r'''"""仅离线校验候选；--test使用固定应答与内存SQLite。"""
import argparse, ast, hashlib, json, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true")
args = parser.parse_args()
for line in (root / "CHECKSUMS.sha256").read_text().splitlines():
    digest, name = line.split("  ", 1)
    path = (root / name).resolve()
    assert path.is_relative_to(root) and path.is_file(), name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
for path in root.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    assert path.name != "source_bound_storage.py"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.ImportFrom): assert "source_bound_storage" not in (node.module or "")
        if isinstance(node, ast.Import): assert all("source_bound_storage" not in alias.name for alias in node.names)
versions = root / "apps/medqc-web/backend/alembic/versions"
revisions, parents = set(), set()
for path in versions.glob("*.py"):
    if path.name == "__init__.py": continue
    assert "000064" not in path.name
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [x.id for x in targets if isinstance(x, ast.Name)]
            if "revision" in names: revisions.add(ast.literal_eval(node.value))
            if "down_revision" in names:
                value = ast.literal_eval(node.value)
                parents.update(value if isinstance(value, (tuple, list)) else [value])
assert revisions - parents == {"20261105_000063"}
assert (root / "apps/medqc-web/dist/index.html").is_file()
package = json.loads((root / "PACKAGE.json").read_text())
assert package["deployable"] is False and package["ordinary_source"] == "independent_cdm"
if args.test:
    backend = root / "apps/medqc-web/backend"
    subprocess.run([sys.executable, "-B", "scripts/run_qc_scheduler_tests.py", "--profile", "offline", "tests/unit/test_single_donghua_source.py"], cwd=backend, check=True)
print(json.dumps({"checksums":"ok", "syntax":"ok", "migration_head":"20261105_000063", "review_only":True, "model_calls":0, "existing_database_connections":0}))
'''


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def include(name):
    if name.startswith(BE + "app/"):
        rel = Path(name[len(BE) :])
        if set(rel.parts) & {
            "storage",
            "sessions",
            "logs",
            "uploads",
            "secrets",
            "__pycache__",
        }:
            return False
        if rel.suffix == ".py":
            return True
        if rel.parent.as_posix() == "app/data":
            return (
                rel.name in PUBLIC_DATA
                or rel.name.startswith("luxian_0609_")
                and rel.suffix in {".json", ".csv"}
            )
        return rel.as_posix() in {
            "app/services/resources/medical_core_systems_2018.json",
            "app/services/skills/field_mapper.yaml",
            "app/database/sql/qc_views.sql",
        }
    if name.startswith(BE + "alembic/"):
        return name.endswith(".py")
    if name in {
        BE + "requirements.txt",
        BE + "alembic.ini",
        BE + "scripts/run_qc_scheduler_tests.py",
        BE + "scripts/run_single_donghua_pg_tests.py",
        BE + "scripts/run_bundle_refresh_pg_ci.sh",
        APP + "scripts/serve_dist_spa.py",
        APP + "scripts/frontpage-v2-no-network.cjs",
        APP + "scripts/linux_offline/deploy/business.env.example",
        APP + "scripts/linux_offline/deploy/runtime-bundle-schema.json",
    }:
        return True
    if name.startswith(BE + "tests/scheduler_support/"):
        return name.endswith(".py")
    if name.startswith(BE + "tests/unit/"):
        return Path(name).name in UNIT or Path(name).name == "__init__.py"
    if name.startswith(BE + "tests/integration/"):
        return Path(name).name in {
            "joint_pg_support.py",
            "test_single_donghua_source_pg16.py",
            "test_dual_source_acceptance_pg16.py",
            "test_bundle_refresh_storage_pg16.py",
        }
    if name.startswith("docs/plans/2026-11-06-single-donghua-cdm"):
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frontend-receipt", type=Path, required=True)
    args = parser.parse_args()
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("candidate_requires_committed_source")
    head = git("rev-parse", "HEAD").decode().strip()
    receipt = json.loads(args.frontend_receipt.read_text())
    if receipt["commit"] != head:
        raise RuntimeError("frontend_commit_mismatch")
    files = git("ls-tree", "-r", "--name-only", head).decode().splitlines()
    selected = [name for name in files if include(name)]
    changed = git("diff", "--name-only", BASE, head).decode().splitlines()
    selected += [
        name
        for name in changed
        if name not in selected and not name.startswith(".github/")
    ]
    assert not any("000064" in x or "source_bound_storage" in x for x in selected)
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="medqc-single-cdm-candidate-") as tmp:
        package = Path(tmp)
        for name in selected:
            target = package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = git("show", f"{head}:{name}")
            if Path(name).suffix in {".pem", ".key"} and b"PRIVATE KEY-----" in data:
                raise RuntimeError("private_key_in_candidate")
            target.write_bytes(data)
        for src in (ROOT / APP / "dist").rglob("*"):
            if src.is_file():
                if src.suffix == ".map":
                    continue
                target = package / APP / "dist" / src.relative_to(ROOT / APP / "dist")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
        (package / "FRONTEND-BUILD.json").write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
        (package / "CHANGES.patch").write_bytes(git("diff", "--binary", BASE, head))
        (package / "CHANGE-LIST.txt").write_text(
            "\n".join(changed) + "\n", encoding="utf-8"
        )
        (package / "PACKAGE.json").write_text(
            json.dumps(
                {
                    "commit": head,
                    "base": BASE,
                    "deployable": False,
                    "purpose": "review_candidate",
                    "mode": "fixed_donghua_cdm",
                    "ordinary_source": "independent_cdm",
                    "required_migration": "20261105_000063",
                    "database_migrations_required_if_below_063": True,
                    "new_migrations": False,
                    "pdf_new_snapshots": False,
                    "historical_results_recomputed": False,
                    "site_acceptance": False,
                },
                indent=2,
            )
            + "\n"
        )
        (package / "selfcheck.py").write_text(SELF_CHECK, encoding="utf-8")
        lines = []
        for path in sorted(package.rglob("*")):
            if path.is_file():
                lines.append(
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    + "  "
                    + path.relative_to(package).as_posix()
                )
        (package / "CHECKSUMS.sha256").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        output = args.out / ("MedQC-single-donghua-cdm-review-" + head[:9] + ".zip")
        if output.exists():
            raise RuntimeError("refuse_overwriting_candidate")
        with zipfile.ZipFile(
            output, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(package).as_posix())
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        output.with_suffix(output.suffix + ".sha256").write_text(
            digest + "  " + output.name + "\n"
        )
        print(
            json.dumps(
                {
                    "zip": str(output),
                    "bytes": output.stat().st_size,
                    "sha256": digest,
                    "commit": head,
                }
            )
        )


if __name__ == "__main__":
    main()
