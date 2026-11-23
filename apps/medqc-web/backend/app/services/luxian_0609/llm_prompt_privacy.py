from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx


logger = logging.getLogger(__name__)

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
# 仅带明确性别/年龄锚点的患者介绍才视为高置信姓名并参与全文替换；
# 仅以“因”为锚点（含“患者某某，因...”与“患者某某因...”）只做原地兜底脱敏，不参与全文替换。
_PATIENT_INTRO = re.compile(
    rf"(?P<label>(?:患者|病人|患儿)\s*)"
    rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    rf"(?=\s*[，,、]\s*(?:{_LABELLED_SEX}|男|女|年龄|\d{{1,3}}\s*岁))"
)
# “因”锚点兜底（含可选逗号，如“患者孙小红，因发热入院”“患者孙小红因发热入院”）
# 只做原地脱敏，不加入全文替换集合，并排除常见临床/时间词，避免误伤医学事实。
_PATIENT_CAUSE_INTRO = re.compile(
    rf"(?P<label>(?:患者|病人|患儿)\s*)"
    rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    r"(?=(?:\s*[，,、]\s*因|\s*因))"
)
_CAUSE_INTRO_NON_NAME_PREFIXES = (
    "于", "从", "经", "查", "后", "左", "双", "单", "全", "空",
    "平素", "平时", "平卧", "平稳", "平车", "常年", "长期", "常规", "周身",
    "连日", "连续", "时有", "时感", "明显", "明确", "危重", "危急", "严重",
    "强直", "强迫", "劳累", "劳力", "步态", "步行", "焦虑", "焦躁", "解黑",
    "解稀", "解血", "解水", "高危", "高龄", "高度", "高热", "高温", "高烧",
    "黄疸", "黄染", "冷汗", "白带", "白内障", "白细胞", "包块", "房颤", "房扑",
    "房早", "房室", "窦性", "窦缓", "窦速", "干咳", "干呕", "干燥", "红肿",
    "红斑", "红细胞", "皮疹", "皮肤", "皮下", "皮损", "水肿", "水疱", "水样",
    "支气管", "关节", "宫缩", "宫颈", "宫腔", "宫口", "宫内", "宫外",
    "阴道", "阴性", "阴囊", "阴茎", "羊水", "怀孕", "仰卧", "苍白", "沙哑",
    "麻醉", "麻木", "麻疹", "糜烂", "满腹", "谷丙", "谷草", "终末", "车祸",
    "家属", "张口", "曾于", "曾经", "曾行", "曾有", "曾患", "曾住",
)
_CAUSE_INTRO_CLINICAL_SUFFIXES = frozenset(
    "热痛咳呕吐泻喘闷晕肿疹斑痰血尿便压糖脂炎癌瘤病症颤烂醉折毒竭乱"
    "肺肾肝胃肠脑胸腹腰背颈眼耳鼻咽喉肢膝肩臂腿肤膜腔管节块液汗温龄院"
)
_DEMOGRAPHIC_LABEL = (
    # 正文可能嵌在一层或多层 JSON 中；识别转义换行边界，不解码/重写整段医疗文本。
    r"(?P<label>(?:(?<=^)|(?<=[\n\r；;。：:])|(?<=\\n)|(?<=\\r))[ \t]*"
    r"(?:(?:[一二三四五六七八九十]+|\d+)[、.．][ \t]*)?)"
)
# 各族正文清洗常把换行压成空格（“时间 标题\n张三，男”→“时间 标题 张三，男”）。仅对已知
# 患者姓名额外接受空白边界；未知姓名仍只按行首/标点边界猜测，避免误删医务人员或病名。
_KNOWN_DEMOGRAPHIC_LABEL = (
    r"(?P<label>(?:(?<=^)|(?<=[\n\r；;。：:])|(?<=\\n)|(?<=\\r)|(?<=[ \t　]))[ \t]*"
    r"(?:(?:[一二三四五六七八九十]+|\d+)[、.．][ \t]*)?)"
)
_DEMOGRAPHIC_FOLLOW = (
    rf"(?=[ \t]*[，,、][ \t]*(?:{_LABELLED_SEX}|(?:老年|中年|青年|成年|幼年)[男女]性|男|女|\d{{1,3}}[ \t]*岁|年龄))"
)
_DEMOGRAPHIC_NAME = re.compile(
    _DEMOGRAPHIC_LABEL
    + rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    + _DEMOGRAPHIC_FOLLOW,
    flags=re.MULTILINE,
)
# 无“患者”字样的人口学介绍（“某某，男，79岁”）也需取已知身份辅助识别。
_DEMOGRAPHIC_HINT = re.compile(r"[，,、][ \t]*[男女][ \t]*[，,、]")
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
    r"工作单位地址|详细地址|住址|地址)\s*[:：]\s*)"
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
# 本模块写入的全部占位；引用核验据此区分“本系统脱敏”与模型自造的方括号文本。
LUXIAN_0609_REDACTION_PLACEHOLDER = re.compile(
    r"\[(?:患者姓名|联系人姓名|身份证号|手机号|座机号码|电话号码|地址|出生日期|工作单位|就诊标识|电子邮箱)已脱敏\]"
)


