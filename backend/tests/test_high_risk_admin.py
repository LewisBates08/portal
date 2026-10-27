"""Focused regressions for access-granting and quota administration routes."""

from sqlalchemy import func, select

from app.config import get_settings
from app.models import AuditEvent, ClientOrg, Membership, User, WebSession


def test_promote_admin_restricts_target_and_revokes_sessions(client, world, auth, db):
    headers = auth("admin")
    recruiter = world["recruiter"]
    auth("recruiter")
    assert (
        db.scalar(
            select(func.count())
            .select_from(WebSession)
            .where(WebSession.user_id == recruiter.id)
        )
        == 1
    )

    response = client.post(
        f"/api/v1/users/{recruiter.id}/promote-admin", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert db.get(User, recruiter.id).role == "admin"
    assert (
        db.scalar(
            select(func.count())
            .select_from(WebSession)
            .where(WebSession.user_id == recruiter.id)
        )
        == 0
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "administrator_promoted",
                AuditEvent.resource == str(recruiter.id),
            )
        )
        == 1
    )

    for target in (world["client"], world["outsider"], world["admin"]):
        before = target.role
        denied = client.post(
            f"/api/v1/users/{target.id}/promote-admin", headers=headers
        )
        assert denied.status_code == 400
        assert db.get(User, target.id).role == before


def test_add_member_enforces_role_agency_organisation_and_duplicates(
    client, world, auth, db, password_hash
):
    headers = auth("admin")
    project_id = world["second"].id
    other_org = ClientOrg(name="Other local client", agency_id=world["agency"].id)
    db.add(other_org)
    db.flush()
    wrong_client = User(
        agency_id=world["agency"].id,
        client_org_id=other_org.id,
        email="wrong-client@example.com",
        name="Wrong client",
        password_hash=password_hash,
        role="client",
        active=True,
        email_verified=True,
    )
    db.add(wrong_client)
    db.commit()

    valid = client.put(
        f"/api/v1/projects/{project_id}/members/{world['recruiter'].id}",
        headers=headers,
    )
    duplicate = client.put(
        f"/api/v1/projects/{project_id}/members/{world['recruiter'].id}",
        headers=headers,
    )
    assert valid.status_code == duplicate.status_code == 204
    assert (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.project_id == project_id,
                Membership.user_id == world["recruiter"].id,
            )
        )
        == 1
    )

    for target in (wrong_client, world["outsider"], world["admin"]):
        denied = client.put(
            f"/api/v1/projects/{project_id}/members/{target.id}", headers=headers
        )
        assert denied.status_code == 400
        assert db.get(Membership, (project_id, target.id)) is None


def test_project_creation_prerequisites_and_active_quota(
    client, world, auth, monkeypatch
):
    headers = auth("admin")
    settings = get_settings()
    monkeypatch.setattr(settings, "max_projects", 2)
    payload = {"title": "At the limit", "client_org_id": world["org"].id}

    assert (
        client.post("/api/v1/projects", headers=headers, json=payload).status_code
        == 409
    )
    foreign = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Foreign", "client_org_id": world["other_org"].id},
    )
    assert foreign.status_code == 400
    assert (
        client.post(
            "/api/v1/projects", headers=auth("recruiter"), json=payload
        ).status_code
        == 403
    )

    archived = client.post(
        f"/api/v1/projects/{world['second'].id}/archive", headers=headers
    )
    assert archived.status_code == 200
    created = client.post("/api/v1/projects", headers=headers, json=payload)
    assert created.status_code == 201
    assert created.json()["title"] == "At the limit"


def test_candidate_quota_boundary(client, world, auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_candidates", 1)
    path = f"/api/v1/projects/{world['project'].id}/candidates"
    headers = auth("recruiter")
    payload = {"name": "First", "stage": "Identified", "client_visible": False}
    assert client.post(path, headers=headers, json=payload).status_code == 201
    assert (
        client.post(
            path, headers=headers, json={**payload, "name": "Second"}
        ).status_code
        == 409
    )
