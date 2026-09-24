"""准生产病例包必须拒绝任务同步中尚未发布的旧快照。"""

from __future__ import annotations

import pytest

from app.services.bundles import assembly
from app.services.luxian_0609 import preproduction_bundle_reader as reader


class _Result:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Connection:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params):
        self.owner.calls.append((str(statement), dict(params)))
        key = (params["institute_id"], params["patient_id"], params["visit_id"])
        return _Result(self.owner.rows.get(key))


class _Engine:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def connect(self):
        return _Connection(self)


def _row(version):
    return {
        "policy_version": version,
        "medical_text": "old content",
        "structured_context": '{"source": "published"}',
        "document_hits": "[]",
        "data_quality_flags": "[]",
        "source_doc_priority": "[]",
    }


def _read(visit_id):
    return reader.read_luxian_0609_preproduction_bundle(
        scene="running", institute_id="H1", patient_id="P1", visit_id=visit_id
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "version",
    [
        assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION,
        f"{assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION}:{'a' * 32}",
    ],
)
def test_invalidated_bundle_is_rejected_before_json_parsing(monkeypatch, version):
    row = _row(version)
    row["structured_context"] = object()
    fake_engine = _Engine({("H1", "P1", "V1"): row})
    monkeypatch.setattr(reader, "engine", fake_engine)
    monkeypatch.setattr(reader, "_parse_json_field", lambda *_args, **_kwargs: pytest.fail("parsed invalid bundle"))

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        _read("V1")

    assert len(fake_engine.calls) == 1
    assert "policy_version" in fake_engine.calls[0][0]


@pytest.mark.unit
def test_normal_bundle_remains_readable_and_invalidated_visit_is_isolated(monkeypatch):
    fake_engine = _Engine({
        ("H1", "P1", "V1"): _row(assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION),
        ("H1", "P1", "V2"): _row("normal-v1"),
    })
    monkeypatch.setattr(reader, "engine", fake_engine)

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        _read("V1")
    assert _read("V2")["structured_context"] == {"source": "published"}
    assert fake_engine.calls[0][1]["visit_id"] == "V1"
    assert fake_engine.calls[1][1]["visit_id"] == "V2"


@pytest.mark.unit
def test_absent_bundle_keeps_lookup_error(monkeypatch):
    monkeypatch.setattr(reader, "engine", _Engine({}))

    with pytest.raises(LookupError, match="preproduction bundle not found"):
        _read("V-missing")
