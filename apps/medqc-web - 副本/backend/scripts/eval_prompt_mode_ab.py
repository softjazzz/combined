"""
Prompt Mode A/B 对比评测脚本（直接调用 Service，无需 Web 服务）

用法：
  python scripts/eval_prompt_mode_ab.py                # 跑 4 种模式
  python scripts/eval_prompt_mode_ab.py --modes plan_a plan_b  # 只跑指定模式
  python scripts/eval_prompt_mode_ab.py --doc-type 手术记录     # 指定文书类型
"""
import asyncio
import json
import time
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 确保 backend 目录在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)


# ==================== 测试病历 ====================

TEST_CASES: Dict[str, Dict[str, str]] = {
    "入院记录": {
        "document_id": "ab-test-admission-001",
        "content": """入院记录

姓名：张三  性别：男  年龄：65岁  婚姻：已婚  职业：退休
入院日期：2025-03-01 14:30  记录日期：2025-03-01 16:00  病史陈述者：患者本人

主诉：反复胸闷、气促3年余，加重伴双下肢水肿1周。

现病史：
患者3年前无明显诱因出现活动后胸闷、气促，休息后可缓解，未予重视及系统诊治。此后上述症状反复发作，活动耐力逐渐下降。1周前受凉后上述症状加重，出现静息状态下胸闷气促，夜间不能平卧，伴双下肢凹陷性水肿，伴咳嗽、咳白色泡沫痰，无发热、胸痛、咯血，无头晕、黑矇，无腹胀、腹痛。曾在基层医院就诊，予以利尿、扩血管治疗后症状改善不明显，为求进一步诊治来我院，门诊以"心力衰竭"收入我科。

既往史：
高血压病史10年，最高血压180/110mmHg，长期服用氨氯地平5mg qd，血压控制尚可。糖尿病病史5年，口服二甲双胍500mg tid，血糖控制一般。否认冠心病、脑血管病史。否认肝炎、结核等传染病史。否认手术外伤史。否认药物食物过敏史。否认输血史。

个人史：
生于原籍，久居本地。否认疫区居住史及传染病接触史。吸烟30年，每日约20支，已戒烟5年。饮酒史20年，每日约100ml白酒，已戒酒3年。

家族史：
父亲因"脑出血"去世，母亲因"心肌梗塞"去世。兄弟姐妹体健。子女体健。否认家族遗传病史。

体格检查：
T 36.5℃  P 92次/分  R 22次/分  BP 156/98mmHg
一般情况：慢性病容，端坐位，精神差，自动体位，查体合作。
皮肤粘膜：无黄染、出血点、蜘蛛痣、肝掌。浅表淋巴结未触及肿大。
头颈部：头颅大小正常，双侧瞳孔等大等圆，光反射灵敏。口唇轻度发绀。颈静脉充盈。甲状腺未触及肿大。
胸部：桶状胸。双肺呼吸音粗，双下肺可闻及湿啰音。心界向左下扩大，心率92次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
腹部：腹软，无压痛反跳痛，肝脾肋下未触及。移动性浊音阴性。
四肢：双下肢凹陷性水肿（++），四肢肌力正常。
神经系统：生理反射存在，病理反射未引出。

辅助检查：
心电图：窦性心律，左心室肥厚。
胸片：心影增大，双肺淤血。
BNP：1850pg/ml。
心脏彩超（外院2025-02-28）：左室射血分数35%，左心扩大。

初步诊断：
1. 慢性心力衰竭急性加重
2. 高血压病3级 极高危
3. 2型糖尿病
4. 肺部感染

诊疗计划：
1. 完善相关检查
2. 强心、利尿、扩血管治疗
3. 控制血压血糖
4. 抗感染治疗
5. 必要时转ICU

医师签名：李四  2025-03-01 16:00
""",
    },
    "手术记录": {
        "document_id": "ab-test-surgery-001",
        "content": """手术记录

患者姓名：王五  性别：男  年龄：52岁  住院号：20250301-002
手术日期：2025-03-02  手术开始时间：09:30  手术结束时间：11:45

术前诊断：右肺上叶周围型肺癌（cT2aN0M0 IIa期）
术后诊断：右肺上叶周围型肺癌（pT2aN0M0 IIa期）

手术名称：胸腔镜下右肺上叶切除术 + 纵隔淋巴结清扫术
麻醉方式：全身麻醉（双腔气管插管）
手术人员：主刀：赵六  一助：孙七  二助：周八  麻醉：郑九

手术经过：
全麻成功后，患者取左侧卧位。常规消毒铺巾。于右侧腋中线第7肋间作1.5cm切口为观察孔，置入胸腔镜。探查见右肺上叶后段一约3.5cm×3.0cm肿物，质硬，与周围粘连不明显。胸腔内无明显积液。

于右侧腋前线第4肋间作3cm操作孔，听诊三角处作2cm辅助操作孔。先处理肺裂，使用直线切割缝合器离断叶间裂。依次解剖右肺上叶动脉分支，分别结扎切断尖段动脉、前段动脉。解剖右上肺静脉，使用血管切割闭合器离断。最后离断右上叶支气管，使用支气管切割闭合器离断并加固缝合。标本装入标本袋经操作孔取出。

系统清扫纵隔淋巴结：2R、4R、7组、10R组，送快速冰冻：均未见转移（0/12枚）。

术中出血约150ml，未输血。冲洗胸腔，检查无活动性出血及漏气。留置28F胸腔引流管1根。清点器械敷料无误，逐层关胸。

术后医嘱：
1. 送ICU监护
2. 持续心电监护、血氧监测
3. 胸管引流并记录
4. 预防性抗感染治疗
5. 镇痛泵持续镇痛

标本送病理检查。

手术医师签名：赵六
记录医师签名：孙七
记录时间：2025-03-02 12:30
""",
    },
}


