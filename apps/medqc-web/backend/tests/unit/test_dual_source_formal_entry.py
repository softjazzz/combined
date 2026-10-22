"""正式服务入口路由：开关关闭保持旧链，开启在任何旧写入之前分流。"""

from unittest.mock import Mock
import json
from types import SimpleNamespace

import pytest

from app.services.case_identity import CaseRef
from app.services.case_set_sync_service import CaseSetSyncService
from app.services import dual_source_case_service as adapter


@pytest.mark.parametrize("value,expected", [("false", False), ("", False), ("0", False), ("true", True), ("1", True), ("yes", True)])
def test_flag(value, expected, monkeypatch):
    monkeypatch.setenv("DUAL_SOURCE_SYNC_ENABLED", value)
    assert adapter.dual_source_enabled() is expected


def test_invalid_flag_rejected(monkeypatch):
    monkeypatch.setenv("DUAL_SOURCE_SYNC_ENABLED", "maybe")
    with pytest.raises(ValueError):
        adapter.dual_source_enabled()


def test_enabled_shared_entry_bypasses_old_replacement(monkeypatch):
    monkeypatch.setenv("DUAL_SOURCE_SYNC_ENABLED", "true")
    route = Mock(return_value="new-result")
    monkeypatch.setattr(adapter, "sync_case_set", route)
    old_fetch = Mock(side_effect=AssertionError("old read path"))
    old_write = Mock(side_effect=AssertionError("old replacement path"))
    service = CaseSetSyncService(row_fetcher=old_fetch, row_upserter=old_write,
                                 db_config_loader=lambda: {"default_institute_id": "H"})
    assert service.sync_case_set(case_refs=[CaseRef("H", "P", "V")], table_names=["admission_record"],
                                  sync_scene="final", policy_version="test") == "new-result"
    old_fetch.assert_not_called()
    old_write.assert_not_called()
    route.assert_called_once()


def test_formal_adapter_explicit_institution_mapping_required(monkeypatch):
    monkeypatch.delenv("HOMOLOGY_TARGET_INSTITUTE_ID", raising=False)
    monkeypatch.delenv("HOMOLOGY_SOURCE_INSTITUTE_ID", raising=False)
    with pytest.raises(ValueError, match="显式配置"):
        adapter.sync_case_set(Mock(), case_refs=[CaseRef("H", "P", "V")], table_names=["admission_record"],
                              policy_version="test", sync_scene="final", case_scene_by_ref=None,
                              progress_callback=None, config={})


@pytest.mark.parametrize("failure", [None, "visit_index", "bundle_refresh"])
def test_formal_writer_and_postprocessing_status(monkeypatch, tmp_path, failure):
    from app.services.bundles import assembly
    from sqlalchemy.engine import make_url
    monkeypatch.setenv("HOMOLOGY_TARGET_INSTITUTE_ID", "H")
    monkeypatch.setenv("HOMOLOGY_SOURCE_INSTITUTE_ID", "UP")
    monkeypatch.setattr(assembly, "engine", SimpleNamespace(url=make_url("postgresql://test:test@127.0.0.1/medqc")))
    report_path = tmp_path / "report.json"
    row = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    report = {"data_committed": True, "report_path": str(report_path), "inserts": 1, "updated_rows": 0,
              "records": [], "tables": [{"table": "admission_record", "operations": 1,
                                         "quarantined_rows": 0, "source_counts": {"clinical_data": 1, "homology": 0, "local": 0}}]}
    execute = Mock(return_value={"report": report, "rows_by_table": {"admission_record": [row]}})
    monkeypatch.setattr(adapter.writer, "run_sync", execute)
    service = Mock()
    service._table_catalog_loader.return_value = [{"name": "admission_record"}]
    service._remote_url_loader.return_value = "postgresql://test:test@127.0.0.1/clinical_data"
    service.refresh_case_set_bundles.return_value = {"scenes": {}, "domains": {}}
    if failure == "visit_index":
        service._visit_index_ingester.side_effect = RuntimeError("private")
    if failure == "bundle_refresh":
        service.refresh_case_set_bundles.side_effect = RuntimeError("private")
    kwargs = dict(case_refs=[CaseRef("H", "P", "V")], table_names=["admission_record"],
                  policy_version="test", sync_scene="final", case_scene_by_ref=None,
                  progress_callback=None, config={})
    if failure:
        with pytest.raises(adapter.writer.DualSourceWriteError) as error:
            adapter.sync_case_set(service, **kwargs)
        assert error.value.data_committed is True
        assert json.loads(report_path.read_text(encoding="utf-8"))["phase"] == failure
        assert "private" not in report_path.read_text(encoding="utf-8")
    else:
        result = adapter.sync_case_set(service, **kwargs)
        assert result.primary_visible and result.total_rows_upserted == 1
        service._visit_index_ingester.assert_called_once()
        service.refresh_case_set_bundles.assert_called_once()
    assert execute.call_args.kwargs["apply"] is True
