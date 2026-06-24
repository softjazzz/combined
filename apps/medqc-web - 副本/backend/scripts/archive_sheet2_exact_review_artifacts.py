#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
ARCHIVE_DIR = QC_DIR / "archive" / "sheet2-exact-review-temp-2026-05-03"
MANIFEST_JSON = QC_DIR / "sheet2_exact_review_archive_manifest.json"

KEEP_FILENAMES = {
    "sheet2_verification_ledger_seed.csv",
    "sheet2_verification_ledger_seed.summary.json",
    "sheet2_rule_mapping_seed.csv",
    "sheet2_rule_mapping_seed.summary.json",
    "sheet2_exact_review_matrix.csv",
    "sheet2_exact_review_summary.json",
    "sheet2_exact_review_summary.baseline.json",
    "sheet2_exact_review_overrides.csv",
    "sheet2_exact_review_blocked_backlog.csv",
    "sheet2_exact_review_blocked_backlog_overrides.csv",
    "sheet2_exact_review_acceptance_package.json",
    "sheet2_exact_review_archive_manifest.json",
    "2026-05-02-Sheet2全量精确复核矩阵.md",
    "2026-05-03-Sheet2客户验收包.md",
}

KEEP_PATTERNS = [
    re.compile(r"^sheet2_.*decisions_probe\.json$"),
]

ARCHIVE_PATTERNS = [
    re.compile(r"^sheet2_.*rows_snapshot.*\.json$"),
    re.compile(r"^sheet2_.*rows_probe\.json$"),
    re.compile(r"^sheet2_.*probe_tmp\.json$"),
    re.compile(r"^sheet2_.*_probe\.json$"),
    re.compile(r"^sheet2_probe_.*\.json$"),
    re.compile(r"^sheet2_.*wave_verification_report\.json$"),
    re.compile(r"^sheet2_.*retry.*report\.json$"),
    re.compile(r"^sheet2_.*_retry\.json$"),
    re.compile(r"^sheet2_.*primary.*report\.json$"),
    re.compile(r"^sheet2_.*secondary.*report\.json$"),
    re.compile(r"^sheet2_.*writeback\.json$"),
    re.compile(r"^sheet2_family_probe_.*\.json$"),
    re.compile(r"^sheet2_current_.*\.(txt|json)$"),
    re.compile(r"^sheet2_remaining_.*\.(txt|json)$"),
    re.compile(r"^sheet2_semantic_.*\.json$"),
    re.compile(r"^sheet2_full_clearance_.*\.json$"),
    re.compile(r"^sheet2_miss_.*\.json$"),
    re.compile(r"^sheet2_skip_.*\.json$"),
    re.compile(r"^sheet2_nonsemantic_.*\.json$"),
    re.compile(r"^sheet2_program_boundary_.*\.json$"),
    re.compile(r"^sheet2_secondary_retry.*\.json$"),
]


def _should_keep(path: Path) -> bool:
    if path.name in KEEP_FILENAMES:
        return True
    return any(pattern.match(path.name) for pattern in KEEP_PATTERNS)


def _should_archive(path: Path) -> bool:
    if not path.is_file() or _should_keep(path):
        return False
    return any(pattern.match(path.name) for pattern in ARCHIVE_PATTERNS)


def main() -> int:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archived_files_this_run: list[str] = []
    for path in sorted(QC_DIR.iterdir()):
        if not _should_archive(path):
            continue
        target = ARCHIVE_DIR / path.name
        if target.exists():
            target.unlink()
        shutil.move(str(path), str(target))
        archived_files_this_run.append(path.name)

    archived_files = sorted(item.name for item in ARCHIVE_DIR.iterdir() if item.is_file())

    MANIFEST_JSON.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-03",
                "archive_dir": str(ARCHIVE_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
                "archived_file_count": len(archived_files),
                "archived_file_count_this_run": len(archived_files_this_run),
                "archived_files": archived_files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "archive_dir": str(ARCHIVE_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
                "archived_file_count": len(archived_files),
                "archived_file_count_this_run": len(archived_files_this_run),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
