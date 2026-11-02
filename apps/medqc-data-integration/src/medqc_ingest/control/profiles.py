"""固定两批来源的控制面目录；只读合同，不读取源或PG凭据。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from medqc_ingest.control.models import ControlError
from medqc_ingest.domain import INTERFACE_REGISTRY, IngestError, InterfaceSpec
from medqc_ingest.periop_replay import DISABLED, load_profile

MODES = frozenset({"dry", "replay", "incremental", "publish_only"})
_METADATA_KEYS = frozenset({"enabled", "ready", "incremental_interfaces", "scheduled_interfaces"})


@dataclass(frozen=True)
class Profile:
    profile_id: str
    specs: Mapping[str, InterfaceSpec]
    enabled: bool
    ready: bool
    incremental_interfaces: frozenset[str]
    scheduled_interfaces: frozenset[str]
    source_limits: frozenset[str]

    @property
    def interfaces(self) -> Mapping[str, InterfaceSpec]:
        return self.specs


class ProfileCatalog:
    def __init__(
        self, metadata: Mapping[str, Any] | None = None, contract_path: Path | None = None
    ) -> None:
        config = {} if metadata is None else metadata
        if not isinstance(config, Mapping) or set(config) - {"core13", "periop13"}:
            raise ControlError("invalid_profile_metadata", "catalog_scope")
        path = contract_path
        if path is None:
            path = (
                Path(__file__).resolve().parents[3] / "contracts/periop-acceptance-contracts.json"
            )
            if not path.is_file():
                path = (
                    Path(__file__).resolve().parent / "contracts/periop-acceptance-contracts.json"
                )
        try:
            contract, periop = load_profile(path)
        except (OSError, ValueError, IngestError):
            raise ControlError("configuration_error", "catalog_contract", 503) from None
        self._source_contracts: dict[str, dict[str, Any]] = {
            item["interface"]: item
            for item in contract["interfaces"]
            if item["interface"] in periop
        }
        self._profiles: dict[str, Profile] = {}
        for name, specs, ready, approved, limits in (
            ("core13", dict(INTERFACE_REGISTRY), True, frozenset({"web.mr"}), frozenset()),
            (
                "periop13",
                periop,
                False,
                frozenset(),
                frozenset({"web.surgery_application", "web.blood_application"}),
            ),
        ):
            settings = config.get(name, {})
            if not isinstance(settings, Mapping) or set(settings) - _METADATA_KEYS:
                raise ControlError("invalid_profile_metadata", "catalog_metadata_keys")
            enabled = settings.get("enabled", ready)
            actual_ready = settings.get("ready", ready)
            if type(enabled) is not bool or type(actual_ready) is not bool:
                raise ControlError("invalid_profile_metadata", "catalog_metadata_flags")
            incremental = self._approved(
                settings.get("incremental_interfaces", list(approved)), approved
            )
            scheduled = self._approved(
                settings.get("scheduled_interfaces", list(approved)), approved
            )
            self._profiles[name] = Profile(
                name,
                MappingProxyType(dict(specs)),
                enabled,
                actual_ready,
                incremental,
                scheduled,
                limits,
            )

    @staticmethod
    def _approved(value: Any, maximum: frozenset[str]) -> frozenset[str]:
        if (
            not isinstance(value, list)
            or any(not isinstance(v, str) for v in value)
            or len(value) != len(set(value))
            or not set(value) <= maximum
        ):
            raise ControlError("unverified_strategy", "catalog_strategy")
        return frozenset(value)

    def get(self, profile_id: str) -> Profile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise ControlError("profile_not_found", "catalog_profile", 404)
        return profile

    def resolve_spec(self, profile_id: str, interface_name: str) -> InterfaceSpec:
        spec = self.get(profile_id).specs.get(interface_name)
        if spec is None:
            raise ControlError("interface_not_allowed", "catalog_interface")
        return spec

    def source_contract(self, profile_id: str, interface_name: str) -> dict[str, Any] | None:
        """提供冻结源证据的独立副本；调用方不能扩大已知失败白名单。"""
        self.resolve_spec(profile_id, interface_name)
        if profile_id == "core13":
            return None
        return deepcopy(self._source_contracts[interface_name])

    def validate(
        self, profile_id: str, interfaces: Sequence[str], mode: str, origin: str = "manual"
    ) -> Profile:
        profile = self.get(profile_id)
        if mode not in MODES or origin not in {"manual", "schedule"}:
            raise ControlError("invalid_job_request", "catalog_mode_or_origin")
        if not interfaces or len(interfaces) != len(set(interfaces)):
            raise ControlError("invalid_job_request", "catalog_interface_count")
        if any(name not in profile.specs or name in DISABLED for name in interfaces):
            raise ControlError("interface_not_allowed", "catalog_interface")
        if not profile.enabled:
            raise ControlError("profile_disabled", "catalog_profile_disabled", 409)
        if not profile.ready:
            raise ControlError("profile_not_ready", "catalog_profile_readiness", 409)
        if mode == "incremental" and not set(interfaces) <= profile.incremental_interfaces:
            raise ControlError("unverified_strategy", "catalog_incremental")
        if origin == "schedule" and not set(interfaces) <= profile.scheduled_interfaces:
            raise ControlError("unverified_strategy", "catalog_schedule")
        return profile

    def describe(self) -> list[dict[str, Any]]:
        result = []
        for profile in self._profiles.values():
            interfaces = []
            for name in sorted(profile.specs):
                modes = ["dry", "replay", "publish_only"]
                if name in profile.incremental_interfaces:
                    modes.append("incremental")
                interfaces.append(
                    {
                        "interface": name,
                        "allowed_modes": modes if profile.enabled and profile.ready else [],
                        "capabilities": modes,
                        "scheduled_approved": name in profile.scheduled_interfaces,
                        "source_state": "partial_source"
                        if name in profile.source_limits
                        else "available",
                        "date_semantics": "discharge_date" if name == "web.mr" else "unverified",
                    }
                )
            result.append(
                {
                    "profile": profile.profile_id,
                    "enabled": profile.enabled,
                    "ready": profile.ready,
                    "interfaces": interfaces,
                    "disabled_interfaces": dict(DISABLED)
                    if profile.profile_id == "periop13"
                    else {},
                }
            )
        return result
