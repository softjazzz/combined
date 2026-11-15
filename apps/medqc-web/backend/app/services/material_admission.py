"""取材准入和客户安全错误合同；不读取数据库或更改发布窗口。"""

from datetime import datetime, timedelta, timezone
import os
from .case_material_snapshot import MaterialSnapshotError

MESSAGES = {
    "uncaptured_material_columns": "装配所需的物理表列信息未包含在本次材料中，未开始执行质控规则。",
    "uncaptured_material_table": "装配所需的物理表未包含在本次材料中，未开始执行质控规则。",
    "cdm_publication_window_unconfirmed": "CDM发布范围与取材窗口尚未确认或已过期，未开始执行该病历的质控规则。请先确认发布证据和有效取材窗口。",
    "material_source_contract_incomplete": "临床材料读取合同不完整，病历资料准备失败。",
    "material_source_unavailable": "临床材料来源不可用，病历资料准备失败。",
    "original_task_material_not_retained": "原任务材料快照未保留，不能用当前材料代替原轮次补跑。",
    "material_retry_lineage_invalid": "原任务材料来源链校验失败，未开始执行补跑，请联系管理员核查。",
    "material_integrity_failed": "原任务材料完整性校验失败，不能执行补跑。",
    "material_reference_corrupt": "原任务材料索引损坏，不能执行补跑。",
    "material_object_unavailable": "原任务材料对象不可用，不能执行补跑。",
    "material_projection_failed": "材料快照装配失败，未开始执行该病历的质控规则。",
    "material_capture_failed": "病历材料捕获失败，未开始执行该病历的质控规则。",
    "material_identity_or_source_mismatch": "病历身份或材料来源不一致，未开始执行质控规则。",
    "material_publication_identity_conflict": "材料发布回执的身份关联存在冲突，未开始执行质控规则。",
    "material_publication_version_conflict": "材料发布回执与当前发布版本不一致，未开始执行质控规则。",
}


def report_projection_failure(error, logger):
    """只记录类型及栈位置，不记录异常消息、源码行、局部变量或SQL参数。"""
    from pathlib import Path
    import traceback

    code = "material_projection_failed"
    if isinstance(error, MaterialSnapshotError) and str(error) in MESSAGES:
        code = str(error)
    frames = [
        (Path(frame.f_code.co_filename).name, frame.f_code.co_name, line)
        for frame, line in traceback.walk_tb(error.__traceback__)
    ]
    logger.error("material_assembly_failed code=%s type=%s frames=%s",
                 code, type(error).__name__, frames)
    return code


def safe_material_failure(code):
    code = str(code or "")
    if code not in MESSAGES:
        code = "material_capture_failed"
    return {"code": code, "stage": "material_capture", "message": MESSAGES[code]}


def require_publication_window():
    try:
        until = datetime.fromisoformat(
            os.environ.get("QC_CDM_CAPTURE_WINDOW_UNTIL", "").replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        if until.tzinfo is None or not now < until <= now + timedelta(hours=24):
            raise ValueError
    except ValueError:
        raise MaterialSnapshotError("cdm_publication_window_unconfirmed") from None


def preflight_new_task(filters):
    # 来源由服务端 freeze 固定。正常任务自动在一致性事务中捕获材料；
    # 人工截止时间不能证明发布完整，也不再作为建任务的前置条件。
    # 身份、权限、连接与持久化错误在正式捕获阶段按任务级技术错误交付。
    return None
