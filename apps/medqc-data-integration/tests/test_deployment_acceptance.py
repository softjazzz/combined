"""十三来源调度、凭据边界和验收故障语义；不访问真实数据。"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from medqc_ingest.config import (
    PassfilePostgresSettings,
    PostgresSettings,
    Settings,
    SourceSettings,
    source_zone,
)
from medqc_ingest.daily import run_daily
from medqc_ingest.deployment_acceptance import _FailBeforeCommit, _RowsSource, publish_twice
from medqc_ingest.domain import IngestError
from medqc_ingest.repositories.postgres import _psycopg

ROOT = Path(__file__).resolve().parents[1]


def settings() -> Settings:
    source = SourceSettings(
        "odbc", "fixture", 1972, "fixture", "fixture", Path("unused"), "fixture", None, None, ()
    )
    return Settings(
        source,
        PostgresSettings(
            "127.0.0.1", 5432, "medqc_ingest_takeover_20261030123456", "fixture", Path("unused")
        ),
        PostgresSettings(
            "127.0.0.1", 5432, "medqc_cdm_takeover_20261030123456", "fixture", Path("unused")
        ),
        1000,
        60,
        "Asia/Shanghai",
    )


class TestDaily(unittest.TestCase):
    def run_job(self, **kwargs: Any) -> tuple[Any, Mock, Mock]:
        with (
            patch("medqc_ingest.daily.next_source_day", return_value=date(2026, 10, 29)),
            patch("medqc_ingest.daily.PostgresIngestRepository"),
            patch("medqc_ingest.daily.PostgresCdmRepository"),
            patch("medqc_ingest.daily.ExtractService") as extract,
            patch("medqc_ingest.daily.PublishService") as publish,
        ):
            extract.return_value.run.return_value = SimpleNamespace(
                counts={"fetched": 1, "inserted": 0, "updated": 0, "unchanged": 1}
            )
            publish.return_value.run.return_value = SimpleNamespace(selected=1, written=0)
            result = run_daily(settings(), today=date(2026, 10, 30), **kwargs)
            return result, extract, publish

    def test_exactly_thirteen_sources_run_to_previous_complete_hospital_day(self) -> None:
        result, extract, publish = self.run_job()
        self.assertEqual(len(result), 13)
        self.assertEqual(extract.return_value.run.call_count, 13)
        self.assertEqual(publish.return_value.run.call_count, 13)
        for call in extract.return_value.run.call_args_list:
            self.assertEqual(call.args[1], "2026-10-29")
            self.assertEqual(call.args[2].value, "incremental")
            self.assertEqual(call.args[3].isoformat(), "2026-10-29T00:00:00+08:00")

    def test_historical_overlap_is_replay_before_incremental_progress(self) -> None:
        _, extract, _ = self.run_job(start=date(2026, 10, 27))
        modes = [call.args[2].value for call in extract.return_value.run.call_args_list]
        self.assertEqual(modes[:3], ["replay", "replay", "incremental"])
        self.assertEqual(len(modes), 39)

    def test_replay_never_selects_incremental_mode(self) -> None:
        _, extract, _ = self.run_job(start=date(2026, 10, 28), replay=True)
        self.assertTrue(
            all(call.args[2].value == "replay" for call in extract.return_value.run.call_args_list)
        )

    def test_future_date_is_rejected_before_loading_progress(self) -> None:
        with patch("medqc_ingest.daily.next_source_day") as progress:
            with self.assertRaises(IngestError):
                run_daily(settings(), end=date(2026, 10, 30), today=date(2026, 10, 30))
            progress.assert_not_called()

    def test_no_initial_watermark_requires_explicit_start(self) -> None:
        with (
            patch("medqc_ingest.daily.next_source_day", return_value=None),
            self.assertRaises(IngestError),
        ):
            run_daily(settings(), today=date(2026, 10, 30))

    def test_skipping_unprocessed_dates_is_rejected(self) -> None:
        with (
            patch("medqc_ingest.daily.next_source_day", return_value=date(2026, 10, 27)),
            self.assertRaises(IngestError),
        ):
            run_daily(settings(), start=date(2026, 10, 29), today=date(2026, 10, 30))

    def test_failure_stops_remaining_sources(self) -> None:
        with (
            patch("medqc_ingest.daily.next_source_day", return_value=date(2026, 10, 29)),
            patch("medqc_ingest.daily.PostgresIngestRepository"),
            patch("medqc_ingest.daily.PostgresCdmRepository"),
            patch("medqc_ingest.daily.ExtractService") as extract,
            patch("medqc_ingest.daily.PublishService") as publish,
        ):
            extract.return_value.run.side_effect = IngestError(
                "source_query_error", "fixture_failure"
            )
            with self.assertRaises(IngestError):
                run_daily(settings(), today=date(2026, 10, 30))
            self.assertEqual(extract.return_value.run.call_count, 1)
            publish.assert_not_called()

    def test_caught_up_job_does_not_reextract(self) -> None:
        with (
            patch("medqc_ingest.daily.next_source_day", return_value=date(2026, 10, 30)),
            patch("medqc_ingest.daily.PostgresIngestRepository"),
            patch("medqc_ingest.daily.PostgresCdmRepository"),
            patch("medqc_ingest.daily.ExtractService") as extract,
            patch("medqc_ingest.daily.PublishService") as publish,
        ):
            publish.return_value.run.return_value = SimpleNamespace(selected=1, written=0)
            self.assertEqual(len(run_daily(settings(), today=date(2026, 10, 30))), 13)
            extract.assert_not_called()


class TestDeploymentBoundaries(unittest.TestCase):
    def test_database_driver_selection_is_explicit(self) -> None:
        driver = SimpleNamespace(name="fake")
        with (
            patch.dict(os.environ, {"MEDQC_PG_DRIVER": "psycopg2"}),
            patch(
                "medqc_ingest.repositories.postgres.importlib.import_module", return_value=driver
            ) as load,
        ):
            self.assertIs(_psycopg(), driver)
            load.assert_called_once_with("psycopg2")
        with patch.dict(os.environ, {"MEDQC_PG_DRIVER": "unknown"}), self.assertRaises(IngestError):
            _psycopg()

    def test_passfile_does_not_copy_password_into_connection_kwargs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="medqc-passfile-test-") as folder:
            path = Path(folder) / "fixture.pgpass"
            path.write_text("fixture-only", encoding="utf-8")
            item = PassfilePostgresSettings("127.0.0.1", 5432, "fixture", "fixture", path)
            with patch.dict(os.environ, {}, clear=True):
                self.assertNotIn("password", item.connection_kwargs())
                self.assertEqual(item.connection_kwargs()["passfile"], str(path))
            with (
                patch.dict(os.environ, {"PGPASSWORD": "fixture-only"}),
                self.assertRaises(IngestError),
            ):
                item.connection_kwargs()

    def test_shanghai_source_zone_does_not_require_windows_tzdata(self) -> None:
        with patch("medqc_ingest.config.ZoneInfo", side_effect=AssertionError("not needed")):
            self.assertEqual(
                datetime(2026, 10, 30, tzinfo=source_zone("Asia/Shanghai"))
                .utcoffset()
                .total_seconds(),
                28800,
            )

    def test_injected_commit_failure_does_not_call_real_commit(self) -> None:
        repository = _FailBeforeCommit(Mock())
        repository._data = Mock()
        with self.assertRaises(IngestError) as failure:
            repository.commit_data()
        self.assertEqual(failure.exception.location, "deployment_injected_before_commit")
        repository._data.commit.assert_not_called()

    def test_snapshot_probe_rejects_type_reinterpretation(self) -> None:
        from medqc_ingest.domain import resolve_interface

        payload = dict.fromkeys(resolve_interface("web.mr").source_columns)
        payload["record_content"] = {"$type": "str", "text": "fixture"}
        with self.assertRaises(IngestError):
            _RowsSource([payload])

    def test_second_publication_round_must_have_zero_changes(self) -> None:
        with (
            patch("medqc_ingest.deployment_acceptance.PostgresIngestRepository"),
            patch("medqc_ingest.deployment_acceptance.PostgresCdmRepository"),
            patch("medqc_ingest.deployment_acceptance.PublishService") as service,
        ):
            service.return_value.run.side_effect = [SimpleNamespace(selected=1, written=1)] * 14
            with self.assertRaises(IngestError) as failure:
                publish_twice(settings().ingest, settings().cdm)
            self.assertEqual(failure.exception.location, "publish_second_round_changed")

    def test_runtime_config_rejects_extra_environment_keys_and_business_database(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "configured_daily_test", ROOT / "tools/run_configured_daily.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        valid = {
            "MEDQC_INGEST_PG_HOST": "127.0.0.1",
            "MEDQC_CDM_PG_HOST": "127.0.0.1",
            "MEDQC_INGEST_PG_DATABASE": settings().ingest.database,
            "MEDQC_CDM_PG_DATABASE": settings().cdm.database,
        }
        with tempfile.TemporaryDirectory(prefix="medqc-config-test-") as folder:
            path = Path(folder) / "config.json"
            for data in ({**valid, "PATH": "fixture"}, {**valid, "MEDQC_CDM_PG_DATABASE": "medqc"}):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(IngestError):
                    module.read_runtime(path)
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(module.read_runtime(path), valid)


if __name__ == "__main__":
    unittest.main()
