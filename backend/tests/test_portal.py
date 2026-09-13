from datetime import timedelta
from urllib.parse import urlsplit, parse_qs
import jwt
import pytest
from sqlalchemy import select
from app.config import get_settings
from app.models import Invitation, Membership, User, now

API = '/api/v1'


def token_from(response):
    assert response.status_code == 201, response.text
    return parse_qs(urlsplit(response.json()['url']).fragment)['token'][0]


def candidate(client, base, headers, **extra):
    res = client.post(base + '/candidates', headers=headers, json={'name': 'Candidate', **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_complete_invitation_and_search_workflow(client, world, auth):
    admin = auth('admin')
    res = client.post(API + '/projects', headers=admin, json={'title': 'New search', 'client_org_id': world['org'].id, 'agreement_terms': '25% retained fee', 'start_date': '2026-09-01', 'end_date': '2026-11-01'})
    assert res.status_code == 201, res.text
    base = API + f'/projects/{res.json()["id"]}'
    pid = res.json()['id']
    assert client.put(base + f'/members/{world["recruiter"].id}', headers=admin).status_code == 204
    recruiter = auth('recruiter')
    c = candidate(client, base, recruiter, stage='Interviewing', client_visible=True)
    invitation = client.post(API + '/invitations', headers=admin, json={'email': 'newclient@example.com', 'role': 'client', 'project_id': pid})
    token = token_from(invitation)
    assert client.post(API + '/auth/invitation', json={'token': token}).json()['existing_user'] is False
    accepted = client.post(API + '/auth/accept-invitation', json={'token': token, 'name': 'New Client', 'password': 'NewClientPassword!'})
    assert accepted.status_code == 200, accepted.text
    customer = {'Authorization': 'Bearer ' + accepted.json()['access_token']}
    assert len(client.get(API + '/projects', headers=customer).json()) == 1
    assert client.get(base, headers=customer).json()['agreement_terms'] == '25% retained fee'
    assert client.get(base + '/candidates', headers=customer).json()[0]['stage'] == 'Interviewing'
    assert client.post(base + f'/candidates/{c["id"]}/feedback', headers=customer, json={'body': 'Strong profile.'}).status_code == 201
    assert client.post(base + '/updates', headers=customer, json={'body': 'Focus on leadership.'}).status_code == 201
    assert client.post(base + '/messages', headers=customer, json={'body': 'Ready for interviews.'}).status_code == 201
    assert client.get(base, headers=recruiter).json()['unread_count'] == 1
    assert client.post(API + '/auth/accept-invitation', json={'token': token, 'name': 'Reuse', 'password': 'NewClientPassword!'}).status_code == 400


def test_existing_user_invitation_requires_matching_login(client, world, auth):
    admin = auth('admin')
    token = token_from(client.post(API + '/invitations', headers=admin, json={'email': 'client@example.com', 'role': 'client', 'project_id': world['second'].id}))
    payload = {'token': token, 'name': 'Changed', 'password': 'ChangedPassword!'}
    assert client.post(API + '/auth/accept-invitation', json=payload).status_code == 403
    assert client.post(API + '/auth/accept-invitation', json=payload, headers=auth('colleague')).status_code == 403
    assert client.post(API + '/auth/accept-invitation', json=payload, headers=auth('client')).status_code == 200
    assert client.post(API + '/auth/login', json={'email': 'client@example.com', 'password': 'PasswordForTests!'}).status_code == 200
    assert client.get(API + '/auth/me', headers=auth('client')).json()['name'] == 'client'


@pytest.mark.parametrize('role', ['client', 'recruiter', 'colleague', 'outsider'])
def test_project_and_agency_isolation(client, world, auth, role):
    headers = auth(role)
    forbidden = world['project'] if role in ('colleague', 'outsider') else world['second']
    assert client.get(API + f'/projects/{forbidden.id}', headers=headers).status_code == 404
    assert client.get(API + f'/projects/{world["foreign"].id}', headers=auth('admin')).status_code == 404
    if role != 'outsider':
        assert client.get(API + '/users', headers=headers).status_code == 403
        assert client.get(API + '/client-organisations', headers=headers).status_code == 403


def test_hidden_candidates_and_feedback_are_not_leaked(client, world, auth):
    base = API + f'/projects/{world["project"].id}'
    recruiter, customer = auth('recruiter'), auth('client')
    hidden = candidate(client, base, recruiter, stage='Shortlisted', client_visible=False)
    shown = candidate(client, base, recruiter, stage='Interviewing', client_visible=True)
    client.post(base + f'/candidates/{hidden["id"]}/feedback', headers=recruiter, json={'body': 'Internal review'})
    result = client.get(base + '/candidates', headers=customer).json()
    assert [c['id'] for c in result] == [shown['id']]
    for suffix in ('', '/feedback'):
        assert client.get(base + f'/candidates/{hidden["id"]}' + suffix, headers=customer).status_code == 404
    assert client.post(base + f'/candidates/{hidden["id"]}/feedback', headers=customer, json={'body': 'Sneak in'}).status_code == 404
    for path, body in [('/candidates', {'name': 'Client candidate'}), ('/milestones', {'title': 'Client milestone', 'target_date': '2026-10-01'}), ('/documents', {'title': 'Terms', 'url': 'https://example.com'})]:
        assert client.post(base + path, headers=customer, json=body).status_code == 403
    assert client.put(base + f'/candidates/{shown["id"]}', headers=customer, json={'name': 'Changed'}).status_code == 403
    assert client.put(base, headers=customer, json={'title': 'Changed'}).status_code == 403


def test_nested_resources_cannot_be_addressed_through_another_project(client, world, auth):
    a, b = [API + f'/projects/{world[k].id}' for k in ('project', 'second')]
    admin = auth('admin')
    c = candidate(client, b, admin)
    post = client.post(b + '/updates', headers=admin, json={'body': 'Other project'}).json()
    milestone = client.post(b + '/milestones', headers=admin, json={'title': 'Other', 'target_date': '2026-10-01'}).json()
    doc = client.post(b + '/documents', headers=admin, json={'title': 'Other', 'url': 'https://example.com'}).json()
    msg = client.post(b + '/messages', headers=admin, json={'body': 'Other'}).json()
    assert client.get(a + f'/candidates/{c["id"]}', headers=admin).status_code == 404
    assert client.get(a + f'/candidates/{c["id"]}/feedback', headers=admin).status_code == 404
    assert client.put(a + f'/candidates/{c["id"]}', headers=admin, json={'name': 'Changed'}).status_code == 404
    assert client.post(a + f'/updates/{post["id"]}/comments', headers=admin, json={'body': 'Wrong project'}).status_code == 404
    assert client.delete(a + f'/milestones/{milestone["id"]}', headers=admin).status_code == 404
    assert client.delete(a + f'/documents/{doc["id"]}', headers=admin).status_code == 404
    assert client.put(a + '/messages/read', headers=admin, json={'last_message_id': msg['id']}).status_code == 404


def test_removed_membership_takes_effect_with_existing_token(client, world, auth):
    base = API + f'/projects/{world["project"].id}'
    admin, recruiter, customer = auth('admin'), auth('recruiter'), auth('client')
    for role, headers in [('recruiter', recruiter), ('client', customer)]:
        assert client.get(base, headers=headers).status_code == 200
        assert client.delete(base + f'/members/{world[role].id}', headers=admin).status_code == 204
        assert client.get(base, headers=headers).status_code == 404
        assert client.get(base + '/messages', headers=headers).status_code == 404
        assert client.post(base + '/updates', headers=headers, json={'body': 'No longer permitted'}).status_code == 404


def test_invitation_expiry_revocation_role_and_tenant_checks(client, db, world, auth):
    admin = auth('admin')
    payload = {'email': 'future@example.com', 'role': 'client', 'project_id': world['project'].id}
    token = token_from(client.post(API + '/invitations', headers=admin, json=payload))
    invite = db.scalar(select(Invitation).where(Invitation.email == payload['email']))
    invite.expires_at = now() - timedelta(seconds=1); db.commit()
    assert client.post(API + '/auth/invitation', json={'token': token}).status_code == 400
    assert client.post(API + '/auth/accept-invitation', json={'token': token, 'name': 'Future', 'password': 'PasswordForTests!'}).status_code == 400
    response = client.post(API + '/invitations', headers=admin, json=payload)
    revoked = token_from(response)
    assert client.delete(API + f'/invitations/{response.json()["id"]}', headers=admin).status_code == 204
    assert client.post(API + '/auth/invitation', json={'token': revoked}).status_code == 400
    for invalid in [dict(payload, role='admin'), dict(payload, project_id=None), dict(payload, email='recruiter@example.com'), dict(payload, email='outsider@example.com'), dict(payload, client_org_id=world['other_org'].id)]:
        assert client.post(API + '/invitations', headers=admin, json=invalid).status_code in (400, 409, 422)
    assert client.post(API + '/invitations', headers=admin, json=dict(payload, project_id=world['foreign'].id)).status_code == 404
    assert client.post(API + '/invitations', headers=auth('recruiter'), json=payload).status_code == 403
    assert client.put(API + f'/projects/{world["project"].id}/members/{world["outsider"].id}', headers=admin).status_code == 400


def test_refresh_rotation_replay_and_logout(client, world):
    login = client.post(API + '/auth/login', json={'email': 'admin@example.com', 'password': 'PasswordForTests!'}).json()
    result = client.post(API + '/auth/refresh', json={'refresh_token': login['refresh_token']})
    assert result.status_code == 200
    rotated = result.json()
    assert rotated['refresh_token'] != login['refresh_token']
    assert client.post(API + '/auth/refresh', json={'refresh_token': login['refresh_token']}).status_code == 401
    assert client.get(API + '/auth/me', headers={'Authorization': 'Bearer ' + rotated['access_token']}).status_code == 401
    fresh = client.post(API + '/auth/login', json={'email': 'admin@example.com', 'password': 'PasswordForTests!'}).json()
    assert client.post(API + '/auth/logout', json={'refresh_token': fresh['refresh_token']}).status_code == 204
    assert client.get(API + '/auth/me', headers={'Authorization': 'Bearer ' + fresh['access_token']}).status_code == 401
    assert client.post(API + '/auth/refresh', json={'refresh_token': fresh['refresh_token']}).status_code == 401


def test_invalid_and_expired_tokens_and_passwords(client, world):
    login = client.post(API + '/auth/login', json={'email': 'admin@example.com', 'password': 'PasswordForTests!'}).json()
    claims = jwt.decode(login['access_token'], get_settings().jwt_secret, algorithms=['HS256'])
    claims['exp'] = now() - timedelta(minutes=1)
    expired = jwt.encode(claims, get_settings().jwt_secret, algorithm='HS256')
    for token in (expired, 'garbage', login['refresh_token']):
        assert client.get(API + '/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    assert client.get(API + '/projects').status_code == 401
    for email in ('admin@example.com', 'unknown@example.com'):
        assert client.post(API + '/auth/login', json={'email': email, 'password': 'Wrong'}).status_code == 401
    assert client.post(API + '/auth/login', json={'email': 'ADMIN@EXAMPLE.COM', 'password': 'PasswordForTests!'}).status_code == 200
    assert 'password_hash' not in login['user']


def test_messages_read_marker_and_append_only_collaboration(client, world, auth):
    base = API + f'/projects/{world["project"].id}'
    recruiter, customer = auth('recruiter'), auth('client')
    msg = client.post(base + '/messages', headers=recruiter, json={'body': 'Message one'}).json()
    assert client.get(base, headers=customer).json()['unread_count'] == 1
    client.post(base + '/messages', headers=customer, json={'body': 'My own message'})
    assert client.get(base, headers=customer).json()['unread_count'] == 1
    snapshot = client.get(base + '/messages', headers=customer).json()
    client.post(base + '/messages', headers=recruiter, json={'body': 'Arrived after snapshot'})
    assert client.put(base + '/messages/read', headers=customer, json={'last_message_id': snapshot[-1]['id']}).status_code == 204
    assert client.get(base, headers=customer).json()['unread_count'] == 1
    assert client.put(base + '/messages/read', headers=customer, json={'last_message_id': msg['id']}).status_code == 204
    assert client.get(base, headers=customer).json()['unread_count'] == 1
    assert client.delete(base + f'/messages/{msg["id"]}', headers=recruiter).status_code in (404, 405)
    post = client.post(base + '/updates', headers=customer, json={'body': 'Update', 'attachment_url': 'https://example.com/reference'}).json()
    assert client.post(base + f'/updates/{post["id"]}/comments', headers=recruiter, json={'body': 'Comment'}).status_code == 201
    assert client.get(base + '/updates', headers=customer).json()[0]['comments'][0]['body'] == 'Comment'


def test_milestones_stage_visibility_and_validation(client, world, auth):
    base = API + f'/projects/{world["project"].id}'
    recruiter, customer = auth('recruiter'), auth('client')
    later = client.post(base + '/milestones', headers=recruiter, json={'title': 'Interviews', 'target_date': '2026-10-01'}).json()
    early = client.post(base + '/milestones', headers=recruiter, json={'title': 'Shortlist', 'target_date': '2026-09-01'}).json()
    assert [m['id'] for m in client.get(base + '/milestones', headers=customer).json()] == [early['id'], later['id']]
    for done in (True, False):
        response = client.put(base + f'/milestones/{early["id"]}', headers=recruiter, json={'title': 'Shortlist', 'target_date': '2026-09-01', 'completed': done})
        assert response.status_code == 200 and response.json()['completed'] is done
    assert client.delete(base + f'/milestones/{early["id"]}', headers=customer).status_code == 403
    assert client.delete(base + f'/milestones/{early["id"]}', headers=recruiter).status_code == 204
    c = candidate(client, base, recruiter, stage='Shortlisted', client_visible=True)
    for stage in ('Interviewing', 'Offered'):
        assert client.put(base + f'/candidates/{c["id"]}', headers=recruiter, json={'name': c['name'], 'stage': stage, 'client_visible': True}).status_code == 200
        assert client.get(base + '/candidates', headers=customer).json()[0]['stage'] == stage
    for path, body in [('/documents', {'title': 'Bad', 'url': 'javascript:alert(1)'}), ('/candidates', {'name': 'Bad', 'cv_url': 'data:text/html,bad'}), ('/updates', {'body': 'Bad', 'attachment_url': 'https://name:secret@example.com'}), ('/messages', {'body': '   '})]:
        assert client.post(base + path, headers=recruiter, json=body).status_code == 422
    assert client.put(base, headers=recruiter, json={'title': 'Bad dates', 'start_date': '2026-10-01', 'end_date': '2026-09-01'}).status_code == 422
    assert client.post(base + '/candidates', headers=recruiter, json={'name': 'Unknown field', 'project_id': world['foreign'].id}).status_code == 422


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), 'auth_rate_limit', 2)
    for _ in range(2):
        assert client.post(API + '/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'}).status_code == 401
    response = client.post(API + '/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'})
    assert response.status_code == 429 and response.headers['retry-after'] == '60'
