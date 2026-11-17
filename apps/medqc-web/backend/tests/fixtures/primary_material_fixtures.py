"""四类只读材料链的全合成夹具；不表示真实准入批准，不调用同步构造器。"""
from dataclasses import asdict
import json


def policy(m=None):
    if m is None:
        from app.services import primary_material_readonly as m
    return m.PrimaryPolicy.from_dict({
        "canonical_case": ["i", "p", "v"],
        "native_cases": [["cache", "i", "p", "v"], ["clinical", "i", "p", "v"]],
        "approval_id": "synthetic-only", "mapping_version": "test-v1",
        "approved_types": list(m.KINDS), "shared_document_ids": list(m.KINDS),
        "status_rules": [["cache", None, "USABLE"], ["clinical", None, "USABLE"]],
        "lifecycle_null_approved": True,
    })



def synthetic_material(m, kind, source="clinical", *, body="合成正文", document_id="doc-1",
                       contracts=None, generation=1, lifecycle_values=None):
    """供四类材料链联验复用的合成 DTO；不作为真实批准或同步构造器。"""
    contract = (contracts if contracts is not None else m.real_contracts())[kind]
    spec = contract.spec if source == "clinical" else m.cache_spec(kind)
    key = ["i", "p", "v", document_id]
    payload = dict.fromkeys(spec.publish.target_columns)
    payload.update(zip(m.KEYS, key))
    payload["document_title"] = "合成" + kind
    payload["surgery_process" if kind == "surgery_record" else "record_content"] = body
    publication = {
        "source_namespace": source, "interface": spec.name,
        "source_key_hash": m.digest([spec.name, key]),
        "source_epoch": "00000000-0000-0000-0000-000000000001", "generation": generation,
        "mapping_hash": "synthetic-map", "activation": 1, "operation": "UPSERT",
        "spec_hash": m.digest(asdict(spec)),
    }
    identity = [source, spec.name, key]
    native = dict.fromkeys(contract.columns) if source == "clinical" else dict(payload)
    native.update({"institute_id": "i", "patient_id": "p", "visit_id": "v", "document_id": document_id})
    if source == "clinical":
        native.update(record_status=None, is_deleted="0")
        for target, column in contract.mappings:
            if column is not None:
                native[column] = payload[target]
        native.update(lifecycle_values or {})
        payload["source_payload"] = m.canonical_json({
            "columns": list(contract.columns), "values": [native[name] for name in contract.columns],
        })
    material = {
        "version_id": m.digest([identity, publication]), "record_identity": m.digest(identity),
        "source_namespace": source, "document_type": kind, "native_key": key,
        "body": body, "title": payload["document_title"],
        "times": dict.fromkeys(("record_time", "submit_time", "modified_time", "surgery_begin_time", "surgery_end_time")),
        "time_availability": dict.fromkeys(("record_time", "submit_time", "modified_time", "surgery_begin_time", "surgery_end_time"), "MISSING"),
        "source_status": None, "record_status": None, "raw_fields": dict(payload),
        "native_fields": native, "target_payload": payload, "publication": publication,
    }
    if source == "clinical":
        metadata = m.metadata_document()["tables"][kind]
        source_times = {
            column["name"]: {
                "value": native[column["name"]], "pg_type": column["formatted_type"],
                "comment": column["comment"],
                "role_evidence": "COMMENT_CONFIRMED" if column["comment"] else "UNCONFIRMED",
                "business_semantics_approved": False,
            }
            for column in metadata["columns"]
            if column["formatted_type"].startswith(("timestamp", "date"))
        }
        material.update(source_metadata_revision=m.METADATA_REVISION,
                        source_metadata_sha256=m.METADATA_SHA256,
                        native_primary_key={"institute_id": "i", "document_id": document_id},
                        source_times=source_times, time_role_status=dict.fromkeys(material["times"], "UNCONFIRMED"),
                        lifecycle_admission={"field": "is_deleted", "raw_value": "0", "action": "USABLE", "evidence": "synthetic-only"})
        if getattr(contract, "lifecycle_mode", None) == "record-hold-v1":
            material.update(
                record_status=native["record_status"],
                lifecycle_admission=contract.lifecycle_admission(json.loads(payload["source_payload"])),
                source_lifecycle_revision="clinical-primary-record-lifecycle-v1",
            )
    return material



def selection_fixture():
    """返回 policy/contracts/selection/target_rows/receipts/coverage_rows，均为合成数据。"""
    from app.services import primary_material_readonly as m

    p = policy(m)
    contracts = m.real_contracts()
    materials = [synthetic_material(m, kind, source)
                 for kind in m.KINDS for source in ("clinical", "cache")]
    health = {kind: {"state": "READY", "coverage": "OBSERVED_PUBLISHED",
                     "clinical_absence_confirmed": False} for kind in m.KINDS}
    target_rows = []
    receipts = []
    for material in materials:
        kind = material["document_type"]
        spec = contracts[kind].spec if material["source_namespace"] == "clinical" else m.cache_spec(kind)
        target_rows.append({"spec": spec, "row": material["target_payload"], "material": material})
        ref = material["publication"]
        receipts.append({
            "interface_name": ref["interface"], "source_key_hash": ref["source_key_hash"],
            "source_epoch": ref["source_epoch"], "generation": ref["generation"],
            "mapping_hash": ref["mapping_hash"], "activation": ref["activation"],
            "target_key_hash": m.digest(material["native_key"]),
        })
    coverage_rows = [{"case_id": p.health_case_id(kind), "source_namespace": "clinical",
                      "coverage_json": {"publication_health": {"state": "READY_FOR_INSPECTION"}}}
                     for kind in m.KINDS]
    return {"policy": p, "contracts": contracts,
            "selection": m.select_materials(p, materials, health),
            "target_rows": target_rows, "receipts": receipts, "coverage_rows": coverage_rows}


def lifecycle_fixture(*, held=True):
    """业务读取夹具：30份临床原文及关联/独立缓存，不执行同步构造器。"""
    from app.services import primary_material_readonly as m

    fixture = selection_fixture()
    contracts = m.contracts_for_mode("record-hold-v1", {
        kind: (("is_deleted", '"0"', "USABLE", "SYNTHETIC_ONLY"),) for kind in m.KINDS
    })
    materials = [synthetic_material(
        m, "daily_course_record", document_id=f"daily-{index:02d}", contracts=contracts,
        lifecycle_values={"record_status": "SYNTHETIC_HELD"} if held and index == 29 else {},
    ) for index in range(30)]
    materials.extend([
        synthetic_material(m, "daily_course_record", "cache", document_id="daily-29"),
        synthetic_material(m, "daily_course_record", "cache", document_id="cache-independent"),
        synthetic_material(m, "presurg_summary", "cache", document_id="other-kind-independent"),
    ])
    fixture["contracts"] = contracts
    fixture["selection"] = m.select_materials(fixture["policy"], materials, {
        kind: {"state": "READY", "coverage": "OBSERVED_PUBLISHED",
               "clinical_absence_confirmed": False} for kind in m.KINDS
    })
    fixture["target_rows"] = [
        {"spec": contracts[kind].spec if source == "clinical" else m.cache_spec(kind)}
        for kind in m.KINDS for source in ("clinical", "cache")
    ]
    return fixture
