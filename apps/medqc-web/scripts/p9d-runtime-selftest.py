"""包内独立Runtime固定无效应答冒烟；绝不调用模型，不验证医学质量。"""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys

for key in tuple(os.environ):
    if any(part in key.upper() for part in ('DATABASE', 'DSN', 'LLM', 'STRATA', 'SUPABASE', 'SECRET', 'API_KEY', 'REMOTE_DB')):
        os.environ.pop(key)
os.environ['JWT_SECRET'] = 'p9d-isolated-fixed-only-not-production'
os.environ['DATABASE_URL'] = ''
_PAIR = getattr(socket.socketpair, '__code__', None)
_CONNECT = socket.socket.connect


def deny_connect(sock, address):
    # Windows stdlib实现socketpair需要瞬时本机连接；不放开任意localhost请求。
    if _PAIR is not None and sys._getframe(1).f_code is _PAIR:
        return _CONNECT(sock, address)
    raise RuntimeError('package_full_chain_offline')


socket.socket.connect = deny_connect

from scripts.p9d_isolated_smoke import run_formal  # noqa: E402
from app.core.settings import Settings  # noqa: E402
import app  # noqa: E402

package_root = Path(sys.executable).resolve().parents[1]
assert package_root in Path(app.__file__).resolve().parents
assert sys.flags.isolated == 1 and sys.flags.no_site == 1


class FixedClient:
    provider_code = 'alibaba'
    model = 'synthetic-fixed-protocol-error'
    model_role = 'adjudicator'
    custom_parameters = {}
    temperature = 0

    async def generate(self, *args, **kwargs):
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}}


state = Path(sys.argv[1]).resolve()
state.mkdir(parents=True, exist_ok=False)
report = asyncio.run(run_formal(FixedClient(), Settings(_env_file=None, JWT_SECRET=os.environ['JWT_SECRET']),
                                state, in_memory=True))
assert report['saved_results'] and report['persistence_failures']
assert len(report['selected_rule_ids']) == len(report['results'])
assert not [f for f in report['persistence_failures'] if f['reason'] == 'canonical_save_or_read_failed']
print(json.dumps({'package_fixed_full_chain': True, 'model_requests': 0, 'rules': len(report['results']),
                  'saved': len(report['saved_results']), 'technical_failures': len(report['persistence_failures'])}))
