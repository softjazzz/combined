"""从已验证完整包原样提取应用；排除wheelhouse、PG、7zip及首次安装器。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


SOURCE_SHA256 = "72fd98f7116ccbe6105354caa3ec4902cee6ef397b970bed9367d158040495aa"
APPLICATION_COMMIT = "09f627a0e19380d5a605302cc0058482a7c2682f"
ARCHIVE_NAME = "MedQC-Ubuntu22-Python310-app-upgrade-09f627a0e.tar.gz"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


def build(source: Path, output: Path):
    if output.exists() or digest(source) != SOURCE_SHA256:
        raise ValueError("fresh_output_and_verified_source_required")
    output.mkdir(parents=True)
    kit = output / "medqc-app-upgrade"
    kit.mkdir()
    source_hashes = {}
    expected = None
    selected = {}
    with tarfile.open(source, "r|gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "medqc-offline" or member.issym() or member.islnk():
                raise ValueError("unsafe_source_archive")
            if not member.isfile():
                continue
            name = "/".join(path.parts[1:])
            if name in source_hashes:
                raise ValueError("duplicate_source_member")
            keep = name.startswith("application/") or name in {"BUILD.json", "VALIDATION.json", "DUAL-SOURCE-VALIDATION.json", "requirements-linux.lock", "deploy/cdm-preflight.py"}
            value = hashlib.sha256()
            chunks = []
            with archive.extractfile(member) as file:
                for data in iter(lambda: file.read(1024 * 1024), b""):
                    value.update(data)
                    if keep or name == "SHA256SUMS":
                        chunks.append(data)
            source_hashes[name] = value.hexdigest()
            if name == "SHA256SUMS":
                expected = dict(line.split("  ", 1)[::-1] for line in b"".join(chunks).decode().splitlines())
            if keep:
                target = kit / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"".join(chunks))
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
                selected[name] = value.hexdigest()
    if expected is None or expected != {key: value for key, value in source_hashes.items() if key != "SHA256SUMS"}:
        raise ValueError("source_internal_checksum_mismatch")
    info = json.loads((kit / "BUILD.json").read_text())
    if info["commit"] != APPLICATION_COMMIT:
        raise ValueError("wrong_application_version")
    here = Path(__file__).resolve().parent
    for name in ("check_compat.py", "stage_upgrade.py", "README-DSH.md"):
        shutil.copyfile(here / name, kit / name)
    packaging_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=here, text=True).strip()
    (kit / "PACKAGE.json").write_text(json.dumps({"kind": "application-only-upgrade", "application_commit": APPLICATION_COMMIT,
        "source_base": info["source_base"], "build_id": info["build_id"], "packaging_commit": packaging_commit,
        "source_archive_sha256": SOURCE_SHA256, "source_internal_files_verified": len(expected),
        "all_selected_source_files_identical": True, "selected_source_files": len(selected),
        "dependencies_included": False, "tools_included": False, "database_migrations_required": False}, indent=2) + "\n")
    manifest = {path.relative_to(kit).as_posix(): digest(path) for path in sorted(kit.rglob("*")) if path.is_file()}
    (kit / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in manifest.items()), encoding="utf-8")
    archive = output / ARCHIVE_NAME
    with tarfile.open(archive, "w:gz", compresslevel=9) as tar:
        tar.add(kit, arcname=kit.name)
    archive.with_name(archive.name + ".sha256").write_text(f"{digest(archive)}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "sha256": digest(archive), "application_commit": APPLICATION_COMMIT}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build(arguments.source, arguments.output)
