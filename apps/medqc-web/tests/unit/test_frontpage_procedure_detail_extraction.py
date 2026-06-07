from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.frontpage_extraction_service import FrontPageExtractionService  # noqa: E402


def test_normalize_procedure_details_from_chinese_keys():
    service = FrontPageExtractionService(llm_config={})

    result = service._normalize_procedures_structure(
        {
            "主要手术名称": "冠状动脉造影+冠状动脉支架置入术",
            "手术日期": "2026-02-06",
            "手术级别": "四级",
            "术者医师姓名": "王医生",
            "术者医师代码": "D001",
            "I助姓名": "李一助",
            "I助代码": "D002",
            "II助姓名": "赵二助",
            "II助代码": "D003",
            "切口愈合等级": "I/甲",
            "麻醉方式": "局部麻醉",
            "麻醉医师姓名": "陈麻醉",
            "麻醉医师代码": "D004",
        }
    )

    assert result["main_procedure_text"] == "冠状动脉支架置入术"
    assert result["other_procedures_texts"] == ["冠状动脉造影"]
    assert result["main_procedure_date"] == "2026-02-06"
    assert result["main_procedure_level"] == "四级"
    assert result["surgeon_name"] == "王医生"
    assert result["surgeon_code"] == "D001"
    assert result["assistant1_name"] == "李一助"
    assert result["assistant1_code"] == "D002"
    assert result["assistant2_name"] == "赵二助"
    assert result["assistant2_code"] == "D003"
    assert result["incision_healing_grade"] == "I/甲"
    assert result["anesthesia_method"] == "局部麻醉"
    assert result["anesthetist_name"] == "陈麻醉"
    assert result["anesthetist_code"] == "D004"


def test_normalize_procedure_details_from_nested_main_procedure():
    service = FrontPageExtractionService(llm_config={})

    result = service._normalize_procedures_structure(
        {
            "main_procedure": {
                "name": "腹腔镜胆囊切除术",
                "code": "51.2300",
                "operation_date": "2026-03-01",
                "operation_level": "三级",
                "operator_name": "周医生",
                "operator_code": "OP001",
                "first_assistant_name": "郑一助",
                "first_assistant_code": "OP002",
                "second_assistant_name": "吴二助",
                "second_assistant_code": "OP003",
                "incision_healing": "II/甲",
                "anaesthesia_method": "全身麻醉",
                "anesthesia_doctor_name": "孙麻醉",
                "anesthesia_doctor_code": "AN001",
            },
            "other_procedures": [{"name": "胆道探查术", "date": "2026-03-01"}],
        }
    )

    assert result["main_procedure_text"] == "腹腔镜胆囊切除术"
    assert result["main_procedure_code"] == "51.2300"
    assert result["other_procedures_texts"] == ["胆道探查术"]
    assert result["main_procedure_date"] == "2026-03-01"
    assert result["main_procedure_level"] == "三级"
    assert result["surgeon_name"] == "周医生"
    assert result["surgeon_code"] == "OP001"
    assert result["assistant1_name"] == "郑一助"
    assert result["assistant1_code"] == "OP002"
    assert result["assistant2_name"] == "吴二助"
    assert result["assistant2_code"] == "OP003"
    assert result["incision_healing_grade"] == "II/甲"
    assert result["anesthesia_method"] == "全身麻醉"
    assert result["anesthetist_name"] == "孙麻醉"
    assert result["anesthetist_code"] == "AN001"


def test_normalize_procedure_preserves_no_surgery_shape():
    service = FrontPageExtractionService(llm_config={})

    result = service._normalize_procedures_structure({})

    assert result["main_procedure_text"] is None
    assert result["other_procedures_texts"] == []
