"""一个事件未决不能抹掉另一事件独立成立的确定缺陷（03-01-04、05-02-01、06-04-02）。

只用合成材料与固定应答；混合场景经正式执行器、Binding、Finalizer，并以内存 SQLite 真实保存读回。
"""

import pytest

from test_luxian_0609_death_record_timeliness import saved_roundtrip


def _loaded(result):
    loaded = saved_roundtrip(result)
    assert (loaded["status"], loaded["reason_code"]) == (result["status"], result["reason_code"])
    assert loaded.get("customer_display_facts") == result.get("customer_display_facts")
    assert loaded.get("findings") == result.get("findings")
    return loaded


# ---------- 06-04-02 危急值处置记录 ----------
REPORT_B = {"test_id": "REPORT-B", "item_name": "血钠", "abnormal_indicator": "PL",
            "report_time": "2026-06-01 14:00:00"}


async def _060402(records):
    from test_luxian_0609_critical_value_disposition_time import evaluate

    *_, canonical = await evaluate(records, (REPORT_B,))
    return next(item for item in canonical if item["rule_id"] == "LX0609-06-04-02")


def _outcomes(result):
    return {
        tuple(event["critical_item_names"]): event["outcome"]
        for event in result["customer_display_facts"]["event_results"]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("pending_key", ["REPORT-A", "REPORT-B"], ids=["A_pending", "B_pending"])
async def test_060402_unhandled_report_not_masked_by_other_report_time_gap(pending_key):
    from test_luxian_0609_critical_value_disposition_time import disposition

    result = await _060402([disposition(None, pending_key)])
    loaded = _loaded(result)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "required_document_missing")
    unhandled = ("血钠",) if pending_key == "REPORT-A" else ("血钾",)
    pending = ("血钾",) if pending_key == "REPORT-A" else ("血钠",)
    assert _outcomes(result) == {unhandled: "unhandled", pending: "authoritative_time_missing"}
    # 缺陷清单只列确定未处置的报告；时间待核的报告单列，不写成未处置。
    assert result["findings"].startswith("已确认问题：" + unhandled[0] + "：报告后未找到对应处置记录。")
    assert pending[0] + "的处置时间缺失或无法解析" in result["findings"]
    assert pending[0] + "：报告后未找到" not in result["findings"]


