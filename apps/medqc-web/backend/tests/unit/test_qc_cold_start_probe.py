"""冷启动只开固定、验签且重新隔离的探针，不开放通用进程执行。"""

import subprocess

import pytest

from tests.scheduler_support import isolation


@pytest.fixture(autouse=True)
def parent_offline_guard():
    with isolation.OfflineIsolation():
        yield


def test_tampered_probe_is_rejected_before_any_process(monkeypatch):
    calls = []
    monkeypatch.setattr(isolation, "_COLD_START_PROBE_SHA256", "0" * 64)
    monkeypatch.setattr(
        isolation, "_REAL_SUBPROCESS_POPEN", lambda *a, **k: calls.append((a, k))
    )
    with pytest.raises(isolation.OfflineIsolationError, match="reviewed digest"):
        isolation.run_preproduction_cold_start_probe()
    assert calls == []


def test_cold_start_api_accepts_no_arbitrary_script_or_arguments():
    with pytest.raises(TypeError):
        isolation.run_preproduction_cold_start_probe("arbitrary script")
    with pytest.raises(isolation.OfflineIsolationError):
        subprocess.run(["not-allowed"])
    with pytest.raises(isolation.OfflineIsolationError):
        subprocess.Popen(["not-allowed"])


def test_probe_launch_is_isolated_and_keeps_only_minimal_environment(monkeypatch):
    calls = []
    monkeypatch.setenv("LLM_API_KEY", "DO_NOT_INHERIT")
    monkeypatch.setenv("CUSTOM_TOKEN", "DO_NOT_INHERIT")
    monkeypatch.setenv("HTTP_PROXY", "DO_NOT_INHERIT")

    class Fake:
        returncode = 0

        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def communicate(self, timeout):
            assert timeout == 30
            return "fixed", ""

    monkeypatch.setattr(isolation, "_REAL_SUBPROCESS_POPEN", Fake)
    result = isolation.run_preproduction_cold_start_probe()
    command, options = calls[0]
    assert result.returncode == 0 and result.stdout == "fixed"
    assert command[1:7] == ["-I", "-S", "-B", "-X", "utf8", "-c"]
    assert options["shell"] is False and options["encoding"] == "utf-8"
    assert options["env"]["DATABASE_URL"] == options["env"]["REMOTE_DB_URL"] == ""
    assert options["env"]["MEDQC_ALLOW_REAL_LLM"] == "0"
    assert not {"LLM_API_KEY", "CUSTOM_TOKEN", "HTTP_PROXY"}.intersection(
        options["env"]
    )
    assert "DO_NOT_INHERIT" not in repr(command)
    assert "with OfflineIsolation():" in command[-1]
    # 调用helper不改变外层普通进程护栏，环境也不被其最小化副作用修改。
    with pytest.raises(isolation.OfflineIsolationError):
        subprocess.run(["not-allowed"])
    assert __import__("os").environ["CUSTOM_TOKEN"] == "DO_NOT_INHERIT"


def test_probe_timeout_kills_only_owned_process(monkeypatch):
    calls = []

    class Fake:
        returncode = None

        def __init__(self, command, **_):
            self.command = command
            self.killed = False
            self.attempt = 0
            calls.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def communicate(self, timeout=None):
            self.attempt += 1
            if self.attempt == 1:
                raise subprocess.TimeoutExpired(self.command, 30)
            assert self.killed
            return "", "stopped"

        def kill(self):
            self.killed = True
            self.returncode = -1

    monkeypatch.setattr(isolation, "_REAL_SUBPROCESS_POPEN", Fake)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        isolation.run_preproduction_cold_start_probe()
    assert len(calls) == 1 and calls[0].killed and calls[0].attempt == 2
    assert caught.value.timeout == 30


def test_ci_runs_request_audit_in_offline_mode_for_review_branch():
    from pathlib import Path
    import yaml

    root = Path(__file__).resolve().parents[5]
    workflow = yaml.load(
        (root / ".github/workflows/qc-scheduler-isolation.yml").read_text(
            encoding="utf-8"
        ),
        Loader=yaml.BaseLoader,
    )
    assert (
        "codex/strata-review-base-20261031"
        in workflow["on"]["pull_request"]["branches"]
    )
    assert "codex/**" in workflow["on"]["push"]["branches"]
    job = workflow["jobs"]["qc-scheduler-isolation"]
    assert job["env"]["MEDQC_ALLOW_REAL_LLM"] == "0"
    steps = [
        step
        for step in job["steps"]
        if "--suite llm-request-audit" in step.get("run", "")
    ]
    assert len(steps) == 1
    assert "--profile offline" in steps[0]["run"]
    assert "if" not in steps[0] and "continue-on-error" not in steps[0]
