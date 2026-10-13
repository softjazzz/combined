from __future__ import annotations
import ast,builtins,copy,hashlib,io,json,os,socket,subprocess,sys,types
from pathlib import Path
from datetime import datetime
OUT=Path(__file__).resolve().parent
ROOT=Path('F:/MedQC-worktrees/qc-integration-20261008')
BACKEND=ROOT/'apps/medqc-web/backend'
COMMIT='e5f5696f559b4571b0d2a7d339d0d65485f8344b'
sys.dont_write_bytecode=True
attempts={'env':0,'private':0,'network':0,'database':0,'model':0,'foreign_write':0}
def forbidden(kind):
    attempts[kind]+=1
    raise RuntimeError('offline guard: '+kind)
real_open=builtins.open;real_io_open=io.open
def guard_path(file,mode='r'):
    if isinstance(file,int):return  # Existing file descriptor, no new path access.
    p=Path(os.fsdecode(file)).resolve()
    parts=[v.lower() for v in p.parts]
    if any(v.startswith('.env') for v in parts):forbidden('env')
    if any('private' in v or v=='0910-full-audit' for v in parts):forbidden('private')
    if any(v in str(mode) for v in ('w','a','x','+')) and p!=OUT and OUT not in p.parents:forbidden('foreign_write')
def guarded_open(file,*a,**kw):
    guard_path(file,a[0] if a else kw.get('mode','r'));return real_open(file,*a,**kw)
def guarded_io_open(file,*a,**kw):
    guard_path(file,a[0] if a else kw.get('mode','r'));return real_io_open(file,*a,**kw)
builtins.open=guarded_open;io.open=guarded_io_open
socket.create_connection=lambda *a,**kw:forbidden('network')
socket.socket.connect=lambda *a,**kw:forbidden('network')
config=types.ModuleType('dotenv');config.load_dotenv=lambda *a,**kw:forbidden('env');config.dotenv_values=config.load_dotenv;sys.modules['dotenv']=config
settings=types.ModuleType('app.core.settings');settings.get_settings=lambda *a,**kw:forbidden('env');sys.modules[settings.__name__]=settings
# Audit hook covers low-level file opens and any network/subprocess bypass of wrappers.
def audit_guard(event,args):
    if event=='open':
        file,mode,flags=args
        guard_path(file,mode or ('w' if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) else 'r'))
    elif event in ('sqlite3.connect','sqlite3.connect/handle'):
        forbidden('database')
    elif event in ('socket.__new__','socket.connect','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'):
        forbidden('network')
    elif event=='subprocess.Popen':
        raise RuntimeError('offline guard: all subprocess forbidden after source freeze')
