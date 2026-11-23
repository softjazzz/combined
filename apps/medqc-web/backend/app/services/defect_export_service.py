"""
缺陷列表导出服务

功能:
- 导出为 Excel (.xlsx) 格式（纯内存 BytesIO）
- 导出为 CSV 格式（纯内存 BytesIO）
- 全单元格防公式注入转义
- 兼容历史 FileResponse 调用方时使用隔离临时文件（绝不写入共享 downloads/ 秒级同名文件）
- 最大导出 1 万条
"""

from __future__ import annotations

import atexit
import csv
import logging
import os
import tempfile
import time
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.export_safety import sanitize_spreadsheet_cell

logger = logging.getLogger(__name__)

_TEMP_EXPORT_DIR_NAME = "medqc_defect_exports"
_TEMP_EXPORT_TTL_SECONDS = 300.0
_CREATED_TEMP_FILES: set[str] = set()


def _get_isolated_temp_dir() -> Path:
    temp_dir = Path(tempfile.gettempdir()) / _TEMP_EXPORT_DIR_NAME
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def cleanup_temp_exports(*, max_age_seconds: float = _TEMP_EXPORT_TTL_SECONDS) -> int:
    """清理过期的隔离临时导出文件，避免 PHI 长期滞留磁盘。"""
    temp_dir = Path(tempfile.gettempdir()) / _TEMP_EXPORT_DIR_NAME
    if not temp_dir.exists():
        return 0
    cutoff = time.time() - max(0.0, float(max_age_seconds))
    removed = 0
    for path in temp_dir.glob("medqc_defect_*"):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            if max_age_seconds <= 0 or path.stat().st_mtime <= cutoff:
                path.unlink(missing_ok=True)
                _CREATED_TEMP_FILES.discard(str(path))
                removed += 1
        except OSError:
            continue
    return removed


def _cleanup_created_temp_files_on_exit() -> None:
    for file_path in list(_CREATED_TEMP_FILES):
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            pass
        finally:
            _CREATED_TEMP_FILES.discard(file_path)


atexit.register(_cleanup_created_temp_files_on_exit)


