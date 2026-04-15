import pytest

from app.services.custom_qc_service import build_inline_rule, evaluate_inline_rule_orchestrated


class _FakeClient:
    def __init__(self) -> None:
        self.model = "fake-model"
        self.temperature = 0.1
        self.top_p = 0.8
        self.max_tokens = 1024


class _FakeRuleEngine:
    async def evaluate(self, rule, medical_record):  # pragma: no cover - 通过 orchestrator 回调触发
        return {
            "rule_id": str(rule.get("rule_id") or ""),
            "rule_name": str(rule.get("name") or ""),
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.9,
            "applicability": {"is_applicable": True, "reason": "", "method": "default"},
            "evidence_verified": True,
            "metadata": {},
        }


class _FakeOrchestrator:
    async def evaluate_rules(self, **kwargs):
        return {
            "results": [
                {
                    "rule_id": "LXE-0001",
                    "rule_name": "测试规则",
                    "status": "non_compliant",
                    "is_compliant": False,
                    "issues": [{"description": "问题"}],
                    "findings": "发现问题",
                    "evidence": "证据",
                    "suggestion": "整改建议",
                    "confidence": 0.85,
                    "llm_raw_output": "raw",
                    "applicability": {"is_applicable": True, "reason": "", "method": "default"},
                    "evidence_verified": True,
                    "evidence_span": None,
                    "metadata": {
                        "tokens_used": 123,
                        "api_time": 1.23,
                        "executor_type": "llm",
                        "rule_version": "workspace-v1",
                        "prompt_version": "workspace-prompt-v1",
                        "model_version": "fake-model",
                        "evidence_source": "custom_qc_workspace",
                        "cache_hit": False,
                        "llm_fallback": False,
                        "execution_domain": "course",
                        "doc_scope": "primary",
                        "cost_class": "medium",
                        "cache_key": "abc123",
                    },
                }
            ],
            "executor_breakdown": {"program": 0, "llm": 1, "llm_fallback": 0},
            "cache_breakdown": {"hit": 0, "miss": 1},
            "trace": [{"rule_id": "LXE-0001"}],
        }


class _FakeService:
    def __init__(self) -> None:
        self.client = _FakeClient()
        self.rule_engine = _FakeRuleEngine()
        self.rule_orchestrator = _FakeOrchestrator()
        self.execution_cache = None

    def _ensure_rule_execution_meta(self, rule):
        normalized = dict(rule)
        normalized.setdefault("executor_type", "llm")
        normalized.setdefault("execution_domain", "course")
        normalized.setdefault("doc_scope", "primary")
        return normalized


def test_build_inline_rule_should_fill_execution_meta_defaults():
    inline_rule = build_inline_rule(
        {
            "rule_code": "LXE-0001",
            "name": "规则A",
            "description": "描述A",
            "document_type": "病程记录",
            "prompt_template": "请分析：{medical_text}",
        }
    )

    assert inline_rule["executor_type"] == "llm"
    assert inline_rule["doc_scope"] == "primary"
    assert inline_rule["rule_version"] == "workspace-v1"
    assert inline_rule["prompt_version"] == "workspace-prompt-v1"


@pytest.mark.asyncio
async def test_evaluate_inline_rule_orchestrated_should_return_unified_metadata():
    service = _FakeService()
    result = await evaluate_inline_rule_orchestrated(
        qc_service=service,
        rule={
            "rule_code": "LXE-0001",
            "name": "测试规则",
            "description": "测试描述",
            "document_type": "病程记录",
            "prompt_template": "请分析：{medical_text}",
        },
        record={
            "record_id": "V001",
            "visit_id": "V001",
            "patient_name": "张三",
            "department": "骨科",
            "medical_text": "病历正文",
        },
    )

    metadata = result.get("metadata") or {}
    assert result["status"] == "non_compliant"
    assert metadata.get("executor_type") == "llm"
    assert metadata.get("rule_version") == "workspace-v1"
    assert metadata.get("prompt_version") == "workspace-prompt-v1"
    assert metadata.get("cache_key") == "abc123"
    assert result.get("executor_breakdown") == {"program": 0, "llm": 1, "llm_fallback": 0}
    assert result.get("cache_breakdown") == {"hit": 0, "miss": 1}
