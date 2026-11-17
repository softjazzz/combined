"""四类材料同事务捕获、批准输入、不可变回放的纯合成验证。"""
from contextlib import nullcontext
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from test_primary_material_projection import KINDS, synthetic_manifest, _isolated_material_runtime


def test_capture_freezes_dto_and_retry_keeps_original_without_latest_read(monkeypatch, tmp_path):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, case_material_capture as capture
    from app.services import primary_material_projection as primary, daily_material_projection as daily
    from app.services import clinical_source_contract, cdm_publication_evidence
    from app.services.bundles import assembly
    from app.services.sichuan_qc_service import SichuanQCService
    calls = []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execution_options(self, **kwargs): calls.append(kwargs); return self
        def begin(self): return nullcontext()
        def begin_nested(self): return nullcontext()
        def exec_driver_sql(self, sql): calls.append(sql)

    connection = Connection()
    source_engine = SimpleNamespace(connect=lambda: connection)
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "true")
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED", "true")
    monkeypatch.setattr(clinical, "configured", lambda: True)
    monkeypatch.setattr(assembly, "_source_engine", lambda schema: source_engine)
    monkeypatch.setattr(clinical_source_contract, "inspect_source", lambda *a, **kw: {
        "read_only": True, "account_read_only": True,
        "dependencies": [{"table": kind, "status": "columns_missing", "missing_columns": ["record_content"]} for kind in KINDS],
    })
    monkeypatch.setattr(cdm_publication_evidence, "read_publication", lambda *a: {"status": "metadata_unavailable", "rows": {}})
    monkeypatch.setattr(capture, "inspect", lambda c: SimpleNamespace(has_table=lambda *a, **kw: False))
    monkeypatch.setattr(SichuanQCService, "_resolve_primary_diagnosis_context", lambda **kw: None)
    monkeypatch.setattr(daily, "read_manifest", lambda *a: pytest.fail("old v3 double read"))
    value = synthetic_manifest()

    def read_manifest(conn, identity):
        assert conn is connection
        assert identity == ("I", "P", "V")
        calls.append("primary-manifest")
        return deepcopy(value)

    monkeypatch.setattr(primary, "read_manifest", read_manifest)
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic"}):
        captured = capture.capture(identity=("I", "P", "V"))
        assert calls.count("primary-manifest") == 1
        assert calls.index("SET TRANSACTION READ ONLY") < calls.index("primary-manifest")
        assert "engine" not in captured and "connection" not in captured
        assert captured["primary_material_manifest"] == value
        assert captured["documents"]["primary_material_status"]["contract"] == primary.CONTRACT
        for kind in KINDS:
            assert captured["tables"][kind][0]["version_id"] == kind + "-cache"
            assert captured["programmatic_sources"][kind]["material_scope"]["status"] == "available"
        original = material.persist("primary-root", captured)
        value["materials"][0]["body"] = "later body"
        monkeypatch.setattr(capture, "capture", lambda **kw: pytest.fail("retry recaptured"))
        monkeypatch.setattr(primary, "read_manifest", lambda *a: pytest.fail("history read latest"))
        replay = capture.obtain("primary-root", ("I", "P", "V"), retry=True)
        assert replay == original
        with material.activate(replay):
            assert len(primary.rows(("I", "P", "V"), "surgery_record")) == 1
            assert primary.manifest()["materials"][0]["body"] != "later body"


def test_policy_file_requires_explicit_hash_and_source_binding(monkeypatch, tmp_path):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, primary_material_readonly as readonly
    from app.services import case_material_snapshot as material
    policy_json = {"canonical_case": ["I", "P", "V"], "native_cases": [["cache", "NI", "NP", "NV"]],
                   "approval_id": "synthetic-only", "mapping_version": "synthetic"}
    policy = readonly.PrimaryPolicy.from_dict(policy_json)
    path = tmp_path / "synthetic-approved-policy.json"
    entry = {"policy": policy_json, "policy_hash": policy.policy_hash, "source_binding": "synthetic"}
    path.write_text(json.dumps({"policies": [entry]}), encoding="utf-8")
    monkeypatch.setenv("QC_PRIMARY_FOUR_POLICY_FILE", str(path))
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic"}):
        assert primary.load_policy(("I", "P", "V")) == policy
        for changed in ({**entry, "policy_hash": "wrong"}, {**entry, "source_binding": "wrong"}):
            path.write_text(json.dumps({"policies": [changed]}), encoding="utf-8")
            with pytest.raises(material.MaterialSnapshotError, match="approved_policy_required"):
                primary.load_policy(("I", "P", "V"))
    monkeypatch.delenv("QC_PRIMARY_FOUR_POLICY_FILE")
    with pytest.raises(material.MaterialSnapshotError, match="approved_policy_required"):
        primary.load_policy(("I", "P", "V"))


