import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import Agency, AuthSession, Invitation, Membership, User, now
from .schemas import AcceptInvite, InviteLookup, Login, Refresh, Register
from .security import DUMMY_HASH, bearer, current_user, decode_token, digest, limiter, passwords, resolve_user, token_pair
from .serializers import user_view

from .responses import LoginView, TokenView, UserView, InviteInfo

router = APIRouter(prefix='/auth', tags=['Authentication'])


@router.post('/register', status_code=201, response_model=LoginView)
def register(data: Register, request: Request, db: Session = Depends(get_db)):
    limiter.check(request)
    duplicate = 'An account with this email already exists. Please sign in instead.'
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise HTTPException(409, duplicate)

    # Registration always creates a separate agency. Names and email domains
    # never grant membership in an existing workspace, and roles are server-set.
    try:
        agency = Agency(name=data.agency_name)
        db.add(agency)
        db.flush()
        user = User(
            name=data.name, email=data.email,
            password_hash=passwords.hash(data.password),
            role='admin', agency_id=agency.id, client_org_id=None,
        )
        db.add(user)
        db.flush()
        result = token_pair(db, user)
        db.commit()
    except IntegrityError:
        # Also covers simultaneous registrations with the same email. Roll back
        # the agency and user together so a failed signup leaves no orphan agency.
        db.rollback()
        raise HTTPException(409, duplicate)
    return {**result, 'user': user_view(user)}


@router.post('/login', response_model=LoginView)
def login(data: Login, request: Request, db: Session = Depends(get_db)):
    limiter.check(request)
    user = db.scalar(select(User).where(User.email == data.email))
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, 'Email or password is incorrect.')
    result = token_pair(db, user)
    db.commit()
    return {**result, 'user': user_view(user)}


@router.get('/me', response_model=UserView)
def me(user: User = Depends(current_user)):
    return user_view(user)


@router.post('/refresh', response_model=TokenView)
def refresh(data: Refresh, request: Request, db: Session = Depends(get_db)):
    limiter.check(request)
    claims = decode_token(data.refresh_token, 'refresh')
    session = db.scalar(select(AuthSession).where(AuthSession.id == claims['sid']).with_for_update())
    if not session or session.revoked or session.expires_at <= now() or session.user_id != int(claims['sub']):
        raise HTTPException(401, 'Please sign in again.')
    if not secrets.compare_digest(session.refresh_hash, digest(data.refresh_token)):
        # A consumed refresh token cannot be reused; revoke the entire session.
        session.revoked = True
        db.commit()
        raise HTTPException(401, 'Session revoked. Please sign in again.')
    result = token_pair(db, db.get(User, session.user_id), session)
    db.commit()
    return result


@router.post('/logout', status_code=204)
def logout(data: Refresh, db: Session = Depends(get_db)):
    claims = decode_token(data.refresh_token, 'refresh', allow_expired=True)
    session = db.get(AuthSession, claims['sid'])
    if session and session.user_id == int(claims['sub']):
        session.revoked = True
        db.commit()


def get_invite(db, token, lock=False):
    query = select(Invitation).where(Invitation.token_hash == digest(token))
    invite = db.scalar(query.with_for_update() if lock else query)
    if not invite or invite.revoked or invite.used_at or invite.expires_at <= now():
        raise HTTPException(400, 'This invitation has expired, was revoked or has already been used.')
    return invite


@router.post('/invitation', response_model=InviteInfo)
def invitation(data: InviteLookup, request: Request, db: Session = Depends(get_db)):
    limiter.check(request)
    invite = get_invite(db, data.token)
    return {'email': invite.email, 'role': invite.role, 'existing_user': db.scalar(select(User.id).where(User.email == invite.email)) is not None}


@router.post('/accept-invitation', response_model=LoginView)
def accept(data: AcceptInvite, request: Request, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    limiter.check(request)
    invite = get_invite(db, data.token, lock=True)
    user = db.scalar(select(User).where(User.email == invite.email))
    if user:
        if not credentials or resolve_user(db, credentials).id != user.id:
            raise HTTPException(403, 'Sign in with the invited email address to accept this invitation.')
        if user.role != invite.role or user.agency_id != invite.agency_id or user.client_org_id != invite.client_org_id:
            raise HTTPException(409, 'This invitation does not match your existing role or organisation.')
    else:
        if credentials:
            raise HTTPException(403, 'Sign out before creating the invited account.')
        if not data.name or not data.password:
            raise HTTPException(422, 'Enter your name and a password of at least 10 characters.')
        user = User(email=invite.email, name=data.name, password_hash=passwords.hash(data.password), role=invite.role, agency_id=invite.agency_id, client_org_id=invite.client_org_id)
        db.add(user)
        db.flush()
    if invite.project_id and not db.get(Membership, (invite.project_id, user.id)):
        db.add(Membership(project_id=invite.project_id, user_id=user.id))
    invite.used_at = now()
    result = token_pair(db, user)
    db.commit()
    return {**result, 'user': user_view(user)}
