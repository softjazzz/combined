from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "backend/app/data/luxian_0609_rules_v1.json"
OUTPUT_DIR = REPO_ROOT / ".runtime-logs/qc-synthetic"


def now_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def build_doc(
    *,
    document_type: str,
    title: str,
    record_time: datetime,
    content: str,
    submit_offset_minutes: int = 0,
    doctor_name: str = "测试医师",
    doctor_code: str = "DOCTOR-TEST",
) -> Dict[str, Any]:
    submit_time = record_time + timedelta(minutes=submit_offset_minutes)
    return {
        "document_type": document_type,
        "title": title,
        "record_time": now_text(record_time),
        "submit_time": now_text(submit_time),
        "content": content.strip(),
        "doctor_name": doctor_name,
        "doctor_code": doctor_code,
        "enabled": True,
    }


@dataclass(frozen=True)
class RuleBlueprint:
    rule_id: str
    template_key: str
    expected_status: str
    trigger_facts: List[str]
    evidence_keywords: List[str]
    human_reason: str


def template_basic_timeliness() -> Dict[str, Any]:
    base = datetime(2026, 6, 1, 8, 0, 0)
    return {
        "case_title": "规则反推测试-基础时限缺陷",
        "basic_info": {
            "patient_name": "规则测试患者甲",
            "sex": "男",
            "age": 62,
            "mr_no": "RULE2CASE-001",
            "department": "神经内科",
            "admission_time": now_text(base),
            "discharge_time": now_text(base + timedelta(days=5)),
            "main_diagnosis": "脑梗死",
            "other_diagnoses": ["高血压", "2型糖尿病"],
        },
        "documents": [
            build_doc(
                document_type="admission_record",
                title="2026-06-02 入院记录",
                record_time=base + timedelta(hours=26),
                submit_offset_minutes=30,
                content="""
入院记录
患者因“言语不清伴右侧肢体乏力6小时”入院。
查体：神志清楚，右侧肢体肌力4级。
初步诊断：脑梗死；高血压病。
入院后予完善头颅CT、凝血功能、心电图等检查，给予改善循环及控制血压治疗。
""",
            ),
            build_doc(
                document_type="first_course_record",
                title="2026-06-01 首次病程记录",
                record_time=base + timedelta(hours=11),
                submit_offset_minutes=10,
                content="""
首次病程记录
病例特点：老年男性，急性起病，以言语不清、右侧肢体乏力为主要表现。
诊断依据：神经系统定位体征阳性，既往高血压病史。
诊疗计划：完善头颅MRI及血管评估，严密观察神经功能变化。
""",
            ),
            build_doc(
                document_type="senior_course_record",
                title="2026-06-04 上级医师查房记录",
                record_time=base + timedelta(hours=80),
                submit_offset_minutes=10,
                content="""
上级医师查房记录
副主任医师查房后认为患者目前脑梗死诊断明确，继续抗血小板、稳定斑块及康复治疗，
注意观察吞咽功能和肺部感染风险。
""",
                doctor_name="副主任医师A",
                doctor_code="DOC-SENIOR-A",
            ),
        ],
        "manual_issue_text": "按已选质控点自动反推出的基础时限测试病历。",
    }


