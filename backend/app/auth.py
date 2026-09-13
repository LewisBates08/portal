import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, text, func
from sqlalchemy.orm import Session
import pyotp
from .database import get_db
from .models import Agency, EmailAction, Invitation, Membership, Project, User, now
from .schemas import (
    AcceptInvite,
    InviteLookup,
    Login,
    Register,
    EmailRequest,
    ResetPassword,
    CodeInput,
)
from .security import (
    DUMMY_HASH,
    signed_in_user,
    digest,
    auth_limit,
    hash_password,
    verify_password,
    issue_session,
    session_row,
    csrf_value,
    revoke_sessions,
    audit,
)
from .config import get_settings
from .serializers import user_view
from .mail import queue_action
from .mfa import encrypt, validate_code

router = APIRouter(prefix="/auth", tags=["Authentication"])
GENERIC = {
    "message": "If this address is eligible, an email will arrive shortly. Check your inbox."
}


def email_lock(db, email):
    # Stable across processes. Serializes creation/verification for one email.
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(digest(email)[:15], 16)}
    )


def account_result(db, request, user):
    session = session_row(request, db)
    return {
        "user": user_view(user),
        "mfa_required": user.role == "admin" and not session.mfa_complete,
        "mfa_setup": user.role == "admin" and not user.mfa_enabled,
    }


@router.get("/csrf")
def csrf(request: Request, response: Response, db: Session = Depends(get_db)):
    auth_limit(request, db)
    if not session_row(request, db, False):
        issue_session(db, request, response)
        # The raw token exists only in Set-Cookie; recover it from the response cookie.
        from http.cookies import SimpleCookie

        cookie = SimpleCookie(response.headers["set-cookie"])
        token = cookie[get_settings().cookie_name].value
        db.commit()
    else:
        token = request.cookies[get_settings().cookie_name]
    return {"csrf_token": csrf_value(token)}


@router.post("/register", status_code=202)
def register(data: Register, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db, data.email)
    # Do the password work for both existing and new addresses.
    encoded = hash_password(data.password)
    email_lock(db, data.email)
    if not db.scalar(select(User.id).where(User.email == data.email)):
        queue_action(
            db,
            data.email,
            "verify",
            {
                "name": data.name,
                "agency_name": data.agency_name,
                "password_hash": encoded,
            },
            1440,
        )
    db.commit()
    return GENERIC


@router.post("/login")
def login(
    data: Login, request: Request, response: Response, db: Session = Depends(get_db)
):
    auth_limit(request, db, data.email)
    user = db.scalar(select(User).where(User.email == data.email))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active or not user.email_verified:
        raise HTTPException(
            401, "Email or password is incorrect, or verification is required."
        )
    issue_session(db, request, response, user, user.role != "admin")
    audit(db, user, "login")
    db.commit()
    return {
        "user": user_view(user),
        "mfa_required": user.role == "admin",
        "mfa_setup": not user.mfa_enabled and user.role == "admin",
    }


