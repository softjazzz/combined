import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routers.qc_sichuan import get_rule_prompt


def test_get_rule_prompt_default_template_renders_valid_single_brace_json():
    qc_service = MagicMock()
    qc_service.get_rule_by_id.return_value = {
        "rule_id": "SC-010",
        "name": "主诉与现病史一致性",
        "description": "检查主诉与现病史描述一致",
        "applicable_documents": ["admission_record"],
        "defect_level": "major",
        "complexity": "high",
        "custom_prompt": None,
    }
    request = SimpleNamespace(state=SimpleNamespace(trace_id="trace-prompt-1"))
    admin_user = {"id": "super-1", "roles": ["super_admin"], "institute_id": None}

    response = asyncio.run(
        get_rule_prompt(
            request=request,
            rule_id="SC-010",
            admin_user=admin_user,
            qc_service=qc_service,
        )
    )

    assert response["success"] is True
    prompt = response["data"]["prompt"]
    assert response["data"]["is_default"] is True
    assert "{medical_text}" in prompt
    assert "{{" not in prompt
    assert "}}" not in prompt

    match = re.search(r"\*\*输出格式（JSON）：\*\*\s*(\{.*?\})\s*请直接输出 JSON", prompt, re.S)
    assert match is not None
    parsed = json.loads(match.group(1).replace("true/false", "true"))
    assert set(parsed.keys()) == {"is_compliant", "findings", "evidence", "suggestion", "confidence"}
