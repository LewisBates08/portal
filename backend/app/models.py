"""Small relational models. Project IDs are the boundary for collaboration data."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    JSON,
)
from .database import Base


def now():
    return datetime.now(timezone.utc)


class Agency(Base):
    __tablename__ = "agencies"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    retention_days = Column(Integer)


class ClientOrg(Base):
    __tablename__ = "client_organisations"
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey("agencies.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    __table_args__ = (UniqueConstraint("agency_id", "name"),)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey("agencies.id"), nullable=False, index=True)
    client_org_id = Column(ForeignKey("client_organisations.id"))
    email = Column(String(254), unique=True, nullable=False)
    name = Column(String(160), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    email_verified = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    mfa_secret = Column(Text)
    mfa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    mfa_last_step = Column(Integer, nullable=False, default=0, server_default="0")
    recovery_hashes = Column(JSON, nullable=False, default=list, server_default="[]")
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'recruiter', 'client')"),
        CheckConstraint(
            "(role = 'client' AND client_org_id IS NOT NULL) OR (role != 'client' AND client_org_id IS NULL)"
        ),
    )


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey("agencies.id"), nullable=False, index=True)
    client_org_id = Column(ForeignKey("client_organisations.id"), nullable=False)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default="")
    ideal_profile = Column(Text, nullable=False, default="")
    agreement_terms = Column(Text, nullable=False, default="")
    start_date = Column(Date)
    end_date = Column(Date)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    archived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date"
        ),
    )


class Membership(Base):
    __tablename__ = "memberships"
    project_id = Column(ForeignKey("projects.id"), primary_key=True)
    user_id = Column(ForeignKey("users.id"), primary_key=True, index=True)


class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    agency_id = Column(ForeignKey("agencies.id"), nullable=False)
    client_org_id = Column(ForeignKey("client_organisations.id"))
    project_id = Column(ForeignKey("projects.id"))
    email = Column(String(254), nullable=False)
    role = Column(String(20), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    revoked = Column(Boolean, nullable=False, default=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(String(36), primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    refresh_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    current_role = Column(String(160), nullable=False, default="")
    company = Column(String(160), nullable=False, default="")
    summary = Column(Text, nullable=False, default="")
    cv_url = Column(Text)
    stage = Column(String(20), nullable=False, default="Identified")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    client_visible = Column(Boolean, nullable=False, default=False)
    __table_args__ = (
        CheckConstraint(
            "stage IN ('Identified','Shortlisted','Interviewing','Offered','Hired','Rejected')"
        ),
    )


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True)
    candidate_id = Column(ForeignKey("candidates.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    url = Column(Text, nullable=False)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    attachment_url = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(ForeignKey("posts.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class ReadMarker(Base):
    __tablename__ = "read_markers"
    project_id = Column(ForeignKey("projects.id"), primary_key=True)
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    last_message_id = Column(Integer, nullable=False, default=0)


class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default="")
    target_date = Column(Date, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    completed = Column(Boolean, nullable=False, default=False)


class WebSession(Base):
    __tablename__ = "web_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey("users.id"), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    idle_expires_at = Column(DateTime(timezone=True), nullable=False)
    mfa_complete = Column(Boolean, nullable=False, default=False)
    delivered = Column(JSON, nullable=False, default=dict)


class EmailAction(Base):
    __tablename__ = "email_actions"
    token_hash = Column(String(64), primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class MailOutbox(Base):
    __tablename__ = "mail_outbox"
    id = Column(Integer, primary_key=True)
    recipient = Column(String(254), nullable=False)
    content = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(
        DateTime(timezone=True), nullable=False, default=now, index=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key = Column(String(64), primary_key=True)
    count = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    agency_id = Column(Integer, nullable=False, index=True)
    actor_id = Column(Integer)
    action = Column(String(80), nullable=False)
    resource = Column(String(200), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=now, index=True
    )


class Submission(Base):
    __tablename__ = "submissions"
    key = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    project_id = Column(ForeignKey("projects.id"), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False)
    result = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=now, index=True
    )


for model in (Candidate, Document, Post, Message):
    Index(f"ix_{model.__tablename__}_project_id_id", model.project_id, model.id)
Index(
    "ix_milestones_project_date_id",
    Milestone.project_id,
    Milestone.target_date,
    Milestone.id,
)
Index("ix_invitations_agency_id_id", Invitation.agency_id, Invitation.id)
Index("ix_feedback_candidate_id_id", Feedback.candidate_id, Feedback.id)
Index("ix_comments_post_id_id", Comment.post_id, Comment.id)
