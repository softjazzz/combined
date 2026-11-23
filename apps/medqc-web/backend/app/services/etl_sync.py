"""
ETL 同步服务 — 从远端 PostgreSQL 拉取数据写入本地 PostgreSQL。

当前支持两种模式：
- table: 按远端表 + 日期字段抽取（默认）
- procedure: 调用远端存储过程（兼容回退）
"""

import os
import json
from .clinical_source_policy import legacy_sync_operation

import logging
import re
import uuid
from contextlib import nullcontext
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Callable, Dict, List, Optional, Any, Tuple, Sequence
from dataclasses import dataclass, field, asdict

import psycopg2
import psycopg2.extras
from psycopg2.extensions import make_dsn
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database.connection import DB_SCHEMA_MODE, engine
from .visit_index_service import ingest_sync_rows
from .sync_policy import load_sync_policy
from .config_registry import get_config, set_config
from ..core.clinical_defaults import UNCONFIGURED_INSTITUTE_ID, get_clinical_defaults
from .case_identity import CaseRef, CaseRefInput, normalize_case_refs
from .case_scope_service import ACTIVE_ADMISSION_LOOKBACK_DAYS
from .homology_sync import HOMOLOGY_TABLE_KEYS, resolve_homology_source

logger = logging.getLogger(__name__)

_SYNC_LOCK_KEY = int(os.getenv("PG_SYNC_LOCK_KEY", "2026032601"))
_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))
_runtime_remote_password: str = ""
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VISIT_INDEX_ANCHOR_TABLES = {"admission_record", "discharge_record", "mr"}
_VISIT_KEY_CHUNK_SIZE = max(100, int(os.getenv("PG_SYNC_VISIT_KEY_CHUNK", "500")))
_LOCAL_TARGET_SCHEMAS_RAW = tuple(
    s.strip()
    for s in str(os.getenv("PG_LOCAL_TARGET_SCHEMAS", "public,cdm")).split(",")
    if s.strip()
)
_SCENE_ANCHOR_TABLES = {
    "running": {"admission_record"},
    "final": {"discharge_record"},
    "frontpage": {"mr"},
    "coding": {"mr"},
    "settlement": {"medical_insurance_settlement"},
    "both": {"admission_record", "discharge_record", "mr"},
}
_SUPPORTED_INCREMENTAL_STRATEGIES = frozenset(
    {"updated_at", "append_only_record_time", "full_visit_reload"}
)
_SYNC_CURSOR_SCHEMA_VERSION = "sample-sync-v1"
_DOCUMENT_ID_SOURCE_CANDIDATES = ("document_id", "sys_index_id", "id")
_AUTHORITATIVE_DOCUMENT_TIME_COLUMNS = (
    "record_time",
    "record_datetime",
    "submit_time",
    "submit_datetime",
)

# 病程签名保持各角色独立，只统一已核实的签署时间别名；不以提交人补签名。
_COURSE_SIGNATURE_COLUMN_ALIASES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    table: {
        "physician_sign": ("physician_sign",),
        "physician_sign_datetime": ("physician_sign_datetime", "physician_sign_time"),
    }
    for table in ("daily_course_record", "senior_course_record", "postsurg_firstcourse_record")
}
_COURSE_SIGNATURE_COLUMN_ALIASES["senior_course_record"].update({
    "recorder_sign": ("recorder_sign",),
    "attending_physician_sign": ("attending_physician_sign",),
    "senior_physician_sign": ("senior_physician_sign",),
    "seniorphy_sign_datetime": ("seniorphy_sign_datetime", "seniorphy_sign_time"),
})
_COURSE_SIGNATURE_COLUMN_ALIASES["postsurg_firstcourse_record"]["surgeon_sign"] = ("surgeon_sign",)

# 源库字段与本地 CDM 列名不一致时的同步映射（目标列 -> 源候选列）。
# 仅在目标列存在、本条记录未携带目标列时生效。
_TABLE_COLUMN_ALIASES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    **_COURSE_SIGNATURE_COLUMN_ALIASES,
    "death_record": {
        "death_datetime": ("death_datetime", "death_time"),
    },
    "discharge_record": {
        "chief_physician_sign_datetime": ("chief_physician_sign_datetime", "cheifphy_sign_time"),
    },
    "admission_record": {
        # 客户源表以 record_time / sys_index_id 表示文书时间和稳定身份；
        # 001/002 必须用同一份本地字段计算并定位，不能只在展示层读取原值。
        "document_id": ("document_id", "sys_index_id", "id"),
        "record_datetime": (
            "record_datetime",
            "record_time",
            "submit_datetime",
            "submit_time",
        ),
    },
    "first_course_record": {
        # 泸县源库首程记录常以 submit_time 表示文书完成/记录时间，record_time 可能为空。
        # 最后修改和医师签署时间都不能证明首次完成时间，不得提升为 record_datetime。
        "document_id": ("document_id", "sys_index_id", "id"),
        "record_datetime": (
            "record_datetime",
            "record_time",
            "submit_datetime",
            "submit_time",
        ),
        "physician_sign_datetime": ("physician_sign_datetime", "physician_sign_time"),
    },
    "mr_surgery": {
        "surgery_begin_datetime": ("surgery_begin_time",),
        "surgery_end_datetime": ("surgery_end_time",),
    },
    "inpat_drug_order": {
        "prescribed_datetime": (
            "prescribed_datetime",
            "prescribed_time",
        ),
        # 源字段仅表示计划开始/启用时间，必须与开立时间独立保存。
        "planned_start_datetime": (
            "planned_start_datetime",
            "planned_start_time",
        ),
        "planned_end_datetime": (
            "planned_end_datetime",
            "planned_end_time",
        ),
        "order_status": ("order_status", "status"),
        "generic_name": ("generic_name", "drug_name", "order_item_name", "order_item"),
        "drug_specification": ("drug_specification", "specification"),
        "drug_frequency": ("drug_frequency", "frequency"),
        "drug_apply_method": ("drug_apply_method", "route"),
        "single_dose": ("single_dose", "dose", "dosage"),
        "single_dose_unit": ("single_dose_unit", "dose_unit"),
    },
    "inpat_nondrug_order": {
        "prescribed_datetime": (
            "prescribed_datetime",
            "prescribed_time",
            "start_time",
            "order_start_time",
            "order_time",
        ),
        "planned_start_datetime": (
            "planned_start_datetime",
            "planned_start_time",
        ),
        "planned_end_datetime": (
            "planned_end_datetime",
            "planned_end_time",
        ),
        "order_status": ("order_status", "status"),
        "order_name": ("order_name", "item_name", "order_item_name", "order_item"),
    },
    "inpat_bill_item": {
        "billing_datetime": ("billing_datetime", "billing_time", "charge_time", "bill_time"),
    },
    "blood_application": {
        # 客户源库常用 apply_no/blood_* 命名；本地 CDM 则以 application_id
        # 及 transfuse_* 作为正式字段。申请号是本地复合主键的一部分，不能丢失。
        "application_id": ("application_id", "apply_no", "application_no"),
        "patient_bloodtype_abo": (
            "patient_bloodtype_abo",
            "blood_type",
            "abo_blood_type",
        ),
        "transfuse_variety": ("transfuse_variety", "blood_component"),
        "transfuse_volume": ("transfuse_volume", "blood_amount"),
        "transfuse_volume_unit": ("transfuse_volume_unit", "blood_unit"),
        "request_datetime": (
            "request_datetime",
            "apply_datetime",
            "apply_time",
            "application_datetime",
            "application_time",
            "request_time",
        ),
        "physician_name": ("physician_name", "apply_doctor", "request_physician"),
        "reason_for_blood": (
            "reason_for_blood",
            "transfusion_reason",
            "transfusion_indication",
        ),
    },
    "consent_form": {
        # 输血治疗同意书等专用同意书的标准字段需映射到通用同意书投影。
        # 042 逐项校验这些事实；不能只依赖可能为空的 record_content。
        "name": ("name", "patient_name"),
        "transfusion_reason": (
            "transfusion_reason",
            "transfution_indication",
            "transfusion_indication",
            "indication",
        ),
        "blood_component": ("blood_component", "transfuse_variety"),
        "alternative_plan": ("alternative_plan", "replace_scheme"),
        "patient_sign_datetime": (
            "patient_sign_datetime",
            "patient_agentsign_datetime",
            "patient_sign_time",
        ),
        "physician_sign_datetime": (
            "physician_sign_datetime",
            "physician_sign_time",
            "sign_datetime",
            "sign_time",
        ),
    },
    "consultation_record": {
        # 客户源库用 consult_apply_time 表示会诊申请时间；本地统一为
        # request_time，并同时保留会诊完成时间和记录时间供 069 逐事件核对。
        "request_time": ("request_time", "consult_apply_time"),
        "consultation_time": ("consultation_time",),
        "record_time": ("record_time",),
    },
    "handoff_record": {
        # 071 的交接窗口必须采用实际交班时间；部分源库不会同时填 record_time。
        "record_time": (
            "record_time",
            "handoff_time",
            "submit_datetime",
            "submit_time",
        ),
        "shift_time": ("shift_time", "handoff_time"),
        "handoff_doctor": ("handoff_doctor",),
    },
    "handover_record": {
        # 同上，接班记录的权威时间可能以 handover_time 单独提供。
        "record_time": (
            "record_time",
            "handover_time",
            "submit_datetime",
            "submit_time",
        ),
        "shift_time": ("shift_time", "handover_time"),
        "handover_doctor": ("handover_doctor",),
    },
    "mr_bloodtrans": {
        "transfution_datetime": (
            "transfution_datetime",
            "transfution_time",
            "transfusion_datetime",
            "transfusion_time",
            "blood_transfusion_time",
        ),
    },
    "labtest_item_report": {
        "document_id": ("document_id", "sys_index_id", "print_order_id"),
        "submit_datetime": ("submit_datetime", "report_time", "report_datetime", "result_datetime"),
        "record_content": ("record_content", "content", "summary_text"),
    },
    "exam_item_report": {
        "document_id": ("document_id", "sys_index_id"),
        "submit_datetime": ("submit_datetime", "report_time", "report_datetime", "exam_datetime"),
        "record_content": (
            "record_content",
            "exam_result",
            "exam_impression",
            "exam_conclusion",
            "exam_findings",
            "findings",
            "impression",
            "conclusion",
            "description",
            "summary_text",
            "content",
        ),
    },
    "exam_master": {
        # 客户检查主表的检查/报告时间及报告状态存在两套标准命名；本地
        # evidence reader 使用 exam_time/report_time/report_status，必须在落库时
        # 统一，不能让已同步的影像报告再次被当作没有资料。
        "exam_time": ("exam_time", "exam_datetime"),
        "report_time": ("report_time", "report_datetime"),
        "report_status": ("report_status", "exam_result_status"),
    },
}

_GLOBAL_COLUMN_ALIASES: Dict[str, Tuple[str, ...]] = {
    # 客户源库的多数文书表以 sys_index_id 作稳定行标识。若本地 CDM
    # 仅有 document_id，必须在落库时完成同一字段映射；否则页面能列出
    # 文书而规则无法定位其证据，形成“可见但不可核对”的错位。
    "document_id": ("document_id", "sys_index_id", "id"),
    "admission_datetime": ("admission_datetime", "admission_time"),
    "discharge_datetime": ("discharge_datetime", "discharge_time"),
    "last_modified_datetime": ("last_modified_datetime", "last_modified_time"),
    # 很多本地文书表只有 submit_datetime，而客户源表只给 record_time。
    # 二者均是文书已形成的权威时间，必须至少保存到一个可读取字段。
    "submit_datetime": (
        "submit_datetime",
        "submit_time",
        "record_datetime",
        "record_time",
    ),
    "record_datetime": ("record_datetime", "record_time", "round_time"),
    "report_datetime": ("report_datetime", "report_time", "result_datetime", "result_time", "exam_datetime", "exam_time"),
    "request_datetime": ("request_datetime", "request_time", "apply_datetime", "apply_time", "application_time"),
    "review_datetime": ("review_datetime", "review_time", "audit_time", "verify_time"),
    "mr_datetime": ("mr_datetime", "mr_time", "submit_datetime", "submit_time"),
    "diagnosis_datetime": ("diagnosis_datetime", "diagnosis_time"),
    "settle_datetime": ("settle_datetime", "settle_time", "settlement_time"),
}

# 部分文书源表以结构化章节保存正文。CDM 当前只保留通用文书列和
# record_content；若同步时不组装正文，这些章节会在列过滤阶段被静默丢弃。
# 结构化章节与叙述正文互补，按稳定顺序合并保留；空字段不生成章节，
# 便于展示、质控和真实病例回放。
_STRUCTURED_DOCUMENT_CONTENT_FIELDS: Dict[str, Tuple[Tuple[str, Tuple[str, ...]], ...]] = {
    # 客户死亡记录的 record_content 常为空，正文在这些独立字段中；
    # 必须在目标列过滤之前合并保存，死亡时间不能用文书完成时间代替。
    "death_record": (
        ("入院时间", ("admission_datetime", "admission_time")),
        ("入院情况", ("admission_condition",)),
        ("诊疗经过", ("treatment_course",)),
        ("死亡时间", ("death_datetime", "death_time")),
        ("死亡原因", ("death_reason",)),
    ),
    "presurg_summary": (
        ("术前诊断", ("preoperative_diagnosis", "preop_diagnosis", "surgery_diagnosis", "diagnosis")),
        ("简要病情", ("condition_summary",)),
        ("诊断依据", ("diagnose_based_on", "diagnosis_basis")),
        ("辅助检查", ("assist_exam",)),
        ("手术适应症", ("surgery_indication",)),
        ("手术禁忌症", ("surgery_contraindication",)),
        ("会诊意见", ("consultation_suggestion",)),
        ("拟实施手术", ("planned_surgery_name", "surgery_method")),
        ("手术部位", ("planned_surgery_position_name",)),
        ("手术时间", ("planned_surgery_time", "planned_surgery_datetime", "surgery_datetime", "surgery_time")),
        ("麻醉方式", ("planned_anesthesia_method", "anesthesia_method")),
        ("手术要点", ("surgery_point",)),
        ("术前准备", ("surgery_preparation",)),
        ("术后可能发生的并发症", ("postsurg_complication",)),
        ("术后处理", ("postsurg_operation",)),
        ("参加人员", ("participants",)),
        ("手术医师签名", ("surgeon_sign",)),
        ("记录人签名", ("recorder_sign",)),
    ),
    "surgery_safecheck_record": (
        ("手术时间", ("surgery_begin_time", "surgery_begin_datetime", "surgery_datetime", "surgery_time")),
        ("手术方式", ("surgery_method",)),
        ("手术医师", ("surgeon",)),
        ("麻醉方式", ("anesthesia_method",)),
        ("麻醉医师", ("anesthesiologist",)),
        ("手术护士", ("surgery_nurse",)),
        ("手术医师签名", ("surgeon_sign", "surgeon_signature", "surgeon_signature_name")),
        ("麻醉医师签名", ("anesthesiologist_sign", "anesthesiologist_signature", "anesthetist_sign")),
        ("手术护士签名", ("surgery_nurse_sign", "surg_nurse_sign", "surgery_nurse_signature")),
        ("手术前手术医师签名", ("preoperative_surgeon_sign", "before_surgery_surgeon_sign")),
        ("手术前麻醉医师签名", ("preoperative_anesthesiologist_sign", "before_surgery_anesthesiologist_sign")),
        ("手术前手术护士签名", ("preoperative_surgery_nurse_sign", "before_surgery_surgery_nurse_sign")),
        ("切皮前手术医师签名", ("before_incision_surgeon_sign",)),
        ("切皮前麻醉医师签名", ("before_incision_anesthesiologist_sign",)),
        ("切皮前手术护士签名", ("before_incision_surgery_nurse_sign",)),
        ("离室前手术医师签名", ("before_leave_surgeon_sign", "before_exit_surgeon_sign")),
        ("离室前麻醉医师签名", ("before_leave_anesthesiologist_sign", "before_exit_anesthesiologist_sign")),
        ("离室前手术护士签名", ("before_leave_surgery_nurse_sign", "before_exit_surgery_nurse_sign")),
        ("手术医师陈述", ("surgeon_statement",)),
        ("麻醉医师陈述", ("anesthesiologist_statement",)),
        ("手术护士陈述", ("surg_nurse_statement",)),
    ),
    "anesthesia_record": (
        ("拟实施手术", ("planned_surgery",)),
        ("手术名称", ("surgery_name",)),
        ("手术编码", ("surgery_code",)),
        ("手术体位", ("surgery_bodypost",)),
        ("麻醉方式", ("anesthesia_method",)),
        ("气管插管类型", ("trachea_intubate_type",)),
        ("麻醉体位", ("anesthesia_bodypost",)),
        ("呼吸类型", ("breath_type",)),
        ("麻醉描述", ("anesthesia_description",)),
        ("麻醉合并症", ("anesthesia_complication_sign",)),
        ("诊疗经过", ("treatment_course",)),
        ("穿刺过程", ("puncture_process",)),
        ("麻醉前用药", ("preanes_medication",)),
        ("ASA 分级", ("ASA_level", "asa_level")),
        ("手术开始时间", ("surgery_begin_datetime", "surgery_begin_time")),
        ("手术结束时间", ("surgery_end_datetime", "surgery_end_time")),
        ("麻醉开始时间", ("anesthesia_begin_datetime", "anesthesia_begin_time")),
        ("麻醉结束时间", ("anesthesia_end_datetime", "anesthesia_end_time")),
        ("离室时间", ("leave_operateroom_datetime", "leave_operating_room_datetime", "leave_operateroom_time")),
        ("出血量", ("bleed_volume",)),
        ("尿量", ("urine_volume",)),
        ("患者去向", ("patient_whereabout",)),
        ("意识状态", ("conscious_status",)),
        ("麻醉前收缩压", ("preanes_sbp",)),
        ("麻醉前舒张压", ("preanes_dbp",)),
        ("麻醉前体温", ("preanes_temperature",)),
        ("麻醉前心率", ("preanes_hr",)),
        ("麻醉前脉率", ("preanes_pr",)),
        ("麻醉前呼吸频率", ("preanes_rr",)),
        ("麻醉前血氧饱和度", ("preanes_spo", "preanes_spo2")),
        ("药物商品名", ("brand_name", "preanes_medication_brand_name")),
        ("药物名称", ("generic_name", "preanes_medication_generic_name", "drug_name", "brand_name")),
        ("国药准字号", ("cfda_id",)),
        ("药物编码", ("drug_code",)),
        ("药物剂型", ("dose_form",)),
        ("单次剂量", ("single_dose",)),
        ("单次剂量单位", ("single_dose_unit",)),
        ("数量", ("quantity",)),
        ("总剂量", ("dosage",)),
        ("总剂量单位", ("dosage_unit",)),
        ("给药途径", ("drug_apply_method", "administration_route")),
        ("麻醉效果", ("anesthesia_effect",)),
        ("麻醉总结", ("anesthesia_summary",)),
        ("麻醉中处理措施", ("anesthesia_management_measures",)),
        ("呼吸管理", ("respiratory_management",)),
        ("诱导情况", ("inducing_situation",)),
        ("麻醉医师签名", ("anesthetist_sign",)),
        ("麻醉医师签名时间", ("anesthetist_sign_datetime", "anesthetist_sign_time")),
    ),
    "surgery_inventory_record": (
        ("手术名称", ("surgery_name",)),
        ("手术日期", ("surgery_date",)),
        ("手术间", ("surgery_room_name",)),
        ("入室时间", ("surgery_room_enter_time",)),
        ("出室时间", ("surgery_room_leave_time",)),
        ("药物过敏史", ("allergy",)),
    ),
}


