import os,sys,json,hashlib,subprocess,platform
from pathlib import Path
OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[1]; BACKEND=ROOT/'apps/medqc-web/backend'
if sys.argv[1:]!=['--slot-authorized']: raise SystemExit('requires root test slot')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
targets=json.loads((OUT/'test-args.json').read_text(encoding='utf-8-sig'))
paths=[Path(__file__),OUT/'offline_guard.py',OUT/'test-args.json',*sorted((BACKEND/'app/services/luxian_0609').rglob('*.py')),*sorted((BACKEND/'app/data').glob('luxian_0609*.json')),*[BACKEND/'tests/unit'/s.split('::')[0] for s in targets]]
hashes=lambda:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=hashes(); os.chdir(BACKEND); sys.path[:0]=[str(BACKEND),str(BACKEND/'tests/unit')]; sys.dont_write_bytecode=True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; os.environ['PYTEST_ADDOPTS']=''
platform.uname(); platform.machine()
from offline_guard import install_offline_guard
guards=install_offline_guard()
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]).replace('\\','/').lower(); base=name.rsplit('/',1)[-1]
  if base.startswith('.env') or base in {'.pgpass','.pg_service.conf'} or '/0910-full-audit/' in name or '/round-20261007-private/' in name: raise RuntimeError('private/config read blocked')
  if name.endswith(('.db','.sqlite','.sqlite3')) and not name.startswith(str(OUT).replace('\\','/').lower()+'/'): raise RuntimeError('only fresh synthetic output SQLite allowed')
 if event=='sqlite3.connect':
  dest=str(args[0]).replace('\\','/').lower()
  if dest!=':memory:' and not dest.startswith(str(OUT).replace('\\','/').lower()+'/'): raise RuntimeError('SQLite path outside synthetic output')
 if event in {'socket.getaddrinfo','socket.gethostbyname','subprocess.Popen'}: raise RuntimeError('network/process blocked')
sys.addaudithook(audit)
import pytest
code=int(pytest.main(['--confcutdir=tests/unit','-p','pytest_asyncio.plugin','-p','no:cacheprovider','-q','--tb=short','--disable-warnings','--basetemp',str(OUT/'pytest-tmp'),'--junitxml='+str(OUT/'results.xml'),*['tests/unit/'+s for s in targets]]))
after=hashes(); loaded={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='app' or n.startswith('app.')) and getattr(m,'__file__',None)}
prefix=str((BACKEND/'app').resolve()).lower()+os.sep
correct=bool(loaded) and all(p.lower().startswith(prefix) for p in loaded.values())
(OUT/'manifest.json').write_text(json.dumps({'actual_head':head,'pytest_exit':code,'pre_sha256':before,'post_sha256':after,'unchanged':before==after,'all_app_in_target':correct,'loaded_app':loaded,'scope':'synthetic only; no clinical/model validation'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raise SystemExit(code if before==after and correct else 2)
