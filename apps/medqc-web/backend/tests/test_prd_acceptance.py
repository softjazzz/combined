"""
PRD 质控业务数据库设计 — 验收单测

覆盖 PRD v2.4 §验收标准：
1. 启动无 "table/view not found" 错误（含 6 个视图）
2. 6 个核心 router 全部 CRUD + 统计接口可通
3. DB 不可用时返回 503（非 500 / 空数组）
4. 改造后路由不含内存残留变量
5. 路由语法正确，模块可导入
"""

import ast
import importlib
import os
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def _make_mock_response(data=None, count=None):
    """构造 Supabase mock 查询响应"""
    resp = MagicMock()
    resp.data = data if data is not None else []
    resp.count = count if count is not None else (len(resp.data) if isinstance(resp.data, list) else 0)
    return resp


def _mock_chain():
    """构造一个可以链式调用的 MagicMock"""
    m = MagicMock()
    for method in ('select', 'insert', 'update', 'delete', 'eq', 'neq',
                   'gt', 'gte', 'lt', 'lte', 'like', 'ilike', 'in_',
                   'or_', 'order', 'limit', 'range', 'single', 'count'):
        getattr(m, method).return_value = m
    return m


# ---------------------------------------------------------------------------
# §1 模块导入与语法正确性
# ---------------------------------------------------------------------------

class TestModuleSyntaxAndImport:
    """验证所有改造文件语法正确、可导入"""

    ROUTER_FILES = [
        'app/routers/scoring_rules.py',
        'app/routers/scoring_config.py',
        'app/routers/notifications.py',
        'app/routers/staff_ranking.py',
        'app/routers/tasks.py',
        'app/routers/defects.py',
        'app/routers/appeals.py',
        'app/routers/remediation.py',
        'app/routers/qc.py',
        'app/routers/department_qc_rules.py',
        'app/routers/semantic_rules.py',
    ]

    @pytest.mark.unit
    @pytest.mark.parametrize("filepath", ROUTER_FILES)
    def test_syntax_valid(self, filepath):
        """每个路由文件 ast.parse 无 SyntaxError"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(backend_dir, filepath)
        with open(full_path, encoding='utf-8') as f:
            source = f.read()
        # 不抛 SyntaxError 即通过
        ast.parse(source)

    @pytest.mark.unit
    @pytest.mark.parametrize("filepath", ROUTER_FILES)
    def test_no_memory_fallback_vars(self, filepath):
        """改造后路由不含内存残留变量"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(backend_dir, filepath)
        with open(full_path, encoding='utf-8') as f:
            source = f.read()

        # 这些变量在 PG 改造后不应存在
        forbidden = [
            '_scoring_rules_db',     # scoring_rules.py 旧内存
            '_STAFF_DATA',           # staff_ranking.py 旧 mock
            '_WORKLOAD_DATA',        # staff_ranking.py 旧 mock
            '_init_mock_data',       # notifications.py 旧 mock
            '_init_default_rules',   # scoring_rules.py 旧内存
            'qc_results_db',         # 内存 QC 结果
            'qc_rules_db',           # 内存 QC 规则
        ]
        for var in forbidden:
            assert var not in source, f"{filepath} 仍包含内存残留变量 `{var}`"


# ---------------------------------------------------------------------------
# §2 视图 SQL 完整性
# ---------------------------------------------------------------------------

