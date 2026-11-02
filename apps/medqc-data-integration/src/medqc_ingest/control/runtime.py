"""受控配置装配：控制面与执行绑定分开，API不读取数据面秘密。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from medqc_ingest.config import PassfilePostgresSettings, source_zone
from medqc_ingest.control.models import ControlError
from medqc_ingest.control.profiles import ProfileCatalog


def _require(condition: bool, location: str) -> None:
    if not condition:
        raise ControlError("configuration_error", location, 503)


def _object(value: Any, allowed: set[str], location: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and not set(value) - allowed, location)
    return dict(value)


def _file(value: Any, location: str) -> Path:
    _require(isinstance(value, str), location)
    path = Path(value)
    name = path.name.lower()
    _require(
        path.is_absolute()
        and path.is_file()
        and path.suffix.lower() != ".env"
        and name != ".env"
        and not name.startswith(".env."),
        location,
    )
    return path


def _json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        _require(isinstance(value, dict), "runtime_json_object")
        return dict(value)
    except (OSError, UnicodeError, ValueError, TypeError):
        raise ControlError("configuration_error", "runtime_json", 503) from None


def _positive(value: Any, maximum: float, location: str) -> float:
    _require(type(value) in {int, float} and 0 < value <= maximum, location)
    return float(value)


def _postgres(document: Any, *, control: bool) -> PassfilePostgresSettings:
    config = _object(document, {"host", "port", "database", "user", "passfile"}, "runtime_pg_keys")
    host, database, user = config.get("host"), config.get("database"), config.get("user")
    port = config.get("port", 5432)
    _require(host == "127.0.0.1" and type(port) is int and 0 < port < 65536, "runtime_pg_endpoint")
    if not isinstance(database, str) or not isinstance(user, str):
        raise ControlError("configuration_error", "runtime_pg_identity", 503)
    if control:
        _require(
            database == "medqc_sync_control"
            or re.fullmatch(r"medqc_sync_control_acceptance_[0-9]{14}", database) is not None,
            "runtime_control_database",
        )
        _require(user in {"medqc_job_api", "medqc_job_worker"}, "runtime_control_user")
    else:
        _require(
            re.fullmatch(
                r"medqc_(?:sync_(?:ingest|cdm)_acceptance|(?:ingest|cdm)_takeover|"
                r"periop_live_(?:ingest|cdm))_[0-9]{14}",
                database,
            )
            is not None,
            "runtime_data_database",
        )
        _require(
            database
            not in {
                "medqc_ingest_takeover_20261030205035",
                "medqc_cdm_takeover_20261030205035",
            },
            "runtime_protected_baseline",
        )
        _require(user == "medqc_sync", "runtime_data_user")
    passfile = _file(config.get("passfile"), "runtime_passfile")
    return PassfilePostgresSettings(str(host), int(port), database, user, passfile)


def _catalog(document: Any, approvals: Any) -> dict[str, Any]:
    metadata = _object(document, {"core13", "periop13"}, "runtime_catalog")
    approval_map = _object(approvals, {"periop13"}, "runtime_profile_approvals")
    periop = metadata.get("periop13", {})
    if isinstance(periop, dict) and (periop.get("enabled") is True or periop.get("ready") is True):
        approval = _object(approval_map.get("periop13", {}), {"file", "sha256"}, "runtime_approval")
        path = _file(approval.get("file"), "runtime_approval_file")
        digest = approval.get("sha256")
        _require(
            isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) is not None,
            "runtime_approval_hash",
        )
        _require(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest, "runtime_approval_integrity"
        )
        evidence = _json_file(path)
        _require(
            evidence.get("status")
            in {
                "PERIOP_LIVE_SOURCE_VALIDATION_ACCEPTED",
                "PERIOP_LIVE_SOURCE_VALIDATION_ACCEPTED_WITH_SOURCE_LIMITATIONS",
            }
            and evidence.get("synthetic") is False
            and evidence.get("cache_accessed") is True
            and evidence.get("postgres_major") == 16
            and evidence.get("active_interfaces") == 13,
            "runtime_profile_not_live_validated",
        )
    ProfileCatalog(metadata)  # 包内冻结合同及不可扩大策略也在装配前检查。
    return metadata


@dataclass(frozen=True)
class ApiRuntime:
    bind: str = "127.0.0.1"
    port: int = 8766
    tokens_file: Path | None = None


@dataclass(frozen=True)
class WorkerRuntime:
    worker_id: str = "worker-1"
    poll_seconds: float = 1.0
    heartbeat_seconds: float = 10.0
    lease_seconds: int = 180
    bindings_file: Path | None = None
    automatic_retries: int = 2
    job_budget_seconds: float = 3600.0


@dataclass(frozen=True)
class ControlRuntime:
    path: Path
    postgres: PassfilePostgresSettings
    catalog_metadata: dict[str, Any]
    api: ApiRuntime
    worker: WorkerRuntime

    @classmethod
    def load(cls, path: Path, *, role: str = "worker") -> ControlRuntime:
        _require(role in {"api", "worker"}, "runtime_role")
        _require(not os.environ.get("PGPASSWORD"), "runtime_pgpassword_forbidden")
        config_path = _file(str(path), "runtime_config_file")
        document = _object(
            _json_file(config_path),
            {"postgres", "catalog", "profile_approvals", "api", "worker"},
            "runtime_keys",
        )
        pg = _postgres(document.get("postgres"), control=True)
        _require(
            pg.user == ("medqc_job_api" if role == "api" else "medqc_job_worker"),
            "runtime_role_connection",
        )
        metadata = _catalog(document.get("catalog", {}), document.get("profile_approvals", {}))
        api = _object(document.get("api", {}), {"bind", "port", "tokens_file"}, "runtime_api")
        _require(api.get("bind", "127.0.0.1") == "127.0.0.1", "runtime_api_loopback")
        api_port = api.get("port", 8766)
        _require(type(api_port) is int and 1024 <= api_port <= 65535, "runtime_api_port")
        token_file = (
            _file(api["tokens_file"], "runtime_api_tokens") if "tokens_file" in api else None
        )
        _require(role != "api" or token_file is not None, "runtime_api_tokens_required")
        worker = _object(
            document.get("worker", {}),
            {
                "worker_id",
                "poll_seconds",
                "heartbeat_seconds",
                "lease_seconds",
                "bindings_file",
                "automatic_retries",
                "job_budget_seconds",
            },
            "runtime_worker",
        )
        worker_id = worker.get("worker_id", "worker-1")
        _require(
            isinstance(worker_id, str)
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", worker_id) is not None,
            "runtime_worker_id",
        )
        poll = _positive(worker.get("poll_seconds", 1), 60, "runtime_worker_poll")
        heartbeat = _positive(worker.get("heartbeat_seconds", 10), 60, "runtime_worker_heartbeat")
        lease = worker.get("lease_seconds", 180)
        _require(
            type(lease) is int and 30 <= lease <= 3600 and heartbeat * 3 < lease,
            "runtime_worker_lease",
        )
        retries = worker.get("automatic_retries", 2)
        _require(type(retries) is int and 0 <= retries <= 2, "runtime_worker_retries")
        budget = _positive(worker.get("job_budget_seconds", 3600), 86400, "runtime_worker_budget")
        # 这里只保存路径引用；API及supervisor都不打开bindings或Cache口令。
        binding_path = worker.get("bindings_file")
        _require(
            binding_path is None
            or isinstance(binding_path, str)
            and Path(binding_path).is_absolute(),
            "runtime_bindings_reference",
        )
        return cls(
            config_path,
            pg,
            metadata,
            ApiRuntime(port=api_port, tokens_file=token_file),
            WorkerRuntime(
                worker_id,
                poll,
                heartbeat,
                lease,
                Path(binding_path) if binding_path else None,
                retries,
                budget,
            ),
        )

    def load_bindings(self) -> dict[str, Any]:
        """仅执行子进程调用；加载时每个binding仍受本地验收库白名单限制。"""
        from medqc_ingest.control.pipeline import PipelineBinding
        from medqc_ingest.periop_live import source_settings

        _require(self.postgres.user == "medqc_job_worker", "runtime_api_bindings_forbidden")
        _require(self.worker.bindings_file is not None, "runtime_bindings_required")
        path = _file(str(self.worker.bindings_file), "runtime_bindings_file")
        document = _object(_json_file(path), {"profiles"}, "runtime_bindings_keys")
        profiles = _object(
            document.get("profiles"), {"core13", "periop13"}, "runtime_bindings_profiles"
        )
        result = {}
        for name, value in profiles.items():
            binding = _object(
                value,
                {
                    "source_config_file",
                    "ingest",
                    "cdm",
                    "chunk_size",
                    "initial_incremental_start",
                    "statement_timeout_seconds",
                },
                "runtime_binding_keys",
            )
            source_file = binding.get("source_config_file")
            source = (
                source_settings(_file(source_file, "runtime_source_config"))
                if source_file is not None
                else None
            )
            ingest = _postgres(binding.get("ingest"), control=False)
            cdm = _postgres(binding.get("cdm"), control=False)
            _require(
                ingest.database != cdm.database
                and "ingest" in ingest.database
                and "cdm" in cdm.database,
                "runtime_distinct_data_targets",
            )
            chunk = binding.get("chunk_size", 1000)
            _require(type(chunk) is int and 1 <= chunk <= 5000, "runtime_chunk_size")
            initial_value = binding.get("initial_incremental_start")
            initial = None
            if initial_value is not None:
                _require(isinstance(initial_value, str), "runtime_initial_window")
                try:
                    initial = date.fromisoformat(initial_value)
                except ValueError:
                    raise ControlError(
                        "configuration_error", "runtime_initial_window", 503
                    ) from None
                _require(
                    initial.isoformat() == initial_value
                    and name == "core13"
                    and date(1900, 1, 1)
                    <= initial
                    < datetime.now(source_zone("Asia/Shanghai")).date(),
                    "runtime_initial_window",
                )
            timeout = binding.get("statement_timeout_seconds", 120)
            _require(type(timeout) is int and 1 <= timeout <= 3600, "runtime_statement_timeout")
            result[name] = PipelineBinding(source, ingest, cdm, chunk, initial, timeout)
        return result
