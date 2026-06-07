from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_DEMO_CASES_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "tender_demo_cases.json"


class TenderDemoCaseLoader:
    """加载投标演示用只读病例夹具。"""

    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_DEMO_CASES_PATH

    def list_cases(self) -> list[dict[str, Any]]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        cases = payload.get("cases", [])
        if not isinstance(cases, list):
            raise ValueError("tender_demo_cases.json 的 cases 必须是数组")
        return [case for case in cases if isinstance(case, dict)]

    def get_case(self, case_id: str) -> dict[str, Any]:
        for case in self.list_cases():
            if case.get("case_id") == case_id:
                return case
        raise KeyError(f"未找到演示病例: {case_id}")

    def case_for_clause(self, clause: str) -> dict[str, Any]:
        for case in self.list_cases():
            clauses = case.get("clauses", [])
            if isinstance(clauses, list) and clause in clauses:
                return case
        raise KeyError(f"未找到条款演示病例: {clause}")