def locate_luxian_0609_redacted_quote(quote: str, original: str) -> tuple[int, int] | None:
    """把含本系统脱敏占位的引文唯一回映到原文，返回原文区间；不含占位或不唯一时返回 None。

    模型只看到脱敏正文，含占位的逐字引文不可能出现在原文里。占位外的文字必须按原顺序
    紧邻出现，占位只对应不跨标点/换行、不超过64字的片段，整段在原文中只能匹配一处。
    调用方仍须另行要求引文逐字出自同一份实际发送正文，不能据此接受改写或他文书借用。
    """
    parts = LUXIAN_0609_REDACTION_PLACEHOLDER.split(quote)
    if len(parts) < 2 or not any(part.strip() for part in parts):
        return None
    pattern = re.compile(r"[^\n\r，,。；;]{1,64}?".join(re.escape(part) for part in parts))
    matches = list(pattern.finditer(original))
    return matches[0].span() if len(matches) == 1 else None


def _replace_labelled(pattern: re.Pattern[str], text: str, placeholder: str) -> str:
    return pattern.sub(
        lambda match: f"{match.group('label')}{placeholder}",
        text,
    )


def _is_plausible_unverified_cause_name(value: str) -> bool:
    cleaned = value.strip()
    if len(cleaned) < 2:
        return False
    if any(cleaned.startswith(prefix) for prefix in _CAUSE_INTRO_NON_NAME_PREFIXES):
        return False
    if cleaned[-1] in _CAUSE_INTRO_CLINICAL_SUFFIXES:
        return False
    return True