def _get_local_target_schemas() -> Tuple[str, ...]:
    normalized: List[str] = []
    seen: set[str] = set()
    for schema in _LOCAL_TARGET_SCHEMAS_RAW:
        name = str(schema or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    if "public" not in seen:
        normalized.append("public")
    if "cdm" not in seen:
        normalized.append("cdm")
    return tuple(normalized)


_LOCAL_TARGET_SCHEMAS = _get_local_target_schemas()
_CDM_TARGET_SCHEMA = "cdm"


def _pg_required_in_current_env() -> bool:
    env = str(os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production"}


# ==================== 同步状态管理 ====================

@dataclass
class SyncLog:
    """单次同步记录"""
    table_name: str
    source: str
    stage: str = "schema_check"
    # 兼容旧前端字段，后续可清理
    stored_procedure: str = ""
    record_count: int = 0
    status: str = "pending"  # pending / running / success / failed
    error_msg: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class SyncState:
    """全局同步状态"""
    is_running: bool = False
    last_sync_time: Optional[str] = None
    last_sync_status: str = "never"  # never / success / partial / failed
    total_records_synced: int = 0
    logs: List[Dict] = field(default_factory=list)
    progress: Dict[str, Any] = field(default_factory=dict)
    remote_connected: bool = False
    local_connected: bool = False


# 全局状态（内存中维护，重启后重置）
_sync_state = SyncState()


def _ensure_sync_job_state_table(session: Session):
    exists = session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'qc'
              AND table_name = 'sync_job_state'
            """
        )
    ).first()
    if not exists:
        raise RuntimeError("缺少 qc.sync_job_state（请先执行 Alembic 迁移）")


def _upsert_sync_job_state(state: SyncState):
    if engine is None:
        if _pg_required_in_current_env():
            raise RuntimeError("PG 未就绪：生产环境禁止 etl_sync sync_state 内存回退")
        return
    payload = asdict(state)
    with Session(engine) as session:
        _ensure_sync_job_state_table(session)
        session.execute(
            text(
                f"""
                INSERT INTO {_SYNC_JOB_STATE_TABLE} (
                    job_name, is_running, last_sync_time, last_sync_status,
                    total_records_synced, logs_json, progress_json,
                    remote_connected, local_connected, updated_at
                )
                VALUES (
                    'pg_sync', :is_running, :last_sync_time, :last_sync_status,
                    :total_records_synced, :logs_json, :progress_json,
                    :remote_connected, :local_connected, CURRENT_TIMESTAMP
                )
                ON CONFLICT (job_name)
                DO UPDATE SET
                    is_running = EXCLUDED.is_running,
                    last_sync_time = EXCLUDED.last_sync_time,
                    last_sync_status = EXCLUDED.last_sync_status,
                    total_records_synced = EXCLUDED.total_records_synced,
                    logs_json = EXCLUDED.logs_json,
                    progress_json = EXCLUDED.progress_json,
                    remote_connected = EXCLUDED.remote_connected,
                    local_connected = EXCLUDED.local_connected,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "is_running": bool(payload.get("is_running")),
                "last_sync_time": str(payload.get("last_sync_time") or ""),
                "last_sync_status": payload.get("last_sync_status") or "never",
                "total_records_synced": int(payload.get("total_records_synced") or 0),
                "logs_json": json.dumps(payload.get("logs") or [], ensure_ascii=False),
                "progress_json": json.dumps(payload.get("progress") or {}, ensure_ascii=False),
                "remote_connected": bool(payload.get("remote_connected")),
                "local_connected": bool(payload.get("local_connected")),
            },
        )
        session.commit()


def get_sync_state() -> Dict:
    """获取当前同步状态（优先读取数据库状态，回退内存）"""
    if engine is None:
        if _pg_required_in_current_env():
            raise RuntimeError("PG 未就绪：生产环境禁止 etl_sync sync_state 内存回退")
        return asdict(_sync_state)
    try:
        with Session(engine) as session:
            _ensure_sync_job_state_table(session)
            row = session.execute(
                text(
                    f"""
                    SELECT
                        is_running, last_sync_time, last_sync_status, total_records_synced,
                        logs_json, progress_json, remote_connected, local_connected
                    FROM {_SYNC_JOB_STATE_TABLE}
                    WHERE job_name = 'pg_sync'
                    """
                )
            ).mappings().first()
            if not row:
                _upsert_sync_job_state(_sync_state)
                return asdict(_sync_state)
            logs = row.get("logs_json") or []
            progress = row.get("progress_json") or {}
            last_sync_time = row.get("last_sync_time")
            if hasattr(last_sync_time, "strftime"):
                last_sync_time = last_sync_time.strftime("%Y-%m-%d %H:%M:%S")
            elif last_sync_time is not None:
                last_sync_time = str(last_sync_time)
            if isinstance(logs, str):
                try:
                    logs = json.loads(logs)
                except Exception:
                    logs = []
            if isinstance(progress, str):
                try:
                    progress = json.loads(progress)
                except Exception:
                    progress = {}
            return {
                "is_running": bool(row.get("is_running")),
                "last_sync_time": last_sync_time,
                "last_sync_status": row.get("last_sync_status") or "never",
                "total_records_synced": int(row.get("total_records_synced") or 0),
                "logs": logs if isinstance(logs, list) else [],
                "progress": dict(progress) if isinstance(progress, dict) else {},
                "remote_connected": bool(row.get("remote_connected")),
                "local_connected": bool(row.get("local_connected")),
            }
    except Exception as exc:
        if _pg_required_in_current_env():
            raise RuntimeError("读取 qc.sync_job_state 失败：生产环境禁止回退内存状态") from exc
        logger.warning("读取 sync_job_state 失败，回退内存状态: %s", exc)
        return asdict(_sync_state)


# ==================== 配置文件持久化 ====================

_CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
_CONFIG_FILE = _CONFIG_DIR / "db_config.json"
_SYNC_TABLES_FILE = _CONFIG_DIR / "sync_tables.json"
_DB_CONFIG_NAMESPACE = "sync"
_DB_CONFIG_KEY = "pg_source_config"
_TABLE_CONFIG_NAMESPACE = "sync"
_TABLE_CONFIG_KEY = "sync_tables"
_SYNC_JOB_STATE_TABLE = "qc.sync_job_state"
_SYNC_RUN_DETAILS_TABLE = "qc.sync_run_details"
_SYNC_ERROR_TABLE = "qc.sync_error_records"

_DEFAULT_CONFIG = {
    "remote_host": "192.168.140.160",
    "remote_port": "5432",
    "remote_database": "clinical_data",
    "remote_username": "postgres",
    "remote_password_ref": "env:REMOTE_DB_PASSWORD",
    "remote_schema": "public",
    "sync_mode": "table",  # table | procedure
}


def _safe_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"非法标识符: {name}")
    return name


def _ensure_sync_tracking_tables(session: Session) -> None:
    required = (
        ("qc", "sync_run_details"),
        ("qc", "sync_error_records"),
    )
    missing: list[str] = []
    for schema_name, table_name in required:
        exists = session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                """
            ),
            {"schema_name": schema_name, "table_name": table_name},
        ).first()
        if not exists:
            missing.append(f"{schema_name}.{table_name}")
    if missing:
        raise RuntimeError(f"缺少同步追踪表（请先执行 Alembic 迁移）: {', '.join(missing)}")


def _record_sync_run_detail(
    *,
    run_id: str,
    source_table: str,
    target_table: str,
    status: str,
    pulled_count: int,
    upserted_count: int,
    failed_count: int,
    started_at: Optional[datetime],
    finished_at: Optional[datetime],
    error_message: str = "",
) -> None:
    if engine is None:
        if _pg_required_in_current_env():
            raise RuntimeError("PG 未就绪：生产环境禁止 etl_sync tracking 内存回退")
        return
    if not run_id:
        return
    with Session(engine) as session:
        _ensure_sync_tracking_tables(session)
        session.execute(
            text(
                f"""
                INSERT INTO {_SYNC_RUN_DETAILS_TABLE} (
                    id, run_id, source_table, target_table, status,
                    pulled_count, upserted_count, failed_count,
                    started_at, finished_at, error_message, created_at
                )
                VALUES (
                    :id, :run_id, :source_table, :target_table, :status,
                    :pulled_count, :upserted_count, :failed_count,
                    :started_at, :finished_at, :error_message, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": str(run_id).strip(),
                "source_table": str(source_table).strip(),
                "target_table": str(target_table).strip() or None,
                "status": str(status).strip()[:20] or "unknown",
                "pulled_count": max(0, int(pulled_count)),
                "upserted_count": max(0, int(upserted_count)),
                "failed_count": max(0, int(failed_count)),
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": str(error_message or "")[:2000],
            },
        )
        session.commit()


