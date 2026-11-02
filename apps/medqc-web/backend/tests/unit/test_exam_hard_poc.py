"""难例入口及预先固定的答案；此文件只在严格offline下运行。"""

import json
from dataclasses import asdict
import os
from pathlib import Path

import httpx
import pytest

from app.services.luxian_0609 import exam_result_record_check as check
from scripts.exam_hard_cases import hard_cases, planned_runs, score_attempt
from scripts.exam_poc_acceptance import inspect_completion
from scripts.run_bailian_exam_hard_poc import execution_summary, main, summarize
from scripts.run_bailian_exam_poc import BailianPocTransport, MODELS
from tests.unit.test_exam_result_model_route import response
from tests.unit.test_exam_poc_acceptance import formal_replay
from tests.unit.test_luxian_0609_native_exam_lab_execution import _fact_response


def fixed_completion(case):
    p = case.projection()
    expected = case.expected_kinds(p)
    targets = check._targets(p)
    docs = []
    for (position, ref), kind in expected.items():
        text = check._course_text(p, ref)
        docs.append({"event_position": position, "course_doc_ref": ref,
                     "quote_type": "none" if case.guard_only else kind,
                     "quote": text[-60:] if kind in check.SPAN_TYPES and not case.guard_only else "",
                     "report_span": targets[position][0][:190] if kind in check.SPAN_TYPES and not case.guard_only else ""})
    return response({"schema_version": check.SCHEMA_VERSION, "docs": docs})


def test_catalog_gold_and_visible_inputs_are_fixed_before_live_calls():
    cases = tuple(hard_cases())
    assert len(cases) == 7 and sum(not c.guard_only for c in cases) == 6
    assert len(list(planned_runs())) == 26
    for case in cases:
        p = case.projection()
        expected = case.expected_kinds(p)
        assert not check._verbatim_confirmed(p, check._targets(p)), case.name
        audit = inspect_completion(p, fixed_completion(case), expected_kinds=expected, source_rows=case.rows())
        score = score_attempt(audit, expected, guard_only=case.guard_only)
        assert audit["protocol_valid"], (case.name, audit)
        if case.guard_only:
            assert not audit["coverage_complete"] and audit["incomplete_event_positions"] == [1]
        else:
            assert audit["coverage_complete"] and not score["category_mismatches"] and not score["conflict_mismatches"]
        if case.name == "long_readable_tail":
            assert audit["input_projection_complete"] is True
        runs = [(round_number, arm) for c, round_number, arm in planned_runs() if c.name == case.name]
        if not case.guard_only:
            assert runs[0][1] != runs[2][1]


