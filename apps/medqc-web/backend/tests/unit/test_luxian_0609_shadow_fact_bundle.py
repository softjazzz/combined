from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from app.services.luxian_0609.fact_schema import TimeValue
from app.services.luxian_0609.legacy_fact_adapter import (
    MAX_REDACTION_TERMS,
    LegacyFactV2Mapping,
)
from app.services.luxian_0609.shadow_fact_bundle import (
    MAX_SHADOW_FACTS,
    FactShadowBundle,
    FactShadowBundleItem,
    FactShadowPairInput,
    build_luxian_0609_fact_shadow_bundle,
)
from app.services.luxian_0609.source_manifest import (
    DocumentManifest,
    SourceManifestEntry,
)
from app.services.luxian_0609_fact_extraction import Luxian0609Fact


CREATED_AT = "2026-07-12T09:00:00+08:00"
SNAPSHOT_A = "a" * 64
SNAPSHOT_B = "b" * 64


def _pair_ref(index: int) -> str:
    return hashlib.sha256(f"pair-{index}".encode("utf-8")).hexdigest()


def _manifest(
    *,
    visit_ref: str = "visit-ref-001",
    source_snapshot_hash: str = SNAPSHOT_A,
    source_key: str = "surgery_record",
    status: str = "available",
) -> DocumentManifest:
    record_count = 1 if status == "available" else 0 if status == "empty" else None
    error_code = "QUERY_FAILED" if status == "error" else ""
    reason_code = "NOT_EXPOSED" if status == "unavailable" else ""
    entry = SourceManifestEntry.create(
        source_key=source_key,
        query_status=status,
        record_count=record_count,
        query_version="query-v1",
        snapshot_ref="sha256:" + hashlib.sha256(source_key.encode("utf-8")).hexdigest(),
        error_code=error_code,
        reason_code=reason_code,
    )
    return DocumentManifest.create(
        manifest_schema_version="1.0",
        visit_ref=visit_ref,
        source_snapshot_hash=source_snapshot_hash,
        entries=(entry,),
        created_at=CREATED_AT,
    )


def _legacy(**overrides) -> Luxian0609Fact:
    values = {
        "fact_type": "surgery_presence",
        "family": "surgery_anesthesia",
        "source_document_type": "手术记录",
        "source_document_id": "document-ref-001",
        "record_time": "",
        "quote": "存在手术记录",
        "confidence": 0.9,
        "extractor": "structured",
        "trace": {"matched_by": "legacy"},
    }
    values.update(overrides)
    return Luxian0609Fact(**values)


def _mapping(index: int = 0, **overrides) -> LegacyFactV2Mapping:
    values = {
        "source_key": "surgery_record",
        "normalized_value": {"present": True, "ordinal": index},
        "trigger_scope": "current_visit",
        "current_visit_relevance": "relevant",
        "assertion": "affirmed",
        "assertion_context": "current_narrative",
        "event_status": "performed",
        "extractor_version": "policy-v1",
        "record_time_handling": "absent",
        "mapped_record_time": None,
        "omit_reason_code": "",
    }
    values.update(overrides)
    return LegacyFactV2Mapping(**values)


def _pair(index: int = 0, **overrides) -> FactShadowPairInput:
    values = {
        "pair_ref": _pair_ref(index),
        "legacy_fact": _legacy(source_document_id=f"document-ref-{index}"),
        "mapping": _mapping(index),
    }
    values.update(overrides)
    return FactShadowPairInput(**values)


def _build(
    *,
    manifest: DocumentManifest | None = None,
    paired_inputs=(),
    visit_ref: str = "visit-ref-001",
    bundle_schema_version: str = "1.0",
    created_at: str = CREATED_AT,
    redaction_terms=(),
) -> FactShadowBundle:
    return build_luxian_0609_fact_shadow_bundle(
        visit_ref=visit_ref,
        manifest=manifest or _manifest(),
        paired_inputs=paired_inputs,
        bundle_schema_version=bundle_schema_version,
        created_at=created_at,
        redaction_terms=redaction_terms,
    )


@pytest.mark.unit
def test_zero_fact_bundle_is_valid_stable_and_has_no_customer_status() -> None:
    left = _build()
    right = _build(created_at="2026-07-12T10:00:00+08:00")
    assert left.fact_count == 0
    assert left.items == ()
    assert left.fingerprint() == right.fingerprint()
    payload = left.to_dict()
    assert payload["items"] == []
    assert payload["fact_count"] == 0
    serialized = left.canonical_json()
    for forbidden in ("data_gap", "not_applicable", "compliant", "ai_suggested"):
        assert forbidden not in serialized


