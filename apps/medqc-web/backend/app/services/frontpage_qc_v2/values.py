"""首页质控 V2：取值归一与代码字典。

代码取值以《住院病案首页部分项目填写说明》（2016 版）为准，同时接受中文名称：
真实同步数据里代码和中文混用，归一后规则只比较标准代码。
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Mapping, Optional

# 填写说明：栏目中没有可填写内容的，填写“—”。这些值视为“已填写、无内容”。
NONE_MARKERS = frozenset({"-", "—", "－", "--", "——", "/", "无"})
_EMPTY_TEXTS = frozenset({"", "none", "null", "nan"})


def text_of(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_filled(value: object) -> bool:
    """字段是否已填写；“-”“无”算已填写。"""
    return text_of(value).lower() not in _EMPTY_TEXTS


def has_content(value: object) -> bool:
    """字段是否有实际内容；“-”“无”算没有内容。"""
    text = text_of(value)
    return text.lower() not in _EMPTY_TEXTS and text not in NONE_MARKERS


def _lookup(value: object, table: Mapping[str, str]) -> Optional[str]:
    text = text_of(value)
    if not text:
        return None
    return table.get(text) or table.get(text.upper())


# ---------- 代码字典 ----------

PAYMENT_METHOD = {
    **{str(i): str(i) for i in range(1, 10)},
    "城镇职工基本医疗保险": "1",
    "职工基本医疗保险": "1",
    "城镇居民基本医疗保险": "2",
    "居民基本医疗保险": "2",
    "新型农村合作医疗": "3",
    "贫困救助": "4",
    "商业医疗保险": "5",
    "全公费": "6",
    "全自费": "7",
    "其他社会保险": "8",
    "其他": "9",
}

SEX = {"1": "1", "2": "2", "0": "0", "9": "9", "男": "1", "女": "2", "未知": "0", "未知的性别": "0", "未说明": "9", "未说明的性别": "9"}

MARITAL_STATUS = {
    "1": "1", "2": "2", "3": "3", "4": "4", "9": "9",
    # GB/T 2261.2 两位码
    "10": "1", "20": "2", "21": "2", "22": "2", "23": "2", "30": "3", "40": "4", "90": "9",
    "未婚": "1", "已婚": "2", "初婚": "2", "再婚": "2", "复婚": "2", "丧偶": "3", "离婚": "4",
    "其他": "9", "未说明的婚姻状况": "9",
}

CONTACT_RELATION_NAMES = frozenset({
    "本人", "户主", "配偶", "夫", "妻", "子", "儿子", "女", "女儿", "孙子", "孙女", "外孙子", "外孙女",
    "父母", "父亲", "母亲", "公公", "婆婆", "岳父", "岳母", "祖父母", "祖父", "祖母", "外祖父", "外祖母",
    "兄", "弟", "姐", "妹", "兄弟", "姐妹", "兄弟姐妹", "儿媳", "女婿", "其他",
})

ADMISSION_ROUTE = {
    "1": "1", "2": "2", "3": "3", "9": "9",
    "急诊": "1", "门诊": "2", "其他医疗机构转入": "3", "转入": "3", "其他": "9",
}

LEAVING_WAY = {
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "9": "9",
    "医嘱离院": "1",
    "医嘱转院": "2",
    "医嘱转社区卫生服务机构/乡镇卫生院": "3",
    "医嘱转社区卫生服务机构": "3",
    "医嘱转乡镇卫生院": "3",
    "非医嘱离院": "4",
    "死亡": "5",
    "其他": "9",
}

ADMISSION_CONDITION = {"1": "1", "2": "2", "3": "3", "4": "4", "有": "1", "临床未确定": "2", "情况不明": "3", "无": "4"}

# 2016 版首页“其他”为 9；旧版首页“其他”为 5，同步数据里大量存在，两者都接受（已确认）。
DISCHARGE_CONDITION = {
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "9", "9": "9",
    "治愈": "1", "好转": "2", "未愈": "3", "死亡": "4", "其他": "9",
}

ABO_BLOOD = {
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
    "A": "1", "B": "2", "O": "3", "AB": "4", "A型": "1", "B型": "2", "O型": "3", "AB型": "4",
    "不详": "5", "未查": "6",
}

RH_BLOOD = {"1": "1", "2": "2", "3": "3", "4": "4", "阴": "1", "阴性": "1", "阳": "2", "阳性": "2", "不详": "3", "未查": "4"}

ALLERGY_FLAG = {"1": "1", "2": "2", "无": "1", "有": "2"}

YES_NO_PLAN = {"1": "1", "2": "2", "无": "1", "有": "2"}

AUTOPSY = {"1": "1", "2": "2", "是": "1", "否": "2"}

SURGICAL_LEVEL = {
    "1": "1", "2": "2", "3": "3", "4": "4",
    "一级": "1", "二级": "2", "三级": "3", "四级": "4",
    "一级手术": "1", "二级手术": "2", "三级手术": "3", "四级手术": "4",
}
SURGICAL_LEVEL_UNSET = frozenset({"未定级"})

INCISION_CLASS = {
    "0": "0", "0类": "0", "0类切口": "0",
    "Ⅰ": "1", "I": "1", "1": "1", "Ⅰ类": "1", "I类": "1", "Ⅰ类切口": "1",
    "Ⅱ": "2", "II": "2", "2": "2", "Ⅱ类": "2", "II类": "2", "Ⅱ类切口": "2",
    "Ⅲ": "3", "III": "3", "3": "3", "Ⅲ类": "3", "III类": "3", "Ⅲ类切口": "3",
}

HEALING_GRADE = {"甲": "甲", "乙": "乙", "丙": "丙", "其他": "其他", "甲级愈合": "甲", "乙级愈合": "乙", "丙级愈合": "丙"}


def normalize_code(value: object, table: Mapping[str, str]) -> Optional[str]:
    return _lookup(value, table)


def is_valid_relation(value: object) -> bool:
    text = text_of(value)
    if not text:
        return False
    if re.fullmatch(r"\d{1,2}", text):
        return True
    return text in CONTACT_RELATION_NAMES


# ---------- 编码格式（只校验格式，兼容国临版扩展码；已确认不查字典） ----------

_ICD10_PART = r"[A-Z]\d{2}(?:\.[0-9A-Za-z]{1,8})?"
_ICD10_RE = re.compile(rf"^{_ICD10_PART}(?:[+†]{_ICD10_PART}\*?)?[*†]?$")
_ICD9CM3_RE = re.compile(r"^\d{2}\.[0-9A-Za-z]{1,8}$")
_MORPHOLOGY_RE = re.compile(r"^M\d{4,5}/\d{1,2}$")


def is_icd10(code: object) -> bool:
    return bool(_ICD10_RE.match(text_of(code)))


def icd10_head(code: object) -> str:
    """去掉星剑号部分后的主编码，大写，如 K35.800x001 → K35.800X001。"""
    text = text_of(code).upper()
    return re.split(r"[+†*]", text, maxsplit=1)[0]


def is_external_cause(code: object) -> bool:
    head = icd10_head(code)
    return bool(head) and head[0] in "VWXY"


def is_icd9cm3(code: object) -> bool:
    return bool(_ICD9CM3_RE.match(text_of(code)))


def is_morphology(code: object) -> bool:
    return bool(_MORPHOLOGY_RE.match(text_of(code).upper()))


def icd10_in_ranges(code: object, ranges: tuple[tuple[str, str], ...]) -> bool:
    """按三位类目判断是否落在区间内，如 ('N40', 'N51')。"""
    head = icd10_head(code)[:3]
    if len(head) < 3:
        return False
    return any(lo <= head <= hi for lo, hi in ranges)


def icd9_category(code: object) -> Optional[int]:
    text = text_of(code)
    match = re.match(r"^(\d{2})", text)
    return int(match.group(1)) if match else None


# ---------- 身份证、电话 ----------

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"


def is_valid_id_card(value: object) -> bool:
    text = text_of(value).upper()
    if not re.fullmatch(r"\d{17}[\dX]", text):
        return False
    total = sum(int(ch) * w for ch, w in zip(text[:17], _ID_WEIGHTS))
    return _ID_CHECK[total % 11] == text[17]


def is_id_card_type(value: object) -> bool:
    text = text_of(value)
    return not text or "身份证" in text


def is_valid_phone(value: object) -> bool:
    text = re.sub(r"[\s()（）]", "", text_of(value))
    if text in NONE_MARKERS:
        return True
    return bool(re.fullmatch(r"(?:\+?86)?1\d{10}", text) or re.fullmatch(r"(?:0\d{2,3}-?)?\d{7,8}(?:-\d{1,6})?", text))


# ---------- 数值、日期、年龄 ----------


def parse_number(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    text = text_of(value).replace(",", "")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
)


def parse_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = text_of(value)
    if not text:
        return None
    text = re.sub(r"([+-]\d{2}(:?\d{2})?|Z)$", "", text) if re.search(r"\d{2}:\d{2}", text) else text
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def has_time_part(value: object) -> bool:
    """原值是否带时分。datetime 对象视为带时分（00:00 可能是真实的零点）；纯日期文本或 date 对象不带。"""
    if isinstance(value, datetime):
        return True
    if isinstance(value, date):
        return False
    return re.search(r"\d{1,2}:\d{2}", text_of(value)) is not None


def parse_age_years(value: object) -> Optional[float]:
    """解析年龄：'45'、'45岁'、'3月'、'2月15天'、'10天' → 岁数。无法解析返回 None。"""
    text = text_of(value).replace(" ", "")
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    match = re.fullmatch(r"(?:(\d+)岁)?(?:(\d+)(?:个)?月)?(?:(\d+)(?:天|日))?", text)
    if not match or not any(match.groups()):
        return None
    years, months, days = (int(part) if part else 0 for part in match.groups())
    return years + months / 12 + days / 365


def full_years_between(birth: date, on: date) -> int:
    years = on.year - birth.year
    if (on.month, on.day) < (birth.month, birth.day):
        years -= 1
    return years
