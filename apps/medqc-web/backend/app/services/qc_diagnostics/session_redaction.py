"""当次 provider 证据快照的统一脱敏与引用重建；不作临床重新判定。

只接收已冻结的正式 provider 资料，不接旧事实适配器。当前 provider 不产生
行级 source_document_id 或派生 extensions；遇到这些合同直接报不支持，
不能丢字段后冒充可回放。返回值仍是内部材料，未通过整包隐私/规则等价门禁。
"""
from __future__ import annotations

from types import MappingProxyType
from datetime import date, datetime
import re

from .contracts import DiagnosticPackageError
from .execution_inputs import freeze_execution_inputs
from .material_redaction import sanitize_material_sources
from .sanitization import PayloadSanitizer
from .session_restore import restore_execution_session
from .typed_values import encode_value
from .package import _json


class SessionRedaction:
    """旧→新引用仅在内存中可查，不能随诊断包序列化。"""

    __slots__ = ("inputs", "coordinates", "related_values", "_refs", "_materials")

    def __init__(self, *, inputs, coordinates, related_values, refs, materials):
        self.inputs = inputs
        self.coordinates = coordinates
        self.related_values = related_values
        self._refs = MappingProxyType(dict(refs))
        self._materials = materials

    def __repr__(self):
        return "SessionRedaction(internal_only=True)"

    def remap_reference(self, reference: str) -> str:
        if type(reference) is not str:
            raise DiagnosticPackageError("unresolved_execution_reference")
        if reference in self._refs:
            return self._refs[reference]
        return self._materials.remap_document_refs((reference,))[0]


def _reject_unmapped_related_refs(value, *, references, sanitizer, depth=0):
    if depth > 30:
        raise DiagnosticPackageError("redaction_depth_limit")
    if type(value) in (dict, MappingProxyType):
        for child in value.values():
            _reject_unmapped_related_refs(child, references=references, sanitizer=sanitizer, depth=depth + 1)
    elif type(value) in (tuple, list):
        for child in value:
            _reject_unmapped_related_refs(child, references=references, sanitizer=sanitizer, depth=depth + 1)
    elif type(value) is str:
        normalized = sanitizer._normalize(value)
        if normalized.lstrip().startswith(("{", "[")):
            parsed = _json(normalized.encode("utf-8"), 20000)[0]
            _reject_unmapped_related_refs(parsed, references=references, sanitizer=sanitizer, depth=depth + 1)
        if any(match[0].removeprefix("sha256:") in references
               for match in re.finditer(r"(?:sha256:)?[a-f0-9]{64}", normalized)):
            # 当前 related_values 只支持身份/日期文本；录制模型引用需由完整包
            # 投影处理，不能让普通文本转换静默保留或破坏旧执行引用。
            raise DiagnosticPackageError("related_execution_references_require_projection")


def _provider_value(value) -> bool:
    if type(value) is not dict or not value:
        return False
    boolean_fields = {"surgery_order", "present", "complete", "performed", "emergency_rescue"}
    if value.keys() <= boolean_fields:
        return len(value) == 1 and all(type(v) is bool for v in value.values())
    if not {"horizon_date", "basis"} <= value.keys() <= {"horizon_date", "horizon_datetime", "basis"}:
        return False
    try:
        return (value["basis"] in {"evaluation_as_of", "discharge_date"}
                and type(value["horizon_date"]) is str
                and date.fromisoformat(value["horizon_date"]).isoformat() == value["horizon_date"]
                and ("horizon_datetime" not in value or type(value["horizon_datetime"]) is str
                     and datetime.fromisoformat(value["horizon_datetime"]).isoformat() == value["horizon_datetime"]))
    except (ValueError, TypeError):
        return False


