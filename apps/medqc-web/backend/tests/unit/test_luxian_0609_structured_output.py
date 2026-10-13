"""0609 抽取器的结构化输出参数：只对声明能力的正式客户端关闭 thinking。"""
from __future__ import annotations

from app.services.luxian_0609.structured_output import structured_output_kwargs


class _Capable:
    def supports_strict_json_schema(self):
        return True


class _Incapable:
    def supports_strict_json_schema(self):
        return False


class _Broken:
    def supports_strict_json_schema(self):
        raise RuntimeError("capability probe failed")


def test_capable_client_disables_thinking_without_json_object_constraint():
    # json_object 与关闭 thinking 叠加会让真实模型输出空事实对象，因此不附加。
    assert structured_output_kwargs(_Capable()) == {"enable_thinking": False}


def test_other_clients_keep_default_kwargs():
    for client in (_Incapable(), _Broken(), object(), None):
        assert structured_output_kwargs(client) == {}
