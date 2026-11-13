import pytest
from app.services import case_material_snapshot as material
from app.services.bundles import assembly


@pytest.mark.parametrize('kind', ['exam_attention_report', 'lab_attention_report'])
def test_derived_document_keeps_content_without_physical_columns(kind):
    with material.activate({'schema': 'cdm', 'columns': {}, 'tables': {}}):
        items = assembly._build_document_inventory({kind: [{'record_content': 'synthetic content'}]}, 'cdm')
    assert len(items) == 1
    assert items[0]['document_type'] == kind
    assert 'synthetic content' in str(items[0])


def test_uncaptured_physical_table_still_rejected():
    with material.activate({'schema': 'cdm', 'columns': {}, 'tables': {}}):
        with pytest.raises(material.MaterialSnapshotError, match='uncaptured_material_columns'):
            assembly._build_document_inventory({'daily_course_record': [{'record_content': 'synthetic'}]}, 'cdm')


@pytest.mark.parametrize('controlled', [False, True])
def test_projection_diagnostic_preserves_code_without_secret(caplog, controlled):
    import logging
    from app.services.material_admission import report_projection_failure, safe_material_failure
    try:
        if controlled:
            raise material.MaterialSnapshotError('uncaptured_material_columns')
        raise ValueError('secret-body-and-dsn')
    except Exception as error:
        code = report_projection_failure(error, logging.getLogger('synthetic'))
    assert code == ('uncaptured_material_columns' if controlled else 'material_projection_failed')
    assert safe_material_failure(code)['code'] == code
    assert 'secret-body-and-dsn' not in caplog.text
    assert 'test_snapshot_derived_inventory.py' in caplog.text


@pytest.mark.parametrize('kind', ['exam_attention_report', 'lab_attention_report'])
def test_structured_context_keeps_derived_document(kind):
    with material.activate({'schema': 'cdm', 'columns': {}, 'tables': {}}):
        result = assembly._build_structured_context(
            scene='final', schema='cdm', docs={kind: [{'record_content': 'synthetic content'}]})
    assert 'synthetic content' in str(result)


def test_structured_context_rejects_uncaptured_physical_table():
    with material.activate({'schema': 'cdm', 'columns': {}, 'tables': {}}):
        with pytest.raises(material.MaterialSnapshotError, match='uncaptured_material_columns'):
            assembly._build_structured_context(scene='final', schema='cdm', docs={'daily_course_record': []})


@pytest.mark.parametrize('scene', ['final', 'running'])
def test_scene_assembly_keeps_both_derived_documents(monkeypatch, scene):
    from app.services import validation_material_source
    monkeypatch.setattr(validation_material_source, 'material_source_schema', lambda **kwargs: 'cdm')
    monkeypatch.setattr(assembly, '_source_engine', lambda schema: object())
    monkeypatch.setattr(assembly, '_material_rows', lambda **kwargs: [])
    monkeypatch.setattr(assembly, '_fetch_patient_profile', lambda **kwargs: {'patient_name': '', 'mobile': '', 'id_card': ''})
    monkeypatch.setattr(assembly, '_cache_binding', lambda *args: {})
    monkeypatch.setattr(assembly.clinical_connection, 'source_binding', lambda: {'source': 'synthetic'})
    docs = {kind: [{'record_content': kind + ' synthetic content'}]
            for kind in ('exam_attention_report', 'lab_attention_report')}
    monkeypatch.setattr(assembly, '_build_scene_attention_artifacts', lambda **kwargs: (docs, []))
    physical = set(assembly._SCENE_DOC_PRIORITY[scene]) | set(assembly._RUNNING_SUPPLEMENTARY_DOC_PRIORITY)
    with material.activate({'schema': 'cdm', 'columns': {name: ('id',) for name in physical},
                            'tables': {}, 'fingerprint': 'synthetic-fingerprint',
                            'identity': ['synthetic-i', 'synthetic-p', 'synthetic-v'],
                            'binding': {'source': 'synthetic'}}):
        result = assembly._assemble_scene_bundle(scene=scene, source_schema='cdm',
                    institute_id='synthetic-i', patient_id='synthetic-p', visit_id='synthetic-v')
    for kind in docs:
        assert kind + ' synthetic content' in result['medical_text']
        assert any(item['document_type'] == kind for item in result['source_documents'])
        assert kind + ' synthetic content' in str(result['structured_context'])
    assert result['structured_context']['case_material_fingerprint'] == 'synthetic-fingerprint'
