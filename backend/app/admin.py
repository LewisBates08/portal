from .responses import PageView
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .models import (
    Agency,
    AuditEvent,
    Candidate,
    Comment,
    Document,
    Feedback,
    Post,
    Message,
    Milestone,
    ReadMarker,
    Submission,
    ClientOrg,
    Invitation,
    Membership,
    Project,
    User,
    now,
)
from .schemas import (
    InviteCreate,
    OrgCreate,
    AccountStatus,
    RetentionPolicy,
    DeleteProject,
)
from .security import admin, digest, audit, revoke_sessions
from .resources import Paging, page, write_limit
from .auth import lock_invite
from .mail import queue_invitation
from .serializers import record, user_view

from .responses import UserView, OrgView, InviteLink, InviteView

router = APIRouter(
    tags=["Administration"], dependencies=[Depends(admin), Depends(write_limit)]
)


@router.get("/users", response_model=PageView[UserView])
def users(
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    return page(
        db,
        select(User).where(User.agency_id == user.agency_id),
        User,
        paging,
        user_view,
    )


@router.get("/client-organisations", response_model=PageView[OrgView])
def organisations(
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    return page(
        db,
        select(ClientOrg).where(ClientOrg.agency_id == user.agency_id),
        ClientOrg,
        paging,
        record,
    )


@router.post("/client-organisations", status_code=201, response_model=OrgView)
def create_organisation(
    data: OrgCreate, db: Session = Depends(get_db), user: User = Depends(admin)
):
    org = ClientOrg(name=data.name, agency_id=user.agency_id)
    db.add(org)
    db.commit()
    return record(org)


def owned_project(db, project_id, user):
    db.scalar(select(Agency).where(Agency.id == user.agency_id).with_for_update())
    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if not project or project.agency_id != user.agency_id:
        raise HTTPException(404, "Project not found.")
    return project


@router.get("/projects/{project_id}/members", response_model=PageView[UserView])
def members(
    project_id: int,
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    owned_project(db, project_id, user)
    return page(
        db,
        select(User).join(Membership).where(Membership.project_id == project_id),
        User,
        paging,
        user_view,
    )


@router.put("/projects/{project_id}/members/{user_id}", status_code=204)
def add_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    project = owned_project(db, project_id, user)
    member = db.get(User, user_id)
    if (
        not member
        or member.agency_id != user.agency_id
        or member.role == "admin"
        or (member.role == "client" and member.client_org_id != project.client_org_id)
    ):
        raise HTTPException(
            400, "Choose a recruiter or a client from this project’s organisation."
        )
    if not db.get(Membership, (project_id, user_id)):
        audit(db, user, "membership_added", f"{project_id}/{user_id}")
        db.add(Membership(project_id=project_id, user_id=user_id))
        db.commit()


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    owned_project(db, project_id, user)
    membership = db.get(Membership, (project_id, user_id))
    if membership:
        db.delete(membership)
    audit(db, user, "membership_removed", f"{project_id}/{user_id}")
    # Revoke pending grants too, so an old link cannot silently restore access.
    member = db.get(User, user_id)
    if member:
        for invite in db.scalars(
            select(Invitation).where(
                Invitation.project_id == project_id,
                Invitation.email == member.email,
                Invitation.used_at.is_(None),
            )
        ):
            invite.revoked = True
    db.commit()


@router.post("/invitations", status_code=201, response_model=InviteLink)
def create_invite(
    data: InviteCreate, db: Session = Depends(get_db), user: User = Depends(admin)
):
    db.scalar(select(Agency).where(Agency.id == user.agency_id).with_for_update())
    project = owned_project(db, data.project_id, user) if data.project_id else None
    if data.role == "client":
        if not project:
            raise HTTPException(422, "Client invitations must include a project.")
        org_id = project.client_org_id
        if data.client_org_id and data.client_org_id != org_id:
            raise HTTPException(400, "Client organisation does not match this project.")
    else:
        org_id = None
        if data.client_org_id:
            raise HTTPException(400, "Recruiters belong to the agency.")
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing and (
        existing.role != data.role
        or existing.agency_id != user.agency_id
        or existing.client_org_id != org_id
    ):
        raise HTTPException(
            409, "That email already has a different role or organisation."
        )
    token = secrets.token_urlsafe(32)
    invite = Invitation(
        token_hash=digest(token),
        email=data.email,
        role=data.role,
        agency_id=user.agency_id,
        client_org_id=org_id,
        project_id=data.project_id,
        expires_at=now() + timedelta(days=7),
    )
    db.add(invite)
    db.flush()
    queue_invitation(
        db, data.email, f"{get_settings().frontend_url}/invite#token={token}"
    )
    audit(db, user, "invitation_created", invite.id)
    db.commit()
    return {
        "id": invite.id,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "url": f"{get_settings().frontend_url}/invite#token={token}",
    }


@router.get("/invitations", response_model=PageView[InviteView])
def invites(
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    return page(
        db,
        select(Invitation).where(Invitation.agency_id == user.agency_id),
        Invitation,
        paging,
        lambda i: {
            key: getattr(i, key)
            for key in (
                "id",
                "email",
                "role",
                "project_id",
                "expires_at",
                "used_at",
                "revoked",
            )
        },
        descending=True,
    )


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invite(
    invitation_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    invite = db.get(Invitation, invitation_id)
    if not invite or invite.agency_id != user.agency_id:
        raise HTTPException(404, "Invitation not found.")
    invite = lock_invite(db, invite.id)
    invite.revoked = True
    audit(db, user, "invitation_revoked", invite.id)
    db.commit()


@router.put("/users/{user_id}/status")
def account_status(
    user_id: int,
    data: AccountStatus,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    db.scalar(select(Agency).where(Agency.id == user.agency_id).with_for_update())
    target = db.scalar(
        select(User)
        .where(User.id == user_id, User.agency_id == user.agency_id)
        .with_for_update()
    )
    if not target:
        raise HTTPException(404, "User not found.")
    if not data.active and target.role == "admin" and target.active:
        count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.agency_id == user.agency_id,
                User.role == "admin",
                User.active.is_(True),
            )
        )
        if count <= 1:
            raise HTTPException(
                409, "The last active administrator cannot be suspended."
            )
    target.active = data.active
    revoke_sessions(db, target.id)
    audit(db, user, "account_status_changed", target.id)
    db.commit()
    return user_view(target)


@router.get("/agency/policy")
def policy(db: Session = Depends(get_db), user: User = Depends(admin)):
    return {"retention_days": db.get(Agency, user.agency_id).retention_days}


@router.put("/agency/policy")
def set_policy(
    data: RetentionPolicy, db: Session = Depends(get_db), user: User = Depends(admin)
):
    db.get(Agency, user.agency_id).retention_days = data.retention_days
    audit(db, user, "retention_policy_changed")
    db.commit()
    return data


@router.get("/audit")
def audit_events(
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    return page(
        db,
        select(AuditEvent).where(AuditEvent.agency_id == user.agency_id),
        AuditEvent,
        paging,
        record,
        descending=True,
    )


@router.post("/projects/{project_id}/archive")
def archive(
    project_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    project = owned_project(db, project_id, user)
    project.archived_at = project.archived_at or now()
    project.version += 1
    audit(db, user, "project_archived", project_id)
    db.commit()
    return record(project)


def project_contents(db, project):
    candidate_ids = select(Candidate.id).where(Candidate.project_id == project.id)
    post_ids = select(Post.id).where(Post.project_id == project.id)
    queries = [
        (Feedback, Feedback.candidate_id.in_(candidate_ids)),
        (Comment, Comment.post_id.in_(post_ids)),
    ]
    queries += [
        (model, model.project_id == project.id)
        for model in (
            Candidate,
            Document,
            Post,
            Message,
            Milestone,
            ReadMarker,
            Membership,
            Invitation,
            Submission,
        )
    ]
    return queries


@router.get("/projects/{project_id}/deletion-preview")
def deletion_preview(
    project_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    project = owned_project(db, project_id, user)
    days = db.get(Agency, user.agency_id).retention_days
    return {
        "title": project.title,
        "version": project.version,
        "archived_at": project.archived_at,
        "review_due": bool(
            days and project.archived_at and (now() - project.archived_at).days >= days
        ),
        "counts": {
            model.__tablename__: db.scalar(
                select(func.count()).select_from(model).where(condition)
            )
            for model, condition in project_contents(db, project)
        },
    }


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    # Stream bounded batches rather than materialising the whole search in memory.
    from fastapi.responses import StreamingResponse
    from fastapi.encoders import jsonable_encoder
    import json

    project = owned_project(db, project_id, user)
    audit(db, user, "project_exported", project_id)
    db.commit()

    def stream():
        yield (
            json.dumps({"type": "project", "data": jsonable_encoder(record(project))})
            + "\n"
        )
        for model, condition in project_contents(db, project):
            if model in (Submission, Invitation, ReadMarker, Membership):
                continue
            for row in db.scalars(
                select(model).where(condition).execution_options(yield_per=100)
            ):
                yield (
                    json.dumps(
                        {
                            "type": model.__tablename__,
                            "data": jsonable_encoder(record(row)),
                        }
                    )
                    + "\n"
                )

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="search-{project_id}.ndjson"'
        },
    )


@router.delete("/projects/{project_id}", status_code=204)
def purge_project(
    project_id: int,
    data: DeleteProject,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    project = owned_project(db, project_id, user)
    if (
        not project.archived_at
        or data.confirmation != project.title
        or data.version != project.version
    ):
        raise HTTPException(
            409,
            "Archive the project, review its latest preview and type its exact title to delete.",
        )
    for model, condition in project_contents(db, project):
        db.execute(
            delete(model).where(condition),
            execution_options={"synchronize_session": False},
        )
    audit(db, user, "project_deleted", project_id)
    db.delete(project)
    db.commit()


@router.post("/users/{user_id}/promote-admin")
def promote_admin(
    user_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    db.scalar(select(Agency).where(Agency.id == user.agency_id).with_for_update())
    target = db.scalar(
        select(User)
        .where(User.id == user_id, User.agency_id == user.agency_id)
        .with_for_update()
    )
    if (
        not target
        or target.role != "recruiter"
        or not target.active
        or not target.email_verified
    ):
        raise HTTPException(400, "Choose an active, verified recruiter in your agency.")
    target.role = "admin"
    revoke_sessions(db, target.id)
    audit(db, user, "administrator_promoted", target.id)
    db.commit()
    return user_view(target)
