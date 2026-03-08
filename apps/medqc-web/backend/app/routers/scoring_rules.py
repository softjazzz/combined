"""
评分标准配置 API

功能:
- 扣分规则 CRUD（单项扣分/最高扣分/一票否决）
- 规则 Excel 导入/导出
- 规则分组管理
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

# ==================== 内存存储（Supabase 回退） ====================
_scoring_rules_db: List[dict] = []

def _init_default_rules():
    """初始化默认评分规则"""
    global _scoring_rules_db
    if _scoring_rules_db:
        return

    defaults = [
        # 形式质控
        {"category": "形式质控", "name": "入院记录24h内完成", "deduction": 2, "max_deduction": 2, "veto": False, "severity": "warning"},
        {"category": "形式质控", "name": "首次病程记录8h内完成", "deduction": 2, "max_deduction": 2, "veto": False, "severity": "warning"},
        {"category": "形式质控", "name": "手术记录24h内完成", "deduction": 3, "max_deduction": 3, "veto": False, "severity": "error"},
        {"category": "形式质控", "name": "出院记录24h内完成", "deduction": 2, "max_deduction": 2, "veto": False, "severity": "warning"},
        {"category": "形式质控", "name": "知情同意书签署", "deduction": 5, "max_deduction": 5, "veto": False, "severity": "error"},
        {"category": "形式质控", "name": "病历涂改未签名", "deduction": 1, "max_deduction": 3, "veto": False, "severity": "info"},
        # 内涵质控
        {"category": "内涵质控", "name": "主诊断与病程不符", "deduction": 5, "max_deduction": 5, "veto": False, "severity": "error"},
        {"category": "内涵质控", "name": "病史采集不完整", "deduction": 3, "max_deduction": 6, "veto": False, "severity": "warning"},
        {"category": "内涵质控", "name": "治疗方案无依据", "deduction": 5, "max_deduction": 5, "veto": False, "severity": "error"},
        {"category": "内涵质控", "name": "抗菌药物使用不规范", "deduction": 3, "max_deduction": 6, "veto": False, "severity": "warning"},
        # 一票否决
        {"category": "一票否决", "name": "伪造病历记录", "deduction": 100, "max_deduction": 100, "veto": True, "severity": "critical"},
        {"category": "一票否决", "name": "缺失关键知情同意", "deduction": 100, "max_deduction": 100, "veto": True, "severity": "critical"},
        {"category": "一票否决", "name": "未经授权修改病历", "deduction": 100, "max_deduction": 100, "veto": True, "severity": "critical"},
        # 编码质控
        {"category": "编码质控", "name": "主诊断编码错误", "deduction": 5, "max_deduction": 5, "veto": False, "severity": "error"},
        {"category": "编码质控", "name": "手术编码缺失", "deduction": 3, "max_deduction": 3, "veto": False, "severity": "warning"},
        {"category": "编码质控", "name": "附加编码遗漏", "deduction": 2, "max_deduction": 4, "veto": False, "severity": "warning"},
    ]

    for i, rule in enumerate(defaults):
        _scoring_rules_db.append({
            "id": str(uuid.uuid4()),
            "sort_order": i + 1,
            "category": rule["category"],
            "name": rule["name"],
            "description": f'{rule["category"]}规则：{rule["name"]}',
            "deduction": rule["deduction"],
            "max_deduction": rule["max_deduction"],
            "veto": rule["veto"],
            "severity": rule["severity"],
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })

_init_default_rules()


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
    rules = list(_scoring_rules_db)

    if category:
        rules = [r for r in rules if r["category"] == category]
    if enabled is not None:
        rules = [r for r in rules if r["enabled"] == enabled]
    if keyword:
        rules = [r for r in rules if keyword in r["name"] or keyword in r.get("description", "")]

    rules.sort(key=lambda r: r.get("sort_order", 999))

    # 统计
    categories = {}
    for r in _scoring_rules_db:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "enabled": 0, "veto_count": 0}
        categories[cat]["total"] += 1
        if r["enabled"]:
            categories[cat]["enabled"] += 1
        if r.get("veto"):
            categories[cat]["veto_count"] += 1

    return success_response(
        data={
            "rules": rules,
            "total": len(rules),
            "categories": categories,
        },
        trace_id=get_trace_id(request),
    )


@router.post("")
async def create_scoring_rule(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """创建评分规则"""
    body = await request.json()

    rule = {
        "id": str(uuid.uuid4()),
        "sort_order": len(_scoring_rules_db) + 1,
        "category": body.get("category", "形式质控"),
        "name": body.get("name", ""),
        "description": body.get("description", ""),
        "deduction": body.get("deduction", 1),
        "max_deduction": body.get("max_deduction", body.get("deduction", 1)),
        "veto": body.get("veto", False),
        "severity": body.get("severity", "warning"),
        "enabled": body.get("enabled", True),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    if not rule["name"]:
        raise HTTPException(status_code=400, detail="规则名称不能为空")

    _scoring_rules_db.append(rule)

    return success_response(data=rule, message="创建成功", trace_id=get_trace_id(request))


@router.put("/{rule_id}")
async def update_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """更新评分规则"""
    body = await request.json()

    rule = next((r for r in _scoring_rules_db if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    updatable = ["category", "name", "description", "deduction", "max_deduction", "veto", "severity", "enabled", "sort_order"]
    for key in updatable:
        if key in body:
            rule[key] = body[key]
    rule["updated_at"] = datetime.now().isoformat()

    return success_response(data=rule, message="更新成功", trace_id=get_trace_id(request))


@router.delete("/{rule_id}")
async def delete_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除评分规则"""
    global _scoring_rules_db
    before = len(_scoring_rules_db)
    _scoring_rules_db = [r for r in _scoring_rules_db if r["id"] != rule_id]

    if len(_scoring_rules_db) == before:
        raise HTTPException(status_code=404, detail="规则不存在")

    return success_response(message="删除成功", trace_id=get_trace_id(request))


