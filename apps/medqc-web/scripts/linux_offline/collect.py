"""在Ubuntu22构建依赖及应用目录，产物不得包含运行数据库或患者材料。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def portable(prefix, binaries, out):
    root = out / "tools" / prefix
    (root / "bin").mkdir(parents=True)
    (root / "lib").mkdir()
    for source in binaries:
        source = Path(source).resolve()
        shutil.copy2(source, root / "bin" / source.name)
        if source.name == "7z":
            shutil.copy2(source.parent / "7z.so", root / "bin/7z.so")
        paths = [source] + ([source.parent / "7z.so"] if source.name == "7z" else [])
        for binary in paths:
            result = subprocess.check_output(["ldd", str(binary)], text=True)
            if "not found" in result:
                raise RuntimeError("missing_portable_library")
            for name in re.findall(r"(?:=>\s+)?(/[^\s]+)", result):
                p = Path(name)
                if p.is_file():
                    shutil.copy2(p.resolve(), root / "lib" / p.name)
        wrapper = root / source.name
        wrapper.write_text(
            '#!/bin/sh\nset -eu\nROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$ROOT/lib/ld-linux-x86-64.so.2" --library-path "$ROOT/lib" "$ROOT/bin/'
            + source.name
            + '" "$@"\n'
        )
        wrapper.chmod(0o755)
    (root / "LICENSES").mkdir()
    for p in Path("/usr/share/doc").glob("*"):
        if any(
            x in p.name
            for x in [
                "postgresql",
                "p7zip",
                "libc6",
                "libssl",
                "libpq",
                "libldap",
                "libsasl",
                "liblz4",
                "libzstd",
                "libstdc++",
                "libgcc",
                "libreadline",
                "libgssapi",
                "libkrb",
                "zlib",
                "libgnutls",
                "libnettle",
                "libhogweed",
                "libp11",
                "libtasn",
                "libidn",
                "libunistring",
                "libkeyutils",
                "libcom-err",
                "libk5",
                "libtinfo",
                "libgmp",
                "libffi",
            ]
        ):
            if (p / "copyright").is_file():
                shutil.copy2(
                    p / "copyright", root / "LICENSES" / (p.name + ".copyright")
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    app = repo / "apps/medqc-web"
    out = args.out
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    build_id = os.environ["VITE_MEDQC_BUILD_ID"]
    if not re.fullmatch(r"medqc-web-customer-[0-9]{8}-[0-9]{6}", build_id):
        raise RuntimeError("invalid_build_id")
    runtime = out / "application"
    backend = runtime / "backend"
    for name in subprocess.check_output(
        ["git", "ls-files", "apps/medqc-web/backend"], cwd=repo, text=True
    ).splitlines():
        relative = Path(name).relative_to("apps/medqc-web/backend")
        parts = set(relative.parts)
        if parts & {
            "tests",
            "__pycache__",
            ".tmp",
            "tmp",
            "logs",
            "uploads",
            "qc_results",
            "demo_qc_results",
            "vector",
            "manual_qc_runs",
            "sample_pool_uploads",
            "secrets",
        }:
            continue
        if "private" in name.lower() or relative.name.startswith(
            (".env", "test_", "debug_", "tmp_")
        ):
            continue
        if relative.suffix in {
            ".db",
            ".sqlite",
            ".sqlite3",
            ".log",
            ".pyc",
            ".pkl",
            ".faiss",
        }:
            continue
        if relative.name in {
            "runtime_build.json",
            "product_activation_state.json",
            "activation.json",
            "generate_medqc_activation_code.py",
        }:
            continue
        if "app/storage/qc_diagnostics" in str(relative):
            continue
        src = repo / name
        if not src.is_file():
            continue
        if src.suffix in {".key", ".pem"} and b"PRIVATE KEY" in src.read_bytes():
            raise RuntimeError("private_key_in_source")
        dst = backend / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # 正式规则目录位于backend/app/data；不复制审计/病例文档目录。
    shutil.copytree(app / "dist", runtime / "frontend/dist")
    (backend / "app/data/runtime_build.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "inventory_schema_version": 1,
                "build_id": build_id,
                "git_commit": commit,
            }
        )
        + "\n"
    )
    shutil.copy2(app / "scripts/serve_dist_spa.py", runtime / "serve_dist_spa.py")
    shutil.copytree(app / "scripts/linux_offline/deploy", out / "deploy")
    portable(
        "pg16",
        [
            f"/usr/lib/postgresql/16/bin/{n}"
            for n in ["pg_dump", "pg_restore", "psql", "pg_isready"]
        ],
        out,
    )
    portable("7zip", ["/usr/lib/p7zip/7z"], out)
    (out / "BUILD.json").write_text(
        json.dumps(
            {
                "commit": commit,
                "build_id": build_id,
                "platform": "Ubuntu22.04-x86_64-Python3.10",
                "source_base": "0d3c17c447c873735842eb2a568b38985dfca68f",
                "scope": "Business database and 1026 display; independent CDM is not connected",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
