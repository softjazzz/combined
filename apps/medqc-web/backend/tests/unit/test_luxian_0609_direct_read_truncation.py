"""P2-2 直读路径 +1 截断探测与 P2-6 bundle 缺 visit_id 不得回退 document_id 回归测试。"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    source_evidence_reader,
)
from app.services.luxian_0609.native_package import Luxian0609PackagePlan
from app.services.sichuan_qc_service import SichuanQCService


@dataclass
class _FakeMappingsResult:
    rows: list[dict]

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _LimitedRowsConnection:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        bound = dict(params)
        self.calls.append((str(statement), bound))
        return _FakeMappingsResult(self.rows[: bound["limit_rows"]])


class _FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


def _patch_direct_source_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[dict],
    columns: list[str],
    limit: int,
) -> _LimitedRowsConnection:
    connection = _LimitedRowsConnection(rows)
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection)
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm"
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _table: columns,
    )
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: limit)
    return connection


def test_runtime_direct_read_exact_cap_is_not_falsely_truncated(monkeypatch) -> None:
    rows = [
        {"surgery_begin_time": "2026-07-01 08:00:00+08"},
        {"surgery_begin_time": "2026-07-02 08:00:00+08"},
    ]
    connection = _patch_direct_source_env(
        monkeypatch,
        rows=rows,
        columns=["institute_id", "patient_id", "visit_id", "surgery_begin_time"],
        limit=2,
    )

    result = source_evidence_reader.read_luxian_0609_runtime_source_rows(
        source_key="surgery_record",
        institute_id="safe-inst",
        patient_id="safe-pat",
        visit_id="safe-visit",
        source_schema="cdm",
    )

    assert result == rows
    assert connection.calls[0][1]["limit_rows"] == 3


def test_runtime_direct_read_overflow_raises_source_evidence_truncated(monkeypatch) -> None:
    rows = [
        {"surgery_begin_time": f"2026-07-0{idx} 08:00:00+08"}
        for idx in range(1, 4)
    ]
    connection = _patch_direct_source_env(
        monkeypatch,
        rows=rows,
        columns=["institute_id", "patient_id", "visit_id", "surgery_begin_time"],
        limit=2,
    )

    with pytest.raises(source_evidence_reader.SourceEvidenceTruncated):
        source_evidence_reader.read_luxian_0609_runtime_source_rows(
            source_key="surgery_record",
            institute_id="safe-inst",
            patient_id="safe-pat",
            visit_id="safe-visit",
            source_schema="cdm",
        )

    assert connection.calls[0][1]["limit_rows"] == 3


def test_native_direct_read_exact_cap_is_not_falsely_truncated(monkeypatch) -> None:
    rows = [
        {"document_id": "DOC-1", "record_content": "第一条会诊记录"},
        {"document_id": "DOC-2", "record_content": "第二条会诊记录"},
    ]
    connection = _patch_direct_source_env(
        monkeypatch,
        rows=rows,
        columns=["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
        limit=2,
    )

    result = source_evidence_reader.read_luxian_0609_native_source_rows(
        source_key="consultation_record",
        institute_id="safe-inst",
        patient_id="safe-pat",
        visit_id="safe-visit",
        source_schema="cdm",
    )

    assert result == rows
    assert connection.calls[0][1]["limit_rows"] == 3


def test_native_direct_read_overflow_raises_source_evidence_truncated(monkeypatch) -> None:
    rows = [
        {"document_id": f"DOC-{idx}", "record_content": f"第{idx}条会诊记录"}
        for idx in range(1, 4)
    ]
    connection = _patch_direct_source_env(
        monkeypatch,
        rows=rows,
        columns=["institute_id", "patient_id", "visit_id", "document_id", "record_content"],
        limit=2,
    )

    with pytest.raises(source_evidence_reader.SourceEvidenceTruncated):
        source_evidence_reader.read_luxian_0609_native_source_rows(
            source_key="consultation_record",
            institute_id="safe-inst",
            patient_id="safe-pat",
            visit_id="safe-visit",
            source_schema="cdm",
        )

    assert connection.calls[0][1]["limit_rows"] == 3


def test_snapshot_reader_distinguishes_exact_cap_from_overflow(monkeypatch) -> None:
    columns = ["institute_id", "patient_id", "visit_id", "document_id", "record_content"]
    exact_rows = [
        {"document_id": "DOC-1", "record_content": "记录一"},
        {"document_id": "DOC-2", "record_content": "记录二"},
    ]
    conn_exact = _patch_direct_source_env(
        monkeypatch, rows=exact_rows, columns=columns, limit=2
    )
    exact_result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="consultation_record",
        institute_id="safe-inst",
        patient_id="safe-pat",
        visit_id="safe-visit",
        source_schema="cdm",
    )
    assert exact_result.truncated is False
    assert len(exact_result.rows) == 2
    assert conn_exact.calls[0][1]["limit_rows"] == 3

    overflow_rows = [
        *exact_rows,
        {"document_id": "DOC-3", "record_content": "记录三"},
    ]
    conn_overflow = _patch_direct_source_env(
        monkeypatch, rows=overflow_rows, columns=columns, limit=2
    )
    overflow_result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="consultation_record",
        institute_id="safe-inst",
        patient_id="safe-pat",
        visit_id="safe-visit",
        source_schema="cdm",
    )
    assert overflow_result.truncated is True
    assert len(overflow_result.rows) == 2
    assert conn_overflow.calls[0][1]["limit_rows"] == 3


def test_discharge_horizon_multi_row_conflict_preserves_truncated_flag(monkeypatch) -> None:
    connection = _LimitedRowsConnection(
        [
            {"discharge_datetime": "2026-07-15 10:00:00"},
            {"discharge_datetime": "2026-07-16 12:00:00"},
        ]
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection)
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm"
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, table: (
            ["institute_id", "patient_id", "visit_id", "discharge_datetime"]
            if table == "inpat_registration"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_discharge_horizon_rows(
        institute_id="safe-inst",
        patient_id="safe-pat",
        visit_id="safe-visit",
        source_schema="cdm",
    )

    assert result.truncated is True
    assert result.limit_rows == 1
    assert len(result.rows) == 1
    assert connection.calls[0][1]["limit_rows"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bundle_visit_id", "expected_visit_id"),
    [
        (None, ""),
        ("   ", ""),
        ("V-EXPLICIT-001", "V-EXPLICIT-001"),
    ],
)
async def test_running_final_bundle_does_not_substitute_document_id_for_missing_visit_id(
    monkeypatch,
    bundle_visit_id: str | None,
    expected_visit_id: str,
) -> None:
    captured: dict[str, object] = {}
    selected = ("LX0609-01-01-01",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(),
    )

    async def _fake_prepare(**kwargs):
        captured["prepare_visit_id"] = kwargs["visit_id"]
        captured["prepare_institute_id"] = kwargs["institute_id"]
        captured["prepare_patient_id"] = kwargs["patient_id"]
        return [], SimpleNamespace(enabled=True)

    def _fake_aggregate(*, orchestrated, visit_id, **_kwargs):
        captured["aggregate_visit_id"] = visit_id
        orchestrated["results"] = [
            {
                "rule_id": selected[0],
                "status": "data_gap",
                "is_compliant": None,
                "metadata": {"execution_source": "lx0609_native"},
            }
        ]

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: SimpleNamespace(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
            LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        ),
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.resolve_mainline_rule_decision_settings",
        lambda settings: settings,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.assert_luxian_0609_customer_native_delivery_ready",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.load_luxian_0609_dependency_inventory",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.assert_luxian_0609_formal_package_plan_native_only",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.load_luxian_0609_rules",
        lambda: [{"rule_id": selected[0], "rule_name": "测试规则"}],
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.prepare_luxian_0609_execution",
        _fake_prepare,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _fake_aggregate,
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)

    bundle: dict[str, object] = {
        "scene": "running",
        "institute_id": "HOSP-1",
        "patient_id": "PAT-1",
        "structured_context": {"documents": {}},
        "text_available": False,
    }
    if bundle_visit_id is not None:
        bundle["visit_id"] = bundle_visit_id

    result = await SichuanQCService().evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=list(selected),
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert captured["prepare_institute_id"] == "HOSP-1"
    assert captured["prepare_patient_id"] == "PAT-1"
    assert captured["prepare_visit_id"] == expected_visit_id
    assert captured["aggregate_visit_id"] == expected_visit_id
    assert captured["prepare_visit_id"] != "HOSP-1-PAT-1"
    assert result["bundle_metadata"]["visit_id"] == (bundle_visit_id or "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_visit_id", "expected_visit_id"),
    [
        ("VISIT-TRUSTED-001", "VISIT-TRUSTED-001"),
        ("  VISIT-TRUSTED-001  ", "VISIT-TRUSTED-001"),
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
async def test_evaluate_rules_orchestrated_uses_consistent_trusted_visit_id_without_document_id_fallback(
    monkeypatch,
    source_visit_id: str | None,
    expected_visit_id: str,
) -> None:
    from app.services.luxian_0609.execution import Luxian0609ExecutionContext

    captured: dict[str, object] = {}

    async def _fake_prepare(**kwargs):
        captured["prepare_visit_id"] = kwargs["visit_id"]
        captured["prepare_institute_id"] = kwargs["institute_id"]
        captured["prepare_patient_id"] = kwargs["patient_id"]
        return [], Luxian0609ExecutionContext(enabled=True)

    def _fake_aggregate(*, orchestrated, visit_id, **_kwargs):
        captured["aggregate_visit_id"] = visit_id
        orchestrated["results"] = [
            {
                "rule_id": "LX0609-01-01-01",
                "status": "data_gap",
                "is_compliant": None,
                "metadata": {"execution_source": "lx0609_native"},
            }
        ]
        return orchestrated

    async def _fake_evaluate_rules(**_kwargs):
        return {"results": []}

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.prepare_luxian_0609_execution",
        _fake_prepare,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _fake_aggregate,
    )

    service = SichuanQCService()
    monkeypatch.setattr(service.rule_orchestrator, "evaluate_rules", _fake_evaluate_rules)

    result = await service._evaluate_rules_orchestrated(
        document_id="DOC-ONLY-001",
        content="合成测试病历文本",
        document_type="病程记录",
        rules=[{"rule_id": "LX0609-01-01-01", "rule_name": "测试规则"}],
        use_execution_cache=False,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        source_institute_id="HOSP-1",
        source_patient_id="PAT-1",
        source_visit_id=source_visit_id,  # type: ignore[arg-type]
    )

    assert captured["prepare_institute_id"] == "HOSP-1"
    assert captured["prepare_patient_id"] == "PAT-1"
    assert captured["prepare_visit_id"] == expected_visit_id
    assert captured["aggregate_visit_id"] == expected_visit_id
    assert captured["prepare_visit_id"] == captured["aggregate_visit_id"]
    assert captured["prepare_visit_id"] != "DOC-ONLY-001"
    assert captured["aggregate_visit_id"] != "DOC-ONLY-001"
    assert result["results"][0]["rule_id"] == "LX0609-01-01-01"
