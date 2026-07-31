#!/usr/bin/env python3
"""校验正式客户版发布所依赖的源码状态。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


PUBLIC_API_DOMAIN = "api.medqc.com"
VALID_CATEGORIES = {"A", "B", "C", "D", "E"}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".ts",
    ".tsx",
    ".vue",
}
FORBIDDEN_DIRECTORY_NAMES = {
    ".codegraph",
    ".release-packages",
    ".worktrees",
    "__pycache__",
    "coverage",
    "dist",
    "htmlcov",
    "logs",
}
FORBIDDEN_LOCAL_FILENAMES = {
    "6.6.6304.400local.stat",
    "inputstat.dat",
    "sgim_punc.bin",
    "share.config",
    "user.config",
}


def _normalize(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def _inventory_is_classified(inventory: Mapping[str, Any]) -> bool:
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, Mapping):
            return False
        if entry.get("category") not in VALID_CATEGORIES:
            return False
        if not str(entry.get("owner") or "").strip():
            return False
        if not isinstance(entry.get("release_required"), bool):
            return False
        if not str(entry.get("reason") or "").strip():
            return False
    return True


def _is_forbidden_local_path(path: str) -> bool:
    normalized = _normalize(path)
    parts = PurePosixPath(normalized).parts
    if any(part in FORBIDDEN_DIRECTORY_NAMES for part in parts):
        return True
    name = parts[-1] if parts else ""
    lower_name = name.lower()
    return (
        lower_name.startswith("tmp-")
        or lower_name.startswith("tmp_")
        or lower_name in FORBIDDEN_LOCAL_FILENAMES
        or lower_name.endswith((".db", ".sqlite", ".sqlite3", ".log"))
    )


def _is_sensitive_filename(path: str) -> bool:
    name = PurePosixPath(_normalize(path)).name.lower()
    if name in {".env.example", ".env.sample", ".env.template"}:
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        and name not in {".env.production"}
        or name.endswith((".key", ".p12", ".pfx", ".pem"))
    )


def _read_small_text(path: Path, *, limit: int = 2 * 1024 * 1024) -> str | None:
    if not path.is_file() or path.stat().st_size > limit:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _contains_private_key(path: Path) -> bool:
    text = _read_small_text(path)
    if text is None:
        return False
    markers = {
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
    }
    return any(line.strip() in markers for line in text.splitlines())


def _should_scan_public_api(path: str) -> bool:
    normalized = _normalize(path)
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix not in TEXT_SUFFIXES and not normalized.endswith(
        (".env.production", "vite.config.mjs")
    ):
        return False
    return (
        normalized.startswith("apps/medqc-web/src/")
        or normalized == "apps/medqc-web/.env.production"
        or normalized == "apps/medqc-web/vite.config.mjs"
    )


def _contains_public_api_domain(repo_root: Path, path: str) -> bool:
    if not _should_scan_public_api(path):
        return False
    text = _read_small_text(repo_root / Path(_normalize(path)))
    return text is not None and PUBLIC_API_DOMAIN in text


def verify_source_state(
    *,
    repo_root: Path,
    inventory: Mapping[str, Any],
    changed_paths: Iterable[str],
    scan_paths: Iterable[str] | None = None,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    """返回不包含文件内容和密钥值的源码预检报告。"""

    normalized_changes = sorted({_normalize(path) for path in changed_paths})
    normalized_scan_paths = sorted(
        {
            _normalize(path)
            for path in (
                scan_paths if scan_paths is not None else normalized_changes
            )
        }
    )
    reason_codes: list[str] = []
    warnings: list[str] = []
    findings: dict[str, list[str]] = {
        "forbidden_paths": [],
        "sensitive_files": [],
        "public_api_files": [],
    }

    if not _inventory_is_classified(inventory):
        reason_codes.append("unclassified_inventory")

    if normalized_changes:
        if allow_dirty:
            warnings.append("dirty_git_tree_allowed_for_development")
        else:
            reason_codes.append("dirty_git_tree")

    for path in normalized_changes:
        if _is_forbidden_local_path(path):
            findings["forbidden_paths"].append(path)
        absolute = repo_root / Path(path)
        if _is_sensitive_filename(path) or _contains_private_key(absolute):
            findings["sensitive_files"].append(path)

    for path in normalized_scan_paths:
        absolute = repo_root / Path(path)
        if _is_sensitive_filename(path) or _contains_private_key(absolute):
            if path not in findings["sensitive_files"]:
                findings["sensitive_files"].append(path)
        if _contains_public_api_domain(repo_root, path):
            findings["public_api_files"].append(path)

    if findings["forbidden_paths"]:
        reason_codes.append("forbidden_local_path")
    if findings["sensitive_files"]:
        reason_codes.append("sensitive_source_file")
    if findings["public_api_files"]:
        reason_codes.append("forbidden_public_api_domain")

    reason_codes = list(dict.fromkeys(reason_codes))
    return {
        "schema_version": 1,
        "passed": not reason_codes,
        "non_releasable": bool(allow_dirty and normalized_changes),
        "reason_codes": reason_codes,
        "warnings": warnings,
        "changed_path_count": len(normalized_changes),
        "findings": findings,
    }


def _resolve_repo_root(path: Path) -> Path:
    candidate = path.resolve()
    for possible_root in (candidate, *candidate.parents):
        marker = possible_root / ".git"
        if marker.is_file() or (
            marker.is_dir()
            and (marker / "HEAD").is_file()
            and (marker / "config").is_file()
        ):
            return possible_root
    raise RuntimeError(f"未找到 Git 仓库根目录：{candidate}")


def _run_git(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo_root.as_posix()}",
            "-C",
            str(repo_root),
            *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _changed_paths(repo_root: Path) -> list[str]:
    raw = _run_git(
        repo_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
    )
    tokens = raw.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        status = token[:2].decode("ascii", errors="strict")
        paths.append(token[3:].decode("utf-8", errors="surrogateescape"))
        if "R" in status or "C" in status:
            index += 1
    return paths


def _runtime_scan_paths(repo_root: Path) -> list[str]:
    raw = _run_git(
        repo_root,
        "ls-files",
        "-z",
        "--",
        "apps/medqc-web/src",
        "apps/medqc-web/.env.production",
        "apps/medqc-web/vite.config.mjs",
    )
    return [
        token.decode("utf-8", errors="surrogateescape")
        for token in raw.split(b"\0")
        if token
    ]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    repo_root = _resolve_repo_root(args.repo)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    changed_paths = [
        path
        for path in _changed_paths(repo_root)
        if _normalize(path).startswith("apps/medqc-web/")
    ]
    scan_paths = sorted(
        set(changed_paths) | set(_runtime_scan_paths(repo_root))
    )
    report = verify_source_state(
        repo_root=repo_root,
        inventory=inventory,
        changed_paths=changed_paths,
        scan_paths=scan_paths,
        allow_dirty=args.allow_dirty,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
    print(serialized, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
