"""Prepared runner. No execution until root allocates an exclusive test slot."""
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path('F:/MedQC-worktrees/qc-integration-20261008');BACKEND=ROOT/'apps/medqc-web/backend'
def git(*args):return subprocess.run(['git','-C',str(ROOT),*args],check=True,capture_output=True,encoding='utf-8').stdout.strip()
def main():
    if sys.argv[1:] != ['--slot-authorized']:
        raise SystemExit('Prepared only: root exclusive slot required; no tests started.')
    plan=json.loads((OUT/'replay-plan.json').read_text(encoding='utf-8'))
    target=plan['target_sha'];head=git('rev-parse','HEAD')
    production_delta=git('diff','--name-only',target,'--','apps/medqc-web/backend/app')
    if production_delta:raise SystemExit('Target production source differs; do not relabel new source as fixed target.')
    bindings=[]
    entries=[*plan['test_bindings'],*plan['source_bindings'].values(),plan['helper_binding']]
    for entry in entries:
        path=entry['repo_path'];actual=git('hash-object','--path='+path,str(ROOT/path))
        if actual!=entry['current_blob']:raise SystemExit('Source/test binding mismatch: '+path)
        bindings.append({'repo_path':path,'blob':actual})
    for entry in plan['test_bindings']:
        data=(OUT/'frozen-tests'/entry['name']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise SystemExit('Frozen original oracle changed')
    if git('diff','--name-only',target,'--','apps/medqc-web/backend/pytest.ini'):
        raise SystemExit('pytest.ini differs from fixed target')
    os.chdir(BACKEND);sys.path.insert(0,str(BACKEND/'tests/unit'));sys.path.insert(0,str(BACKEND));sys.dont_write_bytecode=True
    os.environ['DATABASE_URL']='';os.environ['JWT_SECRET']='synthetic-iml-current-only';os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1';os.environ['PYTEST_ADDOPTS']=''
    # Prewarm stdlib Windows platform cache before denying subprocess. No project import.
    platform.uname();platform.machine()
    integrity_paths=[Path(__file__),OUT/'offline_guard.py',BACKEND/'pytest.ini',*[ROOT/entry['repo_path'] for entry in entries],*[OUT/'frozen-tests'/entry['name'] for entry in plan['test_bindings']]]
    before_hashes={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in integrity_paths}
    from offline_guard import install
    guard=install()
    manifest={'schema_version':'iml-current-synthetic-run-v1','target_sha':target,'actual_head':head,'source_and_oracle_bindings':bindings,'historical_report_sha':plan['historical_report_sha'],'historical_report_not_relabelled':True,'scope':'two original synthetic unit files only; unchanged oracle including legacy 015 prompt failure','guard':guard,'phase':'started','junit_path':str(OUT/'current-synthetic.xml'),'runner_sha256':before_hashes[str(Path(__file__).resolve())],'pre_execution_sha256':before_hashes,'stdlib_platform_pre_cached_before_guard':True}
    (OUT/'current-synthetic-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    import pytest
    args=['-c',str(BACKEND/'pytest.ini'),'--confcutdir='+str(OUT/'frozen-tests'),'-p','pytest_asyncio.plugin','-p','no:cacheprovider','-q','--tb=short','--disable-warnings','--junitxml='+str(OUT/'current-synthetic.xml'),'--basetemp='+str(OUT/'pytest-tmp'),*[str(OUT/'frozen-tests'/entry['name']) for entry in plan['test_bindings']]]
    code=int(pytest.main(args));manifest['phase']='completed';manifest['pytest_exit_code']=code
    after_hashes={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in integrity_paths}
    manifest['post_execution_sha256']=after_hashes
    manifest['all_source_test_runner_hashes_unchanged']=before_hashes==after_hashes
    loaded={name:str(Path(value.__file__).resolve()) for name,value in sys.modules.items() if name=='app' or name.startswith('app.') if getattr(value,'__file__',None)}
    manifest['actual_loaded_app_paths']=loaded
    expected_app=str((BACKEND/'app').resolve()).replace('\\','/').lower().rstrip('/')+'/'
    manifest['all_loaded_app_paths_in_target']=all(path.replace('\\','/').lower().startswith(expected_app) for path in loaded.values()) and bool(loaded)
    if not manifest['all_source_test_runner_hashes_unchanged'] or not manifest['all_loaded_app_paths_in_target']:
        manifest['phase']='integrity_failed';code=2
    (OUT/'current-synthetic-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return code
if __name__=='__main__':raise SystemExit(main())

