"""按正式来源定位当前文书，不按标题或相似文本猜测。"""
import pytest
from fastapi import HTTPException

from app.services.qc_agent.business_documents import locate_document, read_evidence_document


def document(**changes):
    return {"source_ref": "src_a", "doc_type": "admission_record", "doc_name": "入院记录", "content": "😀乙原文摘录丁", **changes}


def test_exact_source_and_unique_quote_use_unicode_character_offsets():
    result = locate_document({"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "原文摘录"}, {"documents": [document()]})
    assert result["state"] == "located"
    assert result["start"] == 2 and result["end"] == 6
    assert result["content"][result["start"]:result["end"]] == "原文摘录"
    assert result["source_view"] == "current"


@pytest.mark.parametrize("documents,state", [
    ([document(source_ref="src_b")], "source_not_found"),
    ([document(), document()], "source_ambiguous"),
    ([document(doc_type="rescue_record")], "source_type_mismatch"),
    ([document(content="更新后的文书")], "quote_not_found"),
    ([document(content="原文摘录；原文摘录")], "quote_ambiguous"),
])
def test_unproven_position_is_never_fabricated(documents, state):
    result = locate_document({"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "原文摘录"}, {"documents": documents})
    assert result["state"] == state
    assert "start" not in result and "end" not in result
    if state in {"source_not_found", "source_ambiguous", "source_type_mismatch"}:
        assert not result.get("content")


def test_exact_alias_can_locate_merged_document():
    doc = document(source_ref="src_merged", source_document_aliases=[{"source_ref": "src_a", "source_document_type": "admission_record"}])
    assert locate_document({"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "原文摘录"}, {"documents": [doc]})["state"] == "located"


def test_read_failure_has_no_empty_success_or_saved_document_fallback(monkeypatch):
    from app.services.bundles import current_view
    def fail(**_):
        raise RuntimeError("read_failed")
    monkeypatch.setattr(current_view, "load_current_documents", fail)
    with pytest.raises(HTTPException) as failure:
        read_evidence_document({"institute_id": "H", "patient_id": "P", "visit_id": "V"}, {"source_ref": "src_a"})
    assert failure.value.status_code == 503


def test_document_endpoint_rechecks_saved_task_owner_and_access_before_loading(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
    user = {"id": "doctor-a", "roles": ["doctor"]}
    identity = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    store = BusinessSessionStore(tmp_path)
    session = store.create(user, BusinessContext(view="doctor", **identity))
    store.bind(session["session_id"], user, "result-a", {"kind": "saved_result", "identity": identity, "job_id": "task-a", "record_ref": "record-a", "rule_id": "LX0609-01-01-01"})
    access = BusinessAccess({"version": 1, "accounts": {user["id"]: {"doctor_cases": [identity]}}})
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    evidence = {"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "原文摘录"}
    saved = {"state": "ready", "job_id": "task-a", "record_ref": "record-a", "items": [{"rule_id": "LX0609-01-01-01", "evidence": [evidence]}]}
    import httpx
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": saved}))))
    calls = []
    def read(ident, selected):
        calls.append((ident, selected))
        return locate_document(selected, {"documents": [document()]})
    monkeypatch.setattr(api.business_documents, "read_evidence_document", read)
    client = TestClient(app)
    url = f"/business/sessions/{session['session_id']}/evidence-document"
    params = {"reference_id": "result-a", "evidence_index": 0, "source_ref": "forged", "institute_id": "other-hospital", "patient_id": "other-patient", "visit_id": "other-visit"}
    assert client.get(url, params=params).json()["state"] == "located"
    assert calls == [(identity, evidence)]
    assert client.get(url, params={**params, "evidence_index": 1}).status_code == 404
    assert client.get(url, params={**params, "reference_id": "unknown"}).status_code == 404
    saved["job_id"] = "task-b"
    assert client.get(url, params=params).status_code == 409
    user["id"] = "other-account"
    assert client.get(url, params=params).status_code == 404
    user["id"] = "doctor-a"
    access.config.accounts.clear()
    assert client.get(url, params=params).status_code == 403
    assert len(calls) == 1



def test_legacy_excerpt_prefix_is_explicit_and_original_quote_is_preserved():
    text = "😀" + "保留否定条件，不得改写。" * 40
    evidence = {"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": text[:300] + "…", "excerpt_kind": "文书级依据"}
    result = locate_document(evidence, {"documents": [document(content=text)]})
    assert result["state"] == "located"
    assert result["quote"] == evidence["evidence_excerpt"]
    assert result["matched_quote"] == text[:300]
    assert result["content"][result["start"]:result["end"]] == result["matched_quote"]
    assert result["match_scope"] == "excerpt_prefix"
    assert "未整段匹配" in result["note"]


@pytest.mark.parametrize("kind,content,state", [
    ("", "甲" * 300, "quote_not_found"),
    ("文书级依据", "甲" * 301, "quote_ambiguous"),
    ("文书级依据", "乙" * 300, "quote_not_found"),
])
def test_legacy_prefix_requires_known_excerpt_contract_and_unique_exact_text(kind, content, state):
    evidence = {"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "甲" * 300 + "…", "excerpt_kind": kind}
    result = locate_document(evidence, {"documents": [document(content=content)]})
    assert result["state"] == state
    assert "start" not in result and "end" not in result


@pytest.mark.parametrize("quote", ["原句中的省略号…", "甲" * 300 + "…"])
def test_literal_ellipsis_prefers_exact_whole_excerpt(quote):
    evidence = {"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": quote, "excerpt_kind": "字段级依据"}
    result = locate_document(evidence, {"documents": [document(content=quote)]})
    assert result["state"] == "located"
    assert result["matched_quote"] == quote
    assert result["match_scope"] == "exact_excerpt"


def test_short_ellipsis_is_not_assumed_to_be_truncation():
    evidence = {"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "真实正文…", "excerpt_kind": "文书级依据"}
    result = locate_document(evidence, {"documents": [document(content="真实正文")]})
    assert result["state"] == "quote_not_found"


def test_saved_excerpt_compaction_can_locate_original_indented_document():
    # 原反例形态：保存摘录压缩了签名之前的72个空格，当前文书保留排版。
    from app.services.luxian_0609.customer_evidence_enrichment import _excerpt
    content = "查房记录 已阅读本次检查报告。 " + " " * 72 + "医师签名"
    field, quote = _excerpt({"record_content": content})
    assert field == "record_content" and quote not in content
    result = locate_document({"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": quote}, {"documents": [document(content=content)]})
    assert result["state"] == "located"
    assert result["quote"] == quote and result["content"] == content
    assert result["matched_quote"] == content
    assert (result["start"], result["end"]) == (0, len(content))
    assert "空白" in result["note"]


def test_whitespace_equivalent_quote_maps_to_original_unicode_offsets():
    content = "😀前言\n检查\t 结果\r\n未见\t异常。尾注"
    quote = "检查 结果 未见 异常。"
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": quote}, {"documents": [document(content=content)]})
    assert result["state"] == "located"
    assert result["start"] == 4
    assert result["content"][result["start"]:result["end"]] == "检查\t 结果\r\n未见\t异常。"
    assert result["matched_quote"] == "检查\t 结果\r\n未见\t异常。"
    assert result["quote"] == quote


def test_exact_and_whitespace_variant_repeated_quote_are_ambiguous():
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": "原文 摘录"}, {"documents": [document(content="原文 摘录；原文\n\t摘录")]})
    assert result["state"] == "quote_ambiguous"
    assert "start" not in result and "end" not in result


@pytest.mark.parametrize("content,quote", [
    ("剂量 50 mg 已给药", "剂量 5 mg 已给药"),
    ("AB 阴性", "A B 阴性"),
    ("所见：阴性。诊断：待复核。", "阴性。 待复核。"),
    ("原\u200b文摘录", "原文摘录"),
])
def test_non_whitespace_changes_and_disjoint_fields_never_match(content, quote):
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": quote}, {"documents": [document(content=content)]})
    assert result["state"] == "quote_not_found"
    assert "start" not in result and "end" not in result


def test_missing_body_is_distinguished_without_fabricated_location():
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": "原文摘录"}, {"documents": [document(content=None)]})
    assert result["state"] == "quote_not_found"
    assert "未提供正文" in result["note"]
    assert result["quote"] == "原文摘录" and not result["content"]
    assert "start" not in result and "end" not in result


def test_whitespace_matching_cannot_select_another_document_identity():
    result = locate_document({"source_ref": "src_a", "source_type": "admission_record", "evidence_excerpt": "原文 摘录"}, {"documents": [document(content="当前版本已变"), document(source_ref="src_b", content="原文\n摘录")]})
    assert result["state"] == "quote_not_found"
    assert result["content"] == "当前版本已变"
    assert "start" not in result and "end" not in result


def test_whitespace_normalized_legacy_prefix_keeps_truncation_scope():
    compact = "开头 " + "原句" * 170
    quote = compact[:300] + "…"
    content = compact.replace(" ", "\n\t  ")
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": quote, "excerpt_kind": "文书级依据"}, {"documents": [document(content=content)]})
    assert result["state"] == "located" and result["match_scope"] == "excerpt_prefix"
    assert result["quote"] == quote
    assert result["matched_quote"] == compact[:300].replace(" ", "\n\t  ")
    assert result["content"][result["start"]:result["end"]] == result["matched_quote"]
    assert "省略号" in result["note"] and "空白" in result["note"]


def test_whitespace_equivalent_literal_ellipsis_does_not_use_prefix_fallback():
    quote = "甲" * 149 + " " + "乙" * 150 + "…"
    content = quote.replace(" ", "\n\t ")
    result = locate_document({"source_ref": "src_a", "evidence_excerpt": quote, "excerpt_kind": "文书级依据"}, {"documents": [document(content=content)]})
    assert result["state"] == "located" and result["match_scope"] == "exact_excerpt"
    assert result["quote"] == quote and result["matched_quote"] == content
