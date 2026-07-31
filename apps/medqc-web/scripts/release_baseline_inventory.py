#!/usr/bin/env python3
"""只读生成并校验发布基线改动清单。"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
CATEGORIES = {"A", "B", "C", "D", "E", "F"}
REQUIRED_ENTRY_FIELDS = {
    "path",
    "git_status",
    "sha256",
    "size",
    "category",
    "owner",
    "release_required",
    "reason",
}


class InventoryValidationError(ValueError):
    """发布基线清单不满足受控要求。"""


def _decode_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def parse_porcelain_z(raw: bytes) -> list[dict[str, str | None]]:
    """解析 ``git status --porcelain=v1 -z``，保留重命名前后路径。"""

    tokens = raw.split(b"\0")
    entries: list[dict[str, str | None]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4 or token[2:3] != b" ":
            raise InventoryValidationError("无法解析 Git porcelain 状态记录")
        status = token[:2].decode("ascii", errors="strict")
        path = _decode_path(token[3:])
        original_path: str | None = None
        if "R" in status or "C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise InventoryValidationError(f"重命名记录缺少原路径：{path}")
            original_path = _decode_path(tokens[index])
            index += 1
        entries.append(
            {
                "git_status": status,
                "path": path,
                "original_path": original_path,
            }
        )
    return entries


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_relative_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def classify_path(
    path: str,
    rules: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """按有序规则分类路径；首个命中规则生效。"""

    normalized = _normalize_relative_path(path)
    for index, rule in enumerate(rules):
        pattern = str(rule.get("pattern") or "")
        if not pattern or not fnmatch.fnmatchcase(normalized, pattern):
            continue
        category = rule.get("category")
        required = rule.get("release_required")
        owner = str(rule.get("owner") or "").strip()
        reason = str(rule.get("reason") or "").strip()
        if category not in CATEGORIES:
            raise InventoryValidationError(
                f"分类规则[{index}] category 非法：{category!r}"
            )
        if not isinstance(required, bool) or not owner or not reason:
            raise InventoryValidationError(
                f"分类规则[{index}] 缺少 owner、reason 或布尔 release_required"
            )
        return {
            "category": category,
            "owner": owner,
            "release_required": required,
            "reason": reason,
        }
    return None


def build_entry(
    *,
    repo_root: Path,
    change: Mapping[str, str | None],
    previous: Mapping[str, Any] | None = None,
    classification_rules: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """构造单条清单记录；只读取元数据和摘要，不保存文件内容。"""

    relative_path = _normalize_relative_path(str(change["path"]))
    source_path = repo_root / Path(relative_path)
    is_file = source_path.is_file()
    previous = previous or {}
    automatic = classify_path(relative_path, classification_rules) or {}
    previous_category = str(previous.get("category") or "F")
    category = (
        previous_category
        if previous_category != "F"
        else str(automatic.get("category") or "F")
    )
    if category not in CATEGORIES:
        category = "F"

    return {
        "path": relative_path,
        "original_path": (
            _normalize_relative_path(str(change["original_path"]))
            if change.get("original_path")
            else None
        ),
        "git_status": str(change["git_status"]),
        "sha256": _sha256_file(source_path) if is_file else None,
        "size": source_path.stat().st_size if is_file else 0,
        "category": category,
        "owner": str(
            previous.get("owner")
            or automatic.get("owner")
            or ""
        ),
        "release_required": (
            previous.get("release_required")
            if isinstance(previous.get("release_required"), bool)
            else automatic.get("release_required")
        ),
        "reason": str(
            previous.get("reason")
            or automatic.get("reason")
            or ""
        ),
    }


def _entry_errors(entry: Mapping[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_ENTRY_FIELDS - set(entry))
    if missing:
        errors.append(f"entries[{index}] 缺少字段：{', '.join(missing)}")
        return errors
    category = entry.get("category")
    if category not in CATEGORIES:
        errors.append(f"entries[{index}] category 非法：{category!r}")
    if category == "F":
        errors.append(f"entries[{index}] 未分类：{entry.get('path')}")
    if not str(entry.get("owner") or "").strip():
        errors.append(f"entries[{index}] owner 不能为空")
    if not isinstance(entry.get("release_required"), bool):
        errors.append(f"entries[{index}] release_required 必须为布尔值")
    if not str(entry.get("reason") or "").strip():
        errors.append(f"entries[{index}] reason 不能为空")
    return errors


def validate_inventory(payload: Mapping[str, Any]) -> None:
    """校验所有路径均已完成受控分类。"""

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version 必须为 {SCHEMA_VERSION}，"
            f"实际为 {payload.get('schema_version')!r}"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list):
        errors.append("entries 必须为数组")
    else:
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                errors.append(f"entries[{index}] 必须为对象")
                continue
            errors.extend(_entry_errors(entry, index))
    if errors:
        raise InventoryValidationError("\n".join(errors))


def _run_git(repo_root: Path, *args: str) -> bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={repo_root.as_posix()}",
        "-C",
        str(repo_root),
        *args,
    ]
    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def resolve_repo_root(path: Path) -> Path:
    candidate = path.resolve()
    for possible_root in (candidate, *candidate.parents):
        git_marker = possible_root / ".git"
        is_worktree_marker = git_marker.is_file()
        is_complete_git_dir = (
            git_marker.is_dir()
            and (git_marker / "HEAD").is_file()
            and (git_marker / "config").is_file()
        )
        if is_worktree_marker or is_complete_git_dir:
            output = _run_git(possible_root, "rev-parse", "--show-toplevel")
            return Path(
                output.decode("utf-8", errors="strict").strip()
            ).resolve()
    raise InventoryValidationError(f"未找到 Git 仓库根目录：{candidate}")


def read_git_state(
    repo_root: Path,
    *,
    untracked_files: str = "normal",
) -> tuple[str, str, list[dict[str, str | None]]]:
    if untracked_files not in {"normal", "all"}:
        raise InventoryValidationError(
            "untracked_files 仅允许 normal 或 all"
        )
    head = (
        _run_git(repo_root, "rev-parse", "HEAD")
        .decode("ascii", errors="strict")
        .strip()
    )
    branch = (
        _run_git(repo_root, "branch", "--show-current")
        .decode("utf-8", errors="strict")
        .strip()
    )
    status = _run_git(
        repo_root,
        "status",
        "--porcelain=v1",
        "-z",
        f"--untracked-files={untracked_files}",
    )
    return head, branch, parse_porcelain_z(status)


def _load_previous(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return {}
    return {
        str(entry.get("path")): entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("path")
    }


def _load_classification_rules(path: Path | None) -> list[Mapping[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules") if isinstance(payload, Mapping) else None
    if not isinstance(rules, list):
        raise InventoryValidationError("分类规则文件必须包含 rules 数组")
    for rule in rules:
        if not isinstance(rule, Mapping):
            raise InventoryValidationError("每条分类规则必须为对象")
    return rules


def build_inventory(
    *,
    repo_root: Path,
    release_id: str,
    excluded_paths: Iterable[str] = (),
    previous_path: Path | None = None,
    untracked_files: str = "normal",
    classification_rules: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    head, branch, changes = read_git_state(
        repo_root,
        untracked_files=untracked_files,
    )
    excluded = {_normalize_relative_path(path) for path in excluded_paths}
    previous = _load_previous(previous_path)
    entries = [
        build_entry(
            repo_root=repo_root,
            change=change,
            previous=previous.get(_normalize_relative_path(str(change["path"]))),
            classification_rules=classification_rules,
        )
        for change in changes
        if _normalize_relative_path(str(change["path"])) not in excluded
    ]
    entries.sort(key=lambda item: item["path"])
    tracked_changes = sum(
        1 for entry in entries if entry["git_status"] != "??"
    )
    untracked_entries = sum(
        1 for entry in entries if entry["git_status"] == "??"
    )
    unclassified = sum(1 for entry in entries if entry["category"] == "F")
    return {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": head,
        "git_branch": branch,
        "excluded_control_paths": sorted(excluded),
        "entries": entries,
        "summary": {
            "tracked_changes": tracked_changes,
            "untracked_entries": untracked_entries,
            "unclassified": unclassified,
            "total": len(entries),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary", {})
    rows = [
        "# 发布基线改动清单",
        "",
        f"- 候选标识：`{payload.get('release_id', '')}`",
        f"- Git HEAD：`{payload.get('git_head', '')}`",
        f"- 分支：`{payload.get('git_branch', '')}`",
        f"- 已跟踪改动：{summary.get('tracked_changes', 0)}",
        f"- 未跟踪文件：{summary.get('untracked_entries', 0)}",
        f"- 未分类：{summary.get('unclassified', 0)}",
        "",
        "| 类别 | 发布需要 | Git | 路径 | 责任域 | 原因 |",
        "|---|---:|---|---|---|---|",
    ]
    for entry in payload.get("entries", []):
        required = entry.get("release_required")
        required_text = "是" if required is True else "否" if required is False else "待定"
        reason = str(entry.get("reason") or "").replace("|", "\\|")
        owner = str(entry.get("owner") or "").replace("|", "\\|")
        path = str(entry.get("path") or "").replace("|", "\\|")
        rows.append(
            f"| {entry.get('category', 'F')} | {required_text} | "
            f"`{entry.get('git_status', '')}` | `{path}` | {owner} | {reason} |"
        )
    rows.append("")
    return "\n".join(rows)


def _relative_to_repo(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--release-id", default="baseline-20260731-rc1")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument(
        "--untracked-files",
        choices=("normal", "all"),
        default="normal",
    )
    parser.add_argument("--classification-rules", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    repo_root = resolve_repo_root(args.repo)
    if args.check:
        payload = json.loads(args.check.read_text(encoding="utf-8"))
        try:
            validate_inventory(payload)
        except InventoryValidationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("发布基线清单校验通过：未分类数量为 0")
        return 0

    if args.output is None:
        raise SystemExit("生成模式必须提供 --output")
    excluded_paths = [
        path
        for path in (
            _relative_to_repo(repo_root, args.output),
            _relative_to_repo(repo_root, args.markdown),
        )
        if path
    ]
    payload = build_inventory(
        repo_root=repo_root,
        release_id=args.release_id,
        excluded_paths=excluded_paths,
        previous_path=args.output,
        untracked_files=args.untracked_files,
        classification_rules=_load_classification_rules(
            args.classification_rules
        ),
    )
    _write_json(args.output, payload)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(
            render_markdown(payload),
            encoding="utf-8",
            newline="\n",
        )
    summary = payload["summary"]
    print(
        "发布基线清单已生成："
        f"tracked={summary['tracked_changes']} "
        f"untracked={summary['untracked_entries']} "
        f"unclassified={summary['unclassified']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