def _write_isolated_temp_file(payload: bytes, suffix: str) -> str:
    """将导出字节流写入唯一随机隔离临时文件，彻底杜绝并发串覆与 downloads/ 落盘。"""
    cleanup_temp_exports()
    temp_dir = _get_isolated_temp_dir()
    fd, temp_path = tempfile.mkstemp(
        prefix="medqc_defect_",
        suffix=suffix,
        dir=str(temp_dir),
    )
    try:
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(payload)
    except Exception:
        if fd >= 0:
            os.close(fd)
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    _CREATED_TEMP_FILES.add(temp_path)
    return temp_path


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
        from ..core.supabase_client import async_execute, get_supabase

        sb = get_supabase()
        if sb is None:
            raise RuntimeError("数据库不可用")

        query = sb.table("qc_defects").select("*")
        for key, value in filters.items():
            if key == "start_date":
                query = query.gte("created_at", value)
            elif key == "end_date":
                query = query.lte("created_at", value)
            else:
                query = query.eq(key, value)

        query = query.order("created_at", desc=True).limit(max_rows)
        resp = await async_execute(query)
        return list(getattr(resp, "data", None) or [])

    def _translate_row(self, row: Dict[str, Any]) -> Dict[str, str]:
        """翻译行数据为中文（空值转空串，枚举映射为中文标签）。"""
        translated: Dict[str, str] = {}
        for col_key, col_name in self.COLUMN_HEADERS.items():
            value = row.get(col_key, "")
            if col_key == "severity":
                value = self.SEVERITY_MAP.get(value, value)
            elif col_key == "status":
                value = self.STATUS_MAP.get(value, value)
            translated[col_name] = "" if value is None or value == "" else str(value)
        return translated

    def render_csv_stream(self, rows: List[Dict[str, Any]]) -> BytesIO:
        """在内存中渲染带 BOM 的 UTF-8 CSV 字节流，并对全部单元格做公式注入防护。"""
        headers = list(self.COLUMN_HEADERS.values())
        text_buf = StringIO()
        writer = csv.DictWriter(text_buf, fieldnames=headers)
        writer.writeheader()
        for row_data in rows:
            writer.writerow(
                {
                    header: sanitize_spreadsheet_cell(row_data.get(header, ""))
                    for header in headers
                }
            )
        stream = BytesIO(text_buf.getvalue().encode("utf-8-sig"))
        stream.seek(0)
        return stream

    def render_xlsx_stream(self, rows: List[Dict[str, Any]]) -> BytesIO:
        """在内存中渲染格式化 Excel (.xlsx) 字节流，并对全部单元格做公式注入防护。"""
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        wb = Workbook()
        ws = wb.active
        ws.title = "缺陷列表"

        header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        headers = list(self.COLUMN_HEADERS.values())
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=sanitize_spreadsheet_cell(header))
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        data_font = Font(name="微软雅黑", size=10)
        data_alignment = Alignment(vertical="center", wrap_text=True)

        for row_idx, row_data in enumerate(rows, 2):
            for col_idx, header in enumerate(headers, 1):
                safe_value = sanitize_spreadsheet_cell(row_data.get(header, ""))
                cell = ws.cell(row=row_idx, column=col_idx, value=safe_value)
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = thin_border

        column_widths = {
            "病历ID": 15,
            "患者姓名": 10,
            "科室": 10,
            "规则名称": 25,
            "缺陷描述": 40,
            "严重程度": 15,
            "缺陷分类": 12,
            "缺陷位置": 15,
            "修改建议": 35,
            "处理状态": 12,
            "发现时间": 18,
            "整改时间": 18,
            "审核时间": 18,
        }
        for col_idx, header in enumerate(headers, 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
                column_widths.get(header, 15)
            )

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    async def export(
        self,
        format: str = "xlsx",
        max_rows: int = 10000,
        filters: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """执行纯内存流式导出，不向 downloads/ 写入任何共享或持久文件。

        Returns:
            包含 content (BytesIO), file_name, media_type, total_rows 的字典。
        """
        filters = filters or {}
        defects = await self._fetch_defects(filters, max_rows)
        translated_rows = [self._translate_row(d) for d in defects]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "csv":
            return await self._export_csv(translated_rows, export_dir=None, timestamp=timestamp)
        return await self._export_xlsx(translated_rows, export_dir=None, timestamp=timestamp)

    async def _export_csv(
        self,
        rows: List[Dict[str, Any]],
        export_dir: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导出为 CSV。

        - 默认纯内存返回 ``content: BytesIO``，不落盘；
        - 若历史调用方显式传入 ``export_dir``（如基于 FileResponse 的旧路由），
          忽略共享 ``downloads/`` 目录，改为写入唯一随机隔离临时文件以避免并发串覆与 PHI 永久落盘。
        """
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"缺陷列表_{ts}.csv"
        stream = self.render_csv_stream(rows)
        result: Dict[str, Any] = {
            "content": stream,
            "file_name": file_name,
            "media_type": "text/csv; charset=utf-8",
            "total_rows": len(rows),
        }
        if export_dir is not None:
            result["file_path"] = _write_isolated_temp_file(stream.getvalue(), ".csv")
        return result

    async def _export_xlsx(
        self,
        rows: List[Dict[str, Any]],
        export_dir: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导出为 Excel (.xlsx)。

        - 默认纯内存返回 ``content: BytesIO``，不落盘；
        - 若历史调用方显式传入 ``export_dir``，忽略共享 ``downloads/`` 目录，
          改为写入唯一随机隔离临时文件以避免并发串覆与 PHI 永久落盘。
        """
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"缺陷列表_{ts}.xlsx"

        try:
            stream = self.render_xlsx_stream(rows)
        except ImportError:
            logger.warning("openpyxl 未安装，回退到 CSV 导出")
            return await self._export_csv(rows, export_dir=export_dir, timestamp=ts)

        result: Dict[str, Any] = {
            "content": stream,
            "file_name": file_name,
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "total_rows": len(rows),
        }
        if export_dir is not None:
            result["file_path"] = _write_isolated_temp_file(stream.getvalue(), ".xlsx")
        return result
