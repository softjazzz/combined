"""PRIV002：合成整ORM→私有collector→实际worker病例/正式scope→attempt。"""
import ast
import asyncio
from copy import deepcopy
import json
import pickle
from types import SimpleNamespace

import pytest

from offline_support import (
    SERVICES, bind_execution_source, client_with_counters, load_bundle_runtime,
    load_identity_namespace, load_pure_privacy, load_repository_methods,
    load_worker_case_wrapper,
)


FIELDS = {
    "name": "合成原名甲", "mr_no": "MR-RAW-A", "inpat_no": "INPAT-RAW-A",
    "id_card_no": "CARD-RAW-A", "insurance_no": "INSURANCE-RAW-A",
    "contact_number": "PHONE-RAW-A", "contact_name": "合成联系人甲",
    "contact_address": "CONTACT-ADDRESS-RAW-A", "contact_telephone": "CONTACT-PHONE-RAW-A",
    "nativeplace": "NATIVE-ADDRESS-RAW-A", "currentaddress": "HOME-ADDRESS-RAW-A", "work_unit": "WORK-UNIT-RAW-A",
}


def orm(patient="P-A", **overrides):
    fields = dict(FIELDS, institute_id="I-A", patient_id=patient, visit_id="V-" + patient,
                  discharge_datetime=None, admission_datetime=None, discharge_dept_name="", admission_dept_name="", attending_physician_sign="保留医生甲", record_content="合成临床材料", drug_name="保留药品甲")
    fields.update(overrides)
    return SimpleNamespace(**fields)


def repository_case(*, main_rows=(), registration_rows=(), admission_rows=(), discharge_rows=()):
    cls, namespace = load_repository_methods()
    events = []
    class Query:
        def __init__(self, key, rows):
            self.key, self.rows = key, rows
        def filter(self, *args):
            return self
        def order_by(self, *args):
            return self
        def all(self):
            events.append(self.key)
            return list(self.rows)
    data = {"InpatRegistration": registration_rows, "AdmissionRecord": admission_rows, "DischargeRecord": discharge_rows}
    session = SimpleNamespace(query=lambda model: Query(model.__name__, data.get(model.__name__, ())), close=lambda: events.append("close"))
    repo = object.__new__(cls)
    repo._session_factory = lambda: session
    repo._build_records_query = lambda *args, **kwargs: Query("mr", main_rows)
    return repo, namespace, events


def collect(repo, *, sink=None, refs=None, ids=None):
    kwargs = dict(scope="all", department=None, doctor=None, date_field="admission", start_date=None, end_date=None, keyword=None, record_refs=refs, record_ids=ids)
    if sink is not None:
        kwargs["_private_identity_collector"] = sink
    return repo.collect_records(**kwargs)


@pytest.mark.parametrize("exact_anchors", [False, True])
def test_actual_repository_callback_preserves_record_contract_and_read_count(exact_anchors):
    identity = load_identity_namespace()
    source = orm()
    args = dict(registration_rows=[source], admission_rows=[orm(name="合成入院别名乙")]) if exact_anchors else dict(main_rows=[(source, None, None)])
    plain_repo, _, plain_events = repository_case(**args)
    private_repo, _, private_events = repository_case(**args)
    ref = identity["CaseRef"]("I-A", "P-A", "V-P-A")
    collector = identity["_Luxian0609IdentityCollector"]()
    plain = collect(plain_repo, refs=[ref])
    private = collect(private_repo, sink=collector.capture, refs=[ref])
    assert private == plain
    assert private_events == plain_events
    values = collector.provider_for_case(ref)()
    assert set(FIELDS.values()).issubset(values)
    assert "保留医生甲" not in values and "保留药品甲" not in values and "合成临床材料" not in values
    assert "CARD-RAW-A" not in json.dumps(private, ensure_ascii=False)
    assert not any(key.startswith("_private") for record in private for key in record)
    collector.close()