# ==================== 直接调用 Service ====================

async def evaluate_with_mode(
    service,
    document_id: str,
    content: str,
    document_type: str,
    prompt_mode: str,
) -> Dict[str, Any]:
    """直接调用 SichuanQCService.evaluate_document_fast"""
    start = time.time()
    try:
        result = await service.evaluate_document_fast(
            document_id=f"{document_id}-{prompt_mode}",
            content=content,
            document_type=document_type,
            prompt_mode=prompt_mode,
        )
        elapsed = time.time() - start
        result["_elapsed"] = elapsed
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": time.time() - start}


# ==================== 结果分析 ====================

def analyze_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """从评测结果中提取关键指标"""
    if "error" in result:
        return {
            "status": "error",
            "error": result["error"],
            "elapsed": result.get("_elapsed", 0),
        }

    eval_summary = result.get("evaluation_summary", {})
    eval_results = result.get("evaluation_results", [])

    total_rules = eval_summary.get("total_rules", 0)
    compliant = eval_summary.get("compliant_rules", 0)
    issues = eval_summary.get("issues_found", 0)
    compliance_rate = eval_summary.get("compliance_rate", 0)
    tokens = result.get("token_usage", {}).get("total_tokens", 0)

    # 统计每条规则的判定
    non_compliant_rules = []
    for r in eval_results:
        if not r.get("is_compliant", True):
            non_compliant_rules.append({
                "rule_id": r.get("rule_id"),
                "rule_name": r.get("rule_name"),
                "findings": (r.get("findings") or "")[:100],
                "confidence": r.get("confidence", 0),
            })

    return {
        "status": "ok",
        "total_rules": total_rules,
        "compliant_rules": compliant,
        "issues_found": issues,
        "compliance_rate": round(compliance_rate, 2),
        "grade": eval_summary.get("overall_grade", "?"),
        "elapsed": round(result.get("_elapsed", 0), 2),
        "tokens": tokens,
        "model": result.get("model", "unknown"),
        "prompt_mode": result.get("prompt_mode", "unknown"),
        "non_compliant_rules": non_compliant_rules,
    }


# ==================== 对比报告 ====================

