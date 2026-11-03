"""配置快照保护：合成环境、临时文件身份，不读取开发机.env。"""
import asyncio
import threading

import pytest

from app.core import settings as module


@pytest.fixture
def counted_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('JWT_SECRET', 'synthetic-snapshot-test')
    calls = []
    original = module.Settings

    class Counted(original):
        def __init__(self, **kwargs):
            calls.append(1)
            super().__init__(**kwargs)

    monkeypatch.setattr(module, 'Settings', Counted)
    return calls


def test_repeated_settings_are_parsed_once_but_return_independent_values(counted_settings):
    first = module.get_settings()
    first.LLM_VISIBLE_PROVIDERS.append('poison')
    first.JWT_SECRET = 'caller-local-only'
    second = module.get_settings()
    assert second is not first
    assert second.JWT_SECRET == 'synthetic-snapshot-test'
    assert 'poison' not in second.LLM_VISIBLE_PROVIDERS
    assert len(counted_settings) == 1


def test_environment_file_and_explicit_invalidation_refresh_snapshot(counted_settings, monkeypatch, tmp_path):
    module.get_settings()
    monkeypatch.setenv('LLM_MODEL', 'synthetic-small')
    assert module.get_settings().LLM_MODEL == 'synthetic-small'
    assert len(counted_settings) == 2
    # offline runner仍屏蔽dotenv内容；这里只核对文件身份变动触发重新解析。
    (tmp_path / '.env').write_text('SYNTHETIC=1\n', encoding='utf-8')
    module.get_settings()
    assert len(counted_settings) == 3
    module.clear_settings_snapshot()
    module.get_settings()
    assert len(counted_settings) == 4


def test_invalid_new_environment_cannot_reuse_previous_valid_snapshot(counted_settings, monkeypatch):
    module.get_settings()
    monkeypatch.setenv('JWT_SECRET', '')
    with pytest.raises(RuntimeError, match='JWT_SECRET'):
        module.get_settings()
    with pytest.raises(RuntimeError, match='JWT_SECRET'):
        module.get_settings()
    assert len(counted_settings) == 3


@pytest.mark.asyncio
async def test_config_database_wait_does_not_block_event_loop(monkeypatch):
    from app.services import llm_config_loader as loader
    entered, release = threading.Event(), threading.Event()

    class Query:
        def __getattr__(self, name):
            return lambda *a, **kw: self

        def execute(self):
            entered.set()
            assert release.wait(1), '同步execute阻塞了事件循环，释放任务无法运行'
            return type('Response', (), {'data': []})()

    class Client:
        def table(self, name):
            assert name == 'public.user_llm_configs'
            return Query()

    async def release_from_loop():
        for _ in range(100):
            if entered.is_set():
                release.set()
                return
            await asyncio.sleep(.002)
        pytest.fail('未进入配置读取')

    result, _ = await asyncio.gather(loader.LLMConfigLoader._load_from_database(Client(), 'default'), release_from_loop())
    assert result is None
