"""029/030/032 shadow planner 的事实抽取覆盖度纯契约。

覆盖度只描述抽取过程是否完整；它不判断适用性、来源结论或任何客户质控状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any

from .fact_schema import FactV2
from .planner import ShadowRulePlan
from .shadow_fact_bundle import FactShadowBundle
from .source_manifest import DocumentManifest, QueryStatus


MAX_COVERAGE_PAIRS = 64
MAX_FACT_REFS_PER_PAIR = 512
MAX_TOTAL_FACT_REFS = 2_048
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key\s*[:=]|password\s*[:=])"
)
_SENSITIVE_PATTERN = re.compile(
    r"(?i)(patient[_ -]?name|id[_ -]?card|phone|mobile|address|full[_ -]?text|"
    r"prompt|response|trace|quote|source[_ -]?document|error[_ -]?stack|sql)"
)
_FORBIDDEN_STATUS_PATTERN = re.compile(
    r"(?i)(?:not[_ -]?applicable|data[_ -]?gap|non[_ -]?compliant|"
    r"ai[_ -]?suggested|technical[_ -]?error|evaluation[_ -]?unknown|suppressed|"
    r"(?<!non[_ -])compliant)"
)
_PARTIAL_REASONS = frozenset({"partial_budget_limit", "partial_unsupported_record"})
_ERROR_REASON = "extraction_error"


class ExtractionCoverageState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_RUN = "not_run"
    ERROR = "error"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_code(field_name: str, value: Any, *, max_length: int = 128) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    if (
        not value
        or value != value.strip()
        or len(value) > max_length
        or not _CODE_PATTERN.fullmatch(value)
        or _ID_CARD_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
        or _CREDENTIAL_PATTERN.search(value)
        or _SENSITIVE_PATTERN.search(value)
        or _FORBIDDEN_STATUS_PATTERN.search(value)
    ):
        raise ValueError(f"invalid {field_name}")
    return value


def _validate_sha256(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {field_name}")
    return value


def _validate_created_at(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("created_at must be explicit ISO-8601 text")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("created_at must be valid ISO-8601 text") from None
    return value


def _coerce_state(value: ExtractionCoverageState | str) -> ExtractionCoverageState:
    if isinstance(value, ExtractionCoverageState):
        return value
    if isinstance(value, str):
        try:
            return ExtractionCoverageState(value)
        except ValueError:
            pass
    raise ValueError("invalid extraction coverage state")


def _coerce_query_status(value: QueryStatus | str) -> QueryStatus:
    if isinstance(value, QueryStatus):
        return value
    if isinstance(value, str):
        try:
            return QueryStatus(value)
        except ValueError:
            pass
    raise ValueError("invalid source query status")


@dataclass(frozen=True)
class CoveragePair:
    fact_type: str
    source_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_type", _validate_code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _validate_code("source_key", self.source_key))

    def to_dict(self) -> dict[str, str]:
        return {"fact_type": self.fact_type, "source_key": self.source_key}


@dataclass(frozen=True)
class CoverageSourceContext:
    source_key: str
    query_status: QueryStatus | str
    record_count: int | None

    def __post_init__(self) -> None:
        source_key = _validate_code("source_key", self.source_key)
        status = _coerce_query_status(self.query_status)
        if status is QueryStatus.AVAILABLE:
            if isinstance(self.record_count, bool) or not isinstance(self.record_count, int) or self.record_count < 1:
                raise ValueError("available source context requires positive record_count")
        elif status is QueryStatus.EMPTY:
            if self.record_count != 0:
                raise ValueError("empty source context requires zero record_count")
        elif self.record_count is not None:
            raise ValueError("unavailable or error source context requires null record_count")
        object.__setattr__(self, "source_key", source_key)
        object.__setattr__(self, "query_status", status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_status": self.query_status.value,
            "record_count": self.record_count,
            "source_key": self.source_key,
        }


@dataclass(frozen=True)
class FactCoverageObservation:
    fact_type: str
    source_key: str
    state: ExtractionCoverageState | str
    extractor_version: str
    mapping_policy_version: str
    processed_record_count: int
    produced_fact_ids: tuple[str, ...]
    reason_code: str = ""
    error_code: str = ""

    def __post_init__(self) -> None:
        fact_type = _validate_code("fact_type", self.fact_type)
        source_key = _validate_code("source_key", self.source_key)
        state = _coerce_state(self.state)
        if type(self.produced_fact_ids) is not tuple:
            raise TypeError("produced_fact_ids must be tuple")
        if len(self.produced_fact_ids) > MAX_FACT_REFS_PER_PAIR:
            raise ValueError("too many produced_fact_ids")
        fact_ids = tuple(_validate_sha256("produced_fact_id", item) for item in self.produced_fact_ids)
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("duplicate produced_fact_id")
        if isinstance(self.processed_record_count, bool) or not isinstance(self.processed_record_count, int) or self.processed_record_count < 0:
            raise ValueError("invalid processed_record_count")
        reason_code = _validate_code("reason_code", self.reason_code, max_length=64) if self.reason_code else ""
        error_code = _validate_code("error_code", self.error_code, max_length=64) if self.error_code else ""
        object.__setattr__(self, "fact_type", fact_type)
        object.__setattr__(self, "source_key", source_key)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "extractor_version", _validate_code("extractor_version", self.extractor_version, max_length=96))
        object.__setattr__(self, "mapping_policy_version", _validate_code("mapping_policy_version", self.mapping_policy_version, max_length=96))
        object.__setattr__(self, "produced_fact_ids", fact_ids)
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "error_code", error_code)

    @property
    def pair(self) -> CoveragePair:
        return CoveragePair(self.fact_type, self.source_key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "extractor_version": self.extractor_version,
            "fact_type": self.fact_type,
            "mapping_policy_version": self.mapping_policy_version,
            "processed_record_count": self.processed_record_count,
            "produced_fact_ids": list(self.produced_fact_ids),
            "reason_code": self.reason_code,
            "source_key": self.source_key,
            "state": self.state.value,
        }


@dataclass(frozen=True)
class FactCoverageRef:
    fact_id: str
    fact_type: str
    source_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_id", _validate_sha256("fact_id", self.fact_id))
        object.__setattr__(self, "fact_type", _validate_code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _validate_code("source_key", self.source_key))

    def to_dict(self) -> dict[str, str]:
        return {"fact_id": self.fact_id, "fact_type": self.fact_type, "source_key": self.source_key}


@dataclass(frozen=True)
class FactCoverageItem:
    observation: FactCoverageObservation
    produced_fact_refs: tuple[FactCoverageRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.observation, FactCoverageObservation):
            raise TypeError("observation must be FactCoverageObservation")
        if type(self.produced_fact_refs) is not tuple:
            raise TypeError("produced_fact_refs must be tuple")
        if len(self.produced_fact_refs) > MAX_FACT_REFS_PER_PAIR or not all(isinstance(item, FactCoverageRef) for item in self.produced_fact_refs):
            raise ValueError("invalid produced_fact_refs")
        if tuple(item.fact_id for item in self.produced_fact_refs) != self.observation.produced_fact_ids:
            raise ValueError("produced fact refs do not match observation")
        if any(
            item.fact_type != self.observation.fact_type or item.source_key != self.observation.source_key
            for item in self.produced_fact_refs
        ):
            raise ValueError("produced fact ref pair mismatch")

    @property
    def pair(self) -> CoveragePair:
        return self.observation.pair

    def to_dict(self) -> dict[str, Any]:
        value = self.observation.to_dict()
        value["produced_fact_refs"] = [item.to_dict() for item in self.produced_fact_refs]
        return value


def _validate_truth_table(item: FactCoverageItem, context: CoverageSourceContext) -> None:
    observation = item.observation
    if observation.source_key != context.source_key:
        raise ValueError("coverage source context mismatch")
    state = observation.state
    count = observation.processed_record_count
    has_facts = bool(observation.produced_fact_ids)
    if context.query_status is QueryStatus.AVAILABLE:
        assert context.record_count is not None
        if state is ExtractionCoverageState.COMPLETE:
            if count != context.record_count or observation.reason_code or observation.error_code:
                raise ValueError("invalid available complete coverage")
        elif state is ExtractionCoverageState.PARTIAL:
            if not 0 <= count < context.record_count or observation.reason_code not in _PARTIAL_REASONS or observation.error_code:
                raise ValueError("invalid available partial coverage")
        elif state is ExtractionCoverageState.NOT_RUN:
            if count != 0 or has_facts or observation.reason_code != "extractor_not_run" or observation.error_code:
                raise ValueError("invalid available not_run coverage")
        elif state is ExtractionCoverageState.ERROR:
            if not 0 <= count <= context.record_count or observation.reason_code != _ERROR_REASON or not observation.error_code:
                raise ValueError("invalid available error coverage")
    elif context.query_status is QueryStatus.EMPTY:
        if state is ExtractionCoverageState.COMPLETE:
            if count != 0 or has_facts or observation.reason_code or observation.error_code:
                raise ValueError("invalid empty complete coverage")
        elif state is ExtractionCoverageState.NOT_RUN:
            if count != 0 or has_facts or observation.reason_code != "extractor_not_run" or observation.error_code:
                raise ValueError("invalid empty not_run coverage")
        else:
            raise ValueError("empty source only allows complete or not_run coverage")
    elif context.query_status is QueryStatus.UNAVAILABLE:
        if state is not ExtractionCoverageState.NOT_RUN or count != 0 or has_facts or observation.reason_code != "source_unavailable" or observation.error_code:
            raise ValueError("invalid unavailable source coverage")
    elif context.query_status is QueryStatus.ERROR:
        if state is not ExtractionCoverageState.NOT_RUN or count != 0 or has_facts or observation.reason_code != "source_query_error" or observation.error_code:
            raise ValueError("invalid source query error coverage")


@dataclass(frozen=True)
class FactCoverageReport:
    coverage_schema_version: str
    coverage_policy_version: str
    visit_ref: str
    plan_fingerprint: str
    manifest_fingerprint: str
    source_snapshot_hash: str
    bundle_fingerprint: str
    required_pairs: tuple[CoveragePair, ...]
    source_contexts: tuple[CoverageSourceContext, ...]
    items: tuple[FactCoverageItem, ...]
    bundle_fact_index: tuple[FactCoverageRef, ...] = field(repr=False)
    plan: ShadowRulePlan = field(repr=False, compare=False)
    manifest: DocumentManifest = field(repr=False, compare=False)
    bundle: FactShadowBundle = field(repr=False, compare=False)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ShadowRulePlan) or not isinstance(self.manifest, DocumentManifest) or not isinstance(self.bundle, FactShadowBundle):
            raise TypeError("coverage report requires accepted plan, manifest and bundle")
        if self.plan.visit_ref != self.manifest.visit_ref or self.plan.visit_ref != self.bundle.visit_ref:
            raise ValueError("coverage report visit_ref mismatch")
        if self.visit_ref != self.plan.visit_ref:
            raise ValueError("coverage report visit_ref does not match inputs")
        if self.bundle.manifest_fingerprint != self.manifest.fingerprint() or self.bundle.source_snapshot_hash != self.manifest.source_snapshot_hash:
            raise ValueError("coverage report bundle manifest mismatch")
        if any(type(value) is not tuple for value in (self.required_pairs, self.source_contexts, self.items, self.bundle_fact_index)):
            raise TypeError("coverage report collections must be tuple")
        if len(self.required_pairs) > MAX_COVERAGE_PAIRS or len(self.items) > MAX_COVERAGE_PAIRS:
            raise ValueError("too many coverage pairs")
        if not all(isinstance(item, CoveragePair) for item in self.required_pairs):
            raise TypeError("required_pairs must contain CoveragePair")
        required_pairs = tuple(sorted(self.required_pairs, key=lambda item: (item.fact_type, item.source_key)))
        if len(required_pairs) != len(set(required_pairs)):
            raise ValueError("duplicate required coverage pair")
        if required_pairs != _required_pairs_from_plan(self.plan):
            raise ValueError("required coverage pairs do not match plan")
        source_contexts = tuple(sorted(self.source_contexts, key=lambda item: item.source_key))
        if not all(isinstance(item, CoverageSourceContext) for item in source_contexts):
            raise TypeError("source_contexts must contain CoverageSourceContext")
        if len({item.source_key for item in source_contexts}) != len(source_contexts):
            raise ValueError("duplicate source coverage context")
        if {pair.source_key for pair in required_pairs} != {item.source_key for item in source_contexts}:
            raise ValueError("source contexts do not exactly match required pairs")
        manifest_entries = {entry.source_key: entry for entry in self.manifest.entries}
        if not {pair.source_key for pair in required_pairs}.issubset(manifest_entries):
            raise ValueError("required coverage source is absent from manifest")
        expected_contexts = tuple(
            CoverageSourceContext(
                source_key=source_key,
                query_status=manifest_entries[source_key].query_status,
                record_count=manifest_entries[source_key].record_count,
            )
            for source_key in sorted({pair.source_key for pair in required_pairs})
        )
        if source_contexts != expected_contexts:
            raise ValueError("source contexts do not match manifest")
        if not all(isinstance(item, FactCoverageItem) for item in self.items):
            raise TypeError("items must contain FactCoverageItem")
        items = tuple(sorted(self.items, key=lambda item: (item.pair.fact_type, item.pair.source_key)))
        if tuple(item.pair for item in items) != required_pairs:
            raise ValueError("coverage items do not exactly match required pairs")
        if not all(isinstance(item, FactCoverageRef) for item in self.bundle_fact_index):
            raise TypeError("bundle_fact_index must contain FactCoverageRef")
        if len(self.bundle_fact_index) > MAX_TOTAL_FACT_REFS or len({item.fact_id for item in self.bundle_fact_index}) != len(self.bundle_fact_index):
            raise ValueError("invalid bundle fact index")
        expected_fact_index = tuple(
            sorted(
                (
                    FactCoverageRef(
                        fact_id=item.fact.fact_id,
                        fact_type=item.fact.fact_type,
                        source_key=item.fact.source_key,
                    )
                    for item in self.bundle.items
                ),
                key=lambda item: item.fact_id,
            )
        )
        if tuple(sorted(self.bundle_fact_index, key=lambda item: item.fact_id)) != expected_fact_index:
            raise ValueError("bundle fact index does not match bundle")
        fact_index = {item.fact_id: item for item in self.bundle_fact_index}
        claimed_ids: list[str] = []
        contexts = {item.source_key: item for item in source_contexts}
        for item in items:
            _validate_truth_table(item, contexts[item.pair.source_key])
            for fact_ref in item.produced_fact_refs:
                if fact_index.get(fact_ref.fact_id) != fact_ref:
                    raise ValueError("produced fact reference is not in bundle index")
                claimed_ids.append(fact_ref.fact_id)
        if len(claimed_ids) != len(set(claimed_ids)):
            raise ValueError("fact id claimed by multiple coverage pairs")
        object.__setattr__(self, "coverage_schema_version", _validate_code("coverage_schema_version", self.coverage_schema_version, max_length=64))
        object.__setattr__(self, "coverage_policy_version", _validate_code("coverage_policy_version", self.coverage_policy_version, max_length=64))
        object.__setattr__(self, "visit_ref", _validate_code("visit_ref", self.visit_ref))
        for name in ("plan_fingerprint", "manifest_fingerprint", "source_snapshot_hash", "bundle_fingerprint"):
            object.__setattr__(self, name, _validate_sha256(name, getattr(self, name)))
        if (
            self.plan_fingerprint != self.plan.fingerprint()
            or self.manifest_fingerprint != self.manifest.fingerprint()
            or self.source_snapshot_hash != self.manifest.source_snapshot_hash
            or self.bundle_fingerprint != self.bundle.fingerprint()
        ):
            raise ValueError("coverage report fingerprints do not match inputs")
        object.__setattr__(self, "required_pairs", required_pairs)
        object.__setattr__(self, "source_contexts", source_contexts)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "bundle_fact_index", tuple(sorted(self.bundle_fact_index, key=lambda item: item.fact_id)))
        object.__setattr__(self, "created_at", _validate_created_at(self.created_at))

    def summary_dict(self) -> dict[str, Any]:
        counts = {state.value: 0 for state in ExtractionCoverageState}
        for item in self.items:
            counts[item.observation.state.value] += 1
        return {
            "all_required_pairs_complete": counts["complete"] == len(self.items),
            "complete_pair_count": counts["complete"],
            "error_pair_count": counts["error"],
            "not_run_pair_count": counts["not_run"],
            "partial_pair_count": counts["partial"],
            "required_pair_count": len(self.items),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_policy_version": self.coverage_policy_version,
            "coverage_schema_version": self.coverage_schema_version,
            "created_at": self.created_at,
            "items": [item.to_dict() for item in self.items],
            "manifest_fingerprint": self.manifest_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "required_pairs": [item.to_dict() for item in self.required_pairs],
            "source_contexts": [item.to_dict() for item in self.source_contexts],
            "source_snapshot_hash": self.source_snapshot_hash,
            "summary": self.summary_dict(),
            "bundle_fingerprint": self.bundle_fingerprint,
            "visit_ref": self.visit_ref,
        }

    def identity_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("created_at")
        return value

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json(self.identity_dict()).encode("utf-8")).hexdigest()


def _required_pairs_from_plan(plan: ShadowRulePlan) -> tuple[CoveragePair, ...]:
    return tuple(
        sorted(
            {
                CoveragePair(requirement.fact_type, source_key)
                for rule in plan.planned_rules
                for requirement in rule.trigger_requirements
                for source_key in requirement.allowed_source_keys
            },
            key=lambda item: (item.fact_type, item.source_key),
        )
    )


def build_luxian_0609_fact_coverage_shadow(
    *,
    plan: ShadowRulePlan,
    manifest: DocumentManifest,
    bundle: FactShadowBundle,
    observations: tuple[FactCoverageObservation, ...] | list[FactCoverageObservation],
    coverage_schema_version: str,
    coverage_policy_version: str,
    created_at: str,
) -> FactCoverageReport:
    """用显式 observation 构造 planner 所需的事实抽取覆盖度 shadow report。"""

    if not isinstance(plan, ShadowRulePlan) or not isinstance(manifest, DocumentManifest) or not isinstance(bundle, FactShadowBundle):
        raise TypeError("plan, manifest and bundle must be accepted value objects")
    if type(observations) not in (tuple, list):
        raise TypeError("observations must be a concrete tuple or list")
    if len(observations) > MAX_COVERAGE_PAIRS:
        raise ValueError("too many observations")
    if plan.visit_ref != manifest.visit_ref or plan.visit_ref != bundle.visit_ref:
        raise ValueError("coverage visit_ref mismatch")
    if bundle.manifest_fingerprint != manifest.fingerprint() or bundle.source_snapshot_hash != manifest.source_snapshot_hash:
        raise ValueError("coverage bundle manifest mismatch")
    required_pairs = _required_pairs_from_plan(plan)
    if len(observations) != len(required_pairs) or not all(isinstance(item, FactCoverageObservation) for item in observations):
        raise ValueError("observations must exactly cover required pairs")
    observations_by_pair = {item.pair: item for item in observations}
    if len(observations_by_pair) != len(observations) or set(observations_by_pair) != set(required_pairs):
        raise ValueError("observations must exactly match required pairs")
    entries = {entry.source_key: entry for entry in manifest.entries}
    if not {pair.source_key for pair in required_pairs}.issubset(entries):
        raise ValueError("required coverage source is absent from manifest")
    contexts = tuple(
        CoverageSourceContext(
            source_key=source_key,
            query_status=entries[source_key].query_status,
            record_count=entries[source_key].record_count,
        )
        for source_key in sorted({pair.source_key for pair in required_pairs})
    )
    fact_index = tuple(
        FactCoverageRef(
            fact_id=item.fact.fact_id,
            fact_type=item.fact.fact_type,
            source_key=item.fact.source_key,
        )
        for item in bundle.items
    )
    indexed_facts = {item.fact_id: item for item in fact_index}
    claimed_ids: set[str] = set()
    items: list[FactCoverageItem] = []
    for pair in required_pairs:
        observation = observations_by_pair[pair]
        refs: list[FactCoverageRef] = []
        for fact_id in observation.produced_fact_ids:
            fact_ref = indexed_facts.get(fact_id)
            if fact_ref is None or fact_ref.fact_type != pair.fact_type or fact_ref.source_key != pair.source_key:
                raise ValueError("produced fact reference does not match coverage pair")
            if fact_id in claimed_ids:
                raise ValueError("fact id claimed by multiple coverage pairs")
            claimed_ids.add(fact_id)
            refs.append(fact_ref)
        items.append(FactCoverageItem(observation=observation, produced_fact_refs=tuple(refs)))
    return FactCoverageReport(
        coverage_schema_version=coverage_schema_version,
        coverage_policy_version=coverage_policy_version,
        visit_ref=plan.visit_ref,
        plan_fingerprint=plan.fingerprint(),
        manifest_fingerprint=manifest.fingerprint(),
        source_snapshot_hash=manifest.source_snapshot_hash,
        bundle_fingerprint=bundle.fingerprint(),
        required_pairs=required_pairs,
        source_contexts=contexts,
        items=tuple(items),
        bundle_fact_index=fact_index,
        plan=plan,
        manifest=manifest,
        bundle=bundle,
        created_at=created_at,
    )