@pytest.mark.unit
def test_single_and_multiple_pairs_are_explicit_and_sorted_by_pair_ref() -> None:
    first = _pair(1)
    second = _pair(2)
    single = _build(paired_inputs=(first,))
    multiple = _build(paired_inputs=(second, first))
    assert single.fact_count == 1
    assert multiple.fact_count == 2
    assert [item.pair_ref for item in multiple.items] == sorted(
        [first.pair_ref, second.pair_ref]
    )
    assert all(item.fact.fact_id for item in multiple.items)


@pytest.mark.unit
def test_input_order_and_created_at_do_not_change_bundle_fingerprint() -> None:
    pairs = (_pair(1), _pair(2), _pair(3))
    left = _build(paired_inputs=pairs)
    right = _build(
        paired_inputs=tuple(reversed(pairs)),
        created_at="2026-07-12T10:00:00+08:00",
    )
    assert left.fingerprint() == right.fingerprint()
    assert [item.pair_ref for item in left.items] == [
        item.pair_ref for item in right.items
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "pair_ref",
    ["short", "A" * 64, "g" * 64, ("a" * 64) + "tail"],
)
def test_pair_ref_format_is_strict_on_direct_input_construction(pair_ref: str) -> None:
    with pytest.raises(ValueError):
        FactShadowPairInput(
            pair_ref=pair_ref,
            legacy_fact=_legacy(),
            mapping=_mapping(),
        )


@pytest.mark.unit
def test_pair_input_requires_real_legacy_and_mapping_objects_without_repr_leak() -> None:
    with pytest.raises(TypeError):
        FactShadowPairInput(
            pair_ref=_pair_ref(1),
            legacy_fact={"fact_type": "x"},  # type: ignore[arg-type]
            mapping=_mapping(),
        )
    with pytest.raises(TypeError):
        FactShadowPairInput(
            pair_ref=_pair_ref(1),
            legacy_fact=_legacy(),
            mapping={"source_key": "x"},  # type: ignore[arg-type]
        )
    pair = _pair(1, legacy_fact=_legacy(quote="private quote", trace={"prompt": "hidden"}))
    assert "private quote" not in repr(pair)
    assert "hidden" not in repr(pair)


@pytest.mark.unit
def test_bundle_item_direct_construction_revalidates_pair_ref_and_fact_type() -> None:
    fact = _build(paired_inputs=(_pair(1),)).items[0].fact
    with pytest.raises(ValueError):
        FactShadowBundleItem(pair_ref="invalid", fact=fact)
    with pytest.raises(TypeError):
        FactShadowBundleItem(pair_ref=_pair_ref(1), fact={})  # type: ignore[arg-type]


@pytest.mark.unit
def test_duplicate_pair_ref_and_duplicate_fact_identity_fail_closed() -> None:
    first = _pair(1)
    with pytest.raises(ValueError):
        _build(paired_inputs=(first, replace(first, legacy_fact=_legacy())))

    duplicate_identity = FactShadowPairInput(
        pair_ref=_pair_ref(2),
        legacy_fact=first.legacy_fact,
        mapping=first.mapping,
    )
    with pytest.raises(ValueError):
        _build(paired_inputs=(first, duplicate_identity))


@pytest.mark.unit
def test_max_shadow_facts_allows_limit_and_consumes_only_limit_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.luxian_0609.shadow_fact_bundle as bundle_module

    monkeypatch.setattr(bundle_module, "MAX_SHADOW_FACTS", 2)
    allowed = _build(paired_inputs=(_pair(1), _pair(2)))
    assert allowed.fact_count == 2

    consumed = 0

    def pairs():
        nonlocal consumed
        for index in range(100):
            consumed += 1
            yield _pair(index + 10)

    with pytest.raises(ValueError):
        _build(paired_inputs=pairs())
    assert consumed == 3


@pytest.mark.unit
@pytest.mark.parametrize(
    "redaction_terms",
    ["person-name", b"person-name", bytearray(b"person-name"), iter(["person-name"])],
)
def test_bundle_redaction_terms_require_concrete_non_binary_sequence(redaction_terms) -> None:
    with pytest.raises(TypeError):
        _build(redaction_terms=redaction_terms)


