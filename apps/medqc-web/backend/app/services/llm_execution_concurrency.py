"""模型质控执行并发合同。

模型配置负责持久化这三个全局上限；任务可以申请更低的病历并发，不能突破这里的系统值。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ..core.settings import Settings, get_settings


EXECUTION_CONCURRENCY_KEY = "execution_concurrency"
_LEGACY_MAX_PARALLEL_RECORDS = 16
_LEGACY_FAMILY_MAX_CONCURRENCY = 4
_LEGACY_HTTP_MAX_CONCURRENCY = 40


@dataclass(frozen=True)
class LLMExecutionConcurrency:
    max_parallel_records: int
    family_max_concurrency: int
    http_max_concurrency: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _bounded_integer(*, value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} 必须是整数")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def default_llm_execution_concurrency(
    settings: Settings | None = None,
) -> LLMExecutionConcurrency:
    current = settings or get_settings()
    return LLMExecutionConcurrency(
        max_parallel_records=int(
            getattr(
                current,
                "QC_BATCH_RECORD_MAX_CONCURRENCY",
                _LEGACY_MAX_PARALLEL_RECORDS,
            )
        ),
        family_max_concurrency=int(
            getattr(
                current,
                "LUXIAN_0609_FAMILY_MAX_CONCURRENCY",
                _LEGACY_FAMILY_MAX_CONCURRENCY,
            )
        ),
        http_max_concurrency=int(
            getattr(
                current,
                "LLM_HTTP_MAX_CONCURRENCY",
                _LEGACY_HTTP_MAX_CONCURRENCY,
            )
        ),
    )


def capture_llm_execution_concurrency(
    client: Any,
    *,
    settings: Settings | None = None,
) -> LLMExecutionConcurrency:
    """从未包装客户端冻结一次执行策略；旧客户端缺字段时保持原默认。"""

    defaults = default_llm_execution_concurrency(settings)
    return resolve_llm_execution_concurrency(
        {
            "max_parallel_records": getattr(
                client,
                "max_parallel_records",
                defaults.max_parallel_records,
            ),
            "family_max_concurrency": getattr(
                client,
                "family_max_concurrency",
                defaults.family_max_concurrency,
            ),
            "http_max_concurrency": getattr(
                client,
                "http_max_concurrency",
                defaults.http_max_concurrency,
            ),
        },
        settings=settings,
    )


def resolve_llm_execution_concurrency(
    value: Mapping[str, Any] | None,
    *,
    settings: Settings | None = None,
) -> LLMExecutionConcurrency:
    defaults = default_llm_execution_concurrency(settings)
    raw = dict(value or {})
    return LLMExecutionConcurrency(
        max_parallel_records=_bounded_integer(
            value=raw.get("max_parallel_records", defaults.max_parallel_records),
            name="同时处理病历数",
            minimum=1,
            maximum=32,
        ),
        family_max_concurrency=_bounded_integer(
            value=raw.get("family_max_concurrency", defaults.family_max_concurrency),
            name="单病历规则族并发",
            minimum=1,
            maximum=4,
        ),
        http_max_concurrency=_bounded_integer(
            value=raw.get("http_max_concurrency", defaults.http_max_concurrency),
            name="模型 HTTP 槽位",
            minimum=1,
            maximum=64,
        ),
    )


def concurrency_from_custom_parameters(
    custom_parameters: Mapping[str, Any] | None,
    *,
    settings: Settings | None = None,
) -> LLMExecutionConcurrency:
    params = dict(custom_parameters or {})
    raw = params.get(EXECUTION_CONCURRENCY_KEY)
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError("execution_concurrency 必须是对象")
    return resolve_llm_execution_concurrency(raw, settings=settings)


def with_execution_concurrency_defaults(
    custom_parameters: Mapping[str, Any] | None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    params = dict(custom_parameters or {})
    params[EXECUTION_CONCURRENCY_KEY] = concurrency_from_custom_parameters(
        params,
        settings=settings,
    ).as_dict()
    return params
