"""会诊意见事实冻结：命中、失效、损坏与首写者赢的契约测试。"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import consultation_opinion_freeze as freeze


DOCUMENTS = (
    {
        "ref": "consultation_record-1",
        "time": "2025-07-20 10:28:56",
        "text": "会诊意见：建议继续中药内服，方选消风散加减。",
    },
    {
        "ref": "consultation_record-2",
        "time": "2025-07-22 13:09:40",
        "text": "会诊意见：建议复查血常规。",
    },
)

PAYLOAD = {
    "episodes": [
        {
            "episode_ref": "consultation_record-1",
            "member_refs": ["consultation_record-1"],
            "application_refs": [],
            "opinion_refs": ["consultation_record-1"],
            "application_state": "absent",
            "opinion_state": "clear",
            "confidence": "high",
            "recommendations": [],
        }
    ],
    "non_target_refs": [],
    "unresolved_refs": [],
}


def test_fingerprint_is_stable_and_sensitive_to_document_content():
    baseline = freeze.documents_fingerprint(DOCUMENTS)
    assert baseline == freeze.documents_fingerprint(tuple(dict(item) for item in DOCUMENTS))

    edited = (dict(DOCUMENTS[0], text="会诊意见：建议继续中药内服。"), DOCUMENTS[1])
    assert freeze.documents_fingerprint(edited) != baseline

    reordered = (DOCUMENTS[1], DOCUMENTS[0])
    assert freeze.documents_fingerprint(reordered) != baseline


def test_missing_freeze_returns_none(tmp_path):
    assert (
        freeze.load_opinion_payload(
            visit_id="v-1", documents=DOCUMENTS, store_dir=tmp_path
        )
        is None
    )


def test_saved_freeze_is_reused_with_same_fingerprint(tmp_path):
    created = freeze.save_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, payload=PAYLOAD, store_dir=tmp_path
    )
    assert created.state == "created"
    assert created.path.is_file()

    loaded = freeze.load_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, store_dir=tmp_path
    )
    assert loaded is not None
    assert loaded.state == "reused"
    assert loaded.fingerprint == created.fingerprint
    assert loaded.payload == PAYLOAD


def test_changed_document_invalidates_freeze(tmp_path):
    freeze.save_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, payload=PAYLOAD, store_dir=tmp_path
    )
    edited = (dict(DOCUMENTS[0], text="会诊意见：建议停用中药。"), DOCUMENTS[1])
    assert (
        freeze.load_opinion_payload(
            visit_id="v-1", documents=edited, store_dir=tmp_path
        )
        is None
    )
    rebuilt = freeze.save_opinion_payload(
        visit_id="v-1", documents=edited, payload=PAYLOAD, store_dir=tmp_path
    )
    assert rebuilt.state == "rebuilt"


def test_first_writer_wins_for_same_fingerprint(tmp_path):
    first = freeze.save_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, payload=PAYLOAD, store_dir=tmp_path
    )
    second_payload = dict(PAYLOAD, extra_marker="second")
    second = freeze.save_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, payload=second_payload, store_dir=tmp_path
    )
    assert second.state == "reused"
    assert second.created_at == first.created_at
    assert (
        freeze.load_opinion_payload(
            visit_id="v-1", documents=DOCUMENTS, store_dir=tmp_path
        ).payload
        == PAYLOAD
    )


@pytest.mark.parametrize(
    "artifact",
    [
        "{not-json",
        json.dumps({"schema_version": "older-v0", "visit_id": "v-1", "fingerprint": "x", "payload": PAYLOAD}),
        json.dumps(
            {
                "schema_version": freeze.FREEZE_SCHEMA_VERSION,
                "visit_id": "v-other",
                "fingerprint": "x",
                "payload": PAYLOAD,
            }
        ),
    ],
)
def test_corrupt_or_mismatched_freeze_is_treated_as_miss(tmp_path, artifact):
    path = tmp_path / "v-1.json"
    path.write_text(artifact, encoding="utf-8")
    assert (
        freeze.load_opinion_payload(
            visit_id="v-1", documents=DOCUMENTS, store_dir=tmp_path
        )
        is None
    )


def test_reset_removes_freeze(tmp_path):
    freeze.save_opinion_payload(
        visit_id="v-1", documents=DOCUMENTS, payload=PAYLOAD, store_dir=tmp_path
    )
    assert freeze.reset_opinion_freeze(visit_id="v-1", store_dir=tmp_path) is True
    assert (
        freeze.load_opinion_payload(
            visit_id="v-1", documents=DOCUMENTS, store_dir=tmp_path
        )
        is None
    )
    assert freeze.reset_opinion_freeze(visit_id="v-1", store_dir=tmp_path) is False


def test_default_store_dir_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv(freeze._ENV_STORE_DIR, str(tmp_path / "store"))
    assert freeze.default_store_dir() == tmp_path / "store"
