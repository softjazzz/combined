"""Prepared pure-stdlib fixed-blob carrier capture. Requires explicit slot token."""
import ast, asyncio, hashlib, json, re, sys, traceback, types
from collections.abc import Mapping
from pathlib import Path
from typing import Any
OUT=Path(__file__).resolve().parent
PLAN=OUT/'expectations-frozen.json'
def install_guard():
    def local_pair():
        return any(f.name=='socketpair' and f.filename.endswith('socket.py') for f in traceback.extract_stack())
    def audit(event,args):
        if event=='open':
            name=str(args[0]).replace('\\','/').lower();base=name.rsplit('/',1)[-1]
            if base.startswith('.env') or base in {'.pgpass','.pg_service.conf'} or '/.tmp/0910-full-audit/' in name or name.endswith(('.db','.sqlite','.sqlite3')):
                raise RuntimeError('offline credential/private/db read forbidden')
        if event=='subprocess.Popen' or event.startswith('sqlite3.') or event in {'socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'}:
            raise RuntimeError('offline subprocess/db/network forbidden')
        if event in {'socket.connect','socket.bind'}:
            address=args[1] if len(args)>1 else None
            if not (local_pair() and (not isinstance(address,tuple) or address[0] in {'127.0.0.1','::1','localhost'})):
                raise RuntimeError('offline external socket forbidden')
    sys.addaudithook(audit)
    class NoAppDriver:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in {'app','dotenv','psycopg','psycopg2','asyncpg','pg8000','sqlalchemy','httpx','requests'}:
                raise RuntimeError('non-stdlib project/transport/db import forbidden')
            return None
    sys.meta_path.insert(0,NoAppDriver())
def source(name):return (OUT/name).read_text(encoding='utf-8')
def module(name):
    m=types.ModuleType(name);sys.modules[name]=m;return m

def load_actual():
    privacy=module('n12_fixed_privacy')
    exec(compile(source('llm_prompt_privacy.py'),'fixed:llm_prompt_privacy.py','exec'),privacy.__dict__)
    helper=module('n12_fixed_helper')
    helper.__dict__.update({'re':re,'Mapping':Mapping,'Any':Any,'redact_luxian_0609_patient_privacy':privacy.redact_luxian_0609_patient_privacy})
    for file,names in [('native_preop_content_execution.py',{'_document_spans','_usage'}),('rescue_record_completeness.py',{'_located_present'})]:
        tree=ast.parse(source(file))
        nodes=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        assert len(nodes)==1+len(names)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'fixed:'+file,'exec'),helper.__dict__)
    tree=ast.parse(source('anesthesia_visit_fact_extraction.py'))
    tree.body=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.level)]
    exec(compile(tree,'fixed:anesthesia_visit_fact_extraction.py','exec'),helper.__dict__)
    return privacy,helper

class Capture:
    def __init__(self):self.calls=[];self.parse_error=None;self.documents=None
    async def generate(self,prompt,**kwargs):
        self.calls.append({'prompt':prompt,'kwargs':kwargs})
        try:self.documents=json.loads(prompt.split('\nINPUT_JSON=',1)[1])['documents']
        except (ValueError,IndexError,KeyError,TypeError) as e:
            self.parse_error=type(e).__name__;raise ValueError('synthetic capture JSON malformed') from None
        items=[{'document_ref':d['document_ref'],'fields':{field:{'state':'unknown','span_id':None,'start':None,'end':None,'quote':None} for field in d['required_fields']}} for d in self.documents]
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'schema_version':'lx0609-anesthesia-visit-facts-v1','documents':items},ensure_ascii=False)}}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}