def test_legacy_visit_anchor_collection_does_not_key_identities_by_visit_alone():
    identity = load_identity_namespace()
    a = orm(visit_id="SAME-VISIT")
    b = orm("P-B", visit_id="SAME-VISIT", name="合成原名乙", mr_no="MR-RAW-B")
    repo, _, _ = repository_case(registration_rows=[a, b])
    collector = identity["_Luxian0609IdentityCollector"]()
    collect(repo, sink=collector.capture, ids=["SAME-VISIT"])
    values_a = collector.provider_for_case(identity["CaseRef"]("I-A", "P-A", "SAME-VISIT"))()
    values_b = collector.provider_for_case(identity["CaseRef"]("I-A", "P-B", "SAME-VISIT"))()
    assert "合成原名乙" not in values_a and "合成原名甲" not in values_b
    assert "MR-RAW-B" not in values_a
    collector.close()


def setup_worker_path(*, mode, text):
    identity = load_identity_namespace()
    privacy, scope = load_pure_privacy()
    source = orm()
    collector = identity["_Luxian0609IdentityCollector"]()
    repo, _, reads = repository_case(main_rows=[source])
    record = collect(repo, sink=collector.capture)[0]
    collector.capture_hydrated_record(record)
    client, events = client_with_counters(scope)
    cache = dict(scene="running", institute_id="I-A", patient_id="P-A", visit_id="V-P-A", patient_name_masked="合***", medical_text=text, structured_context={})
    original = deepcopy(cache)
    loads = []
    def cached_or_assembled(**kwargs):
        assert kwargs["force_refresh"] is False and kwargs["force_refresh_if_empty"] is True
        loads.append(mode)
        return deepcopy(cache)
    loader = load_bundle_runtime(cached_or_assembled)

    @scope.luxian_0609_privacy_scope
    async def formal(*, bundle, rule_set_key):
        wrapped = bind_execution_source(scope=scope, privacy=privacy, kwargs=dict(
            institute_id=bundle["institute_id"], patient_id=bundle["patient_id"], visit_id=bundle["visit_id"],
            evidence_payload={}, llm_client=client,
        ))
        assert wrapped is not client
        result, _ = await client._perform_observed_attempt(logical_call_id="offline", attempt_no=2, headers={}, payload={"messages": [{"content": bundle["medical_text"]}]})
        return {"results": result["choices"]}

    async def impl(record):
        loaded = loader(scene="running", institute_id=record["institute_id"], patient_id=record["patient_id"], visit_id=record["visit_id"])
        return await formal(bundle=loaded, rule_set_key="luxian_0609_qc_v1")
    worker = load_worker_case_wrapper(collector=collector, impl=impl)
    return worker, record, events, loads, collector, privacy, scope, cache, original, reads


@pytest.mark.parametrize("mode", ["hit", "miss"])
@pytest.mark.parametrize("field", sorted(FIELDS))
def test_collect_orm_to_actual_formal_attempt_blocks_unlabelled_raw_identity(mode, field):
    worker, record, events, loads, collector, privacy, scope, cache, original, reads = setup_worker_path(mode=mode, text="档案别称【" + FIELDS[field] + "】")
    with pytest.raises(privacy.PatientPrivacyViolation):
        asyncio.run(worker(record))
    assert events == [] and loads == [mode]
    assert reads == ["mr", "close"]
    assert cache == original
    assert scope.is_luxian_0609_privacy_scope_active() is False
    collector.close()


@pytest.mark.parametrize("mode", ["hit", "miss"])
def test_actual_formal_cache_path_sends_privacy_processed_normal_clinical_text(mode):
    worker, record, events, loads, collector, privacy, scope, cache, original, reads = setup_worker_path(mode=mode, text="患者姓名：合成原名甲；拟行甲手术，剂量130mg，复查1.5小时。")
    asyncio.run(worker(record))
    assert [kind for kind, _ in events] == ["observation", "capture", "transport"]
    text = events[-1][1]["messages"][0]["content"]
    assert "合成原名甲" not in text and "130mg" in text and "1.5小时" in text
    assert loads == [mode] and reads == ["mr", "close"]
    assert cache == original
    assert scope.is_luxian_0609_privacy_scope_active() is False
    collector.close()


