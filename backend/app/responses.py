"""Explicit response contracts keep secret columns out of API responses."""

from datetime import datetime
from pydantic import BaseModel
from .schemas import CandidateData, DocumentData, MilestoneData, ProjectData, Role


class UserView(BaseModel):
    id: int
    name: str
    email: str
    role: Role
    agency_id: int
    client_org_id: int | None
    active: bool
    email_verified: bool
    mfa_enabled: bool


class InviteInfo(BaseModel):
    email: str
    role: Role
    existing_user: bool


class InviteLink(BaseModel):
    id: int
    email: str
    expires_at: datetime
    url: str


class InviteView(BaseModel):
    id: int
    email: str
    role: Role
    project_id: int | None
    expires_at: datetime
    used_at: datetime | None
    revoked: bool


class OrgView(BaseModel):
    id: int
    agency_id: int
    name: str


class ProjectView(ProjectData):
    id: int
    agency_id: int
    client_org_id: int
    client_name: str
    archived_at: datetime | None = None
    unread_count: int
    created_at: datetime


class CandidateView(CandidateData):
    id: int
    project_id: int


class DocumentView(DocumentData):
    id: int
    project_id: int


class EntryView(BaseModel):
    id: int
    author_id: int
    author_name: str
    body: str
    created_at: datetime


class FeedbackView(EntryView):
    candidate_id: int


class CommentView(EntryView):
    post_id: int


class MessageView(EntryView):
    project_id: int


class PostView(EntryView):
    project_id: int
    attachment_url: str | None
    comments: list[CommentView] = []
    comment_count: int = 0


class MilestoneView(MilestoneData):
    id: int
    project_id: int


from typing import Generic, TypeVar

T = TypeVar("T")


class PageView(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: int | None
