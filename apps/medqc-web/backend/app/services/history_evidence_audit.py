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


def read_projection(item):
    result = retained_fields(item)
    result["material_evidence_status"] = "retained" if result.get("case_material_fingerprint") else "not_retained"
    if item.get("status") == "not_applicable":
        retained = bool(result.get("applicability_receipt"))
        result["audit_evidence_status"] = "retained" if retained else "not_retained"
        if not retained:
            result["audit_evidence_message"] = "本次不适用判定的历史审计依据未保留，原结论未改写。"
    return result
