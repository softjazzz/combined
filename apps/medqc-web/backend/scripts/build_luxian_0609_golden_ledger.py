"""构建不含患者信息的 LX0609 Golden 候选与人工签收账本。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


CANDIDATE_SCHEMA_VERSION = "lx0609-golden-candidate-v1"
LEDGER_SCHEMA_VERSION = "lx0609-golden-ledger-v1"
API_BATCH_SCHEMA_VERSION = "lx0609-golden-api-batch-v1"

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_CASE_LABEL_RE = re.compile(r"^case-[0-9]{2,4}$")
_RULE_ID_RE = re.compile(r"^LX0609-[0-9]{3}$")
_SAFE_CODE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_REVIEWER_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{2,63}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_CREDENTIAL_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key\s*[:=])"
)

_FORBIDDEN_KEY_PARTS = (
    "instituteid",
    "patientid",
    "visitid",
    "patientname",
    "department",
    "idcard",
    "phone",
    "mobile",
    "address",
    "medicaltext",
    "recordcontent",
    "body",
    "primarydocumenttext",
    "supportingdocuments",
    "sourcecoordinates",
    "evidencepayload",
    "factrefs",
    "snapshot",
    "prompt",
    "rawresponse",
    "rawcontent",
    "rawoutput",
    "rawpayload",
    "rawtext",
    "llmrawoutput",
    "sql",
    "jobid",
    "bundle",
)
_OBSERVED_STATES = {
    "compliant",
    "non_compliant",
    "not_applicable",
    "data_gap",
    "evaluation_unknown",
    "technical_error",
}
_EXPECTED_STATES = _OBSERVED_STATES - {"technical_error"}
_DECISION_KINDS = {"deterministic", "semantic"}
_EXECUTOR_DECISION_KINDS = {
    "program": "deterministic",
    "llm": "semantic",
}


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def canonical_digest(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _assert_safe_api_dto(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = _normalized_key(key)
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError("unsafe API DTO")
            _assert_safe_api_dto(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _assert_safe_api_dto(child)
        return
    if isinstance(value, str):
        # 内部引用统一为精确小写 SHA-256；摘要中偶然出现证件/手机号形数字
        # 不代表原值泄漏。键名禁用已在上方先执行，非精确摘要仍照常扫描。
        if _SHA256_RE.fullmatch(value):
            return
        if (
            _PHONE_RE.search(value)
            or _ID_CARD_RE.search(value)
            or _CREDENTIAL_RE.search(value)
        ):
            raise ValueError("unsafe API DTO")
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("unsafe API DTO")


def _require_digest(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"invalid {field}")
    return normalized


def _evidence_hash(result: Mapping[str, Any]) -> str:
    # benchmark只允许逐规则opaque attestation，禁止再哈希任意客户证据文案。
    evidence_items = result.get("evidence_items")
    if not isinstance(evidence_items, list) or len(evidence_items) != 1:
        raise ValueError("missing evidence attestation")
    item = evidence_items[0]
    if not isinstance(item, Mapping) or set(item) != {"evidence_attestation"}:
        raise ValueError("invalid evidence attestation")
    return _require_digest(
        item.get("evidence_attestation"),
        field="evidence_attestation",
    )


def build_candidate_ledger(
    api_batch: Mapping[str, Any],
    *,
    candidate_version: str,
    generated_at: str,
) -> dict[str, Any]:
    """把已脱敏 API 批次变成候选；不生成任何人工 expected 字段。"""

    _assert_safe_api_dto(api_batch)
    if str(api_batch.get("schema_version") or "") != API_BATCH_SCHEMA_VERSION:
        raise ValueError("invalid API batch schema")
    normalized_version = str(candidate_version or "").strip()
    if not _SAFE_CODE_RE.fullmatch(normalized_version):
        raise ValueError("invalid candidate_version")
    normalized_generated_at = str(generated_at or "").strip()
    if not _UTC_RE.fullmatch(normalized_generated_at):
        raise ValueError("invalid generated_at")
    selector_version = str(api_batch.get("selector_version") or "").strip()
    if not _SAFE_CODE_RE.fullmatch(selector_version):
        raise ValueError("invalid selector_version")
    selector_digest = _require_digest(
        api_batch.get("selector_digest"), field="selector_digest"
    )
    rule_set_digest = _require_digest(
        api_batch.get("rule_set_digest"), field="rule_set_digest"
    )
    cases = api_batch.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("API batch requires cases")

    rows: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("invalid API case")
        case_label = str(case.get("case_label") or "").strip()
        if not _CASE_LABEL_RE.fullmatch(case_label) or case_label in seen_cases:
            raise ValueError("invalid case_label")
        seen_cases.add(case_label)
        response = case.get("response")
        if not isinstance(response, Mapping):
            raise ValueError("invalid API response")
        if str(response.get("schema_version") or "") != "lx0609-preproduction-runner-v1":
            raise ValueError("invalid API response schema")
        results = response.get("results")
        if not isinstance(results, list) or not results:
            raise ValueError("API response requires results")
        for result in results:
            if not isinstance(result, Mapping):
                raise ValueError("invalid API result")
            rule_id = str(result.get("rule_id") or "").strip().upper()
            state = str(result.get("status") or "").strip().lower()
            pair = (case_label, rule_id)
            if (
                not _RULE_ID_RE.fullmatch(rule_id)
                or state not in _OBSERVED_STATES
                or pair in seen_pairs
            ):
                raise ValueError("invalid API result")
            seen_pairs.add(pair)
            metadata = result.get("metadata")
            reason_code = ""
            decision_kind = ""
            executor_type = ""
            if isinstance(metadata, Mapping):
                reason_code = str(metadata.get("reason_code") or "").strip()
                executor_type = str(
                    metadata.get("executor_type") or ""
                ).strip().lower()
                decision_kind = _EXECUTOR_DECISION_KINDS.get(
                    executor_type,
                    "",
                )
            if reason_code and not _SAFE_CODE_RE.fullmatch(reason_code):
                raise ValueError("invalid observed reason")
            if executor_type and decision_kind not in _DECISION_KINDS:
                raise ValueError("invalid decision kind")
            row = {
                "case_label": case_label,
                "selector_digest": selector_digest,
                "rule_id": rule_id,
                "observed_state": state,
                "observed_reason_code": reason_code,
                "evidence_ref_hashes": [_evidence_hash(result)],
                "review_status": "candidate",
            }
            # v1 历史候选没有 executor_type；保留其 promotion 兼容性。
            # 新准生产安全 DTO 会显式携带该字段，review-template 只接受新候选。
            if decision_kind:
                row["decision_kind"] = decision_kind
            rows.append(row)

    candidate: dict[str, Any] = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "candidate_version": normalized_version,
        "selector_version": selector_version,
        "selector_digest": selector_digest,
        "rule_set_digest": rule_set_digest,
        "sample_count": len(seen_cases),
        "candidate_count": len(rows),
        "generated_at": normalized_generated_at,
        "rows": rows,
    }
    candidate["candidate_digest"] = canonical_digest(candidate)
    return candidate


_REVIEW_FIELD_ORDER = (
    "candidate_digest",
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
    "review_status",
)
_REVIEW_FIELDS = set(_REVIEW_FIELD_ORDER)
_CANDIDATE_ROW_REQUIRED_FIELDS = {
    "case_label",
    "selector_digest",
    "rule_id",
    "observed_state",
    "observed_reason_code",
    "evidence_ref_hashes",
    "review_status",
}


def _validate_candidate(candidate: Mapping[str, Any]) -> str:
    _assert_safe_api_dto(candidate)
    if str(candidate.get("schema_version") or "") != CANDIDATE_SCHEMA_VERSION:
        raise ValueError("invalid candidate ledger")
    claimed = _require_digest(
        candidate.get("candidate_digest"), field="candidate_digest"
    )
    material = {key: value for key, value in candidate.items() if key != "candidate_digest"}
    if canonical_digest(material) != claimed:
        raise ValueError("invalid candidate ledger")
    rows = candidate.get("rows")
    if (
        not isinstance(rows, list)
        or not rows
        or int(candidate.get("candidate_count") or 0) != len(rows)
    ):
        raise ValueError("invalid candidate ledger")
    selector_digest = _require_digest(
        candidate.get("selector_digest"), field="selector_digest"
    )
    seen_pairs: set[tuple[str, str]] = set()
    seen_cases: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) not in (
            _CANDIDATE_ROW_REQUIRED_FIELDS,
            _CANDIDATE_ROW_REQUIRED_FIELDS | {"decision_kind"},
        ):
            raise ValueError("invalid candidate ledger")
        case_label = str(row.get("case_label") or "").strip()
        rule_id = str(row.get("rule_id") or "").strip().upper()
        pair = (case_label, rule_id)
        reason_code = str(row.get("observed_reason_code") or "").strip()
        if (
            not _CASE_LABEL_RE.fullmatch(case_label)
            or not _RULE_ID_RE.fullmatch(rule_id)
            or pair in seen_pairs
            or str(row.get("selector_digest") or "").strip() != selector_digest
            or (
                "decision_kind" in row
                and str(row.get("decision_kind") or "").strip().lower()
                not in _DECISION_KINDS
            )
            or str(row.get("observed_state") or "").strip().lower()
            not in _OBSERVED_STATES
            or (reason_code and not _SAFE_CODE_RE.fullmatch(reason_code))
            or str(row.get("review_status") or "").strip().lower() != "candidate"
        ):
            raise ValueError("invalid candidate ledger")
        _review_hashes(row.get("evidence_ref_hashes"))
        seen_pairs.add(pair)
        seen_cases.add(case_label)
    if int(candidate.get("sample_count") or 0) != len(seen_cases):
        raise ValueError("invalid candidate ledger")
    return claimed


def _review_sort_key(row: Mapping[str, Any]) -> tuple[int, int]:
    return (
        int(str(row.get("case_label") or "").removeprefix("case-")),
        int(str(row.get("rule_id") or "").removeprefix("LX0609-")),
    )


def build_review_template_rows(
    candidate: Mapping[str, Any],
) -> list[dict[str, str]]:
    """从候选生成空白人工复核矩阵；绝不复制 observed 判定。"""

    candidate_digest = _validate_candidate(candidate)
    candidate_rows = candidate.get("rows")
    assert isinstance(candidate_rows, list)
    rows: list[dict[str, str]] = []
    for candidate_row in sorted(candidate_rows, key=_review_sort_key):
        assert isinstance(candidate_row, Mapping)
        decision_kind = str(candidate_row.get("decision_kind") or "").strip().lower()
        if decision_kind not in _DECISION_KINDS:
            raise ValueError("invalid candidate ledger")
        rows.append(
            {
                "candidate_digest": candidate_digest,
                "case_label": str(candidate_row.get("case_label") or ""),
                "selector_digest": str(
                    candidate_row.get("selector_digest") or ""
                ),
                "rule_id": str(candidate_row.get("rule_id") or ""),
                "decision_kind": decision_kind,
                "expected_state": "",
                "expected_reason_code": "",
                "evidence_ref_hashes": ";".join(
                    _review_hashes(candidate_row.get("evidence_ref_hashes"))
                ),
                "reviewer_code": "",
                "accepted_at": "",
                "review_revision": "",
                "review_status": "",
            }
        )
    return rows


def write_review_template_csv(
    path: Path,
    review_rows: Sequence[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=_REVIEW_FIELD_ORDER,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(review_rows)


def _review_hashes(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [item.strip() for item in value.split(";") if item.strip()]
    elif isinstance(value, (list, tuple)):
        values = [str(item or "").strip() for item in value]
    else:
        values = []
    if not values or len(values) != len(set(values)):
        raise ValueError("incomplete accepted review")
    if any(not _SHA256_RE.fullmatch(item) for item in values):
        raise ValueError("incomplete accepted review")
    return values


def promote_candidate_ledger(
    candidate: Mapping[str, Any],
    review_rows: Sequence[Mapping[str, Any]],
    *,
    ledger_version: str,
    generated_at: str,
    parent_ledger_digest: str = "",
) -> dict[str, Any]:
    """仅把逐行、显式且完整的人工签收提升为 accepted ledger。"""

    candidate_digest = _validate_candidate(candidate)
    normalized_version = str(ledger_version or "").strip()
    normalized_generated_at = str(generated_at or "").strip()
    if not _SAFE_CODE_RE.fullmatch(normalized_version):
        raise ValueError("invalid ledger_version")
    if not _UTC_RE.fullmatch(normalized_generated_at):
        raise ValueError("invalid generated_at")
    normalized_parent = str(parent_ledger_digest or "").strip()
    if normalized_parent and not _SHA256_RE.fullmatch(normalized_parent):
        raise ValueError("invalid parent_ledger_digest")

    candidate_rows = candidate.get("rows")
    if not isinstance(candidate_rows, list) or not candidate_rows:
        raise ValueError("invalid candidate ledger")
    if len(review_rows) != len(candidate_rows):
        raise ValueError("incomplete accepted review")

    review_map: dict[tuple[str, str], Mapping[str, Any]] = {}
    for review in review_rows:
        if not isinstance(review, Mapping):
            raise ValueError("incomplete accepted review")
        _assert_safe_api_dto(review)
        if set(review) != _REVIEW_FIELDS:
            raise ValueError("incomplete accepted review")
        pair = (
            str(review.get("case_label") or "").strip(),
            str(review.get("rule_id") or "").strip().upper(),
        )
        if pair in review_map:
            raise ValueError("incomplete accepted review")
        review_map[pair] = review

    entries: list[dict[str, Any]] = []
    for candidate_row in candidate_rows:
        if not isinstance(candidate_row, Mapping):
            raise ValueError("invalid candidate ledger")
        case_label = str(candidate_row.get("case_label") or "").strip()
        rule_id = str(candidate_row.get("rule_id") or "").strip().upper()
        review = review_map.get((case_label, rule_id))
        if review is None:
            raise ValueError("incomplete accepted review")
        expected_state = str(review.get("expected_state") or "").strip().lower()
        expected_reason = str(review.get("expected_reason_code") or "").strip()
        reviewer_code = str(review.get("reviewer_code") or "").strip().upper()
        accepted_at = str(review.get("accepted_at") or "").strip()
        decision_kind = str(review.get("decision_kind") or "").strip().lower()
        review_hashes = _review_hashes(review.get("evidence_ref_hashes"))
        candidate_hashes = _review_hashes(candidate_row.get("evidence_ref_hashes"))
        try:
            revision = int(str(review.get("review_revision") or "").strip())
        except ValueError as exc:
            raise ValueError("incomplete accepted review") from exc
        if (
            str(review.get("review_status") or "").strip().lower() != "accepted"
            or str(review.get("candidate_digest") or "").strip() != candidate_digest
            or str(review.get("selector_digest") or "").strip()
            != str(candidate.get("selector_digest") or "")
            or expected_state not in _EXPECTED_STATES
            or not _SAFE_CODE_RE.fullmatch(expected_reason)
            or not _REVIEWER_CODE_RE.fullmatch(reviewer_code)
            or not _UTC_RE.fullmatch(accepted_at)
            or decision_kind not in _DECISION_KINDS
            or (
                "decision_kind" in candidate_row
                and decision_kind
                != str(candidate_row.get("decision_kind") or "").strip().lower()
            )
            or review_hashes != candidate_hashes
            or revision < 1
        ):
            raise ValueError("incomplete accepted review")
        entries.append(
            {
                "case_label": case_label,
                "selector_digest": str(candidate.get("selector_digest") or ""),
                "rule_id": rule_id,
                "decision_kind": decision_kind,
                "expected_state": expected_state,
                "expected_reason_code": expected_reason,
                "evidence_ref_hashes": review_hashes,
                "reviewer_code": reviewer_code,
                "accepted_at": accepted_at,
                "review_revision": revision,
            }
        )

    ledger: dict[str, Any] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_version": normalized_version,
        "rule_set_digest": str(candidate.get("rule_set_digest") or ""),
        "selector_version": str(candidate.get("selector_version") or ""),
        "selector_digest": str(candidate.get("selector_digest") or ""),
        "sample_count": int(candidate.get("sample_count") or 0),
        "accepted_count": len(entries),
        "parent_ledger_digest": normalized_parent,
        "accepted_from_candidate_digest": candidate_digest,
        "generated_at": normalized_generated_at,
        "entries": entries,
    }
    ledger["ledger_digest"] = canonical_digest(ledger)
    return ledger


def _read_json_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("input must be an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609 Golden ledger 构建器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate = subparsers.add_parser("candidate")
    candidate.add_argument("--api-results", type=Path, required=True)
    candidate.add_argument("--candidate-version", required=True)
    candidate.add_argument("--generated-at", required=True)
    candidate.add_argument("--out", type=Path, required=True)

    review_template = subparsers.add_parser("review-template")
    review_template.add_argument("--candidate", type=Path, required=True)
    review_template.add_argument("--out", type=Path, required=True)

    promote = subparsers.add_parser("promote")
    promote.add_argument("--candidate", type=Path, required=True)
    promote.add_argument("--review", type=Path, required=True)
    promote.add_argument("--ledger-version", required=True)
    promote.add_argument("--generated-at", required=True)
    promote.add_argument("--parent-ledger-digest", default="")
    promote.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "candidate":
            output = build_candidate_ledger(
                _read_json_object(args.api_results),
                candidate_version=args.candidate_version,
                generated_at=args.generated_at,
            )
            count_field = "candidate_count"
            digest_field = "candidate_digest"
        elif args.command == "review-template":
            candidate = _read_json_object(args.candidate)
            review_rows = build_review_template_rows(candidate)
            write_review_template_csv(args.out, review_rows)
            output = {
                "review_count": len(review_rows),
                "candidate_digest": str(candidate.get("candidate_digest") or ""),
            }
            count_field = "review_count"
            digest_field = "candidate_digest"
        else:
            candidate = _read_json_object(args.candidate)
            with args.review.open("r", encoding="utf-8-sig", newline="") as handle:
                reviews = list(csv.DictReader(handle))
            output = promote_candidate_ledger(
                candidate,
                reviews,
                ledger_version=args.ledger_version,
                generated_at=args.generated_at,
                parent_ledger_digest=args.parent_ledger_digest,
            )
            count_field = "accepted_count"
            digest_field = "ledger_digest"
        if args.command != "review-template":
            _write_json(args.out, output)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        print(
            json.dumps(
                {"passed": False, "failure_kind": "invalid_golden_input"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            {
                "passed": True,
                count_field: int(output.get(count_field) or 0),
                digest_field: str(output.get(digest_field) or ""),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
