"""E2E 脚本「正式首页」读取合同 — 注入测试（不连库、不发真实请求、不写库）。

覆盖两份脚本调用 ``GET /api/medical-records/frontpage-sheet`` 的方式：

- 有可信病例机构号时按三坐标追加 URL 编码的 ``institute_id``，缺失时不编造机构；
- patient_id / visit_id 路径段逐段编码，避免 ``/``、``?``、``#`` 截断路由；
- 401/403/404/409/503 等失败按阻断错误收口，不用 LLM 草稿顶替「正式首页」统计通过。

运行：``cd backend; python -m pytest tests/unit/test_run_case_e2e_frontpage_sheet_contract.py``
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import run_case_e2e  # noqa: E402
from scripts import run_mongo_pg_v4_e2e as v4_e2e  # noqa: E402


# ---------------------------------------------------------------------------
# run_case_e2e：路径/查询串构造
# ---------------------------------------------------------------------------


def test_case_e2e_path_appends_encoded_institute_id() -> None:
    assert run_case_e2e.build_frontpage_sheet_path("P1", "V1", "SCPH") == (
        "/api/medical-records/frontpage-sheet/P1/V1?institute_id=SCPH"
    )


@pytest.mark.parametrize("value", ["", "   ", None])
def test_case_e2e_path_omits_institute_when_absent(value: Any) -> None:
    assert run_case_e2e.build_frontpage_sheet_path("P1", "V1", value) == (
        "/api/medical-records/frontpage-sheet/P1/V1"
    )


def test_case_e2e_path_encodes_segments_and_query() -> None:
    """patient_id/visit_id 含 `/`、`?`、`#` 时必须编码成路径段，机构号不得注入额外参数。"""

    path = run_case_e2e.build_frontpage_sheet_path("P/1", "V?1#x", "A B&x=1")

    head, separator, query = path.partition("?")
    assert separator == "?", "有可信机构号时必须追加 institute_id 查询串"
    assert head == "/api/medical-records/frontpage-sheet/P%2F1/V%3F1%23x"
    assert query == "institute_id=" + quote("A B&x=1", safe="")
    assert "%2F" in head and "%3F" in head
    assert query.count("&") == 0, "机构号里的 & 必须被编码，不能分裂成额外查询参数"


# ---------------------------------------------------------------------------
# run_case_e2e：失败原因不得回显服务端文本
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "reason"),
    [
        (401, "鉴权失败"),
        (403, "无权限"),
        (404, "正式首页缺失"),
        (409, "正式首页归属不唯一"),
        (503, "首页取数服务不可用"),
    ],
)
def test_case_e2e_failure_reason_covers_documented_statuses(status_code: int, reason: str) -> None:
    assert run_case_e2e.frontpage_sheet_failure_reason(status_code) == reason


def test_case_e2e_failure_reason_takes_only_status_code() -> None:
    """只接受状态码，天然无法回显 detail/SQL/患者标识；防止以后被改成拼接原始错误。"""

    params = inspect.signature(run_case_e2e.frontpage_sheet_failure_reason).parameters
    assert list(params) == ["status_code"]


# ---------------------------------------------------------------------------
# run_case_e2e：主流程注入（不发真实请求）
# ---------------------------------------------------------------------------

_LEAK_MARKER = "内置候选患者 P1 跨机构冲突"


def _run_case_e2e_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sheet_status: int,
    sheet_payload: Any,
    pg_snapshot: Any = None,
    use_real_pg_snapshot: bool = False,
    pg_rows: dict[Any, list[Any]] | None = None,
    extra_argv: tuple[str, ...] = (),
) -> tuple[int, dict[str, Any], list[tuple[str, str]], list[Any]]:
    calls: list[tuple[str, str]] = []
    pg_calls: list[Any] = []

    def fake_request(
        self: Any,
        method: str,
        path: str,
        *,
        params: Any = None,
        json_data: Any = None,
        use_auth: bool = True,
    ) -> tuple[bool, int, float, Any, str]:
        calls.append((method, path))
        if path == "/api/v1/sync/runs":
            return True, 200, 1.0, {"items": [{"status": "success"}]}, ""
        if path.startswith("/api/medical-records/frontpage-sheet/"):
            if sheet_status >= 400:
                # 故意带患者标识：用来证明它不会进入报告
                return False, sheet_status, 1.0, {"detail": _LEAK_MARKER}, _LEAK_MARKER
            return True, sheet_status, 1.0, sheet_payload, ""
        return True, 200, 1.0, {}, ""

    monkeypatch.setattr(run_case_e2e.ApiClient, "request", fake_request)
    monkeypatch.setattr(run_case_e2e, "_load_mongo_snapshot", lambda *a, **k: {"available": False})

    def fake_load_pg_snapshot(patient_id: str, visit_id: str, institute_id: Any = None) -> Any:
        pg_calls.append(institute_id)
        if pg_snapshot is not None:
            return pg_snapshot
        return {
            "mr": {"institute_id": "SCPH", "patient_id": patient_id, "visit_id": visit_id},
            "diagnosis": [],
            "mr_surgery": [],
            "mr_cost": {"institute_id": "SCPH", "patient_id": patient_id, "visit_id": visit_id},
            "institute_id": "SCPH",
            "identity_error": "",
        }

    if use_real_pg_snapshot:
        # 真函数 + 假 Session：让报告里的 PG 事实真的经过三坐标收口
        from app.database import connection as connection_module

        monkeypatch.setattr(
            connection_module,
            "SessionLocal",
            lambda: _SeededSession(pg_rows or {}),
            raising=False,
        )
    else:
        monkeypatch.setattr(run_case_e2e, "_load_pg_snapshot", fake_load_pg_snapshot)

    out_dir = tmp_path / "case-e2e-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_case_e2e",
            "--patient-id",
            "P1",
            "--visit-id",
            "V1",
            "--base-url",
            "http://127.0.0.1:1",
            "--output-dir",
            str(out_dir),
            "--poll-timeout",
            "0",
            *extra_argv,
        ],
    )
    exit_code = run_case_e2e.main()
    reports = sorted(out_dir.glob("case_e2e_*.json"))
    assert reports, "未生成验收报告"
    return exit_code, json.loads(reports[-1].read_text(encoding="utf-8")), calls, pg_calls


@pytest.mark.parametrize("status_code", [401, 403, 404, 409, 503])
def test_case_e2e_frontpage_failure_is_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status_code: int
) -> None:
    exit_code, report, calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=status_code,
        sheet_payload={},
        extra_argv=("--institute-id", "SCPH"),
    )

    assert report["final_status"]["level"] == "fail"
    assert report["final_status"]["passed"] is False
    assert exit_code == 1
    assert any(f"HTTP {status_code}" in item for item in report["final_status"]["errors"])
    assert _LEAK_MARKER not in json.dumps(report, ensure_ascii=False), "阻断错误不得回显服务端 detail"
    assert not any("formal-qc/validate" in path for _, path in calls), "失败时不得继续跑首页形式质控"


def test_case_e2e_empty_200_frontpage_is_not_a_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """HTTP 200 但正文为空 `{}` 不是可评估的正式首页，必须按失败收口。"""

    exit_code, report, calls, _pg_calls = _run_case_e2e_main(
        monkeypatch, tmp_path, sheet_status=200, sheet_payload={}
    )

    assert report["final_status"]["level"] == "fail"
    assert exit_code == 1
    assert any("正式首页响应为空或非对象" in item for item in report["final_status"]["errors"])
    assert not any("formal-qc/validate" in path for _, path in calls)


def test_case_e2e_success_sends_institute_id_and_runs_formal_qc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    _exit_code, report, calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        extra_argv=("--institute-id", "SCPH"),
    )

    assert ("GET", "/api/medical-records/frontpage-sheet/P1/V1?institute_id=SCPH") in calls
    assert any("formal-qc/validate" in path for _, path in calls)
    assert not any("正式首页读取失败" in item for item in report["final_status"]["errors"])
    assert report["case_meta"]["institute_id"] == "SCPH"


def test_case_e2e_without_institute_id_keeps_backend_compat_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    _exit_code, report, calls, _pg_calls = _run_case_e2e_main(
        monkeypatch, tmp_path, sheet_status=200, sheet_payload=payload
    )

    assert ("GET", "/api/medical-records/frontpage-sheet/P1/V1") in calls
    assert report["case_meta"]["institute_id"] == ""


# ---------------------------------------------------------------------------
# run_case_e2e：PG 首页快照必须钉在三坐标上（跨机构同号反例）
# ---------------------------------------------------------------------------


def _pg_case_rows() -> dict[Any, list[Any]]:
    """甲乙两院同 patient+visit：首页/诊断/手术/费用号码全同，猜首行或混读会立刻暴露。"""

    from app.database.models.cdm import Diagnosis, MedicalRecordFrontpage, MrCost, MrSurgery

    return {
        MedicalRecordFrontpage: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", name="甲院患者"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", name="乙院患者"),
        ],
        Diagnosis: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", diagnosis_name="甲院诊断"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", diagnosis_name="乙院诊断"),
        ],
        MrSurgery: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", surgery_name="甲院手术"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", surgery_name="乙院手术"),
        ],
        MrCost: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", total_cost="100.00"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", total_cost="999.00"),
        ],
    }


def _load_case_e2e_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    rows_by_model: dict[Any, list[Any]],
    institute_id: str,
    query_log: list[Any] | None = None,
) -> tuple[dict[str, Any], list[Any]]:
    from app.database import connection as connection_module

    session = _SeededSession(rows_by_model, query_log=query_log)
    monkeypatch.setattr(
        connection_module, "SessionLocal", lambda: session, raising=False
    )
    return run_case_e2e._load_pg_snapshot("P1", "V1", institute_id), session.query_log


def test_pg_snapshot_explicit_institute_reads_exact_three_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, _query_log = _load_case_e2e_snapshot(monkeypatch, _pg_case_rows(), "INST-B")

    assert snapshot["identity_error"] == ""
    assert snapshot["institute_id"] == "INST-B"
    assert snapshot["mr"]["institute_id"] == "INST-B"
    assert snapshot["mr"]["name"] == "乙院患者"
    assert snapshot["mr_cost"]["total_cost"] == "999.00"
    assert [row["diagnosis_name"] for row in snapshot["diagnosis"]] == ["乙院诊断"]
    assert [row["surgery_name"] for row in snapshot["mr_surgery"]] == ["乙院手术"]


def test_pg_snapshot_multi_institute_without_institute_refuses_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.database.models.cdm import MedicalRecordFrontpage

    snapshot, query_log = _load_case_e2e_snapshot(monkeypatch, _pg_case_rows(), "")

    assert "拒绝猜首行" in snapshot["identity_error"]
    assert snapshot["institute_id"] == ""
    assert snapshot["mr"] is None
    assert snapshot["mr_cost"] is None
    assert snapshot["diagnosis"] == []
    assert snapshot["mr_surgery"] == []
    assert query_log == [MedicalRecordFrontpage], "身份不唯一时不得再去读诊断/手术/费用"


def test_pg_snapshot_single_candidate_stays_compatible_and_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只有一家机构有首页时按该机构读取，别家同号杂散行不得混入。"""

    from app.database.models.cdm import MedicalRecordFrontpage

    rows = _pg_case_rows()
    rows[MedicalRecordFrontpage] = [
        row for row in rows[MedicalRecordFrontpage] if row.institute_id == "INST-A"
    ]

    snapshot, _query_log = _load_case_e2e_snapshot(monkeypatch, rows, "")

    assert snapshot["identity_error"] == ""
    assert snapshot["institute_id"] == "INST-A"
    assert snapshot["mr"]["institute_id"] == "INST-A"
    assert [row["institute_id"] for row in snapshot["diagnosis"]] == ["INST-A"]
    assert [row["institute_id"] for row in snapshot["mr_surgery"]] == ["INST-A"]
    assert snapshot["mr_cost"]["total_cost"] == "100.00"


