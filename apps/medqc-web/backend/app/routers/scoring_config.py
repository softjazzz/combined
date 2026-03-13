"""评分阈值配置 API — 管理甲乙丙等级的分数线"""

from fastapi import APIRouter, Depends
from ..utils import success_response, get_trace_id
from fastapi import Request


# 占位：auth 模块暂未实现，跳过认证
async def get_current_user():
    return {"user": "dev"}

router = APIRouter(prefix="/scoring-config", tags=["evaluator-config"])

# ========== 内存存储 ==========
_scoring_config = {
    "grade_thresholds": {
        "甲": {"min_score": 90, "label": "甲级", "color": "#52c41a", "description": "病历质量优秀"},
        "乙": {"min_score": 70, "label": "乙级", "color": "#faad14", "description": "病历质量合格"},
        "丙": {"min_score": 0, "label": "丙级", "color": "#ff4d4f", "description": "病历质量不合格"},
    },
    "deduction_rules": {
        "critical": {"max_deduction": 30, "description": "关键缺陷最大扣分"},
        "major": {"max_deduction": 15, "description": "重要缺陷最大扣分"},
        "minor": {"max_deduction": 5, "description": "一般缺陷最大扣分"},
    },
    "base_score": 100,
    "pass_score": 70,
}


def get_grade(score: int) -> str:
    """根据配置的阈值计算等级"""
    thresholds = _scoring_config["grade_thresholds"]
    if score >= thresholds["甲"]["min_score"]:
        return "甲"
    elif score >= thresholds["乙"]["min_score"]:
        return "乙"
    else:
        return "丙"


@router.get("")
async def get_scoring_config(request: Request, _user=Depends(get_current_user)):
    """获取当前评分阈值配置"""
    return success_response(
        data=_scoring_config,
        message="获取评分配置成功",
        trace_id=get_trace_id(request),
    )


@router.put("")
async def update_scoring_config(request: Request, _user=Depends(get_current_user)):
    """更新评分阈值配置"""
    body = await request.json()

    # 更新等级阈值
    if "grade_thresholds" in body:
        for grade, config in body["grade_thresholds"].items():
            if grade in _scoring_config["grade_thresholds"]:
                _scoring_config["grade_thresholds"][grade].update(config)

    # 更新扣分规则
    if "deduction_rules" in body:
        for severity, config in body["deduction_rules"].items():
            if severity in _scoring_config["deduction_rules"]:
                _scoring_config["deduction_rules"][severity].update(config)

    # 更新基础分/及格线
    if "base_score" in body:
        _scoring_config["base_score"] = body["base_score"]
    if "pass_score" in body:
        _scoring_config["pass_score"] = body["pass_score"]

    return success_response(
        data=_scoring_config,
        message="评分配置更新成功",
        trace_id=get_trace_id(request),
    )


@router.post("/preview")
async def preview_grade(request: Request, _user=Depends(get_current_user)):
    """预览分数对应的等级"""
    body = await request.json()
    score = body.get("score", 0)
    grade = get_grade(score)
    threshold_info = _scoring_config["grade_thresholds"][grade]

    return success_response(
        data={
            "score": score,
            "grade": grade,
            "label": threshold_info["label"],
            "color": threshold_info["color"],
            "description": threshold_info["description"],
        },
        message="等级预览成功",
        trace_id=get_trace_id(request),
    )