@pytest.mark.asyncio
async def test_060402_only_time_gaps_remain_data_gap():
    from test_luxian_0609_critical_value_disposition_time import disposition

    result = await _060402([disposition(None, "REPORT-A"), disposition(None, "REPORT-B")])
    assert (_loaded(result)["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_060402_handled_report_kept_beside_unhandled():
    from test_luxian_0609_critical_value_disposition_time import disposition

    result = await _060402([disposition("2026-06-01 15:00:00", "REPORT-A")])
    assert _loaded(result)["status"] == "non_compliant"
    assert _outcomes(result) == {("血钾",): "handled", ("血钠",): "unhandled"}


# ---------- 03-01-04 会诊建议执行核查 ----------
import json


class _ConsultClient:
    """按请求类型应答：第一阶段（会诊文书）用夹具建议，第二阶段（建议列表）如实答无执行证据。

    未知请求明确失败，不以同一成功应答掩盖夹具错误。
    """

    def __init__(self, payload):
        self.payload = payload
        self.stage_two_refs = []

    async def generate(self, prompt, **kwargs):
        from test_luxian_0609_native_consultation_episode_execution import (
            _materialize_recommendation_quotes,
        )

        body = json.loads(prompt.rsplit("输入：", 1)[1])
        if "consultation_documents" in body:
            payload = _materialize_recommendation_quotes(self.payload, prompt)
        elif "recommendations" in body:
            assert body.get("candidate_documents"), "第二阶段必须带有可比对的候选"
            self.stage_two_refs.extend(item["recommendation_ref"] for item in body["recommendations"])
            payload = {"executions": [
                {"recommendation_ref": item["recommendation_ref"], "execution_state": "absent",
                 "structured_action_refs": [], "execution_record_state": "no_trace", "trace_refs": [],
                 "confidence": "high", "recommendation_coverage_state": "no_trace",
                 "coverage_confidence": "high", "uncovered_source_quotes": []}
                for item in body["recommendations"]
            ]}
        else:
            raise AssertionError("未知请求类型：" + ",".join(sorted(body)))
        return {"content": json.dumps(payload, ensure_ascii=False),
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}


def _consult_case(specs):
    """specs：按文书行顺序给出 (会诊标签, 意见时间)；编号按材料实际顺序分配。"""
    from test_luxian_0609_native_consultation_episode_execution import _episode, _payload, _window_session

    rows, episodes, refs_by_label = [], [], {}
    for position, (label, time) in enumerate(specs, start=1):
        ref = f"consultation_record-{position}"
        refs_by_label[label] = ref
        quotes = [f"复查合成指标{label}{n}" for n in (1, 2)]
        row = {"document_id": f"synthetic-opinion-{label}", "record_content": "会诊意见：" + "；".join(quotes)}
        if time:
            row["record_time"] = time
        rows.append(row)
        episodes.append(_episode(ref, [ref], application="absent", recommendations=[
            {"recommendation_ref": f"{ref}#r{n}", "action_type": "test", "source_quote": q,
             "normalized_action": q, "opinion_ref": ref}
            for n, q in enumerate(quotes, 1)
        ]))
    session = _window_session(rows_by_source={
        "consultation_record": rows,
        "daily_course_record": [{"document_id": "synthetic-course-1", "record_time": "2026-07-02 10:00:00",
                                 "document_title": "日常病程记录", "record_content": "患者一般情况可，继续观察。"}],
        # 会诊后确有医嘱候选，但与建议无关：否定来自完整比对，而非本地没有候选。
        "inpat_nondrug_order": [{"order_id": "synthetic-order-1", "order_name": "更换伤口敷料",
                                 "prescribed_datetime": "2026-07-01 12:00:00"}],
    })
    return session, _payload(episodes=episodes), refs_by_label


async def _030104(specs, tmp_path, monkeypatch):
    from app.services.luxian_0609 import native_consultation_episode_execution as episode
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

    for key in ("LUXIAN_0609_OPINION_FREEZE_DIR", "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR"):
        monkeypatch.setenv(key, str(tmp_path / key))
    session, payload, refs = _consult_case(specs)
    client = _ConsultClient(payload)
    rules = ("LX0609-03-01-01", "LX0609-03-01-04")
    raw = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=rules, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        opinion_freeze_dir=tmp_path / "opinion", decision_rule_ids=rules,
    )
    reduced = {
        item.rule_id: item for item in bind_and_reduce_luxian_0609_rule_decisions(
            decisions=raw.decisions, expected_rule_ids=rules,
            snapshot=session.snapshot, evidence_materials=session.materials,
        )
    }
    finals = {
        rule: finalize_luxian_0609_reduced_customer_result(
            decision=reduced[rule], raw_customer_display_facts=dict(raw.customer_display_facts).get(rule),
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
        for rule in rules
    }
    return finals, client, refs


@pytest.mark.asyncio
@pytest.mark.parametrize("specs", [
    [("A", "2026-07-01 09:00:00"), ("B", None)],
    [("B", None), ("A", "2026-07-01 09:00:00")],
], ids=["reliable_first", "untimed_first"])
async def test_030104_reliable_absent_not_masked_by_untimed_opinion(specs, tmp_path, monkeypatch):
    finals, client, refs = await _030104(specs, tmp_path, monkeypatch)
    final = finals["LX0609-03-01-04"]
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "requirement_violated")
    # 会诊 A 的每条建议都经第二阶段完整比对；未决会诊 B 不进入核查，也不列为未执行。
    assert sorted(client.stage_two_refs) == [f"{refs['A']}#r1", f"{refs['A']}#r2"]
    assert "合成指标B" not in json.dumps(final.get("customer_display_facts"), ensure_ascii=False)
    assert final["customer_display_facts"]["unresolved_opinion_episode_count"] == 1
    assert "另有1次会诊的意见时间缺失或不在本次住院期间，暂未核查" in final["findings"]
    assert "合成指标B" not in final["findings"]
    # 020 不在本轮范围：维持原有的关联未决。
    assert finals["LX0609-03-01-01"]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_030104_reliable_only_control(tmp_path, monkeypatch):
    finals, client, refs = await _030104([("A", "2026-07-01 09:00:00")], tmp_path, monkeypatch)
    assert _loaded(finals["LX0609-03-01-04"])["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_030104_only_untimed_opinion_stays_unresolved(tmp_path, monkeypatch):
    finals, client, _ = await _030104([("B", None)], tmp_path, monkeypatch)
    final = finals["LX0609-03-01-04"]
    assert (_loaded(final)["status"], final["reason_code"]) == ("data_gap", "linkage_unresolved")
    assert client.stage_two_refs == []



# ---------- 05-02-01 化疗医嘱与病程一致性 ----------
CHEMO_DAY = "2026-04-26"
OX_MISMATCH = f"{CHEMO_DAY} 使用奥沙利铂120mg 静滴。"
OX_MIXED = f"{CHEMO_DAY} 使用奥沙利铂120mg 静滴。拟明日使用顺铂40mg 静滴。"


def _cis(**changes):
    from test_luxian_0609_chemo_closure import ORDER

    return {**ORDER, "document_id": "synthetic-cis-order", "generic_name": "顺铂",
            "single_dose": "40", "single_dose_unit": "mg", **changes}


async def _050201(body, orders, annotations=None):
    from test_luxian_0609_chemo_closure import _course, _run

    _, _, final = await _run(_course(body), orders=orders, annotations=annotations)
    return final


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
@pytest.mark.parametrize("case", ["pending_order", "planned_course"])
async def test_050201_confirmed_dose_mismatch_not_masked_by_unresolved_event(case, reverse):
    from chemotherapy_administration_test_support import fact
    from test_luxian_0609_chemo_closure import ORDER

    if case == "pending_order":
        orders, body, annotations = [ORDER, _cis(order_status="拟执行")], OX_MISMATCH, None
    else:
        orders, body = [ORDER, _cis()], OX_MIXED
        annotations = {OX_MIXED: (
            fact(f"{CHEMO_DAY} 使用奥沙利铂120mg 静滴", dose="120mg", route="静滴", date=CHEMO_DAY, target=0),
            fact("拟明日使用顺铂40mg 静滴", action="planned", drug="顺铂", dose="40mg", route="静滴", target=1),
        )}
    if reverse:
        orders.reverse()
        if annotations:
            # 目标编号随医嘱顺序变化。
            annotations = {OX_MIXED: tuple({**item, "target": 1 - item["target"]} for item in annotations[OX_MIXED])}
    final = await _050201(body, orders, annotations)
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "requirement_violated")
    facts = final["customer_display_facts"]
    assert facts["field_results"]["dose"] == "mismatched"
    assert facts["confirmed_mismatch_event_count"] == 1 and facts["unresolved_event_count"] == 1
    # 已确认缺陷只列剂量；顺铂相关项只列为尚无法核对，不列为不一致。
    assert "剂量记录不一致；" in final["findings"]
    assert "尚无法核对" in final["findings"]
    assert "药物名称记录不一致" not in final["findings"] and "用药时间记录不一致" not in final["findings"]


@pytest.mark.asyncio
async def test_050201_single_confirmed_mismatch_control():
    from test_luxian_0609_chemo_closure import ORDER

    final = await _050201(OX_MISMATCH, [ORDER])
    assert (_loaded(final)["status"], final["reason_code"]) == ("non_compliant", "requirement_violated")


@pytest.mark.asyncio
async def test_050201_only_pending_order_stays_data_gap():
    final = await _050201(f"{CHEMO_DAY} 患者一般情况可。", [_cis(order_status="拟执行")])
    assert _loaded(final)["status"] == "data_gap"


@pytest.mark.asyncio
async def test_050201_mismatch_on_untimed_administration_is_not_independent():
    """有不一致的那次给药本身时间未核实时，不能借此越过另一未决事件判缺陷。"""
    from test_luxian_0609_chemo_closure import ORDER

    final = await _050201("使用奥沙利铂120mg 静滴。", [ORDER, _cis(order_status="拟执行")])
    assert _loaded(final)["status"] == "data_gap"


# ---------- 复核补充：06-04-02 另一报告危急值标志冲突 ----------
REPORT_A = {"test_id": "REPORT-A", "item_name": "血钾", "abnormal_indicator": "PH",
            "report_time": "2026-06-01 14:00:00"}
CONFLICT_B = {"test_id": "REPORT-B", "item_name": "血钠", "abnormal_indicator": "PL", "result_flag": "PH",
              "report_time": "2026-06-01 14:00:00"}
HANDLED_C = {"test_id": "REPORT-C", "item_name": "血糖", "abnormal_indicator": "PL",
             "report_time": "2026-06-01 14:00:00"}


async def _060402_rows(items, records, monkeypatch, tmp_path):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected

    for key in ("LUXIAN_0609_OPINION_FREEZE_DIR", "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR",
                "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"):
        monkeypatch.setenv(key, str(tmp_path / key))
    rule = "LX0609-06-04-02"
    rows = {"labtest_item_report": tuple(items), "crisis_value_record": tuple(records),
            "evaluation_context.horizon": ({"horizon_datetime": "2026-06-02 12:00:00", "basis": "evaluation_as_of"},)}
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), rows)
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict_first", [False, True], ids=["A_first", "B_first"])
async def test_060402_unhandled_not_masked_by_other_report_flag_conflict(conflict_first, monkeypatch, tmp_path):
    items = [CONFLICT_B, REPORT_A] if conflict_first else [REPORT_A, CONFLICT_B]
    final = await _060402_rows(items, (), monkeypatch, tmp_path)
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "required_document_missing")
    facts = final["customer_display_facts"]
    assert [(e["critical_item_names"], e["outcome"]) for e in facts["event_results"]] == [(["血钾"], "unhandled")]
    # 冲突报告只列为待核，不任取标志，不列为未处置。
    assert facts["report_time_gaps"] == [
        {"critical_item_names": ["血钠"], "critical_flags": [], "issue": "critical_flag_conflict"}
    ]
    assert "血钠的危急值标志冲突" in final["findings"]
    assert "血钠：报告后未找到" not in final["findings"]


