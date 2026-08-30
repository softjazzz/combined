"""使用人工 accepted ledger 校验 LX0609 准生产 API 批次。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from app.services.sample_validation_rule_sets import (
        get_luxian_0609_customer_delivery_rule_ids,
        get_luxian_0609_customer_execution_scope,
    )
    from app.services.luxian_0609.rule_contracts import (
        Luxian0609RuleContract,
        load_luxian_0609_rule_contracts,
    )
except ModuleNotFoundError:  # 从仓库根目录直接执行 backend/scripts/*.py。
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.sample_validation_rule_sets import (  # type: ignore[no-redef]
        get_luxian_0609_customer_delivery_rule_ids,
        get_luxian_0609_customer_execution_scope,
    )
    from app.services.luxian_0609.rule_contracts import (  # type: ignore[no-redef]
        Luxian0609RuleContract,
        load_luxian_0609_rule_contracts,
    )

try:
    from scripts.build_luxian_0609_runtime_manifest import (
        current_git_head as current_git_head,
        runtime_manifest_hash,
        validate_runtime_manifest_current,
    )
except ModuleNotFoundError:  # 直接执行 scripts/*.py 时使用同目录导入。
    from build_luxian_0609_runtime_manifest import (  # type: ignore[no-redef]
        current_git_head as current_git_head,
        runtime_manifest_hash,
        validate_runtime_manifest_current,
    )

try:
    from scripts.build_luxian_0609_golden_ledger import (
        CANDIDATE_SCHEMA_VERSION_V2,
        LEDGER_SCHEMA_VERSION,
        LEDGER_SCHEMA_VERSION_V2,
        _validate_candidate,
        build_candidate_ledger,
        canonical_digest,
    )
except ModuleNotFoundError:  # 直接执行 scripts/*.py 时使用同目录导入。
    from build_luxian_0609_golden_ledger import (  # type: ignore[no-redef]
        CANDIDATE_SCHEMA_VERSION_V2,
        LEDGER_SCHEMA_VERSION,
        LEDGER_SCHEMA_VERSION_V2,
        _validate_candidate,
        build_candidate_ledger,
        canonical_digest,
    )


SCHEMA_VERSION = "lx0609-golden-gate-v1"
EXIT_PASSED = 0
EXIT_QUALITY_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_BLOCKED = 3
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
_LEDGER_V2_EXTRA_FIELDS = frozenset(
    {"policy_version", "git_head", "runtime_manifest_hash"}
)
_ENTRY_V2_EXTRA_FIELDS = frozenset(
    {
        "safe_case_ref",
        "sample_type",
        "evidence_source_types",
        "manual_review_status",
        "policy_version",
        "git_head",
        "runtime_manifest_hash",
    }
)
_GIT_HEAD_RE = re.compile(r"^[a-f0-9]{40}$")
_SAMPLE_TYPES = frozenset({"real", "synthetic"})

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = (
    ROOT
    / "docs"
    / "acceptance"
    / "lx0609-golden"
    / "accepted20-v2.json"
)
DEFAULT_RUNS = tuple(
    ROOT
    / "docs"
    / "acceptance"
    / "lx0609-golden"
    / f"accepted20-v2-run-{index}.json"
    for index in range(1, 4)
)


def _authoritative_rule_scope() -> tuple[
    tuple[Luxian0609RuleContract, ...], tuple[str, ...], tuple[str, ...]
]:
    """读取完整合同，并按客户交付范围拆分可执行与冻结范围。"""

    contracts = load_luxian_0609_rule_contracts()
    customer_rule_ids = get_luxian_0609_customer_delivery_rule_ids()
    executable, withheld = get_luxian_0609_customer_execution_scope()
    if len(customer_rule_ids) != 70 or len(executable) != 64 or len(withheld) != 6:
        raise ValueError("invalid LX0609 customer scope counts")
    return contracts, executable, withheld


def _rule_scope_summary() -> dict[str, int]:
    """返回发布门禁使用的完整范围计数，避免把内部75条误读为执行数。"""

    contracts, executable, withheld = _authoritative_rule_scope()
    delivery = get_luxian_0609_customer_delivery_rule_ids()
    if set(executable) | set(withheld) != set(delivery) or set(executable) & set(withheld):
        raise ValueError("invalid LX0609 customer scope partition")
    return {
        "catalog_count": len(contracts),
        "customer_delivery_count": len(delivery),
        "executable_count": len(executable),
        "withheld_count": len(withheld),
    }


def _validate_runtime_contract_identity(
    runtime_manifest: Mapping[str, Any],
) -> tuple[str, ...]:
    """运行清单必须逐项绑定完整 75 条合同；Golden 默认只验可执行规则。"""

    contracts, executable, _withheld = _authoritative_rule_scope()
    contract_rule_ids = tuple(contract.rule_id for contract in contracts)
    rule_set = runtime_manifest.get("rule_set")
    manifest_rules = runtime_manifest.get("rules")
    if (
        not isinstance(rule_set, Mapping)
        or type(runtime_manifest.get("customer_rule_count")) is not int
        or runtime_manifest.get("customer_rule_count") != len(contract_rule_ids)
        or type(rule_set.get("rule_count")) is not int
        or rule_set.get("rule_count") != len(contract_rule_ids)
        or tuple(rule_set.get("rule_ids") or ()) != contract_rule_ids
        or not isinstance(manifest_rules, list)
        or len(manifest_rules) != len(contracts)
    ):
        raise ValueError("runtime manifest rule contract identity drift")
    for contract, manifest_rule in zip(contracts, manifest_rules, strict=True):
        if not isinstance(manifest_rule, Mapping) or any(
            str(manifest_rule.get(field) or "") != str(expected)
            for field, expected in (
                ("rule_id", contract.rule_id),
                ("contract_version", contract.contract_version),
                ("phase_status", contract.phase_status),
                ("definition_version", contract.definition_version),
            )
        ):
            raise ValueError("runtime manifest rule contract identity drift")
    return executable


def _resolve_golden_rule_ids(
    selected_rule_ids: Sequence[str] | None,
    *,
    executable_rule_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """解析显式窄范围；不允许重复、未知或冻结规则。"""

    if selected_rule_ids is None:
        return executable_rule_ids
    normalized = tuple(str(rule_id or "").strip().upper() for rule_id in selected_rule_ids)
    executable_set = set(executable_rule_ids)
    if (
        not normalized
        or any(not rule_id for rule_id in normalized)
        or len(normalized) != len(set(normalized))
        or any(rule_id not in executable_set for rule_id in normalized)
    ):
        raise ValueError("invalid Golden rule scope")
    requested = set(normalized)
    return tuple(rule_id for rule_id in executable_rule_ids if rule_id in requested)


def _default_candidate_path(ledger_path: Path) -> Path:
    """根据 accepted 账本推导同目录候选账本，不猜测其他目录。"""

    if ledger_path.name.startswith("accepted"):
        return ledger_path.with_name(
            f"candidate{ledger_path.name[len('accepted') :]}"
        )
    return ledger_path.with_name(
        f"{ledger_path.stem}-candidate{ledger_path.suffix}"
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
    schema_version = str(ledger.get("schema_version") or "")
    is_v2 = schema_version == LEDGER_SCHEMA_VERSION_V2
    expected_fields = _LEDGER_FIELDS | (
        _LEDGER_V2_EXTRA_FIELDS if is_v2 else frozenset()
    )
    if (
        set(ledger) != expected_fields
        or schema_version not in {LEDGER_SCHEMA_VERSION, LEDGER_SCHEMA_VERSION_V2}
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
        or (
            is_v2
            and (
                not _SAFE_CODE_RE.fullmatch(
                    str(ledger.get("policy_version") or "")
                )
                or not _GIT_HEAD_RE.fullmatch(str(ledger.get("git_head") or ""))
                or not _SHA256_RE.fullmatch(
                    str(ledger.get("runtime_manifest_hash") or "")
                )
            )
        )
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
        expected_entry_fields = _ENTRY_FIELDS | (
            _ENTRY_V2_EXTRA_FIELDS if is_v2 else frozenset()
        )
        if not isinstance(entry, Mapping) or set(entry) != expected_entry_fields:
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
        evidence_source_types = entry.get("evidence_source_types")
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
            or (
                is_v2
                and (
                    not _SHA256_RE.fullmatch(
                        str(entry.get("safe_case_ref") or "")
                    )
                    or str(entry.get("sample_type") or "") not in _SAMPLE_TYPES
                    or not isinstance(evidence_source_types, list)
                    or not evidence_source_types
                    or len(evidence_source_types) != len(set(evidence_source_types))
                    or any(
                        not isinstance(item, str)
                        or not _SAFE_CODE_RE.fullmatch(item)
                        for item in evidence_source_types
                    )
                    or str(entry.get("manual_review_status") or "") != "accepted"
                    or str(entry.get("policy_version") or "")
                    != str(ledger.get("policy_version") or "")
                    or str(entry.get("git_head") or "")
                    != str(ledger.get("git_head") or "")
                    or str(entry.get("runtime_manifest_hash") or "")
                    != str(ledger.get("runtime_manifest_hash") or "")
                )
            )
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


def _candidate_row_matches(
    candidate_row: Mapping[str, Any] | None,
    actual_row: Mapping[str, Any] | None,
) -> bool:
    if candidate_row is None or actual_row is None:
        return False
    return (
        str(candidate_row.get("observed_state") or "")
        == str(actual_row.get("observed_state") or "")
        and str(candidate_row.get("observed_reason_code") or "")
        == str(actual_row.get("observed_reason_code") or "")
        and list(candidate_row.get("evidence_ref_hashes") or [])
        == list(actual_row.get("evidence_ref_hashes") or [])
        and (
            "safe_case_ref" not in candidate_row
            or (
                str(candidate_row.get("safe_case_ref") or "")
                == str(actual_row.get("safe_case_ref") or "")
                and str(candidate_row.get("sample_type") or "")
                == str(actual_row.get("sample_type") or "")
                and str(candidate_row.get("decision_kind") or "")
                == str(actual_row.get("decision_kind") or "")
                and list(candidate_row.get("evidence_source_types") or [])
                == list(actual_row.get("evidence_source_types") or [])
            )
        )
    )


def _run_luxian_0609_golden_gate_diagnostic(
    *,
    ledger: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    run_batches: Sequence[Mapping[str, Any]],
    semantic_ppv_min: float = 0.95,
    semantic_recall_min: float = 0.90,
    semantic_min_positive: int = 1,
    semantic_min_negative: int = 1,
    expected_sample_count: int | None = None,
    expected_rule_count: int | None = None,
    expected_rule_ids: Sequence[str] | None = None,
    definite_agreement_min: float = 0.95,
    technical_error_rate_max: float = 0.01,
    high_risk_nc_precision_min: float = 0.95,
    semantic_token_budget_per_rule: int = 8192,
) -> tuple[dict[str, Any], int]:
    if not ledger:
        return _blocked("missing_accepted_ledger")
    if not candidate:
        return _blocked("missing_candidate_ledger")
    if not run_batches:
        return _blocked("missing_golden_runs")
    if (
        not 0.0 <= definite_agreement_min <= 1.0
        or not 0.0 <= technical_error_rate_max <= 1.0
        or not 0.0 <= high_risk_nc_precision_min <= 1.0
        or semantic_token_budget_per_rule < 0
    ):
        return _configuration_failure("invalid_quality_threshold")
    try:
        entries = _validate_ledger(ledger)
    except (TypeError, ValueError):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    try:
        candidate_digest = _validate_candidate(candidate)
    except (TypeError, ValueError):
        return _configuration_failure("invalid_candidate_ledger_or_run")
    if (
        candidate_digest
        != str(ledger.get("accepted_from_candidate_digest") or "")
        or str(candidate.get("selector_digest") or "")
        != str(ledger.get("selector_digest") or "")
        or str(candidate.get("rule_set_digest") or "")
        != str(ledger.get("rule_set_digest") or "")
    ):
        return _configuration_failure("invalid_candidate_ledger_or_run")
    is_v2 = str(ledger.get("schema_version") or "") == LEDGER_SCHEMA_VERSION_V2
    if is_v2 and any(
        str(candidate.get(field) or "") != str(ledger.get(field) or "")
        for field in ("policy_version", "git_head", "runtime_manifest_hash")
    ):
        return _configuration_failure("runtime_identity_mismatch")
    candidate_rows_list = candidate.get("rows")
    if not isinstance(candidate_rows_list, list):
        return _configuration_failure("invalid_candidate_ledger_or_run")
    candidate_rows = {
        (str(row.get("case_label") or ""), str(row.get("rule_id") or "")): row
        for row in candidate_rows_list
        if isinstance(row, Mapping)
    }
    if expected_sample_count is not None or expected_rule_ids is not None:
        normalized_expected_rule_ids = tuple(expected_rule_ids or ())
        resolved_sample_count = (
            expected_sample_count
            if expected_sample_count is not None
            else ledger.get("sample_count")
        )
        if (
            type(resolved_sample_count) is not int
            or resolved_sample_count < 1
            or not normalized_expected_rule_ids
            or len(normalized_expected_rule_ids)
            != len(set(normalized_expected_rule_ids))
            or (
                expected_rule_count is not None
                and (
                    type(expected_rule_count) is not int
                    or expected_rule_count != len(normalized_expected_rule_ids)
                )
            )
        ):
            return _configuration_failure("invalid_expected_matrix")
        by_case: dict[str, set[str]] = {}
        for entry in entries:
            by_case.setdefault(str(entry.get("case_label") or ""), set()).add(
                str(entry.get("rule_id") or "")
            )
        expected_rule_id_set = set(normalized_expected_rule_ids)
        matrix_complete = (
            len(by_case) == resolved_sample_count
            and len(entries)
            == resolved_sample_count * len(normalized_expected_rule_ids)
            and all(rule_ids == expected_rule_id_set for rule_ids in by_case.values())
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
    if is_v2 and any(
        any(
            str(actual_candidate.get(field) or "")
            != str(ledger.get(field) or "")
            for field in ("policy_version", "git_head", "runtime_manifest_hash")
        )
        for actual_candidate, _rows in actual_candidates_and_rows
    ):
        return _configuration_failure("runtime_identity_mismatch")
    accepted_pairs = {
        (str(entry.get("case_label") or ""), str(entry.get("rule_id") or ""))
        for entry in entries
    }
    if (
        set(candidate_rows) != accepted_pairs
        or int(candidate.get("sample_count") or 0)
        != int(ledger.get("sample_count") or 0)
        or int(candidate.get("candidate_count") or 0) != len(entries)
    ):
        return _configuration_failure("invalid_candidate_ledger_or_run")
    if is_v2:
        for entry in entries:
            pair = (
                str(entry.get("case_label") or ""),
                str(entry.get("rule_id") or ""),
            )
            candidate_row = candidate_rows.get(pair)
            if candidate_row is None or any(
                (
                    list(entry.get(field) or [])
                    != list(candidate_row.get(field) or [])
                    if field == "evidence_source_types"
                    else str(entry.get(field) or "")
                    != str(candidate_row.get(field) or "")
                )
                for field in (
                    "safe_case_ref",
                    "sample_type",
                    "decision_kind",
                    "evidence_source_types",
                )
            ):
                return _configuration_failure(
                    "accepted_candidate_classification_mismatch"
                )
    if any(
        set(rows) != accepted_pairs
        or int(candidate.get("sample_count") or 0)
        != int(ledger.get("sample_count") or 0)
        or int(candidate.get("candidate_count") or 0) != len(entries)
        for candidate, rows in actual_candidates_and_rows
    ):
        return _configuration_failure("invalid_accepted_ledger_or_run")
    actual_runs = [rows for _candidate, rows in actual_candidates_and_rows]
    # 候选账本只绑定人工复核所依据的第一份基准运行。后续重复运行
    # 必须继续交由 semantic 的稳定性/PPV 门和 deterministic 精确门判定，
    # 不能把真实模型波动伪装成候选账本配置错误。
    if not all(
        _candidate_row_matches(candidate_rows.get(pair), actual_runs[0].get(pair))
        for pair in accepted_pairs
    ):
        return _configuration_failure("invalid_candidate_ledger_or_run")
    if is_v2 and not all(
        _candidate_row_matches(
            {
                **dict(candidate_rows[pair]),
                "observed_state": str(actual.get(pair, {}).get("observed_state") or ""),
                "observed_reason_code": str(
                    actual.get(pair, {}).get("observed_reason_code") or ""
                ),
                "evidence_ref_hashes": list(
                    actual.get(pair, {}).get("evidence_ref_hashes") or []
                ),
            },
            actual.get(pair),
        )
        for actual in actual_runs
        for pair in accepted_pairs
    ):
        return _configuration_failure("invalid_candidate_ledger_or_run")

    scoring_entries = (
        [entry for entry in entries if entry.get("sample_type") == "real"]
        if is_v2
        else entries
    )
    deterministic_entries = [
        entry
        for entry in scoring_entries
        if entry.get("decision_kind") == "deterministic"
    ]
    semantic_entries = [
        entry for entry in scoring_entries if entry.get("decision_kind") == "semantic"
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
    quality: dict[str, Any] | None = None
    if is_v2:
        first_run = actual_runs[0]
        real_entries = [
            entry for entry in entries if entry.get("sample_type") == "real"
        ]
        synthetic_entries = [
            entry for entry in entries if entry.get("sample_type") == "synthetic"
        ]
        definite_states = {"compliant", "non_compliant", "not_applicable"}
        definite_entries = [
            entry
            for entry in real_entries
            if str(entry.get("expected_state") or "") in definite_states
        ]
        definite_exact = sum(
            _entry_matches(
                entry,
                first_run.get(
                    (
                        str(entry.get("case_label") or ""),
                        str(entry.get("rule_id") or ""),
                    )
                ),
            )
            for entry in definite_entries
        )
        definite_agreement = (
            definite_exact / len(definite_entries) if definite_entries else 0.0
        )
        observed_real = [
            first_run.get(
                (
                    str(entry.get("case_label") or ""),
                    str(entry.get("rule_id") or ""),
                )
            )
            for entry in real_entries
        ]
        observed_states = [
            str(item.get("observed_state") or "missing")
            for item in observed_real
            if item is not None
        ]
        technical_count = observed_states.count("technical_error")
        technical_rate = (
            technical_count / len(real_entries) if real_entries else 0.0
        )
        high_risk_entries = [
            entry
            for entry in real_entries
            if entry.get("decision_kind") == "semantic"
        ]
        predicted_high_risk_nc = 0
        true_high_risk_nc = 0
        for entry in high_risk_entries:
            actual = first_run.get(
                (
                    str(entry.get("case_label") or ""),
                    str(entry.get("rule_id") or ""),
                )
            )
            if str((actual or {}).get("observed_state") or "") == "non_compliant":
                predicted_high_risk_nc += 1
                if str(entry.get("expected_state") or "") == "non_compliant":
                    true_high_risk_nc += 1
        high_risk_precision = (
            true_high_risk_nc / predicted_high_risk_nc
            if predicted_high_risk_nc
            else 1.0
        )
        sample_counts: dict[str, dict[str, int]] = {}
        for entry in entries:
            rule_id = str(entry.get("rule_id") or "")
            bucket = sample_counts.setdefault(
                rule_id,
                {
                    "positive": 0,
                    "negative": 0,
                    "boundary": 0,
                    "real": 0,
                    "synthetic": 0,
                },
            )
            expected_state = str(entry.get("expected_state") or "")
            if expected_state == "non_compliant":
                bucket["positive"] += 1
            elif expected_state in {"compliant", "not_applicable"}:
                bucket["negative"] += 1
            else:
                bucket["boundary"] += 1
            bucket[str(entry.get("sample_type") or "")] += 1

        token_failures: list[dict[str, str]] = []
        for run in actual_runs:
            for entry in entries:
                pair = (
                    str(entry.get("case_label") or ""),
                    str(entry.get("rule_id") or ""),
                )
                actual = run.get(pair) or {}
                total_tokens = int(actual.get("total_tokens") or 0)
                if (
                    entry.get("decision_kind") == "deterministic"
                    and total_tokens != 0
                ):
                    token_failures.append(
                        {
                            "gate": "token_budget",
                            "failure_kind": "program_rule_used_model",
                            "rule_id": pair[1],
                        }
                    )
                elif (
                    entry.get("decision_kind") == "semantic"
                    and total_tokens > semantic_token_budget_per_rule
                ):
                    token_failures.append(
                        {
                            "gate": "token_budget",
                            "failure_kind": "semantic_rule_token_budget_exceeded",
                            "rule_id": pair[1],
                        }
                    )
        synthetic_exact = sum(
            all(
                _entry_matches(
                    entry,
                    run.get(
                        (
                            str(entry.get("case_label") or ""),
                            str(entry.get("rule_id") or ""),
                        )
                    ),
                )
                for run in actual_runs
            )
            for entry in synthetic_entries
        )
        v2_failures: list[dict[str, str]] = []
        if not real_entries:
            v2_failures.append(
                {"gate": "accuracy", "failure_kind": "missing_real_samples"}
            )
        if not definite_entries or definite_agreement < definite_agreement_min:
            v2_failures.append(
                {
                    "gate": "accuracy",
                    "failure_kind": "definite_agreement_below_threshold",
                }
            )
        if technical_rate > technical_error_rate_max:
            v2_failures.append(
                {
                    "gate": "technical_error",
                    "failure_kind": "technical_error_rate_above_threshold",
                }
            )
        if high_risk_precision < high_risk_nc_precision_min:
            v2_failures.append(
                {
                    "gate": "high_risk_nc",
                    "failure_kind": "precision_below_threshold",
                }
            )
        if synthetic_exact != len(synthetic_entries):
            v2_failures.append(
                {"gate": "synthetic", "failure_kind": "synthetic_regression"}
            )
        v2_failures.extend(token_failures)
        failures.extend(v2_failures)
        if v2_failures and exit_code == EXIT_PASSED:
            exit_code = EXIT_QUALITY_FAILURE
        quality = {
            "real_accuracy_denominator": len(definite_entries),
            "definite_agreement": definite_agreement,
            "data_gap_count": observed_states.count("data_gap"),
            "evaluation_unknown_ai_suggestion_count": observed_states.count(
                "evaluation_unknown"
            ),
            "technical_error_count": technical_count,
            "technical_error_rate": technical_rate,
            "high_risk_nc_precision": high_risk_precision,
            "synthetic_count": len(synthetic_entries),
            "synthetic_exact_count": synthetic_exact,
            "per_rule_sample_counts": dict(sorted(sample_counts.items())),
            "semantic_token_budget_per_rule": semantic_token_budget_per_rule,
        }
    payload = {
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
    }
    if quality is not None:
        payload["quality"] = quality
    return (
        payload,
        exit_code,
    )


def run_luxian_0609_golden_gate(
    *,
    ledger: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    run_batches: Sequence[Mapping[str, Any]],
    semantic_ppv_min: float = 0.95,
    semantic_recall_min: float = 0.90,
    semantic_min_positive: int = 1,
    semantic_min_negative: int = 1,
    expected_sample_count: int | None = None,
    expected_rule_count: int | None = None,
    selected_rule_ids: Sequence[str] | None = None,
    definite_agreement_min: float = 0.95,
    technical_error_rate_max: float = 0.01,
    high_risk_nc_precision_min: float = 0.95,
    semantic_token_budget_per_rule: int = 8192,
    runtime_manifest: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """正式发布质量门只接受运行身份绑定的 v2 工件。"""

    if not ledger:
        return _blocked("missing_accepted_ledger")
    if not candidate:
        return _blocked("missing_candidate_ledger")
    if not run_batches:
        return _blocked("missing_golden_runs")
    if (
        str(ledger.get("schema_version") or "") != LEDGER_SCHEMA_VERSION_V2
        or str(candidate.get("schema_version") or "") != CANDIDATE_SCHEMA_VERSION_V2
    ):
        return _blocked("legacy_v1_not_release_eligible")
    if runtime_manifest is None:
        return _blocked("missing_current_runtime_manifest")
    try:
        observed_current_git_head = validate_runtime_manifest_current(
            runtime_manifest,
        )
        current_manifest_hash = runtime_manifest_hash(runtime_manifest)
        executable_rule_ids = _validate_runtime_contract_identity(runtime_manifest)
        rule_set = runtime_manifest.get("rule_set")
        if not isinstance(rule_set, Mapping):
            raise ValueError("missing rule set")
        current_policy_version = str(rule_set.get("version") or "").strip()
    except (TypeError, ValueError):
        return _configuration_failure("invalid_current_runtime_manifest")
    try:
        golden_rule_ids = _resolve_golden_rule_ids(
            selected_rule_ids,
            executable_rule_ids=executable_rule_ids,
        )
    except (TypeError, ValueError):
        return _configuration_failure("invalid_expected_rule_scope")
    if expected_rule_count is not None and (
        type(expected_rule_count) is not int
        or expected_rule_count != len(golden_rule_ids)
    ):
        return _configuration_failure("invalid_expected_matrix")
    if (
        observed_current_git_head != str(ledger.get("git_head") or "")
        or current_manifest_hash != str(ledger.get("runtime_manifest_hash") or "")
        or current_policy_version != str(ledger.get("policy_version") or "")
    ):
        return _configuration_failure("stale_release_artifacts")
    summary, exit_code = _run_luxian_0609_golden_gate_diagnostic(
        ledger=ledger,
        candidate=candidate,
        run_batches=run_batches,
        semantic_ppv_min=semantic_ppv_min,
        semantic_recall_min=semantic_recall_min,
        semantic_min_positive=semantic_min_positive,
        semantic_min_negative=semantic_min_negative,
        expected_sample_count=expected_sample_count,
        expected_rule_count=expected_rule_count,
        expected_rule_ids=golden_rule_ids,
        definite_agreement_min=definite_agreement_min,
        technical_error_rate_max=technical_error_rate_max,
        high_risk_nc_precision_min=high_risk_nc_precision_min,
        semantic_token_budget_per_rule=semantic_token_budget_per_rule,
    )
    summary["rule_scope"] = _rule_scope_summary()
    return summary, exit_code


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609 accepted Golden 质量门")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--runtime-manifest", type=Path, default=None)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help="候选账本；省略时按 accepted 账本同目录推导 candidate 文件名",
    )
    parser.add_argument("--run", dest="runs", action="append", type=Path)
    parser.add_argument("--semantic-ppv-min", type=float, default=0.95)
    parser.add_argument("--semantic-recall-min", type=float, default=0.90)
    parser.add_argument("--semantic-min-positive", type=int, default=1)
    parser.add_argument("--semantic-min-negative", type=int, default=1)
    parser.add_argument("--definite-agreement-min", type=float, default=0.95)
    parser.add_argument("--technical-error-rate-max", type=float, default=0.01)
    parser.add_argument("--high-risk-nc-precision-min", type=float, default=0.95)
    parser.add_argument(
        "--semantic-token-budget-per-rule",
        type=int,
        default=8192,
    )
    parser.add_argument("--expected-sample-count", type=int, default=20)
    parser.add_argument("--expected-rule-count", type=int, default=None)
    parser.add_argument(
        "--rule-id",
        dest="selected_rule_ids",
        action="append",
        default=None,
        help="显式窄范围规则编号；仅允许当前可执行规则，每条只能传入一次",
    )
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
    candidate_path = args.candidate or _default_candidate_path(args.ledger)
    candidate = _read_json(candidate_path)
    runtime_manifest = (
        _read_json(args.runtime_manifest) if args.runtime_manifest is not None else None
    )
    run_paths = tuple(args.runs) if args.runs else DEFAULT_RUNS
    runs = [_read_json(path) for path in run_paths]
    if ledger is not None and candidate is None:
        summary, exit_code = _blocked("missing_candidate_ledger")
    elif ledger is not None and any(run is None for run in runs):
        summary, exit_code = _blocked("missing_golden_runs")
    else:
        summary, exit_code = run_luxian_0609_golden_gate(
            ledger=ledger,
            candidate=candidate,
            run_batches=[run for run in runs if run is not None],
            semantic_ppv_min=args.semantic_ppv_min,
            semantic_recall_min=args.semantic_recall_min,
            semantic_min_positive=args.semantic_min_positive,
            semantic_min_negative=args.semantic_min_negative,
            definite_agreement_min=args.definite_agreement_min,
            technical_error_rate_max=args.technical_error_rate_max,
            high_risk_nc_precision_min=args.high_risk_nc_precision_min,
            semantic_token_budget_per_rule=args.semantic_token_budget_per_rule,
            expected_sample_count=args.expected_sample_count,
            expected_rule_count=args.expected_rule_count,
            selected_rule_ids=args.selected_rule_ids,
            runtime_manifest=runtime_manifest,
        )
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
