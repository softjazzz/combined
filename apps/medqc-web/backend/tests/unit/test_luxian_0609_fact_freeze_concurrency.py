"""事实冻结同进程并发临时文件争用与会诊冻结命名碰撞回归测试（离线）。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import errno
import json
import os
from pathlib import Path
import threading

import pytest

from app.services.luxian_0609 import (
    antimicrobial_freeze,
    consultation_opinion_freeze,
    consultation_response_freeze,
    exam_analysis_freeze,
)
from app.services.luxian_0609.llm_prompt_privacy import PrivacyIdentityContextError
from app.services.luxian_0609.privacy_request_scope import (
    luxian_0609_case_identity_scope,
)


_OPINION_DOCS = (
    {
        "ref": "consultation_record-1",
        "time": "2026-07-20 10:00:00",
        "text": "会诊意见：建议完善合成复查并评估疗效。",
    },
)


def _opinion_payload(marker: str) -> dict:
    return {
        "episodes": [
            {
                "episode_ref": "consultation_record-1",
                "member_refs": ["consultation_record-1"],
                "application_refs": [],
                "opinion_refs": ["consultation_record-1"],
                "application_state": "absent",
                "opinion_state": "clear",
                "confidence": "high",
                "recommendations": [],
                "marker": marker,
            }
        ],
        "non_target_refs": [],
        "unresolved_refs": [],
    }


class _FixedResponseLLM:
    def __init__(self, answers: dict[str, str]) -> None:
        self._answers = dict(answers)
        self.calls: list[str] = []

    async def generate(self, prompt: str, **_kwargs):
        self.calls.append(prompt)
        return {
            "choices": [{"message": {"content": self._answers[prompt]}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }


def test_antimicrobial_freeze_concurrent_same_key_writers_no_race_and_no_tmp_leak(
    monkeypatch, tmp_path
):
    store = tmp_path / "antimicrobial"
    monkeypatch.setenv(antimicrobial_freeze._ENV_STORE_DIR, str(store))
    key = antimicrobial_freeze.freeze_key("synthetic-antimicrobial-prompt")
    workers = 16
    barrier = threading.Barrier(workers)

    def _write(worker_id: int) -> None:
        barrier.wait()
        antimicrobial_freeze.save_payload("order_reason", key, {"writer": worker_id})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_write, range(workers)))

    loaded = antimicrobial_freeze.load_payload("order_reason", key)
    assert loaded is not None
    assert loaded["writer"] in range(workers)
    assert len(list(store.rglob("*.json"))) == 1
    assert list(store.rglob("*.tmp")) == []


def test_exam_analysis_freeze_concurrent_same_key_writers_and_replace_fallback(
    monkeypatch, tmp_path
):
    store = tmp_path / "exam"
    monkeypatch.setenv(exam_analysis_freeze._ENV_STORE_DIR, str(store))
    key = exam_analysis_freeze.freeze_key("synthetic-exam-prompt")
    workers = 16
    barrier = threading.Barrier(workers)

    def _write(worker_id: int) -> None:
        barrier.wait()
        exam_analysis_freeze.save_payload("analysis", key, {"writer": worker_id})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_write, range(workers)))

    loaded = exam_analysis_freeze.load_payload("analysis", key)
    assert loaded is not None
    assert loaded["writer"] in range(workers)
    assert len(list(store.rglob("*.json"))) == 1
    assert list(store.rglob("*.tmp")) == []

    # 模拟不支持硬链接的文件系统，回退 os.replace 同样不得触发共享 .tmp 争用或遗留临时文件。
    fallback_key = exam_analysis_freeze.freeze_key("synthetic-exam-fallback-prompt")
    fallback_barrier = threading.Barrier(workers)

    def _unsupported_link(_src, _dst):
        raise OSError(errno.EPERM, "hard links unsupported")

    monkeypatch.setattr(os, "link", _unsupported_link)

    def _write_fallback(worker_id: int) -> None:
        fallback_barrier.wait()
        exam_analysis_freeze.save_payload("analysis", fallback_key, {"writer": worker_id})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_write_fallback, range(workers)))

    fallback_loaded = exam_analysis_freeze.load_payload("analysis", fallback_key)
    assert fallback_loaded is not None
    assert fallback_loaded["writer"] in range(workers)
    assert list(store.rglob("*.tmp")) == []


def test_consultation_opinion_freeze_concurrent_same_visit_and_schema_rebuild(tmp_path):
    store = tmp_path / "opinions"
    workers = 16
    barrier = threading.Barrier(workers)

    def _save(worker_id: int):
        barrier.wait()
        return consultation_opinion_freeze.save_opinion_payload(
            visit_id="visit-concurrent",
            documents=_OPINION_DOCS,
            payload=_opinion_payload(f"writer-{worker_id}"),
            store_dir=store,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_save, range(workers)))

    states = [item.state for item in results]
    assert states.count("created") == 1
    assert states.count("reused") == workers - 1
    markers = {item.payload["episodes"][0]["marker"] for item in results}
    assert len(markers) == 1
    loaded = consultation_opinion_freeze.load_opinion_payload(
        visit_id="visit-concurrent", documents=_OPINION_DOCS, store_dir=store
    )
    assert loaded is not None
    assert loaded.payload["episodes"][0]["marker"] == next(iter(markers))
    assert list(store.rglob("*.tmp")) == []

    # 旧 schema 版本在并发重建下仍可平滑升级，且只重建一次、其余复用。
    artifact = json.loads(loaded.path.read_text(encoding="utf-8"))
    artifact["schema_version"] = "consultation-opinion-freeze-v2"
    loaded.path.write_text(json.dumps(artifact), encoding="utf-8")

    rebuild_workers = 8
    rebuild_barrier = threading.Barrier(rebuild_workers)

    def _rebuild(worker_id: int):
        rebuild_barrier.wait()
        return consultation_opinion_freeze.save_opinion_payload(
            visit_id="visit-concurrent",
            documents=_OPINION_DOCS,
            payload=_opinion_payload(f"rebuilt-{worker_id}"),
            store_dir=store,
        )

    with ThreadPoolExecutor(max_workers=rebuild_workers) as pool:
        rebuilt_results = list(pool.map(_rebuild, range(rebuild_workers)))

    rebuilt_states = [item.state for item in rebuilt_results]
    assert rebuilt_states.count("rebuilt") == 1
    assert rebuilt_states.count("reused") == rebuild_workers - 1
    rebuilt_markers = {item.payload["episodes"][0]["marker"] for item in rebuilt_results}
    assert len(rebuilt_markers) == 1
    assert list(store.rglob("*.tmp")) == []


def test_consultation_response_freeze_concurrent_commits_merge_and_keep_first_writer(
    monkeypatch, tmp_path
):
    store = tmp_path / "responses"
    monkeypatch.setenv(consultation_response_freeze._ENV_STORE_DIR, str(store))
    workers = 12
    barrier = threading.Barrier(workers)

    def _worker(worker_id: int) -> None:
        llm = _FixedResponseLLM(
            {
                "shared-prompt": f"shared-from-{worker_id}",
                f"unique-prompt-{worker_id}": f"unique-from-{worker_id}",
            }
        )
        client = consultation_response_freeze.FrozenResponseClient(
            llm, visit_id="visit-response-concurrent"
        )
        asyncio.run(client.generate("shared-prompt"))
        asyncio.run(client.generate(f"unique-prompt-{worker_id}"))
        barrier.wait()
        client.commit()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_worker, range(workers)))

    assert len(list(store.rglob("*.json"))) == 1
    assert list(store.rglob("*.tmp")) == []

    # 校验所有并发线程各自提交的新提示词均未丢失，且共享提示词遵循首次写入者赢。
    verify_llm = _FixedResponseLLM({})
    verifier = consultation_response_freeze.FrozenResponseClient(
        verify_llm, visit_id="visit-response-concurrent"
    )
    shared = asyncio.run(verifier.generate("shared-prompt"))
    assert shared["choices"][0]["message"]["content"].startswith("shared-from-")
    for worker_id in range(workers):
        unique = asyncio.run(verifier.generate(f"unique-prompt-{worker_id}"))
        assert unique["choices"][0]["message"]["content"] == f"unique-from-{worker_id}"
    assert verify_llm.calls == []
    assert verifier.reused_calls == workers + 1


def test_failed_publish_cleans_up_temporary_files_across_all_freeze_modules(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(antimicrobial_freeze._ENV_STORE_DIR, str(tmp_path / "abx"))
    monkeypatch.setenv(exam_analysis_freeze._ENV_STORE_DIR, str(tmp_path / "exam"))
    monkeypatch.setenv(
        consultation_response_freeze._ENV_STORE_DIR, str(tmp_path / "resp")
    )

    def _fail_io(*_args, **_kwargs):
        raise OSError("synthetic disk error")

    monkeypatch.setattr(os, "link", _fail_io)
    monkeypatch.setattr(os, "replace", _fail_io)

    # 1. antimicrobial_freeze 吞掉 OSError 并清理临时文件与锁文件
    antimicrobial_freeze.save_payload("order_reason", "k1", {"ok": True})
    assert list((tmp_path / "abx").rglob("*.tmp")) == []
    assert list((tmp_path / "abx").rglob("*.lock")) == []

    # 2. exam_analysis_freeze 透传 OSError 但不遗留临时文件与锁文件
    with pytest.raises(OSError, match="synthetic disk error"):
        exam_analysis_freeze.save_payload("analysis", "k2", {"ok": True})
    assert list((tmp_path / "exam").rglob("*.tmp")) == []
    assert list((tmp_path / "exam").rglob("*.lock")) == []

    # 3. consultation_opinion_freeze 透传 OSError 但不遗留临时文件
    with pytest.raises(OSError, match="synthetic disk error"):
        consultation_opinion_freeze.save_opinion_payload(
            visit_id="v-fail",
            documents=_OPINION_DOCS,
            payload=_opinion_payload("fail"),
            store_dir=tmp_path / "opinion",
        )
    assert list((tmp_path / "opinion").rglob("*.tmp")) == []

    # 4. consultation_response_freeze 透传 OSError 但不遗留临时文件
    client = consultation_response_freeze.FrozenResponseClient(
        _FixedResponseLLM({"p": "ans"}), visit_id="v-fail"
    )
    asyncio.run(client.generate("p"))
    with pytest.raises(OSError, match="synthetic disk error"):
        client.commit()
    assert list((tmp_path / "resp").rglob("*.tmp")) == []


def test_consultation_opinion_freeze_isolates_same_visit_across_institutes_and_patients(
    tmp_path,
):
    store = tmp_path / "opinions"
    saved_a = consultation_opinion_freeze.save_opinion_payload(
        visit_id="V100",
        institute_id="HOSP_A",
        patient_id="PAT_SECRET_1",
        documents=_OPINION_DOCS,
        payload=_opinion_payload("hosp-a-p1"),
        store_dir=store,
    )
    saved_b = consultation_opinion_freeze.save_opinion_payload(
        visit_id="V100",
        institute_id="HOSP_B",
        patient_id="PAT_SECRET_1",
        documents=_OPINION_DOCS,
        payload=_opinion_payload("hosp-b-p1"),
        store_dir=store,
    )
    saved_p2 = consultation_opinion_freeze.save_opinion_payload(
        visit_id="V100",
        institute_id="HOSP_A",
        patient_id="PAT_SECRET_2",
        documents=_OPINION_DOCS,
        payload=_opinion_payload("hosp-a-p2"),
        store_dir=store,
    )
    saved_legacy = consultation_opinion_freeze.save_opinion_payload(
        visit_id="V100",
        documents=_OPINION_DOCS,
        payload=_opinion_payload("unscoped-legacy"),
        store_dir=store,
    )

    paths = {saved_a.path, saved_b.path, saved_p2.path, saved_legacy.path}
    assert len(paths) == 4
    assert saved_legacy.path == store / "V100.json"
    # 患者号不直接暴露在文件名或落盘元数据中
    assert "PAT_SECRET_1" not in saved_a.path.name
    assert "PAT_SECRET_1" not in saved_a.path.read_text(encoding="utf-8")

    assert (
        consultation_opinion_freeze.load_opinion_payload(
            visit_id="V100",
            institute_id="HOSP_A",
            patient_id="PAT_SECRET_1",
            documents=_OPINION_DOCS,
            store_dir=store,
        ).payload["episodes"][0]["marker"]
        == "hosp-a-p1"
    )
    assert (
        consultation_opinion_freeze.load_opinion_payload(
            visit_id="V100",
            institute_id="HOSP_B",
            patient_id="PAT_SECRET_1",
            documents=_OPINION_DOCS,
            store_dir=store,
        ).payload["episodes"][0]["marker"]
        == "hosp-b-p1"
    )
    assert (
        consultation_opinion_freeze.load_opinion_payload(
            visit_id="V100",
            institute_id="HOSP_A",
            patient_id="PAT_SECRET_2",
            documents=_OPINION_DOCS,
            store_dir=store,
        ).payload["episodes"][0]["marker"]
        == "hosp-a-p2"
    )

    # 重置单院区冻结不影响其他院区
    assert consultation_opinion_freeze.reset_opinion_freeze(
        visit_id="V100",
        institute_id="HOSP_A",
        patient_id="PAT_SECRET_1",
        store_dir=store,
    )
    assert (
        consultation_opinion_freeze.load_opinion_payload(
            visit_id="V100",
            institute_id="HOSP_A",
            patient_id="PAT_SECRET_1",
            documents=_OPINION_DOCS,
            store_dir=store,
        )
        is None
    )
    assert (
        consultation_opinion_freeze.load_opinion_payload(
            visit_id="V100",
            institute_id="HOSP_B",
            patient_id="PAT_SECRET_1",
            documents=_OPINION_DOCS,
            store_dir=store,
        )
        is not None
    )


def test_consultation_opinion_freeze_inherits_ambient_case_scope(tmp_path):
    store = tmp_path / "opinions-ambient"
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "PAT_1", "V200"),
        identity_provider=lambda: ("合成甲",),
    ):
        a = consultation_opinion_freeze.save_opinion_payload(
            visit_id="V200",
            documents=_OPINION_DOCS,
            payload=_opinion_payload("ambient-a"),
            store_dir=store,
        )
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_B", "PAT_1", "V200"),
        identity_provider=lambda: ("合成乙",),
    ):
        assert (
            consultation_opinion_freeze.load_opinion_payload(
                visit_id="V200", documents=_OPINION_DOCS, store_dir=store
            )
            is None
        )
        b = consultation_opinion_freeze.save_opinion_payload(
            visit_id="V200",
            documents=_OPINION_DOCS,
            payload=_opinion_payload("ambient-b"),
            store_dir=store,
        )

    assert a.path != b.path
    # 显式传入三坐标与隐式病例作用域定位到同一冻结文件
    explicit = consultation_opinion_freeze.load_opinion_payload(
        visit_id="V200",
        institute_id="HOSP_A",
        patient_id="PAT_1",
        documents=_OPINION_DOCS,
        store_dir=store,
    )
    assert explicit is not None
    assert explicit.path == a.path
    assert explicit.payload["episodes"][0]["marker"] == "ambient-a"


@pytest.mark.asyncio
async def test_consultation_response_freeze_isolates_same_visit_explicit_and_ambient(
    monkeypatch, tmp_path
):
    store = tmp_path / "responses-scoped"
    monkeypatch.setenv(consultation_response_freeze._ENV_STORE_DIR, str(store))

    # 显式院区/患者隔离
    llm_a = _FixedResponseLLM({"same-prompt": "answer-hosp-a"})
    client_a = consultation_response_freeze.FrozenResponseClient(
        llm_a, visit_id="V300", institute_id="HOSP_A", patient_id="PAT_SECRET_A"
    )
    resp_a = await client_a.generate("same-prompt")
    client_a.commit()

    llm_b = _FixedResponseLLM({"same-prompt": "answer-hosp-b"})
    client_b = consultation_response_freeze.FrozenResponseClient(
        llm_b, visit_id="V300", institute_id="HOSP_B", patient_id="PAT_SECRET_A"
    )
    resp_b = await client_b.generate("same-prompt")
    client_b.commit()

    assert resp_a["choices"][0]["message"]["content"] == "answer-hosp-a"
    assert resp_b["choices"][0]["message"]["content"] == "answer-hosp-b"
    assert client_b.reused_calls == 0
    assert client_a._store_path != client_b._store_path
    assert "PAT_SECRET_A" not in client_a._store_path.name
    assert "PAT_SECRET_A" not in client_a._store_path.read_text(encoding="utf-8")

    # 隐式病例作用域自动隔离（兼容现有只传 visit_id 的调用点）
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "PAT_SECRET_A", "V300"),
        identity_provider=lambda: ("合成甲",),
    ):
        reuse_llm = _FixedResponseLLM({})
        reused_a = consultation_response_freeze.FrozenResponseClient(
            reuse_llm, visit_id="V300"
        )
        got_a = await reused_a.generate("same-prompt")
        assert got_a["choices"][0]["message"]["content"] == "answer-hosp-a"
        assert reused_a.reused_calls == 1
        assert reuse_llm.calls == []

    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_C", "PAT_SECRET_A", "V300"),
        identity_provider=lambda: ("合成丙",),
    ):
        llm_c = _FixedResponseLLM({"same-prompt": "answer-hosp-c"})
        client_c = consultation_response_freeze.FrozenResponseClient(
            llm_c, visit_id="V300"
        )
        got_c = await client_c.generate("same-prompt")
        client_c.commit()
        assert got_c["choices"][0]["message"]["content"] == "answer-hosp-c"
        assert client_c.reused_calls == 0

    assert len(list(store.glob("*.json"))) == 3


@pytest.mark.asyncio
async def test_consultation_freeze_prevents_visit_id_sanitization_collisions(
    monkeypatch, tmp_path
):
    opinion_store = tmp_path / "opinions-sanitize"
    response_store = tmp_path / "responses-sanitize"
    monkeypatch.setenv(consultation_response_freeze._ENV_STORE_DIR, str(response_store))

    variants = [
        "hospA/001",
        "hospA:001",
        "hospA_001",
        "中文甲",
        "中文乙",
        "..",
        ".",
    ]

    opinion_paths: dict[str, Path] = {}
    for visit_id in variants:
        saved = consultation_opinion_freeze.save_opinion_payload(
            visit_id=visit_id,
            documents=_OPINION_DOCS,
            payload=_opinion_payload(visit_id),
            store_dir=opinion_store,
        )
        opinion_paths[visit_id] = saved.path

    assert len(set(opinion_paths.values())) == len(variants)
    assert opinion_paths["hospA_001"] == opinion_store / "hospA_001.json"
    for visit_id in variants:
        loaded = consultation_opinion_freeze.load_opinion_payload(
            visit_id=visit_id, documents=_OPINION_DOCS, store_dir=opinion_store
        )
        assert loaded is not None
        assert loaded.payload["episodes"][0]["marker"] == visit_id

    response_paths: dict[str, Path] = {}
    for visit_id in variants:
        client = consultation_response_freeze.FrozenResponseClient(
            _FixedResponseLLM({"prompt": f"resp-{visit_id}"}), visit_id=visit_id
        )
        await client.generate("prompt")
        client.commit()
        response_paths[visit_id] = client._store_path

    assert len(set(response_paths.values())) == len(variants)
    assert response_paths["hospA_001"] == response_store / "hospA_001.json"
    for visit_id in variants:
        verifier = consultation_response_freeze.FrozenResponseClient(
            _FixedResponseLLM({}), visit_id=visit_id
        )
        got = await verifier.generate("prompt")
        assert got["choices"][0]["message"]["content"] == f"resp-{visit_id}"
        assert verifier.reused_calls == 1


@pytest.mark.parametrize(
    ("owner", "namespace"),
    [
        (exam_analysis_freeze, "analysis"),
        (antimicrobial_freeze, "order_reason"),
    ],
)
def test_fallback_publish_preserves_first_writer_wins_when_hard_links_unavailable(
    monkeypatch, tmp_path, owner, namespace
):
    store = tmp_path / namespace
    monkeypatch.setenv(owner._ENV_STORE_DIR, str(store))
    key = owner.freeze_key(f"synthetic-fallback-first-writer-{namespace}")

    both_passed_initial_check = threading.Barrier(2)
    first_published = threading.Event()
    writer_tag = threading.local()
    real_replace = os.replace
    replace_calls = 0
    replace_lock = threading.Lock()

    def _unsupported_link(_src, _dst):
        # 两个线程均先穿过入口 if path.is_file(): return，再先后进入无硬链接回退路径。
        both_passed_initial_check.wait(timeout=5.0)
        if getattr(writer_tag, "name", None) == "second":
            assert first_published.wait(timeout=5.0)
        raise OSError(errno.EPERM, "hard links unsupported")

    def _counting_replace(src, dst):
        nonlocal replace_calls
        with replace_lock:
            replace_calls += 1
        result = real_replace(src, dst)
        if getattr(writer_tag, "name", None) == "first":
            first_published.set()
        return result

    monkeypatch.setattr(os, "link", _unsupported_link)
    monkeypatch.setattr(os, "replace", _counting_replace)

    def _run(label: str) -> None:
        writer_tag.name = label
        owner.save_payload(namespace, key, {"writer": label})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, "first"), pool.submit(_run, "second")]
        for future in futures:
            future.result()

    assert owner.load_payload(namespace, key) == {"writer": "first"}
    assert replace_calls == 1
    assert len(list(store.rglob("*.json"))) == 1
    assert list(store.rglob("*.tmp")) == []
    assert list(store.rglob("*.lock")) == []


def test_consultation_opinion_freeze_rejects_active_scope_conflicts_and_preserves_legacy(
    tmp_path,
):
    store = tmp_path / "opinions-scope-conflict"
    legacy = consultation_opinion_freeze.save_opinion_payload(
        visit_id="V1",
        documents=_OPINION_DOCS,
        payload=_opinion_payload("legacy-unscoped"),
        store_dir=store,
    )
    assert legacy.path == store / "V1.json"
    legacy_bytes = legacy.path.read_bytes()

    # 在 V2 活跃作用域内请求 V1：读写/重置均必须 fail-closed 拒绝，不得回退到旧 V1.json。
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "P2", "V2"),
        identity_provider=lambda: ("合成乙",),
    ):
        with pytest.raises(PrivacyIdentityContextError):
            consultation_opinion_freeze.load_opinion_payload(
                visit_id="V1", documents=_OPINION_DOCS, store_dir=store
            )
        with pytest.raises(PrivacyIdentityContextError):
            consultation_opinion_freeze.save_opinion_payload(
                visit_id="V1",
                documents=_OPINION_DOCS,
                payload=_opinion_payload("must-not-write"),
                store_dir=store,
            )
        with pytest.raises(PrivacyIdentityContextError):
            consultation_opinion_freeze.reset_opinion_freeze(
                visit_id="V1", store_dir=store
            )
    assert legacy.path.read_bytes() == legacy_bytes

    # 在 V1 合法活跃作用域内：旧无归属 V1.json 不得被盲目复用，scoped 读写独立落盘且保留旧文件。
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "P1", "V1"),
        identity_provider=lambda: ("合成甲",),
    ):
        assert (
            consultation_opinion_freeze.load_opinion_payload(
                visit_id="V1", documents=_OPINION_DOCS, store_dir=store
            )
            is None
        )
        scoped = consultation_opinion_freeze.save_opinion_payload(
            visit_id="V1",
            documents=_OPINION_DOCS,
            payload=_opinion_payload("scoped-v1"),
            store_dir=store,
        )
        assert scoped.path != legacy.path
        reused = consultation_opinion_freeze.load_opinion_payload(
            visit_id="V1", documents=_OPINION_DOCS, store_dir=store
        )
        assert reused is not None
        assert reused.payload["episodes"][0]["marker"] == "scoped-v1"

        # 与当前活跃作用域一致的显式坐标允许命中；冲突的显式院区或患者号必须拒绝。
        explicit_ok = consultation_opinion_freeze.load_opinion_payload(
            visit_id="V1",
            institute_id="HOSP_A",
            patient_id="P1",
            documents=_OPINION_DOCS,
            store_dir=store,
        )
        assert explicit_ok is not None and explicit_ok.path == scoped.path

        with pytest.raises(PrivacyIdentityContextError):
            consultation_opinion_freeze.load_opinion_payload(
                visit_id="V1",
                institute_id="HOSP_B",
                patient_id="P1",
                documents=_OPINION_DOCS,
                store_dir=store,
            )
        with pytest.raises(PrivacyIdentityContextError):
            consultation_opinion_freeze.save_opinion_payload(
                visit_id="V1",
                institute_id="HOSP_A",
                patient_id="P_OTHER",
                documents=_OPINION_DOCS,
                payload=_opinion_payload("conflict-pat"),
                store_dir=store,
            )

    assert legacy.path.read_bytes() == legacy_bytes


@pytest.mark.asyncio
async def test_consultation_response_freeze_rejects_active_scope_conflicts_and_preserves_legacy(
    monkeypatch, tmp_path
):
    store = tmp_path / "responses-scope-conflict"
    monkeypatch.setenv(consultation_response_freeze._ENV_STORE_DIR, str(store))

    # 先在无作用域旧模式下落盘 legacy V1.json
    legacy_client = consultation_response_freeze.FrozenResponseClient(
        _FixedResponseLLM({"p": "legacy-answer"}), visit_id="V1"
    )
    await legacy_client.generate("p")
    legacy_client.commit()
    legacy_path = store / "V1.json"
    assert legacy_path.is_file()
    legacy_bytes = legacy_path.read_bytes()

    # 预先在无作用域下构造的 V1 客户端，也绝不能在冲突作用域中读/写
    unscoped_retained = consultation_response_freeze.FrozenResponseClient(
        _FixedResponseLLM({"p2": "new-unscoped"}), visit_id="V1"
    )
    await unscoped_retained.generate("p2")

    # 在 V2 活跃作用域内请求 V1：构造/调用/提交全部拒绝，不读取也不改动 V1.json
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "P2", "V2"),
        identity_provider=lambda: ("合成乙",),
    ):
        with pytest.raises(PrivacyIdentityContextError):
            consultation_response_freeze.FrozenResponseClient(
                _FixedResponseLLM({"p": "must-not-run"}), visit_id="V1"
            )
        with pytest.raises(PrivacyIdentityContextError):
            await unscoped_retained.generate("p")
        with pytest.raises(PrivacyIdentityContextError):
            unscoped_retained.commit()
    assert legacy_path.read_bytes() == legacy_bytes

    # 在 V1 合法活跃作用域内：不误用旧无归属 V1.json，scoped 读写独立落盘并保留旧文件
    with luxian_0609_case_identity_scope(
        case_coordinates=("HOSP_A", "P1", "V1"),
        identity_provider=lambda: ("合成甲",),
    ):
        scoped_llm = _FixedResponseLLM({"p": "scoped-v1-answer"})
        scoped_client = consultation_response_freeze.FrozenResponseClient(
            scoped_llm, visit_id="V1"
        )
        got = await scoped_client.generate("p")
        assert got["choices"][0]["message"]["content"] == "scoped-v1-answer"
        assert scoped_client.reused_calls == 0
        scoped_client.commit()
        assert scoped_client._store_path != legacy_path

        # 再次在同作用域内读取可正常复用
        reuse_llm = _FixedResponseLLM({})
        reused = consultation_response_freeze.FrozenResponseClient(
            reuse_llm, visit_id="V1", institute_id="HOSP_A", patient_id="P1"
        )
        got_reused = await reused.generate("p")
        assert got_reused["choices"][0]["message"]["content"] == "scoped-v1-answer"
        assert reused.reused_calls == 1
        assert reuse_llm.calls == []

        # 显式院区/患者号与当前活跃作用域冲突时必须拒绝
        with pytest.raises(PrivacyIdentityContextError):
            consultation_response_freeze.FrozenResponseClient(
                _FixedResponseLLM({"p": "bad"}),
                visit_id="V1",
                institute_id="HOSP_B",
                patient_id="P1",
            )
        with pytest.raises(PrivacyIdentityContextError):
            consultation_response_freeze.FrozenResponseClient(
                _FixedResponseLLM({"p": "bad"}),
                visit_id="V1",
                institute_id="HOSP_A",
                patient_id="P_OTHER",
            )

    assert legacy_path.read_bytes() == legacy_bytes