def _replace_unverified_cause_intro(text: str, placeholder: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        value = match.group("value")
        if not _is_plausible_unverified_cause_name(value):
            return match.group(0)
        return f"{match.group('label')}{placeholder}"

    return _PATIENT_CAUSE_INTRO.sub(_replace, text)


def _protect_clinician_names(text: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    protected: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        marker = f"__LX0609_CLINICIAN_NAME_{len(protected)}__"
        protected.append((marker, match.group(0)))
        return marker

    return _CLINICIAN_NAME_LABEL.sub(_replace, text), tuple(protected)


def redact_luxian_0609_patient_privacy(
    prompt: str, *, identity_values: Iterable[str] | None = None,
) -> str:
    """删除LX0609模型prompt中的患者身份信息，保留医疗事实和医务人员姓名。"""

    if not isinstance(prompt, str):
        raise TypeError("prompt must be str")
    if identity_values is None and (
        any(label in prompt for label in ("患者", "病人", "患儿")) or _DEMOGRAPHIC_HINT.search(prompt)
    ):
        from .privacy_request_scope import current_luxian_0609_redaction_identities

        identity_values = current_luxian_0609_redaction_identities()
    # 已知身份只补充明确患者介绍的识别，不靠扩充姓氏表猜测，也不盲删数字/无标签身份。
    known_names = [
        re.escape(value) for value in _freeze_identity_values(identity_values if identity_values is not None else ())
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", value)
    ]
    name_patterns = (_PATIENT_NAME_LABEL, _PATIENT_INTRO, _DEMOGRAPHIC_NAME)
    if known_names:
        known_intro = re.compile(
            r"(?P<label>(?:患者|病人|患儿)\s*)"
            + r"(?P<value>" + "|".join(known_names) + r")(?=[\s，,、；;。]|因|$)"
        )
        # 已知姓名出现在句首/冒号后并紧跟性别、年龄（如“新建S章节:某某，男，79岁”），
        # 同样是患者介绍；姓氏不在常见表时只能靠已知身份识别。
        known_demographic = re.compile(
            _KNOWN_DEMOGRAPHIC_LABEL + r"(?P<value>" + "|".join(known_names) + r")" + _DEMOGRAPHIC_FOLLOW,
            flags=re.MULTILINE,
        )
        name_patterns = (*name_patterns, known_intro, known_demographic)
    protected_prompt, protected_clinicians = _protect_clinician_names(prompt)
    patient_names = {
        match.group("value").strip()
        for pattern in name_patterns
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
    if known_names:
        redacted = _replace_labelled(known_intro, redacted, _PATIENT_NAME_PLACEHOLDER)
        redacted = _replace_labelled(known_demographic, redacted, _PATIENT_NAME_PLACEHOLDER)
    redacted = _replace_unverified_cause_intro(
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
def _is_transient_transport_error(error: BaseException) -> bool:
    """只重试已确认的瞬时故障，未知错误和确定性拒绝不能消耗重试预算。"""
    from ..qc_execution_errors import safe_exception_failure

    return safe_exception_failure(error)["retryable"] is True


def is_luxian_0609_privacy_block(error: BaseException) -> bool:
    """隐私护栏发送前拒绝；补核/二次调用据此与预算失败同等闭合，不回退为无效输出。"""

    return isinstance(error, (PatientPrivacyViolation, PrivacyIdentityContextError))


def luxian_0609_llm_call_failure_reason(
    error: BaseException, fallback: str = "model_transport_error"
) -> str:
    """模型调用点共享失败码：隐私护栏拦截固定为不可重试，其余异常保留调用点原回退码。

    隐私拦截是确定性拒绝，若记为传输错误会被重试并误导为网络故障。
    """

    if is_luxian_0609_privacy_block(error):
        return "privacy_guard_blocked"
    return fallback


def classify_luxian_0609_llm_call_failure(error: BaseException) -> str:
    """保留模型边界安全类别，不把参数、鉴权或未知错误误判成网络失败。"""
    from ..qc_execution_errors import safe_exception_failure

    if isinstance(error, (PatientPrivacyViolation, PrivacyIdentityContextError)):
        return "privacy_guard_blocked"
    return safe_exception_failure(error)["reason_code"]


def describe_luxian_0609_llm_parse_failure(error: BaseException, response: Any) -> str:
    """模型输出解析失败的安全描述，供诊断日志使用：不含提示词、病历或模型原文。

    只保留异常类型、解析器自身写死的英文失败类别、finish_reason 与输出 Token 数；
    KeyError 等可能携带模型输出片段的异常信息一律不记录。
    """

    detail = "-"
    if type(error) is ValueError:
        message = str(error)
        if message.isascii() and len(message) <= 80 and not any(ch.isdigit() for ch in message):
            detail = message
    finish_reason = completion_tokens = "-"
    try:
        choice = response["choices"][0]
        finish_reason = str(choice.get("finish_reason") or "-")[:20]
    except Exception:
        pass
    try:
        completion_tokens = str(int(response["usage"]["completion_tokens"]))
    except Exception:
        pass
    return (
        f"error_kind={type(error).__name__} detail={detail} "
        f"finish_reason={finish_reason} completion_tokens={completion_tokens}"
    )


def _log_privacy_guard_block(error: BaseException) -> None:
    """隐私护栏拦截只记录异常类别与脱敏观测上下文，不记录提示词或身份值。"""

    try:
        from ..llm_observability import current_llm_observation_context

        context = current_llm_observation_context()
        executor_key = context.executor_key or "unknown"
        record_key_hash = context.record_key_hash or "unknown"
    except Exception:
        executor_key = record_key_hash = "unknown"
    logger.warning(
        "LX0609 隐私护栏拦截模型请求: error_kind=%s executor_key=%s record_key_hash=%s",
        type(error).__name__,
        executor_key,
        record_key_hash,
    )


@dataclass(frozen=True)
class _Luxian0609PrivacyRedactingLLMClient:
    delegate: Any = field(repr=False)
    identity_values: tuple[str, ...] = field(default=(), repr=False)
    identity_providers: tuple[Callable[[], Iterable[str]], ...] = field(
        default=(), repr=False
    )

    @property
    def task_role_identity(self):
        return getattr(self.delegate, "task_role_identity", None)

    @property
    def model_role(self):
        return getattr(self.delegate, "model_role", "adjudicator")

    def _prepare_request(self, prompt, kwargs):
        try:
            identities = set(self.identity_values)
            for provider in self.identity_providers:
                try:
                    identities.update(_freeze_identity_values(provider()))
                except Exception:
                    raise PrivacyIdentityContextError(
                        "Patient identity context is unavailable"
                    ) from None
            redacted = redact_luxian_0609_patient_privacy(prompt, identity_values=identities)
            assert_no_known_identity(redacted, identities)
            assert_no_known_identity_in_model_request(kwargs, identities)
        except (PatientPrivacyViolation, PrivacyIdentityContextError) as error:
            _log_privacy_guard_block(error)
            raise
        if "temperature" not in kwargs and _accepts_temperature(self.delegate):
            kwargs = {**kwargs, "temperature": EXTRACTION_TEMPERATURE}
        return redacted, kwargs

    def probe_context_budget(self, prompt: str, **kwargs: Any):
        redacted, kwargs = self._prepare_request(prompt, kwargs)
        probe = getattr(self.delegate, "probe_context_budget", None)
        return probe(redacted, **kwargs) if callable(probe) else None

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        redacted, kwargs = self._prepare_request(prompt, kwargs)
        from .exam_token_budget import model_call_scope
        with model_call_scope():
            for _ in range(TRANSPORT_RETRY_ATTEMPTS):
                try:
                    return await self.delegate.generate(redacted, **kwargs)
                except Exception as error:
                    if getattr(error, "transport_retry_managed", False) is True:
                        # Gateway 已拥有传输重试预算；包装层不得再次乘算同一错误。
                        raise
                    if not _is_transient_transport_error(error):
                        raise
                    from .execution_time_budget import model_timeout_seconds, retry_fits

                    if not retry_fits(
                        delay_seconds=TRANSPORT_RETRY_DELAY_SECONDS,
                        attempt_seconds=model_timeout_seconds(self.delegate),
                    ):
                        raise
                await asyncio.sleep(TRANSPORT_RETRY_DELAY_SECONDS)
            return await self.delegate.generate(redacted, **kwargs)

    def for_role(self, role: str) -> Any:
        """按调用点换用 LLM_ROLE_MODELS 配置的模型；身份脱敏与护栏不变。"""
        from .llm_role_routing import build_role_delegate

        identity = getattr(self.delegate, "task_role_identity", None)
        if isinstance(identity, dict) and "specialty_verification" in identity.get("roles", {}):
            return self.for_task_role("specialty_verification")
        selector = getattr(self.delegate, "for_legacy_role", None)
        delegate = selector(role) if callable(selector) else build_role_delegate(role)
        if delegate is None:
            return self
        if delegate is self.delegate:
            return self
        return _Luxian0609PrivacyRedactingLLMClient(delegate, self.identity_values, self.identity_providers)

    def for_task_role(self, role: str) -> Any:
        from ..llm_task_roles import client_for_task

        delegate = client_for_task(self.delegate, role)
        if delegate is self.delegate:
            return self
        return _Luxian0609PrivacyRedactingLLMClient(delegate, self.identity_values, self.identity_providers)

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
