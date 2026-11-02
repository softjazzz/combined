from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from medqc_ingest.control.cli import build_parser, main
from medqc_ingest.control.models import ControlError


def test_parser_has_explicit_manual_fields_and_replay_default():
    args = build_parser().parse_args(
        [
            "--config",
            "control.json",
            "job",
            "submit",
            "--profile",
            "core13",
            "--interface",
            "web.mr",
            "--start",
            "2026-10-26",
            "--end",
            "2026-10-28",
            "--idempotency-key",
            "manual-1",
        ]
    )
    assert args.config == Path("control.json")
    assert args.mode == "replay" and args.publish is None
    assert args.interfaces == ["web.mr"] and args.command == "job" and args.action == "submit"


def test_config_and_token_file_can_follow_command_for_direct_launchers():
    args = build_parser().parse_args(
        ["job", "show", "job-id", "--config", "control.json", "--token-file", "operator-token"]
    )
    assert args.config == Path("control.json") and args.token_file == Path("operator-token")
    args = build_parser().parse_args(["worker", "--once", "--config", "worker.json"])
    assert args.once is True and args.config == Path("worker.json")


def test_publish_only_parser_does_not_require_source_dates():
    args = build_parser().parse_args(
        [
            "job",
            "submit",
            "--profile",
            "core13",
            "--interface",
            "web.mr",
            "--mode",
            "publish_only",
            "--idempotency-key",
            "publish-1",
        ]
    )
    assert args.start_date is None and args.end_date is None


def test_cli_delegates_only_control_arguments_to_bootstrap():
    with patch("medqc_ingest.control.bootstrap.dispatch", return_value=0) as dispatch:
        assert main(["api", "--config", "api.json"]) == 0
    assert dispatch.call_args.args[0].command == "api"


def test_cli_errors_are_controlled_and_no_driver_text_is_printed(capsys):
    with patch(
        "medqc_ingest.control.bootstrap.dispatch", side_effect=RuntimeError("fictional-secret-body")
    ):
        assert main(["job", "list"]) == 1
    out = capsys.readouterr()
    assert "fictional-secret-body" not in out.err
    assert json.loads(out.err)["location"] == "control_cli"
    with patch(
        "medqc_ingest.control.bootstrap.dispatch",
        side_effect=ControlError("forbidden", "actor_permission", 403),
    ):
        assert main(["job", "list"]) == 1
    assert json.loads(capsys.readouterr().err)["code"] == "forbidden"


def test_no_plaintext_token_password_or_sql_argument():
    for forbidden in ("--token", "--password", "--sql", "--dsn"):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["job", "list", forbidden, "fictional-secret"])


def test_schedule_modification_requires_version_and_file():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["schedule", "enable", "schedule-id"])
    args = build_parser().parse_args(
        ["schedule", "update", "schedule-id", "--version", "2", "--schedule-file", "schedule.json"]
    )
    assert args.version == 2 and args.schedule_file == Path("schedule.json")


def test_reconcile_requires_controlled_decision_and_proof_file():
    parser = build_parser()
    args = parser.parse_args(
        ["job", "reconcile", "job-id", "--decision", "retry", "--proof-file", "proof.json"]
    )
    assert args.action == "reconcile" and args.decision == "retry"
    assert args.proof_file == Path("proof.json")
    for remaining in (
        [],
        ["--decision", "retry"],
        ["--decision", "force", "--proof-file", "proof.json"],
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(["job", "reconcile", "job-id", *remaining])
