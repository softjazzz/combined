"""三项手术规则的合成验收；不依赖首页、模型或真实数据库。"""
import pytest
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.native_surgery_gate_execution import _typed_003_decision
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.phase_scope import partition_luxian_0609_rule_scope, frozen_luxian_0609_delivery_scope

RULES=('LX0609-04-02-01','LX0609-04-05-03','LX0609-04-01-01')

async def evaluate(rule,case):
    surgery={'document_id':'S1','surgery_id':'S1','surgery_name':'腹腔镜胆囊切除术','surgery_code':'51.2300',
             'surgery_begin_time':'2026-01-01 08:00:00+08:00','surgery_end_time':'2026-01-01 10:00:00+08:00',
             'record_time':'2026-01-01 11:00:00','record_content':'合成正式手术记录：已实施手术。'}
    rows={'surgery_record':(surgery,),
          'presurg_summary':({'document_id':'P1','record_time':'2026-01-01 07:00:00','record_content':'合成术前小结。'},),
          'postsurg_firstcourse_record':({'document_id':'C1','surgery_id':'S1','record_time':'2026-01-01 12:00:00','record_content':'合成术后首次病程。'},),
          'evaluation_context.horizon':({'horizon_date':'2026-01-03','horizon_datetime':'2026-01-03 12:00:00','basis':'evaluation_as_of'},)}
    target={RULES[0]:'surgery_record',RULES[1]:'postsurg_firstcourse_record',RULES[2]:'presurg_summary'}[rule]
    if case=='missing':
        rows[target]=()
        if rule==RULES[0]:
            rows['anesthesia_record']=({'document_id':'A1','record_content':'本次手术已完成。\n手术开始时间：2026-01-01 08:00:00+08:00\n手术结束时间：2026-01-01 10:00:00+08:00'},)
    if case=='cancelled':
        rows['surgery_record']=()
        rows['presurg_summary']=();rows['postsurg_firstcourse_record']=()
        rows['inpat_nondrug_order']=({'document_id':'O1','order_type':'手术','order_name':'腹腔镜胆囊切除术','order_status':'取消','canceled_datetime':'2026-01-01 07:30:00'},)
    def reader(**kw):
        key=kw['source_key']
        assert not key.startswith('mr_'), '不能依赖首页'
        if case=='unavailable' and key==target:raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=key,rows=rows.get(key,()),truncated=False,limit_rows=50)
    session=build_luxian_0609_evidence_read_session(selected_rule_ids=(rule,),additional_source_keys=tuple(k for k in rows if k!='evaluation_context.horizon'),
        institute_id='SYN-I',patient_id='SYN-P',visit_id='SYN-V',source_schema=None,
        created_at='2026-01-03T12:00:00+08:00',evaluation_as_of_date='2026-01-03',row_reader=reader)
    facts=[]
    if rule==RULES[0]:
        decisions=(_typed_003_decision(snapshot=session.snapshot,materials=session.materials,customer_display_facts=facts),)
    else:
        kwargs=dict(rule_ids=(rule,),decision_rule_ids=(rule,),evidence_snapshot=session.snapshot,evidence_materials=session.materials,llm_client=None)
        if rule==RULES[2]:
            result=await execute_luxian_0609_native_surgery_document_rules(wrapper_rules=[],evidence_payload=None,**kwargs)
        else:result=await execute_luxian_0609_native_extended_document_rules(**kwargs)
        assert result.llm_call_count==0
        decisions=result.decisions;facts=list(result.customer_display_facts)
    reduced=bind_and_reduce_luxian_0609_rule_decisions(decisions=decisions,expected_rule_ids=(rule,),snapshot=session.snapshot,evidence_materials=session.materials)[0]
    published=finalize_luxian_0609_reduced_customer_result(decision=reduced,raw_customer_display_facts=dict(facts).get(rule),evidence_snapshot=session.snapshot,evidence_materials=session.materials)
    return published

@pytest.mark.asyncio
@pytest.mark.parametrize('rule',RULES)
@pytest.mark.parametrize('case,expected',[('normal','compliant'),('missing','non_compliant'),('unavailable','data_gap'),('cancelled','not_applicable')])
async def test_three_surgery_matrix(rule,case,expected):
    result=await evaluate(rule,case)
    assert result['status']==expected, (rule,case,result['status'],result.get('reason_code'))

def test_only_three_restored_and_consultation_paused():
    active,paused=partition_luxian_0609_rule_scope((*RULES,'LX0609-04-02-07','LX0609-04-02-02','LX0609-07-01-01','LX0609-12-02-01'))
    assert set(active)==set(RULES)
    assert set(paused)=={'LX0609-04-02-07','LX0609-04-02-02','LX0609-07-01-01','LX0609-12-02-01'}
    # 读取历史任务仍尊重当时冻结范围，不能因当前暂停抹去旧会诊结果。
    assert 'LX0609-04-02-07' in frozen_luxian_0609_delivery_scope({'scoped_customer_rule_ids':['LX0609-04-02-07']})