def _record_sync_error(
    *,
    run_id: str,
    source_table: str,
    source_primary_key: str,
    visit_id: str = "",
    error_code: str = "",
    error_message: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    if engine is None:
        if _pg_required_in_current_env():
            raise RuntimeError("PG 未就绪：生产环境禁止 etl_sync tracking 内存回退")
        return
    if not run_id:
        return
    with Session(engine) as session:
        _ensure_sync_tracking_tables(session)
        session.execute(
            text(
                f"""
                INSERT INTO {_SYNC_ERROR_TABLE} (
                    id, run_id, source_table, source_primary_key, visit_id,
                    error_code, error_message, payload_json, retry_count, created_at
                )
                VALUES (
                    :id, :run_id, :source_table, :source_primary_key, :visit_id,
                    :error_code, :error_message, :payload_json, 0, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": str(run_id).strip(),
                "source_table": str(source_table).strip(),
                "source_primary_key": str(source_primary_key or "")[:300],
                "visit_id": str(visit_id or "")[:100] or None,
                "error_code": str(error_code or "")[:80] or None,
                "error_message": str(error_message or "")[:2000],
                "payload_json": json.dumps(payload or {}, ensure_ascii=False),
            },
        )
        session.commit()


def _parse_local_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    if " " in text_value and "T" not in text_value:
        text_value = text_value.replace(" ", "T")
    if text_value.endswith("Z"):
        text_value = text_value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text_value)
    except Exception:
        return None


def _normalize_sync_scene(scene: Optional[str]) -> str:
    normalized = str(scene or "").strip().lower()
    if normalized in {"running", "final", "frontpage", "coding", "settlement", "both"}:
        return normalized
    return "both"


def _apply_sync_column_aliases(
    *,
    table_name: str,
    record: Dict[str, Any],
    existing_columns: set[str],
) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {str(k).lower(): v for k, v in record.items()}
    if table_name.strip().lower() == "discharge_record" and isinstance(normalized.get("v2_schema"), (dict, list)):
        normalized["v2_schema"] = json.dumps(normalized["v2_schema"], ensure_ascii=False)
    _apply_sync_alias_map(
        normalized=normalized,
        existing_columns=existing_columns,
        alias_map=_build_generic_column_aliases(existing_columns),
    )
    alias_map = _TABLE_COLUMN_ALIASES.get(str(table_name or "").strip().lower(), {})
    if alias_map:
        _apply_sync_alias_map(
            normalized=normalized,
            existing_columns=existing_columns,
            alias_map=alias_map,
        )
    _apply_sync_derived_fields(
        table_name=table_name,
        normalized=normalized,
        existing_columns=existing_columns,
    )
    _validate_document_field_preservation(
        table_name=table_name,
        normalized=normalized,
        existing_columns=existing_columns,
    )
    _validate_order_time_preservation(
        table_name=table_name,
        normalized=normalized,
        existing_columns=existing_columns,
    )
    return normalized


def _build_generic_column_aliases(existing_columns: set[str]) -> Dict[str, Tuple[str, ...]]:
    alias_map: Dict[str, Tuple[str, ...]] = {}
    for column_name in existing_columns:
        candidates: List[str] = list(_GLOBAL_COLUMN_ALIASES.get(column_name, ()))
        if column_name.endswith("_datetime"):
            base_name = column_name[: -len("_datetime")]
            candidates.extend((f"{base_name}_time", f"{base_name}_date"))
        elif column_name.endswith("_updatetime"):
            base_name = column_name[: -len("_updatetime")]
            candidates.extend((f"{base_name}_uptime", f"{base_name}_update_time"))
        if not candidates:
            continue
        seen: set[str] = set()
        unique_candidates: List[str] = []
        for candidate in candidates:
            normalized_candidate = str(candidate or "").strip().lower()
            if not normalized_candidate or normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            unique_candidates.append(normalized_candidate)
        alias_map[column_name] = tuple(unique_candidates)
    return alias_map


def _apply_sync_alias_map(
    *,
    normalized: Dict[str, Any],
    existing_columns: set[str],
    alias_map: Dict[str, Tuple[str, ...]],
) -> None:
    for target_col, source_cols in alias_map.items():
        if target_col not in existing_columns:
            continue
        current_value = normalized.get(target_col)
        if current_value not in (None, ""):
            continue
        for source_col in source_cols:
            alias_value = normalized.get(source_col)
            if alias_value in (None, ""):
                continue
            normalized[target_col] = alias_value
            break


def _first_non_empty(record: Dict[str, Any], field_names: Tuple[str, ...]) -> str:
    for field_name in field_names:
        value = record.get(field_name)
        if value in (None, ""):
            continue
        text_value = str(value).strip()
        if text_value:
            return text_value
    return ""


def _compose_structured_document_content(
    *,
    table_name: str,
    normalized: Dict[str, Any],
) -> str:
    fields = _STRUCTURED_DOCUMENT_CONTENT_FIELDS.get(str(table_name or "").strip().lower(), ())
    fragments: List[str] = []
    for label, source_fields in fields:
        value = _first_non_empty(normalized, source_fields)
        if value:
            fragments.append(f"{label}：{value}")
    return "\n".join(fragments)


def _apply_sync_derived_fields(
    *,
    table_name: str,
    normalized: Dict[str, Any],
    existing_columns: set[str],
) -> None:
    normalized_table = str(table_name or "").strip().lower()
    if (
        normalized_table == "senior_course_record"
        and "document_title" in existing_columns
        and not _first_non_empty(normalized, ("document_title",))
    ):
        ward_round_type = _first_non_empty(
            normalized,
            ("ward_round_type", "round_type"),
        )
        if not ward_round_type:
            # 源表普通列可能为空，查房类型仍保存在二级结构化的同名字段中。
            payload = normalized.get("v2_schema")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = None
            if isinstance(payload, dict):
                candidate = payload.get("ward_round_type")
                if isinstance(candidate, str):
                    ward_round_type = candidate.strip()
        if ward_round_type:
            normalized["document_title"] = (
                ward_round_type
                if ward_round_type.endswith("记录")
                else f"{ward_round_type}记录"
            )

    if "document_id" in existing_columns and not _first_non_empty(normalized, ("document_id",)):
        if normalized_table == "labtest_item_report":
            test_no = _first_non_empty(normalized, ("test_no", "test_id"))
            item_no = _first_non_empty(normalized, ("item_no", "item_id", "item_code", "item_name"))
            if test_no or item_no:
                normalized["document_id"] = f"lab:{test_no or '-'}:{item_no or '-'}"
        elif normalized_table == "exam_item_report":
            exam_no = _first_non_empty(normalized, ("exam_no", "exam_id"))
            item_no = _first_non_empty(normalized, ("item_no", "item_id", "item_code", "exam_item_name", "item_name"))
            if exam_no or item_no:
                normalized["document_id"] = f"exam:{exam_no or '-'}:{item_no or '-'}"

    if normalized_table == "labtest_item_report" and "record_content" in existing_columns:
        if not _first_non_empty(normalized, ("record_content",)):
            item_name = _first_non_empty(normalized, ("item_name", "item_abbreviation", "item_code"))
            result = _first_non_empty(normalized, ("result", "result_value"))
            unit = _first_non_empty(normalized, ("unit", "result_unit"))
            abnormal = _first_non_empty(normalized, ("abnormal_indicator", "abnormal_flag"))
            reference = _first_non_empty(normalized, ("reference_range",))
            if not reference:
                ref_min = _first_non_empty(normalized, ("referencevalue_min", "reference_min"))
                ref_max = _first_non_empty(normalized, ("referencevalue_max", "reference_max"))
                reference = "-".join([item for item in (ref_min, ref_max) if item])
            fragments = []
            if item_name or result:
                fragments.append(f"{item_name or '检验项目'}：{result or '未填写'}{(' ' + unit) if unit else ''}")
            if reference:
                fragments.append(f"参考范围：{reference}")
            if abnormal:
                fragments.append(f"异常标记：{abnormal}")
            if fragments:
                normalized["record_content"] = "；".join(fragments)

    if normalized_table == "exam_item_report" and "record_content" in existing_columns:
        if not _first_non_empty(normalized, ("record_content",)):
            exam_text = _first_non_empty(
                normalized,
                (
                    "exam_result",
                    "exam_impression",
                    "exam_conclusion",
                    "exam_findings",
                    "findings",
                    "impression",
                    "conclusion",
                    "diagnosis",
                    "description",
                    "summary_text",
                    "content",
                ),
            )
            if exam_text:
                normalized["record_content"] = exam_text

    if (
        normalized_table == "consent_form"
        and "consent_type" in existing_columns
        and not _first_non_empty(normalized, ("consent_type",))
        # 只依据输血治疗同意书标准字段名标型；不能把手术/麻醉同意书误标为输血。
        and any(
            field in normalized
            for field in (
                "blood_transfusion_history",
                "transfution_indication",
                "transfusion_indication",
                "transfuse_variety",
                "blood_transfusion_method",
                "planned_transfusion_datetime",
            )
        )
    ):
        normalized["consent_type"] = "blood_transfusion"

    if normalized_table in _STRUCTURED_DOCUMENT_CONTENT_FIELDS and "record_content" in existing_columns:
        source_content = _first_non_empty(normalized, ("record_content",))
        structured_content = _compose_structured_document_content(
            table_name=normalized_table,
            normalized=normalized,
        )
        if structured_content:
            normalized["record_content"] = (
                f"{structured_content}\n记录内容：{source_content}"
                if source_content
                else structured_content
            )


def _validate_order_time_preservation(
    *,
    table_name: str,
    normalized: Dict[str, Any],
    existing_columns: set[str],
) -> None:
    """源端有值的医嘱时间须原义落库；旧表缺列时在删除旧快照前提示升级。"""
    normalized_table = str(table_name or "").strip().lower()
    if normalized_table not in {"inpat_drug_order", "inpat_nondrug_order"}:
        return
    for field in (
        "planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime",
    ):
        # 与通用 datetime/time 别名映射一致，不把计划、执行、撤销互相替代。
        source_fields = (field, field.removesuffix("_datetime") + "_time")
        if _first_non_empty(normalized, source_fields) and (
            field not in existing_columns or not _first_non_empty(normalized, (field,))
        ):
            raise ValueError(
                f"{normalized_table} 医嘱时间字段未保留：{field}，请先升级本地数据库"
            )


def _validate_document_field_preservation(
    *,
    table_name: str,
    normalized: Dict[str, Any],
    existing_columns: set[str],
) -> None:
    """阻止文书定位、时间及三类病程签名在落库时静默丢失。

    文书稳定身份、正式记录时间以及源端有值的病程签名均按明确字段映射
    检查；不从提交人或病历正文补造结构化签名。其他正文和业务字段仍按
    各表明确模型/结构化正文映射处理。
    """

    normalized_table = str(table_name or "").strip().lower()
    if "document_id" in existing_columns:
        source_document_id = _first_non_empty(
            normalized, _DOCUMENT_ID_SOURCE_CANDIDATES
        )
        if source_document_id and not _first_non_empty(normalized, ("document_id",)):
            raise ValueError(
                f"{normalized_table} 文书标识未保留，拒绝静默同步"
            )

    source_time = _first_non_empty(normalized, _AUTHORITATIVE_DOCUMENT_TIME_COLUMNS)
    target_time_columns = tuple(
        field
        for field in _AUTHORITATIVE_DOCUMENT_TIME_COLUMNS
        if field in existing_columns
    )
    if source_time and target_time_columns and not _first_non_empty(
        normalized, target_time_columns
    ):
        raise ValueError(
            f"{normalized_table} 文书权威时间未保留，拒绝静默同步"
        )

    # 069/071 的真实客户源已证明这些结构化字段不可由正文等价替代。
    # 若客户未执行对应迁移，必须在写库前失败关闭，不能继续生成残缺快照。
    required_structured_targets: tuple[str, ...] = ()
    if normalized_table == "consultation_record":
        required_structured_targets = (
            "request_time",
            "consultation_time",
            "record_time",
        )
    elif normalized_table == "discharge_record":
        # 独立保存签署时钟与完整JSON，缺列必须在写SQL前报出，不静默过滤。
        required_structured_targets = ("chief_physician_sign_datetime", "v2_schema")
    elif normalized_table == "death_record":
        required_structured_targets = (
            "death_datetime", "admission_condition", "treatment_course", "death_reason",
        )
    elif normalized_table == "handoff_record":
        required_structured_targets = ("shift_time", "handoff_doctor")
    elif normalized_table == "handover_record":
        required_structured_targets = ("shift_time", "handover_doctor")

    alias_map = _TABLE_COLUMN_ALIASES.get(normalized_table, {})
    for target_column in required_structured_targets:
        source_candidates = alias_map.get(target_column, (target_column,))
        if _first_non_empty(normalized, source_candidates) and (
            target_column not in existing_columns
            or not _first_non_empty(normalized, (target_column,))
        ):
            raise ValueError(
                f"{normalized_table} 结构化字段未保留：{target_column}，拒绝静默同步"
            )

    for target_column, source_candidates in _COURSE_SIGNATURE_COLUMN_ALIASES.get(
        normalized_table, {}
    ).items():
        if _first_non_empty(normalized, source_candidates) and (
            target_column not in existing_columns
            or not _first_non_empty(normalized, (target_column,))
        ):
            # 在任何写SQL（含整次住院重载删除旧行）之前拒绝丢失有值签名。
            # 只报表和字段名，不把签署人或源数据写入错误日志。
            raise ValueError(
                f"{normalized_table} 签名字段未保留：{target_column}，请先升级本地数据库"
            )


def _route_tables_by_scene(
    target_tables: List[Dict[str, Any]],
    scene: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Route execution table set by scene anchors.
    - running: admission_record
    - final: discharge_record
    - frontpage/coding: mr
    - settlement: medical_insurance_settlement
    - both: admission_record + discharge_record + mr
    """
    anchor_set = _SCENE_ANCHOR_TABLES.get(scene)
    if not anchor_set:
        return target_tables, []
    # 执行表集合不再按 scene 裁剪。
    # scene 仅用于确定“病例集合锚点表”，执行阶段仍跑调用方选中的所有表。
    routed = list(target_tables)
    existing = {str(item.get("name") or "") for item in target_tables}
    missing_anchors = sorted(list(anchor_set - existing))
    return routed, missing_anchors


def _resolve_password_from_ref(ref: str) -> str:
    if not ref:
        return ""
    env_key = ref
    if ref.startswith("env:"):
        env_key = ref.split(":", 1)[1].strip()
    return os.getenv(env_key, "")


def load_db_config() -> Dict:
    """读取数据库配置（配置文件仅保存非敏感字段；口令通过环境变量/运行时注入）"""
    global _runtime_remote_password
    cfg = dict(_DEFAULT_CONFIG)

    pg_cfg = get_config(_DB_CONFIG_NAMESPACE, _DB_CONFIG_KEY)
    if isinstance(pg_cfg, dict):
        legacy_password = str(pg_cfg.get("remote_password") or "")
        if legacy_password and not _runtime_remote_password:
            _runtime_remote_password = legacy_password
        pg_cfg.pop("remote_password", None)
        cfg.update(pg_cfg)

    if not isinstance(pg_cfg, dict) and _pg_required_in_current_env():
        raise RuntimeError("缺少 PG 配置 sync/pg_source_config：生产环境禁止读取文件回退")

    if _CONFIG_FILE.exists() and not _pg_required_in_current_env():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    # 兼容旧格式（含 remote_password），读取但不再持久化
                    legacy_password = str(raw.get("remote_password") or "")
                    if legacy_password and not _runtime_remote_password:
                        _runtime_remote_password = legacy_password
                    raw.pop("remote_password", None)
                    cfg.update(raw)
        except Exception:
            pass

    # 回退：从 .env 的 REMOTE_DB_URL 解析（用于 host/user/db）
    env_url = os.getenv("REMOTE_DB_URL", "")
    if env_url:
        try:
            # postgresql://user:pass@host:port/db
            rest = env_url.split("://", 1)[1]
            cred, hostdb = rest.split("@", 1)
            username, password = cred.rsplit(":", 1)
            hostport, database = hostdb.split("/", 1)
            host, port = hostport.split(":", 1) if ":" in hostport else (hostport, "5432")
            cfg.update({
                "remote_host": host,
                "remote_port": port,
                "remote_database": database,
                "remote_username": username,
            })
            if password and not _runtime_remote_password:
                _runtime_remote_password = password
        except Exception:
            pass

    if not cfg.get("remote_password_ref"):
        cfg["remote_password_ref"] = "env:REMOTE_DB_PASSWORD"
    cfg["remote_schema"] = str(cfg.get("remote_schema") or "public")
    cfg["default_institute_id"] = (
        str(cfg.get("default_institute_id") or "").strip()
        or get_clinical_defaults().sync_institute_id
    )
    cfg["sync_mode"] = str(cfg.get("sync_mode") or "table").lower()

    cfg["remote_password"] = _runtime_remote_password or _resolve_password_from_ref(str(cfg.get("remote_password_ref", "")))
    return cfg


@legacy_sync_operation
def save_db_config(config: Dict, runtime_password: Optional[str] = None) -> Dict:
    """保存数据库配置到 PG config registry（不持久化明文密码）。"""
    global _runtime_remote_password
    if runtime_password is not None and str(runtime_password).strip():
        _runtime_remote_password = str(runtime_password).strip()
    # 只保存白名单字段（不包含 remote_password）
    safe_keys = {
        "remote_host",
        "remote_port",
        "remote_database",
        "remote_username",
        "remote_password_ref",
        "remote_schema",
        "default_institute_id",
        "sync_mode",
    }
    to_save = {k: v for k, v in config.items() if k in safe_keys}
    if not to_save.get("remote_password_ref"):
        to_save["remote_password_ref"] = "env:REMOTE_DB_PASSWORD"
    if not to_save.get("remote_schema"):
        to_save["remote_schema"] = "public"
    if not str(to_save.get("default_institute_id") or "").strip():
        to_save["default_institute_id"] = get_clinical_defaults().sync_institute_id
    if str(to_save.get("sync_mode") or "").lower() not in {"table", "procedure"}:
        to_save["sync_mode"] = "table"
    if not set_config(
        _DB_CONFIG_NAMESPACE,
        _DB_CONFIG_KEY,
        to_save,
        updated_by="system",
        source="etl_sync",
        change_reason="update pg source config",
    ):
        raise RuntimeError("写入 PG pg_source_config 失败")
    return to_save


# ==================== 远端数据库连接 ====================

@legacy_sync_operation
def get_remote_db_url() -> str:
    """从配置构建远端 PG DSN（安全处理特殊字符口令）。"""
    cfg = load_db_config()
    host = str(cfg.get("remote_host") or "").strip()
    port = str(cfg.get("remote_port") or "5432").strip() or "5432"
    db = str(cfg.get("remote_database") or "").strip()
    user = str(cfg.get("remote_username") or "").strip()
    pwd = str(cfg.get("remote_password") or "").strip()
    if not host or not user or not pwd:
        return os.getenv("REMOTE_DB_URL", "")
    return make_dsn(host=host, port=port, dbname=db, user=user, password=pwd)


def get_remote_display_url() -> str:
    """返回脱敏后的远端连接信息，供 UI/日志展示。"""
    cfg = load_db_config()
    host = str(cfg.get("remote_host") or "").strip()
    port = str(cfg.get("remote_port") or "5432").strip() or "5432"
    db = str(cfg.get("remote_database") or "").strip()
    user = str(cfg.get("remote_username") or "").strip()
    if not host or not user:
        return ""
    return f"postgresql://{user}:***@{host}:{port}/{db}"


def _refresh_all_bundle_variants_after_sync(
    *, case_refs: List[tuple[str, str, str]], policy_version: str
) -> Dict[str, Any]:
    """旧同步入口对公共病例集Bundle刷新边界的薄适配。"""

    from .case_identity import CaseRef
    from .case_set_sync_service import CaseSetSyncService

    return CaseSetSyncService().refresh_case_set_bundles(
        case_refs=[CaseRef(*identity) for identity in case_refs],
        policy_version=policy_version,
    )


@legacy_sync_operation
def test_remote_connection() -> Dict:
    """测试远端数据库连接"""
    url = get_remote_db_url()
    if not url:
        return {"connected": False, "error": "REMOTE_DB_URL 未配置", "url": ""}

    display_url = get_remote_display_url() or ""

    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        _sync_state.remote_connected = True
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": True,
            "version": version[:80],
            "url": display_url,
            "error": "",
        }
    except Exception as e:
        _sync_state.remote_connected = False
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": False,
            "error": str(e)[:200],
            "url": display_url,
        }


def test_local_connection() -> Dict:
    """测试本地数据库连接"""
    from ..database.connection import DATABASE_URL
    display_url = DATABASE_URL
    try:
        if "@" in DATABASE_URL and ":" in DATABASE_URL.split("@")[0]:
            parts = DATABASE_URL.split("@")
            credential = parts[0].rsplit(":", 1)
            display_url = credential[0] + ":***@" + parts[1]
    except Exception:
        pass

    try:
        with Session(engine) as session:
            result = session.execute(text("SELECT version()"))
            version = result.scalar()
            # 统计各表数据量
            tables_info = {}
            for table_name in ["mr", "diagnosis", "admission_record"]:
                try:
                    schema_name, _, _ = _get_local_table_meta(session, table_name)
                    if not schema_name:
                        tables_info[table_name] = 0
                        continue
                    schema_ident = _safe_identifier(schema_name)
                    table_ident = _safe_identifier(table_name)
                    count = session.execute(text(f"SELECT count(*) FROM {schema_ident}.{table_ident}")).scalar()
                    tables_info[table_name] = int(count or 0)
                except Exception:
                    tables_info[table_name] = 0
        _sync_state.local_connected = True
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": True,
            "version": version[:80] if version else "",
            "url": display_url,
            "tables": tables_info,
            "error": "",
        }
    except Exception as e:
        _sync_state.local_connected = False
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": False,
            "error": str(e)[:200],
            "url": display_url,
        }


