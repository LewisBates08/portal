from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

Short = Annotated[str, Field(min_length=1, max_length=160)]
Body = Annotated[str, Field(min_length=1, max_length=10000)]
Role = Literal["admin", "recruiter", "client"]
Stage = Literal[
    "Identified", "Shortlisted", "Interviewing", "Offered", "Hired", "Rejected"
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def trim_text(cls, value, info):
        return (
            value.strip()
            if isinstance(value, str)
            and info.field_name not in ("password", "token", "refresh_token")
            else value
        )

    @field_validator("email", check_fields=False)
    @classmethod
    def normalise_email(cls, value):
        return str(value).lower()

    @field_validator("url", "cv_url", "attachment_url", check_fields=False)
    @classmethod
    def external_link(cls, value):
        if not value:
            return None
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Use a full https:// link without credentials.")
            _ = parsed.port
        except ValueError:
            raise ValueError("Use a valid https:// link without credentials.")
        return value


class Login(Input):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class Register(Login):
    name: Short
    agency_name: Short
    password: Annotated[str, Field(min_length=10, max_length=128)]


class InviteCreate(Input):
    email: EmailStr
    role: Literal["recruiter", "client"]
    project_id: int | None = None
    client_org_id: int | None = None


class InviteLookup(Input):
    token: str = Field(min_length=1, max_length=512)


class AcceptInvite(InviteLookup):
    name: Short | None = None
    password: Annotated[str, Field(min_length=10, max_length=128)] | None = None


class OrgCreate(Input):
    name: Short


class ProjectData(Input):
    version: int | None = Field(default=None, ge=1)
    title: Short
    description: str = Field(default="", max_length=10000)
    ideal_profile: str = Field(default="", max_length=10000)
    agreement_terms: str = Field(default="", max_length=10000)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date.")
        return self


class ProjectCreate(ProjectData):
    client_org_id: int


class CandidateData(Input):
    version: int | None = Field(default=None, ge=1)
    name: Short
    current_role: str = Field(default="", max_length=160)
    company: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=10000)
    cv_url: str | None = Field(default=None, max_length=2048)
    stage: Stage = "Identified"
    client_visible: bool = False


class TextData(Input):
    body: Body


class PostData(TextData):
    attachment_url: str | None = Field(default=None, max_length=2048)


class DocumentData(Input):
    title: Short
    url: Annotated[str, Field(min_length=1, max_length=2048)]


class MilestoneData(Input):
    version: int | None = Field(default=None, ge=1)
    title: Short
    description: str = Field(default="", max_length=10000)
    target_date: date
    completed: bool = False


class ReadData(Input):
    last_message_id: int = Field(ge=0)


class EmailRequest(Input):
    email: EmailStr


class ResetPassword(InviteLookup):
    password: Annotated[str, Field(min_length=10, max_length=128)]


class CodeInput(Input):
    code: str = Field(min_length=6, max_length=64)


class AccountStatus(Input):
    active: bool


class RetentionPolicy(Input):
    retention_days: int = Field(ge=1, le=3650)


class DeleteProject(Input):
    confirmation: str
    version: int = Field(ge=1)