@pytest.mark.asyncio
async def test_060402_handled_report_kept_beside_unhandled_and_flag_conflict(monkeypatch, tmp_path):
    from test_luxian_0609_critical_value_disposition_time import disposition

    final = await _060402_rows([REPORT_A, CONFLICT_B, HANDLED_C],
                               (disposition("2026-06-01 15:00:00", "REPORT-C"),), monkeypatch, tmp_path)
    assert _loaded(final)["status"] == "non_compliant"
    outcomes = {tuple(e["critical_item_names"]): e["outcome"] for e in final["customer_display_facts"]["event_results"]}
    assert outcomes == {("血钾",): "unhandled", ("血糖",): "handled"}


@pytest.mark.asyncio
async def test_060402_only_flag_conflict_report_is_not_a_defect(monkeypatch, tmp_path):
    final = await _060402_rows([CONFLICT_B], (), monkeypatch, tmp_path)
    assert (_loaded(final)["status"], final["reason_code"]) == ("data_gap", "required_field_missing")


# ---------- 复核补充：05-02-01 未决事件的字段差异不混入确定缺陷 ----------
CIS_ORAL_UNDATED = "使用顺铂40mg 口服"


def _mixed_route_case(reverse, *, ox_route="静滴"):
    from chemotherapy_administration_test_support import fact
    from test_luxian_0609_chemo_closure import ORDER

    ox_quote = f"{CHEMO_DAY} 使用奥沙利铂120mg {ox_route}"
    body = ox_quote + "。" + CIS_ORAL_UNDATED + "。"
    orders = [ORDER, _cis()]
    if reverse:
        orders.reverse()
    annotations = {body: (
        fact(ox_quote, dose="120mg", route=ox_route, date=CHEMO_DAY, target=1 if reverse else 0),
        fact(CIS_ORAL_UNDATED, drug="顺铂", dose="40mg", route="口服", target=0 if reverse else 1),
    )}
    return body, orders, annotations


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
async def test_050201_unconfirmed_route_difference_not_published_as_defect(reverse):
    final = await _050201(*_mixed_route_case(reverse))
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "requirement_violated")
    fields = final["customer_display_facts"]["field_results"]
    assert (fields["dose"], fields["route"]) == ("mismatched", "unknown")
    assert final["customer_display_facts"]["confirmed_mismatch_event_count"] == 1
    assert "剂量记录不一致；" in final["findings"] and "使用方法记录不一致" not in final["findings"]
    assert "剂量、使用方法记录不一致" not in final["findings"]


