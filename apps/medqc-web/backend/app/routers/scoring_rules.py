"""
评分标准配置 API（PG 版）

功能:
- 扣分规则 CRUD（单项扣分/最高扣分/一票否决）
- 规则 Excel 导入/导出
- 规则分组管理

数据源：PostgreSQL scoring_rules 表
"""

import io
import logging
import math
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from urllib.parse import quote

from fastapi import APIRouter, Request, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.roles import effective_roles
from ..core.security import get_current_user, require_global_qc_rule_admin, require_roles

router = APIRouter(prefix="/api/v1/scoring-rules", tags=["scoring-rules"])
logger = logging.getLogger(__name__)

MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_XLSX_ZIP_ENTRIES = 200
MAX_XLSX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_IMPORT_ROWS = 2000
_READ_CHUNK_BYTES = 64 * 1024
_ALLOWED_XLSX_MIMES = frozenset({
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
})
_ALLOWED_SEVERITIES = frozenset({"critical", "error", "warning", "info"})
_DEMO_FULL_ROLES = frozenset({"sync_admin", "super_admin", "developer"})
_OR_FILTER_UNSAFE_RE = re.compile(r"[,().*%_\\\"\']+")


# ==================== 辅助函数 ====================

def _ensure_db():
    """获取 Supabase 实例，不可用时抛 503"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    return sb


def _sanitize_or_keyword(keyword: str) -> str:
    """移除 PostgREST .or_() 语法敏感字符，防止通过逗号/括号/点号注入额外过滤条件。"""
    return _OR_FILTER_UNSAFE_RE.sub("", str(keyword or "").strip())


def _extract_user_roles(current_user: Optional[Dict[str, Any]]) -> set[str]:
    if not isinstance(current_user, dict):
        return set()
    roles = set(effective_roles(current_user.get("roles")))
    single = str(current_user.get("role") or "").strip()
    if single:
        roles.update(effective_roles([single]))
    return {r.strip().lower() for r in roles if isinstance(r, str) and r.strip()}


def _is_restricted_demo_account(current_user: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(current_user, dict):
        return False
    if current_user.get("is_demo_account") is not True:
        return False
    return not bool(_extract_user_roles(current_user).intersection(_DEMO_FULL_ROLES))


def _reject_restricted_demo_account(
    current_user: Optional[Dict[str, Any]],
    detail: str = "演示账号禁止修改评分规则",
) -> None:
    if _is_restricted_demo_account(current_user):
        raise HTTPException(status_code=403, detail=detail)


def _require_global_admin(
    current_user: Optional[Dict[str, Any]],
    detail: str = "仅全局管理员允许修改评分规则",
) -> None:
    require_global_qc_rule_admin(current_user, detail=detail)


def _parse_finite_score(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=422, detail=f"{field_name} 必须为有效数字")
    num = float(value)
    if not math.isfinite(num) or num < 0 or num > 100:
        raise HTTPException(status_code=422, detail=f"{field_name} 须在 0 到 100 之间")
    return num


def _validate_scoring_rule_payload(body: Any, *, is_create: bool) -> Dict[str, Any]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须为 JSON 对象")

    cleaned: Dict[str, Any] = {}
    if is_create or "name" in body:
        raw_name = body.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(status_code=400, detail="规则名称不能为空")
        name = raw_name.strip()
        if len(name) > 200:
            raise HTTPException(status_code=422, detail="规则名称长度不能超过 200 字符")
        cleaned["name"] = name

    if is_create or "category" in body:
        raw_cat = body.get("category", "形式质控")
        if not isinstance(raw_cat, str) or not raw_cat.strip() or len(raw_cat.strip()) > 100:
            raise HTTPException(status_code=422, detail="规则类别无效")
        cleaned["category"] = raw_cat.strip()

    if is_create or "description" in body:
        raw_desc = body.get("description", "")
        if raw_desc is None:
            raw_desc = ""
        if not isinstance(raw_desc, str) or len(raw_desc) > 2000:
            raise HTTPException(status_code=422, detail="规则说明长度不能超过 2000 字符")
        cleaned["description"] = raw_desc.strip()

    if is_create or "sort_order" in body:
        raw_sort = body.get("sort_order", 0)
        if isinstance(raw_sort, bool) or not isinstance(raw_sort, int) or not 0 <= raw_sort <= 100000:
            raise HTTPException(status_code=422, detail="排序序号必须为 0 到 100000 的整数")
        cleaned["sort_order"] = raw_sort

    if is_create or "deduction" in body:
        cleaned["deduction"] = _parse_finite_score(
            body.get("deduction", 1), field_name="单项扣分"
        )

    if is_create or "max_deduction" in body:
        default_max = cleaned.get("deduction", body.get("deduction", 1))
        cleaned["max_deduction"] = _parse_finite_score(
            body.get("max_deduction", default_max), field_name="最高扣分"
        )

    if "deduction" in cleaned and "max_deduction" in cleaned:
        if cleaned["max_deduction"] < cleaned["deduction"]:
            raise HTTPException(status_code=422, detail="最高扣分不能小于单项扣分")

    if is_create or "severity" in body:
        raw_sev = str(body.get("severity", "warning") or "").strip().lower()
        if raw_sev not in _ALLOWED_SEVERITIES:
            raise HTTPException(status_code=422, detail="严重级别无效")
        cleaned["severity"] = raw_sev

    if is_create or "veto" in body:
        raw_veto = body.get("veto", False)
        if not isinstance(raw_veto, bool):
            raise HTTPException(status_code=422, detail="一票否决标识必须为布尔值")
        cleaned["veto"] = raw_veto

    if is_create or "enabled" in body:
        raw_enabled = body.get("enabled", True)
        if not isinstance(raw_enabled, bool):
            raise HTTPException(status_code=422, detail="启用状态必须为布尔值")
        cleaned["enabled"] = raw_enabled

    return cleaned


async def _read_and_validate_xlsx_upload(file: UploadFile) -> bytes:
    filename = str(file.filename or "").strip()
    ext = Path(filename).suffix.lower() if filename else ""
    if ext != ".xlsx":
        raise HTTPException(status_code=400, detail="仅支持导入 .xlsx 格式的 Excel 文件")

    content_type = str(file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in _ALLOWED_XLSX_MIMES:
        raise HTTPException(status_code=400, detail="不支持的文件 MIME 类型，仅接受 .xlsx 文件")

    chunks: list[bytes] = []
    total_bytes = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_IMPORT_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"导入文件过大，最大支持 {MAX_IMPORT_FILE_BYTES // (1024 * 1024)}MB",
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(status_code=400, detail="导入文件不能为空")

    content = b"".join(chunks)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_XLSX_ZIP_ENTRIES:
                raise HTTPException(status_code=400, detail="导入文件压缩条目数超限")
            uncompressed_total = sum(max(0, int(info.file_size)) for info in infos)
            if uncompressed_total > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise HTTPException(status_code=413, detail="导入文件解压体积超限")
    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 .xlsx 文件格式") from None
    return content


# ==================== API ====================

@router.get("")
async def list_scoring_rules(
    request: Request,
    category: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles("admin", "qc_manager", "super_admin")),
):
    """获取评分规则列表"""
    del current_user
    sb = _ensure_db()

    try:
        query = sb.table('scoring_rules').select('*')
        if category:
            query = query.eq('category', category)
        if enabled is not None:
            query = query.eq('enabled', enabled)
        if keyword is not None and str(keyword).strip():
            safe_keyword = _sanitize_or_keyword(keyword)
            if not safe_keyword:
                return success_response(
                    data={"rules": [], "total": 0, "categories": {}},
                    trace_id=get_trace_id(request),
                )
            if hasattr(query, 'or_'):
                query = query.or_(f"name.ilike.%{safe_keyword}%,description.ilike.%{safe_keyword}%")
        query = query.order('sort_order')

        resp = await async_execute(query)
        rules = list(getattr(resp, 'data', None) or [])

        # 分类统计
        categories = {}
        for r in rules:
            cat = r.get("category", "未分类")
            if cat not in categories:
                categories[cat] = {"total": 0, "enabled": 0, "veto_count": 0}
            categories[cat]["total"] += 1
            if r.get("enabled"):
                categories[cat]["enabled"] += 1
            if r.get("veto"):
                categories[cat]["veto_count"] += 1

        return success_response(
            data={"rules": rules, "total": len(rules), "categories": categories},
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("查询评分规则失败")
        raise HTTPException(status_code=500, detail="查询评分规则失败，请稍后重试")


@router.post("")
async def create_scoring_rule(
    request: Request,
    current_user: dict = Depends(require_roles("admin", "super_admin")),
):
    """创建评分规则（仅全局管理员）"""
    _reject_restricted_demo_account(current_user, "演示账号禁止创建评分规则")
    _require_global_admin(current_user, "仅全局管理员允许创建评分规则")
    sb = _ensure_db()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体 JSON 格式无效") from None

    validated = _validate_scoring_rule_payload(body, is_create=True)
    now_iso = datetime.now().isoformat()
    rule = {
        "id": str(uuid.uuid4()),
        **validated,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        resp = await async_execute(sb.table('scoring_rules').insert(rule).select().single())
        return success_response(data=getattr(resp, 'data', rule), message="创建成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception:
        logger.exception("创建评分规则失败")
        raise HTTPException(status_code=500, detail="创建评分规则失败，请稍后重试")


@router.put("/{rule_id}")
async def update_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(require_roles("admin", "super_admin")),
):
    """更新评分规则（仅全局管理员）"""
    _reject_restricted_demo_account(current_user, "演示账号禁止更新评分规则")
    _require_global_admin(current_user, "仅全局管理员允许更新评分规则")
    sb = _ensure_db()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体 JSON 格式无效") from None

    update_data = _validate_scoring_rule_payload(body, is_create=False)
    update_data["updated_at"] = datetime.now().isoformat()

    try:
        resp = await async_execute(
            sb.table('scoring_rules').update(update_data).eq('id', rule_id).select().single()
        )
        if not getattr(resp, 'data', None):
            raise HTTPException(status_code=404, detail="规则不存在")
        return success_response(data=resp.data, message="更新成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception:
        logger.exception("更新评分规则失败 rule_id=%s", rule_id)
        raise HTTPException(status_code=500, detail="更新评分规则失败，请稍后重试")


@router.delete("/{rule_id}")
async def delete_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(require_roles("admin", "super_admin")),
):
    """删除评分规则（仅全局管理员）"""
    _reject_restricted_demo_account(current_user, "演示账号禁止删除评分规则")
    _require_global_admin(current_user, "仅全局管理员允许删除评分规则")
    sb = _ensure_db()

    try:
        resp = await async_execute(
            sb.table('scoring_rules').delete().eq('id', rule_id).select()
        )
        if not getattr(resp, 'data', None):
            raise HTTPException(status_code=404, detail="规则不存在")
        return success_response(message="删除成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception:
        logger.exception("删除评分规则失败 rule_id=%s", rule_id)
        raise HTTPException(status_code=500, detail="删除评分规则失败，请稍后重试")


@router.put("/{rule_id}/toggle")
async def toggle_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(require_roles("admin", "super_admin")),
):
    """启用/禁用评分规则（仅全局管理员）"""
    _reject_restricted_demo_account(current_user, "演示账号禁止切换评分规则状态")
    _require_global_admin(current_user, "仅全局管理员允许切换评分规则状态")
    sb = _ensure_db()

    try:
        # 先查当前状态
        resp = await async_execute(sb.table('scoring_rules').select('enabled').eq('id', rule_id).single())
        if not getattr(resp, 'data', None):
            raise HTTPException(status_code=404, detail="规则不存在")

        new_enabled = not resp.data.get('enabled', True)
        resp2 = await async_execute(
            sb.table('scoring_rules').update({"enabled": new_enabled, "updated_at": datetime.now().isoformat()}).eq('id', rule_id).select().single()
        )
        return success_response(
            data=getattr(resp2, 'data', None),
            message=f'已{"启用" if new_enabled else "禁用"}',
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("切换评分规则状态失败 rule_id=%s", rule_id)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


@router.get("/export")
async def export_scoring_rules(
    request: Request,
    format: str = Query("xlsx"),
    current_user: dict = Depends(require_roles("admin", "qc_manager", "super_admin")),
):
    """导出评分规则为 Excel"""
    del current_user, format
    sb = _ensure_db()

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        # 从 PG 拉取
        resp = await async_execute(sb.table('scoring_rules').select('*').order('sort_order'))
        rules = list(getattr(resp, 'data', None) or [])

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "评分标准"

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

        headers = ["序号", "类别", "规则名称", "说明", "单项扣分", "最高扣分", "一票否决", "严重级别", "状态"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        severity_map = {"critical": "严重", "error": "错误", "warning": "警告", "info": "提示"}
        for row_idx, rule in enumerate(rules, 2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1).border = thin_border
            ws.cell(row=row_idx, column=2, value=rule.get("category", "")).border = thin_border
            ws.cell(row=row_idx, column=3, value=rule.get("name", "")).border = thin_border
            ws.cell(row=row_idx, column=4, value=rule.get("description", "")).border = thin_border
            ws.cell(row=row_idx, column=5, value=rule.get("deduction", 0)).border = thin_border
            ws.cell(row=row_idx, column=6, value=rule.get("max_deduction", 0)).border = thin_border
            ws.cell(row=row_idx, column=7, value="是" if rule.get("veto") else "否").border = thin_border
            ws.cell(row=row_idx, column=8, value=severity_map.get(rule.get("severity", ""), rule.get("severity", ""))).border = thin_border
            ws.cell(row=row_idx, column=9, value="启用" if rule.get("enabled") else "禁用").border = thin_border
            if rule.get("veto"):
                for col in range(1, 10):
                    ws.cell(row=row_idx, column=col).fill = PatternFill(start_color="FFF2CC", fill_type="solid")

        widths = [6, 12, 24, 30, 10, 10, 10, 10, 8]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        date_tag = datetime.now().strftime('%Y%m%d')
        ascii_filename = f"scoring_rules_{date_tag}.xlsx"
        utf8_filename = quote(f"评分标准_{date_tag}.xlsx", safe="")
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{ascii_filename}"; '
                    f"filename*=UTF-8''{utf8_filename}"
                )
            },
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="导出依赖暂不可用")
    except HTTPException:
        raise
    except Exception:
        logger.exception("导出评分规则失败")
        raise HTTPException(status_code=500, detail="导出失败，请稍后重试")


@router.post("/import")
async def import_scoring_rules(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("admin", "super_admin")),
):
    """从 Excel 导入评分规则（仅全局管理员，限 .xlsx 且校验体积/Zip Bomb）"""
    _reject_restricted_demo_account(current_user, "演示账号禁止导入评分规则")
    _require_global_admin(current_user, "仅全局管理员允许导入评分规则")
    sb = _ensure_db()

    content = await _read_and_validate_xlsx_upload(file)
    wb = None
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active

        severity_map = {"严重": "critical", "错误": "error", "警告": "warning", "提示": "info"}
        imported = 0
        skipped = 0
        processed_rows = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 3 or not row[2]:
                continue
            processed_rows += 1
            if processed_rows > MAX_IMPORT_ROWS:
                raise HTTPException(
                    status_code=413,
                    detail=f"单次导入行数超过上限（最大 {MAX_IMPORT_ROWS} 行）",
                )

            name = str(row[2]).strip()
            if not name or len(name) > 200:
                skipped += 1
                continue

            col_cat = row[1] if len(row) > 1 else None
            col_desc = row[3] if len(row) > 3 else None
            col_ded = row[4] if len(row) > 4 else None
            col_max = row[5] if len(row) > 5 else None
            col_veto = row[6] if len(row) > 6 else None
            col_sev = row[7] if len(row) > 7 else None

            try:
                deduction = float(col_ded) if col_ded not in (None, "") else 1.0
                max_deduction = float(col_max) if col_max not in (None, "") else deduction
                if (
                    not math.isfinite(deduction)
                    or not math.isfinite(max_deduction)
                    or deduction < 0
                    or deduction > 100
                    or max_deduction < deduction
                    or max_deduction > 100
                ):
                    skipped += 1
                    continue
            except (TypeError, ValueError):
                skipped += 1
                continue

            now_iso = datetime.now().isoformat()
            rule_data = {
                "id": str(uuid.uuid4()),
                "sort_order": imported + 1,
                "category": str(col_cat).strip()[:100] if col_cat else "形式质控",
                "name": name,
                "description": str(col_desc).strip()[:2000] if col_desc else "",
                "deduction": deduction,
                "max_deduction": max_deduction,
                "veto": str(col_veto).strip() == "是" if col_veto else False,
                "severity": severity_map.get(str(col_sev).strip(), "warning") if col_sev else "warning",
                "enabled": True,
                "created_at": now_iso,
                "updated_at": now_iso,
            }

            try:
                await async_execute(sb.table('scoring_rules').insert(rule_data))
                imported += 1
            except Exception:
                # upsert 失败（如重名）则跳过
                skipped += 1

        return success_response(
            data={"imported": imported, "skipped": skipped},
            message=f"成功导入 {imported} 条规则",
            trace_id=get_trace_id(request),
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="导入依赖暂不可用")
    except HTTPException:
        raise
    except Exception:
        logger.exception("导入评分规则失败")
        raise HTTPException(status_code=400, detail="导入失败，请检查 Excel 文件格式")
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass
