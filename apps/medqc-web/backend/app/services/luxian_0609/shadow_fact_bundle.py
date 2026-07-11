"""Explicit, bounded shadow bundle for Manifest-paired FactV2 values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from itertools import islice
import json
import re
from typing import Any, Iterable, Sequence

from ..luxian_0609_fact_extraction import Luxian0609Fact
from .fact_schema import FactV2
from .legacy_fact_adapter import (
    MAX_REDACTION_TERMS,
    LegacyFactV2Mapping,
    adapt_luxian_0609_legacy_fact_shadow,
)
from .source_manifest import DocumentManifest


MAX_SHADOW_FACTS = 512
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key\s*[:=]|password\s*[:=])"
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_code(field_name: str, value: Any, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if (
        not text
        or len(text) > max_length
        or not _CODE_PATTERN.fullmatch(text)
        or _ID_CARD_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
        or _CREDENTIAL_PATTERN.search(text)
    ):
        raise ValueError(f"invalid {field_name}")
    return text


def _validate_sha256(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if not _SHA256_PATTERN.fullmatch(text):
        raise ValueError(f"invalid {field_name}")
    return text


def _validate_created_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at must be explicit ISO-8601 text")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("created_at must be valid ISO-8601 text") from None
    return text


def _copy_redaction_terms(values: Sequence[str]) -> tuple[str, ...]:
    if type(values) not in (tuple, list):
        raise TypeError("redaction_terms must be a tuple or list")
    if len(values) > MAX_REDACTION_TERMS:
        raise ValueError("too many redaction_terms")
    terms = tuple(values)
    for term in terms:
        if not isinstance(term, str):
            raise TypeError("redaction_terms must contain str values")
        normalized = term.strip()
        if not normalized:
            continue
        if len(normalized) > 128 or "\n" in normalized or "\r" in normalized:
            raise ValueError("invalid redaction term")
    return terms


@dataclass(frozen=True)
class FactShadowPairInput:
    pair_ref: str
    legacy_fact: Luxian0609Fact = field(repr=False, compare=False)
    mapping: LegacyFactV2Mapping = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pair_ref", _validate_sha256("pair_ref", self.pair_ref))
        if not isinstance(self.legacy_fact, Luxian0609Fact):
            raise TypeError("legacy_fact must be Luxian0609Fact")
        if not isinstance(self.mapping, LegacyFactV2Mapping):
            raise TypeError("mapping must be LegacyFactV2Mapping")


@dataclass(frozen=True)
class FactShadowBundleItem:
    pair_ref: str
    fact: FactV2 = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pair_ref", _validate_sha256("pair_ref", self.pair_ref))
        if not isinstance(self.fact, FactV2):
            raise TypeError("fact must be FactV2")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact.to_dict(),
            "pair_ref": self.pair_ref,
        }


@dataclass(frozen=True)
class FactShadowBundle:
    bundle_schema_version: str
    visit_ref: str
    manifest_fingerprint: str
    source_snapshot_hash: str
    items: tuple[FactShadowBundleItem, ...]
    created_at: str

    def __post_init__(self) -> None:
        try:
            item_iterator = iter(self.items)
        except TypeError:
            raise TypeError("items must be iterable") from None
        raw_items = tuple(islice(item_iterator, MAX_SHADOW_FACTS + 1))
        if len(raw_items) > MAX_SHADOW_FACTS:
            raise ValueError("too many shadow facts")
        if not all(isinstance(item, FactShadowBundleItem) for item in raw_items):
            raise TypeError("items must contain FactShadowBundleItem values")
        items = tuple(sorted(raw_items, key=lambda item: item.pair_ref))
        pair_refs = [item.pair_ref for item in items]
        fact_ids = [item.fact.fact_id for item in items]
        if len(pair_refs) != len(set(pair_refs)):
            raise ValueError("duplicate pair_ref in bundle")
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("duplicate fact_id in bundle")
        normalized_visit_ref = _validate_code(
            "visit_ref",
            self.visit_ref,
            max_length=128,
        )
        normalized_source_snapshot_hash = _validate_sha256(
            "source_snapshot_hash",
            self.source_snapshot_hash,
        )
        if any(item.fact.visit_ref != normalized_visit_ref for item in items):
            raise ValueError("bundle item visit_ref mismatch")
        if any(
            item.fact.source_snapshot_hash != normalized_source_snapshot_hash
            for item in items
        ):
            raise ValueError("bundle item source snapshot mismatch")
        object.__setattr__(
            self,
            "bundle_schema_version",
            _validate_code(
                "bundle_schema_version",
                self.bundle_schema_version,
                max_length=32,
            ),
        )
        object.__setattr__(
            self,
            "visit_ref",
            normalized_visit_ref,
        )
        object.__setattr__(
            self,
            "manifest_fingerprint",
            _validate_sha256("manifest_fingerprint", self.manifest_fingerprint),
        )
        object.__setattr__(
            self,
            "source_snapshot_hash",
            normalized_source_snapshot_hash,
        )
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "created_at", _validate_created_at(self.created_at))

    @property
    def fact_count(self) -> int:
        return len(self.items)

    def identity_dict(self) -> dict[str, Any]:
        return {
            "bundle_schema_version": self.bundle_schema_version,
            "items": [
                {"fact_id": item.fact.fact_id, "pair_ref": item.pair_ref}
                for item in self.items
            ],
            "manifest_fingerprint": self.manifest_fingerprint,
            "source_snapshot_hash": self.source_snapshot_hash,
            "visit_ref": self.visit_ref,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_schema_version": self.bundle_schema_version,
            "created_at": self.created_at,
            "fact_count": self.fact_count,
            "items": [item.to_dict() for item in self.items],
            "manifest_fingerprint": self.manifest_fingerprint,
            "source_snapshot_hash": self.source_snapshot_hash,
            "visit_ref": self.visit_ref,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def fingerprint(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.identity_dict()).encode("utf-8")
        ).hexdigest()


def build_luxian_0609_fact_shadow_bundle(
    *,
    visit_ref: str,
    manifest: DocumentManifest,
    paired_inputs: Iterable[FactShadowPairInput],
    bundle_schema_version: str,
    created_at: str,
    redaction_terms: Sequence[str],
) -> FactShadowBundle:
    """Build one all-or-nothing shadow bundle from explicit fact/mapping pairs."""

    if not isinstance(manifest, DocumentManifest):
        raise TypeError("manifest must be DocumentManifest")
    if manifest.visit_ref != visit_ref:
        raise ValueError("manifest visit_ref mismatch")
    copied_redaction_terms = _copy_redaction_terms(redaction_terms)
    try:
        pair_iterator = iter(paired_inputs)
    except TypeError:
        raise TypeError("paired_inputs must be iterable") from None
    pairs = tuple(islice(pair_iterator, MAX_SHADOW_FACTS + 1))
    if len(pairs) > MAX_SHADOW_FACTS:
        raise ValueError("too many shadow facts")
    if not all(isinstance(pair, FactShadowPairInput) for pair in pairs):
        raise TypeError("paired_inputs must contain FactShadowPairInput values")
    sorted_pairs = tuple(sorted(pairs, key=lambda pair: pair.pair_ref))
    pair_refs = [pair.pair_ref for pair in sorted_pairs]
    if len(pair_refs) != len(set(pair_refs)):
        raise ValueError("duplicate pair_ref")

    items: list[FactShadowBundleItem] = []
    fact_ids: set[str] = set()
    for pair in sorted_pairs:
        fact = adapt_luxian_0609_legacy_fact_shadow(
            legacy_fact=pair.legacy_fact,
            mapping=pair.mapping,
            manifest=manifest,
            visit_ref=visit_ref,
            created_at=created_at,
            redaction_terms=copied_redaction_terms,
        )
        if fact.fact_id in fact_ids:
            raise ValueError("duplicate fact_id")
        fact_ids.add(fact.fact_id)
        items.append(FactShadowBundleItem(pair_ref=pair.pair_ref, fact=fact))

    return FactShadowBundle(
        bundle_schema_version=bundle_schema_version,
        visit_ref=visit_ref,
        manifest_fingerprint=manifest.fingerprint(),
        source_snapshot_hash=manifest.source_snapshot_hash,
        items=tuple(items),
        created_at=created_at,
    )
