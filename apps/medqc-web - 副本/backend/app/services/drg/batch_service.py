from __future__ import annotations

import asyncio
import inspect
import io
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], Awaitable[None] | None]

COLUMN_MAPPING = {
    "病案号": "admission_id",
    "性别": "gender",
    "年龄": "age",
    "年龄天数": "age_day",
    "出生体重": "weight",
    "科室代码": "department",
    "科室名称": "department_name",
    "住院天数": "los",
    "离院方式": "leaving_type",
    "入院日期": "admission_date",
    "出院日期": "discharge_date",
    "诊断列表": "diagnosis_codes",
    "手术操作列表": "procedure_codes",
    "总费用": "total_cost",
    "医保支付": "insurance_payment",
    "主管医生": "doctor",
    "药品费": "drug_cost",
    "耗材费": "material_cost",
    "检查费": "exam_cost",
    "治疗费": "treatment_cost",
}


def _read_dataframe(contents: bytes, filename: str) -> pd.DataFrame:
    file_ext = filename.rsplit(".", 1)[-1].lower() if filename else "xlsx"
    if file_ext == "csv":
        return pd.read_csv(io.BytesIO(contents), encoding="utf-8-sig")
    if file_ext in {"xlsx", "xls"}:
        return pd.read_excel(io.BytesIO(contents))
    raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 CSV 或 Excel 文件")


async def _emit_progress(progress_callback: Optional[ProgressCallback], completed: int, total: int, stage: str) -> None:
    if progress_callback is None:
        return
    result = progress_callback(completed, total, stage)
    if inspect.isawaitable(result):
        await result


async def process_batch_upload(
    *,
    contents: bytes,
    filename: str,
    grouping_service,
    batch_store,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    df = await asyncio.to_thread(_read_dataframe, contents, filename)
    df = df.rename(columns=COLUMN_MAPPING)

    session_id = await asyncio.to_thread(batch_store.create_session)
    batch_id = await asyncio.to_thread(batch_store.generate_batch_id)
    results = []
    success_count = 0
    failed_count = 0
    total_records = len(df)

    await _emit_progress(progress_callback, 0, total_records, "processing")

    for idx, row in df.iterrows():
        try:
            admission_id = str(row.get("admission_id", f"ROW_{idx}"))
            gender = int(row.get("gender", 1))
            age = int(row.get("age", 0))
            los = int(row.get("los", 1))
            total_cost = float(row.get("total_cost", 0) or 0)

            diagnosis_codes = str(row.get("diagnosis_codes", ""))
            procedure_codes = str(row.get("procedure_codes", "") or "")

            diagnoses = [d.strip() for d in diagnosis_codes.split("|") if d.strip()]
            primary_diagnosis = diagnoses[0] if diagnoses else "Z53.900"
            secondary_diagnoses = diagnoses[1:] if len(diagnoses) > 1 else []
            procedures = [p.strip() for p in procedure_codes.split("|") if p.strip()]

            drg_result = await grouping_service.group_drg(
                primary_diagnosis=primary_diagnosis,
                secondary_diagnoses=secondary_diagnoses,
                procedures=procedures,
                patient_age=age,
                patient_gender="M" if gender == 1 else "F",
                los=los,
                city_name="四川省",
                total_fee=total_cost,
            )

            baseline_payment = drg_result.get("baseline_payment", 0)
            profit_margin = round(baseline_payment - total_cost, 2) if baseline_payment else 0
            record_data = {
                "batch_id": batch_id,
                "admission_id": admission_id,
                "gender": gender,
                "age": age,
                "age_day": row.get("age_day"),
                "weight": row.get("weight"),
                "department": row.get("department"),
                "department_name": row.get("department_name"),
                "los": los,
                "leaving_type": row.get("leaving_type"),
                "admission_date": row.get("admission_date"),
                "discharge_date": row.get("discharge_date"),
                "diagnosis_codes": diagnosis_codes,
                "procedure_codes": procedure_codes,
                "total_cost": total_cost,
                "insurance_payment": row.get("insurance_payment"),
                "drug_cost": row.get("drug_cost"),
                "material_cost": row.get("material_cost"),
                "exam_cost": row.get("exam_cost"),
                "treatment_cost": row.get("treatment_cost"),
                "doctor": row.get("doctor"),
                "mdc": drg_result.get("adrg_code", "")[:4] if drg_result.get("adrg_code") else None,
                "adrg": drg_result.get("adrg_code"),
                "drg": drg_result.get("drg_code"),
                "drg_weight": drg_result.get("weight"),
                "baseline_payment": baseline_payment,
                "profit_margin": profit_margin,
                "status": "分组成功" if drg_result.get("success") else "分组失败",
                "messages": drg_result.get("grouping_logic", ""),
            }

            await asyncio.to_thread(batch_store.save_batch_record, session_id, record_data)
            success_count += 1
            results.append(
                {
                    "admission_id": admission_id,
                    "drg": drg_result.get("drg_code"),
                    "status": "成功",
                    "profit": profit_margin,
                }
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "admission_id": str(row.get("admission_id", f"ROW_{idx}")),
                    "error": str(exc),
                    "status": "失败",
                }
            )
            logger.error("处理行 %s 失败: %s", idx, exc)

        await _emit_progress(progress_callback, idx + 1, total_records, "processing")

    await _emit_progress(progress_callback, total_records, total_records, "finalizing")

    return {
        "success": True,
        "session_id": session_id,
        "batch_id": batch_id,
        "total_records": total_records,
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results[:100],
    }


