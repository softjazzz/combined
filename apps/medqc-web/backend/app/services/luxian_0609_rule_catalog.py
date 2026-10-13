from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .luxian_0609_rule_master import load_luxian_0609_rule_master


LUXIAN_0609_RULE_SET_KEY = "luxian_0609_qc_v1"
LUXIAN_0609_RULE_SET_NAME = "泸县0609质控点验证 v1"

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "luxian_0609_rules_v1.json"
_PHASE1_EXTENSION_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "luxian_0609_phase1_rules_extension_v1.json"
)


_ENGINE_JUDGMENT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "luxian_0609_engine_judgment_v1.json"
)
# 判定方式按规则合同 decision_authority 生成，避免说明文字与执行合同脱节。
_ENGINE_METHOD_LABELS = {
    "program_only": "程序判定：按结构化数据、时间和文书存在性直接计算，不调用模型。",
    "program_then_optional_llm": (
        "程序为主、模型辅助：模型只从病历正文抽取事实并给出原文引文，"
        "程序逐字核验引文后按规则下结论；模型不直接给出合规或不合规。"
    ),
}


@lru_cache(maxsize=1)
def load_luxian_0609_engine_judgment() -> dict[str, Any]:
    """加载质控规则页展示用的引擎判定说明（每条客户交付规则一项）。"""
    with _ENGINE_JUDGMENT_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if payload.get("schema_version") != "lx0609-engine-judgment-v1":
        raise ValueError("unsupported LX0609 engine judgment schema")
    return payload


def build_luxian_0609_engine_judgment(
    rule_id: str, *, decision_authority: str, pending_note: str = "",
) -> dict[str, Any] | None:
    payload = load_luxian_0609_engine_judgment()
    entry = (payload.get("rules") or {}).get(rule_id)
    if not isinstance(entry, dict):
        return None
    if entry.get("excluded"):
        return {"withheld": True, "withheld_reason": "本质控点不在本次客户交付范围，不参与正式判定。"}
    if entry.get("withheld"):
        return {"withheld": True, "withheld_reason": pending_note or "本质控点暂不执行。"}
    common = payload.get("common") or {}
    return {
        "withheld": False,
        "method": _ENGINE_METHOD_LABELS.get(decision_authority, ""),
        "trigger": str(entry.get("trigger") or ""),
        "steps": [str(item) for item in entry.get("steps") or []],
        "outcomes": {str(key): str(value) for key, value in (entry.get("outcomes") or {}).items()},
        "extra_notes": [str(item) for item in entry.get("extra_notes") or []],
        "data_gap_note": str(common.get("data_gap") or ""),
    }


@lru_cache(maxsize=1)
def load_luxian_0609_rules() -> list[dict[str, Any]]:
    """Load the customer-facing Luxian 0609 rule wrappers.

    这些对象是 LX0609 独立包的客户规则目录。执行方式由 native_package 清单
    决定；mapped_rule_ids 仅是尚未迁移规则的包内兼容依赖。
    """
    with _DATA_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("luxian_0609_rules_v1.json must contain a list")
    with _PHASE1_EXTENSION_PATH.open("r", encoding="utf-8") as file:
        extension = json.load(file)
    if not isinstance(extension, list):
        raise ValueError("LX0609 phase-1 extension must contain a list")
    wrappers = [
        dict(item)
        for item in (*payload, *extension)
        if isinstance(item, dict)
    ]
    wrappers_by_id: dict[str, dict[str, Any]] = {}
    for wrapper in wrappers:
        rule_id = str(wrapper.get("rule_id") or "").strip().upper()
        if not rule_id or rule_id in wrappers_by_id:
            raise ValueError("LX0609 execution catalog contains an invalid or duplicate rule ID")
        # 通用API保留同值rule_code字段，不允许形成另一套规则身份。
        if str(wrapper.get("rule_code") or rule_id).strip().upper() != rule_id:
            raise ValueError("LX0609 execution catalog contains conflicting rule identities")
        wrappers_by_id[rule_id] = wrapper

    # 业务范围由唯一总表决定；执行目录只能投影总表中已启用的规则。
    active_rule_ids = tuple(
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
    if set(wrappers_by_id) != set(active_rule_ids):
        raise ValueError("LX0609 execution catalog drifted from the canonical rule master")
    return [dict(wrappers_by_id[rule_id]) for rule_id in active_rule_ids]


def get_luxian_0609_rule(rule_id: str) -> dict[str, Any] | None:
    """Return a single Luxian 0609 wrapper rule by its customer-facing ID."""
    normalized_rule_id = str(rule_id or "").strip().upper()
    if not normalized_rule_id:
        return None
    for rule in load_luxian_0609_rules():
        candidate_id = str(rule.get("rule_id") or "").strip().upper()
        if candidate_id == normalized_rule_id:
            return dict(rule)
    return None


def attach_luxian_0609_customer_policy(
    wrappers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach the master-owned customer policy for rule-detail presentation.

    执行包装器仍是运行期映射的唯一所有者；这里仅为规则详情投影总表中的
    客户口径，不覆盖包装器任何已有字段。
    """
    master_by_id = {
        entry.rule_id: entry
        for entry in load_luxian_0609_rule_master()
    }
    from .luxian_0609.rule_contracts import load_luxian_0609_rule_contracts

    authority_by_id = {
        contract.rule_id: contract.decision_authority
        for contract in load_luxian_0609_rule_contracts()
    }
    projected: list[dict[str, Any]] = []
    for wrapper in wrappers:
        copied_wrapper = dict(wrapper)
        rule_id = str(
            copied_wrapper.get("rule_id") or copied_wrapper.get("rule_code") or ""
        ).strip().upper()
        master_entry = master_by_id.get(rule_id)
        if master_entry is None:
            raise ValueError(f"LX0609 customer policy is missing for {rule_id or '<blank>'}")
        copied_wrapper["release_scope"] = master_entry.release_scope
        copied_wrapper["phase_status"] = master_entry.phase_status
        copied_wrapper["pending_reason_code"] = master_entry.pending_reason_code
        copied_wrapper["pending_definition_note"] = master_entry.pending_definition_note
        copied_wrapper["customer_policy"] = {
            "source_document": master_entry.source_document,
            "qc_point": master_entry.qc_point,
            "summary": master_entry.policy_summary,
            "sources": list(master_entry.policy_sources),
        }
        engine_judgment = build_luxian_0609_engine_judgment(
            rule_id,
            decision_authority=authority_by_id.get(rule_id, ""),
            pending_note=master_entry.pending_definition_note,
        )
        if engine_judgment is not None:
            copied_wrapper["engine_judgment"] = engine_judgment
        projected.append(copied_wrapper)
    return projected


def filter_luxian_0609_rules_by_documents(
    rules: list[dict[str, Any]],
    *,
    wanted_docs: set[str],
) -> list[dict[str, Any]]:
    if not wanted_docs:
        return list(rules)

    normalized_wanted = {str(item).strip() for item in wanted_docs if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for rule in rules:
        docs = {str(item).strip() for item in (rule.get("applicable_documents") or [])}
        doc_labels = {str(item).strip() for item in (rule.get("applicable_document_labels") or [])}
        if docs.intersection(normalized_wanted) or doc_labels.intersection(normalized_wanted):
            filtered.append(rule)
    return filtered
