"""Validate the actual frontend patch in an owned temporary Linux fixture; no backend."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = argparse.ArgumentParser()
parser.add_argument('--kit', type=Path, required=True)
parser.add_argument('--old-dist', type=Path, required=True)
parser.add_argument('--server', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
m = load('manager', args.kit / 'manage.py')
server_module = load('static_server', args.server)
meta = m.read(args.kit / 'PATCH.json')
report = {'status': 'RUNNING', 'python': sys.version.split()[0],
          'os_release': Path('/etc/os-release').read_text(),
          'database_connections': 0, 'model_calls': 0, 'backend_started': False}


def smoke(dist, identity):
    # Existing static server, loopback ephemeral port, API proxy deliberately absent.
    server = server_module.ThreadingHTTPServer(('127.0.0.1', 0),
        lambda *a, **kw: server_module.SpaHandler(*a, directory=str(dist), **kw))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(base + '/build-info.json', timeout=5) as response:
            assert json.load(response) == identity
        with opener.open(base + '/workstation-v5/login', timeout=5) as response:
            html = response.read().decode()
        assets = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', html)
        assert assets
        for asset in assets:
            with opener.open(base + asset, timeout=5) as response:
                assert response.read() == (dist / asset.lstrip('/')).read_bytes()
        return len(assets)
    finally:
        server.shutdown(); server.server_close(); thread.join()


with tempfile.TemporaryDirectory(prefix='medqc-frontend-only-') as folder:
    root = Path(folder) / 'business'
    release = root / 'releases/synthetic'
    (release / 'backend/app/data').mkdir(parents=True)
    shutil.copytree(args.old_dist, release / 'frontend/dist')
    (root / 'current').symlink_to(release)
    (release / 'backend/app/data/runtime_build.json').write_text(json.dumps({'git_commit': meta['backend_commit']}))
    for name in ['config/business.env', 'state/case-materials/synthetic', 'state/history-marker']:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('synthetic unchanged')
    protected = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file() and '/frontend/' not in str(p)}
    before = m.hashes(release / 'frontend/dist')
    def run(action):
        result = subprocess.run([sys.executable, '-B', args.kit / 'manage.py', action,
            '--root', root, '--expected-current', release], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    report['check'] = run('check')['ok']
    report['apply'] = run('apply')['ok']
    report['new_entry_assets'] = smoke(release / 'frontend/dist', meta['frontend_identity'])
    assert m.hashes(release / 'frontend/dist') == meta['files']
    report['rollback'] = run('rollback')['ok']
    report['old_entry_assets'] = smoke(release / 'frontend/dist', meta['previous_frontend_identity'])
    assert m.hashes(release / 'frontend/dist') == before
    assert all(Path(p).read_bytes() == data for p, data in protected.items())
    report['old_frontend_exactly_restored'] = True
    report['synthetic_backend_config_history_snapshot_unchanged'] = True
    report['status'] = 'PASS'
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report))
