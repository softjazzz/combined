"""v0.4源码交付包：固定白名单、逐文件校验，不携带客户配置或数据。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = frozenset(
    {"secrets", "private-logs", "backups", "logs", "__pycache__", "node_modules"}
)
REQUIRED_FILES = (
    "src/medqc_ingest/control/models.py",
    "src/medqc_ingest/control/profiles.py",
    "src/medqc_ingest/control/admission.py",
    "src/medqc_ingest/control/ports.py",
    "src/medqc_ingest/control/memory.py",
    "src/medqc_ingest/control/postgres.py",
    "src/medqc_ingest/control/runner.py",
    "src/medqc_ingest/control/worker.py",
    "src/medqc_ingest/control/pipeline.py",
    "src/medqc_ingest/control/recovery.py",
    "src/medqc_ingest/control/scheduler.py",
    "src/medqc_ingest/control/api.py",
    "src/medqc_ingest/control/auth.py",
    "src/medqc_ingest/control/cli.py",
    "src/medqc_ingest/control/runtime.py",
    "src/medqc_ingest/control/bootstrap.py",
    "control_migrations/001_job_control.sql",
    "tools/initialize_sync_control.py",
    "tools/run_sync_control.py",
    "tools/prepare_sync_control_acceptance.py",
    "tools/accept_sync_control.py",
    "tools/build_sync_control_package.py",
    "deploy/windows/sync-worker.disabled.xml",
    "deploy/windows/sync-api.disabled.xml",
    "deploy/systemd/medqc-sync-worker.service",
    "deploy/systemd/medqc-sync-api.service",
    "docs/DSH_SYNC_CONTROL_ACCEPTANCE.txt",
    "docs/sync-control-operations.md",
    "docs/sync-control-development-acceptance.md",
    "pyproject.toml",
)


def validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or any(ord(character) < 32 for character in name)
        or path.is_absolute()
        or ".." in path.parts
        or any(part.lower() in FORBIDDEN_PARTS for part in path.parts)
        or any(part.startswith(".env") for part in path.parts)
        or path.suffix.lower() in {".dump", ".pgpass", ".pyc", ".pem", ".key", ".log"}
        or name.lower().endswith(("runtime.json", "worker.json", "api.json", "bindings.json"))
    ):
        raise ValueError("unsafe_package_member")


def protected_read(root: Path, path: Path) -> tuple[str, bytes]:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError("package_file_outside_root")
    name = path.relative_to(root).as_posix()
    validate_member_name(name)
    return name, resolved.read_bytes()


def example_configuration() -> dict[str, dict[str, Any]]:
    postgres = {
        "host": "127.0.0.1",
        "port": 5432,
        "database": "medqc_sync_control_acceptance___TIMESTAMP14__",
        "user": "medqc_job_worker",
        "passfile": "__ABSOLUTE_CONTROL_PASSFILE__",
    }
    catalog = {
        "core13": {
            "enabled": True,
            "ready": True,
            "incremental_interfaces": ["web.mr"],
            "scheduled_interfaces": ["web.mr"],
        },
        "periop13": {"enabled": False, "ready": False},
    }
    return {
        "examples/control-worker.example.json": {
            "postgres": postgres,
            "catalog": catalog,
            "worker": {
                "worker_id": "worker-1",
                "poll_seconds": 1,
                "heartbeat_seconds": 10,
                "lease_seconds": 180,
                "bindings_file": "__ABSOLUTE_WORKER_BINDINGS_FILE__",
            },
        },
        "examples/control-api.example.json": {
            "postgres": dict(postgres, user="medqc_job_api"),
            "catalog": catalog,
            "api": {
                "bind": "127.0.0.1",
                "port": 8766,
                "tokens_file": "__ABSOLUTE_API_TOKEN_FILE__",
            },
        },
        "examples/worker-bindings.example.json": {
            "profiles": {
                "core13": {
                    "source_config_file": "__ABSOLUTE_SOURCE_REFERENCE_CONFIG__",
                    "chunk_size": 1000,
                    "ingest": {
                        "host": "127.0.0.1",
                        "port": 5432,
                        "database": "medqc_sync_ingest_acceptance___TIMESTAMP14__",
                        "user": "medqc_sync",
                        "passfile": "__ABSOLUTE_DATA_PASSFILE__",
                    },
                    "cdm": {
                        "host": "127.0.0.1",
                        "port": 5432,
                        "database": "medqc_sync_cdm_acceptance___TIMESTAMP14__",
                        "user": "medqc_sync",
                        "passfile": "__ABSOLUTE_DATA_PASSFILE__",
                    },
                }
            }
        },
    }


def collect(root: Path) -> dict[str, bytes]:
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError("package_components_not_ready")
    paths = {root / name for name in REQUIRED_FILES}
    paths.update((root / "src/medqc_ingest").rglob("*.py"))
    paths.update((root / "contracts").glob("*.json"))
    # PG集成测试的正式SQL和fixture一同交付；DSH不会自动执行这些opt-in测试。
    paths.update((root / "migrations").glob("*.sql"))
    # 包含新控制面纯测试，PG测试不由客户盲跑，按明确标志跳过。
    paths.update((root / "tests").glob("test_control_*.py"))
    for pattern in ("test_job_*.py", "test_worker_*.py", "test_sync_scheduler.py"):
        paths.update((root / "tests").glob(pattern))
    helper = root / "tests/control_pg_fixture.py"
    if helper.is_file():
        paths.add(helper)
    files = dict(protected_read(root, path) for path in sorted(paths))
    for optional in (
        "requirements-sync-control.lock", "requirements-sync-control-dev.lock",
        "requirements-control.lock", "docs/sync-control-offline-dependencies.json",
    ):
        if (root / optional).is_file():
            files.update([protected_read(root, root / optional)])
    files["DSH_START.txt"] = (root / "docs/DSH_SYNC_CONTROL_ACCEPTANCE.txt").read_bytes()
    for name, content in example_configuration().items():
        validate_member_name(name)
        files[name] = (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode()
    files["README.md"] = (
        "# MedQC独立同步服务 v0.4候选包\n\n"
        "入口和边界以DSH_START.txt为准。交付包不会注册/启用任务或修改客户环境。\n"
        "先运行fake控制流程验证；新控制PG验证必须显式授权写控制元数据，只允许全新空验收控制库。\n"
        "fake/控制PG通过不代表Caché、raw/CDM、HTTP鉴权、备份恢复或生产部署已经通过。\n"
        "人工请求和计划走同一任务控制层；示例计划和部署模板默认禁用。\n"
        "所有example.json均有未替换占位符，不可直接作为运行配置。\n"
        "原13接口代码/注册表和正式业务库保持保护，第二批未获真实源验收时保持禁用。\n"
        "本包可从源码launcher运行，无需先安装本项目wheel；第三方依赖仍需预先存在或离线准备。\n"
    ).encode()
    return files


def build(output: Path, *, root: Path = ROOT, wheelhouse: Path | None = None) -> dict[str, Any]:
    if output.exists() or not output.parent.is_dir() or output.suffix.lower() != ".zip":
        raise ValueError("new_package_output_required")
    files = collect(root)
    wheels = {}
    if wheelhouse is not None:
        if not wheelhouse.is_dir():
            raise ValueError("wheelhouse_directory_required")
        for path in sorted(wheelhouse.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".whl" or path.is_symlink():
                raise ValueError("wheelhouse_only_wheels")
            name = "wheelhouse/" + path.name
            validate_member_name(name)
            files[name] = path.read_bytes()
            wheels[path.name] = hashlib.sha256(files[name]).hexdigest()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project)
    manifest = {
        "package": "medqc-sync-control-v0.4",
        "source_version": match[1] if match else None,
        "commit": commit,
        "contains_phi": False,
        "contains_raw_values": False,
        "contains_keys": False,
        "customer_acceptance_executed": False,
        "production_enabled": False,
        "scheduled_task_registered": False,
        "offline_dependency_closure_verified": False,
        "wheel_hashes": wheels,
        "dependency_status": "supply_and_verify_offline_before_missing_imports_are_accepted",
        "runtime_configuration_included": False,
        "example_placeholders_required": True,
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode()
    for name in files:
        validate_member_name(name)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return {
        "path": str(output),
        "bytes": output.stat().st_size,
        "files": len(files),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "offline_dependency_closure_verified": False,
    }


def build_dependencies(
    output: Path, *, wheelhouse: Path, verification: Path, root: Path = ROOT
) -> dict[str, Any]:
    """独立依赖附件；验证记录必须绑定实际wheel和两份锁文件，不猜测闭包。"""
    if output.exists() or not output.parent.is_dir() or output.suffix.lower() != ".zip":
        raise ValueError("new_package_output_required")
    if not wheelhouse.is_dir():
        raise ValueError("wheelhouse_directory_required")
    files: dict[str, bytes] = {}
    hashes = {}
    for path in sorted(wheelhouse.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".whl" or path.is_symlink():
            raise ValueError("wheelhouse_only_wheels")
        name = "wheelhouse/" + path.name
        validate_member_name(name)
        files[name] = path.read_bytes()
        hashes[path.name] = hashlib.sha256(files[name]).hexdigest()
    if not hashes:
        raise ValueError("wheelhouse_empty")
    report = json.loads(verification.read_text(encoding="utf-8"))
    required = ("no_index_install", "require_hashes_install", "pip_check", "in_process_api",
                "control_tests_passed", "wheel_installed_independently")
    if (
        report.get("status") != "verified"
        or report.get("target") != {"implementation": "CPython", "python": "3.10",
                                    "platform": "win_amd64"}
        or any(report.get(key) is not True for key in required)
        or report.get("wheel_hashes") != hashes
    ):
        raise ValueError("dependency_verification_mismatch")
    lock_hashes = {}
    for name in ("requirements-sync-control.lock", "requirements-sync-control-dev.lock"):
        relative, content = protected_read(root, root / name)
        files[relative] = content
        lock_hashes[name] = hashlib.sha256(content).hexdigest()
    if report.get("lock_hashes") != lock_hashes:
        raise ValueError("dependency_lock_mismatch")
    # 只输出允许的证据字段，忽略调用方报告里可能包含的本机路径或日志。
    safe_report = {key: report[key] for key in (*required, "status", "target")}
    safe_report.update(wheel_hashes=hashes, lock_hashes=lock_hashes)
    safe_report.update(
        cache_accessed=False, customer_acceptance_executed=False,
        offline_dependency_closure_verified=True,
    )
    files["dependency-verification.json"] = (
        json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    files["README.txt"] = (
        "CPython 3.10 / Windows x64依赖附件。先核对CHECKSUMS，再在新venv安装。\n"
        "python -m pip install --no-index --require-hashes --find-links wheelhouse "
        "-r requirements-sync-control.lock\n"
        "测试/build工具可选：再添加-r requirements-sync-control-dev.lock。\n"
        "仅开发机离线闭包/进程内API已验证，不代表客户驱动、Caché或数据面已验证。\n"
    ).encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(value).hexdigest() + "  " + name + "\n"
        for name, value in sorted(files.items())
    ).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return {
        "path": str(output), "bytes": output.stat().st_size, "wheels": len(hashes),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "offline_dependency_closure_verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--dependencies-only", action="store_true")
    parser.add_argument("--dependency-report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.dependencies_only:
            if args.wheelhouse is None or args.dependency_report is None:
                raise ValueError("dependency_wheelhouse_and_report_required")
            result = build_dependencies(
                args.output, wheelhouse=args.wheelhouse, verification=args.dependency_report
            )
        else:
            if args.dependency_report is not None:
                raise ValueError("dependency_report_requires_dependencies_only")
            result = build(args.output, wheelhouse=args.wheelhouse)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "location": "build_sync_control_package",
                    "exception_type": type(error).__name__,
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
