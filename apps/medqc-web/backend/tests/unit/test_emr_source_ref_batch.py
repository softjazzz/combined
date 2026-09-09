from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from app.routers.emr_render import _project_customer_safe_source_refs
from app.services.qc_workspace import canonical_result_store as refs


def test_batch_reads_settings_once_and_preserves_all_refs(monkeypatch):
    settings = Mock(return_value=SimpleNamespace(JWT_SECRET="test-batch-key"))
    monkeypatch.setattr(refs, "get_settings", settings)
    payload = {"documents": [
        {"document_id": f"doc-{i}", "document_type": "lab_report",
         "source_document_ids": [f"alias-{i}", "", None]}
        for i in range(805)
    ]}
    result = _project_customer_safe_source_refs(deepcopy(payload))
    assert settings.call_count == 1
    for i, document in enumerate(result["documents"]):
        assert document["source_ref"] == refs.keyed_ref("src", f"doc-{i}", hmac_key="test-batch-key")
        assert document["source_document_aliases"] == [{
            "source_document_id": f"alias-{i}",
            "source_ref": refs.keyed_ref("src", f"alias-{i}", hmac_key="test-batch-key"),
            "source_document_type": "lab_report",
        }]
    settings.return_value = SimpleNamespace(JWT_SECRET="next-request-key")
    again = _project_customer_safe_source_refs(deepcopy(payload))
    assert settings.call_count == 2
    assert again["documents"][0]["source_ref"] != result["documents"][0]["source_ref"]


def test_empty_documents_do_not_require_key(monkeypatch):
    settings = Mock(side_effect=AssertionError("没有引用时不读取配置"))
    monkeypatch.setattr(refs, "get_settings", settings)
    payload = {"documents": [None, {}, {"source_document_ids": ["", None]}]}
    assert _project_customer_safe_source_refs(deepcopy(payload)) == payload
    settings.assert_not_called()
