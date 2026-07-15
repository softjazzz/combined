"""LX0609 规则族执行器注册表。

注册表只负责 ``executor_key`` 到执行器的解析和依赖声明，不读取数据库，
也不包含任何临床规则分支。
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import math
import re
from typing import Any, Awaitable, Callable, Iterable, Protocol, TYPE_CHECKING

from .evidence_material import Luxian0609EvidenceMaterialStore
from .execution_contract import FamilyExecutionEnvelope

if TYPE_CHECKING:
    from .engine import FamilyExecutionContext


_EXECUTOR_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class Luxian0609FamilyExecutor(Protocol):
    async def evaluate(
        self,
        context: FamilyExecutionContext,
    ) -> FamilyExecutionEnvelope:
        """执行一个规则族；临床结果契约由后续 exactly-once 层校验。"""


@dataclass(frozen=True)
class ExecutorRegistration:
    executor_key: str
    executor: Luxian0609FamilyExecutor
    depends_on: tuple[str, ...] = ()
    deadline_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.executor_key, str) or not _EXECUTOR_KEY_PATTERN.fullmatch(
            self.executor_key
        ):
            raise ValueError("invalid executor_key")
        if not callable(getattr(self.executor, "evaluate", None)):
            raise TypeError("executor must provide evaluate")
        if (
            not isinstance(self.depends_on, tuple)
            or len(self.depends_on) != len(set(self.depends_on))
            or any(
                not isinstance(item, str)
                or not _EXECUTOR_KEY_PATTERN.fullmatch(item)
                or item == self.executor_key
                for item in self.depends_on
            )
        ):
            raise ValueError("invalid executor dependency")
        if self.deadline_seconds is not None and (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, (int, float))
            or not math.isfinite(self.deadline_seconds)
            or self.deadline_seconds <= 0
        ):
            raise ValueError("deadline_seconds must be positive")


class Luxian0609ExecutorRegistry:
    """进程内不可猜测的执行器注册表；重复和未知 key 均 fail-closed。"""

    def __init__(
        self,
        registrations: Iterable[ExecutorRegistration] = (),
    ) -> None:
        self._registrations: dict[str, ExecutorRegistration] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: ExecutorRegistration) -> None:
        if not isinstance(registration, ExecutorRegistration):
            raise TypeError("registration must be ExecutorRegistration")
        if registration.executor_key in self._registrations:
            raise ValueError("duplicate executor_key")
        self._registrations[registration.executor_key] = registration

    def resolve(self, executor_key: str) -> ExecutorRegistration:
        normalized = str(executor_key or "").strip()
        try:
            return self._registrations[normalized]
        except KeyError:
            raise KeyError("unregistered executor_key") from None

    @property
    def executor_keys(self) -> tuple[str, ...]:
        return tuple(self._registrations)


# 冻结现有正式链调用顺序。规则目录顺序与模型调用顺序不同，迁移期不可互换。
LEGACY_NATIVE_EXECUTION_ORDER = (
    "surgery_presence",
    "basic_timeliness",
    "exam_lab",
    "consultation_quality",
    "transfusion",
    "tumor_pathology",
    "course_quality",
    "surgery_gate",
    "surgery_document",
    "surgery_mdt",
)

# 第一批可由现有 bounded snapshot 投影完整承载的请求内材料来源。
LEGACY_EXECUTOR_MATERIAL_SOURCE_KEYS = {
    "consultation_quality": (
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
    ),
    "surgery_mdt": (
        "mr_surgery",
        "presurg_discussion",
        "consultation_record",
    ),
}


def resolve_legacy_executor_material_source_keys(
    executor_keys: Iterable[str],
) -> tuple[str, ...]:
    """按物理 source 去重，供一次性 read-session 预取。"""

    requested = tuple(executor_keys)
    return tuple(
        sorted(
            {
                source_key
                for executor_key in requested
                for source_key in LEGACY_EXECUTOR_MATERIAL_SOURCE_KEYS.get(
                    executor_key, ()
                )
            }
        )
    )


@dataclass(frozen=True)
class LegacyFamilyExecutionResources:
    """迁移期请求级私有资源；不得序列化进客户结果或 trace。"""

    wrapper_rules: tuple[dict[str, Any], ...]
    evidence_payload: dict[str, Any] | None
    institute_id: str
    patient_id: str
    visit_id: str
    source_schema: str | None
    llm_client: Any
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None


@dataclass(frozen=True)
class LegacyNativeExecutorFunctions:
    surgery_presence: Callable[..., Any]
    basic_timeliness: Callable[..., Any]
    exam_lab: Callable[..., Any]
    consultation_quality: Callable[..., Any]
    transfusion: Callable[..., Any]
    tumor_pathology: Callable[..., Any]
    course_quality: Callable[..., Any]
    surgery_gate: Callable[..., Any]
    surgery_document: Callable[..., Any]
    surgery_mdt: Callable[..., Any]


@dataclass(frozen=True)
class _RequestScopedExecutor:
    callback: Callable[[FamilyExecutionContext], Awaitable[FamilyExecutionEnvelope]]

    async def evaluate(
        self,
        context: FamilyExecutionContext,
    ) -> FamilyExecutionEnvelope:
        return await self.callback(context)


async def _resolve_call(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _to_envelope(
    raw: Any,
    *,
    selected_rule_ids: tuple[str, ...],
    single_result: bool = False,
) -> FamilyExecutionEnvelope:
    results = (getattr(raw, "result"),) if single_result else tuple(getattr(raw, "results"))
    planned_rule_ids = (
        selected_rule_ids
        if single_result
        else tuple(getattr(raw, "planned_rule_ids"))
    )
    return FamilyExecutionEnvelope(
        results=results,
        planned_rule_ids=planned_rule_ids,
        llm_call_count=int(getattr(raw, "llm_call_count", 0) or 0),
        prompt_tokens=int(getattr(raw, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(raw, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(raw, "total_tokens", 0) or 0),
        api_time=float(getattr(raw, "api_time", 0.0) or 0.0),
    )


def build_luxian_0609_legacy_executor_registry(
    *,
    resources: LegacyFamilyExecutionResources,
    functions: LegacyNativeExecutorFunctions,
) -> Luxian0609ExecutorRegistry:
    """把现有10族函数薄适配为统一信封；不修改临床逻辑和模型输入。"""

    wrappers = list(resources.wrapper_rules)

    async def surgery_presence(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.surgery_presence(
                rule_ids=context.selected_rule_ids,
                visit_id=resources.visit_id,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                source_schema=resources.source_schema,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def basic_timeliness(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.basic_timeliness(
                rule_ids=context.selected_rule_ids,
                evidence_payload=resources.evidence_payload,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def exam_lab(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.exam_lab(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def consultation(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.consultation_quality(
                rule_ids=context.selected_rule_ids,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
                evidence_materials=resources.evidence_materials,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def transfusion(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.transfusion(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def tumor_pathology(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.tumor_pathology(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def course_quality(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.course_quality(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def surgery_gate(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.surgery_gate(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def surgery_document(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.surgery_document(
                rule_ids=context.selected_rule_ids,
                wrapper_rules=wrappers,
                evidence_payload=resources.evidence_payload,
                llm_client=resources.llm_client,
            )
        )
        return _to_envelope(raw, selected_rule_ids=context.selected_rule_ids)

    async def surgery_mdt(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
        raw = await _resolve_call(
            functions.surgery_mdt(
                institute_id=resources.institute_id,
                patient_id=resources.patient_id,
                visit_id=resources.visit_id,
                source_schema=resources.source_schema,
                llm_client=resources.llm_client,
                evidence_materials=resources.evidence_materials,
            )
        )
        return _to_envelope(
            raw,
            selected_rule_ids=context.selected_rule_ids,
            single_result=True,
        )

    callbacks = {
        "surgery_presence": surgery_presence,
        "basic_timeliness": basic_timeliness,
        "exam_lab": exam_lab,
        "consultation_quality": consultation,
        "transfusion": transfusion,
        "tumor_pathology": tumor_pathology,
        "course_quality": course_quality,
        "surgery_gate": surgery_gate,
        "surgery_document": surgery_document,
        "surgery_mdt": surgery_mdt,
    }
    from .rule_contracts import load_luxian_0609_rule_contracts

    contract_keys = {item.executor_key for item in load_luxian_0609_rule_contracts()}
    if set(callbacks) != contract_keys:
        raise ValueError("LX0609 executor registry does not match rule contracts")
    return Luxian0609ExecutorRegistry(
        ExecutorRegistration(
            executor_key=executor_key,
            executor=_RequestScopedExecutor(callbacks[executor_key]),
        )
        for executor_key in LEGACY_NATIVE_EXECUTION_ORDER
    )
