from __future__ import annotations

import sys
import os
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.schemas.frontpage_generation_contract import (  # noqa: E402
    fields_by_tender_item,
    labels_for_group,
    missing_settlement_mappings,
    required_frontpage_paths,
    settlement_mapping_fields,
)
from app.services.frontpage_extraction_service import get_tender_extraction_contract  # noqa: E402
from app.services.settlement_assembly_service import get_frontpage_to_settlement_mapping  # noqa: E402


def test_contract_covers_all_311_tender_groups():
    contract = get_tender_extraction_contract()

    assert fields_by_tender_item("3.1.1(1)")
    assert fields_by_tender_item("3.1.1(2)")
    assert fields_by_tender_item("3.1.1(3)")
    assert fields_by_tender_item("3.1.1(4)")
    assert fields_by_tender_item("3.1.1(5)")
    assert fields_by_tender_item("3.1.1(6)")
    assert all(field.frontpage_path.startswith("frontpage.") for field in contract)
    assert required_frontpage_paths()


def test_contract_includes_required_procedure_detail_fields():
    labels = labels_for_group("诊断及手术操作信息")

    assert "手术操作日期" in labels
    assert "手术操作级别" in labels
    assert "术者医师姓名" in labels
    assert "术者医师代码" in labels
    assert "I助姓名" in labels
    assert "I助代码" in labels
    assert "II助姓名" in labels
    assert "II助代码" in labels
    assert "切口愈合等级" in labels
    assert "麻醉方式" in labels
    assert "麻醉医师姓名" in labels
    assert "麻醉医师代码" in labels


def test_contract_includes_required_other_medical_fields():
    labels = labels_for_group("其他住院医疗信息")

    assert "损伤中毒外部原因名称" in labels
    assert "损伤中毒外部原因编码" in labels
    assert "病理诊断名称" in labels
    assert "病理诊断编码" in labels
    assert "药物过敏" in labels
    assert "ABO血型" in labels
    assert "Rh血型" in labels
    assert "呼吸机使用时间" in labels
    assert "重症监护病房类型" in labels
    assert "重症监护进入时间" in labels
    assert "重症监护退出时间" in labels
    assert "重症监护转移情况" in labels
    assert "入院前昏迷时间" in labels
    assert "入院后昏迷时间" in labels


def test_contract_settlement_fields_match_current_mapping():
    mapping = get_frontpage_to_settlement_mapping()

    assert settlement_mapping_fields()
    assert missing_settlement_mappings(mapping) == []
