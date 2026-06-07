import json
from pathlib import Path

from backend.app.services.drg.analysis_service import build_analysis_export_response


class _EmptyBatchStore:
    def get_all_records(self, session_id=None, batch_id=None):
        return []


class _FixtureDemoStore:
    def __init__(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "drg_analysis_realistic_cases.json"
        self.records = json.loads(fixture.read_text(encoding="utf-8"))

    def list_cases(self, limit=500):
        return self.records[:limit]


def _export(file_format: str):
    return build_analysis_export_response(
        file_format=file_format,
        dimension="department",
        start_date=None,
        end_date=None,
        filter_id=None,
        session_id=None,
        batch_id=None,
        department=None,
        doctor=None,
        version_id="analysis-test",
        batch_store=_EmptyBatchStore(),
        demo_store=_FixtureDemoStore(),
    )


def test_drg_analysis_supports_excel_pdf_docx_exports():
    excel = _export("excel")
    pdf = _export("pdf")
    docx = _export("docx")

    assert excel.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert pdf.media_type == "application/pdf"
    assert docx.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
