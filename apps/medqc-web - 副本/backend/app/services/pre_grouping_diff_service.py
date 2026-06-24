from __future__ import annotations

from typing import Any, Dict, List, Optional


TRACKED_INPUT_FIELDS = (
    "pdx_code",
    "adx_count",
    "procedure_count",
    "patient_age",
    "patient_gender",
    "los",
    "total_fee",
)


class PreGroupingDiffService:
    """比较两次事前模拟入组的关键输入变化。"""

    def build_change_tracking(
        self,
        *,
        previous_result: Optional[Dict[str, Any]],
        current_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not previous_result:
            return {
                "previous_version": None,
                "current_version": current_result.get("version"),
                "needs_regrouping": True,
                "reason": "first_simulation",
                "changed_fields": [],
            }

        previous_summary = previous_result.get("input_summary") or {}
        current_summary = current_result.get("input_summary") or {}
        changed_fields: List[Dict[str, Any]] = []
        for field in TRACKED_INPUT_FIELDS:
            before = previous_summary.get(field)
            after = current_summary.get(field)
            if before != after:
                changed_fields.append(
                    {
                        "field": field,
                        "previous": before,
                        "current": after,
                    }
                )

        input_hash_changed = previous_result.get("input_hash") != current_result.get("input_hash")
        if input_hash_changed and not changed_fields:
            changed_fields.append(
                {
                    "field": "medical_text",
                    "previous": "changed",
                    "current": "changed",
                }
            )

        return {
            "previous_version": previous_result.get("version"),
            "current_version": current_result.get("version"),
            "needs_regrouping": bool(changed_fields),
            "reason": "tracked_input_changed" if changed_fields else "no_relevant_change",
            "changed_fields": changed_fields,
        }
