"""
病案首页导出服务 — 单元测试

TDD RED 阶段：测试先行
支持 3 种导出格式：卫健委标准、医保、结算清单
"""
import pytest
from io import BytesIO
from app.services.frontpage_export_service import (
    FrontpageExportService,
    ExportFormat,
)


# ============================================================
# Fixtures
# ============================================================

def _make_frontpage_data() -> dict:
    """构造一份完整的首页数据用于导出测试。"""
    return {
        "patient_name": "张三",
        "sex": "男",
        "age": 45,
        "id_card": "510521198001011234",
        "nationality": "中国",
        "ethnicity": "汉族",
        "occupation": "工人",
        "marital_status": "已婚",
        "admission_datetime": "2025-12-01 10:00:00",
        "discharge_datetime": "2025-12-10 09:00:00",
        "los_days": 9,
        "admission_dept": "心内科",
        "discharge_dept": "心内科",
        "admission_route": 1,
        "discharge_method": 1,
        "attending_physician": "李医生",
        "diagnoses": [
            {
                "diagnosis_name": "急性心肌梗死",
                "diagnosis_code": "I21.0",
                "diagnosis_type": "主诊断",
                "admission_condition": "1",
            },
            {
                "diagnosis_name": "高血压",
                "diagnosis_code": "I10",
                "diagnosis_type": "次诊断",
                "admission_condition": "1",
            }
        ],
        "surgeries": [
            {
                "surgery_name": "经皮冠状动脉支架置入术",
                "surgery_code": "36.07",
                "surgery_date": "2025-12-02",
                "surgeon_name": "王医生",
                "anesthesia_method": "局部麻醉",
            }
        ],
        "total_cost": 85000.00,
    }


# ============================================================
# 1. 服务基本功能
# ============================================================

class TestExportServiceBasics:
    """导出服务创建和格式列表。"""

    def test_service_creates(self):
        service = FrontpageExportService()
        assert service is not None

    def test_supported_formats(self):
        service = FrontpageExportService()
        formats = service.get_supported_formats()
        assert len(formats) == 3
        assert ExportFormat.NHC in formats      # 卫健委标准
        assert ExportFormat.INSURANCE in formats  # 医保
        assert ExportFormat.SETTLEMENT in formats  # 结算清单


# ============================================================
# 2. 卫健委标准格式导出
# ============================================================

class TestNHCExport:
    """卫健委标准格式导出（住院病案首页）。"""

    def test_export_nhc_returns_bytes(self):
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.NHC)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_nhc_is_valid_excel(self):
        """导出的文件应该是有效的 Excel 文件。"""
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.NHC)
        # Excel 文件以 PK 开头 (ZIP 格式)
        assert result[:2] == b'PK', "导出的文件不是有效的 Excel/ZIP 格式"

    def test_export_nhc_contains_patient_info(self):
        """导出文件应包含患者基本信息。"""
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.NHC)

        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(result))
        ws = wb.active
        # 遍历所有单元格寻找患者姓名
        all_values = [
            str(cell.value) for row in ws.iter_rows() for cell in row
            if cell.value is not None
        ]
        assert any("张三" in v for v in all_values), "导出文件应包含患者姓名"


# ============================================================
# 3. 医保格式导出
# ============================================================

class TestInsuranceExport:
    """医保格式导出。"""

    def test_export_insurance_returns_bytes(self):
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.INSURANCE)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_insurance_is_valid_excel(self):
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.INSURANCE)
        assert result[:2] == b'PK'


# ============================================================
# 4. 结算清单格式导出
# ============================================================

class TestSettlementExport:
    """结算清单格式导出。"""

    def test_export_settlement_returns_bytes(self):
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.SETTLEMENT)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_settlement_is_valid_excel(self):
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        result = service.export(fp, ExportFormat.SETTLEMENT)
        assert result[:2] == b'PK'


# ============================================================
# 5. 边界情况
# ============================================================

class TestEdgeCases:
    """边界情况处理。"""

    def test_export_empty_frontpage(self):
        """空首页应该仍然能导出（只是字段为空）。"""
        service = FrontpageExportService()
        result = service.export({}, ExportFormat.NHC)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_no_diagnoses(self):
        """无诊断的首页应正常导出。"""
        service = FrontpageExportService()
        fp = _make_frontpage_data()
        fp["diagnoses"] = []
        result = service.export(fp, ExportFormat.NHC)
        assert isinstance(result, bytes)
