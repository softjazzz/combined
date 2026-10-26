"""细化预览的保守去重、字段差异和材料 owner 保护，全部使用合成正文。"""

import ast
import hashlib
import importlib.util
import sys
import types
import zipfile
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("pdf_refine", SCRIPT_DIR / "refine_pdf_supplement.py")
refine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refine)

BODY = "患者今日复查结果稳定，继续记录治疗反应并观察症状变化。" * 4
CLOCK = "2026-10-01T09:01+08:00"


def document(**values):
    return dict(dict(table="daily_course_record", title="日常病程记录", content=BODY,
                     record_time=CLOCK, matches=[]), **values)


def row(**values):
    return dict(dict(_table="daily_course_record", document_id="synthetic-1",
                     record_content=BODY, record_time=CLOCK), **values)


def compare(doc=None, rows=None):
    return refine.match_document(doc or document(), refine.indexed_rows(rows or [row()]))


def test_heading_and_whitespace_are_not_new_clinical_content():
    doc = document(content="2026-10-01 09:01 日常病程记录\n" + BODY)
    assert compare(doc)["action"] == "same_body"


def test_identical_body_in_multiple_old_rows_does_not_choose_by_time():
    result = compare(rows=[row(), row(document_id="synthetic-2", record_time="2026-10-02T08:00+08:00")])
    assert result["action"] == "held"


def test_same_body_missing_clock_is_field_supplement_not_new_record():
    result = compare(rows=[row(record_time=None, submit_datetime="2026-10-02T10:00+08:00")])
    assert result["action"] == "supplement_candidate"
    assert result["differences"] == ["record_time_missing_in_database"]


def test_timezone_equivalence_and_minute_precision_do_not_conflict():
    assert compare(rows=[row(record_time="2026-10-01T01:01:59+00:00")])["action"] == "same_body"


def test_different_nonempty_clock_requires_version_review():
    result = compare(rows=[row(record_time="2026-10-03T09:01+08:00")])
    assert result["action"] == "version_review"
    assert "record_time_conflict" in result["differences"]


def test_naive_time_cannot_be_assumed_same_timezone():
    assert refine.minute("2026-10-01 09:01") is None
    result = compare(rows=[row(record_time="2026-10-01 09:01")])
    assert result["time_comparison_basis"] == "database_unzoned_wall_clock_only"
    assert "record_time_conflict" not in result["differences"]
    changed = compare(rows=[row(record_time="2026-10-02 09:01")])
    assert changed["action"] == "version_review"
    assert changed["differences"] == ["record_time_timezone_unverified"]


def test_dose_change_can_never_be_same_body():
    result = compare(document(content=BODY+"用量15g"), [row(record_content=BODY+"用量1.5g")])
    assert result["action"] != "same_body"
    assert "body_version_difference" in result["differences"]


def test_two_names_are_preserved_without_role_inference():
    doc = document(content=BODY+"\n医师签名：合成甲 合成乙\n日期：2026年10月01日")
    result = compare(doc)
    assert result["action"] == "supplement_candidate"
    assert refine.signatures(doc["content"]) == ("合成甲", "合成乙")
    assert "explicit_signatures_missing_in_database" in result["differences"]


def test_different_nonempty_signature_is_not_overwritten():
    result = compare(document(content=BODY+"\n医生签名：合成甲"), [row(physician_sign="合成乙")])
    assert result["action"] == "version_review"
    assert "signature_conflict" in result["differences"]


def test_signature_alone_does_not_match():
    doc = document(content="完全不同的情况变化"*20+"\n医师签名：合成甲")
    result = compare(doc, [row(record_content=BODY+"\n医师签名：合成甲")])
    assert not result["matches"]


def test_multiple_signature_labels_do_not_hide_second_clinical_body():
    text = BODY+"\n医师签名：合成甲\n另一份正文\n医师签名：合成乙"
    assert "另一份正文" in refine.core(text)


def test_small_structured_field_is_not_whole_document_identity():
    result = compare(rows=[row(record_content="", treatment_plan="继续观察")])
    assert not result["matches"]


def test_metadata_in_json_cannot_create_content_match():
    assert refine.row_bodies(row(record_content="", v2_schema={"metadata": BODY})) == []


def test_prior_weak_match_blocks_new_record():
    doc = document(content="其他完全不同正文"*20, matches=[{"evidence":"same_record_minute_only"}])
    assert compare(doc)["reason"] == "prior_match_needs_review"


@pytest.mark.parametrize("title", ["输血前评估记录", "输血后评价记录", "危急值处理记录"])
def test_assessment_or_disposition_is_course_not_event(title):
    table, _ = refine.storage_proposal(document(title=title, table="bloodtrans_assessment_record" if title.startswith("输血") else None))
    assert table == "daily_course_record"


@pytest.mark.parametrize("title", ["请会诊执行记录", "记录", "气管插管操作记录", "入ICU记录"])
def test_ambiguous_titles_do_not_invent_consult_surgery_or_transfer(title):
    assert refine.storage_proposal(document(title=title, table=None))[0] is None


def test_unknown_title_can_inherit_unique_existing_owner_only_as_proposal():
    result = compare(document(title="请会诊执行记录", table=None), [row(_table="consultation_record")])
    assert result["proposed_table"] == "consultation_record"
    assert result["write_approved"] is False


def literal_constant(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


def test_suggested_transfusion_course_owner_is_on_actual_bundle_and_rule_read_paths():
    services = SCRIPT_DIR.parents[1] / "backend/app/services"
    assert "daily_course_record" in literal_constant(services/"bundles/assembly.py", "_RUNNING_DOC_PRIORITY")
    assert "daily_course_record" in literal_constant(services/"bundles/assembly.py", "_FINAL_DOC_PRIORITY")
    executor = services/"luxian_0609/native_transfusion_execution.py"
    contexts = literal_constant(executor, "_RULE_CONTEXT_SOURCES")
    assert "daily_course_record" in contexts["LX0609-07-01-02"]
    assert "daily_course_record" in contexts["LX0609-07-03-01"]
    assert "daily_course_record" not in literal_constant(executor, "_TRIGGER_SOURCES")


@pytest.mark.parametrize("header,verified", [("住院号：SYN123", True), ("住院号：OTHER", False), ("正文提到SYN123", False)])
def test_additional_identity_requires_explicit_exact_header_and_name(tmp_path, monkeypatch, header, verified):
    data = b"synthetic-pdf"
    archive = tmp_path/"synthetic.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("synthetic.pdf", data)

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def __getitem__(self, _):
            return types.SimpleNamespace(get_text=lambda **_: "姓名：合成甲\n"+header)

    monkeypatch.setitem(sys.modules, "fitz", types.SimpleNamespace(open=lambda **_: FakePDF()))
    payload = dict(files=[dict(file_id="F001", sample="C01", identity_basis="name_only", source_sha256=hashlib.sha256(data).hexdigest())],
                   existing_documents={"C01":[row(name="合成甲", mr_no="SYN123")]})
    assert refine.additional_identity(payload, archive)["F001"]["verified"] is verified
