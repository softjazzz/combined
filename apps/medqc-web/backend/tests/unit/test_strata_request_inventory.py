"""盘点真实生产者在合成材料上的精确输入，不伪称 Token 缓存命中。"""

import hashlib

import pytest

from app.services.strata_observation import describe_strata_request
from tests.scheduler_support.strata_synthetic import build_requests


def key(prompt, *, case="case-a", executor="exam_lab"):
    return describe_strata_request(
        {"model": "synthetic", "messages": [{"role": "user", "content": prompt}],
         "chat_template_kwargs": {"enable_thinking": False}},
        scope_key=case, route_key=executor,
        digest=lambda text: hashlib.sha256(text.encode()).hexdigest(),
    )


def test_real_retry_preserves_projection_but_not_current_token_prefix():
    examples = build_requests()
    a, duplicate, retry, finding, subset, primary, other_case = examples
    original = key(a[2])
    assert key(duplicate[2]) == original
    assert key(retry[2])["input_group_key"] != original["input_group_key"]
    assert key(retry[2])["evidence_projection_key"] == original["evidence_projection_key"]
    for item in (finding, subset):
        assert key(item[2])["evidence_projection_key"] != original["evidence_projection_key"]
    assert key(primary[2])["producer_kind"] == "unclassified"
    assert key(other_case[2], case=other_case[1])["input_group_key"] != original["input_group_key"]
    assert all(key(item[2])["leading_messages_key"] is None for item in examples)


def test_projection_is_byte_exact_and_does_not_sort_or_repair_original_json():
    prompt = build_requests()[0][2]
    reordered = prompt.replace('"events":', '"events" :', 1)
    assert key(prompt)["evidence_projection_key"] != key(reordered)["evidence_projection_key"]
    assert key(prompt + "\nsynthetic-trailing-content")["evidence_projection_key"] is None


@pytest.mark.asyncio
async def test_offline_probe_actual_gateway_fixed_transport_and_safe_report():
    from scripts.audit_strata_p0 import run_probe

    report = await run_probe()
    assert report["synthetic_transport_requests"] == 7
    assert report["attempt_count"] == 7
    assert report["business_database_writes"] == 0
    assert report["real_model_calls"] == 0
    assert report["strata_connections"] == 0
    assert report["token_reuse_verified"] is False
    assert len(report["groups"]["identical_input"]) == 1
    assert report["groups"]["identical_input"][0]["attempt_count"] == 2
    assert report["groups"]["leading_messages_candidates"] == []
    assert report["groups"]["evidence_projection_candidates"][0]["attempt_count"] == 3
