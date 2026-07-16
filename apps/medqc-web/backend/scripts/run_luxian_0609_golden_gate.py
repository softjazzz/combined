"""使用人工 accepted ledger 校验 LX0609 准生产 API 批次。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from scripts.build_luxian_0609_golden_ledger import (
        LEDGER_SCHEMA_VERSION,
        build_candidate_ledger,
        canonical_digest,
    )
except ModuleNotFoundError:  # 直接执行 scripts/*.py 时使用同目录导入。
    from build_luxian_0609_golden_ledger import (  # type: ignore[no-redef]
        LEDGER_SCHEMA_VERSION,
        build_candidate_ledger,
        canonical_digest,
    )


SCHEMA_VERSION = "lx0609-golden-gate-v1"
EXIT_PASSED = 0
EXIT_QUALITY_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_BLOCKED = 3
_CANONICAL_RULE_IDS = frozenset(
    f"LX0609-{number:03d}" for number in range(1, 50)
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_CODE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_CASE_LABEL_RE = re.compile(r"^case-[0-9]{2,4}$")
_RULE_ID_RE = re.compile(r"^LX0609-[0-9]{3}$")
_REVIEWER_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{2,63}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_EXPECTED_STATES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
    }
)
_DECISION_KINDS = frozenset({"deterministic", "semantic"})
_LEDGER_FIELDS = frozenset(
    {
        "schema_version",
        "ledger_version",
        "rule_set_digest",
        "selector_version",
        "selector_digest",
        "sample_count",
        "accepted_count",
        "parent_ledger_digest",
        "accepted_from_candidate_digest",
        "generated_at",
        "entries",
        "ledger_digest",
    }
)
_ENTRY_FIELDS = frozenset(
    {
        "case_label",
        "selector_digest",
        "rule_id",
        "decision_kind",
        "expected_state",
        "expected_reason_code",
        "evidence_ref_hashes",
        "reviewer_code",
        "accepted_at",
        "review_revision",
    }
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = (
    ROOT
    / "docs"
    / "acceptance"
    / "lx0609-golden"
    / "accepted20-v1.json"
)
DEFAULT_RUNS = tuple(
    ROOT
    / "docs"
    / "acceptance"
    / "lx0609-golden"
    / f"accepted20-run-{index}.json"
    for index in range(1, 4)
)


def _blocked(failure_kind: str) -> tuple[dict[str, Any], int]:
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "passed": False,
            "exit_code": EXIT_BLOCKED,
            "status": "blocked",
            "accepted_count": 0,
            "deterministic": {},
            "semantic": {},
            "failures": [
                {
                    "gate": "accepted_ledger",
                    "failure_kind": failure_kind,
                }
            ],
        },
        EXIT_BLOCKED,
    )


def _configuration_failure(failure_kind: str) -> tuple[dict[str, Any], int]:
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "passed": False,
            "exit_code": EXIT_CONFIGURATION_ERROR,
            "status": "configuration_error",
            "accepted_count": 0,
            "deterministic": {},
            "semantic": {},
            "failures": [
                {"gate": "accepted_ledger", "failure_kind": failure_kind}
            ],
        },
        EXIT_CONFIGURATION_ERROR,
    )


def _validate_ledger(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if (
        set(ledger) != _LEDGER_FIELDS
        or str(ledger.get("schema_version") or "") != LEDGER_SCHEMA_VERSION
        or not _SAFE_CODE_RE.fullmatch(str(ledger.get("ledger_version") or ""))
        or not _SHA256_RE.fullmatch(str(ledger.get("rule_set_digest") or ""))
        or not _SAFE_CODE_RE.fullmatch(str(ledger.get("selector_version") or ""))
        or not _SHA256_RE.fullmatch(str(ledger.get("selector_digest") or ""))
        or type(ledger.get("sample_count")) is not int
        or int(ledger.get("sample_count") or 0) < 1
        or type(ledger.get("accepted_count")) is not int
        or int(ledger.get("accepted_count") or 0) < 1
        or (
            str(ledger.get("parent_ledger_digest") or "") != ""
            and not _SHA256_RE.fullmatch(
                str(ledger.get("parent_ledger_digest") or "")
            )
        )
        or not _SHA256_RE.fullmatch(
            str(ledger.get("accepted_from_candidate_digest") or "")
        )
        or not _UTC_RE.fullmatch(str(ledger.get("generated_at") or ""))
    ):
        raise ValueError("invalid_accepted_ledger")
    claimed = ledger.get("ledger_digest")
    material = {key: value for key, value in ledger.items() if key != "ledger_digest"}
    entries = ledger.get("entries")
    if (
        not isinstance(claimed, str)
        or not _SHA256_RE.fullmatch(claimed)
        or canonical_digest(material) != claimed
        or not isinstance(entries, list)
        or not entries
        or int(ledger.get("accepted_count") or 0) != len(entries)
    ):
        raise ValueError("invalid_accepted_ledger")
    pairs: set[tuple[str, str]] = set()
    case_labels: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != _ENTRY_FIELDS:
            raise ValueError("invalid_accepted_ledger")
        case_label = str(entry.get("case_label") or "")
        selector_digest = str(entry.get("selector_digest") or "")
        rule_id = str(entry.get("rule_id") or "")
        decision_kind = str(entry.get("decision_kind") or "")
        expected_state = str(entry.get("expected_state") or "")
        expected_reason = str(entry.get("expected_reason_code") or "")
        evidence_hashes = entry.get("evidence_ref_hashes")
        reviewer_code = str(entry.get("reviewer_code") or "")
        accepted_at = str(entry.get("accepted_at") or "")
        revision = entry.get("review_revision")
        if (
            not _CASE_LABEL_RE.fullmatch(case_label)
            or not _SHA256_RE.fullmatch(selector_digest)
            or selector_digest != str(ledger.get("selector_digest") or "")
            or not _RULE_ID_RE.fullmatch(rule_id)
            or decision_kind not in _DECISION_KINDS
            or expected_state not in _EXPECTED_STATES
            or not _SAFE_CODE_RE.fullmatch(expected_reason)
            or not isinstance(evidence_hashes, list)
            or not evidence_hashes
            or len(evidence_hashes) != len(set(evidence_hashes))
            or any(
                not isinstance(item, str) or not _SHA256_RE.fullmatch(item)
                for item in evidence_hashes
            )
            or not _REVIEWER_CODE_RE.fullmatch(reviewer_code)
            or not _UTC_RE.fullmatch(accepted_at)
            or type(revision) is not int
            or revision < 1
        ):
            raise ValueError("invalid_accepted_ledger")
        pair = (
            case_label,
            rule_id,
        )
        if pair in pairs:
            raise ValueError("invalid_accepted_ledger")
        pairs.add(pair)
        case_labels.add(pair[0])
    if int(ledger.get("sample_count") or 0) != len(case_labels):
        raise ValueError("invalid_accepted_ledger")
    return entries


def _actual_rows(
    run_batch: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[tuple[str, str], Mapping[str, Any]]]:
    candidate = build_candidate_ledger(
        run_batch,
        candidate_version="golden-gate-run-v1",
        generated_at="1970-01-01T00:00:00Z",
    )
    rows = candidate.get("rows") or []
    return (
        candidate,
        {
            (str(row.get("case_label") or ""), str(row.get("rule_id") or "")): row
            for row in rows
            if isinstance(row, Mapping)
        },
    )


def _entry_matches(
    entry: Mapping[str, Any],
    actual: Mapping[str, Any] | None,
) -> bool:
    if actual is None:
        return False
    return (
        str(actual.get("observed_state") or "")
        == str(entry.get("expected_state") or "")
        and _evidence_matches(entry, actual)
    )


def _evidence_matches(
    entry: Mapping[str, Any],
    actual: Mapping[str, Any] | None,
) -> bool:
    if actual is None:
        return False
    return (
        str(actual.get("observed_reason_code") or "")
        == str(entry.get("expected_reason_code") or "")
        and list(actual.get("evidence_ref_hashes") or [])
        == list(entry.get("evidence_ref_hashes") or [])
    )


def run_luxian_0609_golden_gate(
    *,
    ledger: Mapping[str, Any] | None,
    run_batches: Sequence[Mapping[str, Any]],
    semantic_ppv_min: float = 0.95,
    semantic_recall_min: float = 0.90,
    semantic_min_positive: int = 1,
    semantic_min_negative: int = 1,
    expected_sample_count: int | None = None,
    expected_rule_count: int | None = None,
) -> tuple[dict[str, Any], int]:
    if not ledger:
        return _blocked("missing_accepted_ledger")
    if not run_batches:
        return _blocked("missing_golden_runs")
    try:
        entries = _validate_ledger(ledger)
    except (TypeError, ValueError):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    if expected_sample_count is not None or expected_rule_count is not None:
        if (
            not isinstance(expected_sample_count, int)
            or not isinstance(expected_rule_count, int)
            or expected_sample_count < 1
            or expected_rule_count < 1
        ):
            return _configuration_failure("invalid_expected_matrix")
        by_case: dict[str, set[str]] = {}
        for entry in entries:
            by_case.setdefault(str(entry.get("case_label") or ""), set()).add(
                str(entry.get("rule_id") or "")
            )
        expected_rule_ids = (
            _CANONICAL_RULE_IDS
            if expected_rule_count == len(_CANONICAL_RULE_IDS)
            else next(iter(by_case.values()), set())
        )
        matrix_complete = (
            len(by_case) == expected_sample_count
            and len(entries) == expected_sample_count * expected_rule_count
            and len(expected_rule_ids) == expected_rule_count
            and all(rule_ids == expected_rule_ids for rule_ids in by_case.values())
        )
        if not matrix_complete:
            return (
                {
                    "schema_version": SCHEMA_VERSION,
                    "passed": False,
                    "exit_code": EXIT_BLOCKED,
                    "status": "blocked",
                    "accepted_count": len(entries),
                    "deterministic": {},
                    "semantic": {},
                    "failures": [
                        {
                            "gate": "accepted_ledger",
                            "failure_kind": "incomplete_accepted_matrix",
                        }
                    ],
                },
                EXIT_BLOCKED,
            )
    try:
        actual_candidates_and_rows = [_actual_rows(run) for run in run_batches]
    except (TypeError, ValueError):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    if any(
        str(candidate.get("selector_digest") or "")
        != str(ledger.get("selector_digest") or "")
        or str(candidate.get("rule_set_digest") or "")
        != str(ledger.get("rule_set_digest") or "")
        for candidate, _rows in actual_candidates_and_rows
    ):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    accepted_pairs = {
        (str(entry.get("case_label") or ""), str(entry.get("rule_id") or ""))
        for entry in entries
    }
    if any(
        set(rows) != accepted_pairs
        or int(candidate.get("sample_count") or 0)
        != int(ledger.get("sample_count") or 0)
        or int(candidate.get("candidate_count") or 0) != len(entries)
        for candidate, rows in actual_candidates_and_rows
    ):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    actual_runs = [rows for _candidate, rows in actual_candidates_and_rows]

    deterministic_entries = [
        entry for entry in entries if entry.get("decision_kind") == "deterministic"
    ]
    semantic_entries = [
        entry for entry in entries if entry.get("decision_kind") == "semantic"
    ]
    deterministic_exact = 0
    for entry in deterministic_entries:
        pair = (str(entry.get("case_label") or ""), str(entry.get("rule_id") or ""))
        if all(_entry_matches(entry, actual.get(pair)) for actual in actual_runs):
            deterministic_exact += 1
    deterministic = {
        "accepted_count": len(deterministic_entries),
        "exact_count": deterministic_exact,
        "exact_rate": (
            deterministic_exact / len(deterministic_entries)
            if deterministic_entries
            else 1.0
        ),
    }
    failures: list[dict[str, str]] = []
    if deterministic_exact != len(deterministic_entries):
        failures.append(
            {"gate": "deterministic", "failure_kind": "not_exact_100_percent"}
        )
    semantic: dict[str, Any]
    if semantic_entries:
        if len(actual_runs) < 3:
            semantic = {
                "accepted_count": len(semantic_entries),
                "status": "blocked",
            }
            failures.append(
                {"gate": "semantic", "failure_kind": "requires_three_runs"}
            )
            exit_code = EXIT_BLOCKED
        else:
            stable_count = 0
            evidence_exact_count = 0
            true_positive = 0
            false_positive = 0
            false_negative = 0
            truth_positive = 0
            truth_negative = 0
            semantic_rule_stats: dict[str, dict[str, int]] = {}
            for entry in semantic_entries:
                rule_id = str(entry.get("rule_id") or "")
                rule_stats = semantic_rule_stats.setdefault(
                    rule_id,
                    {
                        "accepted_count": 0,
                        "stable_count": 0,
                        "evidence_exact_count": 0,
                        "true_positive": 0,
                        "false_positive": 0,
                        "false_negative": 0,
                        "truth_positive": 0,
                        "truth_negative": 0,
                    },
                )
                rule_stats["accepted_count"] += 1
                pair = (
                    str(entry.get("case_label") or ""),
                    rule_id,
                )
                observed = [actual.get(pair) for actual in actual_runs]
                states = [
                    str(item.get("observed_state") or "") if item else "missing"
                    for item in observed
                ]
                if (
                    len(set(states)) == 1
                    and states[0] != "technical_error"
                    and states[0] != "missing"
                ):
                    stable_count += 1
                    rule_stats["stable_count"] += 1
                if all(_evidence_matches(entry, item) for item in observed):
                    evidence_exact_count += 1
                    rule_stats["evidence_exact_count"] += 1
                expected_positive = (
                    str(entry.get("expected_state") or "") == "non_compliant"
                )
                predicted_positive = states[0] == "non_compliant"
                if expected_positive:
                    truth_positive += 1
                    rule_stats["truth_positive"] += 1
                    if predicted_positive:
                        true_positive += 1
                        rule_stats["true_positive"] += 1
                    else:
                        false_negative += 1
                        rule_stats["false_negative"] += 1
                else:
                    truth_negative += 1
                    rule_stats["truth_negative"] += 1
                    if predicted_positive:
                        false_positive += 1
                        rule_stats["false_positive"] += 1
            predicted_positive_count = true_positive + false_positive
            ppv = (
                true_positive / predicted_positive_count
                if predicted_positive_count
                else 0.0
            )
            recall = (
                true_positive / truth_positive if truth_positive else 0.0
            )
            semantic_failures: list[dict[str, str]] = []
            insufficient = False
            for rule_id in sorted(semantic_rule_stats):
                rule_stats = semantic_rule_stats[rule_id]
                if (
                    rule_stats["truth_positive"] < semantic_min_positive
                    or rule_stats["truth_negative"] < semantic_min_negative
                ):
                    insufficient = True
                    semantic_failures.append(
                        {
                            "gate": "semantic",
                            "failure_kind": "insufficient_sample",
                            "rule_id": rule_id,
                        }
                    )
                    continue
                if rule_stats["stable_count"] != rule_stats["accepted_count"]:
                    semantic_failures.append(
                        {
                            "gate": "semantic",
                            "failure_kind": "unstable_state",
                            "rule_id": rule_id,
                        }
                    )
                if (
                    rule_stats["evidence_exact_count"]
                    != rule_stats["accepted_count"]
                ):
                    semantic_failures.append(
                        {
                            "gate": "semantic",
                            "failure_kind": "evidence_mismatch",
                            "rule_id": rule_id,
                        }
                    )
                rule_predicted_positive = (
                    rule_stats["true_positive"] + rule_stats["false_positive"]
                )
                rule_ppv = (
                    rule_stats["true_positive"] / rule_predicted_positive
                    if rule_predicted_positive
                    else 0.0
                )
                rule_recall = (
                    rule_stats["true_positive"] / rule_stats["truth_positive"]
                )
                if rule_ppv < semantic_ppv_min:
                    semantic_failures.append(
                        {
                            "gate": "semantic",
                            "failure_kind": "ppv_below_threshold",
                            "rule_id": rule_id,
                        }
                    )
                if rule_recall < semantic_recall_min:
                    semantic_failures.append(
                        {
                            "gate": "semantic",
                            "failure_kind": "recall_below_threshold",
                            "rule_id": rule_id,
                        }
                    )
            semantic_failed = bool(semantic_failures)
            semantic = {
                "accepted_count": len(semantic_entries),
                "stable_count": stable_count,
                "stability_rate": stable_count / len(semantic_entries),
                "evidence_exact_count": evidence_exact_count,
                "true_positive": true_positive,
                "false_positive": false_positive,
                "false_negative": false_negative,
                "truth_positive": truth_positive,
                "truth_negative": truth_negative,
                "ppv": ppv,
                "recall": recall,
                "ppv_min": semantic_ppv_min,
                "recall_min": semantic_recall_min,
                "status": (
                    "blocked"
                    if insufficient
                    else "failed"
                    if semantic_failed
                    else "passed"
                ),
            }
            if insufficient:
                failures.extend(semantic_failures)
                exit_code = EXIT_BLOCKED
            else:
                failures.extend(semantic_failures)
                exit_code = (
                    EXIT_PASSED if not failures else EXIT_QUALITY_FAILURE
                )
    else:
        semantic = {"accepted_count": 0, "status": "not_applicable"}
        exit_code = EXIT_PASSED if not failures else EXIT_QUALITY_FAILURE
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "passed": exit_code == EXIT_PASSED,
            "exit_code": exit_code,
            "status": (
                "passed"
                if exit_code == EXIT_PASSED
                else "blocked"
                if exit_code == EXIT_BLOCKED
                else "failed"
            ),
            "accepted_count": len(entries),
            "deterministic": deterministic,
            "semantic": semantic,
            "failures": failures,
        },
        exit_code,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609 accepted Golden 质量门")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--run", dest="runs", action="append", type=Path)
    parser.add_argument("--semantic-ppv-min", type=float, default=0.95)
    parser.add_argument("--semantic-recall-min", type=float, default=0.90)
    parser.add_argument("--semantic-min-positive", type=int, default=1)
    parser.add_argument("--semantic-min-negative", type=int, default=1)
    parser.add_argument("--expected-sample-count", type=int, default=20)
    parser.add_argument("--expected-rule-count", type=int, default=49)
    return parser.parse_args(argv)


def _read_json(path: Path) -> Mapping[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    ledger = _read_json(args.ledger)
    run_paths = tuple(args.runs) if args.runs else DEFAULT_RUNS
    runs = [_read_json(path) for path in run_paths]
    if ledger is not None and any(run is None for run in runs):
        summary, exit_code = _blocked("missing_golden_runs")
    else:
        summary, exit_code = run_luxian_0609_golden_gate(
            ledger=ledger,
            run_batches=[run for run in runs if run is not None],
            semantic_ppv_min=args.semantic_ppv_min,
            semantic_recall_min=args.semantic_recall_min,
            semantic_min_positive=args.semantic_min_positive,
            semantic_min_negative=args.semantic_min_negative,
            expected_sample_count=args.expected_sample_count,
            expected_rule_count=args.expected_rule_count,
        )
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
