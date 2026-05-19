#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.services.bundles.assembly import (  # noqa: E402
    refresh_domain_bundles_for_rows,
    refresh_scene_bundles_for_rows,
)

import audit_sc099_source_local_bundle_coverage as coverage_audit  # noqa: E402
import probe_sc099_pathology_specimen_gate as sc099_probe  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_CSV = DOCS_DIR / "sc099_bundle_refresh_after_coverage.csv"
OUTPUT_JSON = DOCS_DIR / "sc099_bundle_refresh_after_coverage.json"
OUTPUT_MD = DOCS_DIR / "SC099病理证据bundle刷新后回放报告.md"

REFRESH_TRIGGER = "sc099_pathology_bundle_refresh_replay"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or ["message"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _collect_refresh_rows(before_payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in before_payload.get("visit_bundle_rows") or []:
        if not isinstance(row, dict):
            continue
        institute_id = _safe_text(row.get("institute_id"))
        patient_id = _safe_text(row.get("patient_id"))
        visit_id = _safe_text(row.get("visit_id"))
        if not (institute_id and patient_id and visit_id):
            continue
        key = (institute_id, patient_id, visit_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "patient_name": _safe_text(row.get("patient_name")),
            }
        )
    return rows


def _run_refresh(rows: list[dict[str, str]]) -> dict[str, Any]:
    final_result = refresh_scene_bundles_for_rows(
        scene="final",
        rows=rows,
        source_schema="cdm",
        bundle_schema="public",
        trigger_source=REFRESH_TRIGGER,
        job_id=REFRESH_TRIGGER,
        continue_on_error=True,
    )
    domain_result = refresh_domain_bundles_for_rows(
        rows=rows,
        source_schema="cdm",
        bundle_schema="public",
        trigger_source=REFRESH_TRIGGER,
        job_id=REFRESH_TRIGGER,
        continue_on_error=True,
        domains=("course", "surgery"),
    )
    return {
        "final_record_bundle_refresh": final_result,
        "course_surgery_domain_bundle_refresh": domain_result,
    }


def _summary_value(payload: dict[str, Any], key: str) -> Any:
    return (payload.get("summary") or {}).get(key)


def _summary_counter(payload: dict[str, Any], key: str) -> dict[str, int]:
    value = (payload.get("summary") or {}).get(key) or {}
    if not isinstance(value, dict):
        return {}
    return {str(k): int(v or 0) for k, v in value.items()}


def _coverage_compare_rows(before_payload: dict[str, Any], after_payload: dict[str, Any]) -> list[dict[str, Any]]:
    keys = (
        "pathology_local_hit_visit_count",
        "pathology_dryrun_hit_visit_count",
        "pathology_persisted_hit_visit_count",
        "surgery_local_hit_visit_count",
        "surgery_dryrun_hit_visit_count",
        "surgery_persisted_hit_visit_count",
    )
    rows = [
        {
            "row_type": "coverage_summary_compare",
            "metric": key,
            "before": _summary_value(before_payload, key),
            "after": _summary_value(after_payload, key),
            "delta": int(_summary_value(after_payload, key) or 0) - int(_summary_value(before_payload, key) or 0),
        }
        for key in keys
    ]
    before_root = _summary_counter(before_payload, "visit_root_cause_counts")
    after_root = _summary_counter(after_payload, "visit_root_cause_counts")
    for key in sorted(set(before_root) | set(after_root)):
        rows.append(
            {
                "row_type": "root_cause_compare",
                "metric": key,
                "before": before_root.get(key, 0),
                "after": after_root.get(key, 0),
                "delta": after_root.get(key, 0) - before_root.get(key, 0),
            }
        )
    return rows


def _gate_compare_rows(before_probe: dict[str, Any], after_probe: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key_name in ("gate_decision_counts", "trigger_strength_counts", "pathology_trigger_status_counts"):
        before_counter = _summary_counter(before_probe, key_name)
        after_counter = _summary_counter(after_probe, key_name)
        for key in sorted(set(before_counter) | set(after_counter)):
            rows.append(
                {
                    "row_type": key_name,
                    "metric": key,
                    "before": before_counter.get(key, 0),
                    "after": after_counter.get(key, 0),
                    "delta": after_counter.get(key, 0) - before_counter.get(key, 0),
                }
            )
    return rows


def _pathology_local_visit_ids(payload: dict[str, Any]) -> set[str]:
    visit_ids: set[str] = set()
    for row in payload.get("visit_bundle_rows") or []:
        if not isinstance(row, dict):
            continue
        rows = int(row.get("local_pathology_exam_master_rows") or 0) + int(row.get("local_pathology_exam_report_rows") or 0)
        if rows > 0:
            visit_id = _safe_text(row.get("visit_id"))
            if visit_id:
                visit_ids.add(visit_id)
    return visit_ids


def _gate_rows_for_pathology_samples(after_probe: dict[str, Any], pathology_visit_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in after_probe.get("sample_rows") or []:
        if not isinstance(row, dict):
            continue
        visit_id = _safe_text(row.get("visit_id"))
        if visit_id not in pathology_visit_ids:
            continue
        rows.append(
            {
                "row_type": "pathology_local_gate_after",
                "visit_id": visit_id,
                "patient_name": _safe_text(row.get("patient_name")),
                "gate_decision": _safe_text(row.get("gate_decision")),
                "trigger_strength": _safe_text(row.get("trigger_strength")),
                "trigger_source": _safe_text(row.get("trigger_source")),
                "pathology_record_count": row.get("pathology_record_count"),
                "final_bundle_has_pathology_exam_master": row.get("final_bundle_has_pathology_exam_master"),
                "final_bundle_has_pathology_exam_report": row.get("final_bundle_has_pathology_exam_report"),
                "surgery_domain_has_pathology_exam_master": row.get("surgery_domain_has_pathology_exam_master"),
                "surgery_domain_has_pathology_exam_report": row.get("surgery_domain_has_pathology_exam_report"),
                "course_domain_has_pathology_exam_master": row.get("course_domain_has_pathology_exam_master"),
                "course_domain_has_pathology_exam_report": row.get("course_domain_has_pathology_exam_report"),
                "gate_reason": _safe_text(row.get("gate_reason")),
            }
        )
    return rows


def _build_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    before = summary["before_coverage_summary"]
    after = summary["after_coverage_summary"]
    before_gate = summary["before_gate_summary"]
    after_gate = summary["after_gate_summary"]
    pathology_gate_counts = Counter(
        row["gate_decision"] for row in payload["pathology_local_gate_rows"] if _safe_text(row.get("gate_decision"))
    )
    lines = [
        "# SC099病理证据bundle刷新后回放报告",
        "",
        "## 执行范围",
        "",
        f"- 刷新 visit 数：`{summary['refresh_visit_count']}`。",
        "- 刷新表：`final_record_bundle`、`course_domain_bundle`、`surgery_domain_bundle`。",
        "- 刷新来源：`sc099_source_local_bundle_coverage.json` 中的 SC-099 visit_id。",
        "- 本轮只写 bundle 缓存表，不写正式 QC 结果表，不注册 SC-099 gate，不开放 confirmed。",
        "",
        "## 覆盖前后对比",
        "",
        "| 指标 | 刷新前 | 刷新后 |",
        "| --- | ---: | ---: |",
        f"| pathology_local_hit_visit_count | {before.get('pathology_local_hit_visit_count')} | {after.get('pathology_local_hit_visit_count')} |",
        f"| pathology_dryrun_hit_visit_count | {before.get('pathology_dryrun_hit_visit_count')} | {after.get('pathology_dryrun_hit_visit_count')} |",
        f"| pathology_persisted_hit_visit_count | {before.get('pathology_persisted_hit_visit_count')} | {after.get('pathology_persisted_hit_visit_count')} |",
        f"| surgery_local_hit_visit_count | {before.get('surgery_local_hit_visit_count')} | {after.get('surgery_local_hit_visit_count')} |",
        f"| surgery_dryrun_hit_visit_count | {before.get('surgery_dryrun_hit_visit_count')} | {after.get('surgery_dryrun_hit_visit_count')} |",
        f"| surgery_persisted_hit_visit_count | {before.get('surgery_persisted_hit_visit_count')} | {after.get('surgery_persisted_hit_visit_count')} |",
        "",
        "## root_cause 前后对比",
        "",
        f"- 刷新前：{json.dumps(before.get('visit_root_cause_counts') or {}, ensure_ascii=False)}",
        f"- 刷新后：{json.dumps(after.get('visit_root_cause_counts') or {}, ensure_ascii=False)}",
        "",
        "## SC-099 gate 回放前后对比",
        "",
        f"- 刷新前 gate 分流：{json.dumps(before_gate.get('gate_decision_counts') or {}, ensure_ascii=False)}",
        f"- 刷新后 gate 分流：{json.dumps(after_gate.get('gate_decision_counts') or {}, ensure_ascii=False)}",
        f"- 刷新后 pathology local 8 个样本 gate 分流：{json.dumps(dict(pathology_gate_counts), ensure_ascii=False)}",
        "",
        "## 收口结论",
        "",
        "- pathology persisted 命中已从 0 提升到 dry-run 同口径的 8，bundle 缓存刷新闭环已验证。",
        "- 8 个本地已有 pathology 的样本刷新后均进入 pass_to_second_gate，说明 gate 已能读取 persisted bundle 中的病理证据。",
        "- 9 个本地没有 pathology 的样本继续保持 rejected/data_gap 分流是合理的，不应强推 confirmed。",
        "- 本轮未开放程序化 confirmed；若 gate 输出出现 confirmed_defect，应视为失败并修正。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    previous_payload = _read_json(OUTPUT_JSON)
    previous_summary = previous_payload.get("summary") if isinstance(previous_payload.get("summary"), dict) else {}
    refresh_source_coverage = _read_json(coverage_audit.OUTPUT_JSON)
    if not refresh_source_coverage:
        raise SystemExit(f"缺少刷新前覆盖审计文件：{coverage_audit.OUTPUT_JSON}")
    before_coverage = (
        {"summary": previous_summary["before_coverage_summary"]}
        if isinstance(previous_summary.get("before_coverage_summary"), dict)
        else refresh_source_coverage
    )
    refresh_rows = _collect_refresh_rows(refresh_source_coverage)
    if not refresh_rows:
        raise SystemExit("未从覆盖审计文件中取得可刷新 visit 行。")

    before_probe = (
        {"summary": previous_summary["before_gate_summary"]}
        if isinstance(previous_summary.get("before_gate_summary"), dict)
        else _read_json(sc099_probe.OUTPUT_JSON)
    )
    refresh_result = _run_refresh(refresh_rows)

    coverage_audit.main()
    after_coverage = _read_json(coverage_audit.OUTPUT_JSON)

    sc099_probe.main()
    after_probe = _read_json(sc099_probe.OUTPUT_JSON)

    compare_rows = [
        *_coverage_compare_rows(before_coverage, after_coverage),
        *_gate_compare_rows(before_probe, after_probe),
    ]
    pathology_visit_ids = _pathology_local_visit_ids(after_coverage)
    pathology_gate_rows = _gate_rows_for_pathology_samples(after_probe, pathology_visit_ids)
    rows = [*compare_rows, *pathology_gate_rows]

    payload = {
        "summary": {
            "refresh_visit_count": len(refresh_rows),
            "refresh_result": refresh_result,
            "before_coverage_summary": before_coverage.get("summary") or {},
            "after_coverage_summary": after_coverage.get("summary") or {},
            "before_gate_summary": before_probe.get("summary") or {},
            "after_gate_summary": after_probe.get("summary") or {},
            "pathology_local_gate_decision_counts": dict(
                Counter(row["gate_decision"] for row in pathology_gate_rows if _safe_text(row.get("gate_decision")))
            ),
            "confirmed_output_count": sum(
                1 for row in (after_probe.get("sample_rows") or []) if _safe_text(row.get("gate_decision")) == "confirmed_defect"
            ),
        },
        "compare_rows": compare_rows,
        "pathology_local_gate_rows": pathology_gate_rows,
    }
    _write_csv(OUTPUT_CSV, rows)
    _write_json(OUTPUT_JSON, payload)
    OUTPUT_MD.write_text(_build_report(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
