"""请求级恶性肿瘤事实解析：确定性门控后最多一次受控语义分类。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Mapping, Protocol, Sequence


SCHEMA_VERSION = "lx0609_malignancy_v1"
# 32条诊断的逐条受控结果在真实 qwen3.7-flash 响应中超过1024 Token；
# 2048仍是固定上限，且禁止长度重试，避免一次病例被二次调用。
MAX_COMPLETION_TOKENS = 2048
_ALLOWED_ITEM_STATES = frozenset(
    {"explicit_malignant", "explicit_nonmalignant", "uncertain"}
)
_MALIGNANT_CODE = re.compile(r"^C\d{2}(?:[.A-Z0-9-]*)$")
_UNCERTAIN_NEOPLASM_CODE = re.compile(r"^D(?:0[0-9]|3[7-9]|4[0-8])")


class MalignancyLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class MalignancySource:
    source_key: str
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()
    required_for_absence: bool = True


@dataclass(frozen=True)
class MalignancyResolution:
    state: str
    reason_code: str


@dataclass(frozen=True)
class MalignancyUsage:
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _DiagnosisItem:
    ref: str
    source_kind: str
    name: str
    code: str


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_malignancy_sources(
    *,
    diagnosis_state: str,
    diagnosis_rows: Sequence[Mapping[str, Any]],
    pathology_state: str,
    pathology_rows: Sequence[Mapping[str, Any]],
) -> tuple[MalignancySource, ...]:
    """诊断是完整阴性结论的必需来源；病理仅作为可选阳性证据。"""

    sources = [
        MalignancySource("diagnosis", diagnosis_state, tuple(diagnosis_rows), True)
    ]
    meaningful_pathology_rows = tuple(
        row
        for row in pathology_rows
        if _clean(row.get("diagnosis") or row.get("pathology_diagnosis"))
        not in {"", "病理诊断资料", "病理诊断资料。"}
    )
    if pathology_state in {"available", "present"} and meaningful_pathology_rows:
        sources.append(
            MalignancySource(
                "pathology_exam_report",
                pathology_state,
                meaningful_pathology_rows,
                False,
            )
        )
    return tuple(sources)


def resolve_malignancy_visit_stage(
    *,
    horizon_state: str,
    horizon_rows: Sequence[Mapping[str, Any]],
    discharge_record_state: str,
) -> str:
    """仅按权威出院时点和正式出院记录确定本次住院阶段。"""

    if horizon_state == "error" or discharge_record_state == "error":
        return "technical_error"
    if horizon_state in {"unavailable", "truncated", "missing"}:
        return "unknown"
    if any(
        _clean(row.get("discharge_datetime") or row.get("discharge_time"))
        for row in horizon_rows
    ) or discharge_record_state in {"present", "available"}:
        return "discharged"
    return "inpatient"


def build_stage_malignancy_sources(
    *,
    visit_stage: str,
    admission_state: str,
    admission_rows: Sequence[Mapping[str, Any]],
    diagnosis_state: str,
    diagnosis_rows: Sequence[Mapping[str, Any]],
    discharge_diagnosis_state: str,
    discharge_diagnosis_rows: Sequence[Mapping[str, Any]],
    pathology_state: str,
    pathology_rows: Sequence[Mapping[str, Any]],
) -> tuple[MalignancySource, ...]:
    """按病历阶段选择唯一阴性诊断链；病理只提供明确阳性证据。"""

    if visit_stage == "inpatient":
        return build_malignancy_sources(
            diagnosis_state=admission_state,
            diagnosis_rows=admission_rows,
            pathology_state=pathology_state,
            pathology_rows=pathology_rows,
        )
    if visit_stage != "discharged":
        raise ValueError("malignancy diagnosis source requires known visit stage")

    diagnosis_candidates = (
        (diagnosis_state, tuple(diagnosis_rows)),
        (discharge_diagnosis_state, tuple(discharge_diagnosis_rows)),
    )
    selected_state, selected_rows = next(
        (
            (state, rows)
            for state, rows in diagnosis_candidates
            if state in {"present", "available"} and rows
        ),
        next(
            (
                (state, rows)
                for state, rows in diagnosis_candidates
                if state == "error"
            ),
            next(
                (
                    (state, rows)
                    for state, rows in diagnosis_candidates
                    if state in {"unavailable", "truncated", "missing"}
                ),
                diagnosis_candidates[0],
            ),
        ),
    )
    return build_malignancy_sources(
        diagnosis_state=selected_state,
        diagnosis_rows=selected_rows,
        pathology_state=pathology_state,
        pathology_rows=pathology_rows,
    )


def _diagnosis_item(
    row: Mapping[str, Any], *, source_kind: str, index: int
) -> _DiagnosisItem | None:
    name = _clean(
        row.get("diagnosis_name")
        or row.get("diagnosis")
        or row.get("pathology_diagnosis")
    )
    code = _clean(row.get("diagnosis_code") or row.get("icd_code")).upper()
    if not name and not code:
        return None
    prefix = "P" if source_kind == "pathology" else "D"
    return _DiagnosisItem(
        ref=f"{prefix}{index:02d}",
        source_kind=source_kind,
        name=name[:240],
        code=code[:32],
    )


def _strict_usage(response: Mapping[str, Any]) -> MalignancyUsage:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        raise ValueError("malignancy usage missing")
    values: list[int] = []
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("malignancy usage invalid")
        values.append(value)
    prompt_tokens, completion_tokens, total_tokens = values
    if total_tokens != prompt_tokens + completion_tokens:
        raise ValueError("malignancy token total mismatch")
    if completion_tokens > MAX_COMPLETION_TOKENS:
        raise ValueError("malignancy completion token limit exceeded")
    api_time = response.get("_api_time", 0.0)
    if (
        isinstance(api_time, bool)
        or not isinstance(api_time, (int, float))
        or not math.isfinite(float(api_time))
        or float(api_time) < 0
    ):
        raise ValueError("malignancy api time invalid")
    return MalignancyUsage(
        llm_call_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=float(api_time),
    )


def _response_payload(response: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("malignancy response missing") from None
    if not isinstance(content, str):
        raise ValueError("malignancy response invalid")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("malignancy response invalid") from None
    if not isinstance(payload, Mapping):
        raise ValueError("malignancy response invalid")
    return payload


def _parse_resolution(
    response: Mapping[str, Any], *, items: Sequence[_DiagnosisItem]
) -> MalignancyResolution:
    payload = _response_payload(response)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("malignancy schema invalid")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list) or len(raw_results) != len(items):
        raise ValueError("malignancy result count invalid")
    expected_refs = {item.ref for item in items}
    states_by_ref: dict[str, str] = {}
    for raw in raw_results:
        if not isinstance(raw, Mapping) or set(raw) != {"ref", "state"}:
            raise ValueError("malignancy result item invalid")
        ref = raw.get("ref")
        state = raw.get("state")
        if (
            not isinstance(ref, str)
            or ref not in expected_refs
            or ref in states_by_ref
            or state not in _ALLOWED_ITEM_STATES
        ):
            raise ValueError("malignancy result reference invalid")
        states_by_ref[ref] = state
    if set(states_by_ref) != expected_refs:
        raise ValueError("malignancy result references incomplete")
    states = set(states_by_ref.values())
    if "explicit_malignant" in states:
        return MalignancyResolution("confirmed", "malignancy_confirmed")
    if "uncertain" in states:
        return MalignancyResolution("unknown", "malignancy_semantics_uncertain")
    return MalignancyResolution("absent", "malignancy_absent_complete")


def _prompt(items: Sequence[_DiagnosisItem]) -> str:
    safe_items = [
        {
            "ref": item.ref,
            "source_kind": item.source_kind,
            "diagnosis_name": item.name,
            "diagnosis_code": item.code,
        }
        for item in items
    ]
    return (
        "你只负责逐条判断诊断是否明确恶性，不输出质控结论。"
        "不得依据患者身份、坐标或文书编号推断。\n"
        f"schema_version固定为{SCHEMA_VERSION}。每个输入ref必须恰好返回一次，"
        "state只允许explicit_malignant、explicit_nonmalignant、uncertain。"
        "疑似、待排、占位、肿物、性质待定必须返回uncertain。\n"
        "只能输出一个JSON对象，禁止输出顶层数组、Markdown、解释或额外字段。"
        "输出结构示例："
        f'{{"schema_version":"{SCHEMA_VERSION}","results":['
        '{"ref":"D01","state":"explicit_nonmalignant"}]}.\n'
        "输入：" + json.dumps(safe_items, ensure_ascii=False, separators=(",", ":"))
    )


class MalignancyFactResolver:
    """单个质控请求内共享；相同病例最多执行一次语义分类。"""

    def __init__(self, llm_client: MalignancyLLMClient | None) -> None:
        self._llm_client = llm_client
        self._resolution: MalignancyResolution | None = None
        self._usage = MalignancyUsage()
        self._usage_claimed = False

    async def resolve(
        self, sources: Sequence[MalignancySource]
    ) -> MalignancyResolution:
        if self._resolution is not None:
            return self._resolution
        if not sources or any(source.state == "error" for source in sources):
            self._resolution = MalignancyResolution(
                "technical_error", "malignancy_source_query_error"
            )
            return self._resolution
        required_source_incomplete = any(
            source.required_for_absence
            and source.state in {"unavailable", "truncated", "missing"}
            for source in sources
        )

        items: list[_DiagnosisItem] = []
        unreadable_row = False
        diagnosis_index = pathology_index = 0
        for source in sources:
            source_kind = (
                "pathology" if source.source_key == "pathology_exam_report" else "diagnosis"
            )
            for row in source.rows:
                if source_kind == "pathology":
                    pathology_index += 1
                    index = pathology_index
                else:
                    diagnosis_index += 1
                    index = diagnosis_index
                item = _diagnosis_item(row, source_kind=source_kind, index=index)
                if item is None:
                    unreadable_row = True
                else:
                    items.append(item)
        if not items and required_source_incomplete:
            self._resolution = MalignancyResolution(
                "unknown", "malignancy_source_unavailable"
            )
            return self._resolution
        if unreadable_row or not items:
            self._resolution = MalignancyResolution(
                "unknown", "malignancy_diagnosis_content_missing"
            )
            return self._resolution
        if any(_MALIGNANT_CODE.fullmatch(item.code) for item in items):
            self._resolution = MalignancyResolution(
                "confirmed", "malignancy_confirmed_by_code"
            )
            return self._resolution
        if all(
            item.code
            and not _UNCERTAIN_NEOPLASM_CODE.match(item.code)
            and not item.name
            for item in items
        ):
            self._resolution = (
                MalignancyResolution("unknown", "malignancy_source_unavailable")
                if required_source_incomplete
                else MalignancyResolution(
                    "absent", "malignancy_absent_by_complete_codes"
                )
            )
            return self._resolution
        if self._llm_client is None:
            self._resolution = MalignancyResolution(
                "technical_error", "malignancy_llm_unavailable"
            )
            return self._resolution
        try:
            response = await self._llm_client.generate(
                _prompt(items),
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                allow_length_retry=False,
            )
            self._usage = _strict_usage(response)
            parsed = _parse_resolution(response, items=items)
            self._resolution = (
                MalignancyResolution("unknown", "malignancy_source_unavailable")
                if parsed.state == "absent" and required_source_incomplete
                else parsed
            )
        except Exception:
            self._resolution = MalignancyResolution(
                "technical_error", "malignancy_llm_invalid"
            )
        return self._resolution

    def claim_usage(self) -> MalignancyUsage:
        if self._usage_claimed:
            return MalignancyUsage()
        self._usage_claimed = True
        return self._usage
