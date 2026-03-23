import json
from pathlib import Path

from app.services.frontpage_settings import (
    FrontpageExtractionSettings,
    should_include_demo_records,
)
from app.routers.medical_records import _build_demo_workstation_records, _filter_demo_records


def test_frontpage_settings_default_non_production(monkeypatch):
    monkeypatch.setattr("app.services.frontpage_settings._is_production_env", lambda: False)
    settings = FrontpageExtractionSettings()
    assert settings.include_demo_records is True
    assert settings.auto_hide_demo_when_real_data is True
    assert settings.demo_hide_threshold == 1


def test_frontpage_settings_default_production(monkeypatch):
    monkeypatch.setattr("app.services.frontpage_settings._is_production_env", lambda: True)
    settings = FrontpageExtractionSettings()
    assert settings.include_demo_records is False


def test_demo_decision_matrix():
    settings = FrontpageExtractionSettings(
        include_demo_records=True,
        auto_hide_demo_when_real_data=True,
        demo_hide_threshold=1,
    )
    assert should_include_demo_records(settings, 0) is True
    assert should_include_demo_records(settings, 1) is False

    settings.auto_hide_demo_when_real_data = False
    assert should_include_demo_records(settings, 999) is True

    settings.include_demo_records = False
    assert should_include_demo_records(settings, 0) is False


def test_workstation_demo_filtering():
    demos = _build_demo_workstation_records()
    assert len(demos) >= 2
    assert len(_filter_demo_records(demos, dept="Cardiology", keyword=None)) == 1
    assert len(_filter_demo_records(demos, dept=None, keyword="V-LM-001")) == 1
    assert len(_filter_demo_records(demos, dept="不存在科室", keyword=None)) == 0


def test_frontpage_settings_api_crud(client, monkeypatch, tmp_path: Path):
    config_path = tmp_path / "frontpage_settings.json"
    monkeypatch.setattr("app.services.frontpage_settings.CONFIG_PATH", config_path)
    monkeypatch.setattr("app.services.frontpage_settings._is_production_env", lambda: False)

    resp = client.get("/api/v1/frontpage/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "default"
    assert body["settings"]["include_demo_records"] is True

    update_payload = {
        "include_demo_records": False,
        "demo_hide_threshold": 3,
        "default_preview_tab": "preview",
        "allow_force_llm_regenerate": False,
    }
    resp = client.put("/api/v1/frontpage/settings", json=update_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "file"
    assert body["settings"]["include_demo_records"] is False
    assert body["settings"]["demo_hide_threshold"] == 3
    assert body["settings"]["default_preview_tab"] == "preview"
    assert body["settings"]["allow_force_llm_regenerate"] is False
    assert config_path.exists()

    stored = json.loads(config_path.read_text(encoding="utf-8"))
    assert stored["default_preview_tab"] == "preview"

    resp = client.post("/api/v1/frontpage/settings/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "default"
    assert body["settings"]["include_demo_records"] is True
    assert body["settings"]["demo_hide_threshold"] == 1


def test_frontpage_stream_respects_settings(client, monkeypatch, tmp_path: Path):
    config_path = tmp_path / "frontpage_settings.json"
    monkeypatch.setattr("app.services.frontpage_settings.CONFIG_PATH", config_path)
    config_path.write_text(
        json.dumps(
            {
                "sql_prefill_enabled": True,
                "llm_backfill_enabled": True,
                "allow_force_llm_regenerate": False,
                "include_demo_records": True,
                "auto_hide_demo_when_real_data": True,
                "demo_hide_threshold": 1,
                "stream_progress_enabled": False,
                "default_preview_tab": "fields",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {"force_llm": None}

    class FakeFrontpageService:
        async def _get_llm_context_text(self, _visit_id: str) -> str:
            return ""

        async def extract_from_text_stream(self, _medical_text: str, *, visit_id: str = "", force_llm: bool = False):
            captured["force_llm"] = force_llm
            yield "update", {"module": "basic_info", "frontpage": {"basic_info": {}}}
            yield "done", {"frontpage": {"basic_info": {"patient_name": "测试"}}}

    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", FakeFrontpageService())

    resp = client.post(
        "/api/v1/frontpage/auto-generate-draft-stream",
        json={"visit_id": "V-TEST-001", "medical_text": "demo", "force_llm": True},
    )
    assert resp.status_code == 200
    assert captured["force_llm"] is False
    assert "event: update" not in resp.text
    assert "event: done" in resp.text
