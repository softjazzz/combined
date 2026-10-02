"""助手可办理能力的权威说明：只列出已接通的操作，未接通的给出明确原因，不放静默无效入口。"""
from __future__ import annotations

# 每项均对应已核查的真实调用链；状态变化须同步修改此表及其测试。
AVAILABLE = {
    "doctor": [
        ("单病例复检预览", "为当前病例的明确规则生成预览，用户点击确认后由正式质控任务服务创建任务；材料同步未证实时会提示"),
        ("参考补充草稿", "仅不合规问题，依据保存结论与证据摘录起草，不写入病历、不等于整改"),
        ("异议反馈", "对已查看的保存问题提交实名异议理由，不改变质控结论"),
    ],
    "manager": [
        ("专项质控任务预览", "对本会话已下钻的病例（最多20份）与明确规则生成预览，用户点击确认后由正式质控任务服务创建任务"),
        ("科室趋势与跨期描述", "只读取正式统计原值，不计算差值或推断原因"),
    ],
}
UNAVAILABLE = [
    ("整改分派", "现有整改服务尚未提供保存问题到缺陷记录的权威映射、责任科室目录、逐病例授权和重复提交保护；助手不能代替业务流程分派"),
    ("催办", "现有催办接口只更新缺陷状态，未接入真实通知投递；助手不能把状态修改说成已送达"),
    ("写回 EMR 或修改病历", "首版不直接写入电子病历；修改需医生在病历系统中完成"),
    ("主动订阅与定期推送", "尚无调度、投递目标与停用合同；未配置时不会自动后台执行"),
    ("医生本人趋势", "缺少账号与医生工号的授权映射，正式统计也无按医生过滤的合同"),
]


def capabilities(view: str) -> dict:
    available = AVAILABLE.get(view, [])
    lines = ["可办理：", *[f"· {name}：{note}" for name, note in available], "", "暂不可办理：",
             *[f"· {name}：{reason}" for name, reason in UNAVAILABLE]]
    return {"available": [name for name, _ in available], "unavailable": [{"name": name, "reason": reason} for name, reason in UNAVAILABLE],
            "references": [{"id": f"capabilities:{view}", "kind": "evidence", "title": "助手可办理事项说明",
                            "locator": "按当前已接通的业务服务说明；不可办理事项不提供入口", "text": "\n".join(lines)}]}