async def capture_case(case,privacy,helper):
    doc=helper.VisitDocument('synthetic-n12-'+case['case_id'],case['source_type'],case['input_body'],tuple(case['required_fields']))
    direct=Capture();formal=Capture()
    direct_out=await helper.extract_anesthesia_visit_facts([doc],direct)
    formal_out=await helper.extract_anesthesia_visit_facts([doc],privacy.wrap_luxian_0609_llm_client(formal,identity_values=case['private_values']))
    assert len(direct.calls)==1
    d=direct.documents[0] if direct.documents else None
    f=formal.documents[0] if formal.documents else None
    prompt=formal.calls[0]['prompt'] if formal.calls else ''
    actual={'direct_INPUT_JSON_valid':direct.documents is not None,'formal_delegate_INPUT_JSON_valid':formal.documents is not None,'formal_body_equals_direct_helper_view':bool(f and d and f['body']==d['body']),'formal_spans_equal_direct_helper_view':bool(f and d and f['spans']==d['spans']),'all_medical_quotes_retained':bool(f and all(q in f['body'] and any(q in s for s in f['spans'].values()) for q in case['medical_quotes'])),'private_values_absent':all(v not in prompt for v in case['private_values']),'body_is_exact_prefix_plus_original_n12_text':case['input_body']==case['synthetic_prefix']+case['original_n12_body']}
    return {'case_id':case['case_id'],'expected':case['expected'],'actual':actual,'mismatches':[k for k,v in case['expected'].items() if actual[k]!=v],'direct_capture':direct.calls,'formal_capture':formal.calls,'direct_document':d,'formal_document':f,'formal_parse_error':formal.parse_error,'direct_helper_state':direct_out.state,'direct_helper_reason':direct_out.reason_code,'formal_helper_state':formal_out.state,'formal_helper_reason':formal_out.reason_code,'logical_direct_calls':direct_out.llm_call_count,'logical_formal_calls':formal_out.llm_call_count,'actual_delegate_capture_calls':len(formal.calls),'clinical_inference':'capture only; unknown fixture response is not a semantic verdict'}

async def run(plan,privacy,helper):return [await capture_case(c,privacy,helper) for c in plan['cases']]

def main():
    if sys.argv[1:]!=['--slot-authorized']:raise SystemExit('No authorized test slot token; prepared probe does not execute')
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    pre={b['frozen_file']:hashlib.sha256((OUT/b['frozen_file']).read_bytes()).hexdigest() for b in plan['source_bindings']}
    assert all(pre[b['frozen_file']]==b['sha256'] for b in plan['source_bindings'])
    plan_hash=hashlib.sha256(PLAN.read_bytes()).hexdigest();runner_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    sys.dont_write_bytecode=True;install_guard();privacy,helper=load_actual()
    rows=asyncio.run(run(plan,privacy,helper))
    post={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in pre}
    result={'fixed_sha':plan['fixed_sha'],'phase':'completed','probe_kind':'pure stdlib actual helper/formal wrapper synthetic carrier capture','case_count':len(rows),'mismatch_case_count':sum(bool(r['mismatches']) for r in rows),'source_hashes_unchanged':pre==post,'expectations_unchanged':hashlib.sha256(PLAN.read_bytes()).hexdigest()==plan_hash,'runner_sha256':runner_hash,'expectations_sha256':plan_hash,'guard':'credential/private/DB/network/model/subprocess denied; stdlib local asyncio socketpair only','real_model_calls':0,'actual_helpers':['extract_anesthesia_visit_facts','wrap_luxian_0609_llm_client','redact_luxian_0609_patient_privacy','_document_spans','_usage','_located_present'],'loader_limit':'exact fixed production AST; only three relative dependency imports omitted and their verbatim stdlib helper symbols injected; no full application execution','rows':rows}
    (OUT/'first-capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for r in rows:print(r['case_id'], 'matches' if not r['mismatches'] else 'MISMATCH:'+','.join(r['mismatches']))
    print(json.dumps({k:result[k] for k in ('fixed_sha','case_count','mismatch_case_count','source_hashes_unchanged','expectations_unchanged','real_model_calls')},ensure_ascii=False))
if __name__=='__main__':main()
