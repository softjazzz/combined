"""集中验收源码包：固定白名单，不读取客户配置、统计或数据库。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "backend" if (ROOT / "backend").is_dir()
           else ROOT.parents[1] / "apps/medqc-web/backend")
REQUIRED_SERVICE = (
    "docs/remaining-consolidated-development-validation.md",
    "tools/run_remaining_acceptance.py",
    "tools/remaining_environment.py",
    "tools/validate_remaining_interfaces.py",
    "tools/build_remaining_acceptance_package.py",
    "tools/periop_transform.py",
    "tools/major_document_transform.py",
    "contracts/remaining-interface-contracts.json",
    "contracts/periop-acceptance-contracts.json",
    "src/medqc_ingest/remaining_contracts.py",
    "docs/DSH_REMAINING_ACCEPTANCE.txt",
    "tests/test_remaining_package.py",
    "tests/test_remaining_contracts.py",
    "pyproject.toml",
)
BACKEND_FILES = (
    "scripts/bootstrap_cache_sync_database.py",
    "requirements-cache-bootstrap.txt",
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
    # 正式读取器源码供静态分类，不在本包要求启动规则/模型或整个业务服务。
    "app/services/__init__.py",
    "app/services/document_assembly/__init__.py",
    "app/services/document_assembly/assembler.py",
    "app/services/document_assembly/signatures.py",
    "app/services/bundles/__init__.py",
    "app/services/bundles/assembly.py",
    "app/services/bundles/contracts.py",
    "app/services/bundles/factory.py",
    "app/services/bundles/masking.py",
    "app/services/bundles/refresh_manager.py",
    "app/services/luxian_0609/__init__.py",
    "app/services/luxian_0609/source_evidence_reader.py",
    "app/services/luxian_0609/surgery_procedure_catalog.py",
    "app/services/validation_material_source.py",
    "app/data/surgery_procedure_catalog_2025.csv",
)
FORBIDDEN = {"secrets", "backups", "private-logs", "logs", "__pycache__", "node_modules"}


def validate_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
        or any(ord(value) < 32 for value in name)
        or any(value.lower() in FORBIDDEN or value.startswith(".env") for value in path.parts)
        or path.suffix.lower() in {".dump", ".pgpass", ".log", ".pyc", ".pem", ".key"}
        or path.name.lower() in {"runtime.json", "worker.json", "api.json", "bindings.json"}
    ):
        raise ValueError("unsafe_package_member")


def read_member(base: Path, path: Path, prefix: str = "") -> tuple[str, bytes]:
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("package_file_outside_root")
    name = prefix + path.relative_to(base).as_posix()
    validate_name(name)
    return name, path.read_bytes()


def migration_heads(backend: Path) -> list[str]:
    revisions, parents = set(), set()
    files = sorted((backend / "alembic/versions").glob("*.py"))
    if not files:
        raise ValueError("official_migrations_missing")
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    value = ast.literal_eval(node.value)
                    if target.id == "revision":
                        if not isinstance(value, str) or value in revisions:
                            raise ValueError("official_migration_revision_invalid")
                        revisions.add(value)
                    elif value is not None:
                        parents.update([value] if isinstance(value, str) else value)
    if not revisions or not parents.issubset(revisions):
        raise ValueError("official_migration_chain_incomplete")
    return sorted(revisions - parents)


def add_local_tool_imports(root: Path, paths: set[Path]) -> None:
    """包含工具/测试的本地Python导入闭包，不依赖客户PYTHONPATH上的旧文件。"""
    checked: set[Path] = set()
    while pending := [path for path in paths - checked if path.suffix == ".py"]:
        for path in pending:
            checked.add(path)
            _, source = read_member(root, path)
            tree = ast.parse(source.decode("utf-8-sig"))
            for node in ast.walk(tree):
                modules = ([x.name for x in node.names] if isinstance(node, ast.Import) else
                           [node.module] if isinstance(node, ast.ImportFrom) and not node.level
                           and node.module else [])
                for module in modules:
                    candidate = root / "tools" / (module.split(".", 1)[0] + ".py")
                    if candidate.is_file():
                        paths.add(candidate)


def collect(root: Path, backend: Path) -> tuple[dict[str, bytes], list[str]]:
    if any(not (root / name).is_file() for name in REQUIRED_SERVICE):
        raise ValueError("remaining_components_not_ready")
    if any(not (backend / name).is_file() for name in BACKEND_FILES):
        raise ValueError("official_backend_components_not_ready")
    paths = {root / name for name in REQUIRED_SERVICE}
    paths.update((root / "src/medqc_ingest").rglob("*.py"))
    paths.update((root / "contracts").glob("*.json"))
    paths.update((root / "migrations").glob("*.sql"))
    paths.update((root / "control_migrations").glob("*.sql"))
    paths.update((root / "tools").glob("remaining_*.py"))
    for pattern in ("test_remaining*.py", "test_periop_live.py", "test_periop_transform.py"):
        paths.update((root / "tests").glob(pattern))
    add_local_tool_imports(root, paths)
    for name in (
        "requirements-remaining-acceptance.lock", "requirements-remaining-bootstrap.lock",
        "docs/remaining-offline-dependencies.json",
    ):
        if (root / name).is_file():
            paths.add(root / name)
    files = dict(read_member(root, path) for path in sorted(paths))
    backend_paths = {backend / name for name in BACKEND_FILES}
    backend_paths.update((backend / "alembic/versions").glob("*.py"))
    files.update(read_member(backend, path, "backend/") for path in sorted(backend_paths))
    heads = migration_heads(backend)
    tree = ast.parse((backend / "scripts/bootstrap_cache_sync_database.py").read_text("utf-8-sig"))
    expected = next(
        (ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == "TARGET_REVISION" for t in node.targets)), None
    )
    if heads != [expected]:
        raise ValueError("official_initializer_head_mismatch")
    files["DSH_START.txt"] = (root / "docs/DSH_REMAINING_ACCEPTANCE.txt").read_bytes()
    return files, heads


def complete_dependencies(root: Path, wheelhouse: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """以已验证完整锁及源wheel哈希挑选闭包，拒绝多余/缺失/改写内容。"""
    report_path = root / "docs/remaining-offline-dependencies.json"
    _, proof_data = read_member(root, report_path)
    report = json.loads(proof_data)
    required = ("no_index_install", "require_hashes_install", "pip_check",
                "official_bootstrap_import", "official_orm_import", "alembic_head_verified",
                "remaining_fake_tests_passed")
    if (
        report.get("status") != "verified" or any(report.get(key) is not True for key in required)
        or report.get("target") != {"implementation": "CPython", "python": "3.10",
                                    "platform": "win_amd64"}
    ):
        raise ValueError("complete_dependency_evidence_required")
    selected = set()
    for name in ("requirements-remaining-acceptance.lock", "requirements-remaining-bootstrap.lock"):
        _, data = read_member(root, root / name)
        if report.get("lock_hashes", {}).get(name) != hashlib.sha256(data).hexdigest():
            raise ValueError("complete_dependency_lock_mismatch")
        if name == "requirements-remaining-acceptance.lock":
            for line in data.decode("utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                match = re.fullmatch(r"[A-Za-z0-9_.-]+==\S+ --hash=sha256:([0-9a-f]{64})", line)
                if match is None:
                    raise ValueError("complete_dependency_lock_format")
                selected.add(match[1])
    available = dict(report.get("base_wheel_hashes", {}))
    available.update(report.get("supplement_wheel_hashes", {}))
    expected = {name: value for name, value in available.items() if value in selected}
    if (len(expected) != report.get("complete_locked_distribution_count")
            or len(expected) != len(selected) or not wheelhouse.is_dir()):
        raise ValueError("complete_dependency_inventory_invalid")
    files, hashes = {}, {}
    for path in sorted(wheelhouse.iterdir()):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".whl":
            raise ValueError("complete_wheelhouse_only_wheels")
        name = "wheelhouse/" + path.name
        validate_name(name)
        files[name] = path.read_bytes()
        hashes[path.name] = hashlib.sha256(files[name]).hexdigest()
    if hashes != expected:
        raise ValueError("complete_wheelhouse_hash_mismatch")
    files["standalone-dependency-verification.json"] = (json.dumps({
        "target": report["target"], "wheel_hashes": hashes,
        "lock_hashes": report["lock_hashes"], "no_index_install": True,
        "require_hashes_install": True, "pip_check": True,
        "standalone_offline_dependency_closure_verified": True,
        "customer_acceptance_executed": False, "cache_accessed": False,
        "postgres_accessed": False,
        "source_dependency_report_sha256": hashlib.sha256(proof_data).hexdigest(),
    }, indent=2) + "\n").encode()
    return files, hashes


def build(
    output: Path, *, root: Path = ROOT, backend: Path = BACKEND,
    complete_wheelhouse: Path | None = None,
) -> dict[str, Any]:
    if output.exists() or not output.parent.is_dir() or output.suffix.lower() != ".zip":
        raise ValueError("new_output_zip_required")
    files, heads = collect(root, backend)
    wheel_hashes = {}
    if complete_wheelhouse is not None:
        dependency_files, wheel_hashes = complete_dependencies(root, complete_wheelhouse)
        files.update(dependency_files)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    files["README.md"] = (
        "# Caché其余来源集中验收\n\n按DSH_START.txt一次执行，固定同一run manifest续跑。\n"
        "55来源状态=原13既有证据复用+剩25+围术期17；不调用原13，不操作业务库。\n"
        "源失败/零样本/缺在院对照必须分列，不能用总PASS掩盖；不运行规则、模型或任务。\n"
        "若含wheelhouse，缺依赖从本包完整锁离线安装至新venv，不改全局环境。\n"
    ).encode()
    files["manifest.json"] = (json.dumps({
        "package_kind": "remaining-concentrated-acceptance-v1", "base_commit": commit,
        "official_alembic_heads": heads, "official_modules_copied_verbatim": True,
        "interface_inventory": 55, "prior_evidence_reused_without_calls": 13,
        "execution_scope": {"remaining": 25, "periop": 17},
        "fixed_dates": ["2026-10-26", "2026-10-27", "2026-10-28"],
        "zero_sample_fallback": ["2026-10-19", "2026-10-25"],
        "one_fixed_environment": True, "customer_acceptance_executed": False,
        "contains_phi": False, "contains_raw_values": False, "contains_credentials": False,
        "automatic_incremental": False, "scheduled_tasks_enabled": False,
        "standalone_offline_dependency_closure_verified": bool(wheel_hashes),
        "wheel_hashes": wheel_hashes,
    }, ensure_ascii=False, indent=2) + "\n").encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(content).hexdigest() + "  " + name + "\n"
        for name, content in sorted(files.items())
    ).encode()
    for name in files:
        validate_name(name)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return {"path": str(output), "bytes": output.stat().st_size, "files": len(files),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "standalone_offline_dependency_closure_verified": bool(wheel_hashes)}


def build_dependencies(
    output: Path, *, wheelhouse: Path, verification: Path, root: Path = ROOT
) -> dict[str, Any]:
    """只封装bootstrap补充wheel；完整离线闭包依赖v0.4基础附件。"""
    if output.exists() or not output.parent.is_dir() or output.suffix.lower() != ".zip":
        raise ValueError("new_output_zip_required")
    if not wheelhouse.is_dir():
        raise ValueError("supplement_wheelhouse_required")
    files, hashes = {}, {}
    for path in sorted(wheelhouse.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".whl" or path.is_symlink():
            raise ValueError("wheelhouse_only_wheels")
        name = "wheelhouse/" + path.name
        validate_name(name)
        files[name] = path.read_bytes()
        hashes[path.name] = hashlib.sha256(files[name]).hexdigest()
    report = json.loads(verification.read_text(encoding="utf-8"))
    required = ("no_index_install", "require_hashes_install", "pip_check",
                "official_bootstrap_import", "official_orm_import", "alembic_head_verified",
                "remaining_fake_tests_passed")
    if (
        not hashes or report.get("supplement_wheel_hashes") != hashes
        or report.get("status") != "verified"
        or any(report.get(key) is not True for key in required)
        or report.get("target") != {"implementation": "CPython", "python": "3.10",
                                    "platform": "win_amd64"}
        or not isinstance(report.get("base_wheel_hashes"), dict)
        or not report["base_wheel_hashes"]
    ):
        raise ValueError("supplement_verification_mismatch")
    lock_hashes = {}
    for name in ("requirements-remaining-acceptance.lock", "requirements-remaining-bootstrap.lock"):
        relative, data = read_member(root, root / name)
        files[relative] = data
        lock_hashes[name] = hashlib.sha256(data).hexdigest()
    if report.get("lock_hashes") != lock_hashes:
        raise ValueError("supplement_lock_mismatch")
    safe = {key: report[key] for key in (*required, "target", "status", "base_wheel_hashes")}
    safe.update(supplement_wheel_hashes=hashes, lock_hashes=lock_hashes,
                standalone_dependency_closure_verified=False,
                complete_dependency_closure_verified_with_base=True,
                customer_acceptance_executed=False, cache_accessed=False, postgres_accessed=False)
    files["dependency-verification.json"] = (json.dumps(safe, indent=2) + "\n").encode()
    files["README.txt"] = (
        "CPython3.10 Windows x64补充依赖；必须与v0.4基础wheelhouse配套。\n"
        "仅对新venv执行：pip install --no-index --require-hashes "
        "--find-links BASE/wheelhouse --find-links SUPPLEMENT/wheelhouse "
        "-r requirements-remaining-acceptance.lock\n"
        "不要同时-r旧v0.4锁；psycopg2固定为本次bootstrap要求的2.9.11。\n"
        "开发机只验证离线包/导入/fake测试，不证明客户真实源/PG/ODBC驱动已通过。\n"
    ).encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return {"path": str(output), "bytes": output.stat().st_size, "wheels": len(hashes),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "standalone_dependency_closure_verified": False,
            "complete_dependency_closure_verified_with_base": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dependencies-only", action="store_true")
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--dependency-report", type=Path)
    parser.add_argument("--complete-wheelhouse", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.dependencies_only:
            if args.complete_wheelhouse is not None:
                raise ValueError("complete_wheelhouse_is_source_package_option")
            if args.wheelhouse is None or args.dependency_report is None:
                raise ValueError("supplement_wheelhouse_and_report_required")
            result = build_dependencies(
                args.output, wheelhouse=args.wheelhouse, verification=args.dependency_report
            )
        else:
            if args.wheelhouse is not None or args.dependency_report is not None:
                raise ValueError("dependency_options_require_dependencies_only")
            result = build(args.output, complete_wheelhouse=args.complete_wheelhouse)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "location": "build_remaining_package",
                          "exception_type": type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
