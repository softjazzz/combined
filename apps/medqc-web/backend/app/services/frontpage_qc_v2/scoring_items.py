"""首页质控 V2：评分项（《住院病案首页数据质量管理与控制指标（2016版）》评分表）。

仓库内评分表的住院过程条目合计 17 分（标题 26 分）、诊疗信息合计 46 分（标题 50 分），
已确认按现有条目扣分、不补缺口，满分仍为 100。
"""
from __future__ import annotations

from typing import Dict, Tuple

from .model import ScoreItem

_ITEMS = (
    # 患者基本信息（18 分）
    ScoreItem("newborn_admission_weight", "新生儿入院体重", "patient", "A", 4),
    ScoreItem("newborn_birth_weight", "新生儿出生体重", "patient", "A", 4),
    ScoreItem("mr_no", "病案号", "patient", "B", 2),
    ScoreItem("sex", "性别", "patient", "C", 1),
    ScoreItem("birthday", "出生日期", "patient", "C", 1),
    ScoreItem("age", "年龄", "patient", "C", 1),
    ScoreItem("payment", "医疗付费方式", "patient", "C", 1),
    ScoreItem("name", "患者姓名", "patient", "D", 0.5),
    ScoreItem("ethnicity", "民族", "patient", "D", 0.5),
    ScoreItem("id_card", "身份证号", "patient", "D", 0.5),
    ScoreItem("marital", "婚姻状况", "patient", "D", 0.5),
    ScoreItem("current_address", "现住址", "patient", "D", 0.5),
    ScoreItem("contact_name", "联系人姓名", "patient", "D", 0.5),
    ScoreItem("contact_relation", "联系人关系", "patient", "D", 0.5),
    ScoreItem("contact_address", "联系人地址", "patient", "D", 0.5),
    ScoreItem("contact_phone", "联系人电话", "patient", "D", 0.5),
    # 住院过程信息（26 分）
    ScoreItem("leaving_way", "离院方式", "hospitalization", "A", 4),
    ScoreItem("admission_time", "入院时间", "hospitalization", "B", 2),
    ScoreItem("discharge_time", "出院时间", "hospitalization", "B", 2),
    ScoreItem("los", "实际住院天数", "hospitalization", "B", 2),
    ScoreItem("discharge_dept", "出院科别", "hospitalization", "B", 2),
    ScoreItem("readmission", "是否有31天内再住院计划", "hospitalization", "B", 2),
    ScoreItem("admission_route", "入院途径", "hospitalization", "C", 1),
    ScoreItem("admission_dept", "入院科别", "hospitalization", "C", 1),
    ScoreItem("transfer_dept", "转科科别", "hospitalization", "C", 1),
    # 诊疗信息（50 分）
    ScoreItem("main_diag_name", "出院主要诊断", "diagnosis", "A", 4),
    ScoreItem("main_diag_code", "主要诊断编码", "diagnosis", "A", 4),
    ScoreItem("other_diag_name", "其他诊断", "diagnosis", "A", 1, per_item=True, item_cap=4),
    ScoreItem("other_diag_code", "其他诊断编码", "diagnosis", "A", 1, per_item=True, item_cap=4),
    ScoreItem("main_surgery_name", "主要手术或操作名称", "diagnosis", "A", 4),
    ScoreItem("main_surgery_code", "主要手术或操作编码", "diagnosis", "A", 4),
    ScoreItem("admission_condition", "入院病情", "diagnosis", "B", 2),
    ScoreItem("pathology_diag", "病理诊断", "diagnosis", "B", 2),
    ScoreItem("pathology_code", "病理诊断编码", "diagnosis", "B", 2),
    ScoreItem("incision_heal", "切口愈合等级", "diagnosis", "B", 2),
    ScoreItem("coma_time", "颅脑损伤患者昏迷时间", "diagnosis", "B", 2),
    ScoreItem("surgery_date", "手术及操作日期", "diagnosis", "B", 2),
    ScoreItem("other_surgery_name", "其他手术或操作名称", "diagnosis", "B", 0.5, per_item=True, item_cap=2),
    ScoreItem("other_surgery_code", "其他手术或操作编码", "diagnosis", "B", 0.5, per_item=True, item_cap=2),
    ScoreItem("outpatient_diag", "门（急）诊诊断", "diagnosis", "C", 1),
    ScoreItem("outpatient_code", "门（急）诊诊断疾病编码", "diagnosis", "C", 1),
    ScoreItem("anesthesia", "麻醉方式", "diagnosis", "C", 1),
    ScoreItem("external_cause", "损伤（中毒）外部原因及疾病编码", "diagnosis", "D", 0.5),
    ScoreItem("pathology_no", "病理号", "diagnosis", "D", 0.5),
    ScoreItem("allergy", "药物过敏史", "diagnosis", "D", 0.5),
    ScoreItem("autopsy", "尸检记录", "diagnosis", "D", 0.5),
    ScoreItem("blood", "血型及Rh标识", "diagnosis", "D", 0.5),
    ScoreItem("surgery_level", "手术级别", "diagnosis", "D", 0.5),
    ScoreItem("surgeon", "术者", "diagnosis", "D", 0.5),
    ScoreItem("first_assistant", "第一助手", "diagnosis", "D", 0.5),
    # 费用信息（6 分）
    ScoreItem("total_cost", "总费用", "cost", "A", 4),
    ScoreItem("fee_items", "费用分项", "cost", "D", 0.5, per_item=True, item_cap=2),
)

SCORE_ITEMS: Dict[str, ScoreItem] = {item.key: item for item in _ITEMS}

# D 类“扣至 N 分为止”的分组封顶
GROUP_CAPS: Dict[Tuple[str, str], float] = {
    ("patient", "D"): 4.0,
    ("diagnosis", "D"): 3.0,
    ("cost", "D"): 2.0,
}

SECTION_POINTS = {"patient": 18, "hospitalization": 26, "diagnosis": 50, "cost": 6}


def max_points(item: ScoreItem) -> float:
    return item.item_cap if item.per_item and item.item_cap is not None else item.points