def get_statistics(
    *,
    session_id: str,
    batch_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    department: Optional[str],
    doctor: Optional[str],
    batch_store,
) -> Dict[str, Any]:
    try:
        basic_stats = batch_store.get_statistics(
            session_id=session_id,
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date,
            department=department,
            doctor=doctor,
        )

        records, _total = batch_store.drill_down(
            session_id=session_id,
            dimension="all",
            value="all",
            batch_id=batch_id,
            page=1,
            per_page=10000,
        )

        if not records:
            basic_stats["ai_insights"] = []
            basic_stats["charts"] = {}
            return {"success": True, "data": basic_stats}

        df = pd.DataFrame(records)
        try:
            from ..services.enhanced_analysis import EnhancedAnalyzer
            from ..services.chart_service import ChartService

            mappings = {
                "baseline_payment": "dip_payment",
                "drg_weight": "dip_weight",
                "drg": "dip_name",
                "department_name": "department",
            }
            analyzer = EnhancedAnalyzer(df, user_mappings=mappings)
            analysis_results = analyzer.run_full_analysis()
            basic_stats["advanced_analysis"] = analysis_results

            insights = []
            overview = analysis_results.get("overview", {})
            if overview.get("loss_case_count", 0) > 0:
                insights.append(f"发现 {overview['loss_case_count']} 例亏损病案，建议关注。")

            top_loss_depts = overview.get("top_loss_departments", [])
            if top_loss_depts:
                dept_names = ", ".join([d["name"] for d in top_loss_depts])
                insights.append(f"前三大亏损科室为: {dept_names}。")

            basic_stats["ai_insights"] = insights
            basic_stats["charts"] = ChartService.generate_all_charts(analysis_results)
        except Exception as exc:
            logger.error("高级分析或图表生成失败: %s", exc, exc_info=True)
            basic_stats["advanced_analysis"] = {}
            basic_stats["ai_insights"] = ["高级分析引擎运行出错"]
            basic_stats["charts"] = {}

        return {"success": True, "data": basic_stats}
    except Exception as exc:
        logger.error("获取统计数据失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


def get_drill_down(
    *,
    session_id: str,
    dimension: str,
    value: str,
    page: int,
    per_page: int,
    batch_id: Optional[str],
    batch_store,
) -> Dict[str, Any]:
    records, total = batch_store.drill_down(
        session_id=session_id,
        dimension=dimension,
        value=value,
        page=page,
        per_page=per_page,
        batch_id=batch_id,
    )
    return {
        "success": True,
        "data": {
            "records": records,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


def list_batches(*, session_id: str, batch_store) -> Dict[str, Any]:
    batches = batch_store.get_batch_list(session_id)
    return {"success": True, "data": batches}


def delete_session(*, session_id: str, batch_store) -> Dict[str, Any]:
    deleted = batch_store.delete_session(session_id)
    if deleted:
        return {"success": True, "message": f"Session {session_id} 已删除"}
    return {"success": False, "message": f"Session {session_id} 不存在"}


def cleanup_expired_sessions(*, batch_store) -> Dict[str, Any]:
    cleaned = batch_store.cleanup_expired_sessions()
    return {"success": True, "cleaned_count": cleaned}


def list_active_sessions(*, batch_store) -> Dict[str, Any]:
    sessions = batch_store.list_active_sessions()
    return {"success": True, "data": sessions}


def build_template_response() -> StreamingResponse:
    template_data = {
        "病案号": ["22058878", "22058879"],
        "性别": [2, 1],
        "年龄": [88, 65],
        "年龄天数": ["", ""],
        "出生体重": ["", ""],
        "科室代码": ["13040503", "13040501"],
        "科室名称": ["心内科", "心内科"],
        "住院天数": [94, 15],
        "离院方式": [1, 1],
        "入院日期": ["2024-01-01", "2024-01-05"],
        "出院日期": ["2024-04-04", "2024-01-20"],
        "诊断列表": ["K22.301|K11.901|E11.900|I10.x05", "I21.001|E11.900|I10.x05"],
        "手术操作列表": ["96.0800x005", "36.0600"],
        "总费用": [85000.00, 45000.00],
        "医保支付": [68000.00, 36000.00],
        "主管医生": ["张三", "李四"],
        "药品费": [25000.00, 15000.00],
        "耗材费": [30000.00, 20000.00],
        "检查费": [10000.00, 5000.00],
        "治疗费": [20000.00, 5000.00],
    }

    df = pd.DataFrame(template_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DRG批量上传模板")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=drg_batch_template.xlsx"},
    )


def export_excel_report(*, session_id: str, batch_id: Optional[str], days: int, batch_store) -> StreamingResponse:
    stats = batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
    records = batch_store.get_all_records(session_id=session_id, batch_id=batch_id)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary = stats["summary"]
        summary_data = {
            "指标": ["总病例数", "入组成功率", "平均CMI", "总费用", "总盈亏", "平均住院日"],
            "数值": [
                summary.get("total_cases", 0),
                f"{summary.get('success_rate', 0):.1f}%",
                f"{summary.get('avg_cmi', 0):.2f}",
                f"¥{summary.get('total_cost', 0):,.2f}",
                f"¥{summary.get('total_profit', 0):,.2f}",
                f"{summary.get('avg_los', 0):.1f} 天",
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name="统计汇总")
        if stats.get("department_stats"):
            pd.DataFrame(stats["department_stats"]).to_excel(writer, index=False, sheet_name="科室统计")
        if records:
            records_df = pd.DataFrame(records)
            col_map = {
                "record_id": "病案号",
                "patient_gender": "性别",
                "patient_age": "年龄",
                "dept_name": "科室",
                "primary_diagnosis": "主诊断",
                "drg_code": "DRG编码",
                "drg_name": "DRG名称",
                "weight": "权重",
                "total_cost": "总费用",
                "profit_margin": "盈亏",
            }
            records_df = records_df.rename(columns=col_map)
            records_df.to_excel(writer, index=False, sheet_name="病例明细")

    output.seek(0)
    filename = f"drg_report_{batch_id or 'all'}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def trigger_notification(*, batch_id: str, notification_type: str, batch_store) -> Dict[str, Any]:
    stats = batch_store.get_statistics(batch_id=batch_id)
    summary = stats.get("summary", {})
    total_cases = summary.get("total_cases", summary.get("total_records", 0))
    message_map = {
        "batch_complete": f"DRG批量分析完成：共{total_cases}例，平均CMI {summary.get('avg_cmi', 0):.2f}，总盈亏 ¥{summary.get('total_profit', 0):,.0f}",
        "cost_warning": "费用预警：发现超标病例",
        "high_loss": "高亏损提醒：发现亏损病例",
    }
    message = message_map.get(notification_type, "通知")
    logger.info("Notification triggered: %s - %s", notification_type, message)
    return {
        "success": True,
        "notification_type": notification_type,
        "message": message,
        "note": "通知服务预留接口，实际发送需配置 Webhook/SMTP",
    }


def export_pdf_report(*, session_id: str, batch_id: Optional[str], days: int, batch_store) -> StreamingResponse:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError as exc:
        logger.error("PDF导出依赖缺失: %s", exc)
        raise HTTPException(status_code=500, detail="PDF导出需要安装 reportlab: pip install reportlab")

    stats = batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
    summary = stats["summary"]

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", fontSize=18, alignment=1, spaceAfter=20)
    heading_style = ParagraphStyle("Heading", fontSize=14, spaceAfter=10, spaceBefore=15)

    elements = []
    elements.append(Paragraph("DRG Analysis Report", title_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Summary Statistics", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Cases", str(summary.get("total_cases", 0))],
        ["Success Rate", f"{summary.get('success_rate', 0):.1f}%"],
        ["Average CMI", f"{summary.get('avg_cmi', 0):.2f}"],
        ["Total Cost", f"¥{summary.get('total_cost', 0):,.2f}"],
        ["Total Profit", f"¥{summary.get('total_profit', 0):,.2f}"],
        ["Average LOS", f"{summary.get('avg_los', 0):.1f} days"],
    ]

    table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 20))

    if stats.get("department_stats"):
        elements.append(Paragraph("Department Statistics", heading_style))
        dept_data = [["Department", "Cases", "CMI", "Profit"]]
        for d in stats["department_stats"][:10]:
            dept_data.append(
                [
                    d.get("department_name", d.get("department", "-"))[:20],
                    str(d.get("count", 0)),
                    f"{d.get('cmi', 0):.2f}",
                    f"¥{d.get('profit', 0):,.0f}",
                ]
            )

        t2 = Table(dept_data, colWidths=[6 * cm, 3 * cm, 3 * cm, 4 * cm])
        t2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22c55e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        elements.append(t2)

    doc.build(elements)
    output.seek(0)
    filename = f"drg_report_{batch_id or 'all'}.pdf"
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def export_word_report(*, session_id: str, batch_id: Optional[str], days: int, batch_store) -> StreamingResponse:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as exc:
        logger.error("Word导出依赖缺失: %s", exc)
        raise HTTPException(status_code=500, detail="Word导出需要安装 python-docx")

    stats = batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
    summary = stats["summary"]
    records = batch_store.get_all_records(session_id=session_id, batch_id=batch_id)

    doc = Document()
    title = doc.add_heading("DRG 分析报告", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph(f"批次ID: {batch_id or '全部'}")
    doc.add_paragraph()

    doc.add_heading("一、统计汇总", level=1)
    table = doc.add_table(rows=7, cols=2)
    table.style = "Table Grid"
    summary_items = [
        ("总病例数", str(summary.get("total_cases", 0))),
        ("入组成功率", f"{summary.get('success_rate', 0):.1f}%"),
        ("平均CMI", f"{summary.get('avg_cmi', 0):.2f}"),
        ("总费用", f"¥{summary.get('total_cost', 0):,.2f}"),
        ("总盈亏", f"¥{summary.get('total_profit', 0):,.2f}"),
        ("平均住院日", f"{summary.get('avg_los', 0):.1f} 天"),
        ("分析天数", f"{days} 天"),
    ]
    for i, (label, value) in enumerate(summary_items):
        table.rows[i].cells[0].text = label
        table.rows[i].cells[1].text = value

    doc.add_paragraph()

    if stats.get("department_stats"):
        doc.add_heading("二、科室分析", level=1)
        dept_table = doc.add_table(rows=1, cols=4)
        dept_table.style = "Table Grid"
        headers = dept_table.rows[0].cells
        headers[0].text = "科室"
        headers[1].text = "病例数"
        headers[2].text = "平均CMI"
        headers[3].text = "盈亏"
        for d in stats["department_stats"][:10]:
            row = dept_table.add_row().cells
            row[0].text = str(d.get("department_name", d.get("department", "-")))[:20]
            row[1].text = str(d.get("count", 0))
            row[2].text = f"{d.get('cmi', 0):.2f}"
            row[3].text = f"¥{d.get('profit', 0):,.0f}"

    if records:
        doc.add_heading("三、病例明细（前20例）", level=1)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        header = table.rows[0].cells
        header[0].text = "病案号"
        header[1].text = "DRG"
        header[2].text = "费用"
        header[3].text = "盈亏"
        for record in records[:20]:
            row = table.add_row().cells
            row[0].text = str(record.get("admission_id", ""))
            row[1].text = str(record.get("drg", ""))
            row[2].text = str(record.get("total_cost", ""))
            row[3].text = str(record.get("profit_margin", ""))

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    filename = f"drg_report_{batch_id or 'all'}.docx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
