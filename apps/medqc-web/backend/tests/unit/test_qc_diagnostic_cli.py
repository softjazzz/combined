"""CLI 版本门禁与输出泄露回归；仅匿名包与模拟本地 Git。"""

import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli():
    return _module("diagnostic_cli_under_test", Path(__file__).parents[2] / "scripts" / "qc_diagnostic.py")


@pytest.fixture
def documents():
    helper = _module("diagnostic_contract_fixture", Path(__file__).with_name("test_qc_diagnostic_contracts.py"))
    return helper.sample_documents()


def _git(monkeypatch, cli, *, commit="a" * 40, dirty=""):
    calls = []
    answers = iter([commit, dirty])

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=next(answers))

    monkeypatch.setattr(cli.subprocess, "run", run)
    return calls


def test_local_git_commands_are_fixed_without_package_arguments(cli, monkeypatch):
    calls = _git(monkeypatch, cli)
    assert cli._local_commit() == "a" * 40
    prefix = ["git", "-c", "core.fsmonitor=false", "-C", str(cli.BACKEND)]
    assert calls[0][0] == prefix + ["rev-parse", "HEAD"]
    assert calls[1][0] == prefix + [
        "status", "--porcelain", "--untracked-files=all", "--", "app", "scripts/qc_diagnostic.py",
    ]
    for _, options in calls:
        assert options == {"capture_output": True, "text": True, "check": True, "timeout": 10}


def test_local_dirty_backend_refuses_version_claim(cli, monkeypatch):
    _git(monkeypatch, cli, dirty=" M app/private-patient.py")
    with pytest.raises(DiagnosticPackageError) as error:
        cli._local_commit()
    assert str(error.value) == "local_backend_dirty"


@pytest.mark.parametrize("failure", [
    OSError("secret-path"),
    subprocess.CalledProcessError(1, "secret-command", stderr="secret-output"),
    subprocess.TimeoutExpired("secret-command", 10),
], ids=["oserror", "exit", "timeout"])
def test_git_failure_is_safe(cli, monkeypatch, failure):
    def run(*args, **kwargs):
        raise failure
    monkeypatch.setattr(cli.subprocess, "run", run)
    with pytest.raises(DiagnosticPackageError) as error:
        cli._local_commit()
    assert str(error.value) == "local_version_unavailable"


def test_inspect_does_not_require_git_or_echo_observation(cli, documents, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_diagnostic_package", lambda path: documents)
    monkeypatch.setattr(cli, "_local_commit", lambda: pytest.fail("inspect called Git"))
    assert cli.main(["inspect", "untrusted-name.zip"]) == 0
    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert summary["rule_ids"] == ["LX0609-04-03-01"]
    assert summary["privacy_verified"] is False
    assert documents["results.json"]["rules"][0]["findings"] not in output.out
    assert "untrusted-name" not in output.out + output.err


def test_bad_package_prints_only_fixed_code(cli, monkeypatch, capsys):
    def load(_path):
        raise DiagnosticPackageError("invalid_zip")
    monkeypatch.setattr(cli, "load_diagnostic_package", load)
    assert cli.main(["inspect", "private-name.zip"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {"error": "invalid_zip"}


def test_unexpected_failure_does_not_echo_exception(cli, monkeypatch, capsys):
    def load(_path):
        raise RuntimeError("sensitive-user-input")
    monkeypatch.setattr(cli, "load_diagnostic_package", load)
    assert cli.main(["inspect", "private-name.zip"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {"error": "diagnostic_failed"}


def test_different_commit_requires_explicit_comparison(cli, documents, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_diagnostic_package", lambda path: documents)
    _git(monkeypatch, cli, commit="b" * 40)
    assert cli.main(["replay", "anonymous.zip"]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "version_mismatch"}


def test_explicit_compare_current_labels_comparison(cli, documents, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_diagnostic_package", lambda path: documents)
    _git(monkeypatch, cli, commit="b" * 40)
    assert cli.main(["replay", "anonymous.zip", "--compare-current"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "cross_version_comparison"
    assert result["same_version"] is False
    assert result["clinical_correctness_verified"] is False


def test_compare_flag_does_not_bypass_dirty_backend(cli, documents, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_diagnostic_package", lambda path: documents)
    _git(monkeypatch, cli, dirty=" M app/renderer.py")
    assert cli.main(["replay", "anonymous.zip", "--compare-current"]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "local_backend_dirty"}
