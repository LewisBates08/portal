import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .models import ClientOrg, Invitation, Membership, Project, User, now
from .schemas import InviteCreate, OrgCreate
from .security import admin, digest
from .serializers import record, user_view

from .responses import UserView, OrgView, InviteLink, InviteView

router = APIRouter(tags=['Administration'], dependencies=[Depends(admin)])


@router.get('/users', response_model=list[UserView])
def users(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [user_view(u) for u in db.scalars(select(User).where(User.agency_id == user.agency_id).order_by(User.name))]


@router.get('/client-organisations', response_model=list[OrgView])
def organisations(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [record(o) for o in db.scalars(select(ClientOrg).where(ClientOrg.agency_id == user.agency_id).order_by(ClientOrg.name))]


@router.post('/client-organisations', status_code=201, response_model=OrgView)
def create_organisation(data: OrgCreate, db: Session = Depends(get_db), user: User = Depends(admin)):
    org = ClientOrg(name=data.name, agency_id=user.agency_id)
    db.add(org)
    db.commit()
    return record(org)


def owned_project(db, project_id, user):
    project = db.get(Project, project_id)
    if not project or project.agency_id != user.agency_id:
        raise HTTPException(404, 'Project not found.')
    return project


@router.get('/projects/{project_id}/members', response_model=list[UserView])
def members(project_id: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    owned_project(db, project_id, user)
    return [user_view(u) for u in db.scalars(select(User).join(Membership).where(Membership.project_id == project_id).order_by(User.name))]


@router.put('/projects/{project_id}/members/{user_id}', status_code=204)
def add_member(project_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    project = owned_project(db, project_id, user)
    member = db.get(User, user_id)
    if not member or member.agency_id != user.agency_id or member.role == 'admin' or (member.role == 'client' and member.client_org_id != project.client_org_id):
        raise HTTPException(400, 'Choose a recruiter or a client from this project’s organisation.')
    if not db.get(Membership, (project_id, user_id)):
        db.add(Membership(project_id=project_id, user_id=user_id))
        db.commit()


@router.delete('/projects/{project_id}/members/{user_id}', status_code=204)
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    owned_project(db, project_id, user)
    membership = db.get(Membership, (project_id, user_id))
    if membership:
        db.delete(membership)
    # Revoke pending grants too, so an old link cannot silently restore access.
    member = db.get(User, user_id)
    if member:
        for invite in db.scalars(select(Invitation).where(Invitation.project_id == project_id, Invitation.email == member.email, Invitation.used_at.is_(None))):
            invite.revoked = True
    db.commit()


@router.post('/invitations', status_code=201, response_model=InviteLink)
def create_invite(data: InviteCreate, db: Session = Depends(get_db), user: User = Depends(admin)):
    project = owned_project(db, data.project_id, user) if data.project_id else None
    if data.role == 'client':
        if not project:
            raise HTTPException(422, 'Client invitations must include a project.')
        org_id = project.client_org_id
        if data.client_org_id and data.client_org_id != org_id:
            raise HTTPException(400, 'Client organisation does not match this project.')
    else:
        org_id = None
        if data.client_org_id:
            raise HTTPException(400, 'Recruiters belong to the agency.')
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing and (existing.role != data.role or existing.agency_id != user.agency_id or existing.client_org_id != org_id):
        raise HTTPException(409, 'That email already has a different role or organisation.')
    token = secrets.token_urlsafe(32)
    invite = Invitation(token_hash=digest(token), email=data.email, role=data.role, agency_id=user.agency_id, client_org_id=org_id, project_id=data.project_id, expires_at=now() + timedelta(days=7))
    db.add(invite)
    db.commit()
    return {'id': invite.id, 'email': invite.email, 'expires_at': invite.expires_at, 'url': f'{get_settings().frontend_url}/invite#token={token}'}


@router.get('/invitations', response_model=list[InviteView])
def invites(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [{key: getattr(i, key) for key in ('id', 'email', 'role', 'project_id', 'expires_at', 'used_at', 'revoked')} for i in db.scalars(select(Invitation).where(Invitation.agency_id == user.agency_id).order_by(Invitation.id.desc()))]


@router.delete('/invitations/{invitation_id}', status_code=204)
def revoke_invite(invitation_id: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    invite = db.get(Invitation, invitation_id)
    if not invite or invite.agency_id != user.agency_id:
        raise HTTPException(404, 'Invitation not found.')
    invite.revoked = True
    db.commit()
