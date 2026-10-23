"""备份单个源码文件后安装 044 合同修复，并用已录制应答离线验收；失败恢复原文件。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def replay_verified(events, expected_calls):
    finished = [row for row in events if row.get("event") == "finished"]
    results = finished[0].get("results", []) if len(finished) == 1 else []
    return (
        len(results) == 1
        and results[0].get("rule") == "LX0609-07-01-02"
        and results[0].get("status") == "non_compliant"
        and not any(row.get("event") in {"replay_stopped", "diagnostic_error"} for row in events)
        and sum(row.get("event") == "replay_matched" for row in events) == expected_calls
        and any(row.get("event") == "existing_results_check" and row.get("items_unchanged") is True for row in events)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--replay-file", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    backend = Path(args.backend).resolve()
    target = (backend / "app/services/luxian_0609/native_transfusion_execution.py").resolve()
    target.relative_to(backend)
    manifest = json.loads((here / "patch-manifest.json").read_text(encoding="utf-8"))
    fixed = (here / "native_transfusion_execution.fixed.py").read_bytes()
    original = target.read_bytes()
    if sha256(fixed) != manifest["fixed_sha256"]:
        raise ValueError("patch_resource_hash_mismatch")
    if sha256(original) not in {manifest["original_sha256"], manifest["fixed_sha256"]}:
        raise ValueError("installed_source_differs_do_not_overwrite")
    recordings = json.loads(Path(args.replay_file).read_text(encoding="utf-8-sig"))
    if not isinstance(recordings, list) or len(recordings) != 2:
        raise ValueError("expected_two_recorded_responses")
    compile(fixed, str(target), "exec", dont_inherit=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = Path(args.backup_dir) / ("c18-assessment-before-" + stamp)
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup = backup_dir / target.name
    backup.write_bytes(original)
    if sha256(backup.read_bytes()) != sha256(original):
        raise ValueError("backup_hash_mismatch")
    (backup_dir / "manifest.json").write_text(json.dumps({
        "target": str(target), "original_sha256": sha256(original),
        "fixed_sha256": sha256(fixed), "patch": manifest["patch"]
    }, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "code_backup_saved", "path": str(backup),
                      "database_writes": 0, "model_calls": 0}), flush=True)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / ("c18-hotfix-replay-" + stamp + ".jsonl")
    try:
        target.write_bytes(fixed)
        if sha256(target.read_bytes()) != manifest["fixed_sha256"]:
            raise ValueError("installed_patch_hash_mismatch")
        result = subprocess.run([
            sys.executable, "-u", str(here / "diagnose_transfusion_pair.py"),
            "--backend", str(backend), "--output", str(report),
            "--replay-calls", args.replay_file,
        ], check=False)
        events = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines() if line.strip()]
        if result.returncode != 0 or not replay_verified(events, len(recordings)):
            raise ValueError("offline_acceptance_failed")
    except BaseException:
        target.write_bytes(original)
        print(json.dumps({"event": "code_restored_after_failed_acceptance",
                          "restored": sha256(target.read_bytes()) == sha256(original),
                          "database_writes": 0, "model_calls": 0}), flush=True)
        raise
    print(json.dumps({"event": "hotfix_verified", "patch": manifest["patch"],
                      "replayed_responses": len(recordings), "report": str(report),
                      "database_writes": 0, "model_calls": 0,
                      "qc_results_changed": False, "backend_restart_required": True}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"event": "hotfix_stopped", "exception": type(error).__name__,
                          "reason": str(error) if type(error) is ValueError else "file_or_process_error",
                          "database_writes": 0, "model_calls": 0}), flush=True)
        raise SystemExit(1)
