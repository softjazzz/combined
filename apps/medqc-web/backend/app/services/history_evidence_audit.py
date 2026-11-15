"""结果读取的审计状态投影；不读取来源，也不改写历史结果。"""
from copy import deepcopy
import re


def retained_fields(item):
    result = {}
    material = item.get("case_material_fingerprint")
    if "case_material_fingerprint" in item:
        if not isinstance(material, str) or not re.fullmatch(r"[0-9a-f]{64}", material):
            raise ValueError("invalid_saved_material_fingerprint")
        result["case_material_fingerprint"] = material
    if "applicability_receipt" in item:
        from .luxian_0609.applicability_receipt import validate_applicability_receipt
        receipt = validate_applicability_receipt(item["applicability_receipt"])
        if receipt.get("rule_id") != item.get("rule_id", item.get("rule_code")):
            raise ValueError("applicability_receipt_rule_mismatch")
        if receipt.get("status") != item.get("status") or receipt.get("reason_code") != item.get("reason_code"):
            raise ValueError("applicability_receipt_result_mismatch")
        receipt_material = receipt.get("material_fingerprint")
        if receipt_material and receipt_material != material:
            raise ValueError("applicability_receipt_material_mismatch")
        result["applicability_receipt"] = deepcopy(receipt)
    return result


# 结果在服务投影、任务装配等边界按固定字段重建时必须随行搬运的审计字段。
# 唯一定义处；新增审计字段只改这里，避免多个白名单各自遗漏（1026 回执剥离根因）。
AUDIT_RETAINED_KEYS = ("case_material_fingerprint", "applicability_receipt")


def carry_retained_fields(source, target):
    """把 source 已有的审计字段搬到重建后的 target，并按 target 最终结论校验。

    只搬运、不生成：source 没有回执时 target 也没有，不补造。回执与 target 的
    规则、状态或原因码不一致（如生成回执后结论被改写）时拒绝，不静默丢弃。
    """
    carried = {key: deepcopy(source[key]) for key in AUDIT_RETAINED_KEYS if key in source}
    if carried:
        retained_fields({**target, **carried})
        target.update(carried)
    return target


def read_projection(item):
    result = retained_fields(item)
    result["material_evidence_status"] = "retained" if result.get("case_material_fingerprint") else "not_retained"
    if item.get("status") == "not_applicable":
        retained = bool(result.get("applicability_receipt"))
        result["audit_evidence_status"] = "retained" if retained else "not_retained"
        if not retained:
            result["audit_evidence_message"] = "本次不适用判定的审计依据当时未保留，原结论未改写。"
    return result
