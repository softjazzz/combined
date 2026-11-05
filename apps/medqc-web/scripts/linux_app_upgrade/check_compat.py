"""只检查平台、包完整性与现有venv；不导入应用、不读.env、不连接数据库。"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def verify_package(kit: Path) -> dict:
    kit = kit.resolve(strict=True)
    if (kit / "SHA256SUMS").is_symlink():
        raise ValueError("symlink_manifest_rejected")
    manifest = {}
    for line in (kit / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in manifest or len(digest) != 64:
            raise ValueError("invalid_package_manifest")
        target = kit / path
        if target.is_symlink() or kit not in target.resolve(strict=True).parents:
            raise ValueError("unsafe_package_member")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("package_checksum_mismatch")
        manifest[relative] = digest
    actual = {path.relative_to(kit).as_posix() for path in kit.rglob("*") if path.is_file()}
    if actual != set(manifest) | {"SHA256SUMS"}:
        raise ValueError("package_file_set_changed")
    build = json.loads((kit / "BUILD.json").read_text(encoding="utf-8"))
    if not re.fullmatch(r"medqc-web-customer-[0-9]{8}-[0-9]{6}", build.get("build_id", "")) or not re.fullmatch(r"[0-9a-f]{40}", build.get("commit", "")):
        raise ValueError("invalid_build_identity")
    return build


def version_differences(lock: Path, resolver=metadata.version) -> list[dict]:
    differences = []
    for line in lock.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = line.split(" --hash=", 1)[0]
        name, expected = requirement.split("==", 1)
        try:
            actual = resolver(name)
        except metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            differences.append({"distribution": name, "expected": expected, "installed": actual})
    return differences


def check(kit: Path, root: Path) -> dict:
    build = verify_package(kit)
    os_release = platform.freedesktop_os_release()
    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "22.04" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 10):
        raise ValueError("requires_Ubuntu22_x86_64_Python310")
    root = root.resolve(strict=True)
    if not (root / "venv").is_symlink() or Path(sys.prefix).resolve() != (root / "venv").resolve() or sys.prefix == sys.base_prefix:
        raise ValueError("must_use_existing_business_venv_python")
    differences = version_differences(kit / "requirements-linux.lock")
    if differences:
        return {"ok": False, "error": "dependency_versions_differ_from_validated_set", "differences": differences}
    env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-I", "-B", "-m", "pip", "check"], capture_output=True, text=True, env=env)
    if result.returncode:
        return {"ok": False, "error": "pip_check_failed"}
    # 仅导入第三方二进制依赖；子进程不加载app或业务.env，Python网络入口拒绝。
    probe = """
import socket
def denied(*args, **kwargs): raise RuntimeError('compatibility_probe_network_denied')
socket.socket.connect = denied
socket.create_connection = denied
socket.getaddrinfo = denied
import fastapi,uvicorn,pydantic,sqlalchemy,psycopg2,asyncpg,fitz,pdfplumber,pandas,numpy,faiss,openpyxl,docx,reportlab,cryptography,sklearn
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", probe], capture_output=True, text=True, env=env, timeout=90)
    if result.returncode:
        return {"ok": False, "error": "native_dependency_import_failed"}
    return {"ok": True, "commit": build["commit"], "build_id": build["build_id"], "exact_validated_dependencies": True,
            "pip_check": True, "native_imports": True, "database_connections": 0, "model_calls": 0, "dependencies_installed": 0}


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/data/medqc/business"))
    args = parser.parse_args()
    try:
        report = check(Path(__file__).resolve().parent, args.root)
    except Exception as error:
        report = {"ok": False, "error": str(error) if isinstance(error, ValueError) else type(error).__name__}
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
