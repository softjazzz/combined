from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


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
    rf"(?P<label>(?:(?<=^)|(?<=[\n\r；;。]))[ \t]*)"
    rf"(?P<value>{_COMMON_SURNAME}[\u4e00-\u9fff·]{{1,3}})"
    rf"(?=[ \t]*[，,、][ \t]*(?:{_LABELLED_SEX}|男|女|\d{{1,3}}[ \t]*岁|年龄))",
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
_ADDRESS = re.compile(
    r"(?P<label>(?:现住址|家庭住址|户籍地址|通讯地址|联系地址|联系人地址|"
    r"工作单位地址|详细地址|地址)\s*[:：]\s*)"
    r"(?P<value>[^\n\r；;]{2,160})"
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
    r"(?P<value>[^\n\r；;]{2,120})"
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


@dataclass(frozen=True)
class _Luxian0609PrivacyRedactingLLMClient:
    delegate: Any

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        return await self.delegate.generate(
            redact_luxian_0609_patient_privacy(prompt),
            **kwargs,
        )

    def supports_strict_json_schema(self) -> bool:
        capability = getattr(self.delegate, "supports_strict_json_schema", None)
        if not callable(capability):
            return False
        return bool(capability())


def wrap_luxian_0609_llm_client(client: Any) -> Any:
    if client is None or isinstance(client, _Luxian0609PrivacyRedactingLLMClient):
        return client
    return _Luxian0609PrivacyRedactingLLMClient(client)