@pytest.mark.parametrize("name", [None, "", "合***"])
def test_only_coordinates_or_masked_name_cannot_supply_raw_name_context(name):
    identity = load_identity_namespace()
    collector = identity["_Luxian0609IdentityCollector"]()
    collector.capture("mr", orm(name=name))
    with pytest.raises(identity["PrivacyIdentityContextUnavailable"]):
        collector.provider_for_case(identity["CaseRef"]("I-A", "P-A", "V-P-A"))()
    collector.close()


def test_collector_is_nonserialized_and_closed_provider_invalidates_without_raw_exception():
    identity = load_identity_namespace()
    collector = identity["_Luxian0609IdentityCollector"]()
    collector.capture("mr", orm())
    provider = collector.provider_for_case(identity["CaseRef"]("I-A", "P-A", "V-P-A"))
    assert "合成原名甲" in provider()
    assert "合成原名甲" not in repr(collector)
    with pytest.raises(TypeError):
        json.dumps(collector)
    with pytest.raises(identity["PrivacyIdentityContextUnavailable"]):
        pickle.dumps(collector)
    collector.close()
    assert collector._cases == {}
    with pytest.raises(identity["PrivacyIdentityContextUnavailable"]) as caught:
        provider()
    assert str(caught.value) == "LX0609 privacy identity context unavailable"


@pytest.mark.parametrize("bad", ["wrong_ref", "missing_ref", "bad_scalar"])
def test_missing_mismatched_or_invalid_collected_identity_fails_closed(bad):
    identity = load_identity_namespace()
    collector = identity["_Luxian0609IdentityCollector"]()
    source = orm(contact_name={} if bad == "bad_scalar" else "合成联系人甲", patient_id="" if bad == "missing_ref" else "P-A")
    collector.capture("mr", source)
    ref = identity["CaseRef"]("I-A", "P-B" if bad == "wrong_ref" else "P-A", "V-P-A")
    with pytest.raises(identity["PrivacyIdentityContextUnavailable"]):
        collector.provider_for_case(ref)()
    collector.close()


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_worker_request_actual_finally_clears_collector_after_case_error(failure):
    identity = load_identity_namespace()
    _, scope = load_pure_privacy()
    collector = identity["_Luxian0609IdentityCollector"]()
    source = orm()
    collector.capture("mr", source)
    async def impl(record):
        raise failure("合成固定错误")
    worker = load_worker_case_wrapper(collector=collector, impl=impl)
    with pytest.raises(failure):
        asyncio.run(worker({"institute_id": "I-A", "patient_id": "P-A", "visit_id": "V-P-A"}))
    assert scope.is_luxian_0609_privacy_scope_active() is False
    tree = ast.parse((SERVICES / "sichuan_workspace_batch_worker.py").read_text(encoding="utf-8"))
    job = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_sichuan_workspace_batch_job")
    finally_body = next(node.finalbody for node in job.body if isinstance(node, ast.Try))
    exec(compile(ast.Module(body=finally_body, type_ignores=[]), "actual-worker-finally", "exec"), {"identity_collector": collector, "lease_stop": None})
    assert collector._cases == {} and collector._active is False


@pytest.mark.parametrize("mode", ["hit", "miss"])
@pytest.mark.parametrize("bad", ["wrong_ref", "missing_ref"])
def test_actual_formal_nested_case_mismatch_cannot_fall_back_to_three_ids(mode, bad):
    worker, record, events, loads, collector, privacy, scope, cache, original, reads = setup_worker_path(mode=mode, text="合成无身份临床材料")
    if bad == "wrong_ref":
        cache["patient_id"] = "P-B"
    else:
        cache["visit_id"] = ""
    with pytest.raises(privacy.PrivacyIdentityContextError):
        asyncio.run(worker(record))
    assert events == []
    assert scope.is_luxian_0609_privacy_scope_active() is False
    collector.close()


