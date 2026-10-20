"""身份闸门必须核验已冻结的截断前缀，不能把临床完整性当作身份可读性。"""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.case_identity import CaseRef
from app.services.luxian_0609.evidence_material import EvidenceMaterialTruncated
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.llm_prompt_privacy import PatientPrivacyViolation, PrivacyIdentityContextError, wrap_luxian_0609_llm_client
from app.services.luxian_0609.privacy_identity_context import _Luxian0609IdentityCollector, build_luxian_0609_identity_provider
from app.services.luxian_0609.privacy_request_scope import _case_scope, bind_luxian_0609_identity_provider, luxian_0609_case_identity_scope


def _session(index):
    def reader(**kw):
        source = kw['source_key']
        rows = [{'order_id': 'order-a', 'patient_name': '前缀患者', 'order_name': '普通医嘱'}] if source == 'inpat_drug_order' else []
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=bool(rows), limit_rows=1)
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=('LX0609-07-01-02',), institute_id='inst', patient_id=f'pat-{index}',
        visit_id='visit', source_schema=None, created_at='2026-10-16T00:00:00+00:00', row_reader=reader,
    )


@pytest.mark.asyncio
async def test_concurrent_collected_identity_with_truncated_material_is_checked():
    collector = _Luxian0609IdentityCollector()
    for index in range(27):
        collector.capture('mr', SimpleNamespace(institute_id='inst', patient_id=f'pat-{index}', visit_id='visit', name=f'合成患者{index}'))

    class Capture:
        calls = 0

        async def generate(self, prompt):
            self.calls += 1
            return {'content': '{}'}

    async def run(index):
        session = _session(index)
        # 临床消费者仍然不能把前缀当作完整来源。
        with pytest.raises(EvidenceMaterialTruncated):
            session.materials.document_rows('inpat_drug_order', snapshot=session.snapshot)
        with luxian_0609_case_identity_scope(case_coordinates=('inst', f'pat-{index}', 'visit'), identity_provider=collector.provider_for_case(CaseRef('inst', f'pat-{index}', 'visit'))), _case_scope(('inst', f'pat-{index}', 'visit')):
            provider = bind_luxian_0609_identity_provider(build_luxian_0609_identity_provider(
                institute_id='inst', patient_id=f'pat-{index}', visit_id='visit', snapshot=session.snapshot, materials=session.materials,
            ), case_coordinates=('inst', f'pat-{index}', 'visit'))
            delegate = Capture()
            client = wrap_luxian_0609_llm_client(delegate, identity_provider=provider)
            await asyncio.sleep(0)
            await client.generate('普通临床材料。')
            for identity in (f'合成患者{index}', '前缀患者'):
                with pytest.raises(PatientPrivacyViolation):
                    await client.generate(f'别称【{identity}】。')
            assert delegate.calls == 1
    await asyncio.gather(*(run(index) for index in range(27)))
    collector.close()


@pytest.mark.asyncio
async def test_truncated_identity_does_not_bypass_missing_collected_name():
    collector = _Luxian0609IdentityCollector()
    session = _session(0)
    with luxian_0609_case_identity_scope(case_coordinates=('inst', 'pat-0', 'visit'), identity_provider=collector.provider_for_case(CaseRef('inst', 'pat-0', 'visit'))), _case_scope(('inst', 'pat-0', 'visit')):
        provider = bind_luxian_0609_identity_provider(build_luxian_0609_identity_provider(snapshot=session.snapshot, materials=session.materials), case_coordinates=('inst', 'pat-0', 'visit'))
        with pytest.raises(PrivacyIdentityContextError):
            await wrap_luxian_0609_llm_client(object(), identity_provider=provider).generate('普通临床材料。')


def test_truncated_identity_still_rejects_material_snapshot_mismatch():
    session = _session(0)
    provider = build_luxian_0609_identity_provider(snapshot=session.snapshot, materials=replace(session.materials, snapshot_hash='bad'))
    with pytest.raises(ValueError):
        provider()


def test_truncated_identity_rejects_mutated_prefix():
    session = _session(0)
    original = session.materials._sources['inpat_drug_order']
    altered = SnapshotSourceRows.create(
        source_key='inpat_drug_order', rows=[{**original.rows[0], 'patient_name': '被改写患者'}],
        truncated=True, limit_rows=1,
    )
    materials = replace(session.materials, _sources={**session.materials._sources, 'inpat_drug_order': altered})
    with pytest.raises(ValueError):
        build_luxian_0609_identity_provider(snapshot=session.snapshot, materials=materials)()
