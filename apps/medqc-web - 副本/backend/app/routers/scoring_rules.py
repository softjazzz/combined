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
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/scoring-rules", tags=["scoring-rules"])
logger = logging.getLogger(__name__)


# ==================== 辅助函数 ====================

def _ensure_db():
    """获取 Supabase 实例，不可用时抛 503"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    return sb


# ==================== API ====================

@router.get("")
async def list_scoring_rules(
    request: Request,
    category: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """获取评分规则列表"""
    sb = _ensure_db()

    try:
        query = sb.table('scoring_rules').select('*')
        if category:
            query = query.eq('category', category)
        if enabled is not None:
            query = query.eq('enabled', enabled)
        if keyword and hasattr(query, 'or_'):
            query = query.or_(f"name.ilike.%{keyword}%,description.ilike.%{keyword}%")
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
    except Exception as e:
        logger.error(f"查询评分规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询评分规则失败: {str(e)}")


@router.post("")
async def create_scoring_rule(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """创建评分规则"""
    sb = _ensure_db()
    body = await request.json()

    if not body.get("name"):
        raise HTTPException(status_code=400, detail="规则名称不能为空")

    rule = {
        "id": str(uuid.uuid4()),
        "sort_order": body.get("sort_order", 0),
        "category": body.get("category", "形式质控"),
        "name": body["name"],
        "description": body.get("description", ""),
        "deduction": body.get("deduction", 1),
        "max_deduction": body.get("max_deduction", body.get("deduction", 1)),
        "veto": body.get("veto", False),
        "severity": body.get("severity", "warning"),
        "enabled": body.get("enabled", True),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    try:
        resp = await async_execute(sb.table('scoring_rules').insert(rule).select().single())
        return success_response(data=getattr(resp, 'data', rule), message="创建成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建评分规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建评分规则失败: {str(e)}")


@router.put("/{rule_id}")
async def update_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """更新评分规则"""
    sb = _ensure_db()
    body = await request.json()

    updatable = ["category", "name", "description", "deduction", "max_deduction", "veto", "severity", "enabled", "sort_order"]
    update_data = {k: body[k] for k in updatable if k in body}
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
    except Exception as e:
        logger.error(f"更新评分规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新评分规则失败: {str(e)}")


@router.delete("/{rule_id}")
async def delete_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除评分规则"""
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
    except Exception as e:
        logger.error(f"删除评分规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除评分规则失败: {str(e)}")


@router.put("/{rule_id}/toggle")
async def toggle_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """启用/禁用评分规则"""
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
    except Exception as e:
        logger.error(f"切换评分规则状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.get("/export")
async def export_scoring_rules(
    request: Request,
    format: str = Query("xlsx"),
    current_user: dict = Depends(get_current_user),
):
    """导出评分规则为 Excel"""
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

        filename = f"评分标准_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="需要安装 openpyxl: pip install openpyxl")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出评分规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/import")
async def import_scoring_rules(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """从 Excel 导入评分规则"""
    sb = _ensure_db()

    try:
        import openpyxl

        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active

        severity_map = {"严重": "critical", "错误": "error", "警告": "warning", "提示": "info"}
        imported = 0
        skipped = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[2]:
                continue

            name = str(row[2]).strip()
            if not name:
                skipped += 1
                continue

            rule_data = {
                "id": str(uuid.uuid4()),
                "sort_order": imported + 1,
                "category": str(row[1]).strip() if row[1] else "形式质控",
                "name": name,
                "description": str(row[3]).strip() if row[3] else "",
                "deduction": float(row[4]) if row[4] else 1,
                "max_deduction": float(row[5]) if row[5] else float(row[4] or 1),
                "veto": str(row[6]).strip() == "是" if row[6] else False,
                "severity": severity_map.get(str(row[7]).strip(), "warning") if row[7] else "warning",
                "enabled": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
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
        raise HTTPException(status_code=500, detail="需要安装 openpyxl")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败: {str(e)}")