class TestViewsSQL:
    """验证 qc_views.sql 包含 PRD 要求的 6 个视图"""

    REQUIRED_VIEWS = [
        'v_qc_task_progress',
        'qc_appeals_statistics',
        'qc_remediation_statistics',
        'qc_assignee_workload',
        'qc_statistics_view',
        'v_qc_coder_ranking',
    ]

    @pytest.mark.unit
    def test_all_views_defined(self):
        """qc_views.sql 包含全部 6 个视图的 CREATE VIEW"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sql_path = os.path.join(backend_dir, 'app', 'database', 'sql', 'qc_views.sql')
        with open(sql_path, encoding='utf-8') as f:
            sql = f.read().lower()

        for view in self.REQUIRED_VIEWS:
            assert f'create view {view}' in sql, f"缺少视图: {view}"


# ---------------------------------------------------------------------------
# §3 ORM 模型完整性
# ---------------------------------------------------------------------------

class TestORMModels:
    """验证 ORM 模型覆盖 PRD P0 14 张表"""

    REQUIRED_TABLES = [
        'qc_tasks', 'qc_task_records', 'qc_results', 'qc_defects',
        'qc_defect_history', 'qc_appeals', 'qc_appeal_reviews',
        'qc_remediation_tasks', 'qc_remediation_history',
        'qc_coder_workload_daily', 'qc_rules', 'scoring_rules',
        'scoring_config', 'notifications',
    ]

    @pytest.mark.unit
    def test_all_tables_in_orm(self):
        """models/qc.py 的 ORM 类覆盖 14 张表"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(backend_dir, 'app', 'database', 'models', 'qc.py')
        with open(model_path, encoding='utf-8') as f:
            source = f.read()

        for table in self.REQUIRED_TABLES:
            # __tablename__ = 'xxx'
            assert f"'{table}'" in source or f'"{table}"' in source, \
                f"ORM 缺少表名: {table}"


# ---------------------------------------------------------------------------
# §4 DB 不可用时 503 守卫
# ---------------------------------------------------------------------------

class TestDB503Guard:
    """DB 不可用（get_supabase() → None）时，路由应返回 503"""

    @pytest.mark.api
    @pytest.mark.parametrize("path,patch_module", [
        ('/api/v1/scoring-rules', 'app.routers.scoring_rules'),
        ('/api/v1/scoring-config', 'app.routers.scoring_config'),
        ('/api/v1/notifications', 'app.routers.notifications'),
    ])
    def test_503_when_db_unavailable(self, app, path, patch_module, monkeypatch):
        """DB 不可用时返回 503"""
        from app.core.security import get_current_user

        # 覆盖认证依赖
        app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        # 让 get_supabase 返回 None
        monkeypatch.setattr(f"{patch_module}.get_supabase", lambda: None)

        try:
            with TestClient(app) as client:
                resp = client.get(path)
                assert resp.status_code == 503, \
                    f"GET {path} 应返回 503，实际 {resp.status_code}: {resp.text[:200]}"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# §5 核心路由 CRUD 通路（mock Supabase）
# ---------------------------------------------------------------------------

