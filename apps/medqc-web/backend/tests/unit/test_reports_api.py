"""
报表 API 单元测试

测试 reports 路由的核心功能：
- 质控汇总报表
- 报表导出
- 缓存机制
- 统计数据
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import reports as reports_module


@pytest.fixture(autouse=True)
def _bypass_default_auth_guard(client, monkeypatch, tmp_path):
    async def _noop_auth_gate():
        return None

    async def _default_current_user():
        return {"id": "reports-owner", "roles": ["qc_manager"]}

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    client.app.dependency_overrides[get_current_user] = _default_current_user
    monkeypatch.setattr(reports_module, "_QC_EXPORT_DIR", tmp_path)
    yield
    client.app.dependency_overrides.pop(enforce_default_auth, None)
    client.app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.unit
@pytest.mark.api
class TestReportsAPI:
    """报表 API 测试类"""

    @pytest.mark.asyncio
    async def test_qc_summary_success(self, client):
        """测试获取质控汇总成功"""
        mock_supabase = MagicMock()
        
        # Mock 视图数据
        mock_view_response = MagicMock()
        mock_view_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        # Mock 规则数据
        mock_rules_response = MagicMock()
        mock_rules_response.data = [{"id": f"rule-{i}"} for i in range(10)]
        mock_defects_response = MagicMock()
        mock_defects_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_view_response, mock_rules_response, mock_defects_response]
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.85,
                        "avg_api_time": 1.2,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "kpis" in data["data"]
                    assert "generated_at" in data["data"]

    @pytest.mark.asyncio
    async def test_qc_summary_kpis_structure(self, client):
        """测试质控汇总 KPI 结构"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    kpis = data["data"]["kpis"]

                    # 验证 KPI 字段
                    assert "total_records" in kpis
                    assert "active_rules" in kpis
                    assert "qc_executions" in kpis
                    assert "pass_rate" in kpis
                    assert "avg_api_time" in kpis
                    assert "avg_qc_score" in kpis
                    assert "passed" in kpis
                    assert "warning" in kpis
                    assert "failed" in kpis
                    assert "pending" in kpis

    @pytest.mark.asyncio
    async def test_qc_summary_cache_mechanism(self, client):
        """测试质控汇总缓存机制"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    # 第一次请求
                    response1 = client.get("/api/v1/reports/qc/summary")
                    assert response1.status_code == 200

                    # 第二次请求（应该使用缓存）
                    response2 = client.get("/api/v1/reports/qc/summary")
                    assert response2.status_code == 200

                    # 验证数据一致
                    assert response1.json()["data"]["kpis"] == response2.json()["data"]["kpis"]

    @pytest.mark.asyncio
    async def test_qc_summary_uses_shared_scan_limit(self, client):
        """测试质控汇总查询使用共享上限。"""
        from app.routers import reports as reports_module

        reports_module._QC_SUMMARY_CACHE = None
        reports_module._QC_SUMMARY_CACHE_TS = 0.0

        class _FakeQuery:
            def __init__(self):
                self.limit_calls = []
                self.exclude_task_manual_source_calls = 0

            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def exclude_task_manual_source(self):
                self.exclude_task_manual_source_calls += 1
                return self

            def limit(self, value):
                self.limit_calls.append(value)
                return self

        class _FakeTable:
            def __init__(self, query):
                self._query = query

            def select(self, *args, **kwargs):
                return self._query.select(*args, **kwargs)

        class _FakeSupabase:
            def __init__(self):
                self.query = _FakeQuery()
                self.table_calls = []

            def table(self, name):
                self.table_calls.append(name)
                return _FakeTable(self.query)

        mock_supabase = _FakeSupabase()
        mock_view_response = MagicMock()
        mock_view_response.data = []
        mock_rules_response = MagicMock()
        mock_rules_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_view_response, mock_rules_response]
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

        assert response.status_code == 200
        assert mock_supabase.table_calls == ["qc_statistics_view", "qc_rules", "qc_defects"]
        assert mock_supabase.query.limit_calls == [1000, 1000, 1000]
        assert mock_supabase.query.exclude_task_manual_source_calls == 1





    @pytest.mark.asyncio
    async def test_qc_export_success(self, client):
        """测试导出质控报表成功"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.audit_event") as mock_audit:
                    response = client.post("/api/v1/reports/qc/export", json={})

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "export_id" in data["data"]
                    assert "download_url" in data["data"]
                    assert "count" in data["data"]
                    mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_qc_export_with_record_ids(self, client):
        """测试导出指定病历的质控报表"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                payload = {"record_ids": ["record-1", "record-2"]}
                response = client.post("/api/v1/reports/qc/export", json=payload)

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["requested_records"] == ["record-1", "record-2"]

    @pytest.mark.asyncio
    async def test_qc_export_no_supabase(self, client):
        """测试 Supabase 不可用时导出报表"""
        with patch("app.routers.reports.get_supabase", return_value=None):
            response = client.post("/api/v1/reports/qc/export", json={})

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_qc_export_empty_result(self, client):
        """测试导出空结果"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                response = client.post("/api/v1/reports/qc/export", json={})

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_qc_export_file_creation(self, client):
        """测试导出文件创建"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                response = client.post("/api/v1/reports/qc/export", json={})

                assert response.status_code == 200
                data = response.json()

                # 验证文件路径格式
                download_url = data["data"]["download_url"]
                assert download_url.startswith("/api/v1/reports/qc/export/")
                assert download_url.endswith("/download")

    @pytest.mark.asyncio
    async def test_qc_export_download_is_private_to_creator_or_admin(self, client):
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                created = client.post("/api/v1/reports/qc/export", json={})

        assert created.status_code == 200
        download_url = created.json()["data"]["download_url"]
        export_id = created.json()["data"]["export_id"]
        assert client.get(download_url).status_code == 200
        assert client.get(download_url).content.startswith(b"record_id,")

        # 即使应用级默认认证被测试替身绕过，下载端点自身仍要求身份认证。
        client.app.dependency_overrides.pop(get_current_user)
        assert client.get(download_url).status_code == 401

        client.app.dependency_overrides[get_current_user] = lambda: {
            "id": "another-user",
            "roles": ["doctor"],
        }
        assert client.get(download_url).status_code == 403

        client.app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-user",
            "roles": ["admin"],
        }
        admin_download = client.get(download_url)
        assert admin_download.status_code == 200
        assert admin_download.headers["cache-control"] == "no-store"
        assert admin_download.headers["content-disposition"].endswith(f'qc_summary_{export_id}.csv"')

        # /downloads 不再公开挂载，猜到旧文件路径也无法读取。
        assert client.get(f"/downloads/qc_summary_{export_id}.csv").status_code == 404

    @pytest.mark.asyncio
    async def test_qc_export_download_expiry_removes_private_artifacts(self, client, tmp_path):
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                created = client.post("/api/v1/reports/qc/export", json={})

        assert created.status_code == 200
        payload = created.json()["data"]
        export_id = payload["export_id"]
        csv_path = tmp_path / f"{export_id}.csv"
        metadata_path = tmp_path / f"{export_id}.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["expires_at"] = "2000-01-01T00:00:00+00:00"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        expired = client.get(payload["download_url"])
        assert expired.status_code == 404
        assert not csv_path.exists()
        assert not metadata_path.exists()

    def test_cleanup_ignores_metadata_removed_after_enumeration(self, monkeypatch, tmp_path):
        """并发清理删除 metadata 后，本轮清理不应因再次 stat 而失败。"""
        export_id = uuid4().hex
        csv_path = tmp_path / f"{export_id}.csv"
        metadata_path = tmp_path / f"{export_id}.json"
        csv_path.write_text("record_id\nrecord-1\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps({"expires_at": "2999-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )

        original_reader = reports_module._read_export_artifact

        def remove_metadata_before_read(path):
            if path == metadata_path:
                path.unlink()
            return original_reader(path)

        monkeypatch.setattr(reports_module, "_read_export_artifact", remove_metadata_before_read)

        reports_module._cleanup_expired_exports(now=datetime.now(timezone.utc))

        assert csv_path.exists()
        assert not metadata_path.exists()

    def test_cleanup_tolerates_csv_removed_before_expired_metadata(self, tmp_path):
        """CSV 先被另一清理者删除时，过期 metadata 仍可安全清除。"""
        export_id = uuid4().hex
        csv_path = tmp_path / f"{export_id}.csv"
        metadata_path = tmp_path / f"{export_id}.json"
        csv_path.write_text("record_id\nrecord-1\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps({"expires_at": "2000-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        csv_path.unlink()

        reports_module._cleanup_expired_exports(now=datetime.now(timezone.utc))

        assert not csv_path.exists()
        assert not metadata_path.exists()

    def test_cleanup_is_idempotent_for_two_competing_cleaners(self, monkeypatch, tmp_path):
        """两个清理者处理同一过期导出时，双方都能正常完成。"""
        export_id = uuid4().hex
        csv_path = tmp_path / f"{export_id}.csv"
        metadata_path = tmp_path / f"{export_id}.json"
        csv_path.write_text("record_id\nrecord-1\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps({"expires_at": "2000-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        current_time = datetime.now(timezone.utc)
        barrier = Barrier(2)
        original_reader = reports_module._read_export_artifact

        def synchronize_metadata_read(path):
            content = original_reader(path)
            if path == metadata_path:
                barrier.wait(timeout=5)
            return content

        monkeypatch.setattr(reports_module, "_read_export_artifact", synchronize_metadata_read)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(reports_module._cleanup_expired_exports, now=current_time)
                for _ in range(2)
            ]
            for future in futures:
                future.result()

        assert not csv_path.exists()
        assert not metadata_path.exists()

    def test_qc_export_removes_csv_when_metadata_write_fails(self, client, monkeypatch, tmp_path):
        """metadata 写入失败不能留下不可下载、不可回收的 CSV。"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        original_write_text = type(tmp_path).write_text

        def fail_metadata_write(path, data, *args, **kwargs):
            if path.suffix == ".json":
                raise OSError("metadata write failed")
            return original_write_text(path, data, *args, **kwargs)

        monkeypatch.setattr(type(tmp_path), "write_text", fail_metadata_write)

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                response = client.post("/api/v1/reports/qc/export", json={})

        assert response.status_code == 500
        assert list(tmp_path.glob("*.csv")) == []
        assert list(tmp_path.glob("*.json")) == []

    def test_cleanup_reclaims_only_old_orphan_csvs(self, tmp_path):
        """无 metadata 的 CSV 仅在超过 TTL 后回收，避免清理正在创建的导出。"""
        old_orphan = tmp_path / f"{uuid4().hex}.csv"
        young_orphan = tmp_path / f"{uuid4().hex}.csv"
        old_orphan.write_text("record_id\nold\n", encoding="utf-8")
        young_orphan.write_text("record_id\nyoung\n", encoding="utf-8")
        current_time = datetime.now(timezone.utc)
        old_timestamp = (current_time - reports_module._QC_EXPORT_TTL - timedelta(seconds=1)).timestamp()
        os.utime(old_orphan, (old_timestamp, old_timestamp))

        reports_module._cleanup_expired_exports(now=current_time)

        assert not old_orphan.exists()
        assert young_orphan.exists()

    def test_cleanup_preserves_valid_report_even_if_csv_is_old(self, tmp_path):
        """仍有有效 metadata 的报表不应被孤儿回收逻辑删除。"""
        export_id = uuid4().hex
        csv_path = tmp_path / f"{export_id}.csv"
        metadata_path = tmp_path / f"{export_id}.json"
        csv_path.write_text("record_id\nrecord-1\n", encoding="utf-8")
        current_time = datetime.now(timezone.utc)
        old_timestamp = (current_time - reports_module._QC_EXPORT_TTL - timedelta(seconds=1)).timestamp()
        os.utime(csv_path, (old_timestamp, old_timestamp))
        metadata_path.write_text(
            json.dumps({"expires_at": (current_time + timedelta(minutes=5)).isoformat()}),
            encoding="utf-8",
        )

        reports_module._cleanup_expired_exports(now=current_time)

        assert csv_path.exists()
        assert metadata_path.exists()

    def test_read_export_artifact_rejects_plain_file_replaced_before_open(self, monkeypatch, tmp_path):
        """首次检查后、open 前替换为另一普通文件时必须拒绝。"""
        artifact_path = tmp_path / "artifact.csv"
        replacement_path = tmp_path / "replacement.csv"
        artifact_path.write_bytes(b"original")
        replacement_path.write_bytes(b"replacement")
        original_open = os.open

        def replace_before_open(path, flags):
            os.replace(replacement_path, artifact_path)
            return original_open(path, flags)

        monkeypatch.setattr(reports_module.os, "open", replace_before_open)

        with pytest.raises(FileNotFoundError):
            reports_module._read_export_artifact(artifact_path)

    def test_read_export_artifact_rejects_plain_file_replaced_after_open(self, monkeypatch, tmp_path):
        """打开描述符后、复查目录项前换代时必须拒绝。"""
        artifact_path = tmp_path / "artifact.csv"
        replacement_path = tmp_path / "replacement.csv"
        artifact_path.write_bytes(b"original")
        replacement_path.write_bytes(b"replacement")
        original_open = os.open
        path_type = type(artifact_path)
        original_lstat = path_type.lstat

        def replace_after_open(path, flags):
            descriptor = original_open(path, flags)
            # Windows 默认不允许替换仍被打开的文件。用真实替代文件的目录项
            # 模拟 open 之后发生的原子换代，验证描述符和当前目录项的身份绑定。
            monkeypatch.setattr(
                path_type,
                "lstat",
                lambda candidate: replacement_path.lstat()
                if candidate == artifact_path
                else original_lstat(candidate),
            )
            return descriptor

        monkeypatch.setattr(reports_module.os, "open", replace_after_open)

        with pytest.raises(FileNotFoundError):
            reports_module._read_export_artifact(artifact_path)

    @pytest.mark.parametrize("artifact_suffix", (".json", ".csv"))
    def test_qc_export_download_rejects_link_or_reparse_artifacts(
        self,
        client,
        monkeypatch,
        tmp_path,
        artifact_suffix,
    ):
        """metadata 和 CSV 任一为链接入口时，下载都必须拒绝。"""

        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                created = client.post("/api/v1/reports/qc/export", json={})

        assert created.status_code == 200
        payload = created.json()["data"]
        linked_path = tmp_path / f"{payload['export_id']}{artifact_suffix}"
        path_type = type(linked_path)
        original_is_symlink = path_type.is_symlink
        monkeypatch.setattr(
            path_type,
            "is_symlink",
            lambda path: path == linked_path or original_is_symlink(path),
        )

        assert client.get(payload["download_url"]).status_code == 404

    @pytest.mark.asyncio
    async def test_qc_summary_trace_id(self, client):
        """测试响应包含 trace_id"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    assert "trace_id" in data

    @pytest.mark.asyncio
    async def test_qc_summary_includes_top_categories(self, client):
        """测试汇总返回真实问题分类统计。"""
        from app.routers import reports as reports_module

        reports_module._QC_SUMMARY_CACHE = None
        reports_module._QC_SUMMARY_CACHE_TS = 0.0

        mock_supabase = MagicMock()
        mock_view_response = MagicMock()
        mock_view_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 4,
                "passed_count": 2,
                "warning_count": 1,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 88.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]
        mock_rules_response = MagicMock()
        mock_rules_response.data = [{"id": "rule-1"}]
        mock_defects_response = MagicMock()
        mock_defects_response.data = [
            {"category": "病程记录"},
            {"category": "病程记录"},
            {"category": "病案首页"},
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute") as mock_execute:
                mock_execute.side_effect = [
                    mock_view_response,
                    mock_rules_response,
                    mock_defects_response,
                ]
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.85,
                        "avg_api_time": 1.2,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["top_categories"] == [
            {"category": "病程记录", "issue_count": 2},
            {"category": "病案首页", "issue_count": 1},
        ]

    @pytest.mark.asyncio
    async def test_qc_trend_returns_bucketed_items(self, client):
        """测试趋势接口返回按周期聚合的数据。"""
        mock_supabase = MagicMock()
        now = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
        mock_trend_response = MagicMock()
        mock_trend_response.data = [
            {
                "record_id": "record-1",
                "passed_count": 3,
                "warning_count": 1,
                "failed_count": 0,
                "pending_count": 0,
                "avg_qc_score": 90,
                "last_analyzed_time": now.isoformat(),
            },
            {
                "record_id": "record-2",
                "passed_count": 1,
                "warning_count": 1,
                "failed_count": 0,
                "pending_count": 0,
                "avg_qc_score": 80,
                "last_analyzed_time": (now - timedelta(days=1)).isoformat(),
            },
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_trend_response):
                response = client.get("/api/v1/reports/qc/trend?period=week")

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["period"] == "week"
        assert len(payload["items"]) == 7
        assert any(item["record_count"] == 1 for item in payload["items"])
        assert any(item["average_score"] == 90 for item in payload["items"])

    @pytest.mark.asyncio
    async def test_qc_trend_invalid_period(self, client):
        """测试趋势接口参数校验。"""
        response = client.get("/api/v1/reports/qc/trend?period=year")
        assert response.status_code == 400
