"""已同步文书的显式栏目适配，不写库、不推断临床事实或跨系统关联。"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence

DIAGNOSIS_PARENTS = {
    "admission_record_diagnosis": ("admission_record", ("入院诊断", "初步诊断")),
    "first_course_record_diagnosis": ("first_course_record", ("初步诊断", "第一诊断")),
    "discharge_record_diagnosis": ("discharge_record", ("出院诊断", "死亡诊断")),
}
_HEADINGS = (
    "主诉", "现病史", "既往史", "体格检查", "辅助检查", "病例特点", "诊断依据",
    "入院诊断", "初步诊断", "第一诊断", "出院诊断", "死亡诊断", "鉴别诊断",
    "诊疗计划", "治疗计划", "治疗经过", "诊疗经过", "出院情况", "出院医嘱",
    "出院带药", "出院用药", "出院指导", "随访计划", "医师签名", "医师签字",
)
_SECTION = re.compile(
    r"(?:^|[\n\r]|(?<=[。；;]))\s*(?:[一二三四五六七八九十]+[、.．]\s*)?"
    r"[【\[]?(?P<label>" + "|".join(map(re.escape, _HEADINGS))
    + r")[】\]]?[ \t]*(?:[:：]|(?=[\r\n]|$))[ \t]*"
)
_NUMBERED = re.compile(r"(?:^|[\n\r；;]|\s)(?P<number>[1-9]\d{0,2})[、.．)](?!\d)\s*")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"p", "div", "br", "tr", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag in {"p", "div", "tr", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def explicit_sections(value: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, str):
        return ()
    text = value
    if re.search(r"</?(?:p|div|br|table|tr|li|span|style|script)\b", value, re.I):
        parser = _Text()
        parser.feed(value)
        text = "".join(parser.parts)
    matches = list(_SECTION.finditer(text))
    return tuple(
        (match["label"], text[match.end():matches[i + 1].start() if i + 1 < len(matches) else None].strip())
        for i, match in enumerate(matches)
    )


def document_diagnoses(
    source_key: str, documents: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    parent, labels = DIAGNOSIS_PARENTS[source_key]
    result = []
    for document in documents:
        document_id = str(document.get("document_id") or "").strip()
        if not document_id:
            raise ValueError("diagnosis_parent_identity_missing")
        bound = [r for r in diagnoses
                 if str(r.get("document_id") or "").strip() == document_id
                 and str(r.get("diagnosis_type") or "").strip() in labels]
        if bound:
            for row in bound:
                result.append({**dict(row), "source_table": "diagnosis"})
            continue
        for label, text in explicit_sections(document.get("record_content")):
            if label not in labels or not text:
                continue
            positions = list(_NUMBERED.finditer(text))
            # 显式编号保存源序号；未编号分行/分号项保持无序，不造“第一诊断”。
            items = [(None, value.strip()) for value in re.split(r"[\r\n；;]+", text) if value.strip()]
            if positions and not text[:positions[0].start()].strip():
                items = [(m["number"], text[m.end():positions[i + 1].start()
                           if i + 1 < len(positions) else None].strip())
                         for i, m in enumerate(positions)]
            for number, name in items:
                if name:
                    result.append({
                        "document_id": document_id,
                        "diagnosis_type": "初步诊断" if label == "第一诊断" else label,
                        "diagnosis_name": name, "source_table": parent,
                        **({"diagnosis_no": number} if number is not None else {}),
                        "source_field": "record_content", "source_section": label,
                    })
    return tuple(result)


def homepage_diagnoses(diagnoses: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """只接受源字段显式声明首页；通用出院诊断不冒充首页诊断。"""
    return tuple({**dict(row), "source_table": "diagnosis"} for row in diagnoses
                 if str(row.get("diagnosis_source") or "").strip() in {"病案首页", "首页", "mr"})


def enrich_discharge_document(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    if str(row.get("discharge_order") or "").strip() or row.get("discharge_medications") is not None:
        return result
    sections = [(label, value) for label, value in explicit_sections(row.get("record_content"))
                if label in {"出院医嘱", "出院带药", "出院用药"} and value]
    specific = [item for item in sections if item[0] in {"出院带药", "出院用药"}]
    sections = specific or sections
    if len(sections) == 1:
        result["discharge_order"] = sections[0][1]
        result["discharge_order_source"] = "record_content:" + sections[0][0]
    # 多个栏目不猜选、不合并，交还既有歧义路径。
    return result
