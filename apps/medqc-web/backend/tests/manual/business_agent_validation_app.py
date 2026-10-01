"""只供本机 M1 联调的合成接口；不导入主应用、不建库、不启动 Worker。"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))

from app.core.security import get_current_user  # noqa: E402
from app.routers.business_agent import router  # noqa: E402
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store  # noqa: E402
from app.services.qc_agent.business_access import BusinessAccess, get_business_access  # noqa: E402
from app.services.qc_agent import business_reads  # noqa: E402

app = FastAPI(title="合成业务助手验证接口")
app.include_router(router, prefix="/api/v1/qc-agent")
store = BusinessSessionStore(Path(__file__).resolve().parents[3] / ".tmp/0910-full-audit/business-agent-validation-private/metadata")
RULES = ("LX0609-01-01-01", "LX0609-01-02-01")


async def synthetic_user(request: Request):
    if request.headers.get("authorization") != "Bearer synthetic-business-agent":
        raise HTTPException(401, "合成联调专用身份无效")
    return {"id": "synthetic-validation", "roles": ["doctor", "qc_manager"]}


app.dependency_overrides[get_current_user] = synthetic_user
app.dependency_overrides[get_business_store] = lambda: store
app.dependency_overrides[get_business_access] = lambda: BusinessAccess({"version": 1, "accounts": {"synthetic-validation": {
    "doctor_cases": [{"institute_id": "SYNTHETIC", "patient_id": patient, "visit_id": f"{patient}1"} for patient in ("A", "B")],
    "manager_scopes": [{"institute_id": "SYNTHETIC", "department": "合成科室"}],
}}})


@app.get("/api/v1/qc/sichuan/workspace/records/{visit_id}/latest-result")
def saved_result(visit_id: str, institute_id: str, patient_id: str, user=Depends(synthetic_user)):
    if institute_id != "SYNTHETIC" or (patient_id, visit_id) not in {("A", "A1"), ("B", "B1")}:
        raise HTTPException(404, "合成病例不存在")
    return {"data": {"state": "ready", "job_id": f"synthetic-job-{patient_id}", "record_ref": f"synthetic-record-{patient_id}", "rule_set_version": "synthetic-v1", "is_complete": True, "missing_rule_ids": [],
                     "items": [{"rule_id": rule_id, "qc_point": f"合成问题 {index + 1}", "status": "non_compliant", "conclusion": f"合成病例{patient_id}的问题{index + 1}：保存时确认必填字段缺失。", "suggestion": "原保存建议：请核对合成记录的必填字段。", "reason_code": "synthetic_missing_field", "evidence": [{"source_type": "admission_record", "source_ref": f"src_synthetic_{patient_id}", "record_time": "2026-09-01T10:00:00+08:00", "field_path": f"synthetic.field_{index + 1}", "evidence_excerpt": f"合成原文{patient_id}：字段{index + 1}为空。"}]} for index, rule_id in enumerate(RULES)]}}


@app.get("/api/v1/workstation/qc-result-analysis/luxian-0609")
def statistics(request: Request, user=Depends(synthetic_user)):
    return {"data": synthetic_statistics(dict(request.query_params))}


def synthetic_statistics(filters):
    return {"scope": filters, "kpis": {"scoped_record_total": 2, "ready_record_total": 2, "unavailable_result_total": 0},
                     "status_distribution": [{"status": "non_compliant", "count": 4}],
                     "rule_distribution": [{"rule_id": rule_id, "rule_name": f"合成问题 {index + 1}", "non_compliant_count": 2, "data_gap_count": 0, "evaluated_count": 2} for index, rule_id in enumerate(RULES)],
                     "record_page": {"page": 1, "page_size": 20, "total": 2, "items": [{"institute_id": "SYNTHETIC", "patient_id": patient, "visit_id": f"{patient}1", "patient_name": f"合成病例{patient}", "department": "合成科室", "status": "ready", "completed_at": "2026-09-02T10:00:00+08:00"} for patient in ("A", "B")]}}


# 仅此合成应用替换数据读服务；生产授权及路由检查保持真实实现。
business_reads.saved_record = lambda identity: saved_result(**identity)["data"]
business_reads.department_analysis = lambda **filters: synthetic_statistics(filters)
business_reads.scoped_records = lambda **_: [{"institute_id": "SYNTHETIC", "patient_id": patient, "visit_id": f"{patient}1", "department": "合成科室"} for patient in ("A", "B")]