def template_ct_mri_culture() -> Dict[str, Any]:
    base = datetime(2026, 6, 1, 8, 0, 0)
    return {
        "case_title": "规则反推测试-检查检验缺陷",
        "basic_info": {
            "patient_name": "规则测试患者乙",
            "sex": "女",
            "age": 64,
            "mr_no": "RULE2CASE-002",
            "department": "骨科",
            "admission_time": now_text(base),
            "discharge_time": now_text(base + timedelta(days=4)),
            "main_diagnosis": "腰椎间盘突出症",
            "other_diagnoses": [],
        },
        "documents": [
            build_doc(
                document_type="admission_record",
                title="2026-06-01 入院记录",
                record_time=base + timedelta(hours=1),
                submit_offset_minutes=10,
                content="""
入院记录
患者因腰痛伴右下肢麻木半月入院。
查体：腰椎活动受限，右下肢直腿抬高试验阳性。
初步诊断：腰椎间盘突出症。
""",
            ),
            build_doc(
                document_type="exam_report",
                title="腰椎MRI检查报告",
                record_time=base + timedelta(hours=6),
                content="""
影像检查报告
检查类型：腰椎MRI。
检查所见：L4/5椎间盘向右后方突出，压迫右侧神经根；椎管轻度狭窄。
报告结论：L4/5椎间盘突出并右侧神经根受压。
""",
            ),
            build_doc(
                document_type="lab_report",
                title="尿培养报告",
                record_time=base + timedelta(hours=30),
                content="""
检验报告
标本：尿液。
培养结果：大肠埃希菌阳性。
药敏提示：对头孢曲松敏感，对左氧氟沙星耐药。
""",
            ),
            build_doc(
                document_type="daily_course_record",
                title="2026-06-01 日常病程记录",
                record_time=base + timedelta(hours=10),
                submit_offset_minutes=10,
                content="""
日常病程记录
患者仍诉腰痛，右下肢麻木同前。
已完善腰椎MRI检查，继续予止痛、营养神经治疗。
""",
            ),
            build_doc(
                document_type="daily_course_record",
                title="2026-06-03 日常病程记录",
                record_time=base + timedelta(hours=52),
                submit_offset_minutes=10,
                content="""
日常病程记录
患者腰痛较前稍缓解，体温正常，继续对症治疗，嘱患者卧床休息并观察病情变化。
""",
            ),
        ],
        "manual_issue_text": "按已选质控点自动反推出的检查检验测试病历。",
    }


def template_consultation_quality() -> Dict[str, Any]:
    base = datetime(2026, 6, 1, 8, 0, 0)
    return {
        "case_title": "规则反推测试-会诊质量缺陷",
        "basic_info": {
            "patient_name": "规则测试患者丙",
            "sex": "男",
            "age": 59,
            "mr_no": "RULE2CASE-003",
            "department": "消化内科",
            "admission_time": now_text(base),
            "discharge_time": now_text(base + timedelta(days=3)),
            "main_diagnosis": "上消化道出血",
            "other_diagnoses": [],
        },
        "documents": [
            build_doc(
                document_type="consultation_record",
                title="会诊申请单",
                record_time=base + timedelta(hours=8),
                submit_offset_minutes=10,
                content="""
会诊申请单
申请科室：消化内科。
申请目的：请会诊。
病情摘要：患者黑便2天，伴头晕乏力，血红蛋白下降，已给予抑酸、补液治疗。
申请医师：测试医师。
""",
            ),
            build_doc(
                document_type="consultation_record",
                title="会诊记录单",
                record_time=base + timedelta(hours=13),
                submit_offset_minutes=10,
                content="""
会诊记录单
会诊科室：普外科。
会诊意见：建议完善相关检查，继续目前治疗，必要时调整用药。
会诊医师：会诊医师A。
""",
                doctor_name="会诊医师A",
                doctor_code="DOC-CONSULT-A",
            ),
            build_doc(
                document_type="daily_course_record",
                title="2026-06-02 日常病程记录",
                record_time=base + timedelta(hours=36),
                submit_offset_minutes=10,
                content="""
日常病程记录
患者黑便较前减少，诉乏力，继续抑酸、补液、止血治疗，密切观察生命体征及大便颜色。
""",
            ),
        ],
        "manual_issue_text": "按已选质控点自动反推出的会诊质量测试病历。",
    }


