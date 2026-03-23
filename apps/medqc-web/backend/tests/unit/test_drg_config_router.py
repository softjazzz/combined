from __future__ import annotations

import pytest


class _FakeDRGConfigStore:
    def __init__(self):
        self.current = {
            "draft": {
                "region": "sichuan",
                "engine": "OpenDRG",
                "baseRate": 10000,
                "hospitalCoefficient": 1.2,
                "regionCoefficient": 1.05,
                "effectiveDate": "2024-01-01",
                "lowRateThreshold": 3,
                "highRateThreshold": 30,
                "enableCCMCC": True,
                "enableAutoSuggestion": True,
            },
            "published_version_id": None,
            "published_config": None,
            "latest_version_id": None,
            "latest_consistency_report": None,
        }
        self.versions = []

    def get_current(self):
        return self.current

    def save_draft(self, config, operator, change_summary):
        self.current["draft"] = dict(config)
        return {
            "draft": self.current["draft"],
            "audit": {
                "version_id": self.current.get("published_version_id"),
                "operator": operator,
                "operated_at": "2026-03-23T00:00:00Z",
                "change_summary": change_summary,
            },
        }

    def publish(self, operator, change_summary):
        version = {
            "version_id": "drgcfg-001",
            "operator": operator,
            "operated_at": "2026-03-23T00:00:00Z",
            "change_summary": change_summary,
            "config": self.current["draft"],
        }
        self.versions.append(version)
        self.current["published_version_id"] = version["version_id"]
        self.current["latest_version_id"] = version["version_id"]
        self.current["published_config"] = self.current["draft"]
        return version

    def list_versions(self):
        return [
            {
                "version_id": item["version_id"],
                "operator": item["operator"],
                "operated_at": item["operated_at"],
                "change_summary": item["change_summary"],
                "published_at": item["operated_at"],
                "is_published": item["version_id"] == self.current.get("published_version_id"),
            }
            for item in self.versions
        ]

    def get_version(self, version_id):
        for item in self.versions:
            if item["version_id"] == version_id:
                return item
        return None

    def rollback(self, version_id, operator, change_summary):
        if not self.get_version(version_id):
            raise KeyError(version_id)
        self.current["published_version_id"] = version_id
        return {
            "version_id": version_id,
            "operator": operator,
            "operated_at": "2026-03-23T00:00:00Z",
            "change_summary": change_summary,
            "config": self.current["draft"],
        }

    def get_audit_logs(self, limit=100):
        return [
            {
                "action": "publish",
                "version_id": self.current.get("published_version_id"),
                "operator": "tester",
                "operated_at": "2026-03-23T00:00:00Z",
                "change_summary": "publish",
            }
        ][:limit]

    def run_consistency_check(self, samples, operator, version_id=None):
        valid = [row for row in samples if row.get("hospital_group") and row.get("insurance_group")]
        matched = [row for row in valid if row.get("hospital_group") == row.get("insurance_group")]
        return {
            "version_id": version_id or self.current.get("published_version_id"),
            "operator": operator,
            "operated_at": "2026-03-23T00:00:00Z",
            "formula": "一致率 = 匹配成功样本数 / 有效对照样本数",
            "summary": {
                "matched_count": len(matched),
                "valid_count": len(valid),
                "consistency_rate": round((len(matched) / len(valid)) * 100, 2) if valid else 0.0,
                "difference_count": len(valid) - len(matched),
            },
            "differences": [
                row for row in valid if row.get("hospital_group") != row.get("insurance_group")
            ],
        }


@pytest.mark.unit
@pytest.mark.api
class TestDRGConfigRouter:
    def test_config_lifecycle(self, client, monkeypatch):
        fake_store = _FakeDRGConfigStore()
        monkeypatch.setattr("app.routers.drg.get_drg_config_store", lambda: fake_store)

        get_resp = client.get("/api/v1/drg/config/current")
        assert get_resp.status_code == 200
        assert get_resp.json()["success"] is True

        save_resp = client.put(
            "/api/v1/drg/config",
            json={
                "operator": "qa-user",
                "change_summary": "调整泸县分组参数",
                "config": {
                    "region": "luzhou",
                    "engine": "OpenDRG",
                    "baseRate": 12000,
                    "hospitalCoefficient": 1.2,
                    "regionCoefficient": 1.05,
                    "effectiveDate": "2026-03-23",
                    "lowRateThreshold": 3,
                    "highRateThreshold": 30,
                    "enableCCMCC": True,
                    "enableAutoSuggestion": True,
                },
            },
        )
        assert save_resp.status_code == 200
        assert save_resp.json()["data"]["audit"]["operator"] == "qa-user"

        publish_resp = client.post(
            "/api/v1/drg/config/publish",
            json={"operator": "qa-user", "change_summary": "泸县发布"},
        )
        assert publish_resp.status_code == 200
        version_id = publish_resp.json()["data"]["version_id"]

        versions_resp = client.get("/api/v1/drg/config/versions")
        assert versions_resp.status_code == 200
        assert versions_resp.json()["data"]["total"] >= 1

        detail_resp = client.get(f"/api/v1/drg/config/versions/{version_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["version_id"] == version_id

        rollback_resp = client.post(
            "/api/v1/drg/config/rollback",
            json={
                "version_id": version_id,
                "operator": "qa-user",
                "change_summary": "回滚验证",
            },
        )
        assert rollback_resp.status_code == 200
        assert rollback_resp.json()["data"]["version_id"] == version_id

    def test_consistency_check_contract(self, client, monkeypatch):
        fake_store = _FakeDRGConfigStore()
        monkeypatch.setattr("app.routers.drg.get_drg_config_store", lambda: fake_store)

        publish_resp = client.post(
            "/api/v1/drg/config/publish",
            json={"operator": "qa-user", "change_summary": "先发布一个版本"},
        )
        assert publish_resp.status_code == 200
        version_id = publish_resp.json()["data"]["version_id"]

        consistency_resp = client.post(
            "/api/v1/drg/config/consistency-check",
            json={
                "operator": "qa-user",
                "version_id": version_id,
                "samples": [
                    {"case_key": "A-1", "hospital_group": "DRG-A", "insurance_group": "DRG-A"},
                    {"case_key": "A-2", "hospital_group": "DRG-B", "insurance_group": "DRG-C"},
                    {"case_key": "A-3", "hospital_group": "", "insurance_group": "DRG-C"},
                ],
            },
        )
        assert consistency_resp.status_code == 200
        data = consistency_resp.json()["data"]
        assert data["summary"]["valid_count"] == 2
        assert data["summary"]["matched_count"] == 1
        assert data["summary"]["consistency_rate"] == 50.0
