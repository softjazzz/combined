"""Prepared offline guard; importing this file does not install or execute tests."""
import sys,traceback,socket
from pathlib import Path

class OfflineGuardViolation(RuntimeError): pass

def install():
    def control_socketpair():
        return any(frame.name == 'socketpair' and str(Path(frame.filename).resolve()).casefold() == str(Path(socket.__file__).resolve()).casefold() for frame in traceback.extract_stack())
    def audit(event,args):
        if event == 'open':
            name=str(args[0]).replace('\\','/').lower();base=name.rsplit('/',1)[-1]
            if base.startswith('.env') or base in {'.pgpass','.pg_service.conf'}:
                raise OfflineGuardViolation('credential/environment-file read forbidden')
            if '/.tmp/0910-full-audit/' in name or '/round-20261007-private/' in name:
                raise OfflineGuardViolation('historical clinical/private material read forbidden')
            if name.endswith(('.db','.sqlite','.sqlite3')):
                raise OfflineGuardViolation('database-file access forbidden')
        if event in {'sqlite3.connect','sqlite3.connect/handle','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'}:
            raise OfflineGuardViolation('database or network resolution forbidden')
        if event in {'socket.connect','socket.bind'}:
            address=args[1] if len(args)>1 else None
            local_pair=control_socketpair() and (not isinstance(address,tuple) or address[0] in {'127.0.0.1','::1','localhost'})
            if not local_pair:raise OfflineGuardViolation('network connection/bind forbidden')
        if event == 'subprocess.Popen':
            raise OfflineGuardViolation('subprocess after guard installation forbidden')
    sys.addaudithook(audit)
    class NoDatabaseDriver:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in {'psycopg','psycopg2','asyncpg','pg8000','pymysql','MySQLdb'}:
                raise OfflineGuardViolation('real database driver import forbidden')
            return None
    sys.meta_path.insert(0,NoDatabaseDriver())
    import dotenv
    dotenv.load_dotenv=lambda *a,**k:False
    dotenv.dotenv_values=lambda *a,**k:{}
    dotenv.find_dotenv=lambda *a,**k:''
    import httpx
    def no_http(*a,**k):raise OfflineGuardViolation('HTTP/model transport forbidden')
    httpx.Client.send=no_http;httpx.AsyncClient.send=no_http
    import sqlalchemy
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    def no_database(*a,**k):raise OfflineGuardViolation('SQLAlchemy connection/query forbidden')
    event.listen(Engine,'do_connect',no_database)
    event.listen(Engine,'before_cursor_execute',no_database)
    return {'credential_reads':'blocked','clinical_private_paths':'blocked','real_db':'blocked','network_and_model_transport':'blocked','asyncio_control_socketpair':'process-local only','subprocess_after_install':'blocked'}