def template_surgery_anesthesia() -> Dict[str, Any]:
    base = datetime(2026, 6, 1, 8, 0, 0)
    return {
        "case_title": "规则反推测试-手术麻醉缺陷",
        "basic_info": {
            "patient_name": "规则测试患者丁",
            "sex": "女",
            "age": 47,
            "mr_no": "RULE2CASE-004",
            "department": "普通外科",
            "admission_time": now_text(base),
            "discharge_time": now_text(base + timedelta(days=4)),
            "main_diagnosis": "胆囊结石伴胆囊炎",
            "other_diagnoses": [],
        },
        "documents": [
            build_doc(
                document_type="presurg_discussion",
                title="术前讨论",
                record_time=base + timedelta(hours=6),
                submit_offset_minutes=10,
                content="""
术前讨论
患者诊断胆囊结石伴胆囊炎，有手术指征。
拟行腹腔镜胆囊切除术，已讨论手术风险、替代方案及围手术期处理。
""",
            ),
            build_doc(
                document_type="surgery_record",
                title="腹腔镜胆囊切除术手术记录",
                record_time=base + timedelta(hours=52),
                submit_offset_minutes=10,
                content="""
手术记录
手术开始时间：2026-06-01 10:00。
手术结束时间：2026-06-01 11:30。
手术名称：腹腔镜胆囊切除术。
术中见胆囊充血水肿，与周围组织轻度粘连，顺利切除胆囊。
""",
                doctor_name="术者A",
                doctor_code="DOC-SUR-A",
            ),
            build_doc(
                document_type="anesthesia_record",
                title="麻醉记录",
                record_time=base + timedelta(hours=53),
                submit_offset_minutes=10,
                content="""
麻醉记录
患者入室后建立静脉通路，监测生命体征。
麻醉方式：。
麻醉医师：王某。
麻醉医师代码：。
术中用药：按麻醉医嘱执行。
麻醉经过平稳，术毕安返病房。
""",
                doctor_name="麻醉医师王某",
                doctor_code="DOC-ANE-WANG",
            ),
        ],
        "manual_issue_text": "按已选质控点自动反推出的手术麻醉测试病历。",
    }


TEMPLATE_BUILDERS = {
    "basic_timeliness": template_basic_timeliness,
    "ct_mri_culture": template_ct_mri_culture,
    "consultation_quality": template_consultation_quality,
    "surgery_anesthesia": template_surgery_anesthesia,
}


RULE_BLUEPRINTS: Dict[str, RuleBlueprint] = {
    "LX0609-01-01-01": RuleBlueprint(
        rule_id="LX0609-01-01-01",
        template_key="basic_timeliness",
        expected_status="non_compliant",
        trigger_facts=["入院时间为2026-06-01 08:00", "入院记录记录时间为2026-06-02 10:00"],
        evidence_keywords=["入院记录", "2026-06-02", "超过24小时"],
        human_reason="入院记录完成时间晚于入院后24小时。",
    ),
    "LX0609-01-02-01": RuleBlueprint(
        rule_id="LX0609-01-02-01",
        template_key="basic_timeliness",
        expected_status="non_compliant",
        trigger_facts=["入院时间为2026-06-01 08:00", "首次病程记录时间为2026-06-01 19:00"],
        evidence_keywords=["首次病程记录", "8小时", "11小时"],
        human_reason="首次病程记录晚于入院后8小时。",
    ),
    "LX0609-02-01-01": RuleBlueprint(
        rule_id="LX0609-02-01-01",
        template_key="basic_timeliness",
        expected_status="non_compliant",
        trigger_facts=["入院48小时内未见主治医师首次查房记录"],
        evidence_keywords=["上级医师查房记录", "2026-06-04", "48小时内未见"],
        human_reason="入院后48小时内缺少主治医师首次查房记录。",
    ),
    "LX0609-06-01-05": RuleBlueprint(
        rule_id="LX0609-06-01-05",
        template_key="ct_mri_culture",
        expected_status="non_compliant",
        trigger_facts=["2026-06-01 14:00 腰椎MRI报告阳性", "24小时内病程未分析神经根受压与诊疗方案关系"],
        evidence_keywords=["腰椎MRI", "神经根受压", "继续予止痛、营养神经治疗"],
        human_reason="MRI阳性结果后24小时内未在病程中完成结果分析。",
    ),
    "LX0609-06-03-03": RuleBlueprint(
        rule_id="LX0609-06-03-03",
        template_key="ct_mri_culture",
        expected_status="non_compliant",
        trigger_facts=["尿培养大肠埃希菌阳性", "报告后24小时内病程未分析阳性菌和药敏结果"],
        evidence_keywords=["尿培养报告", "大肠埃希菌阳性", "药敏"],
        human_reason="培养阳性结果未在病程中及时分析并形成治疗调整依据。",
    ),
    "LX0609-03-01-01": RuleBlueprint(
        rule_id="LX0609-03-01-01",
        template_key="consultation_quality",
        expected_status="non_compliant",
        trigger_facts=["后续病程未记录会诊意见执行情况"],
        evidence_keywords=["日常病程记录", "未记录执行情况"],
        human_reason="病程未说明会诊意见是否采纳及执行结果。",
    ),
    "LX0609-03-01-02": RuleBlueprint(
        rule_id="LX0609-03-01-02",
        template_key="consultation_quality",
        expected_status="non_compliant",
        trigger_facts=["会诊申请目的仅写请会诊"],
        evidence_keywords=["会诊申请单", "申请目的：请会诊", "目的不明确"],
        human_reason="会诊目的未说明具体需要解决的问题。",
    ),
    "LX0609-03-01-03": RuleBlueprint(
        rule_id="LX0609-03-01-03",
        template_key="consultation_quality",
        expected_status="non_compliant",
        trigger_facts=["会诊意见使用必要时调整用药等泛化表述"],
        evidence_keywords=["会诊记录单", "必要时调整用药", "不具备可执行性"],
        human_reason="会诊意见缺少明确处理方案或可执行措施。",
    ),
    "LX0609-04-02-01": RuleBlueprint(
        rule_id="LX0609-04-02-01",
        template_key="surgery_anesthesia",
        expected_status="non_compliant",
        trigger_facts=["手术结束时间为2026-06-01 11:30", "手术记录记录时间为2026-06-03 12:00"],
        evidence_keywords=["手术结束时间", "记录时间", "超过术后24小时"],
        human_reason="手术记录完成时间超过术后24小时。",
    ),
    "LX0609-04-04-03": RuleBlueprint(
        rule_id="LX0609-04-04-03",
        template_key="surgery_anesthesia",
        expected_status="non_compliant",
        trigger_facts=["存在麻醉记录", "麻醉方式、麻醉医师代码填写不完整"],
        evidence_keywords=["麻醉记录", "麻醉方式", "填写不完整"],
        human_reason="麻醉记录关键字段不完整。",
    ),
}


