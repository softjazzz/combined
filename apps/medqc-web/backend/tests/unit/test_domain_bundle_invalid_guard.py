"""任务同步期间所有领域 Bundle 读取形态都拒绝旧资料。"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from app.services.bundles import assembly


COORDS = {"execution_domain": "course", "institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
STAGING_POLICY_VERSION = f"{assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION}:{'a' * 32}"


class _Rows:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Connection:
    def __init__(self, row, statements):
        self.row = row
        self.statements = statements

    def execute(self, sql, params):
        query = str(sql)
        self.statements.append((query, params))
        row = dict(self.row)
        if "'{}'::jsonb AS structured_context" in query:
            row["structured_context"] = {}
        elif "'has_content'" in query:
            row["source_documents"] = '[{"document_type":"daily_course_record","document_id":"D1","has_content":true,"length":2}]'
        return _Rows(row)


class _Engine:
    def __init__(self, row, statements):
        self.row = row
        self.statements = statements

    @contextmanager
    def connect(self):
        yield _Connection(self.row, self.statements)


@pytest.fixture
def db_row(monkeypatch):
    statements = []
    row = {
        **COORDS,
        "policy_version": "normal-v1",
        "bundle_schema_version": assembly.BUNDLE_SCHEMA_VERSION_CURRENT,
        "source_documents": '[{"document_type":"daily_course_record","document_id":"D1","content":"正文"}]',
        "structured_context": '{"domain_projection":{"category":"course"}}',
    }
    monkeypatch.setattr(assembly, "engine", _Engine(row, statements))
    return row, statements


@pytest.mark.parametrize("loader", [
    assembly.load_domain_bundle,
    assembly.load_domain_bundle_document_index,
    assembly.load_domain_bundle_for_emr_render,
])
@pytest.mark.parametrize("version", [assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION, STAGING_POLICY_VERSION])
def test_domain_read_shapes_reject_invalidated_row(db_row, loader, version):
    row, statements = db_row
    row["policy_version"] = version
    kwargs = {**COORDS}
    if loader is assembly.load_domain_bundle_for_emr_render:
        kwargs.update(doc_type="daily_course_record", doc_id="D1")

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        loader(**kwargs)

    assert "policy_version" in statements[0][0].split("FROM")[0]
    assert statements[0][1]["visit_id"] == "V1"


@pytest.mark.parametrize("loader", [
    assembly.load_domain_bundle,
    assembly.load_domain_bundle_document_index,
    assembly.load_domain_bundle_for_emr_render,
])
def test_domain_read_shapes_preserve_normal_payload(db_row, loader):
    row, _ = db_row
    kwargs = {**COORDS}
    if loader is assembly.load_domain_bundle_for_emr_render:
        kwargs.update(doc_type="daily_course_record", doc_id="D1")

    payload = loader(**kwargs)

    assert isinstance(payload, dict)
    assert payload["policy_version"] == "normal-v1"
    assert payload["source_documents"][0]["document_id"] == "D1"
    if loader is assembly.load_domain_bundle_for_emr_render:
        assert payload["structured_context"] == {}
    else:
        assert payload["structured_context"]["domain_projection"]["category"] == "course"
    if loader is assembly.load_domain_bundle_document_index:
        assert "content" not in payload["source_documents"][0]


@pytest.mark.parametrize("force_refresh", [False, True])
@pytest.mark.parametrize("version", [assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION, STAGING_POLICY_VERSION])
def test_load_or_assemble_rejects_invalidated_row_before_rebuild(db_row, monkeypatch, force_refresh, version):
    row, _ = db_row
    row["policy_version"] = version
    monkeypatch.setattr(assembly, "ensure_domain_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(
        assembly, "assemble_domain_bundle",
        lambda **_kwargs: pytest.fail("失效期间不应重组 CDM"),
    )

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        assembly.load_or_assemble_domain_bundle(**COORDS, force_refresh=force_refresh)


def test_load_or_assemble_normal_cache_and_forced_refresh(db_row, monkeypatch):
    row, _ = db_row
    calls = []
    monkeypatch.setattr(assembly, "ensure_domain_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly, "assemble_domain_bundle", lambda **_kwargs: calls.append("assemble") or {"fresh": True})
    monkeypatch.setattr(assembly, "_upsert_domain_bundle", lambda **_kwargs: calls.append("upsert"))

    cached = assembly.load_or_assemble_domain_bundle(**COORDS)
    refreshed = assembly.load_or_assemble_domain_bundle(**COORDS, force_refresh=True)

    assert cached["source_documents"][0]["content"] == "正文"
    assert refreshed == {"fresh": True}
    assert calls == ["assemble", "upsert"]


@pytest.mark.parametrize("version", [assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION, STAGING_POLICY_VERSION])
@pytest.mark.parametrize("force_refresh", [False, True])
def test_scene_read_rejects_static_or_staging_marker(monkeypatch, version, force_refresh):
    monkeypatch.setattr(assembly, "ensure_scene_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly, "_load_scene_bundle", lambda **_kwargs: {"policy_version": version})
    monkeypatch.setattr(
        assembly, "_assemble_scene_bundle",
        lambda **_kwargs: pytest.fail("失效期间不应重组 CDM"),
    )

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        assembly.load_or_assemble_scene_bundle(
            scene="running", institute_id="H1", patient_id="P1", visit_id="V1",
            force_refresh=force_refresh,
        )


def test_scene_fallback_usable_candidate_rejects_staging_marker(monkeypatch):
    calls = []

    def load(**_kwargs):
        calls.append(_kwargs)
        if len(calls) == 1:
            return {"policy_version": "normal-v1", "bundle_schema_version": assembly.BUNDLE_SCHEMA_VERSION_CURRENT}
        return {"policy_version": STAGING_POLICY_VERSION, "medical_text": "旧正文", "text_available": True}

    monkeypatch.setattr(assembly, "ensure_scene_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly, "_load_scene_bundle", load)

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        assembly.load_or_assemble_scene_bundle(
            scene="running", institute_id="H1", patient_id="P1", visit_id="V1",
        )
    assert len(calls) == 2


@pytest.mark.parametrize("version", ["normal-v1", "task-record-sync-invalidated-v1:other", "task-record-sync-invalidated-v1:123"])
def test_non_marker_policy_version_is_unchanged(db_row, version):
    row, _ = db_row
    row["policy_version"] = version

    assert assembly.load_domain_bundle(**COORDS)["policy_version"] == version