def test_not_deployed_is_distinct_from_permissions_and_bad_manifest(monkeypatch):
    from app.services import primary_material_projection as primary, primary_material_readonly as readonly
    connection = object()
    monkeypatch.setattr(readonly, "primary_objects_available", lambda actual: actual is not connection)
    monkeypatch.setattr(primary, "load_read_plan", lambda identity: pytest.fail("undeployed read policy"))
    captured = {}
    primary.capture_into(captured, connection, ("I", "P", "V"))
    assert captured["primary_material_manifest"] is None
    assert captured["primary_material_capability"]["status"] == "NOT_DEPLOYED"

    def denied(actual):
        assert actual is connection
        raise PermissionError("synthetic permission failure")

    monkeypatch.setattr(readonly, "primary_objects_available", denied)
    with pytest.raises(PermissionError):
        primary.read_manifest(connection, ("I", "P", "V"))


def test_primary_live_context_and_daily_arbitration_own_only_one_connection(monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, daily_material_projection as daily
    from app.services import case_material_snapshot as material
    from app.services.bundles import assembly
    calls = []

    class Connection:
        def __enter__(self): calls.append("connect"); return self
        def __exit__(self, *args): calls.append("exit")
        def execution_options(self, **kwargs): return self
        def begin(self): return nullcontext()
        def exec_driver_sql(self, sql): calls.append(sql)

    conn = Connection()
    monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "true")
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED", "true")
    monkeypatch.setattr(assembly, "_source_engine", lambda *a: SimpleNamespace(connect=lambda: conn))
    monkeypatch.setattr(primary, "read_manifest", lambda actual, identity: synthetic_manifest())
    monkeypatch.setattr(daily, "read_manifest", lambda *a: pytest.fail("second selector"))
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic"}):
        with daily.live_context(("I", "P", "V")):
            with primary.live_context(("I", "P", "V")):
                assert material.context()["connection"] is conn
                assert daily.manifest() is None
        assert calls.count("connect") == calls.count("exit") == 1
        with primary.live_context(("I", "pdfp_P", "pdfv_V")):
            assert material.context() is None


def test_approved_native_identity_projects_canonical_without_rewriting_original(monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, primary_material_readonly as readonly
    from app.services import case_material_snapshot as material
    policy = readonly.PrimaryPolicy(canonical_case=("CI", "CP", "CV"),
        native_cases=(("cache", "I", "P", "V"), ("clinical", "I", "P", "V")),
        approval_id="synthetic", mapping_version="synthetic")
    value = synthetic_manifest()
    value.update(case_id=policy.case_id, policy_hash=policy.policy_hash)
    for entry in value["materials"]:
        entry["target_payload"].update(institute_id="I", patient_id="P", visit_id="V")
    monkeypatch.setattr(primary, "load_read_plan", lambda identity: (policy, readonly.real_contracts()))
    monkeypatch.setattr(readonly, "primary_objects_available", lambda connection: True)
    monkeypatch.setattr(readonly, "read_primary_in_transaction", lambda *args: deepcopy(value))
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic"}):
        selected = primary.read_manifest(object(), ("CI", "CP", "CV"))
        projected = primary.project_rows(selected, "surgery_record")[0]
        assert tuple(projected[key] for key in ("institute_id", "patient_id", "visit_id")) == policy.canonical_case
        assert selected["materials"][0]["native_key"][:3] == ["I", "P", "V"]
        assert selected["materials"][0]["target_payload"]["patient_id"] == "P"
        with pytest.raises(material.MaterialSnapshotError, match="identity_mismatch"):
            primary.read_manifest(object(), ("wrong", "CP", "CV"))
