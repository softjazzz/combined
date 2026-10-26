"""离线验收必须同时有目标规则、应答精确匹配和既有结果不变证明。"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/apply_c18_assessment_hotfix.py"
spec = importlib.util.spec_from_file_location("apply_c18_assessment_hotfix", SCRIPT)
hotfix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hotfix)


def events():
    return [{"event": "replay_matched"}, {"event": "replay_matched"},
            {"event": "finished", "results": [{"rule": "LX0609-07-01-02", "status": "non_compliant"}]},
            {"event": "existing_results_check", "items_unchanged": True}]


def test_requires_exact_replay_and_unchanged_existing_results():
    assert hotfix.replay_verified(events(), 2)


@pytest.mark.parametrize("mutation", ["failed", "wrong_rule", "missing_replay", "changed", "diagnostic_error"])
def test_failed_acceptance_cannot_keep_patch(mutation):
    rows = events()
    if mutation == "failed":
        rows[2]["results"][0]["status"] = "technical_error"
    elif mutation == "wrong_rule":
        rows[2]["results"][0]["rule"] = "LX0609-07-04-01"
    elif mutation == "missing_replay":
        rows.pop(0)
    elif mutation == "changed":
        rows[3]["items_unchanged"] = False
    else:
        rows.append({"event": "diagnostic_error"})
    assert not hotfix.replay_verified(rows, 2)


@pytest.mark.parametrize("outcome", ["success", "failed_acceptance", "unknown_source"])
def test_install_backs_up_and_restores_on_replay_failure(tmp_path, monkeypatch, outcome):
    kit = tmp_path / "kit"
    kit.mkdir()
    backend = tmp_path / "backend"
    target = backend / "app/services/luxian_0609/native_transfusion_execution.py"
    target.parent.mkdir(parents=True)
    original, fixed = b"OLD = True\n", b"FIXED = True\n"
    installed = b"UNRELATED = True\n" if outcome == "unknown_source" else original
    target.write_bytes(installed)
    (kit / "native_transfusion_execution.fixed.py").write_bytes(fixed)
    (kit / "patch-manifest.json").write_text(json.dumps({
        "original_sha256": hotfix.sha256(original), "fixed_sha256": hotfix.sha256(fixed),
        "patch": "test-only",
    }), encoding="utf-8")
    replay = tmp_path / "recordings.json"
    replay.write_text("[{}, {}]", encoding="utf-8")
    monkeypatch.setattr(hotfix, "__file__", str(kit / "installer.py"))
    monkeypatch.setattr(hotfix.sys, "argv", ["installer", "--backend", str(backend),
        "--replay-file", str(replay), "--backup-dir", str(tmp_path / "backups"),
        "--output-dir", str(tmp_path / "reports")])

    def run(command, check):
        assert target.read_bytes() == fixed
        assert list((tmp_path / "backups").glob("*/native_transfusion_execution.py"))[0].read_bytes() == original
        report = Path(command[command.index("--output") + 1])
        report.write_text("\n".join(json.dumps(row) for row in events()), encoding="utf-8")
        return SimpleNamespace(returncode=0 if outcome == "success" else 1)

    monkeypatch.setattr(hotfix.subprocess, "run", run)
    if outcome == "success":
        assert hotfix.main() == 0
        assert target.read_bytes() == fixed
    else:
        with pytest.raises(ValueError):
            hotfix.main()
        assert target.read_bytes() == installed