# ==================== 同步表配置 ====================

SYNC_TABLE_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "core_8",
        "label": "核心8表",
        "description": "首页与核心文书最小闭环",
        "table_names": [
            "mr",
            "diagnosis",
            "mr_surgery",
            "mr_cost",
            "admission_record",
            "discharge_record",
            "first_course_record",
            "daily_course_record",
        ],
    },
    {
        "id": "document_extended",
        "label": "文书扩展",
        "description": "上级查房、会诊、手术及相关文书",
        "table_names": [
            "senior_course_record",
            "rescue_record",
            "diffcase_discussion_record",
            "death_discussion",
            "consultation_record",
            "handoff_record",
            "handover_record",
            "summary_record",
            "surgery_record",
            "presurg_summary",
            "presurg_discussion",
            "postsurg_firstcourse_record",
            "surgery_safecheck_record",
            "surgery_risk_assessment",
            "anesthesia_record",
            "newborn_record",
            "bloodtrans_record",
            "nursing_record",
            "death_record",
        ],
    },
    {
        "id": "diagnosis_extended",
        "label": "诊断扩展",
        "description": "文书附属诊断与首页诊断扩展",
        "table_names": [
            "admission_record_diagnosis",
            "discharge_record_diagnosis",
            "first_course_record_diagnosis",
            "mr_diagnosis",
            "preane_surveil_record_diagnosis",
            "daily_admission_record_diagnosis",
            "daily_death_record_diagnosis",
            "transfer_in_record_diagnosis",
            "transfer_out_record_diagnosis",
        ],
    },
    {
        "id": "orders_prescriptions",
        "label": "医嘱处方",
        "description": "住院医嘱与处方相关数据",
        "table_names": [
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_prescription",
            "inpat_prescription_item",
            "inpat_bill_item",
        ],
    },
    {
        "id": "exam_lab_pathology",
        "label": "检验检查病理",
        "description": "检查、检验、病理与术前访视扩展",
        "table_names": [
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item",
            "labtest_item_report",
            "pathology_exam_master",
            "pathology_exam_report",
            "surgery_application",
            "surgery_inform_consent",
            "consent_form",
            "surgery_inventory_record",
            "preane_surveil_record",
            "daily_admission_record",
            "daily_death_record",
            "transfer_in_record",
            "transfer_out_record",
        ],
    },
    {
        "id": "settlement",
        "label": "医保结算",
        "description": "医保结算清单及费用明细",
        "table_names": [
            "medical_insurance_settlement",
            "medical_insurance_settlement_cost",
        ],
    },
    {
        "id": "sample_full_domain",
        "label": "样本验证全域",
        "description": "客户样本验证专用，覆盖已纳管 CDM 证据域",
        "table_names": [
            "mr",
            "inpat_registration",
            "diagnosis",
            "mr_diagnosis",
            "mr_surgery",
            "mr_bloodtrans",
            "mr_cost",
            "admission_record",
            "admission_record_diagnosis",
            "discharge_record",
            "discharge_record_diagnosis",
            "death_record",
            "first_course_record",
            "first_course_record_diagnosis",
            "daily_course_record",
            "senior_course_record",
            "rescue_record",
            "summary_record",
            "transfer_in_record",
            "transfer_out_record",
            "consultation_record",
            "diffcase_discussion_record",
            "death_discussion",
            "handoff_record",
            "handover_record",
            "surgery_record",
            "presurg_summary",
            "presurg_discussion",
            "postsurg_firstcourse_record",
            "surgery_safecheck_record",
            "surgery_risk_assessment",
            "anesthesia_record",
            "surgery_application",
            "surgery_inform_consent",
            "consent_form",
            "surgery_inventory_record",
            "preane_surveil_record",
            "postane_surveil_record",
            "docpat_commu_record",
            "bloodtrans_record",
            "blood_application",
            "crisis_value_record",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_prescription",
            "inpat_prescription_item",
            "inpat_bill_item",
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item",
            "labtest_item_report",
            "pathology_exam_master",
            "pathology_exam_report",
        ],
    },
]

# 一键同步并质控必须选择一份固定、可审计的资料集，不能依赖客户历史
# sync/sync_tables 覆盖配置中的 enabled 开关。它与样本验证全域共用同一组
# 已纳管资料，避免再维护第二份会漂移的表名单。
_sample_full_domain_tables = next(
    (
        list(group.get("table_names") or [])
        for group in SYNC_TABLE_GROUPS
        if str(group.get("id") or "") == "sample_full_domain"
    ),
    [],
)
SYNC_TABLE_GROUPS.append(
    {
        "id": "luxian_0609_formal",
        "label": "泸县0609正式质控资料集",
        "description": "一键同步并质控专用；覆盖已纳管的LX0609正式证据来源",
        "table_names": _sample_full_domain_tables,
    }
)

# 核心同步表配置：存储过程 → 本地 CDM 表
# 历史 key_fields 字段保留兼容；新链路按本地主键 UPSERT
SYNC_TABLES = [
    # ---- 基础表 ----
    {
        "name": "mr",
        "label": "病案首页",
        "procedure": "web.mr",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "diagnosis",
        "label": "诊断表",
        "procedure": "web.diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "mr_surgery",
        "label": "手术明细",
        "procedure": "web.mr_surgery",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        # 输血正式规则必须先绑定本次住院的首页输血事件；不能只同步
        # bloodtrans_record 文书而遗漏这个结构化触发事实。
        "name": "mr_bloodtrans",
        "label": "首页输血明细",
        "procedure": "web.mr_bloodtrans",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "bloodtrans_id"],
    },
    {
        "name": "mr_cost",
        "label": "费用明细",
        "procedure": "web.mr_cost",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    # ---- 入院 / 出院 / 死亡 ----
    {
        "name": "inpat_registration",
        "label": "住院登记",
        "procedure": "web.inpat_registration",
        "params": 1,
        "key_fields": ["institute_id", "patient_id", "visit_id"],
    },
    {
        "name": "admission_record",
        "label": "入院记录",
        "procedure": "web.admission_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "discharge_record",
        "label": "出院记录",
        "procedure": "web.discharge_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "death_record",
        "label": "死亡记录",
        "procedure": "web.death_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    # ---- 病程记录 ----
    {
        "name": "first_course_record",
        "label": "首次病程记录",
        "procedure": "web.first_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "daily_course_record",
        "label": "日常病程记录",
        "procedure": "web.daily_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "senior_course_record",
        "label": "上级查房记录",
        "procedure": "web.senior_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "rescue_record",
        "label": "抢救记录",
        "procedure": "web.rescue_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 讨论 / 会诊 ----
    {
        "name": "diffcase_discussion_record",
        "label": "疑难病例讨论",
        "procedure": "web.diffcase_discussion_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "death_discussion",
        "label": "死亡病例讨论",
        "procedure": "web.death_discussion",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "consultation_record",
        "label": "会诊记录",
        "procedure": "web.consultation_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 交接班 / 转科 / 小结 ----
    {
        "name": "handoff_record",
        "label": "交接班记录",
        "procedure": "web.handoff_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "handover_record",
        "label": "接班记录",
        "procedure": "web.handover_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "summary_record",
        "label": "阶段小结",
        "procedure": "web.summary_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 手术相关 ----
    {
        "name": "surgery_record",
        "label": "手术记录",
        "procedure": "web.surgery_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "presurg_summary",
        "label": "术前小结",
        "procedure": "web.presurg_summary",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "presurg_discussion",
        "label": "术前讨论",
        "procedure": "web.presurg_discussion",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "postsurg_firstcourse_record",
        "label": "术后首次病程",
        "procedure": "web.postsurg_firstcourse_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_safecheck_record",
        "label": "手术安全核查",
        "procedure": "web.surgery_safecheck_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_risk_assessment",
        "label": "手术风险评估",
        "procedure": "web.surgery_risk_assessment",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "anesthesia_record",
        "label": "麻醉记录",
        "procedure": "web.anesthesia_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 其他文书 ----
    {
        "name": "newborn_record",
        "label": "新生儿记录",
        "procedure": "web.newborn_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "bloodtrans_record",
        "label": "输血记录",
        "procedure": "web.bloodtrans_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "nursing_record",
        "label": "护理记录",
        "procedure": "web.nursing_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- Wave 1 / T10 第一批扩表（默认纳管未启用）----
    {
        "name": "admission_record_diagnosis",
        "label": "入院记录诊断",
        "procedure": "web.admission_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "discharge_record_diagnosis",
        "label": "出院记录诊断",
        "procedure": "web.discharge_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "first_course_record_diagnosis",
        "label": "首次病程诊断",
        "procedure": "web.first_course_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "mr_diagnosis",
        "label": "病案首页诊断",
        "procedure": "web.mr_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "inpat_drug_order",
        "label": "住院用药医嘱",
        "procedure": "web.inpat_drug_order",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "order_id"],
    },
    {
        "name": "inpat_nondrug_order",
        "label": "住院非药医嘱",
        "procedure": "web.inpat_nondrug_order",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "order_id"],
    },
    {
        "name": "inpat_prescription",
        "label": "住院处方",
        "procedure": "web.inpat_prescription",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "prescription_id"],
    },
    {
        "name": "inpat_prescription_item",
        "label": "住院处方明细",
        "procedure": "web.inpat_prescription_item",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "prescription_id", "item_id"],
    },
    {
        "name": "inpat_bill_item",
        "label": "住院费用明细",
        "procedure": "web.inpat_bill_item",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "bill_item_id"],
    },
    {
        "name": "exam_master",
        "label": "检查主表",
        "procedure": "web.exam_master",
        "params": 1,
        # 客户实际CDM以 exam_id 标识一张检查主表，历史 exam_no 配置会
        # 使本地无主键表无法形成可重复的 UPSERT 合同。
        "key_fields": ["patient_id", "visit_id", "exam_id"],
    },
    {
        "name": "exam_item_report",
        "label": "检查报告",
        "procedure": "web.exam_item_report",
        "params": 1,
        # 客户源库的检查明细采用 exam_id/item_id，不存在历史 exam_no/item_no。
        "key_fields": ["patient_id", "visit_id", "exam_id", "item_id"],
    },
    {
        "name": "labtest_master",
        "label": "检验主表",
        "procedure": "web.labtest_master",
        "params": 1,
        # 客户源库以 test_id 标识检验申请。
        "key_fields": ["patient_id", "visit_id", "test_id"],
    },
    {
        "name": "labtest_item",
        "label": "检验项目",
        "procedure": "web.labtest_item",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "test_id", "test_item_id"],
    },
    {
        "name": "labtest_item_report",
        "label": "检验报告",
        "procedure": "web.labtest_item_report",
        "params": 1,
        # 同一检验申请可能出现重复 item_id；客户源库的稳定报告标识为
        # test_id + print_order_id，保留 item_id 供规则读取项目事实。
        "key_fields": ["patient_id", "visit_id", "test_id", "print_order_id"],
    },
    # ---- Wave 1 / T10 第二批扩表候选（先纳管，默认不启用）----
    {
        "name": "pathology_exam_master",
        "label": "病理检查主表",
        "procedure": "web.pathology_exam_master",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "pathology_exam_report",
        "label": "病理检查报告",
        "procedure": "web.pathology_exam_report",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_application",
        "label": "手术申请单",
        "procedure": "web.surgery_application",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_inform_consent",
        "label": "手术知情同意书",
        "procedure": "web.surgery_inform_consent",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        # 本地以逻辑 consent_form 汇总正式同意书证据；经客户源库元数据核实，
        # 输血治疗同意书物理表是 bloodtrans_inform_consent。同步配置仍可按
        # 医院能力覆盖，不能再假定存在同名通用表或不存在的标准别名。
        "name": "consent_form",
        "label": "同意书",
        "source_table": "bloodtrans_inform_consent",
        "procedure": "web.bloodtrans_inform_consent",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_inventory_record",
        "label": "术中清点记录",
        "procedure": "web.surgery_inventory_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "docpat_commu_record",
        "label": "医患沟通记录",
        "procedure": "web.docpat_commu_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "blood_application",
        "label": "输血申请单",
        "procedure": "web.blood_application",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "application_id"],
    },
    {
        "name": "crisis_value_record",
        "label": "危急值记录",
        "procedure": "web.crisis_value_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "preane_surveil_record",
        "label": "麻醉前访视记录",
        "procedure": "web.preane_surveil_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "preane_surveil_record_diagnosis",
        "label": "麻醉前访视诊断",
        "procedure": "web.preane_surveil_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "postane_surveil_record",
        "label": "麻醉术后访视记录",
        "procedure": "web.postane_surveil_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "daily_admission_record",
        "label": "日常入院记录",
        "procedure": "web.daily_admission_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "daily_admission_record_diagnosis",
        "label": "日常入院记录诊断",
        "procedure": "web.daily_admission_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "daily_death_record",
        "label": "日常死亡记录",
        "procedure": "web.daily_death_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "daily_death_record_diagnosis",
        "label": "日常死亡记录诊断",
        "procedure": "web.daily_death_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "transfer_in_record",
        "label": "转入记录",
        "procedure": "web.transfer_in_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "transfer_out_record",
        "label": "转出记录",
        "procedure": "web.transfer_out_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "transfer_in_record_diagnosis",
        "label": "转入记录诊断",
        "procedure": "web.transfer_in_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "transfer_out_record_diagnosis",
        "label": "转出记录诊断",
        "procedure": "web.transfer_out_record_diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    # ---- 医保结算清单（源库未提供时按资料不完整失败关闭）----
    {
        "name": "medical_insurance_settlement",
        "label": "医保结算清单",
        "procedure": "web.medical_insurance_settlement",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "medical_insurance_settlement_cost",
        "label": "医保结算费用明细",
        "procedure": "web.medical_insurance_settlement_cost",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "medinsur_serial_item_id"],
    },
]


