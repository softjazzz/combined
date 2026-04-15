"""
同步模板服务单元测试
"""

from __future__ import annotations

import pytest

from app.services.etl_config import MongoSyncConfig
from app.services.sync_templates import build_template_overrides


@pytest.mark.unit
def test_build_single_department_template():
    cfg = MongoSyncConfig()
    payload = build_template_overrides(
        template_id="single_department_focus",
        departments=["心内科"],
        current_config=cfg,
    )
    assert payload["target_departments"] == ["心内科"]
    assert payload["tier1_interval_minutes"] == 30


@pytest.mark.unit
def test_build_multi_department_template():
    cfg = MongoSyncConfig()
    payload = build_template_overrides(
        template_id="multi_department_joint",
        departments=["心内科", "肛肠外科"],
        current_config=cfg,
    )
    assert payload["target_departments"] == ["心内科", "肛肠外科"]
    assert payload["max_batch_size"] == 100


@pytest.mark.unit
def test_build_hospital_standard_template():
    cfg = MongoSyncConfig()
    payload = build_template_overrides(
        template_id="hospital_standard",
        departments=None,
        current_config=cfg,
    )
    assert payload["target_departments"] == ["*"]


@pytest.mark.unit
def test_build_template_supports_dict_current_config():
    payload = build_template_overrides(
        template_id="hospital_standard",
        departments=None,
        current_config={"scope": "both", "target_departments": ["骨科"]},
    )
    assert payload["target_departments"] == ["*"]


@pytest.mark.unit
def test_build_template_invalid_departments():
    cfg = MongoSyncConfig()

    with pytest.raises(ValueError):
        build_template_overrides(
            template_id="single_department_focus",
            departments=[],
            current_config=cfg,
        )

    with pytest.raises(ValueError):
        build_template_overrides(
            template_id="multi_department_joint",
            departments=["*", "心内科"],
            current_config=cfg,
        )