@pytest.mark.parametrize("normal", [False, True])
def test_concurrent_worker_cases_share_collector_but_never_provider_identity(normal):
    identity = load_identity_namespace()
    privacy, scope = load_pure_privacy()
    collector = identity["_Luxian0609IdentityCollector"]()
    rows = [orm(), orm("P-B", **{key: value.replace("A", "B").replace("甲", "乙") for key, value in FIELDS.items()})]
    for row in rows:
        collector.capture("mr", row)
    client, events = client_with_counters(scope)

    @scope.luxian_0609_privacy_scope
    async def formal(*, bundle, rule_set_key):
        bind_execution_source(scope=scope, privacy=privacy, kwargs=dict(institute_id=bundle["institute_id"], patient_id=bundle["patient_id"], visit_id=bundle["visit_id"], evidence_payload={}, llm_client=client))
        if normal:
            await client._perform_observed_attempt(logical_call_id="offline", attempt_no=1, headers={}, payload={"messages": [{"content": "患者姓名：" + bundle["synthetic_name"] + "；拟行甲手术。"}]})
        else:
            with pytest.raises(privacy.PatientPrivacyViolation):
                await client._perform_observed_attempt(logical_call_id="offline", attempt_no=1, headers={}, payload={"messages": [{"content": "档案别称【" + bundle["synthetic_name"] + "】"}]})
        return {}

    async def impl(record):
        await asyncio.sleep(0)
        return await formal(bundle={**record, "synthetic_name": record["patient_name"]}, rule_set_key="luxian_0609_qc_v1")
    worker = load_worker_case_wrapper(collector=collector, impl=impl)
    async def concurrent():
        await asyncio.gather(*(worker({"institute_id": row.institute_id, "patient_id": row.patient_id, "visit_id": row.visit_id, "patient_name": row.name}) for row in rows))
    asyncio.run(concurrent())
    assert [kind for kind, _ in events] == (["observation", "capture", "transport"] * 2 if normal else [])
    assert "合成原名甲" not in json.dumps(events, ensure_ascii=False) and "合成原名乙" not in json.dumps(events, ensure_ascii=False)
    assert scope.is_luxian_0609_privacy_scope_active() is False
    collector.close()


def test_closed_worker_collector_is_not_replaced_by_formal_new_material_provider():
    worker, record, events, loads, collector, privacy, scope, cache, original, reads = setup_worker_path(mode="hit", text="合成无身份材料")
    collector.close()
    with pytest.raises(privacy.PrivacyIdentityContextError):
        asyncio.run(worker(record))
    assert events == []
    assert scope.is_luxian_0609_privacy_scope_active() is False


@pytest.mark.parametrize("bad", ["wrong_ref", "missing_ref"])
def test_execution_binding_must_match_worker_source_even_in_legacy_compat_call(bad):
    identity = load_identity_namespace()
    privacy, scope = load_pure_privacy()
    collector = identity["_Luxian0609IdentityCollector"]()
    collector.capture("mr", orm())
    client, events = client_with_counters(scope)
    with scope.luxian_0609_case_identity_scope(case_coordinates=("I-A", "P-A", "V-P-A"), identity_provider=collector.provider_for_case(identity["CaseRef"]("I-A", "P-A", "V-P-A"))):
        bind_execution_source(scope=scope, privacy=privacy, kwargs=dict(institute_id="I-A", patient_id="P-B" if bad == "wrong_ref" else "P-A", visit_id="" if bad == "missing_ref" else "V-P-A", evidence_payload={}, llm_client=client))
        with pytest.raises(privacy.PrivacyIdentityContextError):
            asyncio.run(client._perform_observed_attempt(logical_call_id="offline", attempt_no=1, headers={}, payload={"messages": [{"content": "合成无身份材料"}]}))
    assert events == []
    collector.close()