def generate_comparison_report(
    doc_type: str,
    model_name: str,
    results: Dict[str, Dict[str, Any]],
) -> str:
    """生成对比报告"""
    lines = []
    lines.append("=" * 80)
    lines.append(f"📊 Prompt Mode A/B 对比报告 — {doc_type}")
    lines.append(f"   模型: {model_name} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 80)
    lines.append("")

    # 汇总表
    header = f"{'指标':<16} |"
    for mode in results:
        header += f" {mode:>12} |"
    lines.append(header)
    lines.append("-" * len(header))

    metrics = [
        ("总规则数", "total_rules"),
        ("合规规则数", "compliant_rules"),
        ("问题数", "issues_found"),
        ("合规率", "compliance_rate"),
        ("等级", "grade"),
        ("耗时(s)", "elapsed"),
        ("Token数", "tokens"),
    ]

    for label, key in metrics:
        row = f"{label:<16} |"
        for mode, data in results.items():
            val = data.get(key, "N/A")
            if key == "compliance_rate" and isinstance(val, (int, float)):
                val = f"{val:.1f}%"
            elif key == "elapsed" and isinstance(val, (int, float)):
                val = f"{val:.1f}s"
            row += f" {str(val):>12} |"
        lines.append(row)

    lines.append("")

    # 各模式发现的问题明细
    for mode, data in results.items():
        issues = data.get("non_compliant_rules", [])
        lines.append(f"\n--- {mode} 发现 {len(issues)} 个问题 ---")
        if not issues:
            lines.append("  （无问题）")
        for issue in issues:
            conf = issue.get("confidence", 0)
            lines.append(f"  [{issue['rule_id']}] {issue['rule_name']} (置信度: {conf})")
            lines.append(f"    {issue['findings']}")

    # 一致性分析
    lines.append("\n" + "=" * 80)
    lines.append("📋 一致性分析")
    lines.append("=" * 80)

    all_issue_sets = {}
    for mode, data in results.items():
        issue_ids = {i["rule_id"] for i in data.get("non_compliant_rules", [])}
        all_issue_sets[mode] = issue_ids

    if all_issue_sets:
        common = set.intersection(*all_issue_sets.values()) if all_issue_sets else set()
        lines.append(f"\n所有模式一致发现的问题: {sorted(common) if common else '无'}")

        for mode, ids in all_issue_sets.items():
            others = set.union(*(v for k, v in all_issue_sets.items() if k != mode)) if len(all_issue_sets) > 1 else set()
            unique = ids - others
            if unique:
                lines.append(f"{mode} 独有发现: {sorted(unique)}")

    lines.append("")
    return "\n".join(lines)


# ==================== 主流程 ====================

async def run_ab_test(
    doc_types: Optional[List[str]] = None,
    modes: Optional[List[str]] = None,
):
    """运行 A/B 对比测试"""
    from app.services.sichuan_qc_service import SichuanQCService

    all_modes = modes or ["current", "plan_a", "plan_b", "plan_c"]
    test_doc_types = doc_types or list(TEST_CASES.keys())

    # 初始化服务
    logger.info("初始化 SichuanQCService ...")
    service = SichuanQCService()
    model_name = service.client.model
    logger.info(f"模型: {model_name}")
    logger.info(f"API: {service.client.api_endpoint}")

    reports = []
    all_data = {}  # 保存全部原始数据

    for doc_type in test_doc_types:
        if doc_type not in TEST_CASES:
            logger.warning(f"未找到 '{doc_type}' 的测试病历，跳过")
            continue

        case = TEST_CASES[doc_type]
        logger.info(f"\n{'='*60}")
        logger.info(f"开始测试: {doc_type} ({len(case['content'])} 字)")
        logger.info(f"{'='*60}")

        mode_results = {}
        for mode in all_modes:
            logger.info(f"  ▶ 运行 prompt_mode={mode} ...")
            result = await evaluate_with_mode(
                service,
                case["document_id"],
                case["content"],
                doc_type,
                mode,
            )
            analysis = analyze_result(result)
            mode_results[mode] = analysis

            if analysis["status"] == "ok":
                logger.info(
                    f"    ✅ 合规率: {analysis['compliance_rate']}%, "
                    f"问题: {analysis['issues_found']}, "
                    f"耗时: {analysis['elapsed']}s, "
                    f"Token: {analysis['tokens']}"
                )
            else:
                logger.error(f"    ❌ 错误: {analysis['error']}")

        all_data[doc_type] = mode_results
        report = generate_comparison_report(doc_type, model_name, mode_results)
        reports.append(report)
        print("\n" + report)

    # 保存报告
    out_dir = Path(__file__).resolve().parent.parent / "reports"
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = out_dir / f"prompt_mode_ab_{timestamp}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(reports))
    logger.info(f"\n📄 文本报告: {report_path}")

    json_path = out_dir / f"prompt_mode_ab_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    logger.info(f"📊 JSON 数据: {json_path}")

    logger.info(f"\n🎯 评测完成！共 {len(test_doc_types)} 个文书类型 × {len(all_modes)} 种模式")


def main():
    parser = argparse.ArgumentParser(description="Prompt Mode A/B 对比评测")
    parser.add_argument("--modes", nargs="+", default=None,
                        help="要测试的 prompt_mode（默认全部 4 种）")
    parser.add_argument("--doc-type", nargs="+", default=None,
                        help="要测试的文书类型（默认全部）")
    args = parser.parse_args()

    asyncio.run(run_ab_test(
        doc_types=args.doc_type,
        modes=args.modes,
    ))


if __name__ == "__main__":
    main()
