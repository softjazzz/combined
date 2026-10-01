"""显式源标志字典→抽样冻结→类型分配；仅合成SQLite/内存来源。"""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord, SysUser
from app.schemas.tasks import TaskCreateRequest, TaskTemplateConfig
from app.routers.tasks import _validate_creation_assign_method
from app.services import task_sampling_service as sampling, task_sampling_persistence as persistence, task_assignment_service as assignment


def config(policy="separate"):
    return {"institutes": [{"institute_id": "SYN-H", "critical": {"positive_codes": ["C+"], "negative_codes": ["C-"]},
            "difficult": {"positive_codes": ["D+"], "negative_codes": ["D-"]}}], "overlap_policy": policy,
            **({"priority": ["difficult", "critical"]} if policy == "priority" else {})}


@pytest.mark.parametrize("flags,bucket", [(('C+', 'D-'), 'critical'), (('C-', 'D+'), 'difficult'),
    (('C+', 'D+'), 'critical_and_difficult'), (('C-', 'D-'), 'ordinary'), ((None, 'D-'), 'unknown'), (('other', 'D-'), 'unknown')])
def test_explicit_codes_classify_without_guessing(flags, bucket):
    value = config()
    sampling.validate_task_record_type_config("running", value)
    assert sampling.classify_task_record_type(('SYN-H', 'P', 'V'), flags, value)['bucket'] == bucket
    assert sampling.classify_task_record_type(('other-H', 'P', 'V'), flags, value)['bucket'] == 'unknown'
    assert sampling.classify_task_record_type(('SYN-H', 'P', 'V'), ('C+', 'D+'), config('priority'))['bucket'] == 'difficult'


@pytest.mark.parametrize("change", [lambda c: c.pop('overlap_policy'), lambda c: c['institutes'][0]['critical'].update(negative_codes=['C+']),
    lambda c: c.update(overlap_policy='priority'), lambda c: c['institutes'][0]['difficult'].update(positive_codes=[])])
def test_invalid_config_not_accepted_by_template_or_sampling(change):
    value = config()
    change(value)
    with pytest.raises(ValueError):
        sampling.validate_scoped_sampling_config('running', 'record_type_count', {'total': 1, 'record_type_config': value})
    with pytest.raises(ValueError):
        TaskTemplateConfig(scene='running', rule_set_key='SYN-RS', sampling_method='record_type_count', sampling_config={'case_scope':'active','total':1,'record_type_config':value})