for _item in SYNC_TABLES:
    _name = str(_item.get("name") or "")
    _item.setdefault("source_table", _name)
    _item.setdefault("date_field", "update_time")
    _item.setdefault("fallback_date_field", None)
    # 全系统同步默认纳管全部已配置资料表；管理员保存的显式开关会在下方覆盖。
    _item.setdefault("enabled", True)
    # 增量能力必须由代码显式批准。date_field/候选时间列不能自动提升同步策略。
    _item.setdefault("incremental_strategy", "full_visit_reload")
    _item.setdefault("watermark_columns", [])
    _item.setdefault("schema_version", _SYNC_CURSOR_SCHEMA_VERSION)

_CDM_SYNC_TABLE_NAMES = {
    str(item.get("name") or "").strip()
    for item in SYNC_TABLES
    if str(item.get("name") or "").strip()
}


def _load_sync_table_overrides() -> Dict[str, Dict[str, Any]]:
    pg_raw = get_config(_TABLE_CONFIG_NAMESPACE, _TABLE_CONFIG_KEY)
    if isinstance(pg_raw, list):
        out: Dict[str, Dict[str, Any]] = {}
        for row in pg_raw:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            out[name] = row
        if out:
            return out

    if _pg_required_in_current_env():
        raise RuntimeError("缺少 PG 配置 sync/sync_tables：生产环境禁止读取文件回退")

    if not _SYNC_TABLES_FILE.exists():
        return {}
    try:
        with open(_SYNC_TABLES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            out[name] = row
        return out
    except Exception:
        return {}


def _apply_sync_table_overrides():
    overrides = _load_sync_table_overrides()
    if not overrides:
        return
    for item in SYNC_TABLES:
        name = str(item.get("name") or "")
        override = overrides.get(name)
        if not override:
            continue
        if "source_table" in override and override.get("source_table"):
            item["source_table"] = str(override["source_table"])
        if "date_field" in override and override.get("date_field"):
            item["date_field"] = str(override["date_field"])
        if "fallback_date_field" in override:
            value = override.get("fallback_date_field")
            item["fallback_date_field"] = str(value) if value else None
        if "enabled" in override:
            item["enabled"] = bool(override.get("enabled"))


_apply_sync_table_overrides()


def list_sync_tables() -> List[Dict[str, Any]]:
    return [
        {
            **dict(item),
            "incremental_strategy": (
                str(item.get("incremental_strategy") or "full_visit_reload")
                if str(item.get("incremental_strategy") or "full_visit_reload")
                in _SUPPORTED_INCREMENTAL_STRATEGIES
                else "full_visit_reload"
            ),
            "watermark_columns": list(item.get("watermark_columns") or []),
            "schema_version": str(
                item.get("schema_version") or _SYNC_CURSOR_SCHEMA_VERSION
            ),
        }
        for item in SYNC_TABLES
    ]


@legacy_sync_operation
def save_sync_tables_config(updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    table_map = {str(item["name"]): item for item in SYNC_TABLES}
    changed_names: set[str] = set()
    for row in updates:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name or name not in table_map:
            raise ValueError(f"未知同步表: {name or '<empty>'}")
        target = table_map[name]
        if "source_table" in row and row.get("source_table") is not None:
            target["source_table"] = str(row.get("source_table") or "").strip() or target["name"]
        if "date_field" in row and row.get("date_field") is not None:
            target["date_field"] = str(row.get("date_field") or "").strip() or "update_time"
        if "fallback_date_field" in row:
            val = row.get("fallback_date_field")
            target["fallback_date_field"] = str(val).strip() if val else None
        if "enabled" in row:
            target["enabled"] = bool(row.get("enabled"))
        changed_names.add(name)

    if changed_names:
        persisted = []
        for item in SYNC_TABLES:
            persisted.append(
                {
                    "name": item["name"],
                    "source_table": item.get("source_table"),
                    "date_field": item.get("date_field"),
                    "fallback_date_field": item.get("fallback_date_field"),
                    "enabled": bool(item.get("enabled")),
                }
            )
        if not set_config(
            _TABLE_CONFIG_NAMESPACE,
            _TABLE_CONFIG_KEY,
            persisted,
            updated_by="system",
            source="etl_sync",
            change_reason="update sync tables config",
        ):
            raise RuntimeError("写入 PG sync_tables 配置失败")

    return list_sync_tables()


def _resolve_sync_mode(mode: Optional[str] = None) -> str:
    if mode and mode in {"table", "procedure"}:
        return mode
    env_mode = str(os.getenv("PG_SYNC_MODE", "")).strip().lower()
    if env_mode in {"table", "procedure"}:
        return env_mode
    cfg_mode = str(load_db_config().get("sync_mode") or "table").strip().lower()
    return cfg_mode if cfg_mode in {"table", "procedure"} else "table"


def _resolve_target_tables(tables: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    table_map = {str(item["name"]): item for item in SYNC_TABLES}
    if tables:
        target: List[Dict[str, Any]] = []
        missing: List[str] = []
        for name in tables:
            key = str(name or "").strip()
            if not key:
                continue
            if key not in table_map:
                missing.append(key)
            else:
                target.append(table_map[key])
        return target, missing
    return [item for item in SYNC_TABLES if bool(item.get("enabled"))], []


def list_sync_table_groups() -> List[Dict[str, Any]]:
    table_map = {str(item["name"]): item for item in SYNC_TABLES}
    groups: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for group in SYNC_TABLE_GROUPS:
        table_names = [str(name) for name in group.get("table_names", []) if str(name) in table_map]
        group_id = str(group.get("id") or "")
        seen_ids.add(group_id)
        groups.append(
            {
                "id": group_id,
                "label": str(group.get("label") or ""),
                "description": str(group.get("description") or ""),
                "table_names": table_names,
                "table_count": len(table_names),
            }
        )
    if "all_56" not in seen_ids:
        all_table_names = [str(item.get("name") or "") for item in SYNC_TABLES if str(item.get("name") or "").strip()]
        groups.append(
            {
                "id": "all_56",
                "label": "全量56表",
                "description": "稳定分组ID，覆盖当前所有已配置同步表",
                "table_names": all_table_names,
                "table_count": len(all_table_names),
            }
        )
    return groups


def expand_table_groups(group_ids: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    if not group_ids:
        return [], []
    valid_groups = {str(group.get("id") or ""): group for group in list_sync_table_groups()}
    missing: List[str] = []
    selected: List[str] = []
    seen: set[str] = set()
    for raw in group_ids:
        gid = str(raw or "").strip()
        if not gid:
            continue
        group = valid_groups.get(gid)
        if not group:
            missing.append(gid)
            continue
        for table_name in group.get("table_names", []):
            if table_name in seen:
                continue
            seen.add(table_name)
            selected.append(str(table_name))
    return selected, missing


def _resolve_target_tables_with_scope(
    tables: Optional[List[str]] = None,
    include_disabled: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if tables:
        return _resolve_target_tables(tables)
    if include_disabled:
        return [dict(item) for item in SYNC_TABLES], []
    return _resolve_target_tables(None)



@legacy_sync_operation
def call_stored_procedure(remote_url: str, procedure: str, date_str: str, param_count: int = 1) -> List[Dict]:
    """
    调用远端存储过程并返回结果
    
    Args:
        remote_url: 远端 PG 连接 URL
        procedure: 存储过程名称，如 'web.mr'
        date_str: 日期参数，如 '2025-01-01'
        param_count: 参数个数（1=单日期，2=起止日期用同一天）
    
    Returns:
        结果字典列表
    """
    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        if param_count == 1:
            cursor.execute(f"CALL {procedure}(%s)", (date_str,))
        else:
            cursor.execute(f"CALL {procedure}(%s, %s)", (date_str, date_str))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


def _resolve_local_table_schema(session: Session, table_name: str) -> Optional[str]:
    schema_params = {f"schema_{idx}": schema for idx, schema in enumerate(_LOCAL_TARGET_SCHEMAS)}
    schema_placeholders = ", ".join(f":schema_{idx}" for idx in range(len(_LOCAL_TARGET_SCHEMAS)))
    rows = session.execute(
        text(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_schema IN (""" + schema_placeholders + """)
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name, **schema_params},
    ).fetchall()
    if not rows:
        return None
    candidates = [str(row[0]) for row in rows if str(row[0] or "").strip()]
    if not candidates:
        return None
    schema_priority = _resolve_local_table_schema_priority(table_name)
    for schema in schema_priority:
        if schema in candidates:
            if len(candidates) > 1:
                logger.warning(
                    "本地目标表 %s 在多个 schema 命中=%s，按优先级选择 %s",
                    table_name,
                    candidates,
                    schema,
                )
            return schema
    return candidates[0]


def _resolve_local_table_schema_priority(table_name: str) -> Tuple[str, ...]:
    normalized_table = str(table_name or "").strip()
    if DB_SCHEMA_MODE == "split" and normalized_table in _CDM_SYNC_TABLE_NAMES:
        ordered = [_CDM_TARGET_SCHEMA]
        ordered.extend(schema for schema in _LOCAL_TARGET_SCHEMAS if schema != _CDM_TARGET_SCHEMA)
        return tuple(ordered)
    return _LOCAL_TARGET_SCHEMAS


def _get_local_table_columns(session: Session, table_name: str, schema: Optional[str] = None) -> List[str]:
    resolved_schema = schema or _resolve_local_table_schema(session, table_name)
    if not resolved_schema:
        return []
    result = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"schema": resolved_schema, "table_name": table_name},
    )
    return [str(row[0]) for row in result]


def _get_local_primary_keys(session: Session, table_name: str, schema: Optional[str] = None) -> List[str]:
    resolved_schema = schema or _resolve_local_table_schema(session, table_name)
    if not resolved_schema:
        return []
    result = session.execute(
        text(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
            WHERE n.nspname = :schema
              AND c.relname = :table_name
              AND i.indisprimary
            ORDER BY k.ord
            """
        ),
        {"schema": resolved_schema, "table_name": table_name},
    )
    return [str(row[0]) for row in result]


def _get_local_table_meta(session: Session, table_name: str) -> Tuple[Optional[str], List[str], List[str]]:
    schema = _resolve_local_table_schema(session, table_name)
    if not schema:
        return None, [], []
    columns = _get_local_table_columns(session, table_name, schema=schema)
    primary_keys = _get_local_primary_keys(session, table_name, schema=schema)
    return schema, columns, primary_keys


def _remote_table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _remote_column_exists(cursor, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


def _remote_procedure_exists(cursor, schema: str, procedure: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = %s AND p.proname = %s
        LIMIT 1
        """,
        (schema, procedure),
    )
    return cursor.fetchone() is not None


def _parse_ymd_or_none(value: Any) -> Optional[date]:
    text_value = str(value or "").strip()
    if not text_value:
        return None
    try:
        return datetime.strptime(text_value, "%Y-%m-%d").date()
    except Exception:
        return None


def _normalize_target_departments(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    wildcard_aliases = {"*", "all", "全部", "全院", "全部科室", "全科室"}
    cleaned: List[str] = []
    seen: set[str] = set()
    wildcard_seen = False
    for item in raw:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        if name.lower() in wildcard_aliases:
            wildcard_seen = True
            continue
        cleaned.append(name)
        seen.add(name)
    if wildcard_seen and cleaned:
        # 具体科室优先，避免 ["*", "骨科"] 被误判为全院
        return cleaned
    if wildcard_seen:
        return []
    return cleaned


def _resolve_pg_extract_window(
    *,
    policy: Dict[str, Any],
    date_window: Optional[Dict[str, str]] = None,
    target_departments: Optional[List[str]] = None,
) -> Tuple[Optional[date], Optional[date], List[str], Optional[str]]:
    window_payload = date_window if isinstance(date_window, dict) else {}
    start_text = str(
        window_payload.get("start") or window_payload.get("start_date") or policy.get("start_date") or ""
    ).strip()
    end_text = str(
        window_payload.get("end") or window_payload.get("end_date") or policy.get("end_date") or ""
    ).strip()
    start_dt = _parse_ymd_or_none(start_text)
    end_dt = _parse_ymd_or_none(end_text)
    if start_dt is None or end_dt is None:
        return None, None, [], "请先设置出院日期范围（开始日期/结束日期）后再执行抽取"
    if start_dt > end_dt:
        return None, None, [], "出院日期范围非法：开始日期不能晚于结束日期"
    if (end_dt - start_dt).days > 180:
        return None, None, [], "出院日期范围过大（最多 180 天），请缩小后重试"

    has_department_override = isinstance(target_departments, list)
    override_departments = (
        _normalize_target_departments(target_departments)
        if has_department_override
        else []
    )
    policy_departments = _normalize_target_departments(policy.get("target_departments"))
    dept_filters = override_departments if has_department_override else policy_departments
    return start_dt, end_dt, dept_filters, None


def _chunk_visit_keys(visit_keys: List[Tuple[str, str]], chunk_size: int = _VISIT_KEY_CHUNK_SIZE):
    for idx in range(0, len(visit_keys), chunk_size):
        yield visit_keys[idx : idx + chunk_size]


def _resolve_remote_visit_filters(cursor, remote_schema: str, source_table: str) -> Tuple[str, Optional[str]]:
    date_field = None
    for column_name in ["discharge_datetime", "discharge_date"]:
        if _remote_column_exists(cursor, remote_schema, source_table, column_name):
            date_field = column_name
            break
    if not date_field:
        raise ValueError(f"{source_table} 缺少出院日期字段（discharge_datetime/discharge_date）")

    dept_field = None
    for column_name in ["discharge_dept_name", "admission_dept_name", "dept_name"]:
        if _remote_column_exists(cursor, remote_schema, source_table, column_name):
            dept_field = column_name
            break
    return date_field, dept_field


@legacy_sync_operation
def list_remote_departments(limit: int = 500) -> Dict[str, Any]:
    """
    从源 PG 拉取科室列表（用于同步策略中的科室选择）。
    固定从 discharge_record 读取，字段兼容 discharge_dept_name / admission_dept_name / dept_name。
    """
    remote_url = get_remote_db_url()
    if not remote_url:
        raise ValueError("远端 PG 未配置（请先保存源 PG 连接）")

    try:
        limit_value = int(limit)
    except Exception:
        limit_value = 500
    limit_value = max(1, min(limit_value, 2000))

    cfg = load_db_config()
    remote_schema = _safe_identifier(str(cfg.get("remote_schema") or "public").strip() or "public")
    schema_ident = _safe_identifier(remote_schema)
    source_table = "discharge_record"
    dept_field_candidates = ["discharge_dept_name", "admission_dept_name", "dept_name"]

    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if not _remote_table_exists(cursor, remote_schema, source_table):
            raise ValueError(f"源 PG 缺少表: {remote_schema}.{source_table}")
        dept_field = None
        for candidate in dept_field_candidates:
            if _remote_column_exists(cursor, remote_schema, source_table, candidate):
                dept_field = candidate
                break
        if dept_field is None:
            raise ValueError(
                f"源 PG 缺少科室字段: {remote_schema}.{source_table}."
                f"{'/'.join(dept_field_candidates)}"
            )

        table_ident = _safe_identifier(source_table)
        dept_ident = _safe_identifier(dept_field)
        sql = (
            f"SELECT DISTINCT TRIM({dept_ident}::text) AS dept_name "
            f"FROM {schema_ident}.{table_ident} "
            f"WHERE {dept_ident} IS NOT NULL AND TRIM({dept_ident}::text) <> '' "
            f"ORDER BY dept_name "
            f"LIMIT %s"
        )
        cursor.execute(sql, (limit_value,))
        rows = cursor.fetchall() or []
        items = [
            str(row.get("dept_name") or "").strip()
            for row in rows
            if str(row.get("dept_name") or "").strip()
        ]
        return {
            "items": items,
            "schema": remote_schema,
            "source_table": table_ident,
            "source_column": dept_field,
        }
    finally:
        cursor.close()
        conn.close()


def collect_visit_keys_by_policy(
    *,
    remote_url: str,
    remote_schema: str,
    start_date: date,
    end_date: date,
    target_departments: List[str],
) -> List[Tuple[str, str]]:
    visit_key_set: set[Tuple[str, str]] = set()
    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # 固定口径：只用 discharge_record 的科室字段筛病例集合。
        source_table = "discharge_record"
        if not _remote_table_exists(cursor, remote_schema, source_table):
            raise ValueError(f"源 PG 缺少表: {remote_schema}.{source_table}")
        if not _remote_column_exists(cursor, remote_schema, source_table, "patient_id") or not _remote_column_exists(
            cursor, remote_schema, source_table, "visit_id"
        ):
            raise ValueError(f"{source_table} 缺少 patient_id/visit_id 字段")
        if not _remote_column_exists(cursor, remote_schema, source_table, "dept_name"):
            raise ValueError(f"{source_table} 缺少 CDM 科室字段 dept_name")

        has_discharge_date = _remote_column_exists(cursor, remote_schema, source_table, "discharge_date")
        has_discharge_time = _remote_column_exists(cursor, remote_schema, source_table, "discharge_time")
        has_discharge_datetime = _remote_column_exists(cursor, remote_schema, source_table, "discharge_datetime")
        if not (has_discharge_date or has_discharge_time or has_discharge_datetime):
            raise ValueError(
                f"{source_table} 缺少出院日期字段（discharge_date/discharge_time/discharge_datetime）"
            )

        schema_ident = _safe_identifier(remote_schema)
        table_ident = _safe_identifier(source_table)
        date_expr: str
        if has_discharge_date and has_discharge_time:
            # 真实源库常见 discharge_date 大量为空；兜底到 discharge_time::date。
            date_expr = "COALESCE(discharge_date, discharge_time::date)"
        elif has_discharge_date and has_discharge_datetime:
            date_expr = "COALESCE(discharge_date, discharge_datetime::date)"
        elif has_discharge_date:
            date_expr = "discharge_date"
        elif has_discharge_time:
            date_expr = "discharge_time::date"
        else:
            date_expr = "discharge_datetime::date"
        dept_ident = _safe_identifier("dept_name")
        where_fragments = [
            f"{date_expr} >= %s::date",
            f"{date_expr} < (%s::date + INTERVAL '1 day')",
        ]
        params: List[Any] = [start_date.isoformat(), end_date.isoformat()]

        if target_departments:
            normalized_departments = [
                str(item or "").strip().lower()
                for item in target_departments
                if str(item or "").strip()
            ]
            normalized_departments = list(dict.fromkeys(normalized_departments))
            if normalized_departments:
                placeholders = ", ".join(["%s"] * len(normalized_departments))
                where_fragments.append(f"LOWER(TRIM(COALESCE({dept_ident}::text, ''))) IN ({placeholders})")
                params.extend(normalized_departments)

        sql = (
            f"SELECT DISTINCT patient_id::text AS patient_id, visit_id::text AS visit_id "
            f"FROM {schema_ident}.{table_ident} "
            f"WHERE {' AND '.join(where_fragments)}"
        )
        cursor.execute(sql, params)
        rows = cursor.fetchall() or []
        for row in rows:
            patient_id = str(row.get("patient_id") or "").strip()
            visit_id = str(row.get("visit_id") or "").strip()
            if not patient_id or not visit_id:
                continue
            visit_key_set.add((patient_id, visit_id))
    finally:
        cursor.close()
        conn.close()

    return sorted(visit_key_set)


def estimate_pg_sync_impact(
    *,
    scene: str = "final",
    date_window: Optional[Dict[str, str]] = None,
    target_departments: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """使用正式三坐标病例范围服务估算同步影响，不读取或写入病历明细。"""
    resolved_scene = _normalize_sync_scene(scene)
    policy = load_sync_policy()
    as_of_date, range_start_date, discharge_end_date, dept_filters, window_error = (
        _resolve_case_scope_window(
            scene=resolved_scene,
            sync_date=None,
            policy=policy,
            date_window=date_window,
            target_departments=target_departments,
        )
    )
    if window_error or as_of_date is None:
        raise ValueError(window_error or "病例范围日期无效")
    scope_result = _create_case_scope_service().resolve_hospitalization_scope(
        scope_mode=_scope_mode_for_scene(resolved_scene),
        as_of_date=as_of_date,
        admission_start_date=(
            as_of_date - timedelta(days=ACTIVE_ADMISSION_LOOKBACK_DAYS)
            if resolved_scene in {"running", "both"}
            else None
        ),
        discharge_start_date=range_start_date if resolved_scene != "running" else None,
        discharge_end_date=discharge_end_date,
        departments=dept_filters,
    )
    if any(_uses_unconfigured_institute(case_ref) for case_ref in scope_result.case_refs):
        raise ValueError("请先配置本院稳定机构标识后再检查同步范围")
    effective_end_date = (
        as_of_date if resolved_scene == "running" else discharge_end_date
    )
    effective_window = {
        "start": range_start_date.isoformat() if range_start_date else "",
        "end": effective_end_date.isoformat() if effective_end_date else "",
    }
    return {
        "estimated_impact": len(scope_result.case_refs),
        "estimate_basis": "case_ref_count",
        "date_window": effective_window,
        "target_departments": dept_filters or ["*"],
        "sources_used": list(scope_result.sources_used),
        "source_status": scope_result.source_status,
        "warnings": list(scope_result.warnings),
    }


@legacy_sync_operation
def fetch_remote_rows_by_visit_keys(
    *,
    remote_url: str,
    remote_schema: str,
    source_table: str,
    visit_keys: List[Tuple[str, str]],
    watermark_column: Optional[str] = None,
    watermark_after: Optional[datetime] = None,
) -> List[Dict]:
    if not visit_keys:
        return []
    schema_ident = _safe_identifier(remote_schema)
    table_ident = _safe_identifier(source_table)

    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if not _remote_column_exists(cursor, remote_schema, source_table, "patient_id") or not _remote_column_exists(
            cursor, remote_schema, source_table, "visit_id"
        ):
            raise ValueError(f"{source_table} 缺少 patient_id/visit_id 字段，无法按病例集合抽取")
        watermark_ident = ""
        if watermark_column:
            watermark_ident = _safe_identifier(watermark_column)
            if not _remote_column_exists(
                cursor, remote_schema, source_table, watermark_column
            ):
                raise ValueError(
                    f"{source_table} 缺少受控水位字段 {watermark_column}，无法执行增量抽取"
                )

        all_rows: List[Dict] = []
        for chunk in _chunk_visit_keys(visit_keys):
            placeholders = ", ".join(["(%s, %s)"] * len(chunk))
            params: List[str] = []
            for patient_id, visit_id in chunk:
                params.extend([str(patient_id), str(visit_id)])
            sql = (
                f"SELECT * FROM {schema_ident}.{table_ident} "
                f"WHERE (patient_id::text, visit_id::text) IN ({placeholders})"
            )
            if watermark_ident and watermark_after is not None:
                sql += f" AND {watermark_ident} >= %s"
                params.append(watermark_after)
            cursor.execute(sql, params)
            rows = cursor.fetchall() or []
            all_rows.extend([dict(row) for row in rows])
        return all_rows
    finally:
        cursor.close()
        conn.close()


@legacy_sync_operation
def fetch_remote_rows_by_case_refs(
    *,
    remote_url: str,
    remote_schema: str,
    source_table: str,
    case_refs: List[Any],
    default_institute_id: str = "",
    readonly: bool = False,
) -> List[Dict]:
    """按病例集合读取源库；单院源表缺机构列时使用固定机构标识。"""

    from .case_identity import normalize_case_refs, stamp_source_rows_institute_id

    normalized_refs = normalize_case_refs(case_refs)
    schema_ident = _safe_identifier(remote_schema)
    table_ident = _safe_identifier(source_table)
    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = None
    try:
        if readonly:
            conn.set_session(readonly=True)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        has_patient_id = _remote_column_exists(
            cursor, remote_schema, source_table, "patient_id"
        )
        has_visit_id = _remote_column_exists(
            cursor, remote_schema, source_table, "visit_id"
        )
        if not has_patient_id or not has_visit_id:
            raise ValueError(
                f"{source_table} 缺少 patient_id/visit_id 字段，无法按病例集合抽取"
            )
        has_institute_id = _remote_column_exists(
            cursor, remote_schema, source_table, "institute_id"
        )
        fallback = str(default_institute_id or "").strip()
        if not has_institute_id:
            if not fallback:
                raise ValueError(
                    f"{source_table} 缺少 institute_id 字段，且未配置固定机构标识"
                )
            if any(case_ref.institute_id != fallback for case_ref in normalized_refs):
                raise ValueError(
                    f"{source_table} 无 institute_id 字段，请求病例与固定机构标识不一致"
                )
        all_rows: List[Dict] = []
        for start in range(0, len(normalized_refs), _VISIT_KEY_CHUNK_SIZE):
            chunk = normalized_refs[start : start + _VISIT_KEY_CHUNK_SIZE]
            params: List[str] = []
            if has_institute_id:
                placeholders = ", ".join(["(%s, %s, %s)"] * len(chunk))
                for institute_id, patient_id, visit_id in chunk:
                    params.extend([institute_id, patient_id, visit_id])
                cursor.execute(
                    f"SELECT * FROM {schema_ident}.{table_ident} "
                    "WHERE (institute_id::text, patient_id::text, visit_id::text) "
                    f"IN ({placeholders})",
                    params,
                )
            else:
                placeholders = ", ".join(["(%s, %s)"] * len(chunk))
                for _institute_id, patient_id, visit_id in chunk:
                    params.extend([patient_id, visit_id])
                cursor.execute(
                    f"SELECT * FROM {schema_ident}.{table_ident} "
                    "WHERE (patient_id::text, visit_id::text) "
                    f"IN ({placeholders})",
                    params,
                )
            all_rows.extend(dict(row) for row in cursor.fetchall() or [])
        return stamp_source_rows_institute_id(
            all_rows,
            default_institute_id=fallback,
        )
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


@legacy_sync_operation
def fetch_remote_rows_by_table(
    remote_url: str,
    remote_schema: str,
    source_table: str,
    date_field: str,
    sync_date: str,
) -> List[Dict]:
    schema_ident = _safe_identifier(remote_schema)
    table_ident = _safe_identifier(source_table)
    date_ident = _safe_identifier(date_field)
    sql = (
        f"SELECT * FROM {schema_ident}.{table_ident} "
        f"WHERE {date_ident} >= %s::date "
        f"AND {date_ident} < (%s::date + INTERVAL '1 day')"
    )

    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(sql, (sync_date, sync_date))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


def validate_pg_sync_plan(
    tables: Optional[List[str]] = None,
    mode: Optional[str] = None,
    include_disabled: bool = False,
) -> Dict[str, Any]:
    """构建 PG 同步预检矩阵。"""
    sync_mode = _resolve_sync_mode(mode)
    cfg = load_db_config()
    remote_schema = _safe_identifier(str(cfg.get("remote_schema") or "public").strip() or "public")

    target_tables, missing = _resolve_target_tables_with_scope(
        tables=tables,
        include_disabled=include_disabled,
    )
    blockers: List[str] = []
    warnings: List[str] = []
    table_validations: List[Dict[str, Any]] = []
    if missing:
        blockers.append(f"未知同步表: {', '.join(missing)}")
    if not target_tables:
        blockers.append(
            "未选择可执行同步表（默认只执行 enabled=true 的表）"
            if not include_disabled
            else "未选择可执行同步表"
        )
    if engine is None:
        blockers.append("本地数据库未初始化")

    remote_url = get_remote_db_url()
    if not remote_url:
        blockers.append("REMOTE_DB_URL 未配置")
    if blockers and (engine is None or not remote_url):
        return {
            "mode": sync_mode,
            "remote_schema": remote_schema,
            "executable": False,
            "blockers": blockers,
            "warnings": warnings,
            "table_validations": table_validations,
            "target_tables": [item.get("name") for item in target_tables],
            "matrix_scope": "all" if include_disabled else "enabled",
        }

    local_session: Optional[Session] = None
    remote_conn = None
    remote_cursor = None
    homology_connections: Dict[str, Tuple[Any, Any]] = {}
    try:
        local_session = Session(engine)
        remote_conn = psycopg2.connect(remote_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        for item in target_tables:
            table_name = str(item["name"])
            source_table = _safe_identifier(str(item.get("source_table") or table_name))
            row_blockers: List[str] = []
            resolved_date_field: Optional[str] = None
            homology = resolve_homology_source(table_name=table_name, remote_url=remote_url)
            table_cursor, table_schema = remote_cursor, remote_schema
            if homology is not None:
                source_table, table_schema = homology.table, homology.schema
                if homology.remote_url not in homology_connections:
                    conn = psycopg2.connect(homology.remote_url, connect_timeout=10)
                    homology_connections[homology.remote_url] = (conn, None)
                    conn.set_session(readonly=True)
                    homology_connections[homology.remote_url] = (conn, conn.cursor())
                table_cursor = homology_connections[homology.remote_url][1]
                if sync_mode != "table":
                    row_blockers.append("homology 同步仅支持表直连模式")

            local_schema, local_columns, local_primary_keys = _get_local_table_meta(local_session, table_name)
            if not local_schema or not local_columns:
                row_blockers.append("本地目标表不存在")
            if not local_primary_keys:
                row_blockers.append("本地目标表缺少主键")
            if homology is not None:
                if set(homology.required_target_columns) - set(local_columns):
                    row_blockers.append("本地缺少 homology 证据字段，请先升级数据库")

            if sync_mode == "table":
                if not _remote_table_exists(table_cursor, table_schema, source_table):
                    row_blockers.append("远端源表不存在")
                else:
                    if not _remote_column_exists(table_cursor, table_schema, source_table, "patient_id") or not _remote_column_exists(
                        table_cursor, table_schema, source_table, "visit_id"
                    ):
                        row_blockers.append("远端缺少 patient_id/visit_id，无法按病例集合抽取")
                    if homology is not None:
                        required = ("institute_id", *HOMOLOGY_TABLE_KEYS[table_name])
                        if any(not _remote_column_exists(
                            table_cursor, table_schema, source_table, column
                        ) for column in required):
                            row_blockers.append("homology 源表缺少机构或稳定行标识字段")
                        if table_name == "pathology_exam_report" and not _remote_column_exists(
                            table_cursor, table_schema, source_table, "diagnosis"
                        ):
                            row_blockers.append("homology 病理报告缺少 diagnosis 字段")
                    # 当前固定病例锚点口径：discharge_record 负责日期过滤能力。
                    if source_table == "discharge_record":
                        date_field = str(item.get("date_field") or "update_time")
                        fallback_date_field = str(item.get("fallback_date_field") or "").strip()
                        if _remote_column_exists(remote_cursor, remote_schema, source_table, date_field):
                            resolved_date_field = date_field
                        elif fallback_date_field and _remote_column_exists(
                            remote_cursor, remote_schema, source_table, fallback_date_field
                        ):
                            resolved_date_field = fallback_date_field
                            warnings.append(f"{table_name}: 使用 fallback_date_field={fallback_date_field}")
                        else:
                            row_blockers.append("远端日期字段不可用（锚点表）")
            else:
                procedure_full = str(item.get("procedure") or "")
                if "." in procedure_full:
                    proc_schema, proc_name = procedure_full.split(".", 1)
                else:
                    proc_schema, proc_name = "public", procedure_full
                if not _remote_procedure_exists(remote_cursor, _safe_identifier(proc_schema), _safe_identifier(proc_name)):
                    row_blockers.append(f"远端过程不存在: {proc_schema}.{proc_name}")

            source = f"{table_schema}.{source_table}" if sync_mode == "table" else str(item.get("procedure") or "")
            if homology is not None:
                source = f"{homology.database}.{source}"
            table_validations.append(
                {
                    "table": table_name,
                    "source_table": source_table,
                    "source": source,
                    "enabled": bool(item.get("enabled")),
                    "mode": sync_mode,
                    "local_schema": local_schema,
                    "date_field": item.get("date_field"),
                    "fallback_date_field": item.get("fallback_date_field"),
                    "resolved_date_field": resolved_date_field,
                    "local_primary_keys": local_primary_keys,
                    "executable": len(row_blockers) == 0,
                    "blockers": row_blockers,
                    **({"source_profile": "homology"} if homology is not None else {}),
                }
            )

        for row in table_validations:
            for reason in row.get("blockers", []):
                blockers.append(f"{row['table']}: {reason}")
        return {
            "mode": sync_mode,
            "remote_schema": remote_schema,
            "executable": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "table_validations": table_validations,
            "target_tables": [item.get("name") for item in target_tables],
            "matrix_scope": "all" if include_disabled else "enabled",
        }
    finally:
        for conn, cursor in homology_connections.values():
            if cursor is not None:
                cursor.close()
            conn.close()
        if remote_cursor is not None:
            remote_cursor.close()
        if remote_conn is not None:
            remote_conn.close()
        if local_session is not None:
            local_session.close()


def upsert_to_local(
    table_name: str,
    records: List[Dict],
    primary_keys: List[str],
    *,
    batch_size: int = 1,
    session: Optional[Session] = None,
    replace_case_refs: Optional[Sequence[CaseRefInput]] = None,
    required_columns: Sequence[str] = (),
) -> int:
    """将数据写入本地 PG；整次住院重载时按三坐标原子替换旧快照。"""
    if not records and replace_case_refs is None:
        return 0

    normalized_replace_refs = (
        normalize_case_refs(replace_case_refs) if replace_case_refs is not None else ()
    )

    requested_primary_keys = [str(key).strip().lower() for key in primary_keys if str(key).strip()]
    for key in requested_primary_keys:
        _safe_identifier(key)

    owns_session = session is None
    session_context = Session(engine) if owns_session else nullcontext(session)
    with session_context as active_session:
        local_schema, local_columns, local_primary_keys = _get_local_table_meta(active_session, table_name)
        if not local_schema:
            raise ValueError(f"表 {table_name} 本地目标 schema 未命中，无法执行 UPSERT")
        if not local_primary_keys:
            raise ValueError(f"表 {table_name} 本地目标表缺少主键信息，无法执行 UPSERT")

        # 历史调用方会传入 table_config.key_fields；这套配置未包含 institute_id 等真实主键字段。
        # 为避免 ON CONFLICT 命中不到唯一约束，写入阶段必须以本地表真实主键为准。
        effective_primary_keys = [str(key).strip().lower() for key in local_primary_keys if str(key).strip()]
        for key in effective_primary_keys:
            _safe_identifier(key)

        if requested_primary_keys and requested_primary_keys != effective_primary_keys:
            logger.info(
                "表 %s UPSERT 主键已按本地约束覆盖：requested=%s effective=%s",
                table_name,
                requested_primary_keys,
                effective_primary_keys,
            )

        table_ident = f"{_safe_identifier(local_schema)}.{_safe_identifier(table_name)}"
        existing_columns = set(local_columns)
        if set(required_columns) - existing_columns:
            raise ValueError(f"表 {table_name} 缺少 homology 证据字段，请先升级本地数据库")
        if normalized_replace_refs:
            identity_columns = {"institute_id", "patient_id", "visit_id"}
            if not identity_columns.issubset(existing_columns):
                raise ValueError(
                    f"表 {table_name} 缺少完整三坐标字段，无法执行整次住院重载"
                )

        normalized_batch_size = max(1, min(int(batch_size), 2000))
        grouped_rows: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
        skipped_empty_rows = 0
        skipped_missing_pk_rows = 0
        missing_pk_names: set[str] = set()
        for record in records:
            normalized_record = _apply_sync_column_aliases(
                table_name=table_name,
                record=record,
                existing_columns=existing_columns,
            )
            filtered: Dict[str, Any] = {}
            for k, v in normalized_record.items():
                col_name = str(k).lower()
                if col_name in existing_columns:
                    filtered[col_name] = v

            if not filtered:
                skipped_empty_rows += 1
                continue
            row_missing_pks = [pk for pk in effective_primary_keys if pk not in filtered or filtered.get(pk) in (None, "")]
            if row_missing_pks:
                skipped_missing_pk_rows += 1
                missing_pk_names.update(row_missing_pks)
                continue

            column_shape = tuple(filtered.keys())
            grouped_rows.setdefault(column_shape, []).append(filtered)

        inserted = sum(len(rows) for rows in grouped_rows.values())
        if normalized_replace_refs and skipped_missing_pk_rows:
            missing_keys = ", ".join(sorted(missing_pk_names))
            raise ValueError(
                f"表 {table_name} 整次住院重载前发现 {skipped_missing_pk_rows}/{len(records)} "
                f"行缺少本地主键字段，拒绝删除旧快照: {missing_keys}"
            )
        if normalized_replace_refs and skipped_empty_rows:
            raise ValueError(
                f"表 {table_name} 整次住院重载前发现 {skipped_empty_rows}/{len(records)} "
                "行没有任何可落库字段，拒绝删除旧快照"
            )
        if inserted == 0 and records:
            if skipped_missing_pk_rows:
                missing_keys = ", ".join(sorted(missing_pk_names))
                raise ValueError(
                    f"表 {table_name} 源库返回 {len(records)} 行，但全部因缺少本地主键字段而未落库: {missing_keys}"
                )
            if skipped_empty_rows:
                raise ValueError(
                    f"表 {table_name} 源库返回 {len(records)} 行，但没有任何字段匹配本地 CDM 表结构"
                )

        if normalized_replace_refs:
            delete_sql = (
                f"DELETE FROM {table_ident} "
                "WHERE institute_id = :institute_id "
                "AND patient_id = :patient_id "
                "AND visit_id = :visit_id"
            )
            delete_params = [case_ref.as_dict() for case_ref in normalized_replace_refs]
            active_session.execute(
                text(delete_sql),
                delete_params if len(delete_params) > 1 else delete_params[0],
            )

        for column_shape, rows_with_same_shape in grouped_rows.items():
            columns = list(column_shape)
            placeholders = ", ".join([f":{c}" for c in columns])
            col_list = ", ".join([_safe_identifier(c) for c in columns])
            conflict_clause = ", ".join([_safe_identifier(k) for k in effective_primary_keys])
            update_cols = [c for c in columns if c not in effective_primary_keys]
            if update_cols:
                update_set = ", ".join(
                    [f"{_safe_identifier(c)} = EXCLUDED.{_safe_identifier(c)}" for c in update_cols]
                )
                sql = (
                    f"INSERT INTO {table_ident} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_set}"
                )
            else:
                sql = (
                    f"INSERT INTO {table_ident} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_clause}) DO NOTHING"
                )

            for start in range(0, len(rows_with_same_shape), normalized_batch_size):
                chunk = rows_with_same_shape[start : start + normalized_batch_size]
                active_session.execute(text(sql), chunk if len(chunk) > 1 else chunk[0])

        if owns_session:
            active_session.commit()
        if skipped_missing_pk_rows:
            logger.warning(
                "表 %s 有 %s/%s 行因缺少本地主键字段被跳过: %s",
                table_name,
                skipped_missing_pk_rows,
                len(records),
                sorted(missing_pk_names),
            )
        return inserted


# ==================== 主同步逻辑 ====================

def _mark_primary_records_sync_completed(
    case_refs: Sequence[CaseRef],
    *,
    completed_at: datetime,
) -> None:
    """仅在整次病例资料完整同步后标记病历池主记录。

    该时间是本地同步事实，不覆盖源库 update_time；病历池的“今日同步·在院”
    依此字段筛选，避免把源资料修改时间误作同步时间。
    """

    if engine is None or not case_refs:
        return

    with Session(engine) as session:
        schema, columns, _ = _get_local_table_meta(session, "mr")
        if not schema or "local_sync_completed_at" not in columns:
            raise RuntimeError("病历池同步时间字段未就绪，请先执行数据库升级")
        table_ident = f"{_safe_identifier(schema)}.mr"
        session.execute(
            text(
                f"""
                UPDATE {table_ident}
                SET local_sync_completed_at = :completed_at
                WHERE institute_id = :institute_id
                  AND patient_id = :patient_id
                  AND visit_id = :visit_id
                """
            ),
            [
                {**case_ref.as_dict(), "completed_at": completed_at}
                for case_ref in case_refs
            ],
        )
        session.commit()


def _emit_sync_progress(
    progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    payload: Dict[str, Any],
) -> None:
    previous = dict(_sync_state.progress or {})
    if previous.get("run_id") != payload.get("run_id"):
        previous = {}
    previous.update(payload)
    _sync_state.progress = previous
    try:
        _upsert_sync_job_state(_sync_state)
    except Exception as exc:
        logger.warning(
            "sync_progress_persist_failed error_type=%s",
            type(exc).__name__,
        )
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception as exc:
        logger.debug("sync progress callback failed (ignored): %s", exc)


def _build_case_ref_progress(
    eligible_case_refs: set[Any],
    visible_case_refs: set[Any],
) -> Dict[str, Any]:
    """按完整三坐标统计病例主记录可见进度。"""
    total = len(eligible_case_refs)
    completed = (
        len(eligible_case_refs & visible_case_refs) if eligible_case_refs else 0
    )
    return {
        "total": total,
        "completed": completed,
        "remaining": max(0, total - completed),
        "missing_mr": max(0, total - completed),
        "detail_only": 0,
        "basis": "case_ref_primary_visible",
        "identity_basis": "institute_id+patient_id+visit_id",
        "label": "病历池可见进度",
    }


def _create_case_scope_service():
    from .case_scope_service import CaseScopeService

    return CaseScopeService(
        remote_url_loader=get_remote_db_url,
        db_config_loader=load_db_config,
        connection_factory=psycopg2.connect,
    )


def _create_case_set_sync_service():
    from .case_set_sync_service import CaseSetSyncService

    return CaseSetSyncService(
        table_catalog_loader=list_sync_tables,
        row_fetcher=fetch_remote_rows_by_case_refs,
        row_upserter=upsert_to_local,
        visit_index_ingester=ingest_sync_rows,
        remote_url_loader=get_remote_db_url,
        db_config_loader=load_db_config,
    )


def _scope_mode_for_scene(scene: str) -> str:
    if scene == "running":
        return "active"
    if scene == "both":
        return "active_and_discharged"
    return "discharged"


def _uses_unconfigured_institute(case_ref: Any) -> bool:
    """识别历史自动补入的占位机构号；该值不能作为生产三坐标。"""
    return str(getattr(case_ref, "institute_id", "") or "").strip().upper() == UNCONFIGURED_INSTITUTE_ID


def _current_hospital_date() -> date:
    """返回医院当前自然日；在院范围不使用客户端选择的历史日期。"""
    return datetime.now(_HOSPITAL_TIMEZONE).date()


def _resolve_case_scope_window(
    *,
    scene: str,
    sync_date: Optional[str],
    policy: Dict[str, Any],
    date_window: Optional[Dict[str, str]],
    target_departments: Optional[List[str]],
) -> Tuple[
    Optional[date],
    Optional[date],
    Optional[date],
    List[str],
    Optional[str],
]:
    if scene != "running":
        start_date, end_date, departments, error = _resolve_pg_extract_window(
            policy=policy,
            date_window=date_window,
            target_departments=target_departments,
        )
        if scene == "both":
            return _current_hospital_date(), start_date, end_date, departments, error
        return end_date, start_date, end_date, departments, error

    has_department_override = isinstance(target_departments, list)
    override_departments = (
        _normalize_target_departments(target_departments)
        if has_department_override
        else []
    )
    policy_departments = _normalize_target_departments(policy.get("target_departments"))
    departments = override_departments if has_department_override else policy_departments
    return _current_hospital_date(), None, None, departments, None


@legacy_sync_operation
def run_sync(
    sync_date: str = None,
    tables: List[str] = None,
    scene: str = "both",
    policy_version: str = "",
    tables_hash: str = "",
    date_window: Optional[Dict[str, str]] = None,
    target_departments: Optional[List[str]] = None,
    run_id: str = "",
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    include_internal_case_refs: bool = False,
) -> Dict:
    """
    执行数据同步
    
    Args:
        sync_date: 兼容历史参数，表模式下优先使用 date_window
        tables: 要同步的表名列表，默认同步所有核心表
        scene: 同步场景（决定公共住院范围：在院、出院或合并）
        policy_version: 策略版本（用于幂等与追溯）
        tables_hash: 表范围哈希（用于幂等与追溯）
        date_window: 出院日期范围（start/end 或 start_date/end_date）；在院场景忽略该字段
        target_departments: 目标科室覆盖（空或 * 表示全院）
    
    Returns:
        同步结果
    """
    lock_conn = None
    lock_acquired = False
    try:
        if engine is not None:
            lock_conn = engine.connect()
            lock_acquired = bool(
                lock_conn.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": _SYNC_LOCK_KEY},
                ).scalar()
            )
            if not lock_acquired:
                return {"success": False, "error": "同步正在进行中，请稍后再试"}
        elif _sync_state.is_running:
            return {"success": False, "error": "同步正在进行中，请稍后再试"}

        _sync_state.is_running = True
        _sync_state.logs = []
        _upsert_sync_job_state(_sync_state)
        _emit_sync_progress(
            progress_callback,
            {
                "run_id": run_id,
                "status": "running",
                "stage": "initializing",
                "current_table": "",
                "tables_total": 0,
                "tables_done": 0,
                "rows_pulled_total": 0,
                "rows_upserted_total": 0,
                "eligible_visit_count": 0,
                "visit_progress": _build_case_ref_progress(set(), set()),
                "failed_tables": 0,
                "eta_seconds": None,
            },
        )

        remote_url = get_remote_db_url()
        if not remote_url:
            return {"success": False, "error": "REMOTE_DB_URL 未配置"}
        sync_mode = _resolve_sync_mode()
        resolved_scene = _normalize_sync_scene(scene)
        base_target_tables, missing_tables = _resolve_target_tables(tables)
        if missing_tables:
            return {"success": False, "error": f"未知同步表: {', '.join(missing_tables)}"}

        target_tables, missing_anchors = _route_tables_by_scene(base_target_tables, resolved_scene)
        if missing_anchors:
            return {
                "success": False,
                "error": f"场景 {resolved_scene} 的锚点表未纳入执行集: {', '.join(missing_anchors)}",
                "scene": resolved_scene,
                "target_tables": [str(item.get('name')) for item in base_target_tables],
            }
        if not target_tables:
            return {
                "success": False,
                "error": f"场景 {resolved_scene} 当前无可执行锚点表",
                "scene": resolved_scene,
            }
        if sync_mode == "table" and "mr" not in {str(item.get("name") or "") for item in target_tables}:
            # mr 是病历池主记录。即使调用方只选明细表，也必须按 eligible visit_ids 补拉 mr，
            # 否则会出现“明细同步成功但病历池不可见”的静默成功。
            mr_tables, mr_missing = _resolve_target_tables(["mr"])
            if mr_missing:
                return {"success": False, "error": "同步表配置缺少 mr，无法补拉病历主记录"}
            target_tables = [*mr_tables, *target_tables]
        if any(str(item.get("name") or "") == "mr" for item in target_tables):
            target_tables = [
                *[item for item in target_tables if str(item.get("name") or "") == "mr"],
                *[item for item in target_tables if str(item.get("name") or "") != "mr"],
            ]
        _emit_sync_progress(
            progress_callback,
            {
                "run_id": run_id,
                "status": "running",
                "stage": "preflight",
                "current_table": "",
                "tables_total": len(target_tables),
                "tables_done": 0,
                "rows_pulled_total": 0,
                "rows_upserted_total": 0,
                "eligible_visit_count": 0,
                "visit_progress": _build_case_ref_progress(set(), set()),
                "failed_tables": 0,
                "eta_seconds": None,
            },
        )

        preflight = validate_pg_sync_plan(
            tables=[str(item.get("name")) for item in target_tables],
            mode=sync_mode,
        )
        if not preflight.get("executable"):
            return {
                "success": False,
                "error": "预检未通过，已阻断同步触发",
                "mode": sync_mode,
                "scene": resolved_scene,
                "blockers": preflight.get("blockers", []),
                "table_validations": preflight.get("table_validations", []),
            }

        policy = load_sync_policy()
        as_of_date, range_start_date, discharge_end_date, dept_filters, window_error = (
            _resolve_case_scope_window(
                scene=resolved_scene,
                sync_date=sync_date,
                policy=policy,
                date_window=date_window,
                target_departments=target_departments,
            )
        )
        if window_error or as_of_date is None:
            return {
                "success": False,
                "status": "rejected",
                "error": window_error or "病例范围日期无效",
                "mode": sync_mode,
                "scene": resolved_scene,
                "total_records": 0,
                "case_ref_count": 0,
                "eligible_visits": 0,
                "eligible_visit_count": 0,
                "tables": [],
                "warnings": list(preflight.get("warnings") or []),
            }
        if sync_mode != "table":
            return {
                "success": False,
                "status": "rejected",
                "error": "存储过程模式暂不支持公共病例集合同步，请切换为表直连模式",
                "mode": sync_mode,
                "scene": resolved_scene,
                "total_records": 0,
                "case_ref_count": 0,
                "eligible_visits": 0,
                "eligible_visit_count": 0,
                "tables": [],
                "warnings": list(preflight.get("warnings") or []),
            }

        target_table_names = [str(item.get("name") or "") for item in target_tables]
        effective_start_date = None if resolved_scene == "running" else range_start_date
        effective_end_date = discharge_end_date or as_of_date
        effective_date_window = {
            "start": effective_start_date.isoformat() if effective_start_date else "",
            "end": effective_end_date.isoformat(),
        }
        scope_mode = _scope_mode_for_scene(resolved_scene)
        run_warnings: List[str] = [
            str(item)
            for item in (preflight.get("warnings") or [])
            if str(item or "").strip()
        ]

        try:
            scope_result = _create_case_scope_service().resolve_hospitalization_scope(
                scope_mode=scope_mode,
                as_of_date=as_of_date,
                admission_start_date=(
                    as_of_date - timedelta(days=ACTIVE_ADMISSION_LOOKBACK_DAYS)
                    if resolved_scene in {"running", "both"}
                    else None
                ),
                discharge_start_date=range_start_date if resolved_scene != "running" else None,
                discharge_end_date=discharge_end_date,
                departments=dept_filters,
            )
        except Exception as exc:
            logger.warning(
                "case_scope_resolution_failed error_type=%s",
                type(exc).__name__,
            )
            _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _sync_state.last_sync_status = "failed"
            _sync_state.total_records_synced = 0
            _sync_state.logs = []
            _emit_sync_progress(
                progress_callback,
                {
                    "run_id": run_id,
                    "status": "failed",
                    "stage": "scope_resolution",
                    "current_table": "",
                    "tables_total": len(target_tables),
                    "tables_done": 0,
                    "rows_pulled_total": 0,
                    "rows_upserted_total": 0,
                    "eligible_visit_count": 0,
                    "case_ref_count": 0,
                    "visit_progress": _build_case_ref_progress(set(), set()),
                    "failed_tables": 0,
                    "eta_seconds": 0,
                },
            )
            return {
                "success": False,
                "status": "failed",
                "error": "病例范围解析失败，请检查同步配置后重试",
                "mode": sync_mode,
                "scene": resolved_scene,
                "policy_version": str(policy_version or ""),
                "tables_hash": str(tables_hash or ""),
                "total_records": 0,
                "target_tables": target_table_names,
                "date_window": effective_date_window,
                "target_departments": dept_filters or ["*"],
                "eligible_visits": 0,
                "eligible_visit_count": 0,
                "case_ref_count": 0,
                "tables": [],
                "warnings": run_warnings,
            }

        case_refs = tuple(scope_result.case_refs)
        eligible_case_refs = set(case_refs)
        discharged_case_refs = {
            case_ref
            for row in scope_result.selected
            if str(row.get("hospitalization_status") or "").strip().lower()
            == "discharged"
            for case_ref in (CaseRef.from_mapping(row),)
            if all(case_ref)
        }
        run_warnings.extend(
            str(item)
            for item in scope_result.warnings
            if str(item or "").strip()
        )
        if not case_refs:
            _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _sync_state.last_sync_status = "failed"
            _sync_state.total_records_synced = 0
            _sync_state.logs = []
            _emit_sync_progress(
                progress_callback,
                {
                    "run_id": run_id,
                    "status": "rejected",
                    "stage": "rejected",
                    "current_table": "",
                    "tables_total": len(target_tables),
                    "tables_done": 0,
                    "rows_pulled_total": 0,
                    "rows_upserted_total": 0,
                    "eligible_visit_count": 0,
                    "case_ref_count": 0,
                    "visit_progress": _build_case_ref_progress(set(), set()),
                    "failed_tables": 0,
                    "eta_seconds": 0,
                },
            )
            return {
                "success": False,
                "status": "rejected",
                "error": "当前病例范围和科室条件下未找到可同步病历，请调整日期范围、科室或源库配置后重试",
                "mode": sync_mode,
                "scene": resolved_scene,
                "policy_version": str(policy_version or ""),
                "tables_hash": str(tables_hash or ""),
                "total_records": 0,
                "target_tables": target_table_names,
                "date_window": effective_date_window,
                "target_departments": dept_filters or ["*"],
                "eligible_visits": 0,
                "eligible_visit_count": 0,
                "case_ref_count": 0,
                "message": "候选病历数为 0，本次未执行同步。",
                "tables": [],
                "sources_used": list(scope_result.sources_used),
                "source_status": scope_result.source_status,
                "warnings": list(dict.fromkeys(run_warnings)),
            }

        placeholder_case_refs = tuple(
            case_ref
            for case_ref in case_refs
            if _uses_unconfigured_institute(case_ref)
        )
        if placeholder_case_refs:
            _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _sync_state.last_sync_status = "rejected"
            _sync_state.total_records_synced = 0
            _sync_state.logs = []
            _emit_sync_progress(
                progress_callback,
                {
                    "run_id": run_id,
                    "status": "rejected",
                    "stage": "institute_configuration",
                    "current_table": "",
                    "tables_total": len(target_tables),
                    "tables_done": 0,
                    "rows_pulled_total": 0,
                    "rows_upserted_total": 0,
                    "eligible_visit_count": len(case_refs),
                    "case_ref_count": len(case_refs),
                    "visit_progress": _build_case_ref_progress(
                        eligible_case_refs,
                        set(),
                    ),
                    "failed_tables": 0,
                    "eta_seconds": 0,
                },
            )
            return {
                "success": False,
                "status": "rejected",
                "error": "请先配置本院稳定机构标识后再执行同步",
                "mode": sync_mode,
                "scene": resolved_scene,
                "total_records": 0,
                "case_ref_count": len(case_refs),
                "eligible_visit_count": len(case_refs),
                "tables": [],
                "warnings": list(dict.fromkeys(run_warnings)),
            }

        visible_case_count = 0

        def _forward_case_set_progress(payload: Dict[str, Any]) -> None:
            nonlocal visible_case_count
            step_key = str(payload.get("step_key") or "")
            stage_by_step = {
                "syncing": "syncing_table",
                "primary_visible": "primary_visibility",
                "primary_unavailable": "primary_visibility",
                "bundle_refresh": "bundle_refresh",
                "completed": "finalizing",
            }
            processed_tables = int(payload.get("processed_tables") or 0)
            total_tables = int(payload.get("total_tables") or len(target_tables))
            if "visible_case_count" in payload:
                visible_case_count = max(
                    0,
                    min(len(case_refs), int(payload.get("visible_case_count") or 0)),
                )
            visit_progress = {
                "total": len(case_refs),
                "completed": visible_case_count,
                "remaining": max(0, len(case_refs) - visible_case_count),
                "missing_mr": max(0, len(case_refs) - visible_case_count),
                "detail_only": 0,
                "basis": "case_ref_primary_visible",
                "identity_basis": "institute_id+patient_id+visit_id",
                "label": "病历池可见进度",
            }
            progress_payload = {
                "run_id": run_id,
                "status": "running",
                "stage": stage_by_step.get(step_key, step_key or "syncing_table"),
                "current_table": str(payload.get("current_table") or ""),
                "tables_total": total_tables,
                "tables_done": processed_tables,
                "rows_pulled_total": 0,
                "rows_upserted_total": 0,
                "eligible_visit_count": len(case_refs),
                "case_ref_count": len(case_refs),
                "visit_progress": visit_progress,
                "failed_tables": 0,
                "eta_seconds": None,
            }
            bundle_progress = payload.get("bundle_progress")
            if isinstance(bundle_progress, dict):
                progress_payload["bundle_progress"] = dict(bundle_progress)
            _emit_sync_progress(progress_callback, progress_payload)

        try:
            sync_result = _create_case_set_sync_service().sync_case_set(
                case_refs=case_refs,
                table_names=target_table_names,
                policy_version=str(policy_version or ""),
                sync_scene=resolved_scene,
                progress_callback=_forward_case_set_progress,
            )
        except Exception as exc:
            logger.warning(
                "case_set_sync_failed error_type=%s",
                type(exc).__name__,
            )
            _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _sync_state.last_sync_status = "failed"
            _sync_state.total_records_synced = 0
            _sync_state.logs = []
            _emit_sync_progress(
                progress_callback,
                {
                    "run_id": run_id,
                    "status": "failed",
                    "stage": "failed",
                    "current_table": "",
                    "tables_total": len(target_tables),
                    "tables_done": 0,
                    "rows_pulled_total": 0,
                    "rows_upserted_total": 0,
                    "eligible_visit_count": len(case_refs),
                    "case_ref_count": len(case_refs),
                    "visit_progress": _build_case_ref_progress(
                        eligible_case_refs,
                        set(),
                    ),
                    "failed_tables": 1,
                    "eta_seconds": 0,
                },
            )
            return {
                "success": False,
                "status": "failed",
                "error": "病例资料同步失败，请稍后重试；如持续失败请联系管理员",
                "mode": sync_mode,
                "scene": resolved_scene,
                "policy_version": str(policy_version or ""),
                "tables_hash": str(tables_hash or ""),
                "total_records": 0,
                "target_tables": target_table_names,
                "date_window": effective_date_window,
                "target_departments": dept_filters or ["*"],
                "eligible_visits": len(case_refs),
                "eligible_visit_count": len(case_refs),
                "case_ref_count": len(case_refs),
                "tables": [],
                "sources_used": list(scope_result.sources_used),
                "source_status": scope_result.source_status,
                "warnings": list(dict.fromkeys(run_warnings)),
            }

        visible_case_refs = set(sync_result.visible_case_refs)
        missing_primary_case_refs = set(sync_result.missing_primary_case_refs)
        table_results = [dict(item) for item in sync_result.synced_tables]
        unavailable_detail_tables = [
            item
            for item in table_results
            if str(item.get("table_name") or "")
            not in {"mr", "inpat_registration", "admission_record"}
            and item.get("sync_status") == "source_table_unavailable"
        ]
        for table_result in table_results:
            if table_result.get("sync_status") != "source_table_unavailable":
                continue
            table_name = str(table_result.get("table_name") or "未知资料表")
            skip_reason = str(
                table_result.get("skip_reason")
                or "该类资料暂未从源系统提供，本次同步已跳过。"
            )
            run_warnings.append(f"{table_name}: {skip_reason}")
        if missing_primary_case_refs:
            run_warnings.append(
                f"{len(missing_primary_case_refs)} 份病例缺少可见主记录，本次未宣称完整成功"
            )

        total_rows_pulled = int(sync_result.total_rows_pulled)
        total_rows_upserted = int(sync_result.total_rows_upserted)
        final_success = not missing_primary_case_refs and not unavailable_detail_tables
        final_status = (
            "success"
            if final_success
            else "partial"
            if visible_case_refs
            else "failed"
        )
        final_stage = (
            "completed"
            if final_success
            else "details_incomplete"
            if unavailable_detail_tables and visible_case_refs
            else "primary_unavailable"
        )
        if final_success:
            try:
                _mark_primary_records_sync_completed(
                    tuple(visible_case_refs),
                    completed_at=datetime.now(),
                )
            except Exception as exc:
                # 病历资料已完成同步；筛选辅助字段失败不能回滚已写入的病历资料。
                logger.warning(
                    "mark_local_sync_completed_failed error_type=%s",
                    type(exc).__name__,
                )
                run_warnings.append("病历池今日同步筛选标记未写入，请完成数据库升级后再次同步")
        _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _sync_state.last_sync_status = final_status
        _sync_state.total_records_synced = total_rows_upserted
        _sync_state.logs = table_results
        _emit_sync_progress(
            progress_callback,
            {
                "run_id": run_id,
                "status": final_status,
                "stage": final_stage,
                "current_table": "",
                "tables_total": len(target_tables),
                "tables_done": len(table_results),
                "rows_pulled_total": total_rows_pulled,
                "rows_upserted_total": total_rows_upserted,
                "eligible_visit_count": len(case_refs),
                "case_ref_count": len(case_refs),
                "visit_progress": _build_case_ref_progress(
                    eligible_case_refs,
                    visible_case_refs,
                ),
                "failed_tables": len(unavailable_detail_tables)
                if unavailable_detail_tables
                else 0
                if final_success
                else 1,
                "eta_seconds": 0,
            },
        )

        mr_result = next(
            (
                item
                for item in table_results
                if str(item.get("table_name") or "") == "mr"
            ),
            {},
        )
        detail_tables_with_rows = sorted(
            str(item.get("table_name") or "")
            for item in table_results
            if str(item.get("table_name") or "") != "mr"
            and int(item.get("rows_pulled") or 0) > 0
        )
        missing_visit_ids = sorted(
            {
                case_ref.visit_id
                for case_ref in missing_primary_case_refs
                if str(case_ref.visit_id or "").strip()
            }
        )
        result_payload = {
            "success": final_success,
            "status": final_status,
            "mode": sync_mode,
            "scene": resolved_scene,
            "policy_version": str(policy_version or ""),
            "tables_hash": str(tables_hash or ""),
            "total_records": total_rows_upserted,
            "target_tables": target_table_names,
            "date_window": effective_date_window,
            "target_departments": dept_filters or ["*"],
            "eligible_visits": len(case_refs),
            "eligible_visit_count": len(case_refs),
            "case_ref_count": len(case_refs),
            "visible_case_ref_count": len(visible_case_refs),
            "missing_primary_case_ref_count": len(missing_primary_case_refs),
            "missing_primary_case_refs": [
                case_ref.as_dict()
                for case_ref in sorted(missing_primary_case_refs)
            ],
            "primary_visible": bool(sync_result.primary_visible),
            "mr_rows_pulled": int(mr_result.get("rows_pulled") or 0),
            "mr_rows_upserted": int(mr_result.get("rows_upserted") or 0),
            "missing_mr_visit_ids": missing_visit_ids,
            "detail_only_visit_count": 0,
            "detail_only_visit_ids": [],
            "detail_tables_with_rows": detail_tables_with_rows,
            "visit_index_upserted_count": 0,
            "visit_index_failed_count": 0,
            "visit_index_skipped_missing_mr_count": 0,
            "tables": table_results,
            "bundle_refresh": dict(sync_result.bundle_refresh),
            "sources_used": list(scope_result.sources_used),
            "source_status": scope_result.source_status,
            "warnings": list(
                dict.fromkeys(item for item in run_warnings if str(item).strip())
            ),
        }
        if include_internal_case_refs:
            deliverable_case_refs = (
                visible_case_refs
                if resolved_scene == "running"
                else visible_case_refs.intersection(discharged_case_refs)
            )
            result_payload["_internal_synced_case_refs"] = [
                case_ref.as_dict()
                for case_ref in sorted(deliverable_case_refs)
            ]
        return result_payload
    finally:
        _sync_state.is_running = False
        try:
            _upsert_sync_job_state(_sync_state)
        except Exception as exc:
            logger.exception("同步结束写入 sync_job_state 失败: %s", exc)
        finally:
            if lock_conn is not None and lock_acquired:
                try:
                    lock_conn.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": _SYNC_LOCK_KEY})
                except Exception as exc:
                    logger.warning("释放同步锁失败: %s", exc)
            if lock_conn is not None:
                try:
                    lock_conn.close()
                except Exception:
                    pass
