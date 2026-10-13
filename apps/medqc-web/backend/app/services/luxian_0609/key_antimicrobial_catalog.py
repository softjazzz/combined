"""LX0609-05-01-04（056）重点抗菌药物目录。

院方口径（2026-10-11）：本指标的重点抗菌药物为以下七类，按药品通用名识别，
不再按限制使用级/特殊使用级合并识别。医嘱名称常带厂家、规格、“钠/钾”盐、
复方分隔符，匹配时兼容这些写法；复方只认完整组合（单用头孢他啶不算）。
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


# (药品, 类别, 匹配模式)
KEY_ANTIMICROBIALS: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    (name, category, re.compile(pattern))
    for name, category, pattern in (
        ("亚胺培南", "碳青霉烯类", r"亚胺培南"),
        ("美罗培南", "碳青霉烯类", r"美罗培南"),
        ("帕尼培南", "碳青霉烯类", r"帕尼培南"),
        ("比阿培南", "碳青霉烯类", r"比阿培南"),
        ("厄他培南", "碳青霉烯类", r"厄他培南"),
        # 院方清单只列万古霉素、替考拉宁；去甲万古霉素不在清单内。
        ("万古霉素", "糖肽类", r"(?<!去甲)万古霉素"),
        ("替考拉宁", "糖肽类", r"替考拉宁"),
        ("替加环素", "新型四环素类", r"替加环素"),
        ("奥玛环素", "新型四环素类", r"奥[玛马]环素"),
        ("依拉环素", "新型四环素类", r"依拉环素"),
        ("利奈唑胺", "噁唑烷酮类", r"利奈唑胺"),
        ("特地唑胺", "噁唑烷酮类", r"特地唑胺"),
        ("康替唑胺", "噁唑烷酮类", r"康替唑胺"),
        ("多黏菌素B", "黏菌素类", r"多[黏粘]菌素\s*[BbＢ]"),
        ("多黏菌素E甲磺酸盐", "黏菌素类", r"多[黏粘]菌素\s*[EeＥ]|黏菌素甲磺酸|粘菌素甲磺酸"),
        ("硫酸黏菌素", "黏菌素类", r"(?<!多)[黏粘]菌素(?!\s*[BbＢEeＥ]|甲磺酸)"),
        ("头孢哌酮舒巴坦", "β-内酰胺类/β-内酰胺酶抑制剂", r"头孢哌酮(?:钠)?\s*[/／·、和与]?\s*舒巴坦"),
        ("头孢他啶阿维巴坦", "β-内酰胺类/β-内酰胺酶抑制剂", r"头孢他啶(?:钠)?\s*[/／·、和与]?\s*阿维巴坦"),
        ("哌拉西林他唑巴坦", "β-内酰胺类/β-内酰胺酶抑制剂", r"哌拉西林(?:钠)?\s*[/／·、和与]?\s*他唑巴坦"),
        ("伏立康唑", "深部抗真菌药", r"伏立康唑"),
        ("泊沙康唑", "深部抗真菌药", r"泊沙康唑"),
        ("艾莎康唑", "深部抗真菌药", r"艾[莎沙]康唑"),
        ("卡泊芬净", "深部抗真菌药", r"卡泊芬净"),
        ("米卡芬净", "深部抗真菌药", r"米卡芬净"),
        ("两性霉素B", "深部抗真菌药", r"两性霉素\s*[BbＢ]"),
    )
)
_NAME_FIELDS = ("generic_name", "brand_name", "order_name", "drug_name")
_CANCELLED_STATUS = re.compile(r"取消|作废|撤销")


def key_antimicrobials_in_order(row: Mapping[str, Any]) -> tuple[str, ...]:
    """返回一条药品医嘱中的重点抗菌药物（已取消/作废医嘱不计）。"""

    if _CANCELLED_STATUS.search(str(row.get("order_status") or "")):
        return ()
    text = " ".join(str(row.get(field) or "") for field in _NAME_FIELDS)
    return tuple(name for name, _category, pattern in KEY_ANTIMICROBIALS if pattern.search(text))
