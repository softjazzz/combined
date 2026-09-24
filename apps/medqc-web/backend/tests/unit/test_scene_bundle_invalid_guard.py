import pytest

from app.services.bundles import assembly


def _bundle(*, policy_version: str, usable: bool = True) -> dict:
    return {
        "bundle_schema_version": assembly.BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": policy_version,
        "medical_text": "病历正文" if usable else "",
        "text_available": usable,
        "document_hits": {},
        "structured_context": {"documents": {}},
    }


@pytest.mark.parametrize(
    ("force_refresh", "force_refresh_if_empty", "usable"),
    [(False, False, True), (False, True, True), (False, True, False), (True, True, True)],
)
def test_invalidated_scene_bundle_fails_closed_before_assembly(
    monkeypatch, force_refresh, force_refresh_if_empty, usable,
):
    calls = []
    monkeypatch.setattr(assembly, "ensure_scene_bundle_tables", lambda schema: None)
    monkeypatch.setattr(
        assembly,
        "_load_scene_bundle",
        lambda **kwargs: calls.append(kwargs) or _bundle(
            policy_version=assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION,
            usable=usable,
        ),
    )
    monkeypatch.setattr(
        assembly,
        "_assemble_scene_bundle",
        lambda **kwargs: pytest.fail("失效 Bundle 不得重组装"),
    )
    monkeypatch.setattr(
        assembly,
        "_upsert_scene_bundle",
        lambda **kwargs: pytest.fail("失效 Bundle 不得改写"),
    )

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        assembly.load_or_assemble_scene_bundle(
            scene="running",
            institute_id="I1",
            patient_id="P1",
            visit_id="V1",
            force_refresh=force_refresh,
            force_refresh_if_empty=force_refresh_if_empty,
        )

    assert len(calls) == 1


def test_invalidated_fallback_candidate_is_not_returned(monkeypatch):
    monkeypatch.setattr(assembly, "ensure_scene_bundle_tables", lambda schema: None)

    def load(**kwargs):
        if kwargs.get("prefer_usable_content"):
            return _bundle(policy_version=assembly.TASK_SYNC_INVALIDATED_POLICY_VERSION)
        return _bundle(policy_version="ordinary-policy", usable=False)

    monkeypatch.setattr(assembly, "_load_scene_bundle", load)
    monkeypatch.setattr(
        assembly,
        "_assemble_scene_bundle",
        lambda **kwargs: pytest.fail("失效 Bundle 不得重组装"),
    )

    with pytest.raises(RuntimeError, match="同步尚未完成"):
        assembly.load_or_assemble_scene_bundle(
            scene="final", institute_id="I1", patient_id="P1", visit_id="V1",
        )


def test_unmarked_policy_keeps_existing_cache_and_force_refresh_behavior(monkeypatch):
    cached = _bundle(policy_version="ordinary-policy")
    refreshed = _bundle(policy_version="another-policy")
    assembled = []
    persisted = []
    monkeypatch.setattr(assembly, "ensure_scene_bundle_tables", lambda schema: None)
    monkeypatch.setattr(assembly, "_load_scene_bundle", lambda **kwargs: cached)
    monkeypatch.setattr(
        assembly,
        "_assemble_scene_bundle",
        lambda **kwargs: assembled.append(kwargs) or refreshed,
    )
    monkeypatch.setattr(
        assembly,
        "_upsert_scene_bundle",
        lambda **kwargs: persisted.append(kwargs),
    )

    kwargs = {"scene": "running", "institute_id": "I1", "patient_id": "P1", "visit_id": "V1"}
    assert assembly.load_or_assemble_scene_bundle(**kwargs, policy_version="requested") is cached
    assert not assembled and not persisted
    assert assembly.load_or_assemble_scene_bundle(**kwargs, force_refresh=True) is refreshed
    assert len(assembled) == len(persisted) == 1
