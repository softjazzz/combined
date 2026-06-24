from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.coding_qc_service import CodingQCEngine  # noqa: E402


def _rule_ids(frontpage: dict) -> set[str]:
    engine = CodingQCEngine(llm_client=None)
    return {issue.rule_id for issue in engine.check_bidding_scenarios(frontpage)}


def test_tumor_primary_diagnosis_requires_morphology_code():
    frontpage = {
        "diagnoses": [
            {"code": "C18.901", "name": "结肠恶性肿瘤"},
        ],
        "fees": {"pathology_diagnosis_fee": 120},
    }

    assert "CQ-TENDER-001" in _rule_ids(frontpage)


def test_pathology_code_requires_pathology_fee_consistency():
    frontpage = {
        "diagnoses": [
            {"code": "C18.901", "name": "结肠恶性肿瘤"},
            {"code": "M8140/3", "name": "腺癌"},
        ],
        "fees": {"pathology_diagnosis_fee": 0},
    }

    assert "CQ-TENDER-001" not in _rule_ids(frontpage)
    assert "CQ-TENDER-002" in _rule_ids(frontpage)


def test_appendicitis_and_peritonitis_trigger_merge_code_suggestion():
    frontpage = {
        "diagnoses": [
            {"code": "K35.901", "name": "急性阑尾炎"},
            {"code": "K65.001", "name": "急性腹膜炎"},
        ],
    }

    assert "CQ-TENDER-003" in _rule_ids(frontpage)


def test_coronary_stent_requires_additional_codes():
    frontpage = {
        "diagnoses": [{"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病"}],
        "surgeries": [
            {"code": "36.0701", "name": "经皮冠状动脉支架植入术"},
        ],
    }

    assert "CQ-TENDER-004" in _rule_ids(frontpage)


def test_coronary_stent_passes_when_required_additional_codes_exist():
    frontpage = {
        "diagnoses": [{"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病"}],
        "surgeries": [
            {"code": "36.0701", "name": "经皮冠状动脉支架植入术"},
            {"code": "00.6601", "name": "置入血管支架数目"},
            {"code": "00.4001", "name": "单支血管操作"},
        ],
    }

    assert "CQ-TENDER-004" not in _rule_ids(frontpage)


@pytest.mark.asyncio
async def test_deterministic_connotation_rules_are_returned_by_run_all():
    engine = CodingQCEngine(llm_client=None)
    report = await engine.run_all({
        "diagnoses": [
            {"code": "K35.901", "name": "急性阑尾炎"},
            {"code": "K65.001", "name": "急性腹膜炎"},
        ],
    })

    assert any(issue.rule_id == "CQ-TENDER-003" for issue in report.rule_issues)
    assert report.llm_issues == []
    assert report.overall_assessment == "需修改"