def test_pg_snapshot_no_match_returns_empty_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.database.models.cdm import MedicalRecordFrontpage

    snapshot, query_log = _load_case_e2e_snapshot(monkeypatch, {}, "")

    assert snapshot["mr"] is None
    assert snapshot["mr_cost"] is None
    assert snapshot["diagnosis"] == []
    assert snapshot["mr_surgery"] == []
    assert snapshot["institute_id"] == ""
    assert query_log == [MedicalRecordFrontpage], "无机构归属时关联表必须 0 次查询"


def test_case_e2e_missing_pg_frontpage_is_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    exit_code, report, _calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        pg_snapshot={
            "mr": None,
            "diagnosis": [],
            "mr_surgery": [],
            "mr_cost": None,
            "institute_id": "",
            "identity_error": "",
        },
    )

    assert report["final_status"]["level"] == "fail"
    assert exit_code == 1
    assert any("PG 首页缺失" in item for item in report["final_status"]["errors"])


def test_case_e2e_ambiguous_pg_identity_is_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    exit_code, report, _calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        pg_snapshot={
            "mr": None,
            "diagnosis": [],
            "mr_surgery": [],
            "mr_cost": None,
            "institute_id": "",
            "identity_error": "缺少机构号且首页候选跨 2 家机构，拒绝猜首行",
        },
    )

    assert report["final_status"]["level"] == "fail"
    assert exit_code == 1
    assert any("PG 首页身份不唯一" in item for item in report["final_status"]["errors"])
    assert report["input_records"]["pg"]["identity_error"] != ""


