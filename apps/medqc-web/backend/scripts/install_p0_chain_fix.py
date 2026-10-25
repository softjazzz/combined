"""已知源码节点的最小补丁安装；整批预检、备份、编译，未知修改不覆盖。"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def node_at(tree, path):
    body = tree.body
    found = None
    for name in path:
        nodes = [node for node in body if getattr(node, "name", None) == name or
                 (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name) or
                 (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))]
        if len(nodes) > 1:
            raise ValueError("ambiguous_source_node")
        if not nodes:
            return None
        found = nodes[0]
        body = getattr(found, "body", [])
    return found


def segment(text, node):
    return "".join(text.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])


def patch_text(text, changes):
    text = text.replace("\r\n", "\n")
    for change in changes:
        tree = ast.parse(text)
        node = node_at(tree, change["path"])
        original = segment(text, node) if node else None
        if original == change["new"]:
            continue
        old_hash = digest(original.encode()) if original is not None else None
        if old_hash not in change["old_sha256"]:
            raise ValueError("unknown_installed_source_do_not_overwrite")
        lines = text.splitlines(keepends=True)
        if node is None:
            anchor = node_at(tree, [change["insert_before"]])
            if anchor is None:
                raise ValueError("source_insert_anchor_missing")
            lines.insert(anchor.lineno - 1, change["new"] + "\n")
        else:
            lines[node.lineno - 1:node.end_lineno] = [change["new"]]
        text = "".join(lines)
    compile(text, "validated_p0_patch.py", "exec")
    return text.encode("utf8")


def install(backend, package, backup_root):
    manifest = json.loads((package / "p0-patch-manifest.json").read_text(encoding="utf8"))
    originals, replacements = {}, {}
    for relative, changes in manifest["nodes"].items():
        target = (backend / relative).resolve()
        target.relative_to(backend)
        originals[relative] = target.read_bytes()
        replacements[relative] = patch_text(originals[relative].decode("utf-8-sig"), changes)
    for relative, expected in manifest["new_files"].items():
        target = (backend / relative).resolve()
        target.relative_to(backend)
        payload = (package / "assets" / relative).read_bytes()
        if digest(payload) != expected:
            raise ValueError("patch_asset_checksum_mismatch")
        if target.exists() and digest(target.read_bytes()) != expected:
            raise ValueError("unknown_existing_helper_do_not_overwrite")
        originals[relative] = target.read_bytes() if target.exists() else None
        compile(payload, str(target), "exec")
        replacements[relative] = payload
    backup = backup_root / ("p0-code-before-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private")
    backup.mkdir(parents=True, exist_ok=False)
    for relative, content in originals.items():
        if content is not None:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            with saved.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if digest(saved.read_bytes()) != digest(content):
                raise ValueError("source_backup_verification_failed")
    (backup / "manifest.json").write_text(json.dumps({key: digest(value) if value is not None else None for key, value in originals.items()}, indent=2), encoding="utf8")
    # 已有 marker 也要备份；它只声明补丁安装，不伪造发行包 build_id。
    marker = backend / ".p0-chain-installed.json"
    marker_before = marker.read_bytes() if marker.exists() else None
    if marker_before is not None:
        (backup / "marker-before.json").write_bytes(marker_before)
    written = []
    try:
        for relative, content in replacements.items():
            target = backend / relative
            current = target.read_bytes() if target.exists() else None
            if current != originals[relative]:
                raise ValueError("source_changed_since_backup")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            written.append(relative)
        marker.write_text(json.dumps({"protocol": "medqc-p0-chain-v1", "backup": str(backup), "source_sha256": {key: digest(value) for key, value in replacements.items()}}), encoding="utf8")
    except BaseException:
        for relative in written:
            original = originals[relative]
            # 新增模块不影响未引用的旧程序，回滚时保留在备份旁，避免递归删除。
            if original is not None:
                (backend / relative).write_bytes(original)
        if marker_before is not None:
            marker.write_bytes(marker_before)
        elif marker.exists():
            marker.replace(backup / "failed-marker.json")
        raise
    return {"event": "p0_code_installed", "files": len(replacements), "backup": str(backup),
            "backend_restart_required": True, "database_writes": 0, "model_calls": 0, "qc_tasks_started": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = install(args.backend.resolve(), Path(__file__).resolve().parent, args.backup_dir)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"event": "p0_install_stopped", "error_type":type(exc).__name__,
                          "code": str(exc) if type(exc) is ValueError else "file_error",
                          "database_writes": 0, "model_calls": 0}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