@pytest.mark.asyncio
@pytest.mark.parametrize("method,parameters", [('record_type_count', {'total':1}), ('record_type_ratio', {'percentage':50,'max_per_group':1})])
async def test_create_sample_freeze_assign_and_replay_ignores_live_source(monkeypatch, method, parameters):
    payload = TaskCreateRequest(task_name='合成类型任务', scene='running', rule_set_key='SYN-RS', assign_method='by_record_type',
        sampling_method=method, sampling_config={'case_scope':'active','record_type_config':config(), **parameters})
    _validate_creation_assign_method(payload)
    reusable = TaskTemplateConfig(scene=payload.scene, rule_set_key=payload.rule_set_key, assign_method=payload.assign_method,
        sampling_method=payload.sampling_method, sampling_config=payload.sampling_config)
    task = reusable.model_dump(mode='json')
    candidates = [{'institute_id':'SYN-H','patient_id':f'SYN-P-{i}','visit_id':f'SYN-V-{i}','department':'合成科室'} for i in range(8)]
    pairs = [('C+','D-'),('C-','D+'),('C+','D+'),('C-','D-')] * 2
    async def source(*_args):
        return candidates
    monkeypatch.setattr(sampling.TaskSamplingService, '_get_active_running_candidates', source)
    monkeypatch.setattr(sampling, '_load_task_record_type_flags', lambda _: {sampling.TaskSamplingService._identity(row): flags for row, flags in zip(candidates,pairs)})
    sampled = await sampling.TaskSamplingService().sample(task)
    assert len(sampled) == 4 and len({row['visit_id'] for row in sampled}) == 4
    assert {row['record_type_snapshot']['bucket'] for row in sampled} == sampling.RECORD_TYPE_BUCKETS
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    for model in (QCTask,QCTaskRecord,SysUser):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(persistence,'SessionLocal',factory)
    monkeypatch.setattr(assignment,'SessionLocal',factory)
    snapshot = {**task, 'id':'SYN-T','creator_id':'SYN-owner','status':'draft','record_refs':None,'record_ids':None}
    with factory.begin() as session:
        session.add(QCTask(id='SYN-T',task_number='SYN-QC',task_name=payload.task_name,task_type='one_time',creator_id='SYN-owner',scene='running',status='draft',
            sampling_method=method,sampling_config=json.dumps(task['sampling_config']),record_refs=None,date_range=None,department_filter=json.dumps([]),assign_method='by_record_type'))
        session.add(SysUser(id='SYN-qc',username='SYN-qc',display_name='合成质控员',role='qc_staff',is_active=True))
    saved = persistence.save_task_sample(snapshot,sampled,actor_id='SYN-owner')
    assert saved['sampled_count'] == 4
    def unavailable(_):
        raise AssertionError('分配不得重读当前源事实')
    monkeypatch.setattr(sampling,'_load_task_record_type_flags',unavailable)
    people = [{'user_id':'SYN-qc','user_name':'请求名不可信','record_types':sorted(sampling.RECORD_TYPE_BUCKETS)}]
    with pytest.raises(assignment.AssignmentConflict) as unmatched:
        assignment.assign_task_records(task_id='SYN-T',actor_id='SYN-owner',assignees=[{**people[0], 'record_types':['critical']}],method='by_record_type')
    assert unmatched.value.code == 'record_type_unassigned'
    with factory() as session:
        assert all(row.assignee_id is None for row in session.execute(select(QCTaskRecord)).scalars())
    with factory.begin() as session:
        first = session.execute(select(QCTaskRecord)).scalars().first()
        saved_snapshot = first.record_type_snapshot
        first.record_type_snapshot = None
        first_id = first.id
    with pytest.raises(assignment.AssignmentConflict) as unknown:
        assignment.assign_task_records(task_id='SYN-T',actor_id='SYN-owner',assignees=people,method='by_record_type')
    assert unknown.value.code == 'record_type_unknown'
    with factory.begin() as session:
        assert all(row.assignee_id is None for row in session.execute(select(QCTaskRecord)).scalars())
        session.get(QCTaskRecord, first_id).record_type_snapshot = saved_snapshot
    result = assignment.assign_task_records(task_id='SYN-T',actor_id='SYN-owner',assignees=people,method='by_record_type')
    assert result['total_assigned'] == 4 and result['assignment_details'][0]['user_name'] == '合成质控员'
    assert assignment.assign_task_records(task_id='SYN-T',actor_id='SYN-owner',assignees=people,method='by_record_type')['idempotent']
    with factory() as session:
        rows = session.execute(select(QCTaskRecord)).scalars().all()
        assert all(row.record_type_snapshot['bucket'] in sampling.RECORD_TYPE_BUCKETS for row in rows)
    engine.dispose()


@pytest.mark.asyncio
async def test_null_or_source_failure_does_not_become_empty_success(monkeypatch):
    async def source(*_):
        return [{'institute_id':'SYN-H','patient_id':'SYN-P','visit_id':'SYN-V'}]
    monkeypatch.setattr(sampling.TaskSamplingService,'_get_active_running_candidates',source)
    task = {'scene':'running','sampling_method':'record_type_count','sampling_config':{'case_scope':'active','total':1,'record_type_config':config()}}
    monkeypatch.setattr(sampling,'_load_task_record_type_flags',lambda _: {})
    with pytest.raises(ValueError,match='NULL'):
        await sampling.TaskSamplingService().sample(task)
    def fail(_):
        raise RuntimeError('SYN source unavailable')
    monkeypatch.setattr(sampling,'_load_task_record_type_flags',fail)
    with pytest.raises(RuntimeError,match='来源不可用'):
        await sampling.TaskSamplingService().sample(task)
