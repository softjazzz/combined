"""从固定业务提交构建应用包，依赖锁复用已验完整离线包，不带wheel。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

COMMIT = "fa314c6c251fc5dd02eda96a7d30d70642cc1eb0"
FULL_SHA = "72fd98f7116ccbe6105354caa3ec4902cee6ef397b970bed9367d158040495aa"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parents[3]
    subprocess.run(["git", "diff", "--exit-code", "09f627a0e19380d5a605302cc0058482a7c2682f", COMMIT,
                    "--", "apps/medqc-web/backend/requirements.txt"], cwd=repo, check=True)
    if args.out.exists() or args.raw.exists():
        raise ValueError("fresh_output_required")
    subprocess.run([os.sys.executable, "-B", str(here.parent / "linux_offline/collect.py"),
                    "--out", str(args.raw), "--application-only", "--application-commit", COMMIT], check=True)
    kit = args.out / "medqc-app-upgrade"
    kit.mkdir(parents=True)
    shutil.copytree(args.raw / "application", kit / "application")
    shutil.copyfile(args.raw / "BUILD.json", kit / "BUILD.json")
    shutil.copyfile(args.full / "requirements-linux.lock", kit / "requirements-linux.lock")
    for name in ("check_compat.py", "stage_upgrade.py", "apply_proxy.py", "probe_proxy.py", "README-DSH.md"):
        shutil.copyfile(here / name, kit / name)
    (kit / "proxy.env.example").write_text("LLM_HTTP_PROXY=http://192.168.118.99:18090\nLLM_HTTP_PROXY_HOSTS=dashscope.aliyuncs.com\n", encoding="utf-8")
    (kit / "PACKAGE.json").write_text(json.dumps({"kind": "application-only-upgrade", "application_commit": COMMIT,
        "packaging_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "dependency_source_archive_sha256": FULL_SHA, "dependencies_included": False, "tools_included": False,
        "database_migrations_required": False, "deployment_proxy_default": "enabled",
        "automatic_config_update": False, "requires_explicit_apply_proxy": True,
        "runtime_empty_configuration_default": "disabled", "compatibility": "Ubuntu22.04 x86_64 CPython3.10; existing locked dependencies"}, indent=2)+"\n")
    for path in kit.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    hashes = {p.relative_to(kit).as_posix(): digest(p) for p in sorted(kit.rglob("*")) if p.is_file()}
    (kit / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k,v in hashes.items()), encoding="utf-8")
    print(json.dumps({"kit": str(kit), "application_commit": COMMIT, "files": len(hashes)}))


if __name__ == "__main__":
    main()
