"""
评分阈值配置 API（PG 版）— 管理甲乙丙等级的分数线

数据源：PostgreSQL scoring_config 表
每条记录为一个 config_key（如 'grade_thresholds'）及其 JSON config_value。
"""

import copy
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user, require_roles

router = APIRouter(prefix="/api/v1/scoring-config", tags=["evaluator-config"])
logger = logging.getLogger(__name__)

# 默认配置（当 PG 表为空时作为 seed 数据的模板）
_DEFAULT_CONFIG = {
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


def _ensure_db():
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    return sb


async def _load_config(sb) -> dict:
    """从 PG 加载所有 scoring_config 行组装为完整配置 dict。"""
    resp = await async_execute(sb.table('scoring_config').select('*'))
    rows = list(getattr(resp, 'data', None) or [])
    if not rows:
        return copy.deepcopy(_DEFAULT_CONFIG)

    config = {}
    for row in rows:
        key = row.get('config_key', '')
        raw = row.get('config_value', '{}')
        try:
            config[key] = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            config[key] = raw
    # 补全不存在于 PG 的默认键
    for k, v in _DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = copy.deepcopy(v)
    return config


async def _save_config_key(sb, key: str, value, user_id: str = "system"):
    """保存/更新单个 config_key 到 PG。"""
    val_str = json.dumps(value, ensure_ascii=False, default=str)
    now = datetime.now().isoformat()

    # 尝试更新
    resp = await async_execute(
        sb.table('scoring_config').update({
            "config_value": val_str,
            "updated_by": user_id,
            "updated_at": now,
        }).eq('config_key', key).select()
    )
    if getattr(resp, 'data', None):
        return

    # 不存在则插入
    await async_execute(
        sb.table('scoring_config').insert({
            "id": str(uuid.uuid4()),
            "config_key": key,
            "config_value": val_str,
            "description": "",
            "updated_by": user_id,
            "updated_at": now,
        })
    )


def _load_grade_thresholds_sync() -> dict:
    """同步优先读取数据库持久化的 grade_thresholds，不可用时回退默认阈值。"""
    thresholds = copy.deepcopy(_DEFAULT_CONFIG["grade_thresholds"])
    sb = get_supabase()
    if sb is None:
        return thresholds
    try:
        resp = sb.table('scoring_config').select('*').eq('config_key', 'grade_thresholds').execute()
        rows = list(getattr(resp, 'data', None) or [])
        if not rows:
            return thresholds
        raw = rows[0].get('config_value', '{}')
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict):
            for grade, cfg in parsed.items():
                if grade in thresholds and isinstance(cfg, dict):
                    thresholds[grade].update(cfg)
                elif isinstance(cfg, dict):
                    thresholds[grade] = dict(cfg)
    except Exception as e:
        logger.warning(f"读取数据库评分阈值失败，回退默认配置: {e}")
    return thresholds


def get_grade(score: int) -> str:
    """根据数据库持久化评分阈值计算等级（同步辅助函数，供其他模块调用）。"""
    thresholds = _load_grade_thresholds_sync()
    if score >= thresholds["甲"]["min_score"]:
        return "甲"
    elif score >= thresholds["乙"]["min_score"]:
        return "乙"
    else:
        return "丙"


@router.get("")
async def get_scoring_config(request: Request, current_user: dict = Depends(get_current_user)):
    """获取当前评分阈值配置"""
    sb = _ensure_db()
    try:
        config = await _load_config(sb)
        return success_response(data=config, message="获取评分配置成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取评分配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取评分配置失败: {str(e)}")


@router.put("")
async def update_scoring_config(
    request: Request,
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    """更新评分阈值配置"""
    sb = _ensure_db()
    body = await request.json()
    user_id = current_user.get("id") or current_user.get("user_id") or "system"

    try:
        config = await _load_config(sb)

        # 合并更新
        if "grade_thresholds" in body:
            for grade, cfg in body["grade_thresholds"].items():
                if grade in config.get("grade_thresholds", {}):
                    config["grade_thresholds"][grade].update(cfg)
            await _save_config_key(sb, "grade_thresholds", config["grade_thresholds"], user_id)

        if "deduction_rules" in body:
            for sev, cfg in body["deduction_rules"].items():
                if sev in config.get("deduction_rules", {}):
                    config["deduction_rules"][sev].update(cfg)
            await _save_config_key(sb, "deduction_rules", config["deduction_rules"], user_id)

        for key in ("base_score", "pass_score"):
            if key in body:
                config[key] = body[key]
                await _save_config_key(sb, key, body[key], user_id)

        return success_response(data=config, message="评分配置更新成功", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新评分配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新评分配置失败: {str(e)}")


@router.post("/preview")
async def preview_grade(request: Request, current_user: dict = Depends(get_current_user)):
    """预览分数对应的等级"""
    sb = _ensure_db()
    body = await request.json()
    score = body.get("score", 0)

    try:
        config = await _load_config(sb)
        thresholds = config.get("grade_thresholds", _DEFAULT_CONFIG["grade_thresholds"])

        if score >= thresholds["甲"]["min_score"]:
            grade = "甲"
        elif score >= thresholds["乙"]["min_score"]:
            grade = "乙"
        else:
            grade = "丙"

        info = thresholds[grade]
        return success_response(
            data={
                "score": score,
                "grade": grade,
                "label": info.get("label", ""),
                "color": info.get("color", ""),
                "description": info.get("description", ""),
            },
            message="等级预览成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"等级预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"等级预览失败: {str(e)}")
