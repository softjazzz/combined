from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx


_PERSON_NAME = r"(?:[\u4e00-\u9fff·]{2,12}|[A-Za-z][A-Za-z .'-]{1,48})"
_CLINICIAN_NAME_LABEL = re.compile(
    rf"(?P<label>(?:主治医师|主任医师|住院医师|会诊医师|记录医师|经治医师|"
    rf"手术医师|麻醉医师|医师|医生|护士|术者|主刀)[ \t]*(?:姓名)?[ \t]*[:：][ \t]*)"
    rf"(?P<value>{_PERSON_NAME})"
)
_PATIENT_NAME_LABEL = re.compile(
    rf"(?P<label>(?:患者姓名|病人姓名|患者名字|病人名字|姓名)[ \t]*[:：][ \t]*)"
    rf"(?P<value>{_PERSON_NAME})"
)
_COMMON_SURNAME = (
    r"(?:欧阳|司马|上官|诸葛|东方|夏侯|尉迟|公孙|慕容|令狐|"
    r"[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    r"戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费"
    r"廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和"
    r"穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴宋茅庞熊纪舒屈项祝董梁杜阮"
    r"蓝闵席季麻强贾路娄危江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡凌霍虞万支"
    r"柯管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包左石崔吉龚程邢裴陆荣翁荀"
    r"羊於惠甄曲家封芮储靳邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班"
    r"仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白"
    r"怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵"
    r"冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀浦尚农温庄晏柴瞿阎充连习艾鱼容向"
    r"古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧沃利蔚越夔隆师巩"
    r"厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺"
    r"权逯盖益桓公])"
)
# 仅识别人口学标签及明确性别值；不把“性别相关”等医疗叙述当身份依据。
_LABELLED_SEX = r"性别[ \t]*[:：]?[ \t]*[男女](?=[\s，,、；;。\"}]|$)"
_PATIENT_INTRO = re.compile(
    rf"(?P<label>(?:患者|病人|患儿)\s*)"
    rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    rf"(?=(?:\s*[，,、]\s*(?:{_LABELLED_SEX}|男|女|年龄|\d{{1,3}}\s*岁|因)|\s*因))"
)
_DEMOGRAPHIC_NAME = re.compile(
    rf"(?P<label>(?:(?<=^)|(?<=[\n\r；;。：:]))[ \t]*"
    rf"(?:(?:[一二三四五六七八九十]+|\d+)[、.．][ \t]*)?)"
    rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    rf"(?=[ \t]*[，,、][ \t]*(?:{_LABELLED_SEX}|(?:老年|中年|青年|成年|幼年)[男女]性|男|女|\d{{1,3}}[ \t]*岁|年龄))",
    flags=re.MULTILINE,
)
_CONTACT_NAME = re.compile(
    rf"(?P<label>(?:联系人|家属)(?:姓名)?[ \t]*[:：][ \t]*)"
    rf"(?P<value>{_PERSON_NAME})"
)
_ID_CARD = re.compile(r"(?<![0-9A-Za-z])(?:\d{17}[0-9Xx]|\d{15})(?![0-9A-Za-z])")
_MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_LANDLINE = re.compile(r"(?<!\d)0\d{2,3}[\-－]?\d{7,8}(?!\d)")
_LABELLED_PHONE = re.compile(
    r"(?P<label>(?:联系人电话|联系电话|联系手机|手机号码|手机号|家庭电话|"
    r"现住址电话|工作单位电话|电话)[ \t]*[:：][ \t]*)"
    r"(?P<value>[+＋()（）0-9\-－ \t]{6,28})"
)
# 自由文本取值止于换行、分号、JSON 转义序列（\n、\" 等）和裸引号：正文常以 JSON
# 字符串嵌入 prompt，发送包装器会对整段 prompt 再脱敏一次，不能越过转义换行吞掉
# 后续正文和 JSON 结构；已是脱敏占位符的取值不再重复匹配，保证二次脱敏幂等。
_FREE_TEXT_CHAR = r'(?:(?!\\[\\"/bfnrtu])[^\n\r；;"])'
_ALREADY_REDACTED = r"(?!\[[^\]\n]{1,16}已脱敏\])"
_ADDRESS = re.compile(
    r"(?P<label>(?:现住址|家庭住址|户籍地址|通讯地址|联系地址|联系人地址|"
    r"工作单位地址|详细地址|地址)\s*[:：]\s*)"
    rf"(?P<value>{_ALREADY_REDACTED}{_FREE_TEXT_CHAR}{{2,160}})"
)
_MEDICAL_IDENTIFIER = re.compile(
    r"(?P<label>(?:住院号|病历号|门诊号|就诊号|医保号|社保号|患者ID|"
    r"patient_id|visit_id|mr_no)"
    r"\s*[:：=]\s*)"
    r"(?P<value>[^\s，,；;\]\[}\{]{2,80})",
    flags=re.IGNORECASE,
)
_BIRTH_DATE = re.compile(
    r"(?P<label>(?:出生日期|出生年月|生日)\s*[:：]\s*)"
    r"(?P<value>\d{4}(?:[-/.年]\d{1,2})?(?:[-/.月]\d{1,2}日?)?)"
)
_WORK_UNIT = re.compile(
    r"(?P<label>(?:工作单位|单位名称)\s*[:：]\s*)"
    rf"(?P<value>{_ALREADY_REDACTED}{_FREE_TEXT_CHAR}{{2,120}})"
)
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9._%+-])"
)