@router.get("/me")
def me(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(signed_in_user),
):
    return account_result(db, request, user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session = session_row(request, db, False)
    if session:
        if session.user_id:
            audit(db, db.get(User, session.user_id), "logout")
        db.delete(session)
        db.commit()
    response.delete_cookie(
        get_settings().cookie_name,
        path="/",
        secure=get_settings().production,
        httponly=True,
        samesite="lax",
    )


@router.post("/forgot-password", status_code=202)
def forgot(data: EmailRequest, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db, data.email)
    user = db.scalar(
        select(User).where(
            User.email == data.email,
            User.active.is_(True),
            User.email_verified.is_(True),
        )
    )
    if user:
        queue_action(db, data.email, "reset", {}, 30)
    db.commit()
    return GENERIC


@router.post("/resend-verification", status_code=202)
def resend(data: EmailRequest, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db, data.email)
    user = db.scalar(
        select(User).where(User.email == data.email, User.active.is_(True))
    )
    if user and not user.email_verified:
        queue_action(db, data.email, "verify", {"user_id": user.id}, 1440)
    db.commit()
    return GENERIC


def action(db, token, kind):
    row = db.scalar(
        select(EmailAction)
        .where(EmailAction.token_hash == digest(token))
        .with_for_update()
    )
    if not row or row.kind != kind or row.expires_at <= now():
        raise HTTPException(400, "This link has expired or has already been used.")
    return row


@router.post("/reset-password", status_code=204)
def reset(data: ResetPassword, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db)
    preview = db.get(EmailAction, digest(data.token))
    if not preview:
        raise HTTPException(400, "This link has expired or has already been used.")
    email_lock(db, preview.email)
    row = action(db, data.token, "reset")
    user = db.scalar(
        select(User)
        .where(User.email == row.email, User.active.is_(True))
        .with_for_update()
    )
    if not user:
        raise HTTPException(400, "This link is no longer valid.")
    user.password_hash = hash_password(data.password)
    revoke_sessions(db, user.id)
    db.execute(
        delete(EmailAction).where(
            EmailAction.email == row.email, EmailAction.kind == "reset"
        )
    )
    audit(db, user, "password_reset")
    db.commit()


@router.post("/verify-email", status_code=204)
def verify_email(data: InviteLookup, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db)
    # Acquire the email lock before row locks to avoid simultaneous-token deadlocks.
    preview = db.get(EmailAction, digest(data.token))
    if not preview:
        raise HTTPException(400, "This link has expired or has already been used.")
    email_lock(db, preview.email)
    row = action(db, data.token, "verify")
    user = db.scalar(select(User).where(User.email == row.email))
    payload = row.payload
    if "invitation_id" in payload:
        invite = lock_invite(db, payload["invitation_id"])
        if user:
            raise HTTPException(
                409, "Account now exists. Sign in and accept the original invitation."
            )
        ensure_user_quota(db, invite.agency_id)
        user = User(
            email=row.email,
            name=payload["name"],
            password_hash=payload["password_hash"],
            agency_id=invite.agency_id,
            client_org_id=invite.client_org_id,
            role=invite.role,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        grant_invite(db, invite, user)
    elif "agency_name" in payload:
        if user:
            raise HTTPException(
                409, "Account already exists. Sign in or reset its password."
            )
        agency = Agency(name=payload["agency_name"])
        db.add(agency)
        db.flush()
        user = User(
            email=row.email,
            name=payload["name"],
            password_hash=payload["password_hash"],
            agency_id=agency.id,
            role="admin",
            email_verified=True,
        )
        db.add(user)
        db.flush()
    elif user and user.id == payload.get("user_id") and user.active:
        user.email_verified = True
    else:
        raise HTTPException(400, "This verification is no longer valid.")
    db.execute(
        delete(EmailAction).where(
            EmailAction.email == row.email, EmailAction.kind == "verify"
        )
    )
    audit(db, user, "email_verified")
    db.commit()


def ensure_user_quota(db, agency_id):
    db.scalar(select(Agency).where(Agency.id == agency_id).with_for_update())
    if (
        db.scalar(
            select(func.count()).select_from(User).where(User.agency_id == agency_id)
        )
        >= get_settings().max_users
    ):
        raise HTTPException(409, "Agency user limit reached. Contact the operator.")


def check_invite(invite):
    if not invite or invite.revoked or invite.used_at or invite.expires_at <= now():
        raise HTTPException(
            400, "This invitation has expired, was revoked or has already been used."
        )
    return invite


def lock_invite(db, invite_id):
    preview = db.get(Invitation, invite_id)
    if not preview:
        return check_invite(None)
    # Agency then project then invitation is the shared administration lock order.
    db.scalar(select(Agency).where(Agency.id == preview.agency_id).with_for_update())
    if preview.project_id:
        db.scalar(
            select(Project).where(Project.id == preview.project_id).with_for_update()
        )
    return check_invite(
        db.scalar(
            select(Invitation)
            .where(Invitation.id == invite_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def get_invite(db, token):
    return check_invite(
        db.scalar(select(Invitation).where(Invitation.token_hash == digest(token)))
    )


def grant_invite(db, invite, user):
    if (
        invite.role != user.role
        or invite.agency_id != user.agency_id
        or invite.client_org_id != user.client_org_id
    ):
        raise HTTPException(409, "Invitation does not match your role or organisation.")
    if invite.project_id and not db.get(Membership, (invite.project_id, user.id)):
        db.add(Membership(project_id=invite.project_id, user_id=user.id))
    invite.used_at = now()
    audit(db, user, "invitation_accepted", invite.id)


@router.post("/invitation")
def invitation(data: InviteLookup, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db)
    invite = get_invite(db, data.token)
    return {
        "email": invite.email,
        "role": invite.role,
        "existing_user": db.scalar(select(User.id).where(User.email == invite.email))
        is not None,
    }


@router.post("/accept-invitation")
def accept(data: AcceptInvite, request: Request, db: Session = Depends(get_db)):
    auth_limit(request, db)
    preview = get_invite(db, data.token)
    email_lock(db, preview.email)
    invite = lock_invite(db, preview.id)
    user = db.scalar(select(User).where(User.email == invite.email))
    session = session_row(request, db)
    if user:
        if session.user_id != user.id or not user.active or not user.email_verified:
            raise HTTPException(403, "Sign in with the verified invited email address.")
        grant_invite(db, invite, user)
        db.commit()
        return {"user": user_view(user)}
    if session.user_id:
        raise HTTPException(403, "Sign out before creating the invited account.")
    if not data.name or not data.password:
        raise HTTPException(
            422, "Enter your name and a password of at least 10 characters."
        )
    queue_action(
        db,
        invite.email,
        "verify",
        {
            "name": data.name,
            "password_hash": hash_password(data.password),
            "invitation_id": invite.id,
        },
        1440,
    )
    db.commit()
    return GENERIC


@router.post("/mfa/setup")
def mfa_setup(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(signed_in_user),
):
    auth_limit(request, db, user.email)
    db.refresh(user, with_for_update=True)
    if user.mfa_enabled:
        raise HTTPException(409, "Authenticator is already configured.")
    secret = pyotp.random_base32()
    user.mfa_secret = encrypt(secret)
    db.commit()
    return {
        "secret": secret,
        "uri": pyotp.TOTP(secret).provisioning_uri(
            user.email, issuer_name="Searchroom"
        ),
    }


@router.post("/mfa/verify")
def mfa_verify(
    data: CodeInput,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(signed_in_user),
):
    auth_limit(request, db, user.email)
    db.refresh(user, with_for_update=True)
    validate_code(user, data.code)
    recovery = []
    if not user.mfa_enabled:
        recovery = [secrets.token_hex(8) for _ in range(10)]
        user.recovery_hashes = [digest(code) for code in recovery]
        user.mfa_enabled = True
    issue_session(db, request, response, user, True)
    audit(db, user, "mfa_verified")
    db.commit()
    return {
        "user": user_view(user),
        "recovery_codes": recovery,
        "mfa_required": False,
        "mfa_setup": False,
    }
