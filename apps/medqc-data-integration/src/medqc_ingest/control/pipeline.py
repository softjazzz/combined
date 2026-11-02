"""任务到原样抽取/发布引擎的桥接；不复制字段映射或写入算法。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from medqc_ingest.adapters.cache import OdbcSourceAdapter, create_source_adapter
from medqc_ingest.config import PostgresSettings, SourceSettings
from medqc_ingest.control.models import ControlError, SourceLimited
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import UnitFailure, safe_result
from medqc_ingest.domain import ErrorKind, IngestError, InterfaceSpec, RunMode
from medqc_ingest.periop_live import StrictLiveSource, known_vendor_failure
from medqc_ingest.periop_replay import VerifiedPublishCursor, explicit_window
from medqc_ingest.ports import (
    CdmRepository,
    IngestRepository,
    PublishAuditRepository,
    SourceAdapter,
)
from medqc_ingest.repositories.postgres import (
    PostgresCdmRepository,
    PostgresIngestRepository,
    PostgresRawPublishCursor,
    _connect,
)
from medqc_ingest.service import ExtractService, PublishService


@dataclass(frozen=True)
class PipelineBinding:
    source: SourceSettings | None
    ingest: PostgresSettings
    cdm: PostgresSettings
    chunk_size: int = 1000
    initial_incremental_start: date | None = None
    statement_timeout_seconds: int = 120


class BoundedOdbcSource(OdbcSourceAdapter):
    """连接超时仍由原适配器负责；SQL超时在创建任何cursor前设置。"""

    def __init__(self, settings: SourceSettings, timeout_seconds: int) -> None:
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ControlError("configuration_error", "pipeline_statement_timeout")
        super().__init__(settings)
        self.timeout_seconds = timeout_seconds

    def open(self) -> None:
        super().open()
        try:
            if self._connection is None:
                raise RuntimeError
            self._connection.timeout = self.timeout_seconds
        except Exception:
            self.close()
            raise IngestError(ErrorKind.CONFIGURATION, "control_odbc_timeout") from None


class ExecutionRepository(IngestRepository, PublishAuditRepository, Protocol):
    def failure_identity(
        self, interface: str, evidence: str, phase: str
    ) -> tuple[int | None, str | None]: ...


class CorrelatedRepository(PostgresIngestRepository):
    def __init__(self, settings: PostgresSettings, spec: InterfaceSpec, strict: bool) -> None:
        super().__init__(settings)
        self.spec, self.strict = spec, strict

    def open_verified_raw(
        self, interface: str, target_key_fields: Sequence[str]
    ) -> PostgresRawPublishCursor:
        cursor = super().open_verified_raw(interface, target_key_fields)
        return VerifiedPublishCursor(cursor, self.spec) if self.strict else cursor

    def failure_identity(
        self, interface: str, evidence: str, phase: str
    ) -> tuple[int | None, str | None]:
        # 不使用max(batch_id)或“最新一行”；关联标记唯一到本次单元尝试。
        table, field = (
            ("sync_ops.sync_batch", "batch_id")
            if phase == "extract"
            else ("sync_ops.publish_batch", "publish_batch_id")
        )
        with (
            closing(
                _connect(
                    self._settings, ErrorKind.INGEST_CONNECT, "control_correlation", readonly=True
                )
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                f"SELECT {field},status FROM {table} "
                "WHERE interface_name=%s AND evidence_version=%s",
                (interface, evidence),
            )
            rows = cursor.fetchall()
        if len(rows) > 1:
            raise ControlError("correlation_conflict", "pipeline_batch_identity", 409)
        return (int(rows[0][0]), str(rows[0][1])) if rows else (None, None)


RepositoryFactory = Callable[[PostgresSettings, InterfaceSpec, bool], ExecutionRepository]
SourceFactory = Callable[[SourceSettings], SourceAdapter]
CdmFactory = Callable[[PostgresSettings], CdmRepository]
CheckpointReader = Callable[[PostgresSettings, str], datetime | None]


def _checkpoint(settings: PostgresSettings, interface: str) -> datetime | None:
    with (
        closing(
            _connect(settings, ErrorKind.INGEST_CONNECT, "control_checkpoint", readonly=True)
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT last_window_end FROM sync_ops.sync_checkpoint WHERE interface_name=%s",
            (interface,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    value = row[0]
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ControlError("checkpoint_invalid", "pipeline_checkpoint_shape", 409)
    return value


class PipelineExecutor:
    def __init__(
        self,
        catalog: ProfileCatalog,
        bindings: Mapping[str, PipelineBinding],
        *,
        source_factory: SourceFactory | None = None,
        repository_factory: RepositoryFactory = CorrelatedRepository,
        cdm_factory: CdmFactory = PostgresCdmRepository,
        checkpoint_reader: CheckpointReader = _checkpoint,
    ) -> None:
        self.catalog, self.bindings = catalog, bindings
        self.source_factory, self.repository_factory = source_factory, repository_factory
        self.cdm_factory, self.checkpoint_reader = cdm_factory, checkpoint_reader

    def execution_identity(self, job: dict[str, Any]) -> str:
        """冻结数据面与合同身份；摘要不含密码、秘密文件路径或患者内容。"""
        profile = str(job["request"]["profile"])
        binding = self.bindings.get(profile)
        if binding is None:
            raise ControlError("configuration_error", "pipeline_binding", 503)

        def identity(value: Any, names: tuple[str, ...]) -> list[Any] | None:
            return [getattr(value, name) for name in names] if value is not None else None

        document = {
            "version": "binding-exact-temporal-v1",
            "profile": profile,
            "source": identity(binding.source, ("adapter", "host", "port", "namespace", "user")),
            "ingest": identity(binding.ingest, ("host", "port", "database", "user")),
            "cdm": identity(binding.cdm, ("host", "port", "database", "user")),
            "initial": str(binding.initial_incremental_start),
            "contracts": [
                asdict(self.catalog.resolve_spec(profile, name))
                for name in sorted(job["request"]["interfaces"])
            ],
        }
        return (
            "v1:"
            + hashlib.sha256(
                json.dumps(document, sort_keys=True, default=str, separators=(",", ":")).encode()
            ).hexdigest()
        )

    def execute(self, job: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
        request = job["request"]
        profile_id, interface = str(request["profile"]), str(unit["interface_name"])
        mode = str(request["mode"])
        self.catalog.validate(profile_id, [interface], mode, str(job.get("source", "manual")))
        spec = self.catalog.resolve_spec(profile_id, interface)
        binding = self.bindings.get(profile_id)
        if binding is None or binding.chunk_size <= 0:
            raise ControlError("configuration_error", "pipeline_binding", 503)
        try:
            job_id = str(UUID(str(job["job_id"])))
            unit_id = str(UUID(str(unit["unit_id"])))
        except (ValueError, TypeError, AttributeError):
            raise ControlError("invalid_identity", "pipeline_job_unit_identity") from None
        spec = replace(
            spec,
            evidence_version=(
                spec.evidence_version + f";job:{job_id};unit:{unit_id};attempt:{uuid4()}"
            ),
        )
        phase = unit["phase"]
        if phase not in {"extract", "publish"}:
            raise ControlError("invalid_unit", "pipeline_phase")
        repository: ExecutionRepository | None = None
        try:
            if phase == "publish":
                if mode == "dry":
                    raise ControlError("invalid_unit", "pipeline_dry_publish")
                repository = self.repository_factory(binding.ingest, spec, profile_id == "periop13")
                published = PublishService(
                    repository, self.cdm_factory(binding.cdm), binding.chunk_size
                ).run(spec)
                return safe_result(
                    {
                        "publish_batch_id": published.publish_batch_id,
                        "selected": published.selected,
                        "written": published.written,
                        "schema_hash": published.schema_hash,
                    }
                )
            if mode == "publish_only" or binding.source is None:
                raise ControlError("configuration_error", "pipeline_source_required")
            start, end = explicit_window(str(unit["source_date"]))
            day = start.date()
            if mode == "incremental":
                prior = self.checkpoint_reader(binding.ingest, interface)
                if (prior is None and binding.initial_incremental_start != day) or (
                    prior is not None and prior != start
                ):
                    raise ControlError("checkpoint_gap", "pipeline_incremental_continuity", 409)
            run_mode = RunMode(mode)
            if run_mode is not RunMode.DRY:
                repository = self.repository_factory(binding.ingest, spec, profile_id == "periop13")
            source_settings = binding.source

            def source() -> SourceAdapter:
                if self.source_factory is not None:
                    return self.source_factory(source_settings)
                if profile_id == "periop13":
                    if source_settings.adapter != "odbc":
                        raise ControlError("configuration_error", "pipeline_periop_odbc")
                    strict = StrictLiveSource(source_settings)
                    strict.inner = BoundedOdbcSource(
                        source_settings, binding.statement_timeout_seconds
                    )
                    return strict
                if source_settings.adapter == "odbc":
                    return BoundedOdbcSource(source_settings, binding.statement_timeout_seconds)
                return create_source_adapter(source_settings)

            result = ExtractService(source, repository, binding.chunk_size).run(
                spec, day.isoformat(), run_mode, start, end
            )
            return safe_result(
                {
                    "batch_id": result.batch_id,
                    "counts": result.counts,
                    "checkpoint_state": result.checkpoint_state,
                    "schema_hash": result.schema_hash,
                }
            )
        except IngestError as error:
            self._handle_ingest_error(error, repository, spec, profile_id, unit, str(phase))
            raise AssertionError("unreachable") from None
        except ControlError:
            raise
        except Exception:
            # 包括驱动清理在提交后抛错：不能把“没拿到正常返回”当成未提交。
            raise UnitFailure(
                "pipeline_failed",
                "pipeline_unexpected",
                result={"code": "execution_failed", "location": "pipeline_unexpected"},
                recovery_required=repository is not None,
            ) from None

    def _handle_ingest_error(
        self,
        error: IngestError,
        repository: ExecutionRepository | None,
        spec: InterfaceSpec,
        profile_id: str,
        unit: dict[str, Any],
        phase: str,
    ) -> None:
        result: dict[str, Any] = {"error_kind": error.kind, "error_location": error.location}
        current: BaseException | None = error
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            code = getattr(current, "pgcode", None)
            if not isinstance(code, str) and current.args:
                code = current.args[0]
            if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code):
                result["sqlstate"] = code
                break
            current = current.__cause__ or current.__context__
        remote_status: str | None = None
        correlation_unknown = False
        if repository is not None and error.location != "ingest_control_connect":
            try:
                batch_id, remote_status = repository.failure_identity(
                    spec.name, spec.evidence_version, phase
                )
                if batch_id is not None:
                    result["batch_id" if phase == "extract" else "publish_batch_id"] = batch_id
            except Exception:
                correlation_unknown = True
        uncertain = (
            correlation_unknown
            or error.location
            in {
                "start_batch",
                "start_publish",
                "commit_data",
                "mark_batch_succeeded",
                "commit_cdm",
                "commit_publish_lineage",
                "mark_publish_succeeded",
            }
            or remote_status == "running"
        )
        if not uncertain and phase == "extract" and profile_id == "periop13":
            item = self.catalog.source_contract(profile_id, spec.name)
            if item is not None and known_vendor_failure(error, item, str(unit["source_date"])):
                raise SourceLimited(
                    "pipeline_known_vendor_failure", dict(result, sqlstate="HY000", native=400)
                ) from None
        raise UnitFailure(
            "pipeline_failed",
            "pipeline_execute",
            result=safe_result(result),
            recovery_required=uncertain,
        ) from None
