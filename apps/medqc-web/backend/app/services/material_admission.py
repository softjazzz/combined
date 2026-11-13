"""取材准入和客户安全错误合同；不读取数据库或更改发布窗口。"""

from datetime import datetime, timedelta, timezone
import os
from .case_material_snapshot import MaterialSnapshotError

MESSAGES = {
    "cdm_publication_window_unconfirmed": "CDM发布范围与取材窗口尚未确认或已过期，未开始执行该病历的质控规则。请先确认发布证据和有效取材窗口。",
    "material_source_contract_incomplete": "临床材料读取合同不完整，病历资料准备失败。",
    "material_source_unavailable": "临床材料来源不可用，病历资料准备失败。",
    "original_task_material_not_retained": "原任务材料快照未保留，不能用当前材料代替原轮次补跑。",
    "material_projection_failed": "材料快照装配失败，未开始执行该病历的质控规则。",
    "material_capture_failed": "病历材料捕获失败，未开始执行该病历的质控规则。",
}


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
    # 来源由服务端 freeze 固定；材料专用入口仍使用原来源，不检查 CDM 窗口。
    if (filters.get("clinical_source") or {}).get("id") == "independent_cdm":
        require_publication_window()