@pytest.mark.unit
def test_bundle_redaction_terms_reject_container_subclasses_before_iteration() -> None:
    consumed = 0

    class CustomList(list):
        def __iter__(self):
            nonlocal consumed
            while True:
                consumed += 1
                yield "unused-term"

    with pytest.raises(TypeError):
        _build(redaction_terms=CustomList(["unused-term"]))
    assert consumed == 0


@pytest.mark.unit
def test_bundle_redaction_terms_are_bounded_copied_and_keep_adapter_semantics() -> None:
    terms = ["person-name"]
    bundle = _build(
        paired_inputs=(
            _pair(1, legacy_fact=_legacy(quote="person-name手术记录")),
        ),
        redaction_terms=terms,
    )
    terms[0] = "changed-after-build"
    assert "person-name" not in bundle.canonical_json()
    assert "changed-after-build" not in bundle.canonical_json()

    _build(redaction_terms=[""] * MAX_REDACTION_TERMS)
    with pytest.raises(ValueError):
        _build(redaction_terms=[""] * (MAX_REDACTION_TERMS + 1))

    with pytest.raises(ValueError):
        _build(
            paired_inputs=(
                _pair(1, legacy_fact=_legacy(source_document_type="person-name手术记录")),
            ),
            redaction_terms=["person-name"],
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "pair",
    [
        _pair(1, mapping=_mapping(source_key="missing_source")),
        _pair(2, mapping=_mapping(assertion="positive")),
        _pair(
            3,
            legacy_fact=_legacy(record_time="raw time"),
            mapping=_mapping(record_time_handling="absent"),
        ),
        _pair(4, mapping=_mapping(normalized_value={"result": "non_compliant"})),
    ],
)
def test_any_item_failure_aborts_entire_pure_build(pair: FactShadowPairInput) -> None:
    with pytest.raises((TypeError, ValueError)):
        _build(paired_inputs=(_pair(100), pair))


@pytest.mark.unit
def test_bundle_fingerprint_tracks_manifest_and_fact_identity_dimensions() -> None:
    baseline = _build(paired_inputs=(_pair(1),))
    mapped_time = TimeValue.create(
        value="2026-01-02T03:04:05+08:00",
        source="caller-mapped-record-time",
        timezone="Asia/Shanghai",
        precision="second",
    )
    changes = [
        _build(
            manifest=_manifest(source_snapshot_hash=SNAPSHOT_B),
            paired_inputs=(_pair(1),),
        ),
        _build(paired_inputs=(_pair(1, mapping=_mapping(assertion="uncertain")),)),
        _build(paired_inputs=(_pair(1, mapping=_mapping(normalized_value={"present": False})),)),
        _build(paired_inputs=(_pair(1, mapping=_mapping(extractor_version="policy-v2")),)),
        _build(
            paired_inputs=(
                _pair(
                    1,
                    legacy_fact=_legacy(record_time="legacy time"),
                    mapping=_mapping(
                        record_time_handling="mapped",
                        mapped_record_time=mapped_time,
                    ),
                ),
            )
        ),
    ]
    assert all(bundle.fingerprint() != baseline.fingerprint() for bundle in changes)

    non_identity = [
        _build(
            paired_inputs=(
                _pair(
                    1,
                    legacy_fact=_legacy(
                        source_document_id="document-ref-1",
                        quote="different quote",
                    ),
                ),
            )
        ),
        _build(
            paired_inputs=(
                _pair(
                    1,
                    legacy_fact=_legacy(
                        source_document_id="document-ref-1",
                        confidence=0.5,
                    ),
                ),
            )
        ),
        _build(paired_inputs=(_pair(1),), created_at="2026-07-12T10:00:00+08:00"),
    ]
    assert all(bundle.fingerprint() == baseline.fingerprint() for bundle in non_identity)


@pytest.mark.unit
def test_bundle_direct_construction_revalidates_and_derives_fact_count() -> None:
    built = _build(paired_inputs=(_pair(1), _pair(2)))
    direct = FactShadowBundle(
        bundle_schema_version=built.bundle_schema_version,
        visit_ref=built.visit_ref,
        manifest_fingerprint=built.manifest_fingerprint,
        source_snapshot_hash=built.source_snapshot_hash,
        items=tuple(reversed(built.items)),
        created_at=built.created_at,
    )
    assert direct.items == built.items
    assert direct.fact_count == 2
    with pytest.raises(TypeError):
        FactShadowBundle(  # type: ignore[call-arg]
            bundle_schema_version="1.0",
            visit_ref="visit-ref-001",
            manifest_fingerprint="a" * 64,
            source_snapshot_hash="b" * 64,
            items=(),
            fact_count=999,
            created_at=CREATED_AT,
        )


