from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.case_identity import CaseRef
from scripts import build_luxian_0609_0426_synthetic_v2 as builder_0426
from scripts import build_luxian_0609_0728_exam_lab_derived_v1 as builder_0728


@pytest.mark.parametrize("builder", [builder_0426, builder_0728])
def test_synthetic_builder_publishes_only_complete_eight_variant_stage(monkeypatch, builder):
    calls = []
    ref = CaseRef("institution", "patient", "visit")
    factory = object()
    monkeypatch.setattr(builder, "new_bundle_staging_token", lambda: "stage-unique")
    monkeypatch.setattr(builder, "_default_source_schema", lambda: "cdm")

    def refresh_scene(**kwargs):
        calls.append(("scene", kwargs))
        return {"processed": 1, "updated": 1, "failed": 0, "skipped": 0}

    def refresh_domain(**kwargs):
        calls.append(("domain", kwargs))
        return {"processed": 1, "updated": 1, "failed": 0, "skipped": 0}

    def publish(*args, **kwargs):
        calls.append(("publish", args, kwargs))

    monkeypatch.setattr(builder, "refresh_scene_bundles_for_rows", refresh_scene)
    monkeypatch.setattr(builder, "refresh_domain_bundles_for_rows", refresh_domain)
    monkeypatch.setattr(builder, "publish_bundle_variants", publish)

    builder._refresh_and_publish([ref], factory)

    assert [name for name, *_ in calls] == ["scene"] * 2 + ["domain"] * 6 + ["publish"]
    for _, kwargs in calls[:-1]:
        assert kwargs["policy_version"] == "stage-unique"
        assert kwargs["source_schema"] == "cdm"
        assert kwargs["continue_on_error"] is False
    assert calls[-1][1] == ([ref],)
    assert calls[-1][2]["session_factory"] is factory


@pytest.mark.parametrize("builder", [builder_0426, builder_0728])
def test_synthetic_builder_never_publishes_partial_bundle(monkeypatch, builder):
    calls = []
    ref = CaseRef("institution", "patient", "visit")
    monkeypatch.setattr(builder, "new_bundle_staging_token", lambda: "stage-unique")
    monkeypatch.setattr(
        builder, "refresh_scene_bundles_for_rows",
        lambda **kwargs: {"processed": 1, "updated": 1, "failed": 0},
    )

    def refresh_domain(**kwargs):
        calls.append(kwargs["domains"][0])
        return {"processed": 1, "updated": 0 if kwargs["domains"] == ("terminal",) else 1, "failed": 0}

    monkeypatch.setattr(builder, "refresh_domain_bundles_for_rows", refresh_domain)
    monkeypatch.setattr(builder, "publish_bundle_variants", lambda *args, **kwargs: pytest.fail("partial published"))

    with pytest.raises(RuntimeError, match="刷新不完整"):
        builder._refresh_and_publish([ref], object())
    assert len(calls) == 6


@pytest.mark.parametrize("builder", [builder_0426, builder_0728])
def test_synthetic_builder_uses_shared_pg_lock_around_write(monkeypatch, builder):
    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append("close")

        def execute(self, statement, params):
            calls.append((str(statement), params["key"]))

        def rollback(self):
            calls.append("rollback")

        def commit(self):
            calls.append("commit")

    monkeypatch.setattr(builder, "engine", SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=lambda: Connection(),
    ))
    with pytest.raises(ValueError, match="write failed"):
        with builder._bundle_write_lock():
            calls.append("write")
            raise ValueError("write failed")

    assert calls[0] == ("SELECT pg_advisory_lock(:key)", builder._GLOBAL_LOCK_KEY)
    assert calls[1] == "write"
    assert calls[2] == "rollback"
    assert calls[3] == ("SELECT pg_advisory_unlock(:key)", builder._GLOBAL_LOCK_KEY)
    assert calls[4:] == ["commit", "close"]
