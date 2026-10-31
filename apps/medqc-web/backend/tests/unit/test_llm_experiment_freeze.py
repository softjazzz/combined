"""A0/A1只隔离持久事实，不修改材料、Prompt或判定。"""

import asyncio

import pytest

from app.services.llm_experiment import (
    LLMExperimentConfigurationError,
    current_llm_experiment_namespace,
    experiment_store_dir,
    llm_experiment_scope,
)
from app.services.luxian_0609 import (
    antimicrobial_freeze,
    consultation_opinion_freeze,
    consultation_response_freeze,
    exam_analysis_freeze,
)


@pytest.fixture(autouse=True)
def isolated_stores(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_EXPERIMENT_NAMESPACE", raising=False)
    for name in (
        "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR",
        "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR",
        "LUXIAN_0609_OPINION_FREEZE_DIR",
        "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR",
    ):
        monkeypatch.setenv(name, str(tmp_path / name))


def test_default_path_is_exactly_legacy_and_explicit_namespace_isolated(tmp_path):
    base = tmp_path / "owner"
    assert current_llm_experiment_namespace() is None
    assert experiment_store_dir(base) == base
    for label in ("A0", "A1", "A0-fixed-run", "A1-20261031"):
        with llm_experiment_scope(label):
            assert current_llm_experiment_namespace() == label
            assert experiment_store_dir(base) == base / "experiments" / label
    assert current_llm_experiment_namespace() is None


@pytest.mark.parametrize(
    "bad",
    [
        "",
        " ",
        " A0",
        "A1 ",
        "../A0",
        "A0/../../other",
        "A0\\other",
        "A0..",
        "baseline",
        "A2-run",
        "a0",
        "A1-",
        "A0-" + "x" * 62,
        None,
        1,
    ],
)
def test_invalid_namespace_fails_closed_without_creating_files(bad, tmp_path):
    with pytest.raises(LLMExperimentConfigurationError):
        with llm_experiment_scope(bad):
            experiment_store_dir(tmp_path / "owner").mkdir(parents=True)
    assert list(tmp_path.iterdir()) == []


def test_environment_and_nested_scope_restore_after_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_EXPERIMENT_NAMESPACE", "A0-env")
    assert current_llm_experiment_namespace() == "A0-env"
    with llm_experiment_scope("A1-outer"):
        with pytest.raises(RuntimeError):
            with llm_experiment_scope("A0-inner"):
                assert current_llm_experiment_namespace() == "A0-inner"
                raise RuntimeError("synthetic")
        assert current_llm_experiment_namespace() == "A1-outer"
    assert current_llm_experiment_namespace() == "A0-env"
    monkeypatch.setenv("LLM_EXPERIMENT_NAMESPACE", "A0/escape")
    with pytest.raises(LLMExperimentConfigurationError):
        experiment_store_dir(tmp_path)


@pytest.mark.asyncio
async def test_parallel_scope_and_cancel_are_context_local():
    gate = asyncio.Event()

    async def inspect(label):
        with llm_experiment_scope(label):
            await gate.wait()
            return current_llm_experiment_namespace()

    first = asyncio.create_task(inspect("A0-parallel"))
    second = asyncio.create_task(inspect("A1-parallel"))
    cancelled = asyncio.create_task(inspect("A1-cancelled"))
    await asyncio.sleep(0)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    gate.set()
    assert await asyncio.gather(first, second) == ["A0-parallel", "A1-parallel"]
    assert current_llm_experiment_namespace() is None


@pytest.mark.parametrize("owner", [exam_analysis_freeze, antimicrobial_freeze])
def test_same_prompt_fixed_answers_never_cross_baseline_a0_a1(owner):
    prompt = "same synthetic evidence and unchanged prompt"
    key = owner.freeze_key(prompt)
    base = owner.default_store_dir()
    calls = []

    def evaluate(answer):
        existing = owner.load_payload("synthetic", key)
        if existing is not None:
            return existing
        calls.append(answer)
        payload = {"fixed_answer": answer, "event_id": "E1", "evidence_ids": ["D1"]}
        owner.save_payload("synthetic", key, payload)
        return payload

    baseline = evaluate("baseline")
    baseline_bytes = (base / "synthetic" / (key + ".json")).read_bytes()
    for label, answer in (("A0-run", "thinking-on"), ("A1-run", "thinking-off")):
        with llm_experiment_scope(label):
            assert owner.load_payload("synthetic", key) is None
            result = evaluate(answer)
            assert result["fixed_answer"] == answer
            assert evaluate("must-not-call") == result
            assert (
                base / "experiments" / label / "synthetic" / (key + ".json")
            ).is_file()
    assert calls == ["baseline", "thinking-on", "thinking-off"]
    assert evaluate("must-not-call") == baseline
    assert (base / "synthetic" / (key + ".json")).read_bytes() == baseline_bytes


def test_consultation_opinion_explicit_directory_and_reset_are_isolated(tmp_path):
    owner = consultation_opinion_freeze
    base = tmp_path / "explicit-owner"
    documents = [
        {"ref": "d1", "time": "2026-01-01", "text": "synthetic fixed document"}
    ]

    def save(answer):
        return owner.save_opinion_payload(
            visit_id="synthetic-visit",
            documents=documents,
            payload={"episodes": [answer]},
            store_dir=base,
            created_at="2026-01-01T00:00:00",
        )

    baseline = save("baseline")
    raw = baseline.path.read_bytes()
    with llm_experiment_scope("A0-run"):
        assert (
            owner.load_opinion_payload(
                visit_id="synthetic-visit", documents=documents, store_dir=base
            )
            is None
        )
        a0 = save("on")
        assert a0.path == base / "experiments" / "A0-run" / "synthetic-visit.json"
        assert save("no-overwrite").payload == {"episodes": ["on"]}
    with llm_experiment_scope("A1-run"):
        assert (
            owner.load_opinion_payload(
                visit_id="synthetic-visit", documents=documents, store_dir=base
            )
            is None
        )
        a1 = save("off")
        assert a1.path != a0.path and a1.payload == {"episodes": ["off"]}
        assert owner.reset_opinion_freeze(visit_id="synthetic-visit", store_dir=base)
        assert a0.path.is_file() and baseline.path.is_file()
    assert baseline.path.read_bytes() == raw


@pytest.mark.asyncio
async def test_consultation_response_client_is_bound_to_experiment():
    owner = consultation_response_freeze
    calls = []

    class Fixed:
        def __init__(self, answer):
            self.answer = answer

        async def generate(self, prompt, **kwargs):
            calls.append(self.answer)
            return {
                "choices": [{"message": {"content": self.answer}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            }

    async def run(answer):
        client = owner.FrozenResponseClient(Fixed(answer), visit_id="same-visit")
        result = await client.generate("unchanged synthetic prompt")
        client.commit()
        return result, client

    baseline, _ = await run("baseline")
    base = owner.default_store_dir()
    before = (base / "same-visit.json").read_bytes()
    with llm_experiment_scope("A0-run"):
        on, retained = await run("on")
        reused, _ = await run("must-not-call")
        assert on["choices"] == reused["choices"]
    with llm_experiment_scope("A1-run"):
        off, _ = await run("off")
        assert off["choices"] != on["choices"]
        with pytest.raises(LLMExperimentConfigurationError):
            await retained.generate("unchanged synthetic prompt")
        with pytest.raises(LLMExperimentConfigurationError):
            retained.commit()
    assert calls == ["baseline", "on", "off"]
    assert (base / "same-visit.json").read_bytes() == before
    assert baseline["choices"] != on["choices"]


def test_legacy_memory_cache_is_partitioned_and_experiment_clear_preserves_baseline():
    from app.services.qc_execution_cache import QCExecutionCache

    owner = QCExecutionCache()
    owner.set("same-key", {"answer": "baseline"})
    for label in ("A0-run", "A1-run"):
        with llm_experiment_scope(label):
            assert owner.get("same-key") is None
            owner.set("same-key", {"answer": label})
            assert owner.get("same-key") == {"answer": label}
    owner.clear()
    assert owner.get("same-key") is None
    for label in ("A0-run", "A1-run"):
        with llm_experiment_scope(label):
            assert owner.get("same-key") == {"answer": label}
    owner.set("same-key", {"answer": "baseline"})
    with llm_experiment_scope("A0-run"):
        owner.clear()
        assert owner.get("same-key") is None
    with llm_experiment_scope("A1-run"):
        assert owner.get("same-key") == {"answer": "A1-run"}
    assert owner.get("same-key") == {"answer": "baseline"}
    assert "same-key" in owner._entries


def test_invalid_environment_namespace_cannot_access_any_memory_or_disk_cache(
    monkeypatch, tmp_path
):
    from app.services.qc_execution_cache import QCExecutionCache

    owner = QCExecutionCache()
    owner.set("key", {"answer": "baseline"})
    monkeypatch.setenv("LLM_EXPERIMENT_NAMESPACE", "../escape")
    for action in (
        lambda: owner.get("key"),
        lambda: owner.set("key", {}),
        owner.clear,
        lambda: exam_analysis_freeze.load_payload("synthetic", "key"),
        lambda: antimicrobial_freeze.save_payload("synthetic", "key", {}),
        lambda: consultation_opinion_freeze.load_opinion_payload(
            visit_id="visit", documents=[]
        ),
        lambda: consultation_response_freeze.FrozenResponseClient(
            None, visit_id="visit"
        ),
    ):
        with pytest.raises(LLMExperimentConfigurationError):
            action()
    assert owner._entries["key"].value == {"answer": "baseline"}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_real_exam_main_extraction_freeze_never_reuses_other_experiment_answer():
    import json
    from app.services.luxian_0609 import native_exam_lab_execution as native
    from app.services.luxian_0609.exam_lab_fact_extraction import (
        build_exam_lab_text_projection,
    )

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": (
                {
                    "labtest_id": "SYN-LAB",
                    "labtest_name": "痰培养",
                    "collect_time": "2026-01-01 08:00:00",
                    "report_time": "2026-01-02 08:00:00",
                    "labtest_result": "合成培养结果",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "SYN-DOC",
                    "record_time": "2026-01-02 12:00:00",
                    "record_content": "已记录合成培养结果。",
                },
            ),
        }
    )
    calls = []

    class Fixed:
        def __init__(self, state):
            self.state = state

        async def generate(self, prompt, **kwargs):
            calls.append(self.state)
            content = {
                "schema_version": "lx0609-exam-lab-text-facts-v3",
                "facts": [
                    {
                        "rule_id": "LX0609-06-03-03",
                        "applicability": "applicable",
                        "semantic_state": self.state,
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1] if self.state == "present" else [],
                    }
                ],
            }
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(content)},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

    async def run(state):
        return await native._extract_exam_lab_batch(
            projection=projection,
            eligible_rule_ids=["LX0609-06-03-03"],
            llm_client=Fixed(state),
        )

    baseline = await run("present")
    assert baseline.facts is not None and baseline.facts[0].semantic_state == "present"
    assert baseline.llm_call_count == 1
    with llm_experiment_scope("A0-main"):
        first = await run("absent")
        repeated = await run("present")
        assert (
            first.facts[0].semantic_state
            == repeated.facts[0].semantic_state
            == "absent"
        )
        assert first.llm_call_count == 1 and repeated.llm_call_count == 0
    with llm_experiment_scope("A1-main"):
        first = await run("present")
        repeated = await run("absent")
        assert (
            first.facts[0].semantic_state
            == repeated.facts[0].semantic_state
            == "present"
        )
        assert first.llm_call_count == 1 and repeated.llm_call_count == 0
    assert (await run("absent")).facts == baseline.facts
    assert calls == ["present", "absent", "present"]
