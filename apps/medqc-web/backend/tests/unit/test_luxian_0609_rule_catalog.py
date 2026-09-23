from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.services.luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    build_family_scopes,
    customer_rule_count,
    load_luxian_0609_rules,
    resolve_execution_scope,
)
from app.services import luxian_0609_rule_catalog
from app.services.luxian_0609_rule_catalog import (
    attach_luxian_0609_customer_policy,
)
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master


def _assert_success_shell(body: dict) -> dict:
    assert body["success"] is True
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert "data" in body
    return body["data"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _load_existing_rule_ids() -> set[str]:
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "app" / "data" / "sichuan_rules_146.json",
        root / "app" / "data" / "custom_rules_33.json",
        root / "app" / "data" / "customer_rules_luxian_v1.json",
    ]
    rule_ids: set[str] = set()
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        for item in payload:
            rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
            if rule_id:
                rule_ids.add(rule_id)
    return rule_ids


def _load_formal_catalog() -> dict[str, dict]:
    repository_root = Path(__file__).resolve().parents[3]
    payload = json.loads(
        (repository_root / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json")
        .read_text(encoding="utf-8")
    )
    mapping = _migration_id_map()
    return {mapping[str(item["qc_point_id"])]: item for item in payload}


def _migration_id_map() -> dict[str, str]:
    # 原始正式标准保留归档身份；仅测试用离线台账核对迁移后合同等价。
    path = Path(__file__).resolve().parents[3] / "docs/plans/lx0609-four-part-rule-code-mapping-v1.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["legacy_rule_id"]: row["rule_id"] for row in csv.DictReader(handle)}


def _load_formal_catalog_csv_statuses() -> dict[str, set[str]]:
    repository_root = Path(__file__).resolve().parents[3]
    mapping = _migration_id_map()
    with (
        repository_root / "docs" / "0602" / "luxian_0609_formal_rule_catalog.csv"
    ).open(encoding="utf-8", newline="") as handle:
        return {
            mapping[str(item["qc_point_id"])]: {
                status.strip()
                for status in str(item["allowed_result_statuses"]).split(";")
                if status.strip()
            }
            for item in csv.DictReader(handle)
        }


@pytest.mark.unit
def test_luxian_0609_catalog_contains_migrated_rules_and_released_extensions():
    rules = load_luxian_0609_rules()
    migrated_rule_ids = set(_migration_id_map().values())
    released_extension_rule_ids = {
        "LX0609-06-01-03",
        "LX0609-06-02-01",
        "LX0609-06-03-02",
        "LX0609-09-01-02",
    }
    expected_rule_ids = migrated_rule_ids | released_extension_rule_ids

    assert {rule["rule_id"] for rule in rules} == expected_rule_ids
    assert len(rules) == len(expected_rule_ids)
    assert customer_rule_count() == len(expected_rule_ids)
    assert rules[0]["rule_id"] == "LX0609-01-01-01"
    assert _migration_id_map()["LX0609-079"] in expected_rule_ids

    existing_rule_ids = _load_existing_rule_ids()
    phase_extension_rule_ids = {
        new_id for old_id, new_id in _migration_id_map().items()
        if int(old_id.rsplit("-", 1)[1]) >= 50
    }
    for rule in rules:
        assert rule["rule_id"].startswith("LX0609-")
        assert rule.get("rule_code", rule["rule_id"]) == rule["rule_id"]
        assert rule.get("positive_example")
        assert rule.get("negative_example")
        assert rule.get("mapped_rule_ids")
        assert rule.get("primary_execution_rule_id") == rule["mapped_rule_ids"][0]
        for mapped_rule_id in rule["mapped_rule_ids"]:
            assert (
                mapped_rule_id.upper() in existing_rule_ids
                or mapped_rule_id.upper() in phase_extension_rule_ids
                or mapped_rule_id.upper() == rule["rule_id"]
            )


@pytest.mark.unit
def test_customer_policy_projection_uses_rule_master_without_mutating_execution_wrappers():
    wrappers = load_luxian_0609_rules()
    projected = attach_luxian_0609_customer_policy(wrappers)
    master_by_id = {entry.rule_id: entry for entry in load_luxian_0609_rule_master()}

    assert len(projected) == len(wrappers)
    assert all(rule.get("customer_policy") for rule in projected)
    assert "customer_policy" not in wrappers[0]
    for rule in projected:
        policy = rule["customer_policy"]
        assert isinstance(policy["source_document"], str) and policy["source_document"]
        assert isinstance(policy["qc_point"], str) and policy["qc_point"]
        assert isinstance(policy["summary"], str) and policy["summary"]
        assert isinstance(policy["sources"], list) and policy["sources"]
        assert all(isinstance(source, str) and source for source in policy["sources"])

    wrapper_by_id = {rule["rule_id"]: rule for rule in wrappers}
    projected_by_id = {rule["rule_id"]: rule for rule in projected}
    for rule_id in ("LX0609-02-01-05", "LX0609-03-01-01", "LX0609-03-01-04", "LX0609-04-02-04", "LX0609-04-05-03", "LX0609-07-01-03"):
        policy = projected_by_id[rule_id]["customer_policy"]
        master = master_by_id[rule_id]
        assert policy == {
            "source_document": master.source_document,
            "qc_point": master.qc_point,
            "summary": master.policy_summary,
            "sources": list(master.policy_sources),
        }
        assert projected_by_id[rule_id]["mapped_rule_ids"] == wrapper_by_id[rule_id]["mapped_rule_ids"]
        assert (
            projected_by_id[rule_id]["primary_execution_rule_id"]
            == wrapper_by_id[rule_id]["primary_execution_rule_id"]
        )

    implant_summary = projected_by_id["LX0609-04-02-04"]["customer_policy"]["summary"]
    assert all(
        field in implant_summary
        for field in ("名称", "种类", "规格或型号", "材质", "数量")
    )
    assert "条码不属于本规则必填字段" in implant_summary
    assert "真实病例金标" in implant_summary
    assert not wrapper_by_id["LX0609-04-05-03"].get("customer_text")
    assert projected_by_id["LX0609-04-05-03"]["customer_policy"]["summary"]
    assert not wrapper_by_id["LX0609-07-01-03"].get("customer_text")
    assert projected_by_id["LX0609-07-01-03"]["customer_policy"]["summary"]


@pytest.mark.unit
def test_formal_catalog_allows_not_executed_only_for_phase_pending_rules():
    """阶段暂停是正式交付状态，且只能由唯一规则主表派生。"""

    catalog = _load_formal_catalog()
    csv_statuses = _load_formal_catalog_csv_statuses()
    pending_rule_ids = {
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.phase_status == "pending_definition" and entry.rule_id in catalog
    }

    assert pending_rule_ids
    for rule_id, item in catalog.items():
        statuses = set(item["allowed_result_statuses"])
        assert ("not_executed" in statuses) is (rule_id in pending_rule_ids)
        assert csv_statuses[rule_id] == statuses


@pytest.mark.unit
def test_025_and_059_catalogs_expose_the_frozen_pending_business_contracts():
    rules = {rule["rule_id"]: rule for rule in load_luxian_0609_rules()}

    implant = rules["LX0609-04-02-04"]
    assert implant["applicable_documents"] == ["surgery_record"]
    assert implant["data_dependencies"] == [
        "永久性植入物实际使用",
        "implant_name",
        "implant_type",
        "implant_specification",
        "implant_material",
        "implant_quantity",
        "病程记录仅辅助确认实际使用，不得替代正式手术记录五字段",
    ]
    assert tuple(item["criterion_id"] for item in implant["criteria"]) == (
        "implant_name",
        "implant_type",
        "implant_specification",
        "implant_material",
        "implant_quantity",
    )
    assert "条码不参与本规则判定" in implant["description"]
    assert "病程记录中有相应记录" not in implant["description"]
    implant_prompt = implant["custom_prompt"]
    assert all(
        field in implant_prompt
        for field in (
            "implant_name",
            "implant_type",
            "implant_specification",
            "implant_material",
            "implant_quantity",
        )
    )
    assert "条码不参与 LX0609-04-02-04 判定" in implant_prompt
    assert "病程记录仅用于辅助确认是否实际使用永久性植入物" in implant_prompt
    assert "不得替代正式手术记录中的五字段" in implant_prompt
    assert "植入物条形码不齐全" not in implant_prompt
    assert "手术记录或病程记录中有相应记录" not in implant_prompt

    treatment_order = rules["LX0609-05-03-01"]
    expected_treatment_sources = [
        "exam_master",
        "exam_item_report",
        "surgery_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "daily_course_record",
        "senior_course_record",
    ]
    assert treatment_order["applicable_documents"] == expected_treatment_sources
    assert treatment_order["applicable_document_labels"] == [
        "检查主记录",
        "检查报告",
        "手术记录",
        "药品医嘱",
        "非药品医嘱",
        "日常病程记录",
        "上级医师查房记录",
    ]
    assert treatment_order["data_dependencies"][:7] == expected_treatment_sources
    assert "抗菌药物名称" not in treatment_order["description"]
    assert all(
        text in treatment_order["description"]
        for text in (
            "order_id",
            "application_id",
            "event_code",
            "禁止药名共现",
            "最近时间猜测",
        )
    )
    assert treatment_order["executor_type"] == "llm"
    assert treatment_order["prompt_version"] == "lx0609-059-event-order-course-shadow-v1"


@pytest.mark.unit
def test_customer_policy_projection_fails_closed_when_rule_master_entry_is_missing(monkeypatch):
    wrappers = load_luxian_0609_rules()
    incomplete_master = tuple(
        entry
        for entry in load_luxian_0609_rule_master()
        if entry.rule_id != "LX0609-04-02-04"
    )
    monkeypatch.setattr(
        luxian_0609_rule_catalog,
        "load_luxian_0609_rule_master",
        lambda: incomplete_master,
    )

    with pytest.raises(ValueError, match="customer policy is missing"):
        attach_luxian_0609_customer_policy(wrappers)


def test_catalog_uses_new_identity_without_runtime_legacy_lookup():
    mapping = _migration_id_map()
    for old_id, new_id in mapping.items():
        assert luxian_0609_rule_catalog.get_luxian_0609_rule(old_id) is None
        assert luxian_0609_rule_catalog.get_luxian_0609_rule(new_id)["rule_id"] == new_id


@pytest.mark.parametrize("field", ["rule_id", "rule_code"])
def test_catalog_rejects_conflicting_or_missing_identity(tmp_path, monkeypatch, field):
    payload = json.loads(luxian_0609_rule_catalog._DATA_PATH.read_text(encoding="utf-8"))
    if field == "rule_code":
        payload[0][field] = "LX0609-001"
    else:
        payload[0].pop("rule_id")
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(luxian_0609_rule_catalog, "_DATA_PATH", path)
    luxian_0609_rule_catalog.load_luxian_0609_rules.cache_clear()
    try:
        with pytest.raises(ValueError):
            luxian_0609_rule_catalog.load_luxian_0609_rules()
    finally:
        luxian_0609_rule_catalog.load_luxian_0609_rules.cache_clear()


@pytest.mark.unit
def test_luxian_0609_customer_rule_package_resolves_scope_and_families():
    execution_rule_ids, invalid_rule_ids, gate_only_customer_rule_ids = resolve_execution_scope(
        ["LX0609-03-01-01", "LX0609-03-01-02", "LX0609-05-01-01", "LX0609-999"],
        allowed_rule_ids={"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-05-01-01"},
    )

    assert execution_rule_ids == ["LX0609-03-01-01", "LX0609-03-01-02", "LX0609-05-01-01"]
    assert invalid_rule_ids == ["LX0609-999"]
    assert gate_only_customer_rule_ids == []

    scopes = build_family_scopes(["LX0609-03-01-01", "LX0609-03-01-02", "LX0609-05-01-01"])
    assert scopes == [
        {"key": "consultation_quality", "name": "会诊质量", "rule_ids": ["LX0609-03-01-01", "LX0609-03-01-02"]},
        {"key": "surgery_anesthesia", "name": "手术麻醉", "rule_ids": ["LX0609-05-01-01"]},
    ]


@pytest.mark.unit
@pytest.mark.api
def test_luxian_0609_rules_endpoint_returns_customer_rule_view(client):
    access_token = _login(client)
    resp = client.get(
        f"/api/v1/qc/sichuan/rules?rule_set_key={LUXIAN_0609_RULE_SET_KEY}",
        headers=_headers(access_token),
    )
    assert resp.status_code == 200, resp.text

    payload = _assert_success_shell(resp.json())
    rules = payload["rules"]
    assert payload["rule_set_key"] == LUXIAN_0609_RULE_SET_KEY
    # 客户当前没有同意书来源，相关规则不进入客户运行范围。
    excluded_rule_ids = {
        "LX0609-11-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
    }
    expected_rule_ids = {
        rule["rule_id"] for rule in load_luxian_0609_rules()
    } - excluded_rule_ids
    assert payload["total_rules"] == len(expected_rule_ids)
    assert len(rules) == len(expected_rule_ids)
    assert {rule["rule_id"] for rule in rules} == expected_rule_ids
    assert rules[0]["rule_id"] == "LX0609-01-01-01"
    assert rules[0]["positive_example"]
    assert rules[0]["negative_example"]
    assert rules[0]["mapped_rule_ids"]
    assert rules[0]["primary_execution_rule_id"] == rules[0]["mapped_rule_ids"][0]
    master_by_id = {entry.rule_id: entry for entry in load_luxian_0609_rule_master()}
    assert rules[24]["customer_policy"]["summary"] == master_by_id["LX0609-04-02-04"].policy_summary

    grouped_resp = client.get(
        f"/api/v1/qc/sichuan/rules?rule_set_key={LUXIAN_0609_RULE_SET_KEY}&grouped=true",
        headers=_headers(access_token),
    )
    assert grouped_resp.status_code == 200, grouped_resp.text
    grouped = _assert_success_shell(grouped_resp.json())["rules_by_document_type"]
    grouped_rules = [
        rule
        for rules_for_document in grouped.values()
        for rule in rules_for_document
    ]
    grouped_by_id = {rule["rule_id"]: rule for rule in grouped_rules}
    assert grouped_by_id["LX0609-03-01-01"]["customer_policy"] == {
        "source_document": master_by_id["LX0609-03-01-01"].source_document,
        "qc_point": master_by_id["LX0609-03-01-01"].qc_point,
        "summary": master_by_id["LX0609-03-01-01"].policy_summary,
        "sources": list(master_by_id["LX0609-03-01-01"].policy_sources),
    }


@pytest.mark.unit
@pytest.mark.api
def test_surgery_procedure_catalog_endpoint_exposes_customer_visible_policy(client):
    access_token = _login(client)
    resp = client.get(
        "/api/v1/qc/sichuan/surgery-procedure-catalog"
        "?keyword=01.2408&category=手术&effective_level=四级",
        headers=_headers(access_token),
    )
    assert resp.status_code == 200, resp.text

    payload = _assert_success_shell(resp.json())
    assert payload["version"] == "luxian-surgery-procedure-2025-v1"
    assert payload["policy"]["level_priority"].startswith("院内绩效分配优先")
    assert payload["policy"]["conditional_level_four"] == "条件四级按四级手术执行"
    assert payload["total"] == 1
    assert payload["items"] == [
        {
            "code": "01.2408",
            "name": "颅内血肿清除术",
            "category": "手术",
            "effective_level": "四级",
            "raw_level": "院内四级",
            "source": "hospital_performance",
            "source_label": "院内绩效分配",
        }
    ]

    operation_resp = client.get(
        "/api/v1/qc/sichuan/surgery-procedure-catalog?category=operation&page_size=100",
        headers=_headers(access_token),
    )
    operation_payload = _assert_success_shell(operation_resp.json())
    assert operation_payload["total"] == operation_payload["summary"]["operation"]
    assert all(item["category"] != "手术" for item in operation_payload["items"])
