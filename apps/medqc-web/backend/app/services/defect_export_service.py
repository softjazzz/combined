"""
缺陷列表导出服务

功能:
- 导出为 Excel (.xlsx) 格式
- 导出为 CSV 格式
- 支持多条件筛选
- 最大导出 1 万条
"""

import os
import csv
import uuid
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class DefectExportService:
    """缺陷列表导出服务"""

    # Excel 表头映射
    COLUMN_HEADERS = {
        "record_id": "病历ID",
        "patient_name": "患者姓名",
        "department": "科室",
        "rule_name": "规则名称",
        "description": "缺陷描述",
        "severity": "严重程度",
        "category": "缺陷分类",
        "location": "缺陷位置",
        "suggestion": "修改建议",
        "status": "处理状态",
        "created_at": "发现时间",
        "remediated_at": "整改时间",
        "approved_at": "审核时间",
    }

    SEVERITY_MAP = {
        "critical": "严重（一票否决）",
        "error": "错误",
        "warning": "警告",
        "info": "提示",
    }

    STATUS_MAP = {
        "pending": "待处理",
        "urged": "已催办",
        "remediated": "已整改",
        "approved": "审核通过",
        "rejected": "审核存疑",
    }

    async def _fetch_defects(
        self, filters: Dict[str, str], max_rows: int
    ) -> List[Dict[str, Any]]:
        """从数据库获取缺陷数据"""
        from ..core.supabase_client import get_supabase, async_execute

        sb = get_supabase()

        if sb is not None:
            try:
                query = sb.table('qc_defects').select('*')
                for key, value in filters.items():
                    if key == "start_date":
                        query = query.gte('created_at', value)
                    elif key == "end_date":
                        query = query.lte('created_at', value)
                    else:
                        query = query.eq(key, value)

                query = query.order('created_at', desc=True).limit(max_rows)
                resp = await async_execute(query)
                return list(getattr(resp, 'data', None) or [])
            except Exception as e:
                logger.warning(f"从数据库获取缺陷失败，回退到内存: {e}")

        # 回退到内存数据
        from ..storage.memory import qc_results_db
        all_defects = []
        for rid, result in qc_results_db.items():
            if "record_id" in filters and rid != filters["record_id"]:
                continue
            issues = result.get("issues", [])
            for issue in issues:
                defect = {
                    "record_id": rid,
                    "patient_name": result.get("patient_name", ""),
                    "department": result.get("department", ""),
                    "rule_name": issue.get("rule_name", ""),
                    "description": issue.get("description", ""),
                    "severity": issue.get("severity", "warning"),
                    "category": issue.get("category", "other"),
                    "location": issue.get("location", ""),
                    "suggestion": issue.get("suggestion", ""),
                    "status": "pending",
                    "created_at": result.get("analysis_date", ""),
                }
                all_defects.append(defect)

        # 应用筛选
        for key in ["severity", "category", "status", "department"]:
            if key in filters:
                all_defects = [d for d in all_defects if d.get(key) == filters[key]]

        return all_defects[:max_rows]

    def _translate_row(self, row: Dict[str, Any]) -> Dict[str, str]:
        """翻译行数据为中文"""
        translated = {}
        for col_key, col_name in self.COLUMN_HEADERS.items():
            value = row.get(col_key, "")
            # 翻译枚举值
            if col_key == "severity":
                value = self.SEVERITY_MAP.get(value, value)
            elif col_key == "status":
                value = self.STATUS_MAP.get(value, value)
            translated[col_name] = str(value) if value else ""
        return translated

    async def export(
        self,
        format: str = "xlsx",
        max_rows: int = 10000,
        filters: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        执行导出

        Returns:
            包含 file_path, file_name, media_type, total_rows 的字典
        """
        filters = filters or {}
        defects = await self._fetch_defects(filters, max_rows)
        translated_rows = [self._translate_row(d) for d in defects]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "downloads"
        )
        os.makedirs(export_dir, exist_ok=True)

        if format == "csv":
            return await self._export_csv(translated_rows, export_dir, timestamp)
        else:
            return await self._export_xlsx(translated_rows, export_dir, timestamp)

    async def _export_csv(
        self, rows: List[Dict[str, str]], export_dir: str, timestamp: str
    ) -> Dict[str, Any]:
        """导出为 CSV"""
        file_name = f"缺陷列表_{timestamp}.csv"
        file_path = os.path.join(export_dir, file_name)

        headers = list(self.COLUMN_HEADERS.values())

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        return {
            "file_path": file_path,
            "file_name": file_name,
            "media_type": "text/csv; charset=utf-8",
            "total_rows": len(rows),
        }

    async def _export_xlsx(
        self, rows: List[Dict[str, str]], export_dir: str, timestamp: str
    ) -> Dict[str, Any]:
        """导出为 Excel"""
        file_name = f"缺陷列表_{timestamp}.xlsx"
        file_path = os.path.join(export_dir, file_name)

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            # 如果没有 openpyxl，回退到 CSV
            logger.warning("openpyxl 未安装，回退到 CSV 导出")
            return await self._export_csv(rows, export_dir, timestamp)

        wb = Workbook()
        ws = wb.active
        ws.title = "缺陷列表"

        # 表头样式
        header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # 写入标题行
        headers = list(self.COLUMN_HEADERS.values())
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # 写入数据行
        data_font = Font(name="微软雅黑", size=10)
        data_alignment = Alignment(vertical="center", wrap_text=True)

        for row_idx, row_data in enumerate(rows, 2):
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=row_data.get(header, ""))
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = thin_border

        # 设置列宽
        column_widths = {
            "病历ID": 15, "患者姓名": 10, "科室": 10, "规则名称": 25,
            "缺陷描述": 40, "严重程度": 15, "缺陷分类": 12, "缺陷位置": 15,
            "修改建议": 35, "处理状态": 12, "发现时间": 18, "整改时间": 18, "审核时间": 18,
        }
        for col_idx, header in enumerate(headers, 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
                column_widths.get(header, 15)
            )

        # 冻结首行
        ws.freeze_panes = "A2"

        # 添加自动筛选
        ws.auto_filter.ref = ws.dimensions

        wb.save(file_path)

        return {
            "file_path": file_path,
            "file_name": file_name,
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "total_rows": len(rows),
        }
