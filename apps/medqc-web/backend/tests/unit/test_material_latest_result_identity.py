"""1026最新结果入口的路径身份兼容；仅合成登记，不读取数据库。"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.services import clinical_sources as sources, validation_material_source as material


def request(query="institute_id=I&patient_id=pdfp_P", suffix="latest-result"):
    return Request({"type": "http", "method": "GET", "headers": [],
                    "path": f"/api/v1/qc/sichuan/workspace/records/pdfv_V/{suffix}",
                    "path_params": {"record_id": "pdfv_V"}, "query_string": query.encode()})


def test_latest_result_uses_path_visit_and_registered_identity(monkeypatch):
    calls = []
    def registered(*identity):
        calls.append(identity)
        assert identity == ("I", "pdfp_P", "pdfv_V")
        return "pdfmat_012345abcdef"
    monkeypatch.setattr(material, "_registered_schema", registered)
    monkeypatch.setattr(sources, "configuration", lambda: pytest.fail("材料入口不读取普通CDM配置"))
    req = request()
    sources.prepare_request(req)
    assert calls == [("I", "pdfp_P", "pdfv_V")]
    assert req.state.clinical_source == sources.legacy_snapshot()


@pytest.mark.parametrize("query", [
    "institute_id=I&patient_id=pdfp_P&visit_id=pdfv_OTHER",
    "patient_id=pdfp_P", "institute_id=I",
    "institute_id=OTHER&patient_id=pdfp_P",
])
def test_identity_conflict_or_incomplete_registration_rejected(monkeypatch, query):
    def registered(*identity):
        if identity != ("I", "pdfp_P", "pdfv_V"):
            raise ValueError("validation_material_identity_not_registered")
        return "pdfmat_012345abcdef"
    monkeypatch.setattr(material, "_registered_schema", registered)
    with pytest.raises(HTTPException) as exc:
        sources.prepare_request(request(query))
    assert exc.value.status_code == 422


def test_other_routes_do_not_infer_visit_from_record_id(monkeypatch):
    monkeypatch.setattr(material, "_registered_schema", lambda *args: pytest.fail("不能替未知接口补身份"))
    with pytest.raises(HTTPException) as exc:
        sources.prepare_request(request(suffix="unknown"))
    assert exc.value.status_code == 422
