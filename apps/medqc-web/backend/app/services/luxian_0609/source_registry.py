"""LX0609 规则文书需求到受控来源的版本化注册表。

注册表区分物理来源、派生父来源和执行器别名。它只声明未来 snapshot
provider 必须遵守的读取能力，绝不把当前 bundle 投影等同于来源完整。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from types import MappingProxyType
import re
from typing import Mapping

from .evidence_snapshot import SourceCompleteness
from .rule_contracts import load_luxian_0609_rule_contracts


SOURCE_REGISTRY_VERSION = "lx0609-source-registry-v1"
EXACT_VISIT_BINDING_FIELDS = ("institute_id", "patient_id", "visit_id")
_SOURCE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class SourceAccessMode(str, Enum):
    BOUNDED_SOURCE_V1 = "bounded_source_v1"
    LEGACY_PROJECTION_V1 = "legacy_projection_v1"
    DERIVED_PROJECTION_V1 = "derived_projection_v1"


class CompletenessAttestationPolicy(str, Enum):
    UNPROVEN_ONLY = "unproven_only"
    PROVIDER_LIMIT_PLUS_ONE_V1 = "provider_limit_plus_one_v1"


@dataclass(frozen=True)
class SourceRegistryEntry:
    document_type: str
    physical_source_keys: tuple[str, ...]
    derived_from_source_keys: tuple[str, ...]
    projection_aliases: tuple[str, ...]
    query_version: str
    binding_fields: tuple[str, ...]
    access_mode: SourceAccessMode
    completeness_attestation_policy: CompletenessAttestationPolicy
    default_completeness: SourceCompleteness

    @property
    def source_keys(self) -> tuple[str, ...]:
        """受控读取键视图；明确排除执行器 projection aliases。"""

        return self.physical_source_keys or self.derived_from_source_keys

    @property
    def complete_capable(self) -> bool:
        """仅 future provider 的 limit+1 协议可证明查询结果未截断。"""

        return (
            self.completeness_attestation_policy
            is CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1
        )

    def __post_init__(self) -> None:
        if not isinstance(self.document_type, str) or not _SOURCE_KEY_PATTERN.fullmatch(
            self.document_type
        ):
            raise ValueError("invalid document_type")
        registered_keys = (*self.physical_source_keys, *self.derived_from_source_keys)
        if not registered_keys or any(
            not isinstance(item, str) or not _SOURCE_KEY_PATTERN.fullmatch(item)
            for item in registered_keys
        ):
            raise ValueError("invalid registered source keys")
        if len(registered_keys) != len(set(registered_keys)):
            raise ValueError("duplicate source_key in registry entry")
        if any(
            not isinstance(item, str) or not _SOURCE_KEY_PATTERN.fullmatch(item)
            for item in self.projection_aliases
        ):
            raise ValueError("invalid projection aliases")
        if not isinstance(self.query_version, str) or not self.query_version.strip():
            raise ValueError("invalid query_version")
        if self.binding_fields != EXACT_VISIT_BINDING_FIELDS:
            raise ValueError("source registry requires exact three-coordinate binding")
        if not isinstance(self.access_mode, SourceAccessMode):
            raise TypeError("access_mode must be SourceAccessMode")
        if not isinstance(self.completeness_attestation_policy, CompletenessAttestationPolicy):
            raise TypeError("invalid completeness attestation policy")
        if (
            self.completeness_attestation_policy
            is CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1
            and self.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1
        ):
            raise ValueError("only bounded source may use limit-plus-one attestation")
        if self.default_completeness is not SourceCompleteness.UNPROVEN:
            raise ValueError("registry cannot predeclare source completeness")


def _entry(
    document_type: str,
    *physical_source_keys: str,
    access_mode: SourceAccessMode = SourceAccessMode.LEGACY_PROJECTION_V1,
    derived_from_source_keys: tuple[str, ...] = (),
    projection_aliases: tuple[str, ...] = (),
) -> SourceRegistryEntry:
    completeness_policy = (
        CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1
        if access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
        else CompletenessAttestationPolicy.UNPROVEN_ONLY
    )
    return SourceRegistryEntry(
        document_type=document_type,
        physical_source_keys=(
            tuple(physical_source_keys)
            if physical_source_keys
            else (() if derived_from_source_keys else (document_type,))
        ),
        derived_from_source_keys=derived_from_source_keys,
        projection_aliases=projection_aliases,
        query_version=(
            f"snapshot-provider-{document_type}-v1"
            if access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
            else f"{access_mode.value}-{document_type}"
        ),
        binding_fields=EXACT_VISIT_BINDING_FIELDS,
        access_mode=access_mode,
        completeness_attestation_policy=completeness_policy,
        default_completeness=SourceCompleteness.UNPROVEN,
    )


_BOUNDED = SourceAccessMode.BOUNDED_SOURCE_V1
_DERIVED = SourceAccessMode.DERIVED_PROJECTION_V1

_REGISTRY_ENTRIES = (
    _entry("admission_record"),
    _entry("anesthesia_record"),
    _entry("bloodtrans_record", access_mode=_BOUNDED),
    _entry(
        "consent_form",
        "consent_form",
        "surgery_inform_consent",
        projection_aliases=(
            "anesthesia_consent",
            "anesthesia_consent_form",
            "blood_transfusion_consent",
        ),
    ),
    _entry("consultation_record", access_mode=_BOUNDED),
    _entry("daily_course_record", access_mode=_BOUNDED),
    _entry("discharge_record", access_mode=_BOUNDED),
    _entry(
        "exam_attention_report",
        access_mode=_DERIVED,
        derived_from_source_keys=("exam_master", "exam_item_report"),
    ),
    _entry("exam_item_report"),
    _entry("first_course_record"),
    _entry(
        "lab_attention_report",
        access_mode=_DERIVED,
        derived_from_source_keys=("labtest_master", "labtest_item_report"),
    ),
    _entry("labtest_item_report"),
    _entry(
        "medical_order",
        access_mode=_DERIVED,
        derived_from_source_keys=("inpat_nondrug_order", "inpat_drug_order"),
    ),
    _entry("postsurg_firstcourse_record"),
    _entry("presurg_discussion", access_mode=_BOUNDED),
    _entry("presurg_summary", access_mode=_BOUNDED),
    _entry("rescue_record"),
    _entry("senior_course_record", access_mode=_BOUNDED),
    _entry("surgery_record", "surgery_record", "mr_surgery", access_mode=_BOUNDED),
    _entry("surgery_risk_assessment"),
    _entry("surgery_safecheck_record", access_mode=_BOUNDED),
)


@lru_cache(maxsize=1)
def load_luxian_0609_source_registry() -> Mapping[str, SourceRegistryEntry]:
    entries = {entry.document_type: entry for entry in _REGISTRY_ENTRIES}
    if len(entries) != len(_REGISTRY_ENTRIES):
        raise ValueError("duplicate document_type in LX0609 source registry")
    declared_documents = {
        document_type
        for contract in load_luxian_0609_rule_contracts()
        for document_type in contract.applicable_documents
    }
    if set(entries) != declared_documents:
        raise ValueError("LX0609 source registry drift")
    return MappingProxyType(entries)


def resolve_luxian_0609_rule_sources(
    selected_rule_ids: tuple[str, ...],
) -> dict[str, tuple[SourceRegistryEntry, ...]]:
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}
    registry = load_luxian_0609_source_registry()
    if len(selected_rule_ids) != len(set(selected_rule_ids)):
        raise ValueError("duplicate LX0609 rule id")
    resolved: dict[str, tuple[SourceRegistryEntry, ...]] = {}
    for raw_rule_id in selected_rule_ids:
        rule_id = str(raw_rule_id or "").strip().upper()
        contract = contracts.get(rule_id)
        if contract is None:
            raise ValueError("unknown LX0609 rule id")
        resolved[rule_id] = tuple(registry[item] for item in contract.applicable_documents)
    return resolved


def _entries_for_source_key(source_key: str) -> tuple[SourceRegistryEntry, ...]:
    normalized = str(source_key or "").strip().lower()
    if not normalized or not _SOURCE_KEY_PATTERN.fullmatch(normalized):
        return ()
    return tuple(
        entry
        for entry in load_luxian_0609_source_registry().values()
        if normalized == entry.document_type or normalized in entry.source_keys
    )


def is_registered_luxian_0609_source_key(source_key: str) -> bool:
    return bool(_entries_for_source_key(source_key))


def source_key_accepts_query_version(source_key: str, query_version: str) -> bool:
    version = str(query_version or "").strip()
    return any(version == entry.query_version for entry in _entries_for_source_key(source_key))


def source_key_supports_proven_completeness(source_key: str, query_version: str) -> bool:
    """只有版本匹配的 limit+1 provider 结果可声明 COMPLETE/TRUNCATED。"""

    version = str(query_version or "").strip()
    return any(
        entry.complete_capable and version == entry.query_version
        for entry in _entries_for_source_key(source_key)
    )
