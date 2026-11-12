"""Synthetic sessions only; actual JWT and role dependencies, no application startup."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core import security
from app.routers import demo
from app.models.demo import Base

PATHS = [('GET', '/feedbacks'), ('GET', '/feedbacks/stats'),
         ('GET', '/feedbacks/by-rule/SYNTHETIC'), ('GET', '/feedbacks/export'),
         ('POST', '/feedbacks'), ('DELETE', '/feedbacks/synthetic')]
PAYLOAD = dict(rule_id='SYNTHETIC', rule_code='SYNTHETIC', rule_name='Synthetic',
               document_name='Synthetic', evaluation_result=True, feedback_type='correct',
               medical_text='SYNTHETIC ONLY')

@pytest.fixture
def setup(monkeypatch):
    app = FastAPI()
    app.include_router(demo.router)
    users = {}
    monkeypatch.setattr(security, 'resolve_user_by_subject', lambda subject: users.get(subject))
    def token(role):
        users[role] = dict(id=role, username=role, roles=[role], is_active=True)
        # An untrusted token claim must not confer administrator rights.
        return {'Authorization': 'Bearer ' + security.create_access_token(
            {'sub': role, 'roles': ['admin']})}
    with TestClient(app) as client:
        yield app, client, token

@pytest.mark.parametrize('method,path', PATHS)
@pytest.mark.parametrize('role', [None, 'doctor', 'qc_manager', 'qc_staff', 'invalid'])
def test_denied_before_feedback_session(setup, method, path, role):
    app, client, token = setup
    def forbidden_db():
        pytest.fail('unauthorized request reached feedback storage')
    app.dependency_overrides[demo.get_db] = forbidden_db
    headers = {} if role is None else ({'Authorization': 'Bearer invalid'} if role == 'invalid' else token(role))
    response = client.request(method, '/api/v1/demo' + path, headers=headers,
                              **({'json': PAYLOAD} if method == 'POST' else {}))
    assert response.status_code in (401, 403)
    assert 'SYNTHETIC ONLY' not in response.text

@pytest.mark.parametrize('role', ['admin', 'super_admin', 'sync_admin'])
def test_authorized_lifecycle_preserves_contract(setup, role):
    app, client, token = setup
    engine = create_engine('sqlite://', poolclass=StaticPool,
                           connect_args={'check_same_thread': False},
                           execution_options={'schema_translate_map': {'qc': None}})
    Base.metadata.create_all(engine)
    def db():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[demo.get_db] = db
    headers = token(role)
    base = '/api/v1/demo/feedbacks'
    try:
        created = client.post(base, headers=headers, json=PAYLOAD)
        assert created.status_code == 200, created.text
        identity = created.json()['data']['feedback_id']
        listing = client.get(base, headers=headers).json()
        assert listing['total'] == 1
        assert listing['data'][0]['medical_text'] == PAYLOAD['medical_text']
        for path in ['/stats', '/by-rule/SYNTHETIC', '/export']:
            response = client.get(base + path, headers=headers)
            assert response.status_code == 200, response.text
        assert client.delete(base + '/' + identity, headers=headers).json()['success']
        assert client.get(base, headers=headers).json()['total'] == 0
    finally:
        engine.dispose()