def test_preview_does_not_read_env_and_real_flag_cannot_escape_offline(tmp_path, capsys):
    assert main(["--env-file", "absent.env"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["planned_arms"] == 26 and preview["max_http_calls"] == 32 and preview["http_calls"] == 0
    path = tmp_path / "backend.env"
    path.write_text("DASHSCOPE_API_KEY=synthetic-never-output\n", encoding="utf-8")
    assert main(["--run-real", "--source-commit", "a" * 40, "--env-file", str(path)]) == 2
    assert "synthetic-never-output" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_explicit_hard_bound_is_finite_and_keeps_original_twelve_default():
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    transport = BailianPocTransport(endpoint, max_requests=32,
        inner=httpx.MockTransport(lambda _: httpx.Response(200, json={"model": MODELS[0], "choices": []})))
    body = {"model": MODELS[0], "messages": [{"role": "user", "content": "synthetic"}],
            "enable_thinking": False, "stream": False, "max_tokens": 4096}
    for _ in range(32):
        await transport.handle_async_request(httpx.Request("POST", endpoint, json=body))
    with pytest.raises(RuntimeError):
        await transport.handle_async_request(httpx.Request("POST", endpoint, json=body))
    for bound in (0, 33, True):
        with pytest.raises(ValueError):
            BailianPocTransport(endpoint, max_requests=bound)
    assert BailianPocTransport(endpoint).max_requests == 12


def test_reference_recovery_does_not_hide_candidate_failure_or_count_guard_as_candidate_quality():
    p = next(hard_cases()).projection()
    bad = inspect_completion(p, response({"schema_version": check.SCHEMA_VERSION, "docs": []}))
    score = score_attempt(bad, {(1, "D06-01"): "result_conflicting"})
    report = {"results": [
        {"guard_only": False, "first_model": MODELS[1], "attempts": [{"score": score}, {"score": {}}]},
        {"guard_only": True, "first_model": MODELS[0], "attempts": [{"score": score}]},
    ]}
    result = summarize(report)
    assert result[MODELS[1]]["runs"] == 1 and result[MODELS[1]]["protocol_failures"] == 1
    assert result[MODELS[0]]["runs"] == 0


def test_failed_last_guard_does_not_report_execution_complete():
    report = {"results": [{"state": "ready"} for _ in range(26)],
              "requests": [{"status": "success", "http_status": 200} for _ in range(26)],
              "gateway_clean_shutdown": True}
    assert execution_summary(report)["complete"] is True
    report["requests"][-1] = {"status": "failed", "error_type": "ConnectError"}
    report["results"][-1]["state"] = "failed"
    report["gateway_clean_shutdown"] = False
    result = execution_summary(report)
    assert result["all_arms_attempted"] is True and result["complete"] is False
    assert result["successful_http_calls"] == 25 and result["failed_http_calls"] == 1


@pytest.mark.asyncio
async def test_hard_offline_save(monkeypatch, tmp_path):
    requests, results = [], []
    for case, round_number, arm in planned_runs():
        model = MODELS[0] if arm == "reference" or case.guard_only else MODELS[1]
        completion = {**fixed_completion(case), "model": model}
        results.append({"case": case.name, "round": round_number, "arm": arm, "request_start": len(requests),
                        "http_calls": 1, "state": "ready", "incomplete_event_positions": [1] if case.guard_only else []})
        requests.append({"case": case.name, "round": round_number, "arm": arm, "attempt": 1,
                         "model": model, "returned_model": model, "completion": completion, "enable_thinking_sent": False})
    source, output = tmp_path / "source.json", tmp_path / "replay.json"
    source.write_text(json.dumps({"schema_version": "bailian-hard-poc-v1", "source_commit": "a" * 40,
        "synthetic_only": True, "models": MODELS, "database_writes": 0,
        "catalog": [asdict(case) for case in hard_cases()], "results": results, "requests": requests}), encoding="utf-8")
    monkeypatch.setenv("MEDQC_EXAM_POC_ARTIFACT", str(source))
    monkeypatch.setenv("MEDQC_EXAM_POC_REPORT", str(output))
    await test_existing_hard_recording_formal_chain(monkeypatch, tmp_path / "s")
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(report["rows"]) == 26 and report["integrity_failures"] == report["clinical_direction_mismatches"] == 0


@pytest.mark.asyncio
async def test_existing_hard_recording_formal_chain(monkeypatch, tmp_path):
    source = os.environ.get("MEDQC_EXAM_POC_ARTIFACT")
    if not source:
        pytest.skip("仅显式传入原报告时重放真实合成难例；CI不持有private报告")
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    cases = {case.name: case for case in hard_cases()}
    assert payload["schema_version"] == "bailian-hard-poc-v1" and payload["synthetic_only"] is True
    assert payload["models"] == list(MODELS) and payload["database_writes"] == 0
    assert payload["catalog"] == json.loads(json.dumps([asdict(case) for case in cases.values()]))
    assert len(payload["requests"]) <= 32
    plan = list(planned_runs())
    rows, offset = [], 0
    for index, result in enumerate(payload["results"]):
        case, round_number, arm = plan[index]
        assert (result["case"], result["round"], result["arm"]) == (case.name, round_number, arm)
        assert result["request_start"] == offset
        requests = payload["requests"][offset:offset + result["http_calls"]]
        assert len(requests) == result["http_calls"] and requests
        offset += len(requests)
        for attempt, request in enumerate(requests, 1):
            assert (request["case"], request["round"], request["arm"], request["attempt"]) == (case.name, round_number, arm, attempt)
            assert request["model"] in MODELS and request["enable_thinking_sent"] is False
            if "completion" in request:
                assert request["returned_model"] == request["model"] == request["completion"]["model"]
        item = {"case": case.name, "round": round_number, "arm": arm}
        if any("completion" not in request for request in requests):
            rows.append({**item, "replay_available": False, "reason": "incomplete_http_recording"})
            continue
        main = None
        if len(case.rows()["exam_master"]) > 1:
            main = {"schema_version": "lx0609-exam-lab-text-facts-v4", "facts": [
                {**_fact_response((check.RULE_ID,))["facts"][0], "event_position": position,
                 "course_doc_positions": [position]} for position in (1, 2)]}
        with monkeypatch.context() as patch:
            try:
                replay = await formal_replay(patch, tmp_path / str(index), case=case, recordings=requests,
                    arm=arm, mature=True, main_payload=main,
                    allow_incomplete=bool(result["incomplete_event_positions"]) or result["state"] != "ready",
                    specialty_targets=["candidate.test" if r["model"] == MODELS[1] else "reference.test" for r in requests])
                expected = "compliant" if all(any(kind == "result_recorded" for p, _, kind in case.gold if p == position)
                    for position in {p for p, _, _ in case.gold}) else "non_compliant"
                rows.append({**item, "replay_available": True, "integrity_passed": True,
                             "gold_status": expected, "status_matches_gold": replay["saved"]["status"] == expected,
                             "replay": replay})
            except (AssertionError, ValueError, TypeError, KeyError) as error:
                rows.append({**item, "replay_available": True, "integrity_passed": False,
                             "error_type": type(error).__name__, "detail": str(error)[:240]})
    assert offset == len(payload["requests"])
    output = Path(os.environ["MEDQC_EXAM_POC_REPORT"])
    assert not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"source_commit": payload["source_commit"], "new_model_calls": 0,
        "business_database_writes": 0, "rows": rows,
        "integrity_failures": sum(r.get("integrity_passed") is False for r in rows),
        "clinical_direction_mismatches": sum(r.get("status_matches_gold") is False for r in rows)},
        ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    assert not any(r.get("integrity_passed") is False for r in rows)