@router.put("/{rule_id}/toggle")
async def toggle_scoring_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    """启用/禁用评分规则"""
    rule = next((r for r in _scoring_rules_db if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    rule["enabled"] = not rule["enabled"]
    rule["updated_at"] = datetime.now().isoformat()

    return success_response(
        data=rule,
        message=f'已{"启用" if rule["enabled"] else "禁用"}',
        trace_id=get_trace_id(request),
    )


@router.get("/export")
async def export_scoring_rules(
    request: Request,
    format: str = Query("xlsx"),
    current_user: dict = Depends(get_current_user),
):
    """导出评分规则为 Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "评分标准"

        # 表头样式
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

        # 数据
        rules = sorted(_scoring_rules_db, key=lambda r: r.get("sort_order", 999))
        severity_map = {"critical": "严重", "error": "错误", "warning": "警告", "info": "提示"}
        for row_idx, rule in enumerate(rules, 2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1).border = thin_border
            ws.cell(row=row_idx, column=2, value=rule["category"]).border = thin_border
            ws.cell(row=row_idx, column=3, value=rule["name"]).border = thin_border
            ws.cell(row=row_idx, column=4, value=rule.get("description", "")).border = thin_border
            ws.cell(row=row_idx, column=5, value=rule["deduction"]).border = thin_border
            ws.cell(row=row_idx, column=6, value=rule["max_deduction"]).border = thin_border
            ws.cell(row=row_idx, column=7, value="是" if rule.get("veto") else "否").border = thin_border
            ws.cell(row=row_idx, column=8, value=severity_map.get(rule["severity"], rule["severity"])).border = thin_border
            ws.cell(row=row_idx, column=9, value="启用" if rule["enabled"] else "禁用").border = thin_border

            # 一票否决行高亮
            if rule.get("veto"):
                for col in range(1, 10):
                    ws.cell(row=row_idx, column=col).fill = PatternFill(start_color="FFF2CC", fill_type="solid")

        # 列宽
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


@router.post("/import")
async def import_scoring_rules(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """从 Excel 导入评分规则"""
    try:
        import openpyxl

        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active

        severity_map = {"严重": "critical", "错误": "error", "警告": "warning", "提示": "info"}
        imported = 0
        skipped = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[2]:  # 跳过空行
                continue

            name = str(row[2]).strip()
            if not name:
                skipped += 1
                continue

            # 检查是否已存在
            existing = next((r for r in _scoring_rules_db if r["name"] == name), None)
            if existing:
                # 更新
                existing["category"] = str(row[1]).strip() if row[1] else existing["category"]
                existing["description"] = str(row[3]).strip() if row[3] else existing.get("description", "")
                existing["deduction"] = float(row[4]) if row[4] else existing["deduction"]
                existing["max_deduction"] = float(row[5]) if row[5] else existing["max_deduction"]
                existing["veto"] = str(row[6]).strip() == "是" if row[6] else existing.get("veto", False)
                existing["severity"] = severity_map.get(str(row[7]).strip(), existing["severity"]) if row[7] else existing["severity"]
                existing["updated_at"] = datetime.now().isoformat()
            else:
                # 新增
                _scoring_rules_db.append({
                    "id": str(uuid.uuid4()),
                    "sort_order": len(_scoring_rules_db) + 1,
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
                })

            imported += 1

        return success_response(
            data={"imported": imported, "skipped": skipped, "total": len(_scoring_rules_db)},
            message=f"成功导入 {imported} 条规则",
            trace_id=get_trace_id(request),
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="需要安装 openpyxl")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败: {str(e)}")
