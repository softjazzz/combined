"""
主诊断规则裁决模块

基于《住院病案首页数据填写质量规范（暂行）》第 10、11(2)、11(5)、22 条，
对 LLM 提取的诊断列表进行规则化裁决，必要时重排主诊断。

设计原则：
- 纯函数，不依赖外部状态
- 不改接口结构，不影响前端主流程
- 在 resolve_diagnosis_codes 前调用，确保重排后的主诊断拿到正确 ICD
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 疾病-手术关联词典：手术关键词 → 相关诊断关键词
# ============================================================================

PROC_DIAG_ALIGNMENT: Dict[str, List[str]] = {
    "冠状动脉": ["冠心病", "冠状动脉粥样硬化", "心绞痛", "心肌梗", "急性冠脉"],
    "支架": ["冠心病", "冠状动脉", "心绞痛", "心肌梗", "急性冠脉"],
    "PCI": ["冠心病", "冠状动脉", "心绞痛", "心肌梗", "急性冠脉"],
    "搭桥": ["冠心病", "冠状动脉粥样硬化"],
    "CABG": ["冠心病", "冠状动脉粥样硬化"],
    "起搏器": ["心律失常", "房室传导阻滞", "病态窦房结", "心动过缓"],
    "射频消融": ["心律失常", "房颤", "房扑", "室上性心动过速", "预激综合征"],
    "瓣膜": ["瓣膜", "瓣狭窄", "瓣关闭不全", "风湿性心脏"],
    "关节置换": ["骨关节炎", "关节退行", "股骨头坏死", "股骨颈骨折"],
    "椎间盘": ["椎间盘突出", "腰椎", "颈椎", "椎管狭窄"],
    "脊柱": ["脊柱", "椎体骨折", "脊髓", "腰椎", "颈椎"],
    "阑尾": ["阑尾炎", "阑尾"],
    "胆囊": ["胆囊炎", "胆石症", "胆管结石", "胆囊息肉"],
    "甲状腺": ["甲状腺", "甲亢", "甲减", "甲状腺癌"],
    "子宫": ["子宫肌瘤", "子宫内膜", "子宫脱垂", "子宫腺肌"],
    "剖宫产": ["妊娠", "分娩", "胎位不正", "瘢痕子宫", "前置胎盘"],
    "肺叶切除": ["肺癌", "肺肿瘤", "肺结节"],
    "肾切除": ["肾癌", "肾肿瘤", "肾细胞癌"],
    "肝切除": ["肝癌", "肝肿瘤", "肝细胞癌"],
    "胃切除": ["胃癌", "胃肿瘤"],
    "结肠": ["结肠癌", "结肠肿瘤", "结肠息肉"],
    "直肠": ["直肠癌", "直肠肿瘤"],
    "乳腺": ["乳腺癌", "乳腺肿瘤"],
    "开颅": ["脑出血", "颅内肿瘤", "脑膜瘤", "脑外伤"],
    "血管介入": ["脑梗", "脑血管", "动脉狭窄", "动脉瘤"],
    "透析": ["肾功能衰竭", "尿毒症", "肾衰"],
    "内镜": ["消化道出血", "食管", "胃溃疡", "息肉"],
}

# 状态/既往类关键词 — 通常不应作为主诊断
_STATUS_KEYWORDS = ["后状态", "术后", "植入后", "既往", "病史", "陈旧性"]

# 治疗性操作关键词
_THERAPEUTIC_PROC_KEYWORDS = [
    "植入", "置入", "置换", "切除", "修复", "成形", "消融", "取栓",
    "引流", "搭桥", "吻合", "移植", "介入治疗", "支架",
]

# 诊断性操作关键词（不能压过治疗性诊断）
_DIAGNOSTIC_PROC_KEYWORDS = ["造影", "活检", "穿刺", "镜检", "探查"]

# 资源消耗/严重度关键词
_SEVERITY_KEYWORDS = [
    "重症", "不稳定", "急性", "危重", "监护", "ICU", "介入",
    "手术", "PCI", "CABG", "透析", "化疗", "放疗",
]

# 更换主诊断的最低分差阈值（避免微小差异导致不必要变动）
_REPLACE_THRESHOLD = 1.5


# ============================================================================
# 辅助函数
# ============================================================================

def _canonical_key(text: str) -> str:
    """诊断/手术文本标准化 key（去空白标点，小写）"""
    return re.sub(
        r"[\s,，;；、:：()（）\[\]【】\.\-_/+]+", "", str(text or "")
    ).lower()


def _compute_procedure_alignment(diagnosis: str, main_procedure: str) -> float:
    """计算诊断与主要手术的语义一致性分数 [0, 1]"""
    if not main_procedure or not diagnosis:
        return 0.0

    diag_lower = diagnosis.lower()
    proc_lower = main_procedure.lower()

    # 方法 1：通过关联词典匹配（最强信号）
    for proc_keyword, diag_keywords in PROC_DIAG_ALIGNMENT.items():
        if proc_keyword.lower() in proc_lower:
            for dk in diag_keywords:
                if dk.lower() in diag_lower:
                    return 1.0

    # 方法 2：直接子串匹配（前 4 字符重叠）
    diag_key = _canonical_key(diagnosis)
    proc_key = _canonical_key(main_procedure)
    if diag_key and proc_key:
        min_len = min(4, len(diag_key), len(proc_key))
        if min_len >= 2:
            if diag_key[:min_len] in proc_key or proc_key[:min_len] in diag_key:
                return 0.7

    return 0.0


def _compute_resource_burden(diagnosis: str, text_lines: List[str]) -> float:
    """搜索病历原文中与该诊断相关的资源消耗/严重度证据 [0, 1]"""
    if not text_lines or not diagnosis:
        return 0.0

    keywords = [
        x for x in re.split(r"[\s,，;；、:：()（）\[\]【】+\-/]+", diagnosis)
        if len(x) >= 2
    ]
    keywords = [x for x in keywords if x not in {"诊断", "疾病", "状态", "综合征"}]
    if not keywords:
        return 0.0

    hits = 0
    for line in text_lines:
        has_diag = any(k in line for k in keywords[:4])
        has_severity = any(k in line for k in _SEVERITY_KEYWORDS)
        if has_diag and has_severity:
            hits += 1
            if hits >= 3:
                break

    return min(1.0, hits / 3.0)


# ============================================================================
# 主函数
# ============================================================================

def apply_main_diagnosis_guideline_rules(
    medical_text: str,
    diagnoses: Dict[str, Any],
    procedures: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    主诊断规则裁决函数（纯函数，无副作用）。

    基于《住院病案首页数据填写质量规范》第 10、11(2)、11(5)、22 条，
    对 LLM 提取的诊断列表进行规则裁决，必要时重排主诊断。

    Args:
        medical_text: 病历原文
        diagnoses:  诊断字典 (discharge_main_diagnosis_text, discharge_other_diagnoses_texts, ...)
        procedures: 手术字典 (main_procedure_text, ...)

    Returns:
        (修正后的 diagnoses, rule_trace 审计日志)
    """
    rule_trace: List[Dict[str, Any]] = []
    diag = dict(diagnoses)  # 浅拷贝

    current_main = str(diag.get("discharge_main_diagnosis_text") or "").strip()
    if not current_main:
        rule_trace.append({"rule": "skip", "reason": "无主诊断，跳过裁决"})
        return diag, rule_trace

    # —— 候选池 ——
    others_raw = diag.get("discharge_other_diagnoses_texts") or []
    if not isinstance(others_raw, list):
        others_raw = []

    all_candidates: List[str] = [current_main]
    seen_keys = {_canonical_key(current_main)}
    for o in others_raw:
        o = str(o or "").strip()
        if not o:
            continue
        key = _canonical_key(o)
        if key and key not in seen_keys:
            seen_keys.add(key)
            all_candidates.append(o)

    if len(all_candidates) < 2:
        rule_trace.append({"rule": "skip", "reason": "仅有1个候选，无需裁决"})
        return diag, rule_trace

    # —— 手术信息 ——
    main_proc = (
        str(procedures.get("main_procedure_text") or "").strip()
        if isinstance(procedures, dict) else ""
    )
    proc_is_therapeutic = main_proc and any(
        k in main_proc for k in _THERAPEUTIC_PROC_KEYWORDS
    )
    proc_is_diagnostic_only = main_proc and (
        any(k in main_proc for k in _DIAGNOSTIC_PROC_KEYWORDS)
        and not proc_is_therapeutic
    )

    # —— 全文行池 ——
    text_lines: List[str] = []
    if medical_text:
        for ln in medical_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            s = ln.strip()
            if s and len(s) >= 4:
                text_lines.append(s)

    # —— 为每个候选计算特征分数 ——
    scored: List[Tuple[float, str, Dict[str, Any]]] = []
    for cand in all_candidates:
        features: Dict[str, Any] = {}

        # R1: 第11(5)条 — 状态/既往降权
        is_status = any(k in cand for k in _STATUS_KEYWORDS)
        features["is_status_like"] = is_status

        # R2: 第11(2)+第22条 — 手术一致性
        proc_align = _compute_procedure_alignment(cand, main_proc)
        features["procedure_alignment"] = proc_align

        # R3: 第10条 — 资源消耗/严重度
        burden = _compute_resource_burden(cand, text_lines)
        features["resource_burden_score"] = round(burden, 3)

        # 综合评分
        score = proc_align * 5.0 + burden * 2.0
        if is_status:
            score -= 4.0
        if proc_is_diagnostic_only and proc_align > 0:
            score -= proc_align * 2.5

        features["total_score"] = round(score, 2)
        scored.append((score, cand, features))

    scored.sort(key=lambda x: x[0], reverse=True)
    recommended = scored[0][1]
    recommended_key = _canonical_key(recommended)
    current_key = _canonical_key(current_main)

    rule_trace.append({
        "rule": "候选评分",
        "candidates": [
            {"diagnosis": s[1], "score": s[2]["total_score"], "features": s[2]}
            for s in scored[:6]
        ],
    })

    # —— 判断是否更换 ——
    if recommended_key != current_key:
        current_score = next(
            (s[0] for s in scored if _canonical_key(s[1]) == current_key),
            scored[0][0],
        )
        score_diff = scored[0][0] - current_score

        if score_diff >= _REPLACE_THRESHOLD:
            old_main = current_main
            new_main = recommended
            new_main_key = _canonical_key(new_main)

            # 重建其他诊断列表
            new_others: List[str] = [
                c for c in all_candidates if _canonical_key(c) != new_main_key
            ]
            diag["discharge_main_diagnosis_text"] = new_main
            diag["discharge_other_diagnoses_texts"] = new_others

            # 同步重排 ICD 编码
            old_main_icd = diag.get("discharge_main_icd")
            old_other_icds = diag.get("discharge_other_icds") or []
            if not isinstance(old_other_icds, list):
                old_other_icds = []

            new_main_idx = next(
                (i for i, c in enumerate(all_candidates)
                 if _canonical_key(c) == new_main_key),
                -1,
            )
            if new_main_idx > 0:
                other_idx = new_main_idx - 1
                new_main_icd = (
                    old_other_icds[other_idx]
                    if other_idx < len(old_other_icds) else None
                )
                new_other_icds: List[Any] = []
                for i, cand in enumerate(all_candidates):
                    if _canonical_key(cand) == new_main_key:
                        continue
                    if i == 0:
                        new_other_icds.append(old_main_icd)
                    else:
                        oidx = i - 1
                        new_other_icds.append(
                            old_other_icds[oidx]
                            if oidx < len(old_other_icds) else None
                        )
                diag["discharge_main_icd"] = new_main_icd
                diag["discharge_other_icds"] = new_other_icds
            else:
                diag["discharge_main_icd"] = None
                diag["discharge_other_icds"] = [None] * len(new_others)

            # 命中规则说明
            hit_rules: List[str] = []
            rec_f = scored[0][2]
            cur_f = next(
                (s[2] for s in scored if _canonical_key(s[1]) == current_key), {}
            )
            if rec_f.get("procedure_alignment", 0) > cur_f.get("procedure_alignment", 0):
                hit_rules.append("第11条第(2)款+第22条：主诊断应与主要手术一致")
            if cur_f.get("is_status_like"):
                hit_rules.append("第11条第(5)款：术后/既往状态不宜作为主诊断")
            if not hit_rules:
                hit_rules.append("第10条：选择对健康危害最大、资源消耗最多的疾病")

            rule_trace.append({
                "rule": "主诊断更换",
                "action": "replaced",
                "old_main": old_main,
                "new_main": new_main,
                "score_diff": round(score_diff, 2),
                "hit_rules": hit_rules,
                "reason": (
                    f"规则裁决: 「{old_main}」→「{new_main}」(分差 {score_diff:.1f})"
                ),
            })
            logger.info(
                "主诊断规则裁决: %s → %s (分差=%.2f, 规则=%s)",
                old_main, new_main, score_diff, ", ".join(hit_rules),
            )
        else:
            rule_trace.append({
                "rule": "主诊断保留",
                "action": "kept",
                "reason": (
                    f"推荐「{recommended}」但分差仅 {score_diff:.2f}，"
                    f"未达阈值 {_REPLACE_THRESHOLD}"
                ),
            })
    else:
        rule_trace.append({
            "rule": "主诊断保留",
            "action": "kept",
            "reason": "当前主诊断与规则裁决推荐一致",
        })

    return diag, rule_trace
