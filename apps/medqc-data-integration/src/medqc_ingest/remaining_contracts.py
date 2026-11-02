"""剩余25接口的冻结候选合同；不扩大生产注册表或自动增量范围。

本模块只读非PHI元数据。ready仅代表结构候选可执行，实际发布仍必须通过
非空样本、源键唯一、整批目标主键无碰撞以及实际catalog等运行时闸门。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from medqc_ingest.domain import (
    ErrorKind,
    FieldMapping,
    IngestError,
    InterfaceSpec,
    PublishSpec,
    canonical_json,
    project_record,
    schema_signature,
    sha256_hex,
)

PROFILE = "remaining-explicit-validation-v1"
CONTRACT_SHA256 = "b59114b424b9e905dafcc4fa32cd45057aecd734ae4da396911cb3ee940ba9d3"
REMAINING_NAMES = frozenset(
    {
        "web.mr_cost",
        "web.medical_insurance_settlement_cost",
        "web.mr_icu",
        "web.medical_insurance_settlement",
        "web.inpat_bill_item",
        "web.pathology_exam_master",
        "web.pathology_exam_report",
        "web.mr_customize",
        "web.diagnosis",
        "web.epidemic_record",
        "web.outpat_record",
        "web.docpat_commu_record",
        "web.handoff_record",
        "web.handover_record",
        "web.diffcase_discussion_record",
        "web.death_discussion",
        "web.death_record",
        "web.daily_admission_record",
        "web.daily_death_record",
        "web.summary_record",
        "web.rescue_record",
        "web.crisis_value_record",
        "web.newborn_record",
        "web.transfer_out_record",
        "web.transfer_in_record",
    }
)
VENDOR_BLOCKED = frozenset({"web.medical_insurance_settlement", "web.inpat_bill_item"})


def _require(condition: bool, location: str) -> None:
    if not condition:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, location)


def default_contract_path() -> Path:
    development = (
        Path(__file__).resolve().parents[2] / "contracts" / ("remaining-interface-contracts.json")
    )
    return (
        development
        if development.is_file()
        else Path(__file__).parent / "control" / "contracts" / "remaining-interface-contracts.json"
    )


def _read_contract(path: Path | None) -> dict[str, Any]:
    try:
        content = (path or default_contract_path()).read_bytes()
        _require(
            hashlib.sha256(content).hexdigest() == CONTRACT_SHA256,
            "remaining_frozen_contract_hash",
        )
        value: dict[str, Any] = json.loads(content)
    except IngestError:
        raise
    except (OSError, ValueError, TypeError):
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "remaining_contract_read") from None
    _require(
        value.get("contract_version") == "remaining-interface-contracts-v1"
        and value.get("scope", {}).get("remaining") == 25
        and value.get("required_alembic_revision") == "20261101_000058",
        "remaining_contract_version",
    )
    items = value.get("interfaces", [])
    _require(
        len(items) == 25 and {item["interface"] for item in items} == REMAINING_NAMES,
        "remaining_contract_scope",
    )
    return value


def load_profile(path: Path | None = None) -> tuple[dict[str, Any], dict[str, InterfaceSpec]]:
    """返回25项证据及23个候选spec；无schema的两项只可做源端探查快照。"""
    contract = _read_contract(path)
    specs: dict[str, InterfaceSpec] = {}
    for item in contract["interfaces"]:
        name = item["interface"]
        if name in VENDOR_BLOCKED:
            _require(
                not item["ready"]
                and item["status"] == "vendor_blocked"
                and not item["source_columns"]
                and not item["raw_key_fields"],
                "remaining_vendor_blocked_contract",
            )
            continue
        columns = tuple(item["source_columns"])
        key_fields = tuple(item["raw_key_fields"])
        mappings = tuple(
            FieldMapping(m["source"], m["target"], m["target_type"]) for m in item["mappings"]
        )
        primary_key = tuple(item["target_primary_key"])
        targets = {m.target for m in mappings}
        _require(
            item["ready"] is True
            and item["status"] == "candidate_ready"
            and not item["block_reasons"]
            and item["argument_count"] in (1, 2)
            and columns == tuple(item["ordered_source_columns"])
            and len(columns) == len(set(columns))
            and schema_signature(columns)[0] == item["schema_hash"]
            and set(key_fields) <= set(columns)
            and {"institute_id", "patient_id", "visit_id"} <= set(key_fields)
            and bool(primary_key)
            and set(primary_key) <= targets
            and len(mappings) == len(targets)
            and all(m.source in columns for m in mappings)
            and all(m.target_type in {"text", "date", "datetime"} for m in mappings)
            and not item["derived_document_id"]
            and item["publish_target"] == "cdm." + name[4:],
            "remaining_candidate_contract",
        )
        publish = PublishSpec(
            "cdm",
            name[4:],
            primary_key,
            tuple(item["required_target_columns"]),
            mappings,
        )
        specs[name] = InterfaceSpec(
            name,
            name,
            item["argument_count"],
            key_fields,
            item["publish_target"],
            columns,
            PROFILE + ";contract:" + sha256_hex(canonical_json(item)),
            publish,
        )
    return contract, specs


def get_contracts(path: Path | None = None) -> list[dict[str, Any]]:
    """每次读取返回独立字典，调用方不能污染后续合同或全局注册表。"""
    contract, _ = load_profile(path)
    return list(contract["interfaces"])


def select_spec(specs: Mapping[str, InterfaceSpec], name: str) -> InterfaceSpec:
    if name not in REMAINING_NAMES or name not in specs or name in VENDOR_BLOCKED:
        raise IngestError(ErrorKind.INTERFACE, "remaining_disabled_or_unknown")
    return specs[name]


def validate_target_keys(
    spec: InterfaceSpec,
    payloads: Iterable[Mapping[str, Any]],
    completed_at: datetime,
) -> int:
    """跨块、跨日整批检查源键和目标键；正文相同也不允许覆盖两条源记录。

    调用方必须在任何CDM提交之前完成此闸门，或将投影与此检查放在同一
    可整体回滚的事务中。哈希只用于内存比较，错误不包含键值或正文。
    """
    publish = spec.publish
    _require(publish is not None, "remaining_publish_contract_missing")
    assert publish is not None
    sources: set[str] = set()
    targets: set[str] = set()
    count = 0
    for payload in payloads:
        projected = project_record(spec, payload, completed_at)
        source_key = sha256_hex(canonical_json([payload.get(k) for k in spec.key_fields]))
        target_key = sha256_hex(canonical_json([projected[k] for k in publish.primary_key]))
        if source_key in sources:
            raise IngestError(ErrorKind.KEY, "remaining_source_key_duplicate")
        if target_key in targets:
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "remaining_target_key_collision")
        sources.add(source_key)
        targets.add(target_key)
        count += 1
    return count