def load_rules() -> Dict[str, Dict[str, Any]]:
    rows = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return {str(item.get("rule_id")).upper(): item for item in rows if item.get("rule_id")}


def normalize_rule_ids(rule_ids: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in rule_ids:
        rule_id = str(raw or "").strip().upper()
        if not rule_id or rule_id in seen:
            continue
        seen.add(rule_id)
        normalized.append(rule_id)
    return normalized


def validate_supported(rule_ids: List[str], rules_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    missing_catalog = [rule_id for rule_id in rule_ids if rule_id not in rules_map]
    unsupported = [rule_id for rule_id in rule_ids if rule_id not in RULE_BLUEPRINTS]
    template_keys = {RULE_BLUEPRINTS[rule_id].template_key for rule_id in rule_ids if rule_id in RULE_BLUEPRINTS}
    return {
        "missing_catalog": missing_catalog,
        "unsupported": unsupported,
        "template_keys": sorted(template_keys),
        "single_template": len(template_keys) == 1,
    }


def build_payload(rule_ids: List[str], rules_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    normalized = normalize_rule_ids(rule_ids)
    validation = validate_supported(normalized, rules_map)
    if validation["missing_catalog"]:
        raise ValueError(f"规则库中不存在: {', '.join(validation['missing_catalog'])}")
    if validation["unsupported"]:
        raise ValueError(f"当前脚本尚未支持这些规则的反推模板: {', '.join(validation['unsupported'])}")
    if not validation["single_template"]:
        raise ValueError(
            "当前 POC 只支持同一规则族/同一模板内的多选规则，不能跨模板混选。"
        )
    template_key = validation["template_keys"][0]
    payload = deepcopy(TEMPLATE_BUILDERS[template_key]())
    payload["selected_rule_ids"] = normalized
    payload["golden_answers"] = [
        {
            "qc_point_id": blueprint.rule_id,
            "expected_status": blueprint.expected_status,
            "trigger_facts": blueprint.trigger_facts,
            "evidence_keywords": blueprint.evidence_keywords,
            "human_reason": blueprint.human_reason,
        }
        for blueprint in (RULE_BLUEPRINTS[rule_id] for rule_id in normalized)
    ]
    payload["manual_issue_text"] = (
        f"按质控点反推测试病历：{', '.join(normalized)}。"
        f" 目标文书：{', '.join(sorted({rules_map[rule_id].get('required_documents_label') or '未标注' for rule_id in normalized}))}。"
    )
    return payload


def validate_with_backend_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from backend.app.routers.qc_sample_pools import TestRecordCreateRequest  # type: ignore

    model = TestRecordCreateRequest.model_validate(payload)
    return model.model_dump(mode="json")


def find_forbidden_self_hints(payload: Dict[str, Any]) -> List[str]:
    forbidden_patterns = ["备注：未分析", "备注:未分析", "这里缺失", "本条为反例", "故意缺失"]
    hits: List[str] = []
    for document in payload.get("documents") or []:
        content = str(document.get("content") or "")
        if any(pattern in content for pattern in forbidden_patterns):
            hits.append(str(document.get("title") or document.get("document_type") or "未命名文书"))
    return hits


def build_markdown_report(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# 泸县0609 质控点 -> 测试病历 POC 报告",
        "",
        "本报告用于验证“用户先选择一个或多个质控点，再自动生成一份可保存测试病历”的方式是否可行。",
        "",
        "## 结论",
        "",
    ]
    passed = [row for row in results if row["ok"]]
    lines.append(f"- 测试组合数：{len(results)}")
    lines.append(f"- 通过数：{len(passed)}")
    lines.append(f"- 失败数：{len(results) - len(passed)}")
    lines.append("")
    lines.append("## 明细")
    lines.append("")
    for row in results:
        lines.append(f"### {', '.join(row['rule_ids'])}")
        lines.append(f"- 结果：{'通过' if row['ok'] else '失败'}")
        lines.append(f"- 模板：{row.get('template_key') or '-'}")
        lines.append(f"- 文书数：{row.get('document_count') or 0}")
        lines.append(f"- golden 数：{row.get('golden_count') or 0}")
        if row.get("required_documents"):
            lines.append(f"- 目标文书：{', '.join(row['required_documents'])}")
        if row.get("error"):
            lines.append(f"- 错误：`{row['error']}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="泸县0609 质控点 -> 测试病历 payload 干跑 POC")
    parser.add_argument(
        "--rules",
        nargs="*",
        default=[],
        help="指定一个规则组合，例如 --rules LX0609-03-01-01 LX0609-03-01-02 LX0609-03-01-03",
    )
    args = parser.parse_args()

    rules_map = load_rules()
    scenarios = (
        [normalize_rule_ids(args.rules)]
        if args.rules
        else [
            ["LX0609-01-01-01", "LX0609-01-02-01", "LX0609-02-01-01"],
            ["LX0609-06-01-05", "LX0609-06-03-03"],
            ["LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"],
            ["LX0609-04-02-01", "LX0609-04-04-03"],
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results: List[Dict[str, Any]] = []

    for scenario_rule_ids in scenarios:
        row: Dict[str, Any] = {"rule_ids": scenario_rule_ids, "ok": False}
        try:
            payload = build_payload(scenario_rule_ids, rules_map)
            validated = validate_with_backend_schema(payload)
            forbidden_hits = find_forbidden_self_hints(validated)
            template_key = RULE_BLUEPRINTS[scenario_rule_ids[0]].template_key
            row.update(
                {
                    "ok": not forbidden_hits,
                    "template_key": template_key,
                    "document_count": len(validated.get("documents") or []),
                    "golden_count": len(validated.get("golden_answers") or []),
                    "required_documents": [
                        str(rules_map[rule_id].get("required_documents_label") or "未标注")
                        for rule_id in scenario_rule_ids
                    ],
                    "forbidden_hits": forbidden_hits,
                }
            )
            preview_name = f"rule_to_case_{'_'.join(scenario_rule_ids)}_{timestamp}.json"
            (OUTPUT_DIR / preview_name).write_text(
                json.dumps(validated, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if forbidden_hits:
                row["error"] = f"命中文书自我提示禁词: {', '.join(forbidden_hits)}"
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)

    report = build_markdown_report(results)
    report_path = OUTPUT_DIR / f"luxian_rule_to_case_poc_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")

    print(report_path)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
