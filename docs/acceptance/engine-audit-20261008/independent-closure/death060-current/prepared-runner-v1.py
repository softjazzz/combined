from __future__ import annotations
import ast,builtins,copy,hashlib,io,json,socket,subprocess,sys,types
from pathlib import Path
from datetime import datetime
OUT=Path(__file__).resolve().parent
ROOT=Path('F:/MedQC-worktrees/qc-integration-20261008')
BACKEND=ROOT/'apps/medqc-web/backend'
RID='LX0609-04-02-06'
COMMIT='21f4a93e103a34002a1f9d36f9d895f226c0122f'
sys.dont_write_bytecode=True
attempts={'env':0,'private':0,'network':0,'database':0,'model':0,'foreign_write':0}
def forbidden(kind):
    attempts[kind]+=1
    raise RuntimeError('offline guard: '+kind)
real_open=builtins.open;real_io_open=io.open
def guard_path(file,mode='r'):
    try:p=Path(file).resolve()
    except TypeError:return
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
MANIFEST=json.loads((OUT/'manifest-v1.json').read_text(encoding='utf8'))
EXPECTED=json.loads((OUT/'inherited-inputs-expected-v1.json').read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_fixed_sources():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==COMMIT
    for item in MANIFEST['responsibility_sources']+MANIFEST['inherited_test_sources']:
        assert sha(ROOT/item['path'])==item['sha256'],item['path']
        assert (ROOT/item['path']).read_bytes()==subprocess.check_output(['git','show',COMMIT+':'+item['path']],cwd=ROOT),item['path']
    assert sha(OUT/'inherited-inputs-expected-v1.json')==MANIFEST['inherited_input_expectation_sha256']
if '--execute' not in sys.argv:
    print('PREPARED ONLY: requires root serial slot and explicit --execute')
    raise SystemExit(0)
check_fixed_sources()
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
# No database connection allowed even if an import accidentally exposes an engine.
from sqlalchemy.engine import Engine
Engine.connect=lambda *a,**kw:forbidden('database')
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules as native
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions as bind
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result as finalize,finalize_luxian_0609_executor_customer_display_facts as finalize_display
from app.services.luxian_0609.death_document_result_mapping import safe_death_document_customer_display_facts as safe,validate_published_death_document_facts as public_validate
source_test=BACKEND/'tests/unit/test_luxian_0609_native_extended_document_execution.py'
tree=ast.parse(source_test.read_text(encoding='utf8'))
allow=('__future__','datetime','app.services.luxian_0609.decision_binding','app.services.luxian_0609.decision_reducer','app.services.luxian_0609.customer_renderer','app.services.luxian_0609.evidence_material','app.services.luxian_0609.evidence_snapshot','app.services.luxian_0609.native_extended_document_execution','app.services.luxian_0609.source_evidence_reader','app.services.luxian_0609.source_manifest','app.services.luxian_0609.source_registry')
parts=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module in allow]+[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_session']
ns={};exec(compile(ast.Module(body=parts,type_ignores=[]),str(source_test),'exec'),ns)
class ForbiddenModel:
    async def generate(self,*a,**kw):forbidden('model')
def drive(coro):
    try:
        try:coro.send(None)
        except StopIteration as ended:return ended.value
        raise RuntimeError('unexpected await in no-I/O replay')
    finally:
        coro.close()
async def evaluate(rows):
    snapshot,materials=ns['_session'](rows)
    raw=await native(rule_ids=(RID,),decision_rule_ids=(RID,),evidence_snapshot=snapshot,evidence_materials=materials,llm_client=ForbiddenModel())
    decision=bind(decisions=raw.decisions,expected_rule_ids=(RID,),snapshot=snapshot,evidence_materials=materials)[0]
    result=finalize(decision=decision,raw_customer_display_facts=dict(raw.customer_display_facts).get(RID),evidence_snapshot=snapshot,evidence_materials=materials)
    return raw,decision,result
native_records=[]
for case in EXPECTED['native_cases']:
    raw,decision,result=drive(evaluate(case['rows']));errors=[]
    if result['status']!=case['expected_status']:errors.append('status')
    if result['reason_code']!=case['expected_reason']:errors.append('reason')
    if case.get('expected_finding') and result.get('findings')!=case['expected_finding']:errors.append('finding')
    if raw.llm_call_count!=case['expected_llm_calls']:errors.append('llm_calls')
    if 'expected_tokens' in case and raw.total_tokens!=case['expected_tokens']:errors.append('tokens')
    native_records.append({'case_id':case['id'],'origin_test':case['origin_test'],'expected_status':case['expected_status'],'pass':not errors,'errors':errors,'native_state':decision.final_state.value,'native_reason':decision.reason_code,'fact_refs':list(decision.fact_refs),'facts':dict(raw.customer_display_facts).get(RID),'result':result,'llm_calls':raw.llm_call_count,'tokens':raw.total_tokens})
case=EXPECTED['finalizer_case'];final,handled=finalize_display(result=case['input_result'],raw_facts=case['raw_facts'])
errors=[]
if handled!=case['expected_handled']:errors.append('handled')
if final['status']!=case['expected_status']:errors.append('status')
if final['reason_code']!=case['expected_reason']:errors.append('reason')
if case['expected_findings_absent'] and 'findings' in final:errors.append('false_finding_retained')
finalizer_records=[{'case_id':case['id'],'pass':not errors,'errors':errors,'result':final}]
published_records=[]
for case in EXPECTED['published_cases']:
    raw=copy.deepcopy(case['raw']);before=copy.deepcopy(raw)
    published=public_validate(rule_id=RID,raw=raw)
    want=safe(rule_id=RID,raw=raw) if case['expected']=='same_safe_facts' else case['expected']
    errors=[]
    if case['expected']=='same_safe_facts' and want is None:errors.append('legal_safe_facts_missing')
    if published!=want:errors.append('published_facts')
    if case.get('input_unchanged') and raw!=before:errors.append('input_mutated')
    published_records.append({'case_id':case['id'],'pass':not errors,'errors':errors,'published':published})
check_fixed_sources();assert sha(OUT/'manifest-v1.json')==manifest_hash;assert sha(Path(__file__))==runner_hash
assert not any(attempts.values()),attempts
observed={'audit_id':'060-current-targeted-evidence-replay-v1','fixed_current_commit':COMMIT,'historical_source_sha256':None,'historical_gap_retained':True,'source_manifest_sha256':manifest_hash,'runner_sha256':runner_hash,'input_expected_sha256':MANIFEST['inherited_input_expectation_sha256'],'sources_unchanged':True,'native_records':native_records,'finalizer_records':finalizer_records,'published_records':published_records,'guard_attempts':attempts,'actual_model_calls':0,'PG_calls':0,'private_material_reads':0,'historical_real_cases_replayed':0,'clinical_acceptance':False}
(OUT/'observed-v1.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
print(json.dumps({name:{'pass':sum(r['pass'] for r in rows),'total':len(rows),'fail':[r['case_id'] for r in rows if not r['pass']]} for name,rows in [('native',native_records),('finalizer',finalizer_records),('published',published_records)]}))
