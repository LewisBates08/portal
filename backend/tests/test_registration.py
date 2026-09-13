import pytest
from sqlalchemy import func, select
from app.config import get_settings
from app.models import Agency, AuthSession, User
from app.security import passwords

URL = '/api/v1/auth/register'
DATA = {'name': 'Taylor Smith', 'agency_name': 'New Search Agency', 'email': 'taylor@example.com', 'password': ' AStrongPassword! '}


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_signup_creates_isolated_agency_and_working_session(client, db, world):
    # Even matching an existing agency name must not join that agency.
    response = client.post(URL, json={**DATA, 'agency_name': world['agency'].name, 'email': 'TAYLOR@EXAMPLE.COM'})
    assert response.status_code == 201, response.text
    data = response.json()
    user = db.get(User, data['user']['id'])
    assert user.agency_id != world['agency'].id
    assert user.role == 'admin' and user.client_org_id is None
    assert user.email == 'taylor@example.com'
    assert user.password_hash != DATA['password']
    assert passwords.verify(DATA['password'], user.password_hash)
    assert 'password_hash' not in data['user']
    headers = {'Authorization': 'Bearer ' + data['access_token']}
    assert client.get('/api/v1/auth/me', headers=headers).json()['id'] == user.id
    assert client.get('/api/v1/projects', headers=headers).json() == []
    assert client.get(f'/api/v1/projects/{world["project"].id}', headers=headers).status_code == 404
    org = client.post('/api/v1/client-organisations', headers=headers, json={'name': 'First client'})
    assert org.status_code == 201
    assert client.post('/api/v1/projects', headers=headers, json={'title': 'First search', 'client_org_id': org.json()['id']}).status_code == 201
    assert client.post('/api/v1/auth/login', json={'email': DATA['email'], 'password': DATA['password']}).status_code == 200
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': data['refresh_token']}).status_code == 200


@pytest.mark.parametrize('role', ['admin', 'recruiter', 'client'])
def test_duplicate_email_never_changes_existing_account(client, db, world, role):
    existing = world[role]
    before = [count(db, model) for model in (Agency, User, AuthSession)]
    original = (existing.role, existing.agency_id, existing.password_hash)
    response = client.post(URL, json={**DATA, 'email': existing.email.upper()})
    assert response.status_code == 409
    assert 'sign in' in response.json()['detail']
    assert [count(db, model) for model in (Agency, User, AuthSession)] == before
    db.refresh(existing)
    assert (existing.role, existing.agency_id, existing.password_hash) == original


@pytest.mark.parametrize('change', [
    {'name': '   '}, {'agency_name': '   '}, {'email': 'invalid'},
    {'password': 'short'}, {'password': 'x' * 129},
    {'role': 'admin'}, {'agency_id': 1}, {'client_org_id': 1},
])
def test_signup_validation_cannot_grant_existing_workspace_access(client, db, change):
    before = [count(db, model) for model in (Agency, User)]
    assert client.post(URL, json={**DATA, **change}).status_code == 422
    assert [count(db, model) for model in (Agency, User)] == before


def test_signup_is_rate_limited(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), 'auth_rate_limit', 1)
    assert client.post(URL, json=DATA).status_code == 201
    before = count(db, Agency)
    result = client.post(URL, json={**DATA, 'email': 'second@example.com'})
    assert result.status_code == 429
    assert count(db, Agency) == before