@pytest.mark.asyncio
async def test_050201_confirmed_route_defect_kept_beside_undated_event():
    final = await _050201(*_mixed_route_case(False, ox_route="口服"))
    fields = _loaded(final)["customer_display_facts"]["field_results"]
    assert final["status"] == "non_compliant"
    assert (fields["dose"], fields["route"]) == ("mismatched", "mismatched")


@pytest.mark.asyncio
async def test_050201_only_undated_route_difference_stays_data_gap():
    from chemotherapy_administration_test_support import fact

    body = CIS_ORAL_UNDATED + "。"
    annotations = {body: (fact(CIS_ORAL_UNDATED, drug="顺铂", dose="40mg", route="口服", target=0),)}
    final = await _050201(body, [_cis()], annotations)
    assert _loaded(final)["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
async def test_050201_missing_order_cannot_promote_undated_route_difference(reverse):
    from chemotherapy_administration_test_support import fact
    from test_luxian_0609_chemo_closure import ORDER

    orders = [ORDER | {"single_dose_unit": ""}, _cis()]
    if reverse:
        orders.reverse()
    body = CIS_ORAL_UNDATED + "。"
    annotations = {body: (fact(CIS_ORAL_UNDATED, drug="顺铂", dose="40mg", route="口服",
                               target=0 if reverse else 1),)}
    final = await _050201(body, orders, annotations)
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("data_gap", "required_field_missing")
    facts = loaded["customer_display_facts"]
    assert facts["confirmed_mismatch_event_count"] == facts["missing_course_event_count"] == 0
    assert facts["unknown_time_event_count"] == facts["missing_order_event_count"] == 1
    assert set(facts["field_results"].values()) == {"unknown"}
    assert "记录不一致" not in loaded["findings"]
    assert "尚无法核对" in loaded["findings"]
    assert len(loaded["evidence"]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
@pytest.mark.parametrize("ox_route", ["静滴", "口服"])
async def test_050201_missing_order_keeps_only_confirmed_fields_and_success(reverse, ox_route):
    from chemotherapy_administration_test_support import fact
    from test_luxian_0609_chemo_closure import ORDER

    partial = {**ORDER, "document_id": "synthetic-partial-taxol", "generic_name": "紫杉醇",
               "single_dose_unit": ""}
    success = {**ORDER, "document_id": "synthetic-success-docetaxel", "generic_name": "多西他赛"}
    orders = [ORDER, _cis(), partial, success]
    if reverse:
        orders.reverse()
    targets = {row["generic_name"]: index for index, row in enumerate(orders)}
    ox_quote = f"{CHEMO_DAY} 使用奥沙利铂120mg {ox_route}"
    success_quote = f"{CHEMO_DAY} 使用多西他赛130mg 静滴"
    body = "。".join((ox_quote, CIS_ORAL_UNDATED, success_quote)) + "。"
    annotations = {body: (
        fact(ox_quote, dose="120mg", route=ox_route, date=CHEMO_DAY, target=targets["奥沙利铂"]),
        fact(CIS_ORAL_UNDATED, drug="顺铂", dose="40mg", route="口服", target=targets["顺铂"]),
        fact(success_quote, drug="多西他赛", dose="130mg", route="静滴", date=CHEMO_DAY,
             target=targets["多西他赛"]),
    )}
    final = await _050201(body, orders, annotations)
    loaded = _loaded(final)
    assert (loaded["status"], loaded["reason_code"]) == ("non_compliant", "requirement_violated")
    facts = loaded["customer_display_facts"]
    assert facts["order_count"] == 4
    assert facts["confirmed_mismatch_event_count"] == facts["unknown_time_event_count"] == 1
    assert facts["missing_order_event_count"] == 1
    assert facts["missing_course_event_count"] == facts["unresolved_event_count"] == 0
    # 成功事件仍完成比较：不混入缺陷、未记录或未决计数，证据保持可定位。
    assert {ref["source_document_id"] for ref in final["customer_evidence"]} == {
        "synthetic-chemo-order", "synthetic-cis-order", "synthetic-partial-taxol",
        "synthetic-success-docetaxel", "synthetic-chemo-course",
    }
    from app.services.qc_workspace.canonical_result_store import keyed_ref
    assert {ref["source_ref"] for ref in loaded["evidence"]} == {
        keyed_ref("src", ref["source_document_id"], hmac_key="synthetic-death-test-key")
        for ref in final["customer_evidence"]
    }
    assert facts["field_results"] == {
        "drug_name": "unknown", "dose": "mismatched",
        "route": "mismatched" if ox_route == "口服" else "unknown", "time": "unknown",
    }
    assert "剂量" in loaded["findings"] and "记录不一致" in loaded["findings"]
    assert ("使用方法记录不一致" in loaded["findings"]) is (ox_route == "口服")


# ---------- 复核补充：05-02-01 拟执行医嘱不改写其他医嘱的技术失败 ----------
@pytest.mark.asyncio
@pytest.mark.parametrize("with_pending", [False, True], ids=["active_only", "with_pending"])
async def test_050201_model_failure_stays_technical_with_or_without_pending(with_pending, monkeypatch):
    import chemotherapy_administration_test_support as support
    from test_luxian_0609_chemo_closure import ORDER, _course, _run

    async def timeout(*_args, **_kwargs):
        raise TimeoutError("synthetic transport timeout")

    monkeypatch.setattr(support.FrozenChemotherapyAdministrationClient, "generate", timeout)
    orders = [ORDER, _cis(order_status="拟执行")] if with_pending else [ORDER]
    _execution, reduced, final = await _run(_course(f"{CHEMO_DAY} 使用奥沙利铂130mg 静滴。"), orders=orders)
    assert reduced.final_state.value == final["status"] == "technical_error"
    assert final["reason_code"] != "required_field_missing"
    # 技术失败走失败通道：不能作为可交付结果保存成临床资料不足。
    with pytest.raises(ValueError):
        saved_roundtrip(final)
