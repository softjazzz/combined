"""同病种对照辅助查询的最小字段合同，不读取首页或修改历史材料。"""
from sqlalchemy import inspect, literal

from . import case_material_snapshot as material
from .clinical_read import clinical_read_schema
from .luxian_0609.source_evidence_reader import SourceEvidenceUnavailable


def gap_result(rule):
    """只供已确认缺少同病种对照依据的CL-276，不制造合规或不适用结论。"""
    return {"rule_id": rule.get("rule_id") or rule.get("rule_code"),
            "rule_name": rule.get("name") or rule.get("rule_name") or "",
            "status": "data_gap", "reason_code": "source_unavailable", "is_compliant": None,
            "findings": "缺少可用诊断或同病种对照材料，无法判定该项。",
            "evidence": "", "suggestion": "", "confidence": None, "evidence_verified": False,
            "data_gap_details": {"source": "diagnosis_auxiliary", "reason_code": "source_unavailable"},
            "metadata": {"tokens_used": 0, "api_time": 0.0, "executor_type": "program",
                         "evidence_source": "bundle", "screening_status": "data_gap"}}


def projected_query(session, model, required, *, optional=(), require_any=()):
    """缺业务字段是局部缺口；身份、权限、连接错误不降级。"""
    state = material.context()
    schema = state["schema"] if state is not None else clinical_read_schema()
    table = model.__tablename__
    if state is not None:
        if table not in state["columns"]:
            raise material.MaterialSnapshotError("uncaptured_material_columns")
        columns = set(state["columns"][table])
    else:
        inspector = inspect(session.connection())
        columns = ({column["name"] for column in inspector.get_columns(table, schema=schema)}
                   if inspector.has_table(table, schema=schema) else set())
    if not columns:
        raise SourceEvidenceUnavailable()
    if not {"institute_id", "patient_id", "visit_id"}.issubset(columns):
        raise material.MaterialSnapshotError("material_identity_or_source_mismatch")
    if not set(required).issubset(columns) or (require_any and not set(require_any).intersection(columns)):
        raise SourceEvidenceUnavailable()
    fields = [getattr(model, name) for name in required]
    fields.extend(getattr(model, name) if name in columns else literal("").label(name) for name in optional)
    query = session.query(*fields)
    return query.execution_options(schema_translate_map={None: schema}) if schema else query
