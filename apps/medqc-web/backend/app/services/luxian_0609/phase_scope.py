"""LX0609 第一阶段的业务定义范围契约。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..luxian_0609_rule_master import (
    LUXIAN_0609_RULE_DEFINITION_VERSION,
    load_luxian_0609_rule_master,
)


_SCOPE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "luxian_0609_phase_scope_v1.json"
)
_SCHEMA_VERSION = "lx0609-phase-scope-v1"
_PHASE_STATUSES = frozenset(
    {"phase_1_target", "phase_1_partial", "pending_definition"}
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class Luxian0609PhaseScopeEntry:
    rule_id: str
    phase_status: str
    catalog_registered: bool
    definition_version: str
    active_criteria: tuple[str, ...] = ()
    pending_criteria: tuple[str, ...] = ()
    pending_reason_code: str = ""

    def __post_init__(self) -> None:
        if self.phase_status not in _PHASE_STATUSES:
            raise ValueError("invalid LX0609 phase status")
        if self.phase_status == "phase_1_target":
            if self.pending_criteria or self.pending_reason_code:
                raise ValueError("phase target cannot contain pending definition")
        elif self.phase_status == "phase_1_partial":
            if (
                not self.active_criteria
                or not self.pending_criteria
                or self.pending_reason_code
            ):
                raise ValueError("partial phase rule must split active and pending criteria")
        elif (
            self.active_criteria
            or self.pending_criteria
            or not self.pending_reason_code
        ):
            raise ValueError("pending phase rule must declare one reason")


def compile_luxian_0609_phase_scope(
    payload: Mapping[str, Any],
) -> tuple[Luxian0609PhaseScopeEntry, ...]:
    if _clean(payload.get("schema_version")) != _SCHEMA_VERSION:
        raise ValueError("unsupported LX0609 phase scope schema")
    definition_version = _clean(payload.get("definition_version"))
    raw_rules = payload.get("rules")
    if (
        definition_version != LUXIAN_0609_RULE_DEFINITION_VERSION
        or not isinstance(raw_rules, list)
    ):
        raise ValueError("invalid LX0609 phase scope payload")

    entries: list[Luxian0609PhaseScopeEntry] = []
    for raw in raw_rules:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid LX0609 phase scope entry")
        entries.append(
            Luxian0609PhaseScopeEntry(
                rule_id=_clean(raw.get("rule_id")).upper(),
                phase_status=_clean(raw.get("phase_status")),
                catalog_registered=raw.get("catalog_registered") is True,
                definition_version=definition_version,
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

    actual_ids = tuple(entry.rule_id for entry in entries)
    master_entries = load_luxian_0609_rule_master()
    master_ids = tuple(entry.rule_id for entry in master_entries)
    if actual_ids != master_ids:
        raise ValueError("LX0609 phase scope rule IDs must exactly match rule master")
    registered_ids = {
        entry.rule_id
        for entry in master_entries
        if entry.implementation_status == "active"
    }
    if any(
        entry.catalog_registered != (entry.rule_id in registered_ids)
        for entry in entries
    ):
        raise ValueError("LX0609 phase scope catalog registration drift")
    if any(
        entry.phase_status == "phase_1_target" and not entry.catalog_registered
        for entry in entries
    ):
        raise ValueError("LX0609 phase target must be catalog registered")
    return tuple(entries)


@lru_cache(maxsize=1)
def load_luxian_0609_phase_scope() -> tuple[Luxian0609PhaseScopeEntry, ...]:
    with _SCOPE_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, Mapping):
        raise ValueError("LX0609 phase scope must be an object")
    return compile_luxian_0609_phase_scope(payload)


def get_luxian_0609_phase_scope(rule_id: str) -> Luxian0609PhaseScopeEntry | None:
    normalized = _clean(rule_id).upper()
    return next(
        (entry for entry in load_luxian_0609_phase_scope() if entry.rule_id == normalized),
        None,
    )


def partition_luxian_0609_rule_scope(
    selected_rule_ids: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """按权威目录顺序拆分正式可执行规则与其余失败关闭规则。"""

    requested = {
        _clean(rule_id).upper() for rule_id in selected_rule_ids if _clean(rule_id)
    }
    entries = load_luxian_0609_phase_scope()
    known_rule_ids = {entry.rule_id for entry in entries}
    if requested.difference(known_rule_ids):
        raise ValueError("invalid LX0609 customer rule id")
    executable = tuple(
        entry.rule_id
        for entry in entries
        if entry.rule_id in requested and entry.phase_status == "phase_1_target"
    )
    withheld = tuple(
        entry.rule_id
        for entry in entries
        if entry.rule_id in requested and entry.phase_status != "phase_1_target"
    )
    return executable, withheld
