"""将既有合成用例的明确引文选择表达为 v4 编号，不模拟临床判断。"""

from copy import deepcopy
import json


def selection_answer(answer, prompt):
    if not isinstance(answer, dict) or "docs" not in answer:
        return answer
    result = deepcopy(answer)
    events = json.loads(prompt.split("EVENTS_JSON=", 1)[1])
    for item in result["docs"]:
        if set(item) != {"event_position", "course_doc_ref", "quote_type", "quote", "report_span"}:
            continue
        event = next((event for event in events if event["event_position"] == item["event_position"]), None)
        doc = next((doc for doc in (event or {}).get("course_docs", [])
                    if doc["course_doc_ref"] == item["course_doc_ref"]), None)
        quote, span = item.pop("quote"), item.pop("report_span")
        fragments = (doc or {}).get("fragments", [])
        text = "".join(part["text"] for part in fragments)
        selected = []
        if quote:
            start = text.find(quote) if isinstance(quote, str) else -1
            if start < 0:
                selected = ["invalid-course-fragment"]
            else:
                offset = 0
                for part in fragments:
                    end = offset + len(part["text"])
                    if end > start and offset < start + len(quote):
                        selected.append(part["id"])
                    offset = end
        report_id = ""
        if span:
            report_id = next((part["id"] for part in (event or {}).get("report_fragments", [])
                              if isinstance(span, str) and span in part["text"]), "invalid-report-fragment")
        item.update(course_fragment_ids=selected, report_fragment_id=report_id,
                    basis_relation="same_finding" if item["quote_type"] in ("finding_linked", "management_linked", "prior_comparison", "targeted_differential") else "none",
                    basis_fragment_ids=selected if item["quote_type"] in ("finding_linked", "management_linked", "prior_comparison", "targeted_differential") else [])
    return result
