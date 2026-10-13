from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import llm_prompt_privacy as privacy


class Capture:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {"content": "{}"}


@pytest.mark.asyncio
async def test_known_unlabelled_patient_name_blocks_before_delegate():
    delegate = Capture()
    with pytest.raises(RuntimeError):
        client = privacy.wrap_luxian_0609_llm_client(
            delegate, identity_values=("张三", "SYN-PATIENT-12")
        )
        await client.generate("拟为张三实施手术。")
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_existing_redaction_can_remove_identity_before_residue_check():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("张三",))
    await client.generate(
        "患者张三,性别男,年龄60岁，拟行手术。", max_completion_tokens=512
    )
    assert delegate.calls == [
        (
            "患者[患者姓名已脱敏],性别男,年龄60岁，拟行手术。",
            {"max_completion_tokens": 512},
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"system": "请先阅读张三的记录"},
        {"messages": [{"role": "user", "content": "张三"}]},
        {"metadata": {"张三": "value"}},
        {"extra_body": {"payload": json.dumps({"name": "张三"}, ensure_ascii=True)}},
        {
            "extra_body": {
                "payload": json.dumps(json.dumps({"name": "张三"}, ensure_ascii=True))
            }
        },
        {"extra_body": {"payload": r"前缀\u5f20\u4e09后缀"}},
    ],
)
async def test_known_identity_in_kwargs_is_rejected_without_forwarding(payload):
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("张三",))
    with pytest.raises(privacy.PatientPrivacyViolation):
        await client.generate("普通医学内容。", **payload)
    assert delegate.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", [1, 2, 4, 8])
async def test_json_escaped_identity_is_checked_at_bounded_nested_levels(depth):
    text = "张三"
    for _ in range(depth):
        text = json.dumps(text, ensure_ascii=True)
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("张三",))
    with pytest.raises(privacy.PatientPrivacyViolation):
        await client.generate(text)
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_known_numeric_identifier_is_not_blindly_deleted_from_medical_content():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("130",))
    with pytest.raises(privacy.PatientPrivacyViolation):
        await client.generate("剂量 130 mg。")
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_medical_content_and_kwargs_unchanged_when_known_identity_absent():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(
        delegate, identity_values=("张三", "SYN-P-12")
    )
    text = "130mg d1，SpO2 96%，T12骨折；患者高热，待复查。"
    kwargs = {
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "metadata": {"trace": "safe"},
    }
    await client.generate(text, **kwargs)
    assert delegate.calls == [(text, kwargs)]


@pytest.mark.asyncio
async def test_identity_provider_is_request_local_and_called_on_each_generate():
    values = ["张三"]
    provider_calls = []

    def provider():
        provider_calls.append(1)
        return tuple(values)

    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_provider=provider)
    await client.generate("李四的记录。")
    values[:] = ["李四"]
    with pytest.raises(privacy.PatientPrivacyViolation):
        await client.generate("李四的记录。")
    assert len(provider_calls) == 2
    assert len(delegate.calls) == 1


@pytest.mark.asyncio
async def test_two_case_contexts_do_not_share_identities():
    first = Capture()
    second = Capture()
    a = privacy.wrap_luxian_0609_llm_client(first, identity_values=("张三",))
    b = privacy.wrap_luxian_0609_llm_client(second, identity_values=("李四",))
    await a.generate("李四的记录。")
    await b.generate("张三的记录。")
    with pytest.raises(privacy.PatientPrivacyViolation):
        await a.generate("张三的记录。")
    assert len(first.calls) == len(second.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("generator_failure", [False, True])
async def test_provider_failures_are_sanitized_and_block_the_delegate(
    generator_failure,
):
    secret = "SYN-PATIENT-SECRET"

    def provider():
        if not generator_failure:
            raise RuntimeError(secret)

        def broken():
            yield "张三"
            raise RuntimeError(secret)

        return broken()

    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_provider=provider)
    with pytest.raises(privacy.PrivacyIdentityContextError) as caught:
        await client.generate("普通内容。")
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)
    assert caught.value.__suppress_context__
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_violation_and_wrapper_repr_do_not_contain_private_values_or_prompt():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(
        delegate, identity_values=("张三", "SYN-P-12")
    )
    prompt = "患者原始正文内提到张三。"
    with pytest.raises(privacy.PatientPrivacyViolation) as caught:
        await client.generate(prompt)
    for rendered in (str(caught.value), repr(caught.value), repr(client)):
        assert (
            "张三" not in rendered
            and "SYN-P-12" not in rendered
            and prompt not in rendered
        )
    assert delegate.calls == []


@pytest.mark.asyncio
async def test_rewrapping_keeps_existing_static_and_provider_contexts():
    delegate = Capture()
    old = privacy.wrap_luxian_0609_llm_client(
        delegate, identity_values=("张三",), identity_provider=lambda: ("SYN-OLD",)
    )
    new = privacy.wrap_luxian_0609_llm_client(
        old, identity_values=("李四",), identity_provider=lambda: ("SYN-NEW",)
    )
    assert privacy.wrap_luxian_0609_llm_client(new) is new
    for text in ("张三", "李四", "SYN-OLD", "SYN-NEW"):
        with pytest.raises(privacy.PatientPrivacyViolation):
            await new.generate(text)
    assert delegate.calls == []


