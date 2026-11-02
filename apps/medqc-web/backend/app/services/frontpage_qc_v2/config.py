"""首页质控 V2：口径配置（2026-10-13 评审确认）。"""
from __future__ import annotations

RULESET_KEY = "frontpage_qc_v2"
RULESET_VERSION = "2026.11.01"

# 首页同步未带入的字段：为空时判“资料不足”，不判不合规。
# 同步修复后从这里删除对应字段，即恢复为正常的必填检查。
SOURCE_GAP_FIELDS = frozenset(
    {
        "admission_datetime",  # 真实首页 10% 有值，入院登记表也没有
        "discharge_datetime",  # 同上
        "coder_sign",  # 真实首页 2% 有值
        "self_pay",  # 费用表真实数据 0% 有值
        "pathology_no",  # 病理诊断行没有病理号；mr.pathology_id 取值不是病理号，不能使用
        "external_cause",  # 真实首页没有任何 V01–Y98 外因编码，损伤中毒外部原因未同步
    }
)

SOURCE_GAP_REASON = "首页同步未带入该字段"

# 等级阈值：≥ 90 优秀，75–90 合格，< 75 不合格
GRADE_EXCELLENT = 90.0
GRADE_QUALIFIED = 75.0


def grade_of(score: float) -> str:
    if score >= GRADE_EXCELLENT:
        return "excellent"
    if score >= GRADE_QUALIFIED:
        return "qualified"
    return "unqualified"


GRADE_LABELS = {"excellent": "优秀", "qualified": "合格", "unqualified": "不合格"}