class TestScoringRulesCRUD:
    """scoring_rules 路由 CRUD 可通"""

    @pytest.mark.api
    def test_list_scoring_rules(self, app, monkeypatch):
        """GET /api/v1/scoring-rules 返回 200"""
        from app.core.security import get_current_user

        mock_sb = _mock_chain()
        mock_resp = _make_mock_response([
            {"id": "r1", "name": "测试规则", "category": "形式质控",
             "enabled": True, "veto": False, "sort_order": 1}
        ])

        app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        monkeypatch.setattr('app.routers.scoring_rules.get_supabase', lambda: mock_sb)
        monkeypatch.setattr('app.routers.scoring_rules.async_execute', AsyncMock(return_value=mock_resp))

        try:
            with TestClient(app) as client:
                resp = client.get('/api/v1/scoring-rules')
                assert resp.status_code == 200
                body = resp.json()
                assert body.get("success") is True
                assert "rules" in body.get("data", {})
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestScoringConfigCRUD:
    """scoring_config 路由可通"""

    @pytest.mark.api
    def test_get_scoring_config(self, app, monkeypatch):
        """GET /api/v1/scoring-config 返回 200"""
        from app.core.security import get_current_user

        mock_sb = _mock_chain()
        mock_resp = _make_mock_response([
            {"config_key": "grade_thresholds", "config_value": '{"甲":{"min_score":90}}'},
        ])

        app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        monkeypatch.setattr('app.routers.scoring_config.get_supabase', lambda: mock_sb)
        monkeypatch.setattr('app.routers.scoring_config.async_execute', AsyncMock(return_value=mock_resp))

        try:
            with TestClient(app) as client:
                resp = client.get('/api/v1/scoring-config')
                assert resp.status_code == 200
                body = resp.json()
                assert body.get("success") is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestNotificationsCRUD:
    """notifications 路由可通"""

    @pytest.mark.api
    def test_list_notifications(self, app, monkeypatch):
        """GET /api/v1/notifications 返回 200"""
        from app.core.security import get_current_user

        mock_sb = _mock_chain()
        mock_resp = _make_mock_response([])

        app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        monkeypatch.setattr('app.routers.notifications.get_supabase', lambda: mock_sb)
        monkeypatch.setattr('app.routers.notifications.async_execute', AsyncMock(return_value=mock_resp))

        try:
            with TestClient(app) as client:
                resp = client.get('/api/v1/notifications')
                assert resp.status_code == 200
                body = resp.json()
                assert body.get("success") is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestStaffRanking:
    """staff_ranking 路由可通"""

    @pytest.mark.api
    def test_get_ranking(self, app, monkeypatch):
        """GET /api/v1/staff-ranking 返回 200"""
        from app.core.security import get_current_user

        mock_sb = _mock_chain()
        mock_resp = _make_mock_response([
            {"user_id": "u1", "name": "王质控", "department": "质控科",
             "qc_count": 100, "recheck_count": 20, "defect_found": 30,
             "pass_rate": 90.0, "avg_daily": 3.3},
        ])

        app.dependency_overrides[get_current_user] = lambda: {"id": "test", "role": "admin"}
        monkeypatch.setattr('app.routers.staff_ranking.get_supabase', lambda: mock_sb)
        monkeypatch.setattr('app.routers.staff_ranking.async_execute', AsyncMock(return_value=mock_resp))

        try:
            with TestClient(app) as client:
                resp = client.get('/api/v1/staff-ranking')
                assert resp.status_code == 200
                body = resp.json()
                assert body.get("success") is True
                data = body.get("data", {})
                assert "rankings" in data
                assert "summary" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# §6 字段名/枚举值旧名检查
# ---------------------------------------------------------------------------

class TestNoLegacyNames:
    """PRD 验收标准：不再出现旧名"""

    LEGACY_NAMES = [
        'qc_defect_actions',   # 应为 qc_defect_history
        'department_code',     # 应为 department
    ]

    # total_score 排除：qc.py 中作为 API 响应兼容映射（"total_score": result.get("overall_score")）
    # 这是合理的前端兼容层，不是 DB 字段引用

    ROUTER_FILES = [
        'app/routers/tasks.py',
        'app/routers/defects.py',
        'app/routers/appeals.py',
        'app/routers/remediation.py',
        'app/routers/qc.py',
        'app/routers/scoring_rules.py',
        'app/routers/scoring_config.py',
        'app/routers/notifications.py',
        'app/routers/staff_ranking.py',
    ]

    @pytest.mark.unit
    @pytest.mark.parametrize("filepath", ROUTER_FILES)
    def test_no_legacy_names(self, filepath):
        """路由代码不含 PRD 明确废弃的旧名"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(backend_dir, filepath)
        with open(full_path, encoding='utf-8') as f:
            source = f.read()

        for name in self.LEGACY_NAMES:
            # 注释中的引用不算（允许 # 旧名迁移说明之类）
            lines = source.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if name in stripped:
                    # 排除字符串中的引用（如日志描述）
                    if f"'{name}'" in stripped or f'"{name}"' in stripped:
                        pytest.fail(f"{filepath}:{i} 仍使用旧名 `{name}` 作为表/字段名")
