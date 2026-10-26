"""独立材料副本的跨表、JSON关联及不覆盖保护；不写库、不含真实患者材料。"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf_material_copy import apply_documents, clone_rows, identity_map, map_json, validate_column_lengths  # noqa: E402

BATCH = "125314b2-c213-42be-9894-85b433c8bf41"
CASE = dict(institute_id="synthetic-hospital", patient_id="SYN-P", visit_id="SYN-V", sample="C01")


def fixtures():
    rows = dict(
        daily_course_record=[dict(**{k:CASE[k] for k in ("institute_id","patient_id","visit_id")},
            document_id="SYN-DOC", record_content="原临床正文与医师姓名保持原值",record_time=None,
            physician_sign=None,submit_datetime="2026-10-02T10:00:00",document_title="日常病程记录",
            v2_schema={"record":{"documentId":"SYN-DOC","patient_id":"SYN-P","visit_id":"SYN-V"}})],
        inpat_drug_order=[dict(**{k:CASE[k] for k in ("institute_id","patient_id","visit_id")},
            order_id="SYN-ORDER", group_id="SYN-GROUP", physician_id="DOCTOR-EXTERNAL", drug_code="DRUG-CODE", planned_end_datetime=None)],
        labtest_item_report=[dict(**{k:CASE[k] for k in ("institute_id","patient_id","visit_id")},
            document_id="SYN-REPORT", test_id="SYN-TEST")],
        labtest_master=[dict(**{k:CASE[k] for k in ("institute_id","patient_id","visit_id")},test_id="SYN-TEST")],
    )
    catalog = {}
    for table,records in rows.items():
        catalog[table] = dict(primary_key=["institute_id","patient_id","visit_id", "order_id" if table=="inpat_drug_order" else "test_id" if table=="labtest_master" else "document_id"],
            columns={key:dict(type="jsonb" if key=="v2_schema" else "text",nullable=True,generated=False) for key in records[0]})
    return rows,catalog,identity_map(batch_id=BATCH,case=CASE,rows=rows,catalog=catalog)


def test_clone_remaps_three_coordinates_and_cross_table_lab_reference():
    rows,catalog,mapping = fixtures()
    before = copy.deepcopy(rows)
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    assert rows == before
    assert copied["labtest_master"][0]["test_id"] == copied["labtest_item_report"][0]["test_id"]
    assert copied["labtest_master"][0]["test_id"] != "SYN-TEST"
    assert copied["daily_course_record"][0]["patient_id"].startswith("pdfp_")
    assert copied["daily_course_record"][0]["visit_id"].startswith("pdfv_")
    assert copied["daily_course_record"][0]["institute_id"] == CASE["institute_id"]


def test_json_reference_mapping_preserves_free_text_and_external_ids():
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    doc = copied["daily_course_record"][0]
    assert doc["v2_schema"]["record"]["documentId"] == doc["document_id"]
    assert doc["record_content"] == rows["daily_course_record"][0]["record_content"]
    assert copied["inpat_drug_order"][0]["physician_id"] == "DOCTOR-EXTERNAL"
    assert copied["inpat_drug_order"][0]["drug_code"] == "DRUG-CODE"
    assert doc["submit_datetime"] == rows["daily_course_record"][0]["submit_datetime"]


def test_unknown_json_document_reference_fails_closed():
    _,_,mapping = fixtures()
    with pytest.raises(ValueError,match="unresolved_local_entity"):
        map_json({"document_id":"UNRESOLVED"},mapping,CASE)
    with pytest.raises(ValueError,match="foreign_case"):
        map_json({"visit_id":"OTHER-VISIT"},mapping,CASE)


def test_json_id_list_and_dictionary_keys_stay_linked():
    _,_,mapping = fixtures()
    mapped = map_json({"document_ids":["SYN-DOC"],"SYN-REPORT":{"original_text":"SYN-DOC正文不替换"}},mapping,CASE)
    assert mapped["document_ids"] == [mapping["entities"]["SYN-DOC"]]
    assert mapped[mapping["entities"]["SYN-REPORT"]]["original_text"] == "SYN-DOC正文不替换"


def test_identity_mapping_is_repeatable_and_other_batch_is_isolated():
    rows,catalog,mapping = fixtures()
    assert identity_map(batch_id=BATCH,case=CASE,rows=rows,catalog=catalog) == mapping
    another = identity_map(batch_id="122314b2-c213-42be-9894-85b433c8bf41",case=CASE,rows=rows,catalog=catalog)
    assert another["patient_id"] != mapping["patient_id"]
    assert another["entities"]["SYN-DOC"] != mapping["entities"]["SYN-DOC"]


def test_other_hospital_same_patient_and_visit_cannot_enter_this_copy():
    rows,catalog,mapping = fixtures()
    rows["daily_course_record"][0]["institute_id"] = "OTHER-HOSPITAL"
    with pytest.raises(ValueError,match="institute_mismatch"):
        clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)


def test_overlong_mapped_id_is_rejected_before_pg_can_truncate():
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    catalog["daily_course_record"]["columns"]["document_id"]["length"] = 10
    with pytest.raises(ValueError,match="column_length"):
        validate_column_lengths(copied,catalog)


def document(action="supplement_candidate", differences=None):
    return dict(candidate_id="synthetic-candidate",source_file_id="F001",page_start=1,page_end=2,
        table="daily_course_record",title="日常病程记录",record_time="2026-10-01T09:01+08:00",
        content="PDF明确记录的临床正文\n医师签名：合成甲 合成乙",time_precision="minute",
        refinement=dict(action=action,proposed_table="daily_course_record",matches=[dict(document_id="SYN-DOC")],
                        mapping_basis="unique_existing_content_owner",differences=differences or ["record_time_missing_in_database"]))


def test_supplement_only_empty_record_time_and_keeps_submit_time_separate():
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    result = apply_documents(documents=[document()],rows=copied,source_rows=rows,mapping=mapping,catalog=catalog,common={},batch_id=BATCH)
    row = copied["daily_course_record"][0]
    assert row["record_time"] == "2026-10-01T09:01+08:00"
    assert row["submit_datetime"] == "2026-10-02T10:00:00"
    assert len(copied["daily_course_record"]) == 1
    assert result[0]["target_document_id"] == row["document_id"]
    assert rows["daily_course_record"][0]["record_time"] is None


def test_nonempty_record_time_never_overwritten():
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    copied["daily_course_record"][0]["record_time"] = "2026-10-03T09:01:00"
    with pytest.raises(ValueError,match="overwrite_time"):
        apply_documents(documents=[document()],rows=copied,source_rows=rows,mapping=mapping,catalog=catalog,common={},batch_id=BATCH)


@pytest.mark.parametrize("action", ["held","version_review","same_body"])
def test_non_active_pdf_version_does_not_replace_or_duplicate_clinical_row(action):
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    before = copy.deepcopy(copied)
    result = apply_documents(documents=[document(action)],rows=copied,source_rows=rows,mapping=mapping,catalog=catalog,common={},batch_id=BATCH)
    assert copied == before
    assert result[0]["content"].startswith("PDF明确")
    assert result[0]["state"] == action


def test_new_document_does_not_invent_submit_or_signing_time():
    rows,catalog,mapping = fixtures()
    copied = clone_rows(rows,case=CASE,mapping=mapping,catalog=catalog)
    doc = document("new_candidate")
    doc["refinement"]["matches"] = []
    apply_documents(documents=[doc],rows=copied,source_rows=rows,mapping=mapping,catalog=catalog,common={},batch_id=BATCH)
    new = copied["daily_course_record"][-1]
    assert new["physician_sign"] == "合成甲 合成乙"
    assert "submit_datetime" not in new
    assert new["document_id"] != copied["daily_course_record"][0]["document_id"]
