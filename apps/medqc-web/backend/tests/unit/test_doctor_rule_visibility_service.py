from __future__ import annotations

from app.services import doctor_rule_visibility_service as service


def _detail(entries):
    return {"entries": entries}


def test_visibility_requires_explicit_entry_configuration_and_result_flag(monkeypatch):
    monkeypatch.setattr(service, "get_version_detail", lambda *_args: _detail([
        {"rule_id": "R-OLD", "state": "active"},
        {
            "rule_id": "R-ALL", "state": "active",
            "department_scope_mode": "all", "department_refs": [], "doctor_visible": True,
        },
        {
            "rule_id": "R-HIDDEN", "state": "active",
            "department_scope_mode": "all", "department_refs": [], "doctor_visible": False,
        },
    ]))

    projected = service.project_doctor_visible_items(
        [
            {"rule_id": "R-OLD", "can_show_to_doctor": True},
            {"rule_id": "R-ALL", "can_show_to_doctor": False},
            {"rule_id": "R-ALL", "can_show_to_doctor": True},
            {"rule_id": "R-HIDDEN", "can_show_to_doctor": True},
        ],
        rule_set_key="rules", rule_set_version="v2",
        institute_id="H-1", department_name="心内科",
    )

    assert projected == [{"rule_id": "R-ALL", "can_show_to_doctor": True}]


def test_selected_department_uses_exact_institute_and_department_pair(monkeypatch):
    monkeypatch.setattr(service, "get_version_detail", lambda *_args: _detail([{
        "rule_id": "R-1", "state": "active",
        "department_scope_mode": "selected",
        "department_refs": [{"institute_id": "H-1", "department_name": "心内科"}],
        "doctor_visible": True,
    }]))

    assert service.visible_rule_ids(
        rule_set_key="rules", rule_set_version="v2",
        institute_id="H-1", department_name="心内科",
    ) == frozenset({"R-1"})
    assert service.visible_rule_ids(
        rule_set_key="rules", rule_set_version="v2",
        institute_id="H-2", department_name="心内科",
    ) == frozenset()
