"""0609 结构化事实抽取的模型输出约束。

thinking 模式下模型偶尔把推理写进正文、JSON 前夹带分析，严格解析器会整批
拒收。客户端声明支持结构化输出时关闭 thinking；不附加 json_object 约束：
真实验证中 json_object 与关闭 thinking 叠加会让模型输出空的事实对象 {}。
不支持的客户端（含测试替身）参数保持不变，解析器始终严格、不放宽。
"""

from __future__ import annotations

from typing import Any


def structured_output_kwargs(llm_client: Any) -> dict[str, Any]:
    capability = getattr(llm_client, "supports_strict_json_schema", None)
    try:
        supported = bool(capability()) if callable(capability) else False
    except Exception:
        supported = False
    if not supported:
        return {}
    return {"enable_thinking": False}