_PATIENT_NAME_PLACEHOLDER = "[患者姓名已脱敏]"
_CONTACT_NAME_PLACEHOLDER = "[联系人姓名已脱敏]"


def _replace_labelled(pattern: re.Pattern[str], text: str, placeholder: str) -> str:
    return pattern.sub(
        lambda match: f"{match.group('label')}{placeholder}",
        text,
    )


def _protect_clinician_names(text: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    protected: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        marker = f"__LX0609_CLINICIAN_NAME_{len(protected)}__"
        protected.append((marker, match.group(0)))
        return marker

    return _CLINICIAN_NAME_LABEL.sub(_replace, text), tuple(protected)


def redact_luxian_0609_patient_privacy(prompt: str) -> str:
    """删除LX0609模型prompt中的患者身份信息，保留医疗事实和医务人员姓名。"""

    if not isinstance(prompt, str):
        raise TypeError("prompt must be str")
    protected_prompt, protected_clinicians = _protect_clinician_names(prompt)
    patient_names = {
        match.group("value").strip()
        for pattern in (_PATIENT_NAME_LABEL, _PATIENT_INTRO, _DEMOGRAPHIC_NAME)
        for match in pattern.finditer(protected_prompt)
    }
    contact_names = {
        match.group("value").strip()
        for match in _CONTACT_NAME.finditer(protected_prompt)
    }

    redacted = _replace_labelled(
        _PATIENT_NAME_LABEL,
        protected_prompt,
        _PATIENT_NAME_PLACEHOLDER,
    )
    redacted = _replace_labelled(
        _PATIENT_INTRO,
        redacted,
        _PATIENT_NAME_PLACEHOLDER,
    )
    redacted = _replace_labelled(
        _DEMOGRAPHIC_NAME,
        redacted,
        _PATIENT_NAME_PLACEHOLDER,
    )
    redacted = _replace_labelled(
        _CONTACT_NAME,
        redacted,
        _CONTACT_NAME_PLACEHOLDER,
    )
    for name in sorted(patient_names, key=len, reverse=True):
        redacted = redacted.replace(name, _PATIENT_NAME_PLACEHOLDER)
    for name in sorted(contact_names, key=len, reverse=True):
        redacted = redacted.replace(name, _CONTACT_NAME_PLACEHOLDER)
    redacted = _ID_CARD.sub("[身份证号已脱敏]", redacted)
    redacted = _MOBILE.sub("[手机号已脱敏]", redacted)
    redacted = _LANDLINE.sub("[座机号码已脱敏]", redacted)
    redacted = _replace_labelled(_LABELLED_PHONE, redacted, "[电话号码已脱敏]")
    redacted = _replace_labelled(_ADDRESS, redacted, "[地址已脱敏]")
    redacted = _replace_labelled(_BIRTH_DATE, redacted, "[出生日期已脱敏]")
    redacted = _replace_labelled(_WORK_UNIT, redacted, "[工作单位已脱敏]")
    redacted = _replace_labelled(
        _MEDICAL_IDENTIFIER,
        redacted,
        "[就诊标识已脱敏]",
    )
    redacted = _EMAIL.sub("[电子邮箱已脱敏]", redacted)
    for marker, original in protected_clinicians:
        redacted = redacted.replace(marker, original)
    return redacted


class PatientPrivacyViolation(RuntimeError):
    """已知患者身份仍存在于待发送内容；异常不得携带原值。"""


class PrivacyIdentityContextError(RuntimeError):
    """无法安全取得或核查本次身份上下文，禁止继续发送。"""


def _freeze_identity_values(values: Iterable[str]) -> tuple[str, ...]:
    try:
        if isinstance(values, (str, bytes)):
            raise TypeError
        unique = set()
        for value in values:
            if not isinstance(value, str):
                raise TypeError
            if value.strip():
                unique.add(value.strip())
        return tuple(sorted(unique, key=len, reverse=True))
    except Exception:
        raise PrivacyIdentityContextError(
            "Patient identity context is unavailable"
        ) from None


_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
# 正文常以 JSON 字符串嵌在 prompt 里，整段 prompt 不是合法 JSON；简单转义（如 \n）
# 紧贴身份值时会让 ASCII 标识的边界判断失效，核查时一并按解码后的文本比对。
_JSON_SIMPLE_ESCAPE = re.compile(r'\\([\\"/bfnrt])')
_JSON_SIMPLE_ESCAPE_VALUES = {
    "\\": "\\", '"': '"', "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
}


def _decode_json_simple_escapes(text: str) -> str:
    return _JSON_SIMPLE_ESCAPE.sub(lambda match: _JSON_SIMPLE_ESCAPE_VALUES[match.group(1)], text)
_MAX_DECODE_LAYERS = 8
_MAX_REQUEST_DEPTH = 32


def _contains_identity(text: str, identity: str) -> bool:
    if identity.isascii():
        # ASCII 标识必须是完整 token，避免患者号 1/P 命中 130、1.5、Patient。
        return (
            re.search(
                rf"(?<![A-Za-z0-9_.+\-]){re.escape(identity)}(?![A-Za-z0-9_.+\-])",
                text,
            )
            is not None
        )
    return identity in text


def _check_identity_residue(
    value: Any, identities: tuple[str, ...], depth: int = 0
) -> None:
    if depth > _MAX_REQUEST_DEPTH:
        raise PrivacyIdentityContextError("Model request cannot be checked safely")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_identity_residue(key, identities, depth + 1)
            _check_identity_residue(item, identities, depth + 1)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _check_identity_residue(item, identities, depth + 1)
        return
    if value is None:
        return
    if isinstance(value, (bool, int, float)):
        value = str(value)
    if not isinstance(value, str):
        # 不调用任意对象的 __str__/repr；不能核查的发送参数安全拒绝。
        raise PrivacyIdentityContextError("Model request cannot be checked safely")
    current = value
    for _ in range(_MAX_DECODE_LAYERS + 1):
        decoded = _UNICODE_ESCAPE.sub(
            lambda match: chr(int(match.group(1), 16)), current
        )
        decoded = re.sub(
            r"([\ud800-\udbff])([\udc00-\udfff])",
            lambda m: chr(0x10000 + ((ord(m[1]) - 0xD800) << 10) + ord(m[2]) - 0xDC00),
            decoded,
        )
        if any(
            _contains_identity(text, identity)
            for identity in identities
            for text in (current, decoded, _decode_json_simple_escapes(decoded))
        ):
            raise PatientPrivacyViolation("Patient identity remains in model request")
        try:
            parsed = json.loads(current)
        except (ValueError, TypeError):
            if decoded == current:
                return
            current = decoded
            continue
        if isinstance(parsed, str):
            if parsed == current:
                return
            current = parsed
            continue
        if isinstance(parsed, (dict, list)):
            _check_identity_residue(parsed, identities, depth + 1)
        return
    raise PrivacyIdentityContextError(
        "Model request encoding exceeds privacy check limit"
    )


def assert_no_known_identity(request: object, identity_values: Iterable[str]) -> None:
    """核查已知身份残留；只拒绝，不修改请求，也不在异常中暴露内容。"""
    identities = _freeze_identity_values(identity_values)
    if not identities:
        return
    try:
        _check_identity_residue(request, identities)
    except (PatientPrivacyViolation, PrivacyIdentityContextError):
        raise
    except Exception:
        raise PrivacyIdentityContextError(
            "Model request cannot be checked safely"
        ) from None


_MODEL_NUMERIC_PARAMETERS = frozenset(
    {
        "temperature",
        "top_p",
        "top_k",
        "max_tokens",
        "max_completion_tokens",
        "max_output_tokens",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "n",
        "timeout",
        "timeout_seconds",
    }
)
_SCHEMA_NUMERIC_CONSTRAINTS = frozenset(
    {
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
    }
)
_SCHEMA_MAP_CHILDREN = frozenset(
    {
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "dependentSchemas",
    }
)
_SCHEMA_SINGLE_CHILDREN = frozenset(
    {
        "items",
        "additionalProperties",
        "contains",
        "propertyNames",
        "not",
        "if",
        "then",
        "else",
        "unevaluatedProperties",
        "unevaluatedItems",
    }
)
_SCHEMA_ARRAY_CHILDREN = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})


