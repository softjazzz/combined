import json

import pytest
from app.services.rectification_document_snapshot import (
    capture_documents,
    compare_documents,
)

IDENTITY = {
    "institute_id": "synthetic-hospital",
    "patient_id": "synthetic-patient",
    "visit_id": "synthetic-visit",
}


def doc(**changes):
    return {
        "execution_domain": "admission",
        "doc_type": "admission_record",
        "document_id": "synthetic-doc",
        "content": "合成正文",
        "sections": [
            {"source_field": "history", "section_label": "现病史", "text": "合成现病史"}
        ],
        **changes,
    }


def capture(documents):
    return capture_documents(
        IDENTITY,
        loader=lambda **identity: {
            "documents": documents,
            "domain_projection": {
                "domains": {
                    "admission": {
                        "per_source": {"admission_record": {"has_more": False}}
                    }
                }
            },
        },
    )


def test_stable_document_pair_missing_added_and_full_sections():
    before = capture([doc(), doc(document_id="removed")])
    after = capture([doc(content="已修改合成正文"), doc(document_id="added")])
    result = compare_documents(before, after, IDENTITY)
    assert result["available"]
    assert [item["state"] for item in result["documents"]] == [
        "added",
        "missing",
        "matched",
    ]
    assert result["documents"][-1]["before"]["sections"][0]["text"] == "合成现病史"
    assert json.loads(before)["documents"][0]["content"] == "合成正文"


def test_fallback_duplicate_partial_and_empty_are_not_comparable():
    result = compare_documents(
        capture([doc(document_id="", id="admission:0")]), capture([doc()]), IDENTITY
    )
    assert result["unavailable_documents"] == 1
    assert result["documents"][0]["state"] == "added"
    assert not compare_documents(
        capture([doc(), doc()]), capture([doc(projection_incomplete=True)]), IDENTITY
    )["available"]
    assert (
        compare_documents(capture([doc(content="")]), capture([doc()]), IDENTITY)[
            "documents"
        ][0]["state"]
        == "empty"
    )
    assert not compare_documents(None, capture([doc()]), IDENTITY)["available"]


def test_identity_fault_empty_and_limits_fail_closed(monkeypatch):
    from app.services import rectification_document_snapshot as module

    with pytest.raises(ValueError):
        compare_documents(
            capture([doc()]), capture([doc()]), {**IDENTITY, "patient_id": "other"}
        )
    with pytest.raises(ValueError):
        capture([])
    with pytest.raises(ValueError):
        capture([doc(document_id=str(i)) for i in range(201)])
    monkeypatch.setattr(module, "MAX_BYTES", 10)
    with pytest.raises(ValueError):
        capture([doc()])

    def fault(**identity):
        raise RuntimeError("synthetic-source-failure")

    with pytest.raises(RuntimeError):
        capture_documents(IDENTITY, loader=fault)


@pytest.mark.parametrize(
    "projection",
    [
        None,
        {},
        {"domains": {}},
        {
            "domains": {
                "admission": {"per_source": {"admission_record": {"has_more": True}}}
            }
        },
        {
            "domains": {
                "admission": {"per_source": {"admission_record": {"has_more": None}}}
            }
        },
    ],
)
def test_upstream_limit_or_missing_completeness_fails_before_freezing(projection):
    with pytest.raises(ValueError):
        capture_documents(
            IDENTITY,
            loader=lambda **identity: {
                "documents": [doc()],
                "domain_projection": projection,
            },
        )
