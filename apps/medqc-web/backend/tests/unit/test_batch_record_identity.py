"""结果页病历身份回查：引用算法与正式结果信封一致，不返回姓名，只按任务范围回查。"""

from app.services.case_identity import CaseRef
from app.services.qc_workspace.batch_record_identity import build_batch_job_record_identities
from app.services.qc_workspace.canonical_result_store import keyed_ref

KEY = "synthetic-identity-key"


def _job(*refs):
    return {"filters": {"record_refs": [
        {"institute_id": inst, "patient_id": pat, "visit_id": visit} for inst, pat, visit in refs
    ]}}


def test_identity_matches_envelope_record_ref_and_omits_patient_name():
    calls = []

    def collect_records(**kwargs):
        calls.append(kwargs)
        return [{"institute_id": "院A", "patient_id": "P1", "visit_id": "V1", "patient_name": "合成姓名",
                 "mr_no": "0001", "department": "骨科", "doctor": "合成医生",
                 "admission_date": "2026-06-01", "discharge_date": "2026-06-10"}]

    items = build_batch_job_record_identities(
        job=_job(("院A", "P1", "V1"), ("院A", "P2", "V2")), collect_records=collect_records, hmac_key=KEY)

    assert items[0]["record_ref"] == keyed_ref("rec", CaseRef("院A", "P1", "V1").as_key(), hmac_key=KEY)
    assert items[0] == {**items[0], "sequence": 1, "inpatient_no": "0001", "department": "骨科",
                        "doctor": "合成医生", "admission_date": "2026-06-01", "discharge_date": "2026-06-10"}
    assert "合成姓名" not in str(items)
    # 病历池查不到的病历仍返回引用与序号，前端按序号展示。
    assert items[1]["sequence"] == 2 and items[1]["inpatient_no"] == "" and items[1]["department"] == ""
    assert calls[0]["record_refs"] == [
        {"institute_id": "院A", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "院A", "patient_id": "P2", "visit_id": "V2"},
    ]


def test_job_without_record_scope_does_not_query_records():
    def collect_records(**kwargs):
        raise AssertionError("不应查询病历")

    assert build_batch_job_record_identities(job={"filters": {}}, collect_records=collect_records, hmac_key=KEY) == []
    duplicate = _job(("院A", "P1", "V1"), ("院A", "P1", "V1"), ("", "P2", "V2"))
    seen = []
    build_batch_job_record_identities(job=duplicate, collect_records=lambda **kw: seen.append(kw) or [], hmac_key=KEY)
    assert len(seen[0]["record_refs"]) == 1
