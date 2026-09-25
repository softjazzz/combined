"""
settlement /generate 与 /generate/qc 端点测试（含反例）

覆盖的最小反例集合：
- 旧入口兼容：/generate 仍调用共享 _generate_draft 且不要求机构号；
  现代组装在 institute_id=None 时保持旧口径。
- 现代入口身份前置：cdm.mr 权威解析的 0 行 → 404、歧义 → 409、坐标残缺 → 422、
  来源不可用 → 503；四类前置失败都不得 start_run、不得持久化。
- 现代入口同源：start_run / finish_success / VerifiedQCIdentity / 结果 metadata
  共用同一三坐标，source_key 固定 settlement_generate_qc，且以解析身份覆盖请求坐标。
- 现代入口失败关闭：草稿三坐标缺失或不符 → 503；组装 ValueError、writer 异常 →
  脱敏 503 且 finish_failed 只落对外文案。
- 现代入口取数：不消费无法核实机构归属的旧 A 表 ai_generation_results。

全部离线执行：mock + SQLite，不连真实库、不迁移、不读凭据。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text

from app.routers import settlement as route
from app.services.qc_persistence_service import VerifiedQCIdentity
from app.services.settlement_assembly_service import (
    SettlementAssemblyService,
    SettlementAssemblyUnavailableError,
)

GENERATED_SOURCE = "settlement_generate_qc"
_LEAK_MARKER = "LEAKMARKER9F3"
_RESOLVED = ("hospital-1", "p1", "v1")


class _EmptyQCEngine:
    """空形式质控报告：把断言收在身份、失败语义与草稿来源上。"""

    def check(self, _draft):
        return _EmptyReport()


class _EmptyReport:
    total_rules = 0
    passed = 0
    failed = 0
    results: list = []


_MR_DDL = (
    "(institute_id TEXT, patient_id TEXT, visit_id TEXT, name TEXT, sex TEXT)"
)


def _seed_mr(conn, schema: str, rows) -> None:
    conn.execute(text(f"CREATE TABLE {schema}.mr {_MR_DDL}"))
    for row in rows:
        conn.execute(
            text(
                f"INSERT INTO {schema}.mr (institute_id, patient_id, visit_id, name, sex) "
                "VALUES (:institute_id, :patient_id, :visit_id, :name, :sex)"
            ),
            {"name": "", "sex": "", **row},
        )


def _sqlite_engine(tmp_path, *, cdm_rows=(), public_mr_rows=(), ai_rows=()):
    """模拟 PG search_path：public 在前、权威病案首页在 cdm schema，旧 A 表在 main。"""
    paths = {
        name: (tmp_path / f"{name}.sqlite3").as_posix()
        for name in ("main", "public", "cdm")
    }
    engine = create_engine(f"sqlite:///{paths['main']}")

    @event.listens_for(engine, "connect")
    def _attach_authoritative_schemas(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE '{paths['public']}' AS public")
        cursor.execute(f"ATTACH DATABASE '{paths['cdm']}' AS cdm")
        cursor.close()

    with engine.begin() as conn:
        _seed_mr(conn, "public", public_mr_rows)
        _seed_mr(conn, "cdm", cdm_rows)
        conn.execute(text(
            "CREATE TABLE ai_generation_results ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, visit_id TEXT, "
            "task_type TEXT, result_data TEXT, created_at TEXT)"
        ))
        for row in ai_rows:
            conn.execute(
                text(
                    "INSERT INTO ai_generation_results "
                    "(patient_id, visit_id, task_type, result_data, created_at) "
                    "VALUES (:patient_id, :visit_id, :task_type, :result_data, :created_at)"
                ),
                {
                    "task_type": "frontpage_extraction",
                    "created_at": "2026-01-01 00:00:00",
                    **row,
                },
            )
    return engine


def _use_engine(monkeypatch, engine):
    """路由与组装都在函数内 import engine，patch 模块属性即可。"""
    from app.database import connection as db_connection

    monkeypatch.setattr(db_connection, "engine", engine)


def _modern_env(monkeypatch, *, identity=None, resolver_error=None, draft=None):
    """现代端点离线环境：解析替身 + 队列替身 + 落库替身（+ 可选草稿替身）。"""
    from app.services import settlement_formal_qc

    resolver_calls = []

    def _resolve(patient_id, visit_id, institute_id=None):
        resolver_calls.append((patient_id, visit_id, institute_id))
        if resolver_error is not None:
            raise resolver_error
        return identity

    monkeypatch.setattr(route, "_resolve_settlement_generate_identity", _resolve)

    queue = MagicMock()
    queue.start_run.return_value = "run-1"
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)

    persisted = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persisted)

    if draft is not None:
        monkeypatch.setattr(route, "_generate_draft", lambda *_a, **_k: dict(draft))

    monkeypatch.setattr(settlement_formal_qc, "SettlementFormalQCEngine", _EmptyQCEngine)
    return queue, persisted, resolver_calls


def _identity(institute_id="hospital-1", patient_id="p1", visit_id="v1"):
    return route.SettlementGenerateIdentity(institute_id, patient_id, visit_id)


def _draft(institute_id="hospital-1", patient_id="p1", visit_id="v1"):
    return {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "is_draft": True,
        "data_source": "generated_from_frontpage",
    }


async def _call(patient_id="p1", visit_id="v1", institute_id="hospital-1"):
    return await route.run_generated_settlement_qc(
        patient_id=patient_id,
        visit_id=visit_id,
        institute_id=institute_id,
        current_user={"id": "u1"},
    )


# --------------------------------------------------------------------------
# 旧入口兼容
# --------------------------------------------------------------------------

class TestGenerateDraft:
    """共享辅助函数 _generate_draft（通过组装服务间接验证）。"""

    def test_assembly_service_returns_draft_markers(self):
        """生成结果必须包含 is_draft 和 data_source 标记。"""
        svc = SettlementAssemblyService()
        result = svc.generate(patient_id="p001", visit_id="v001")
        assert result["is_draft"] is True
        assert result["data_source"] == "generated_from_frontpage"
        assert result["patient_id"] == "p001"
        assert result["visit_id"] == "v001"

    def test_assembly_service_generates_declaration_time(self):
        """自动生成申报时间。"""
        svc = SettlementAssemblyService()
        result = svc.generate(patient_id="p001", visit_id="v001")
        assert result.get("declaration_time")  # 非空


class TestGenerateEndpoint:
    """测试 /generate 端点行为。"""

    @patch("app.routers.settlement._generate_draft")
    @pytest.mark.asyncio
    async def test_generate_calls_shared_helper(self, mock_gen):
        """/generate 端点应调用共享 _generate_draft，且不要求机构号。"""
        from app.routers.settlement import generate_settlement_from_frontpage

        mock_gen.return_value = {"is_draft": True, "data_source": "generated_from_frontpage"}
        result = await generate_settlement_from_frontpage("p001", "v001")

        args, kwargs = mock_gen.call_args
        assert args[:2] == ("p001", "v001")
        assert not kwargs.get("institute_id")
        assert result["is_draft"] is True


# --------------------------------------------------------------------------
# cdm.mr 权威解析：0 行 / 歧义 / 显式机构消歧 / 来源不可用
# --------------------------------------------------------------------------

class TestResolveGeneratedIdentityHelper:

    def test_zero_rows_returns_none(self, monkeypatch, tmp_path):
        _use_engine(monkeypatch, _sqlite_engine(tmp_path))
        assert route._resolve_settlement_generate_identity("p1", "v1", "hospital-1") is None

    def test_public_mr_shadow_cannot_define_identity(self, monkeypatch, tmp_path):
        """默认 search_path 让 public 在前，public.mr 也不得决定身份解析。"""
        _use_engine(monkeypatch, _sqlite_engine(
            tmp_path,
            cdm_rows=[{"institute_id": "hospital-1", "patient_id": "p1", "visit_id": "v1"}],
            public_mr_rows=[
                {"institute_id": "hospital-shadow", "patient_id": "p1", "visit_id": "v1"}
            ],
        ))
        assert route._resolve_settlement_generate_identity("p1", "v1") == _identity("hospital-1")
        # 影子表里的机构不构成可解析身份
        assert route._resolve_settlement_generate_identity(
            "p1", "v1", "hospital-shadow"
        ) is None

    def test_cross_institute_visit_without_institute_is_ambiguous(self, monkeypatch, tmp_path):
        _use_engine(monkeypatch, _sqlite_engine(tmp_path, cdm_rows=[
            {"institute_id": "hospital-1", "patient_id": "p1", "visit_id": "v1"},
            {"institute_id": "hospital-2", "patient_id": "p1", "visit_id": "v1"},
        ]))
        with pytest.raises(route.SettlementGenerateIdentityAmbiguousError):
            route._resolve_settlement_generate_identity("p1", "v1")

    def test_explicit_institute_disambiguates(self, monkeypatch, tmp_path):
        _use_engine(monkeypatch, _sqlite_engine(tmp_path, cdm_rows=[
            {"institute_id": "hospital-1", "patient_id": "p1", "visit_id": "v1"},
            {"institute_id": "hospital-2", "patient_id": "p1", "visit_id": "v1"},
        ]))
        assert route._resolve_settlement_generate_identity(
            "p1", "v1", "hospital-2"
        ) == _identity("hospital-2")

    def test_read_failure_is_reported_as_source_unavailable(self, monkeypatch, tmp_path):
        """权威来源读不出来时不能降级为「查无此例」。"""
        _use_engine(
            monkeypatch, create_engine(f"sqlite:///{(tmp_path / 'bare.sqlite3').as_posix()}")
        )
        with pytest.raises(route.SettlementGenerateSourceUnavailableError):
            route._resolve_settlement_generate_identity("p1", "v1", "hospital-1")


# --------------------------------------------------------------------------
# 现代入口：身份前置失败不得 start、不得持久化
# --------------------------------------------------------------------------

class TestGeneratedQcPreconditions:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "resolver_error, expected_status",
        [
            (None, 404),
            (route.SettlementGenerateIdentityAmbiguousError("身份不唯一"), 409),
            (route.SettlementGenerateIdentityRejectedError("坐标不完整"), 422),
            (
                route.SettlementGenerateSourceUnavailableError(
                    f"{_LEAK_MARKER} postgresql://user:pw@host:5432/medqc"
                ),
                503,
            ),
        ],
        ids=["missing-404", "ambiguous-409", "rejected-422", "unavailable-503"],
    )
    async def test_identity_precondition_failure_never_starts_or_persists(
        self, monkeypatch, resolver_error, expected_status
    ):
        queue, persisted, _ = _modern_env(monkeypatch, resolver_error=resolver_error)

        with pytest.raises(HTTPException) as excinfo:
            await _call()

        assert excinfo.value.status_code == expected_status
        assert _LEAK_MARKER not in str(excinfo.value.detail)
        assert "postgresql://" not in str(excinfo.value.detail)
        queue.start_run.assert_not_called()
        queue.finish_failed.assert_not_called()
        queue.finish_success.assert_not_called()
        persisted.assert_not_awaited()

# --------------------------------------------------------------------------
# 现代入口：start / finish / 落库 / metadata 共用解析身份
# --------------------------------------------------------------------------

class TestGeneratedQcIdentityThreading:

    @pytest.mark.asyncio
    async def test_resolved_identity_is_the_only_source_for_queue_and_persistence(
        self, monkeypatch
    ):
        # 请求坐标与解析结果刻意不同：请求只用于消歧，身份以 cdm.mr 解析为准。
        queue, persisted, resolver_calls = _modern_env(
            monkeypatch, identity=_identity(), draft=_draft()
        )

        result = await _call(visit_id="v-request")

        assert resolver_calls == [("p1", "v-request", "hospital-1")]

        started = queue.start_run.call_args.kwargs
        assert started["workflow_type"] == "settlement_qc"
        assert started["source_key"] == GENERATED_SOURCE
        assert started["user_id"] == "u1"
        assert (started["institute_id"], started["patient_id"], started["visit_id"]) == _RESOLVED

        finished = queue.finish_success.call_args.kwargs
        assert finished["run_id"] == "run-1"
        assert finished["source_key"] == GENERATED_SOURCE
        assert (
            finished["institute_id"],
            finished["patient_id"],
            finished["visit_id"],
        ) == _RESOLVED

        payload = persisted.await_args.args[0]
        metadata = payload["metadata"]
        assert metadata["data_source"] == GENERATED_SOURCE
        assert metadata["trigger_source"] == "workstation_v4"
        assert (
            metadata["institute_id"],
            metadata["patient_id"],
            metadata["visit_id"],
        ) == _RESOLVED
        assert (payload["patient_id"], payload["visit_id"]) == ("p1", "v1")
        assert payload["record_id"] == "settlement::v1"

        verified = persisted.await_args.kwargs["verified_identity"]
        assert isinstance(verified, VerifiedQCIdentity)
        assert (
            verified.institute_id,
            verified.patient_id,
            verified.visit_id,
            verified.source_key,
        ) == (*_RESOLVED, GENERATED_SOURCE)

        assert result["persistence"] == {"success": True}


# --------------------------------------------------------------------------
# 现代入口：草稿身份失败关闭与脱敏
# --------------------------------------------------------------------------

class TestGeneratedQcFailClosed:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "draft",
        [
            {"patient_id": "p1", "visit_id": "v1"},
            _draft(visit_id="v9"),
        ],
        ids=["missing-institute", "mismatched-visit"],
    )
    async def test_draft_identity_must_equal_resolved_identity(self, monkeypatch, draft):
        queue, persisted, _ = _modern_env(
            monkeypatch, identity=_identity(), draft=draft
        )

        with pytest.raises(HTTPException) as excinfo:
            await _call()

        assert excinfo.value.status_code == 503
        persisted.assert_not_awaited()
        queue.finish_success.assert_not_called()
        queue.finish_failed.assert_called_once()
        assert queue.finish_failed.call_args.kwargs["source_key"] == GENERATED_SOURCE

    @pytest.mark.asyncio
    async def test_assembly_valueerror_is_sanitized_503(self, monkeypatch):
        """现代组装缺 mr / SQL 异常抛 ValueError 子类，只能对外暴露脱敏文案。"""
        queue, persisted, _ = _modern_env(monkeypatch, identity=_identity())

        def _boom(*_a, **_k):
            raise SettlementAssemblyUnavailableError(f"{_LEAK_MARKER} cdm.mr 缺失")

        monkeypatch.setattr(route, "_generate_draft", _boom)

        with pytest.raises(HTTPException) as excinfo:
            await _call()

        assert excinfo.value.status_code == 503
        assert _LEAK_MARKER not in str(excinfo.value.detail)
        persisted.assert_not_awaited()
        queue.finish_success.assert_not_called()
        queue.finish_failed.assert_called_once()
        assert _LEAK_MARKER not in str(queue.finish_failed.call_args)

    @pytest.mark.asyncio
    async def test_writer_failure_is_sanitized_503(self, monkeypatch):
        queue, _, _ = _modern_env(monkeypatch, identity=_identity(), draft=_draft())
        persisted = AsyncMock(
            side_effect=RuntimeError(f"{_LEAK_MARKER} postgresql://user:pw@host/db")
        )
        monkeypatch.setattr(
            route.default_qc_persistence_service, "persist_analysis", persisted
        )

        with pytest.raises(HTTPException) as excinfo:
            await _call()

        assert excinfo.value.status_code == 503
        assert _LEAK_MARKER not in str(excinfo.value.detail)
        assert "postgresql://" not in str(excinfo.value.detail)
        queue.finish_success.assert_not_called()
        queue.finish_failed.assert_called_once()
        assert _LEAK_MARKER not in str(queue.finish_failed.call_args)
        assert "postgresql://" not in str(queue.finish_failed.call_args)


# --------------------------------------------------------------------------
# 现代入口：结果已落库后队列收尾失败不得降级为失败
# --------------------------------------------------------------------------

class TestGeneratedQcQueueEpilogue:

    @pytest.mark.asyncio
    async def test_finish_success_failure_keeps_saved_result(self, monkeypatch):
        """落库成功、队列收尾抛错：仍返回保存成功结果，且不写 finish_failed。"""
        queue, persisted, _ = _modern_env(
            monkeypatch, identity=_identity(), draft=_draft()
        )
        queue.finish_success.side_effect = RuntimeError(f"{_LEAK_MARKER} 队列收尾失败")

        result = await _call()

        persisted.assert_awaited_once()
        assert result["persistence"] == {"success": True}
        queue.finish_failed.assert_not_called()


# --------------------------------------------------------------------------
# 现代入口：不消费无法核实机构归属的旧 A 表
# --------------------------------------------------------------------------

class TestGeneratedQcDraftSource:

    @pytest.mark.asyncio
    async def test_modern_path_skips_legacy_ai_results_but_legacy_entry_consumes(
        self, monkeypatch, tmp_path
    ):
        """同一份毒数据：旧入口照旧消费（对照），现代入口必须完全跳过。"""
        poison = {"basic_info": {"patient_name": f"{_LEAK_MARKER}患者"}}
        _use_engine(monkeypatch, _sqlite_engine(
            tmp_path,
            cdm_rows=[{
                "institute_id": "hospital-1",
                "patient_id": "p1",
                "visit_id": "v1",
                "name": "本院患者",
            }],
            ai_rows=[{
                "patient_id": "p1",
                "visit_id": "v1",
                "result_data": json.dumps(poison, ensure_ascii=False),
            }],
        ))

        captured = []

        def _spy_generate(
            self, patient_id, visit_id, frontpage_draft=None, db=None, institute_id=None
        ):
            captured.append({"frontpage_draft": frontpage_draft, "institute_id": institute_id})
            return {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "is_draft": True,
                "data_source": "generated_from_frontpage",
            }

        monkeypatch.setattr(SettlementAssemblyService, "generate", _spy_generate)

        legacy = await route.generate_settlement_from_frontpage("p1", "v1")
        assert captured[-1]["frontpage_draft"] == poison
        assert captured[-1]["institute_id"] is None
        assert legacy["is_draft"] is True

        _, persisted, _ = _modern_env(monkeypatch, identity=_identity())

        result = await _call()

        assert captured[-1]["institute_id"] == "hospital-1"
        assert captured[-1]["frontpage_draft"] is None
        assert _LEAK_MARKER not in json.dumps(result["settlement"], ensure_ascii=False)
        assert result["settlement"]["institute_id"] == "hospital-1"
        assert persisted.await_args.kwargs["verified_identity"].institute_id == "hospital-1"