def _schema_privacy_projection(schema: object, depth: int = 0) -> object:
    if depth > _MAX_REQUEST_DEPTH:
        raise PrivacyIdentityContextError("Model request cannot be checked safely")
    if not isinstance(schema, Mapping):
        return schema
    projected = {}
    for key, value in schema.items():
        if key in _SCHEMA_NUMERIC_CONSTRAINTS and type(value) in (int, float):
            projected[key] = None
        elif key in _SCHEMA_MAP_CHILDREN and isinstance(value, Mapping):
            projected[key] = {
                name: _schema_privacy_projection(child, depth + 1)
                for name, child in value.items()
            }
        elif key in _SCHEMA_SINGLE_CHILDREN:
            projected[key] = _schema_privacy_projection(value, depth + 1)
        elif key in _SCHEMA_ARRAY_CHILDREN and isinstance(value, (list, tuple)):
            projected[key] = [
                _schema_privacy_projection(child, depth + 1) for child in value
            ]
        else:
            # default/const/enum/examples 和未知字段是内容，不能豁免其数值。
            projected[key] = value
    return projected


def assert_no_known_identity_in_model_request(
    request: object, identity_values: Iterable[str]
) -> None:
    """区分模型技术数值与病例内容，只改变检查投影，不修改实际请求。"""
    identities = _freeze_identity_values(identity_values)
    if not identities:
        return
    try:
        projected = request
        if isinstance(request, Mapping):
            projected = dict(request)
            for key in _MODEL_NUMERIC_PARAMETERS:
                if type(projected.get(key)) in (int, float):
                    projected[key] = None
            response_format = request.get("response_format")
            if (
                isinstance(response_format, Mapping)
                and response_format.get("type") == "json_schema"
            ):
                envelope = response_format.get("json_schema")
                if isinstance(envelope, Mapping) and "schema" in envelope:
                    projected["response_format"] = {
                        **response_format,
                        "json_schema": {
                            **envelope,
                            "schema": _schema_privacy_projection(envelope["schema"]),
                        },
                    }
        assert_no_known_identity(projected, identities)
    except (PatientPrivacyViolation, PrivacyIdentityContextError):
        raise
    except Exception:
        raise PrivacyIdentityContextError(
            "Model request cannot be checked safely"
        ) from None


