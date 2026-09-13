"""Permission, concurrency-contract and persistence regressions on PostgreSQL."""

import uuid
import pytest
from app.models import Message

API = "/api/v1"


def base(world, key="project"):
    return API + f"/projects/{world[key].id}"


@pytest.mark.parametrize("role", ["recruiter", "client", "colleague", "outsider"])
def test_project_and_agency_isolation(client, world, auth, role):
    headers = auth(role)
    forbidden = "project" if role in ("colleague", "outsider") else "second"
    assert client.get(base(world, forbidden), headers=headers).status_code == 404
    assert client.get(base(world, "foreign"), headers=auth("admin")).status_code == 404
    if role != "outsider":
        assert client.get(API + "/users", headers=headers).status_code == 403


def test_hidden_candidates_feedback_and_client_writes(client, world, auth):
    staff, customer = auth("recruiter"), auth("client")
    path = base(world)
    hidden = client.post(
        path + "/candidates", headers=staff, json={"name": "Private"}
    ).json()
    shown = client.post(
        path + "/candidates",
        headers=staff,
        json={"name": "Shared", "client_visible": True},
    ).json()
    assert (
        client.post(
            path + f"/candidates/{hidden['id']}/feedback",
            headers=staff,
            json={"body": "Internal"},
        ).status_code
        == 201
    )
    assert [
        c["id"]
        for c in client.get(path + "/candidates", headers=customer).json()["items"]
    ] == [shown["id"]]
    for suffix in ("", "/feedback"):
        assert (
            client.get(
                path + f"/candidates/{hidden['id']}" + suffix, headers=customer
            ).status_code
            == 404
        )
    for resource, data in [
        ("candidates", {"name": "Bad"}),
        ("milestones", {"title": "Bad", "target_date": "2026-10-01"}),
        ("documents", {"title": "Bad", "url": "https://example.com"}),
    ]:
        assert (
            client.post(path + "/" + resource, headers=customer, json=data).status_code
            == 403
        )
    assert (
        client.put(
            path, headers=customer, json={"title": "Bad", "version": 1}
        ).status_code
        == 403
    )


def test_nested_ids(client, world, auth):
    headers = auth("admin")
    first, second = base(world), base(world, "second")
    c = client.post(
        second + "/candidates", headers=headers, json={"name": "Other"}
    ).json()
    p = client.post(second + "/updates", headers=headers, json={"body": "Other"}).json()
    m = client.post(
        second + "/milestones",
        headers=headers,
        json={"title": "Other", "target_date": "2026-10-01"},
    ).json()
    assert (
        client.get(
            first + f"/candidates/{c['id']}/feedback", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            first + f"/updates/{p['id']}/comments",
            headers=headers,
            json={"body": "Bad"},
        ).status_code
        == 404
    )
    assert (
        client.delete(first + f"/milestones/{m['id']}", headers=headers).status_code
        == 404
    )


def test_removed_access_and_suspension_immediate(client, world, auth):
    admin, customer = auth("admin"), auth("client")
    path = base(world)
    assert (
        client.delete(
            path + f"/members/{world['client'].id}", headers=admin
        ).status_code
        == 204
    )
    assert client.get(path, headers=customer).status_code == 404
    assert (
        client.put(
            API + f"/users/{world['recruiter'].id}/status",
            headers=admin,
            json={"active": False},
        ).status_code
        == 200
    )
    assert client.get(path, headers=auth("recruiter")).status_code == 401
    assert (
        client.put(
            API + f"/users/{world['admin'].id}/status",
            headers=admin,
            json={"active": False},
        ).status_code
        == 409
    )
    assert (
        client.put(
            API + f"/users/{world['outsider'].id}/status",
            headers=admin,
            json={"active": False},
        ).status_code
        == 404
    )


def test_retry_deduplication_and_conflict(client, world, auth):
    h = {**auth("client"), "Idempotency-Key": str(uuid.uuid4())}
    path = base(world) + "/messages"
    one = client.post(path, headers=h, json={"body": "Hello"})
    two = client.post(path, headers=h, json={"body": "Hello"})
    assert one.status_code == two.status_code == 201
    assert one.json()["id"] == two.json()["id"]
    assert client.post(path, headers=h, json={"body": "Different"}).status_code == 409


