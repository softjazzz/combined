from datetime import datetime
import pytest

from app.services.luxian_0609.native_surgery_document_execution import _anesthesia_consent_completeness
from app.services.luxian_0609.native_transfusion_execution import _programmatic_042_status


def anesthesia(**changes):
    return dict(patient_sign='张某', physician_sign='李某',
                patient_sign_datetime='2026-01-01 09:15',
                physician_sign_datetime='2026-01-01 09:16') | changes


def transfusion(**changes):
    row = dict(consent_type='blood_transfusion', patient_name='张某', diagnosis='贫血',
               transfusion_reason='改善贫血', blood_component='红细胞',
               risk_description='输血反应', alternative_plan='药物治疗',
               patient_sign='张某', physician_sign='李某', sign_datetime='2026-01-01 09:15')
    row.update(changes)
    return {'consent_form': [row], '__logical_source_states__': {'consent_form': 'available'}}


@pytest.mark.parametrize('value', ['', '未签名', '尚未签字', '未签名（待补）', '-', '---', '/', '未知', '[]', 'null'])
def test_unsigned_signatures_cannot_satisfy_anesthesia_consent(value):
    status, missing = _anesthesia_consent_completeness([anesthesia(patient_sign=value, physician_sign=value)])
    assert status == 'incomplete'
    assert {'patient_signature', 'physician_signature'} <= set(missing)


@pytest.mark.parametrize('value', ['', '未签名', '尚未签字', '未签名（待补）', '-', '---', '/', '未知', '[]', 'null'])
def test_unsigned_signatures_cannot_satisfy_transfusion_consent(value):
    status, _, facts = _programmatic_042_status(transfusion(patient_sign=value, physician_sign=value))
    assert status == 'non_compliant'
    assert {'patient_or_agent_signature', 'physician_signature'} <= set(facts['missing_fields'])


@pytest.mark.parametrize('value', ['2026-01-01 99:99', '2026-01-01 24:60', '2026-02-30 10:15', '2026-01-01', '', '签署于2026-01-01 10:15'])
def test_invalid_or_imprecise_anesthesia_signature_time(value):
    status, missing = _anesthesia_consent_completeness([anesthesia(patient_sign_datetime=value)])
    assert status == 'incomplete'
    assert missing == ['patient_signature_time']


@pytest.mark.parametrize('value', ['2026-01-01 09:15', '2026年1月1日 09:15', '2026-01-01 09:15:01', '2026-1-1 9:15', '2026-01-01T09:15:00+08:00', datetime(2026, 1, 1, 9, 15)])
def test_legal_anesthesia_signatures(value):
    assert _anesthesia_consent_completeness([anesthesia(patient_sign_datetime=value)]) == ('complete', [])


def test_transfusion_agent_signature_retains_existing_acceptance():
    assert _programmatic_042_status(transfusion(patient_sign='未签名', agent_sign='王某'))[0] == 'compliant'


def test_anesthesia_agent_does_not_expand_existing_contract():
    assert _anesthesia_consent_completeness([anesthesia(patient_sign='', agent_sign='王某')])[1] == ['patient_signature']


def test_negative_labeled_text_cannot_supply_signature():
    status, _, facts = _programmatic_042_status(transfusion(patient_sign='', physician_sign='', record_content='患者签名：未签名；医师签名：未签名'))
    assert status == 'non_compliant'
    assert set(facts['missing_fields']) == {'patient_or_agent_signature', 'physician_signature'}


def test_unavailable_source_remains_data_gap():
    data = transfusion()
    data['__logical_source_states__']['consent_form'] = 'unavailable'
    assert _programmatic_042_status(data)[:2] == ('data_gap', 'consent_signature_contract_unavailable')


def test_valid_transfusion_signatures():
    assert _programmatic_042_status(transfusion())[0] == 'compliant'
