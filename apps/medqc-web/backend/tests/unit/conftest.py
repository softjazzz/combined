"""单元测试共享 fixtures。

LX0609 质量门以 --confcutdir=tests/unit 运行，不加载上层 tests/conftest.py；
需要在质量门内生效的隔离 fixture 放在这里。
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_consultation_opinion_freeze(tmp_path, monkeypatch):
    """会诊意见事实冻结按用例隔离：避免用例之间复用第一阶段事实，也不写入 data/ 目录。"""

    monkeypatch.setenv(
        "LUXIAN_0609_OPINION_FREEZE_DIR", str(tmp_path / "opinion-freeze")
    )


@pytest.fixture
def workspace_tables_without_database(monkeypatch):
    """自定义质控工作区服务只取表定义，不连接数据库（按文件以 usefixtures 引用）。

    写入口构造 CustomQCWorkspaceService 时会对真实库执行 PostgreSQL 专用的建表/补列
    语句。会话全部为替身的合同用例此前依赖同进程内其他用例先缓存表定义（执行顺序
    依赖），在 SQLite 临时库或无库环境下直接失败。
    """

    import app.services.custom_qc_workspace_service as workspace_module

    drafts_table = workspace_module._drafts_table
    batch_jobs_table = workspace_module._batch_jobs_table
    monkeypatch.setattr(workspace_module, "engine", object())
    monkeypatch.setattr(workspace_module, "_drafts_table", lambda **_kwargs: drafts_table(readonly=True))
    monkeypatch.setattr(workspace_module, "_batch_jobs_table", lambda **_kwargs: batch_jobs_table(readonly=True))
