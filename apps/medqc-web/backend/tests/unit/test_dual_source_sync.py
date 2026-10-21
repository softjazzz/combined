"""双源只读规划：确认合并行为，不依赖数据库或模型。"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).parents[2] / "app/services/dual_source_sync.py"
SPEC = importlib.util.spec_from_file_location("dual_source_sync", MODULE)
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


CASE = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}


def row(doc="D1", **fields):
    return {**CASE, "document_id": doc, "is_deleted": "0", **fields}


def snapshot(source, rows=(), status="ok"):
    return sync.SourceSnapshot(source, tuple(rows), status=status)


def plan(table="bloodtrans_record", clinical=(), homology=(), local=()):
    return sync.plan_table(
        table, CASE,
        snapshot("clinical_data", clinical), snapshot("homology", homology),
        snapshot("local", local), source_institutes={"clinical_data": "H", "homology": "H", "local": "H"},
    )


class DualSourceTests(unittest.TestCase):
    def test_c18_complementary_tables_keep_discharge_and_three_transfusions(self):
        blood = plan(homology=[row(f"T{i}", recordcontent="输血内容", documentstatus="Save") for i in range(3)])
        discharge = plan("discharge_record", clinical=[row("DC", treatment_course="诊疗经过", discharge_order="出院医嘱")])
        self.assertEqual(len(blood.candidates), 3)
        self.assertEqual(len(discharge.candidates), 1)
        self.assertTrue(all("source_validity_unconfirmed" in c.blockers for c in blood.candidates))
        self.assertEqual(discharge.candidates[0].values["treatment_course"], "诊疗经过")

    def test_same_id_is_one_record_and_only_empty_fields_are_filled(self):
        result = plan(clinical=[row(record_content="正文")], homology=[row(recordcontent="正文", physician_sign="签署甲")])
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].values["physician_sign"], "签署甲")
        self.assertEqual(result.candidates[0].provenance["physician_sign"], "homology")

    def test_body_conflict_keeps_both_variants_without_concatenation(self):
        result = plan(clinical=[row(record_content="版本甲")], homology=[row(recordcontent="版本乙")])
        candidate = result.candidates[0]
        self.assertEqual(candidate.values["record_content"], "版本甲")
        self.assertEqual(candidate.variants["homology"]["record_content"], "版本乙")
        self.assertIn("record_content", candidate.conflicts)

    def test_local_nonempty_body_is_preserved_on_conflict(self):
        result = plan(clinical=[row(record_content="新内容")], local=[row(record_content="原内容")])
        self.assertEqual(result.candidates[0].values["record_content"], "原内容")
        self.assertIn("record_content", result.candidates[0].conflicts)

    def test_source_empty_never_erases_local(self):
        result = plan(clinical=[row(record_content="")], local=[row(record_content="原文")])
        self.assertEqual(result.candidates[0].values["record_content"], "原文")

    def test_source_read_failure_is_not_an_empty_success(self):
        result = sync.plan_table("bloodtrans_record", CASE, snapshot("clinical_data", status="read_error"),
                                 snapshot("homology"), snapshot("local"), source_institutes={"clinical_data": "H", "homology": "H", "local": "H"})
        self.assertFalse(result.complete)
        self.assertIn("clinical_data:read_error", result.issues)

    def test_duplicate_and_missing_ids_are_quarantined(self):
        result = plan(clinical=[row("D"), row("D"), row("")])
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.quarantined_rows, 3)
        self.assertFalse(result.ready)

    def test_same_name_different_ids_are_not_deduplicated(self):
        result = plan(clinical=[row("A", record_content="同文")], homology=[row("B", record_content="同文")])
        self.assertEqual(len(result.candidates), 2)

    def test_existing_lab_detail_without_upstream_composite_key_is_retained(self):
        result = plan("labtest_item_report", local=[row("LEGACY-LAB", record_content="检验明细")])
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.quarantined_rows, 0)
        self.assertEqual(result.candidates[0].values["document_id"], "LEGACY-LAB")
        self.assertIn("cross_source_identity_unavailable", result.candidates[0].blockers)

    def test_json_payloads_are_retained_separately_not_merged(self):
        result = plan(clinical=[row(v2_schema={"custom": "甲"})], homology=[row(v2_schema={"custom": "乙"})])
        self.assertEqual(result.candidates[0].values["v2_schema"], {"custom": "甲"})
        self.assertEqual(result.candidates[0].variants["homology"]["v2_schema"], {"custom": "乙"})
        self.assertIn("v2_schema", result.candidates[0].conflicts)

    def test_patient_and_institution_mismatch_are_blocked(self):
        result = plan(clinical=[row("A", patient_id="OTHER"), row("B", institute_id="OTHER")])
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.quarantined_rows, 2)

    def test_sys_index_id_maps_to_stable_document_identity(self):
        result = plan(homology=[{**CASE, "sys_index_id": "D1", "recordcontent": "正文"}])
        self.assertEqual(result.candidates[0].key, ("D1",))

    def test_record_and_submit_times_remain_distinct(self):
        result = plan(homology=[row(recorddatetime="2026-10-02T20:14:48", submitdatetime="2026-10-02T20:45:33")])
        values = result.candidates[0].values
        self.assertEqual(values["record_datetime"], "2026-10-02T20:14:48+08:00")
        self.assertEqual(values["submit_datetime"], "2026-10-02T20:45:33+08:00")

    def test_equivalent_utc_and_beijing_times_are_equal(self):
        result = plan(clinical=[row(record_time="2026-10-02T12:14:48+00:00")], homology=[row(recorddatetime="2026-10-02T20:14:48")])
        self.assertNotIn("record_datetime", result.candidates[0].conflicts)

    def test_invalid_time_not_replaced_by_submit_time(self):
        result = plan(homology=[row(recorddatetime="not-a-time", submitdatetime="2026-10-02T20:45:33")])
        self.assertNotIn("record_datetime", result.candidates[0].values)
        self.assertIn("invalid_time:record_datetime", result.candidates[0].blockers)

    def test_json_body_used_only_when_plain_body_empty(self):
        v2 = {"record_content": [{"original_text": "第一段"}, {"original_text": "第二段"}], "physician_sign": "签署甲"}
        result = plan(clinical=[row(record_content="", v2_schema=v2)])
        self.assertEqual(result.candidates[0].values["record_content"], "第一段第二段")
        self.assertEqual(result.candidates[0].values["physician_sign"], "签署甲")

    def test_json_and_plain_body_difference_is_explicit(self):
        result = plan(clinical=[row(record_content="普通列", v2_schema={"record_content": [{"original_text": "JSON正文"}]})])
        self.assertEqual(result.candidates[0].values["record_content"], "普通列")
        self.assertIn("within_source_conflict:record_content", result.candidates[0].blockers)

    def test_deleted_source_does_not_delete_local_record(self):
        result = plan(clinical=[row(is_deleted="1")], local=[row(record_content="本地")])
        self.assertEqual(result.candidates[0].values["record_content"], "本地")
        self.assertIn("source_deleted", result.candidates[0].blockers)

    def test_verified_pathology_diagnosis_preference_is_traced(self):
        result = plan("pathology_exam_report", clinical=[{**row(), "pathology_exam_id": "R", "diagnosis": "旧诊断"}],
                      homology=[{**row(), "pathology_exam_id": "R", "diagnosis": "完整诊断"}])
        self.assertEqual(result.candidates[0].values["diagnosis"], "完整诊断")
        self.assertEqual(result.candidates[0].provenance["diagnosis"], "homology")
        self.assertIn("diagnosis", result.candidates[0].conflicts)

    def test_drug_code_conflict_blocks_cross_source_fill(self):
        result = plan("inpat_drug_order", clinical=[{**row(), "order_id": "O", "drug_code": "A"}],
                      homology=[{**row(), "order_id": "O", "drug_code": "B", "carried_datetime": "2026-10-02T10:00:00"}])
        self.assertNotIn("carried_datetime", result.candidates[0].values)
        self.assertIn("identity_conflict:drug_code", result.candidates[0].blockers)

    def test_c18_discharge_sections_survive_target_projection_and_document_assembly(self):
        fields = {"admission_condition": "入院情况甲", "positive_assist_exam": "检查结果乙",
                  "treatment_course": "诊疗经过丙", "discharge_condition": "出院情况丁", "discharge_order": "出院医嘱戊"}
        candidate = plan("discharge_record", clinical=[row("DC", record_content="", **fields)]).candidates[0]
        columns = {name: "text" for name in (*CASE, "document_id", "record_content", *fields)}
        projection = sync.project_candidate(candidate, CASE, columns)
        self.assertEqual({k: projection.values[k] for k in fields}, fields)
        sys.path.insert(0, str(MODULE.parents[2]))
        from app.services.document_assembly import assemble_document
        document = assemble_document("discharge_record", projection.values)
        self.assertTrue(all(text in document.assembled_text for text in fields.values()))

    def test_blood_body_status_and_times_survive_legacy_target_columns(self):
        candidate = plan(homology=[row(record_content="正文及明确签名", document_status="Save",
                                       record_datetime="2026-10-10T20:20:50", submit_datetime="2026-10-10T20:23:03")]).candidates[0]
        columns = {**{k: "character varying" for k in (*CASE, "document_id", "document_status")},
                   "record_content": "text", "record_time": "text", "submit_datetime": "timestamp without time zone"}
        projection = sync.project_candidate(candidate, CASE, columns)
        self.assertEqual(projection.values["document_status"], "Save")
        self.assertEqual(projection.values["record_content"], "正文及明确签名")
        self.assertEqual(projection.values["record_time"], "2026-10-10T20:20:50+08:00")
        self.assertEqual(projection.values["submit_datetime"], "2026-10-10T20:23:03")

    def test_json_section_array_can_fill_an_empty_plain_section(self):
        candidate = plan("discharge_record", clinical=[row(v2_schema={"discharge_order": [{"original_text": "出院安排"}]})]).candidates[0]
        self.assertEqual(candidate.values["discharge_order"], "出院安排")

    def test_status_fields_are_preserved_without_guessing_their_meaning(self):
        candidate = plan(homology=[row(document_status="Save", record_status="submitted")]).candidates[0]
        self.assertEqual(candidate.values["document_status"], "Save")
        self.assertEqual(candidate.values["record_status"], "submitted")
        self.assertIn("source_validity_unconfirmed", candidate.blockers)

    def test_missing_target_column_is_reported_not_silently_filtered(self):
        candidate = plan("discharge_record", clinical=[row(treatment_course="诊疗经过")]).candidates[0]
        projection = sync.project_candidate(candidate, CASE, {"document_id": "text"})
        self.assertIn("treatment_course", projection.unmapped_fields)

    def test_nonempty_invalid_original_value_is_retained_for_review(self):
        candidate = plan(local=[row(record_time="坏时间")]).candidates[0]
        self.assertEqual(candidate.raw_variants["local"]["record_time"], "坏时间")
        self.assertIn("invalid_time:record_datetime", candidate.blockers)

    def test_bad_json_is_reported_as_json_not_as_a_time_error(self):
        candidate = plan(clinical=[row(v2_schema="bad-json")]).candidates[0]
        self.assertIn("invalid_v2_schema", candidate.blockers)
        self.assertNotIn("invalid_time:v2_schema", candidate.blockers)

    def test_input_is_unchanged_and_public_report_contains_no_text_or_ids(self):
        rows = [row("PRIVATE-ID", record_content="私人正文", physician_sign="私人姓名")]
        before = deepcopy(rows)
        result = plan(clinical=rows)
        self.assertEqual(rows, before)
        import json
        rendered = json.dumps(result.report("C18"), ensure_ascii=False)
        for value in ("PRIVATE-ID", "私人正文", "私人姓名", '"patient_id"', '"visit_id"'):
            self.assertNotIn(value, rendered)


if __name__ == "__main__":
    unittest.main()