def sanitize_execution_inputs(inputs, *, coordinates: tuple[str, str, str],
                              sanitizer: PayloadSanitizer, related_values=()) -> SessionRedaction:
    """材料及附带文本同次 collect，保留事实状态、来源状态和行顺序。

    字段白名单由受信调用方固定，不从输入数据自动放行字段。不会重新生成
    provider 的事实，只改变匿名坐标、已转换的内容和由此派生的引用。
    """
    from ..luxian_0609.evidence_material import (
        Luxian0609EvidenceMaterialStore, Luxian0609EvidenceReadSession,
        build_material_document_refs, build_material_snapshot_ref,
    )
    from ..luxian_0609.evidence_snapshot import (
        Luxian0609EvidenceSnapshot, SourceObservation, build_luxian_0609_visit_ref,
    )
    from ..luxian_0609.fact_schema import FactV2, TimeValue

    original = restore_execution_session(inputs, coordinates=coordinates)
    snapshot = original.snapshot
    encode_value(related_values)
    old_references = {snapshot.snapshot_hash, snapshot.visit_ref.removeprefix("sha256:"),
                      *snapshot.document_refs, *(f.fact_id for f in snapshot.facts),
                      *(o.snapshot_ref.removeprefix("sha256:") for o in snapshot.observations)}
    _reject_unmapped_related_refs(related_values, references=old_references, sanitizer=sanitizer)
    if any(f.source_document_id or f.extensions for f in snapshot.facts):
        raise DiagnosticPackageError("unsupported_provider_fact_references")
    fact_payloads = tuple((
        fact.to_dict()["normalized_value"], fact.quote, fact.created_at,
        tuple(t.value if t is not None else None for t in (fact.record_time, fact.submit_time, fact.update_time)),
    ) for fact in snapshot.facts)
    # provider 的 normalized_value 只含布尔和 horizon 数据；拒绝扩展合同中
    # 嵌套引用，避免把旧引用当普通文本日期/号码转换后静默丢失其归属。
    if any(not _provider_value(payload[0]) for payload in fact_payloads):
        raise DiagnosticPackageError("unsupported_provider_fact_values")
    material = sanitize_material_sources(
        original.materials.diagnostic_sources(snapshot=snapshot), sanitizer=sanitizer,
        related_values=(dict(zip(("institute_id", "patient_id", "visit_id"), coordinates)),
                        snapshot.created_at, inputs["evaluation_as_of_date"], fact_payloads, related_values),
    )
    identity, created_at, as_of, cleaned_facts, cleaned_related = material.related_values
    new_coordinates = tuple(identity[key] for key in ("institute_id", "patient_id", "visit_id"))
    visit_ref = build_luxian_0609_visit_ref(**identity)
    observations = []
    refs = {snapshot.visit_ref: visit_ref}
    by_source = {}
    original_sources = original.materials.diagnostic_sources(snapshot=snapshot)
    for key, source in material.sources.items():
        for old_row, new_row in zip(original_sources[key].rows, source.rows):
            if type(old_row.get("row_ref")) is str and old_row["row_ref"]:
                refs[old_row["row_ref"]] = new_row["row_ref"]
    for observation in snapshot.observations:
        source = material.sources.get(observation.source_key)
        new_ref = build_material_snapshot_ref(
            source_key=observation.source_key, query_version=observation.query_version,
            query_state=observation.query_state, completeness=observation.completeness,
            document_refs=build_material_document_refs(observation.source_key, source.rows) if source else (),
        )
        rebuilt = SourceObservation.create(**{**observation.to_dict(), "snapshot_ref": new_ref})
        observations.append(rebuilt)
        by_source[observation.source_key] = rebuilt
        refs[observation.snapshot_ref] = new_ref
        refs[observation.snapshot_ref.removeprefix("sha256:")] = new_ref.removeprefix("sha256:")
    facts = []
    for old, (value, quote, fact_created_at, times) in zip(snapshot.facts, cleaned_facts):
        original_value = old.to_dict()["normalized_value"]
        if not _provider_value(value) or any(value.get(key) != val for key, val in original_value.items()
                                           if key not in {"horizon_date", "horizon_datetime"}):
            raise DiagnosticPackageError("redaction_changed_business_fact")
        parameters = {key: val for key, val in old.to_dict().items() if key != "fact_id"}
        parameters.update(visit_ref=visit_ref, normalized_value=value, quote=quote, created_at=fact_created_at,
                          source_snapshot_hash=by_source[old.source_key].snapshot_ref.removeprefix("sha256:"))
        for key, raw_time, shifted_time in zip(("record_time", "submit_time", "update_time"),
                                               (old.record_time, old.submit_time, old.update_time), times):
            parameters[key] = None if raw_time is None else TimeValue.create(**{**raw_time.to_dict(), "value": shifted_time})
        rebuilt = FactV2.create(**parameters, redaction_terms=(), known_upstream_fact_ids=())
        if rebuilt.quote != quote:
            raise DiagnosticPackageError("redacted_fact_quote_changed")
        facts.append(rebuilt)
        refs[old.fact_id] = rebuilt.fact_id
    new_snapshot = Luxian0609EvidenceSnapshot.create(
        **identity, snapshot_schema_version=snapshot.snapshot_schema_version,
        source_registry_version=snapshot.source_registry_version, observations=observations, facts=facts,
        document_refs=material.remap_document_refs(snapshot.document_refs), created_at=created_at,
    )
    refs[snapshot.snapshot_hash] = new_snapshot.snapshot_hash
    session = Luxian0609EvidenceReadSession(snapshot=new_snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(snapshot=new_snapshot, sources=material.sources))
    result = freeze_execution_inputs(session, selected_rule_ids=inputs["selected_rule_ids"],
        evaluation_as_of_date=as_of, evaluation_horizon_policy=inputs["evaluation_horizon_policy"],
        horizon_unavailable_reason=inputs["horizon_unavailable_reason"])
    restore_execution_session(result, coordinates=new_coordinates)
    return SessionRedaction(inputs=result, coordinates=new_coordinates, related_values=cleaned_related,
                            refs=refs, materials=material)
