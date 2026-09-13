"""Small relational models. Project IDs are the boundary for collaboration data."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from .database import Base


def now():
    return datetime.now(timezone.utc)


class Agency(Base):
    __tablename__ = 'agencies'
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)


class ClientOrg(Base):
    __tablename__ = 'client_organisations'
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey('agencies.id'), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    __table_args__ = (UniqueConstraint('agency_id', 'name'),)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey('agencies.id'), nullable=False, index=True)
    client_org_id = Column(ForeignKey('client_organisations.id'))
    email = Column(String(254), unique=True, nullable=False)
    name = Column(String(160), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'recruiter', 'client')"),
        CheckConstraint("(role = 'client' AND client_org_id IS NOT NULL) OR (role != 'client' AND client_org_id IS NULL)"),
    )


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    agency_id = Column(ForeignKey('agencies.id'), nullable=False, index=True)
    client_org_id = Column(ForeignKey('client_organisations.id'), nullable=False)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default='')
    ideal_profile = Column(Text, nullable=False, default='')
    agreement_terms = Column(Text, nullable=False, default='')
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date'),)


class Membership(Base):
    __tablename__ = 'memberships'
    project_id = Column(ForeignKey('projects.id'), primary_key=True)
    user_id = Column(ForeignKey('users.id'), primary_key=True)


class Invitation(Base):
    __tablename__ = 'invitations'
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    agency_id = Column(ForeignKey('agencies.id'), nullable=False)
    client_org_id = Column(ForeignKey('client_organisations.id'))
    project_id = Column(ForeignKey('projects.id'))
    email = Column(String(254), nullable=False)
    role = Column(String(20), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    revoked = Column(Boolean, nullable=False, default=False)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id = Column(String(36), primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    refresh_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)


class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    current_role = Column(String(160), nullable=False, default='')
    company = Column(String(160), nullable=False, default='')
    summary = Column(Text, nullable=False, default='')
    cv_url = Column(Text)
    stage = Column(String(20), nullable=False, default='Identified')
    client_visible = Column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("stage IN ('Identified','Shortlisted','Interviewing','Offered','Hired','Rejected')"),)


class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(ForeignKey('candidates.id'), nullable=False, index=True)
    author_id = Column(ForeignKey('users.id'), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    url = Column(Text, nullable=False)


class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    author_id = Column(ForeignKey('users.id'), nullable=False)
    body = Column(Text, nullable=False)
    attachment_url = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True)
    post_id = Column(ForeignKey('posts.id'), nullable=False, index=True)
    author_id = Column(ForeignKey('users.id'), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    author_id = Column(ForeignKey('users.id'), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class ReadMarker(Base):
    __tablename__ = 'read_markers'
    project_id = Column(ForeignKey('projects.id'), primary_key=True)
    user_id = Column(ForeignKey('users.id'), primary_key=True)
    last_message_id = Column(Integer, nullable=False, default=0)


class Milestone(Base):
    __tablename__ = 'milestones'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default='')
    target_date = Column(Date, nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