MANIFEST=json.loads((OUT/'manifest-v1.json').read_text(encoding='utf8'))
EXPECTED=json.loads((OUT/'original-rows-expected-v1.json').read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_sources():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert MANIFEST['approved_execution_head'] is not None, 'root must grant serial slot and fix approved execution HEAD'
    assert head==MANIFEST['approved_execution_head'], 'execution HEAD changed'
    for item in MANIFEST['sources']:
        assert sha(ROOT/item['path'])==item['sha256'],item['path']
        assert (ROOT/item['path']).read_bytes()==subprocess.check_output(['git','show',item.get('blob_commit',COMMIT)+':'+item['path']],cwd=ROOT),item['path']
    assert sha(OUT/'original-rows-expected-v1.json')==MANIFEST['original_expectation_sha256']
    for item in MANIFEST['provenance']:assert sha(Path(item['path']))==item['sha256'],item['path']
def check_source_hashes_only():
    for item in MANIFEST['sources']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    assert sha(OUT/'original-rows-expected-v1.json')==MANIFEST['original_expectation_sha256']
    for item in MANIFEST['provenance']:assert sha(Path(item['path']))==item['sha256'],item['path']
if '--execute' not in sys.argv:
    print('PREPARED ONLY: no production imports or probe execution; root serial slot required')
    raise SystemExit(0)
log=OUT/'run-04.log'
# Refuse overwriting even a failed first run. Root must approve a separately named follow-up.
with log.open('x',encoding='utf8') as fh:fh.write('START fourth attempt; all three earlier support errors retained\n')
def note(value):
    with log.open('a',encoding='utf8') as fh:fh.write(value+'\n')
try:
    # Only pre-import readonly git HEAD/blob checks precede audit installation.
    check_sources()
    # Standard-library Windows metadata cache only; avoids platform.machine shell fallback during SQLAlchemy import.
    import platform
    platform.uname();platform.machine()
    sys.addaudithook(audit_guard)
    manifest_hash=sha(OUT/'manifest-v1.json');runner_hash=sha(Path(__file__))
    sys.path.insert(0,str(BACKEND))
    for name,path in [('app.database',BACKEND/'app/database'),('app.services.bundles',BACKEND/'app/services/bundles')]:
        module=types.ModuleType(name);module.__path__=[str(path)];sys.modules[name]=module
    connection=types.ModuleType('app.database.connection');connection.engine=None;connection.DB_SCHEMA_MODE='legacy';sys.modules[connection.__name__]=connection;sys.modules['app.database'].connection=connection
    assembly=types.ModuleType('app.services.bundles.assembly');assembly.engine=None;sys.modules[assembly.__name__]=assembly;sys.modules['app.services.bundles'].assembly=assembly
    family_tree=ast.parse((BACKEND/'app/services/luxian_0609/customer_rule_package.py').read_text(encoding='utf8'))
    static=types.ModuleType('app.services.luxian_0609.customer_rule_package')
    static.RULE_FAMILY_DEFINITIONS=ast.literal_eval(next(n.value for n in family_tree.body if isinstance(n,ast.AnnAssign) and n.target.id=='RULE_FAMILY_DEFINITIONS'))
    sys.modules[static.__name__]=static
    class NoDatabaseDrivers:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in {'psycopg','psycopg2','asyncpg','pg8000','pymysql','MySQLdb'}:forbidden('database')
            return None
    sys.meta_path.insert(0,NoDatabaseDrivers())
    from sqlalchemy.engine import Engine
    from sqlalchemy import event
    from sqlalchemy.pool import Pool
    Engine.connect=lambda *a,**kw:forbidden('database')
    @event.listens_for(Pool,'connect')
    def block_db(*a,**kw):forbidden('database')
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows,build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
    from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
    from app.services.luxian_0609.native_execution import execute_luxian_0609_native_rules
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from dataclasses import asdict
    class ForbiddenModel:
        async def generate(self,*a,**kw):forbidden('model')
    def drive(coro):
        try:
            try:coro.send(None)
            except StopIteration as ended:return ended.value
            raise RuntimeError('unexpected await in no-I/O replay')
        finally:coro.close()
    async def evaluate(case):
        rows=copy.deepcopy(case['rows']);rule=case['rule_id']
        for row in rows.get('mr_surgery',[]):
            for key in ('surgery_begin_datetime','surgery_end_datetime'):
                if row.get(key):row[key]=datetime.fromisoformat(row[key])
        def reader(**kwargs):
            return SnapshotSourceRows.create(source_key=kwargs['source_key'],rows=rows.get(kwargs['source_key'],()),truncated=False,limit_rows=50)
        family='surgery_document' if rule=='LX0609-04-01-01' else ''
        extra=resolve_legacy_executor_material_source_keys((family,),selected_rule_ids=(rule,)) if family else ('inpat_nondrug_order','surgery_application')
        coords=dict(institute_id='safe-institute',patient_id='safe-patient',visit_id='safe-visit',source_schema=None)
        session=build_luxian_0609_evidence_read_session(selected_rule_ids=(rule,),**coords,created_at='2026-10-07T12:00:00+08:00',row_reader=reader,additional_source_keys=extra)
        kwargs=dict(rule_ids=(rule,),decision_rule_ids=(rule,),evidence_snapshot=session.snapshot,evidence_materials=session.materials)
        if family:
            raw=await execute_luxian_0609_native_surgery_document_rules(**kwargs,wrapper_rules=[{'rule_id':rule,'custom_prompt':'{medical_text}'}],evidence_payload=None,llm_client=ForbiddenModel())
        else:raw=execute_luxian_0609_native_rules(**kwargs,**coords)
        reduced=bind_and_reduce_luxian_0609_rule_decisions(decisions=raw.decisions,expected_rule_ids=(rule,),snapshot=session.snapshot,evidence_materials=session.materials)[0]
        final=finalize_luxian_0609_reduced_customer_result(decision=reduced,raw_customer_display_facts=dict(raw.customer_display_facts).get(rule),evidence_snapshot=session.snapshot,evidence_materials=session.materials)
        errors=[]
        if reduced.final_state.value not in case['expected_statuses']:errors.append('reduced_status')
        if final['status'] not in case['expected_statuses']:errors.append('public_status')
        if getattr(raw,'llm_call_count',0)!=0:errors.append('llm_call_count')
        return {'case_id':case['case_id'],'rule_id':rule,'expected_statuses':case['expected_statuses'],'pass':not errors,'errors':errors,'native_decisions':[asdict(x) for x in raw.decisions],'reduced':reduced.to_safe_dict(),'raw_facts':dict(raw.customer_display_facts).get(rule),'public_result':final,'reported_model_calls':getattr(raw,'llm_call_count',0),'reported_tokens':getattr(raw,'total_tokens',0),'synthetic_snapshot_hash':session.snapshot.snapshot_hash}
    records=[]
    for case in EXPECTED['cases']:
        record=drive(evaluate(case));records.append(record)
        note(json.dumps({'case_id':record['case_id'],'pass':record['pass'],'public_status':record['public_result']['status'],'public_reason':record['public_result']['reason_code']},ensure_ascii=False))
    check_source_hashes_only();assert sha(OUT/'manifest-v1.json')==manifest_hash;assert sha(Path(__file__))==runner_hash
    assert not any(attempts.values()),attempts
    loaded_app_paths={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='app' or n.startswith('app.')) and getattr(m,'__file__',None)}
    assert loaded_app_paths and all((BACKEND/'app').resolve() in Path(p).parents for p in loaded_app_paths.values()),'production imported outside target tree'
    observed={'loaded_app_paths':loaded_app_paths,'all_loaded_app_paths_in_target':True,'audit_id':'surgery029030-original-normal-current-replay-v1','fixed_responsibility_commit':COMMIT,'actual_execution_head':MANIFEST['approved_execution_head'],'manifest_sha256':manifest_hash,'runner_sha256':runner_hash,'original_expectation_sha256':MANIFEST['original_expectation_sha256'],'records':records,'guard_attempts':attempts,'sources_unchanged':True,'layer':MANIFEST['runtime_layer'],'substitutions':MANIFEST['substitutions'],'historical_candidate_failures_retained':True,'clinical_acceptance':False,'negative_coverage_closure':False}
    with (OUT/'observed-run-04.json').open('x',encoding='utf8') as fh:fh.write(json.dumps(observed,ensure_ascii=False,indent=2,default=str)+'\n')
    note('END pass='+str(sum(x['pass'] for x in records))+'/'+str(len(records)))
    print(json.dumps({'pass':sum(x['pass'] for x in records),'total':len(records),'guard_attempts':attempts}))
except BaseException:
    import traceback
    note(traceback.format_exc());note('guard_attempts='+json.dumps(attempts))
    raise
