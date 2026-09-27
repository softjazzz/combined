"""泸县 0609 客户质控点及正式发布阶段的唯一业务总表。

总表描述客户确认的完整规则范围。``implementation_status`` 只表示目录注册
状态；``phase_status`` 表示是否参与本版本的正式结论。下游 ``phase_scope``
只能由本表投影，禁止再维护第二份规则编号或暂停规则清单。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


LUXIAN_0609_RULE_MASTER_SCHEMA_VERSION = "lx0609-rule-master-v2"
LUXIAN_0609_RULE_MASTER_VERSION = "2026-09-22-identity-v1"
LUXIAN_0609_RULE_DEFINITION_VERSION = "lx0609-defined-scope-2026-09-22-identity-v1"

_MASTER_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "luxian_0609_rule_master_v1.json"
)
_IMPLEMENTATION_STATUSES = frozenset(
    {"active", "contract_ready", "pending_definition"}
)
_PHASE_STATUSES = frozenset(
    {"phase_1_target", "phase_1_partial", "pending_definition"}
)
_POLICY_SOURCE_ORDER = (
    "sichuan_2026_handbook",
    "sichuan_2023_standard",
    "customer_confirmed",
    "hospital_local_extension",
)
_POLICY_SOURCE_CODES = frozenset(_POLICY_SOURCE_ORDER)
_MAX_POLICY_TEXT_LENGTH = 240
_RULE_ID_PATTERN = re.compile(r"^LX0609-(?!00)\d{2}-(?!00)\d{2}-(?!00)\d{2}$")


def _clean(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class Luxian0609RuleMasterEntry:
    rule_id: str
    source_document: str
    qc_point: str
    implementation_status: str
    definition_note: str = ""
    policy_sources: tuple[str, ...] = ()
    policy_summary: str = ""
    pending_definition_note: str = ""
    phase_status: str = "phase_1_target"
    active_criteria: tuple[str, ...] = ()
    pending_criteria: tuple[str, ...] = ()
    pending_reason_code: str = ""
    release_scope: str = "default"

    def __post_init__(self) -> None:
        if not _RULE_ID_PATTERN.fullmatch(self.rule_id):
            raise ValueError("invalid LX0609 rule identity")
        if self.implementation_status not in _IMPLEMENTATION_STATUSES:
            raise ValueError(f"invalid LX0609 implementation status: {self.rule_id}")
        if not self.source_document or not self.qc_point:
            raise ValueError(f"LX0609 master entry is incomplete: {self.rule_id}")
        if self.implementation_status == "active" and self.definition_note:
            raise ValueError(f"active LX0609 rule cannot contain a pending note: {self.rule_id}")
        if self.implementation_status != "active" and not self.definition_note:
            raise ValueError(f"inactive LX0609 rule must explain its status: {self.rule_id}")

        if self.release_scope not in {"default", "acceptance_only"}:
            raise ValueError(f"invalid LX0609 release scope: {self.rule_id}")
        if self.release_scope == "acceptance_only" and (
            self.implementation_status != "active" or self.phase_status != "phase_1_target"
        ):
            raise ValueError(f"acceptance-only rule must be an active phase target: {self.rule_id}")
        if self.phase_status not in _PHASE_STATUSES:
            raise ValueError(f"invalid LX0609 phase status: {self.rule_id}")
        if (
            self.phase_status == "phase_1_target"
            and self.implementation_status != "active"
        ):
            raise ValueError(
                f"phase target must be catalog registered: {self.rule_id}"
            )
        if self.phase_status == "phase_1_target":
            if self.pending_criteria or self.pending_reason_code:
                raise ValueError(
                    f"phase target cannot contain pending definition: {self.rule_id}"
                )
        elif self.phase_status == "phase_1_partial":
            if (
                not self.active_criteria
                or not self.pending_criteria
                or self.pending_reason_code
            ):
                raise ValueError(
                    f"partial phase rule must split active and pending criteria: {self.rule_id}"
                )
        elif self.active_criteria or self.pending_criteria or not self.pending_reason_code:
            raise ValueError(
                f"pending phase rule must declare one reason: {self.rule_id}"
            )

        if not isinstance(self.policy_sources, tuple):
            raise ValueError(f"LX0609 policy sources must be a tuple: {self.rule_id}")
        policy_sources = tuple(_clean(source) for source in self.policy_sources)
        if not policy_sources:
            raise ValueError(f"LX0609 policy sources cannot be empty: {self.rule_id}")
        if len(set(policy_sources)) != len(policy_sources):
            raise ValueError(f"LX0609 policy sources cannot contain duplicates: {self.rule_id}")
        unknown_sources = set(policy_sources) - _POLICY_SOURCE_CODES
        if unknown_sources:
            raise ValueError(f"LX0609 unknown policy source: {self.rule_id}")
        canonical_sources = tuple(
            source for source in _POLICY_SOURCE_ORDER if source in policy_sources
        )
        if policy_sources != canonical_sources:
            raise ValueError(f"LX0609 policy sources must use stable order: {self.rule_id}")
        object.__setattr__(self, "policy_sources", policy_sources)

        policy_summary = _clean(self.policy_summary)
        if not policy_summary or len(policy_summary) > _MAX_POLICY_TEXT_LENGTH:
            raise ValueError(f"LX0609 policy summary is invalid: {self.rule_id}")
        object.__setattr__(self, "policy_summary", policy_summary)

        pending_definition_note = _clean(self.pending_definition_note)
        if len(pending_definition_note) > _MAX_POLICY_TEXT_LENGTH:
            raise ValueError(
                f"LX0609 pending definition note is too long: {self.rule_id}"
            )
        object.__setattr__(self, "pending_definition_note", pending_definition_note)
        object.__setattr__(
            self,
            "active_criteria",
            tuple(_clean(item) for item in self.active_criteria if _clean(item)),
        )
        object.__setattr__(
            self,
            "pending_criteria",
            tuple(_clean(item) for item in self.pending_criteria if _clean(item)),
        )
        object.__setattr__(self, "pending_reason_code", _clean(self.pending_reason_code))

    @property
    def title(self) -> str:
        return f"{self.source_document}：{self.qc_point}"


def compile_luxian_0609_rule_master(
    payload: Mapping[str, Any],
) -> tuple[Luxian0609RuleMasterEntry, ...]:
    if _clean(payload.get("schema_version")) != LUXIAN_0609_RULE_MASTER_SCHEMA_VERSION:
        raise ValueError("unsupported LX0609 rule master schema")
    if _clean(payload.get("master_version")) != LUXIAN_0609_RULE_MASTER_VERSION:
        raise ValueError("unsupported LX0609 rule master version")
    if _clean(payload.get("definition_version")) != LUXIAN_0609_RULE_DEFINITION_VERSION:
        raise ValueError("unsupported LX0609 rule definition version")

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("LX0609 rule master must contain a rules list")

    entries: list[Luxian0609RuleMasterEntry] = []
    for raw in raw_rules:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid LX0609 rule master entry")
        raw_policy_sources = raw.get("policy_sources")
        if not isinstance(raw_policy_sources, list):
            raise ValueError("LX0609 rule master policy sources must be a list")
        entries.append(
            Luxian0609RuleMasterEntry(
                rule_id=_clean(raw.get("rule_id")).upper(),
                source_document=_clean(raw.get("source_document")),
                qc_point=_clean(raw.get("qc_point")),
                implementation_status=_clean(raw.get("implementation_status")),
                release_scope=_clean(raw.get("release_scope", "default")),
                definition_note=_clean(raw.get("definition_note")),
                policy_sources=tuple(raw_policy_sources),
                policy_summary=_clean(raw.get("policy_summary")),
                pending_definition_note=_clean(raw.get("pending_definition_note")),
                phase_status=_clean(raw.get("phase_status")) or "phase_1_target",
                active_criteria=tuple(
                    _clean(item)
                    for item in (raw.get("active_criteria") or ())
                    if _clean(item)
                ),
                pending_criteria=tuple(
                    _clean(item)
                    for item in (raw.get("pending_criteria") or ())
                    if _clean(item)
                ),
                pending_reason_code=_clean(raw.get("pending_reason_code")),
            )
        )

    if not entries:
        raise ValueError("LX0609 rule master must contain at least one rule")
    actual_ids = tuple(entry.rule_id for entry in entries)
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("LX0609 rule master must contain unique rule IDs")
    return tuple(entries)


@lru_cache(maxsize=1)
def load_luxian_0609_rule_master() -> tuple[Luxian0609RuleMasterEntry, ...]:
    with _MASTER_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, Mapping):
        raise ValueError("LX0609 rule master must be an object")
    return compile_luxian_0609_rule_master(payload)


def get_luxian_0609_rule_master_entry(
    rule_id: str,
) -> Luxian0609RuleMasterEntry | None:
    normalized_rule_id = _clean(rule_id).upper()
    return next(
        (
            entry
            for entry in load_luxian_0609_rule_master()
            if entry.rule_id == normalized_rule_id
        ),
        None,
    )


def get_luxian_0609_rule_master_summary() -> dict[str, int]:
    entries = load_luxian_0609_rule_master()
    return {
        "total": len(entries),
        **{
            status: sum(entry.implementation_status == status for entry in entries)
            for status in sorted(_IMPLEMENTATION_STATUSES)
        },
    }