def test_edit_versions_and_milestone_reopen(client, world, auth):
    h = auth("recruiter")
    path = base(world)
    c = client.post(
        path + "/candidates", headers=h, json={"name": "Name", "client_visible": True}
    ).json()
    assert (
        client.put(
            path + f"/candidates/{c['id']}", headers=h, json={"name": "Changed"}
        ).status_code
        == 428
    )
    assert (
        client.put(
            path + f"/candidates/{c['id']}",
            headers=h,
            json={"name": "Changed", "stage": "Interviewing", "version": 1},
        ).status_code
        == 200
    )
    assert (
        client.put(
            path + f"/candidates/{c['id']}",
            headers=h,
            json={"name": "Stale", "version": 1},
        ).status_code
        == 409
    )
    m = client.post(
        path + "/milestones",
        headers=h,
        json={"title": "Shortlist", "target_date": "2020-01-01"},
    ).json()
    for version, done in [(1, True), (2, False)]:
        r = client.put(
            path + f"/milestones/{m['id']}",
            headers=h,
            json={
                "title": "Shortlist",
                "target_date": "2020-01-01",
                "completed": done,
                "version": version,
            },
        )
        assert r.status_code == 200 and r.json()["completed"] == done


def test_pagination_and_read_markers(client, world, auth, db):
    h = auth("client")
    path = base(world)
    db.add_all(
        [
            Message(
                project_id=world["project"].id,
                author_id=world["recruiter"].id,
                body=f"Message {i}",
            )
            for i in range(55)
        ]
    )
    db.commit()
    result = client.get(path + "/messages", headers=h).json()
    assert len(result["items"]) == 50 and result["next_cursor"]
    first = result["items"][-1]["id"]
    assert (
        client.put(
            path + "/messages/read", headers=h, json={"last_message_id": first}
        ).status_code
        == 204
    )
    assert client.get(path, headers=h).json()["unread_count"] == 5
    assert (
        client.put(
            path + "/messages/read", headers=h, json={"last_message_id": first + 1}
        ).status_code
        == 400
    )
    tail = client.get(
        path + f"/messages?cursor={result['next_cursor']}", headers=h
    ).json()
    assert len(tail["items"]) == 5 and tail["next_cursor"] is None
    assert (
        client.put(
            path + "/messages/read",
            headers=h,
            json={"last_message_id": tail["items"][-1]["id"]},
        ).status_code
        == 204
    )
    assert (
        client.put(
            path + "/messages/read", headers=h, json={"last_message_id": first}
        ).status_code
        == 204
    )
    assert client.get(path, headers=h).json()["unread_count"] == 0
    assert client.get(path + "/messages?limit=101", headers=h).status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "javascript:alert(1)",
        "https://user:secret@example.com",
        "data:text/html,bad",
    ],
)
def test_external_links(client, world, auth, url):
    assert (
        client.post(
            base(world) + "/documents",
            headers=auth("recruiter"),
            json={"title": "Bad", "url": url},
        ).status_code
        == 422
    )


def test_retention_export_deletion(client, world, auth):
    h = auth("admin")
    path = base(world)
    client.post(path + "/candidates", headers=h, json={"name": "Export Candidate"})
    client.post(path + "/updates", headers=h, json={"body": "Notes"})
    assert "Export Candidate" in client.get(path + "/export", headers=h).text
    assert client.post(path + "/archive", headers=h).status_code == 200
    assert (
        client.post(
            path + "/messages", headers=h, json={"body": "Archived"}
        ).status_code
        == 409
    )
    preview = client.get(path + "/deletion-preview", headers=h).json()
    assert preview["counts"]["candidates"] == 1
    assert (
        client.request(
            "DELETE",
            path,
            headers=h,
            json={"confirmation": "Wrong", "version": preview["version"]},
        ).status_code
        == 409
    )
    assert (
        client.request(
            "DELETE",
            path,
            headers=h,
            json={"confirmation": preview["title"], "version": preview["version"]},
        ).status_code
        == 204
    )
    assert client.get(path, headers=h).status_code == 404
