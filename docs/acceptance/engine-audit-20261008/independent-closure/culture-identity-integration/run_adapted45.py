import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path("F:/MedQC-worktrees/qc-integration-20261008")
BACKEND=ROOT/"apps/medqc-web/backend"
if sys.argv[1:] != ["--slot-authorized"]: raise SystemExit("prepared only; explicit root slot required")
base="21f4a93e103a34002a1f9d36f9d895f226c0122f"
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT,text=True,encoding="utf-8").strip()
assert not git("diff",base,"--","apps/medqc-web/backend/app")
files=["test_luxian_0609_culture_source_gap.py","test_luxian_0609_culture_identified_organism.py"]
assert git("hash-object","apps/medqc-web/backend/tests/unit/"+files[0])=="37a1954066d2fae3a105e423e1a5c4a0ecee9e13"
paths=[Path(__file__),OUT/"offline_guard.py",BACKEND/"pytest.ini",*[BACKEND/"tests/unit"/f for f in files],BACKEND/"app/services/luxian_0609/native_exam_lab_execution.py",BACKEND/"app/services/luxian_0609/exam_lab_fact_extraction.py"]
before={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
head=git("rev-parse","HEAD")
os.chdir(BACKEND);sys.path[:0]=[str(BACKEND),str(BACKEND/"tests/unit")];sys.dont_write_bytecode=True
os.environ["DATABASE_URL"]="";os.environ["JWT_SECRET"]="synthetic-culture-identity-only";os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1";os.environ["PYTEST_ADDOPTS"]=""
platform.uname();platform.machine()
from offline_guard import install
guard=install()
import pytest
args=["-c",str(BACKEND/"pytest.ini"),"--confcutdir="+str(BACKEND/"tests/unit"),"-p","pytest_asyncio.plugin","-p","no:cacheprovider","-q","--tb=short","--disable-warnings","--junitxml="+str(OUT/"adapted45.xml"),"--basetemp="+str(OUT/"pytest-tmp"),*[str(BACKEND/"tests/unit"/f) for f in files]]
code=int(pytest.main(args))
after={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
loaded={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=="app" or n.startswith("app.")) and getattr(m,"__file__",None)}
expected=str((BACKEND/"app").resolve()).replace("\\","/").lower().rstrip("/")+"/"
all_in_target=bool(loaded) and all(p.replace("\\","/").lower().startswith(expected) for p in loaded.values())
manifest={"base":base,"actual_head":head,"test_files":files,"pytest_exit":code,"guard":guard,"pre_execution_sha256":before,"post_execution_sha256":after,"all_hashes_unchanged":before==after,"all_loaded_app_paths_in_target":all_in_target,"loaded_app_paths":loaded,"scope":"synthetic contract adaptation only; not45 medical gold cases"}
(OUT/"adapted45-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
if before!=after or not all_in_target: code=2
raise SystemExit(code)