def test_case_e2e_forwards_institute_id_into_pg_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    _exit_code, _report, _calls, pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        extra_argv=("--institute-id", "INST-B"),
    )

    assert pg_calls == ["INST-B"], "PG 快照必须拿到同一个可信机构号做三坐标读取"


def test_case_e2e_failure_report_has_no_cross_institute_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """缺机构且跨机构同号：失败报告也不得写入别家患者/机构事实。"""

    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    exit_code, report, _calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        use_real_pg_snapshot=True,
        pg_rows=_pg_case_rows(),
    )

    assert report["final_status"]["level"] == "fail"
    assert exit_code == 1
    assert any("PG 首页身份不唯一" in item for item in report["final_status"]["errors"])

    pg_summary = report["input_records"]["pg"]
    assert pg_summary["mr_found"] is False
    assert pg_summary["diagnosis_count"] == 0
    assert pg_summary["surgery_count"] == 0
    assert pg_summary["cost_found"] is False

    rendered = json.dumps(report, ensure_ascii=False)
    for leaked in ("乙院诊断", "乙院手术", "999.00"):
        assert leaked not in rendered, f"失败报告混入了别家机构事实：{leaked}"


def test_case_e2e_failure_report_without_frontpage_candidate_has_no_facts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无首页候选（无机构归属）时关联事实必须为空，且阻断错误为「PG 首页缺失」。"""

    payload = {"basic": {"name": "测试患者"}, "diagnoses": [], "surgeries": [], "cost": {}}

    exit_code, report, _calls, _pg_calls = _run_case_e2e_main(
        monkeypatch,
        tmp_path,
        sheet_status=200,
        sheet_payload=payload,
        use_real_pg_snapshot=True,
        pg_rows={},
    )

    assert report["final_status"]["level"] == "fail"
    assert exit_code == 1
    assert any("PG 首页缺失" in item for item in report["final_status"]["errors"])

    pg_summary = report["input_records"]["pg"]
    assert pg_summary["mr_found"] is False
    assert pg_summary["diagnosis_count"] == 0
    assert pg_summary["surgery_count"] == 0
    assert pg_summary["cost_found"] is False
    assert pg_summary["institute_id"] == ""


# ---------------------------------------------------------------------------
# run_mongo_pg_v4_e2e：持久化验收注入（窄口径假 Session，不连库）
# ---------------------------------------------------------------------------


class _Column:
    def __init__(self, name: str) -> None:
        self.name = name


class _Table:
    def __init__(self, names: list[str]) -> None:
        self.columns = [_Column(name) for name in names]


class _Row:
    """最小行对象：``_to_plain_dict`` 只依赖 ``__table__.columns`` 与属性读取。"""

    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)
        self.__table__ = _Table(list(values))


class _SeededQuery:
    """窄口径假 Query：只支持被测代码真实调用的 filter/filter_by/order_by/all/first/count。"""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def filter(self, *_args: Any, **_kwargs: Any) -> "_SeededQuery":
        return self

    def filter_by(self, **criteria: Any) -> "_SeededQuery":
        return _SeededQuery(
            [
                row
                for row in self._rows
                if all(getattr(row, key, None) == value for key, value in criteria.items())
            ]
        )

    def order_by(self, *_args: Any, **_kwargs: Any) -> "_SeededQuery":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def count(self) -> int:
        return len(self._rows)


class _SeededSession:
    def __init__(
        self, rows_by_model: dict[Any, list[Any]], query_log: list[Any] | None = None
    ) -> None:
        self._rows_by_model = rows_by_model
        self.query_log: list[Any] = [] if query_log is None else query_log

    def __enter__(self) -> "_SeededSession":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def query(self, model: Any = None, *_args: Any, **_kwargs: Any) -> _SeededQuery:
        self.query_log.append(model)
        return _SeededQuery(list(self._rows_by_model.get(model, [])))

    def rollback(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}"

    def json(self) -> Any:
        return self._payload


_V4_LEAK_MARKER = "患者 P1 跨机构冲突"


def _run_v4_persistence(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frontpage_status: int,
    frontpage_payload: Any = None,
    institute_id: str = "SCPH",
    patient_id: str = "P1",
    visit_id: str = "V1",
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    monkeypatch.setattr(v4_e2e, "SessionLocal", lambda: _SeededSession({}))
    captured: dict[str, list[str]] = {"gets": [], "posts": []}

    def fake_get(url: str, **_kwargs: Any) -> _FakeResponse:
        captured["gets"].append(url)
        if "/frontpage-sheet/" in url:
            if frontpage_status >= 400:
                return _FakeResponse(frontpage_status, {"detail": _V4_LEAK_MARKER})
            payload = {"basic": {}} if frontpage_payload is None else frontpage_payload
            return _FakeResponse(frontpage_status, payload)
        return _FakeResponse(200, {})

    def fake_post(url: str, **_kwargs: Any) -> _FakeResponse:
        captured["posts"].append(url)
        return _FakeResponse(200, {"data": {"persistence": {"qc_result_id": "q1"}}})

    monkeypatch.setattr(v4_e2e.requests, "get", fake_get)
    monkeypatch.setattr(v4_e2e.requests, "post", fake_post)

    result = v4_e2e._run_persistence_checks(
        base_url="http://127.0.0.1:1",
        timeout=1,
        access_token="test-token",
        patient_id=patient_id,
        visit_id_discharged=visit_id,
        institute_id=institute_id,
    )
    return result, captured


@pytest.mark.parametrize("status_code", [401, 403, 404, 409, 503])
def test_v4_frontpage_failure_is_blocking_without_draft_fallback(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    result, captured = _run_v4_persistence(monkeypatch, frontpage_status=status_code)

    assert any(
        "正式首页读取失败" in item and f"HTTP {status_code}" in item
        for item in result["blocking_errors"]
    )
    assert result["details"]["frontpage_sheet_request"]["status_code"] == status_code
    assert result["details"]["frontpage_sheet_request"]["institute_id_applied"] is True
    assert not any("formal-qc/validate" in url for url in captured["posts"]), (
        "正式首页失败时不得用草稿 payload 继续调用首页质控"
    )

    rendered = json.dumps(result, ensure_ascii=False)
    assert "draft" not in rendered.lower()
    assert _V4_LEAK_MARKER not in rendered


def test_v4_empty_frontpage_payload_is_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    result, captured = _run_v4_persistence(
        monkeypatch, frontpage_status=200, frontpage_payload={}
    )

    assert any("正式首页响应为空或非对象" in item for item in result["blocking_errors"])
    assert not any("formal-qc/validate" in url for url in captured["posts"])


def test_v4_success_runs_formal_qc_with_encoded_institute(monkeypatch: pytest.MonkeyPatch) -> None:
    result, captured = _run_v4_persistence(
        monkeypatch, frontpage_status=200, institute_id="A B&x"
    )

    sheet_url = next(url for url in captured["gets"] if "/frontpage-sheet/" in url)
    assert sheet_url.endswith("?institute_id=" + quote("A B&x", safe=""))
    assert any("formal-qc/validate" in url for url in captured["posts"])
    assert not any("正式首页读取失败" in item for item in result["blocking_errors"])


def test_v4_frontpage_sheet_url_encodes_path_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    _result, captured = _run_v4_persistence(
        monkeypatch,
        frontpage_status=200,
        institute_id="S/1",
        patient_id="P/1",
        visit_id="V?1",
    )

    sheet_url = next(url for url in captured["gets"] if "/frontpage-sheet/" in url)
    assert sheet_url.endswith("/frontpage-sheet/P%2F1/V%3F1?institute_id=S%2F1")


def test_v4_without_institute_id_omits_query(monkeypatch: pytest.MonkeyPatch) -> None:
    result, captured = _run_v4_persistence(monkeypatch, frontpage_status=200, institute_id="")

    sheet_url = next(url for url in captured["gets"] if "/frontpage-sheet/" in url)
    assert "?" not in sheet_url
    assert sheet_url.endswith("/api/medical-records/frontpage-sheet/P1/V1")
    assert result["details"]["frontpage_sheet_request"]["institute_id_applied"] is False


# ---------------------------------------------------------------------------
# run_mongo_pg_v4_e2e：PG 断言必须钉在三坐标上（跨机构同号反例）
# ---------------------------------------------------------------------------


def _v4_pg_rows(*, frontpage_institutes: tuple[str, ...] = ("INST-A", "INST-B")) -> dict[Any, list[Any]]:
    """已出院 V1 与在院 V2 的两院数据；frontpage_institutes 控制首页落在哪几家机构。"""

    from app.database.models.cdm import Diagnosis, MedicalRecordFrontpage, MrCost, MrSurgery

    return {
        MedicalRecordFrontpage: [
            _Row(institute_id=institute, patient_id="P1", visit_id=visit_id)
            for institute in frontpage_institutes
            for visit_id in ("V1", "V2")
        ],
        Diagnosis: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", diagnosis_id="D1"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", diagnosis_id="D1"),
        ],
        MrSurgery: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", surgery_id="S1"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", surgery_id="S1"),
        ],
        MrCost: [
            _Row(institute_id="INST-A", patient_id="P1", visit_id="V1", total_cost="100.00"),
            _Row(institute_id="INST-B", patient_id="P1", visit_id="V1", total_cost="999.00"),
        ],
    }


def _run_v4_pg_assertions(
    monkeypatch: pytest.MonkeyPatch,
    rows_by_model: dict[Any, list[Any]],
    *,
    institute_id: Any = None,
) -> dict[str, Any]:
    monkeypatch.setattr(v4_e2e, "SessionLocal", lambda: _SeededSession(rows_by_model))
    return v4_e2e._query_pg_assertions(
        patient_id="P1",
        visit_id_discharged="V1",
        visit_id_inpatient="V2",
        automation_started_at=datetime(2026, 9, 25, 12, 0, 0),
        institute_id=institute_id,
    )


def test_v4_pg_assertions_explicit_institute_reads_exact_three_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_v4_pg_assertions(monkeypatch, _v4_pg_rows(), institute_id="INST-B")
    snapshot = result["cdm_snapshot"]

    assert snapshot["identity_error"] == ""
    assert snapshot["identity_institute_id"] == "INST-B"
    assert snapshot["discharged_mr_found"] is True
    assert snapshot["inpatient_mr_found"] is True
    assert snapshot["discharged_cost_found"] is True
    assert snapshot["discharged_diagnosis_count"] == 1
    assert snapshot["discharged_surgery_count"] == 1
    assert not any("身份不唯一" in item for item in result["blocking_errors"])


def test_v4_pg_assertions_multi_institute_without_institute_is_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_v4_pg_assertions(monkeypatch, _v4_pg_rows(), institute_id=None)
    snapshot = result["cdm_snapshot"]

    assert any("拒绝猜首行" in item for item in result["blocking_errors"])
    assert snapshot["identity_error"] != ""
    assert snapshot["discharged_mr_found"] is False
    assert snapshot["discharged_cost_found"] is False
    assert snapshot["discharged_diagnosis_count"] == 0
    assert snapshot["discharged_surgery_count"] == 0


def test_v4_pg_assertions_single_candidate_stays_compatible_and_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首页只落在 INST-A 时按 INST-A 读取，INST-B 的同号杂散诊断/手术/费用不得混入。"""

    rows = _v4_pg_rows(frontpage_institutes=("INST-A",))
    result = _run_v4_pg_assertions(monkeypatch, rows, institute_id=None)
    snapshot = result["cdm_snapshot"]

    assert snapshot["identity_error"] == ""
    assert snapshot["identity_institute_id"] == "INST-A"
    assert snapshot["discharged_mr_found"] is True
    assert snapshot["inpatient_mr_found"] is True
    assert snapshot["discharged_diagnosis_count"] == 1
    assert snapshot["discharged_surgery_count"] == 1
    assert snapshot["discharged_cost_found"] is True


def test_v4_pg_assertions_no_match_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_v4_pg_assertions(monkeypatch, {}, institute_id="SCPH")
    snapshot = result["cdm_snapshot"]

    assert snapshot["discharged_mr_found"] is False
    assert snapshot["discharged_cost_found"] is False
    assert any("PG 未落到已出院病例 mr 主表" in item for item in result["blocking_errors"])


# ---------------------------------------------------------------------------
# 静态回归：下划线草稿变量不得复活（旧代码 draft_frontpage 未定义即为 NameError 溯源）
# ---------------------------------------------------------------------------


def test_scripts_no_longer_reference_undefined_draft_frontpage() -> None:
    for module in (run_case_e2e, v4_e2e):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "draft_frontpage" not in source