def test_none_and_empty_legacy_context_remain_compatible():
    assert privacy.wrap_luxian_0609_llm_client(None, identity_values=("张三",)) is None


@pytest.mark.parametrize(
    "text", ["130mg", "1.5mg", "-1", "SYN-P-12", "Patient", "PD-1", "T1/T2"]
)
def test_ascii_identity_matches_complete_token_not_other_medical_values(text):
    privacy.assert_no_known_identity(text, ("1", "P"))


@pytest.mark.parametrize(
    "payload", ["标识 1", {"visit_id": 1}, {"patient_id": "P"}, "患者号：P。"]
)
def test_complete_short_identifier_is_still_rejected(payload):
    with pytest.raises(privacy.PatientPrivacyViolation):
        privacy.assert_no_known_identity(payload, ("1", "P"))


def test_public_gate_decodes_surrogate_pair_json_unicode_without_mutating_request():
    request = {"body": r"说明\ud842\udfb7野"}
    with pytest.raises(privacy.PatientPrivacyViolation):
        privacy.assert_no_known_identity(request, ("𠮷野",))
    assert request == {"body": r"说明\ud842\udfb7野"}


def test_excessive_nested_string_encoding_is_rejected_instead_of_skipped():
    text = "张三"
    for _ in range(12):
        text = json.dumps(text, ensure_ascii=True)
    with pytest.raises(privacy.PrivacyIdentityContextError):
        privacy.assert_no_known_identity(text, ("张三",))


def test_identity_values_generator_failure_has_no_private_exception_message():
    def values():
        yield "张三"
        raise RuntimeError("secret-patient-data")

    with pytest.raises(privacy.PrivacyIdentityContextError) as caught:
        privacy.assert_no_known_identity("正文", values())
    assert "secret-patient-data" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_cyclic_request_is_safely_rejected_without_repr():
    request = {}
    request["loop"] = request
    with pytest.raises(privacy.PrivacyIdentityContextError):
        privacy.assert_no_known_identity(request, ("张三",))


@pytest.mark.asyncio
async def test_wrapper_accepts_numeric_model_settings_and_actual_schema_constraints():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("1",))
    kwargs = {
        "temperature": 1,
        "max_completion_tokens": 1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "facts",
                "schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "items": {"type": "integer", "minimum": 1},
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
    }
    await client.generate("仅医学内容。", **kwargs)
    assert delegate.calls == [("仅医学内容。", kwargs)]


def _schema_request(schema):
    return {
        "response_format": {"type": "json_schema", "json_schema": {"schema": schema}}
    }


@pytest.mark.parametrize(
    "keyword",
    [
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "minProperties",
        "maxProperties",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    ],
)
def test_numeric_schema_constraints_only_in_recognized_schema_position(keyword):
    payload = _schema_request({"type": "array", keyword: 1})
    snapshot = json.dumps(payload)
    privacy.assert_no_known_identity_in_model_request(payload, ("1",))
    assert json.dumps(payload) == snapshot
    with pytest.raises(privacy.PatientPrivacyViolation):
        privacy.assert_no_known_identity(payload, ("1",))


@pytest.mark.parametrize(
    "payload",
    [
        {"metadata": {"temperature": 1}},
        {"messages": [{"content": {"minItems": 1}}]},
        {"unknown_setting": 1},
        {"temperature": "1"},
        {
            "response_format": {
                "type": "json_object",
                "json_schema": {"schema": {"minItems": 1}},
            }
        },
        {
            "metadata": {
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"schema": {"minItems": 1}},
                }
            }
        },
        _schema_request({"minItems": "1"}),
        _schema_request({"default": 1}),
        _schema_request({"const": 1}),
        _schema_request({"enum": [1]}),
        _schema_request({"examples": [1]}),
        _schema_request({"description": "患者号1"}),
        _schema_request({"properties": {"minItems": {"const": 1}}}),
        _schema_request({"properties": {"minItems": 1}}),
        _schema_request({"examples": [{"minimum": 1}]}),
    ],
)
def test_technical_numeric_projection_does_not_exempt_content_or_unknown_fields(
    payload,
):
    with pytest.raises(privacy.PatientPrivacyViolation):
        privacy.assert_no_known_identity_in_model_request(payload, ("1",))


def test_schema_compositions_allow_constraints_without_suppressing_schema_field_names():
    schema = {
        "$defs": {"count": {"minimum": 1}},
        "allOf": [{"properties": {"count": {"minimum": 1}}}],
        "if": {"minProperties": 1},
        "then": {"maxProperties": 1},
    }
    privacy.assert_no_known_identity_in_model_request(_schema_request(schema), ("1",))
    schema["properties"] = {"1": {"minimum": 1}}
    with pytest.raises(privacy.PatientPrivacyViolation):
        privacy.assert_no_known_identity_in_model_request(
            _schema_request(schema), ("1",)
        )


@pytest.mark.asyncio
async def test_wrapper_checks_original_prompt_even_if_kwargs_also_contains_messages():
    delegate = Capture()
    client = privacy.wrap_luxian_0609_llm_client(delegate, identity_values=("张三",))
    with pytest.raises(privacy.PatientPrivacyViolation):
        await client.generate("张三", messages=[{"content": "安全文本"}], temperature=1)
    assert delegate.calls == []