@pytest.mark.unit
def test_bundle_direct_construction_rejects_duplicate_pair_and_fact_identity() -> None:
    built = _build(paired_inputs=(_pair(1), _pair(2)))
    first, second = built.items
    duplicate_pair = FactShadowBundleItem(
        pair_ref=first.pair_ref,
        fact=second.fact,
    )
    duplicate_fact = FactShadowBundleItem(
        pair_ref=_pair_ref(99),
        fact=first.fact,
    )
    for items in ((first, duplicate_pair), (first, duplicate_fact)):
        with pytest.raises(ValueError):
            FactShadowBundle(
                bundle_schema_version=built.bundle_schema_version,
                visit_ref=built.visit_ref,
                manifest_fingerprint=built.manifest_fingerprint,
                source_snapshot_hash=built.source_snapshot_hash,
                items=items,
                created_at=built.created_at,
            )


@pytest.mark.unit
def test_bundle_direct_construction_bounds_item_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.luxian_0609.shadow_fact_bundle as bundle_module

    built = _build(paired_inputs=(_pair(1), _pair(2), _pair(3)))
    monkeypatch.setattr(bundle_module, "MAX_SHADOW_FACTS", 2)
    consumed = 0

    def items():
        nonlocal consumed
        for item in built.items:
            consumed += 1
            yield item

    with pytest.raises(ValueError):
        FactShadowBundle(
            bundle_schema_version=built.bundle_schema_version,
            visit_ref=built.visit_ref,
            manifest_fingerprint=built.manifest_fingerprint,
            source_snapshot_hash=built.source_snapshot_hash,
            items=items(),  # type: ignore[arg-type]
            created_at=built.created_at,
        )
    assert consumed == 3


@pytest.mark.unit
def test_bundle_direct_construction_enforces_item_visit_and_snapshot_relationship() -> None:
    built = _build(paired_inputs=(_pair(1),))
    with pytest.raises(ValueError):
        replace(built, visit_ref="different-visit")
    with pytest.raises(ValueError):
        replace(built, source_snapshot_hash=SNAPSHOT_B)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bundle_schema_version", "bad schema"),
        ("visit_ref", ""),
        ("manifest_fingerprint", "short"),
        ("source_snapshot_hash", "G" * 64),
        ("created_at", "not-a-time"),
    ],
)
def test_bundle_direct_construction_cannot_bypass_grammar(field: str, value: str) -> None:
    built = _build()
    with pytest.raises(ValueError):
        replace(built, **{field: value})


@pytest.mark.unit
def test_bundle_to_dict_is_defensive_and_json_excludes_legacy_private_material() -> None:
    patient_name = "person-" + "alpha"
    credential = "Author" + "ization: Basic hidden-token"
    raw_time = "untrusted raw time"
    bundle = _build(
        paired_inputs=(
            _pair(
                1,
                legacy_fact=_legacy(
                    record_time=raw_time,
                    quote=f"{patient_name}手术记录",
                    trace={
                        "patient_name": patient_name,
                        "prompt": "complete prompt",
                        "response": "complete response",
                        "status": "non_compliant",
                        "credential": credential,
                    },
                ),
                mapping=_mapping(
                    record_time_handling="omitted_untrusted",
                    omit_reason_code="UNTRUSTED_FORMAT",
                ),
            ),
        ),
        redaction_terms=[patient_name],
    )
    original_json = bundle.canonical_json()
    exported = bundle.to_dict()
    exported["items"][0]["fact"]["normalized_value"]["present"] = False
    exported["items"].append({"pair_ref": "x", "fact": {}})
    assert bundle.canonical_json() == original_json
    for forbidden in (
        patient_name,
        "complete prompt",
        "complete response",
        "non_compliant",
        "hidden-token",
        raw_time,
        "UNTRUSTED_FORMAT",
        "redaction_terms",
        "trace",
    ):
        assert forbidden not in original_json


@pytest.mark.unit
def test_bundle_module_has_no_mutable_global_or_runtime_side_effect_dependency() -> None:
    module_path = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609"
        / "shadow_fact_bundle.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    )
    assert imported.isdisjoint({"os", "sqlalchemy", "httpx", "requests", "openai", "socket"})
    mutable_globals = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(getattr(node, "value", None), (ast.Dict, ast.List, ast.Set))
    ]
    assert mutable_globals == []
