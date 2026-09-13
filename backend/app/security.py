"""JWTs identify a database session; memberships are always checked live."""
import hashlib
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import timedelta
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .models import AuthSession, User, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash('not-a-real-user-password')
bearer = HTTPBearer(auto_error=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode_token(user_id, session_id, kind, expires):
    return jwt.encode({'sub': str(user_id), 'sid': session_id, 'type': kind, 'exp': expires, 'iat': now(), 'jti': secrets.token_hex(16)}, get_settings().jwt_secret, algorithm='HS256')


def decode_token(token, kind, allow_expired=False):
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=['HS256'], options={'verify_exp': not allow_expired, 'require': ['sub', 'sid', 'type', 'exp', 'iat', 'jti']})
        if data['type'] != kind:
            raise ValueError()
        int(data['sub'])
        return data
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(401, 'Your session has expired. Please sign in again.')


def token_pair(db, user, session=None):
    expiry = now() + timedelta(days=7)
    session = session or AuthSession(id=str(uuid.uuid4()), user_id=user.id)
    refresh = encode_token(user.id, session.id, 'refresh', expiry)
    session.refresh_hash, session.expires_at = digest(refresh), expiry
    db.add(session)
    db.flush()
    return {'access_token': encode_token(user.id, session.id, 'access', now() + timedelta(minutes=15)), 'refresh_token': refresh, 'token_type': 'bearer'}


def resolve_user(db, credentials):
    data = decode_token(credentials.credentials, 'access')
    session = db.get(AuthSession, data['sid'])
    if not session or session.revoked or session.expires_at <= now() or session.user_id != int(data['sub']):
        raise HTTPException(401, 'Please sign in again.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Please sign in again.')
    return user


def current_user(db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, 'Please sign in.')
    return resolve_user(db, credentials)


def admin(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Agency administrator access is required.')
    return user


class RateLimiter:
    """Single-process development limiter. No Redis or background service required."""
    def __init__(self):
        self.events = {}
        self.lock = threading.Lock()

    def check(self, request: Request):
        key = request.client.host if request.client else 'unknown'
        cutoff = time.monotonic() - 60
        with self.lock:
            for old_key in list(self.events):
                q = self.events[old_key]
                while q and q[0] <= cutoff:
                    q.popleft()
                if not q:
                    del self.events[old_key]
            q = self.events.setdefault(key, deque())
            if len(q) >= get_settings().auth_rate_limit:
                raise HTTPException(429, 'Too many attempts. Try again in a minute.', headers={'Retry-After': '60'})
            q.append(time.monotonic())


limiter = RateLimiter()