# 用户口径（2026-10-11）：0609 只做受控事实抽取，固定温度 0，减少同一输入的随机漂移。
EXTRACTION_TEMPERATURE = 0.0


def _accepts_temperature(delegate: Any) -> bool:
    """只在下游 generate 显式声明 temperature 参数时传入，不向未知客户端塞参数。"""
    try:
        return "temperature" in inspect.signature(delegate.generate).parameters
    except (TypeError, ValueError, AttributeError):
        return False


# 用户口径（2026-10-11）：网络/上游临时错误重试，间隔片刻；其余错误不重试。
# 用户口径（2026-10-12）：重试次数由 1 次增至 2 次（真实跑批中 SSL 断连重试 1 次仍偶发失败）。
TRANSPORT_RETRY_DELAY_SECONDS = 2.0
TRANSPORT_RETRY_ATTEMPTS = 2
_RETRYABLE_UPSTREAM_STATUS = re.compile(r"upstream_http_status=(?:429|5\d\d|unknown)(?!\w)")


def _is_transient_transport_error(error: BaseException) -> bool:
    """只认定超时、连接失败和上游 429/5xx；参数、隐私、4xx 等确定性错误不重试。"""
    if isinstance(error, (httpx.TransportError, TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True
    return (
        isinstance(error, RuntimeError)
        and str(error).startswith("upstream_http_error")
        and _RETRYABLE_UPSTREAM_STATUS.search(str(error)) is not None
    )


@dataclass(frozen=True)
class _Luxian0609PrivacyRedactingLLMClient:
    delegate: Any = field(repr=False)
    identity_values: tuple[str, ...] = field(default=(), repr=False)
    identity_providers: tuple[Callable[[], Iterable[str]], ...] = field(
        default=(), repr=False
    )

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        identities = set(self.identity_values)
        for provider in self.identity_providers:
            try:
                identities.update(_freeze_identity_values(provider()))
            except Exception:
                raise PrivacyIdentityContextError(
                    "Patient identity context is unavailable"
                ) from None
        redacted = redact_luxian_0609_patient_privacy(prompt)
        assert_no_known_identity(redacted, identities)
        assert_no_known_identity_in_model_request(kwargs, identities)
        if "temperature" not in kwargs and _accepts_temperature(self.delegate):
            kwargs = {**kwargs, "temperature": EXTRACTION_TEMPERATURE}
        for _ in range(TRANSPORT_RETRY_ATTEMPTS):
            try:
                return await self.delegate.generate(redacted, **kwargs)
            except Exception as error:
                if not _is_transient_transport_error(error):
                    raise
            await asyncio.sleep(TRANSPORT_RETRY_DELAY_SECONDS)
        return await self.delegate.generate(redacted, **kwargs)

    def supports_strict_json_schema(self) -> bool:
        capability = getattr(self.delegate, "supports_strict_json_schema", None)
        if not callable(capability):
            return False
        return bool(capability())


def wrap_luxian_0609_llm_client(
    client: Any,
    *,
    identity_values: Iterable[str] = (),
    identity_provider: Callable[[], Iterable[str]] | None = None,
) -> Any:
    if client is None:
        return None
    values = _freeze_identity_values(identity_values)
    providers = (identity_provider,) if identity_provider is not None else ()
    if isinstance(client, _Luxian0609PrivacyRedactingLLMClient):
        if not values and not providers:
            return client
        return _Luxian0609PrivacyRedactingLLMClient(
            client.delegate,
            _freeze_identity_values((*client.identity_values, *values)),
            (*client.identity_providers, *providers),
        )
    return _Luxian0609PrivacyRedactingLLMClient(client, values, providers)
