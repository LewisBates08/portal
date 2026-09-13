from .responses import PageView
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .access import child, project_access, project_editor, visible_candidate
from .database import get_db
from .models import (
    Candidate,
    ClientOrg,
    Comment,
    Document,
    Feedback,
    Membership,
    Message,
    Milestone,
    Post,
    Project,
    ReadMarker,
    User,
)
from .schemas import (
    CandidateData,
    DocumentData,
    MilestoneData,
    PostData,
    ProjectCreate,
    ProjectData,
    ReadData,
    TextData,
)
from .security import admin, current_user, audit, session_row
from .config import get_settings
from .resources import (
    Paging,
    page,
    author_page,
    versioned,
    write_limit,
    lock_project,
    submission,
    require_retention,
)
from sqlalchemy.dialects.postgresql import insert
from .serializers import authored, project_view, record

from .responses import (
    ProjectView,
    CandidateView,
    FeedbackView,
    DocumentView,
    PostView,
    CommentView,
    MessageView,
    MilestoneView,
)

router = APIRouter(
    prefix="/projects", tags=["Projects"], dependencies=[Depends(write_limit)]
)


@router.get("", response_model=PageView[ProjectView])
def projects(
    paging: Paging = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = select(Project).where(Project.agency_id == user.agency_id)
    if user.role != "admin":
        query = query.join(Membership).where(Membership.user_id == user.id)
    return project_page(db, query, user, paging)


@router.post("", status_code=201, response_model=ProjectView)
def create_project(
    data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(admin)
):
    org = db.get(ClientOrg, data.client_org_id)
    if not org or org.agency_id != user.agency_id:
        raise HTTPException(400, "Choose a client organisation in your agency.")
    require_retention(db, user.agency_id)
    if (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.agency_id == user.agency_id, Project.archived_at.is_(None))
        )
        >= get_settings().max_projects
    ):
        raise HTTPException(
            409,
            "Active project limit reached. Archive a project or contact the operator.",
        )
    project = Project(**data.model_dump(exclude={"version"}), agency_id=user.agency_id)
    db.add(project)
    db.commit()
    return project_view(db, project, user)


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    accessible = select(Project.id).where(Project.agency_id == user.agency_id)
    if user.role != "admin":
        accessible = accessible.join(Membership).where(Membership.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(accessible.subquery()))
    unread = db.scalar(
        select(func.count())
        .select_from(Message)
        .outerjoin(
            ReadMarker,
            (ReadMarker.project_id == Message.project_id)
            & (ReadMarker.user_id == user.id),
        )
        .where(
            Message.project_id.in_(accessible),
            Message.author_id != user.id,
            Message.id > func.coalesce(ReadMarker.last_message_id, 0),
        )
    )
    return {"project_count": total, "unread_count": unread}


@router.get("/{project_id}", response_model=ProjectView)
def get_project(
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return project_view(db, project, user)


@router.put("/{project_id}", response_model=ProjectView)
def update_project(
    data: ProjectData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    versioned(db, project, data)
    audit(db, user, "project_updated", project.id)
    db.commit()
    return project_view(db, project, user)


@router.get("/{project_id}/candidates", response_model=PageView[CandidateView])
def candidates(
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = select(Candidate).where(Candidate.project_id == project.id)
    if user.role == "client":
        query = query.where(Candidate.client_visible.is_(True))
    return page(db, query, Candidate, paging, record)


@router.post("/{project_id}/candidates", status_code=201, response_model=CandidateView)
def create_candidate(
    data: CandidateData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    lock_project(db, project.id)
    require_retention(db, project.agency_id)
    if (
        db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(Candidate.project_id == project.id)
        )
        >= get_settings().max_candidates
    ):
        raise HTTPException(409, "Candidate limit reached. Contact the operator.")
    candidate = Candidate(**data.model_dump(exclude={"version"}), project_id=project.id)
    db.add(candidate)
    audit(db, user, "candidate_created", project.id)
    db.commit()
    return record(candidate)


@router.get("/{project_id}/candidates/{candidate_id}", response_model=CandidateView)
def get_candidate(
    candidate_id: int,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return record(visible_candidate(db, candidate_id, project.id, user))


@router.put("/{project_id}/candidates/{candidate_id}", response_model=CandidateView)
def update_candidate(
    candidate_id: int,
    data: CandidateData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    candidate = child(db, Candidate, candidate_id, project.id)
    versioned(db, candidate, data)
    audit(db, user, "candidate_updated", project.id)
    db.commit()
    return record(candidate)


@router.get(
    "/{project_id}/candidates/{candidate_id}/feedback",
    response_model=PageView[FeedbackView],
)
def feedback(
    candidate_id: int,
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    visible_candidate(db, candidate_id, project.id, user)
    return author_page(
        db,
        select(Feedback).where(Feedback.candidate_id == candidate_id),
        Feedback,
        paging,
    )


@router.post(
    "/{project_id}/candidates/{candidate_id}/feedback",
    status_code=201,
    response_model=FeedbackView,
)
def create_feedback(
    request: Request,
    candidate_id: int,
    data: TextData,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    visible_candidate(db, candidate_id, project.id, user)
    lock_project(db, project.id)

    def create():
        feedback = Feedback(
            candidate_id=candidate_id, author_id=user.id, body=data.body
        )
        db.add(feedback)
        db.flush()
        return authored(db, feedback)

    return submission(db, request, user, project, data, create)


@router.get("/{project_id}/documents", response_model=PageView[DocumentView])
def documents(
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    return page(
        db,
        select(Document).where(Document.project_id == project.id),
        Document,
        paging,
        record,
    )


@router.post("/{project_id}/documents", status_code=201, response_model=DocumentView)
def create_document(
    data: DocumentData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    document = Document(**data.model_dump(), project_id=project.id)
    db.add(document)
    audit(db, user, "document_created", project.id)
    db.commit()
    return record(document)


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.delete(child(db, Document, document_id, project.id))
    audit(db, user, "document_deleted", project.id)
    db.commit()


@router.get("/{project_id}/updates", response_model=PageView[PostView])
def posts(
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    result = author_page(
        db,
        select(Post).where(Post.project_id == project.id),
        Post,
        paging,
        descending=True,
    )
    ids = [p["id"] for p in result["items"]]
    counts = dict(
        db.execute(
            select(Comment.post_id, func.count())
            .where(Comment.post_id.in_(ids))
            .group_by(Comment.post_id)
        ).all()
    )
    for post in result["items"]:
        post.update(comments=[], comment_count=counts.get(post["id"], 0))
    return result


@router.post("/{project_id}/updates", status_code=201, response_model=PostView)
def create_post(
    request: Request,
    data: PostData,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):

    lock_project(db, project.id)

    def create():
        post = Post(**data.model_dump(), project_id=project.id, author_id=user.id)
        db.add(post)
        db.flush()
        return {**authored(db, post), "comments": []}

    return submission(db, request, user, project, data, create)


@router.post(
    "/{project_id}/updates/{post_id}/comments",
    status_code=201,
    response_model=CommentView,
)
def create_comment(
    request: Request,
    post_id: int,
    data: TextData,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    child(db, Post, post_id, project.id)
    lock_project(db, project.id)

    def create():
        comment = Comment(**data.model_dump(), post_id=post_id, author_id=user.id)
        db.add(comment)
        db.flush()
        return authored(db, comment)

    return submission(db, request, user, project, data, create)


@router.get("/{project_id}/messages", response_model=PageView[MessageView])
def messages(
    request: Request,
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    session = session_row(request, db)
    marker = db.get(ReadMarker, (project.id, session.user_id))
    baseline = marker.last_message_id if marker else 0
    if paging.cursor > max(baseline, session.delivered.get(str(project.id), 0)):
        raise HTTPException(400, "Read messages in order before advancing the cursor.")
    if not paging.cursor:
        paging.cursor = baseline
        if not db.scalar(
            select(Message.id)
            .where(Message.project_id == project.id, Message.id > baseline)
            .limit(1)
        ):
            ids = list(
                db.scalars(
                    select(Message.id)
                    .where(Message.project_id == project.id)
                    .order_by(Message.id.desc())
                    .limit(paging.limit)
                )
            )
            paging.cursor = min(ids) - 1 if ids else 0
    result = author_page(
        db, select(Message).where(Message.project_id == project.id), Message, paging
    )
    if result["items"]:
        db.refresh(session, with_for_update=True)
        delivered = dict(session.delivered)
        delivered[str(project.id)] = max(
            delivered.get(str(project.id), 0), result["items"][-1]["id"]
        )
        session.delivered = delivered
        db.commit()
    return result


@router.post("/{project_id}/messages", status_code=201, response_model=MessageView)
def create_message(
    request: Request,
    data: TextData,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):

    lock_project(db, project.id)

    def create():
        message = Message(**data.model_dump(), project_id=project.id, author_id=user.id)
        db.add(message)
        db.flush()
        return authored(db, message)

    return submission(db, request, user, project, data, create)


@router.put("/{project_id}/messages/read", status_code=204)
def mark_read(
    request: Request,
    data: ReadData,
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    # Only acknowledge messages actually received, not messages arriving during the request.
    if data.last_message_id:
        child(db, Message, data.last_message_id, project.id)
    if data.last_message_id > session_row(request, db).delivered.get(
        str(project.id), 0
    ):
        raise HTTPException(400, "Only delivered messages can be marked read.")
    stmt = insert(ReadMarker).values(
        project_id=project.id, user_id=user.id, last_message_id=data.last_message_id
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["project_id", "user_id"],
            set_={
                "last_message_id": func.greatest(
                    ReadMarker.last_message_id, data.last_message_id
                )
            },
        )
    )
    db.commit()


@router.get("/{project_id}/milestones", response_model=PageView[MilestoneView])
def milestones(
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    from sqlalchemy import tuple_

    query = select(Milestone).where(Milestone.project_id == project.id)
    if paging.cursor:
        anchor = child(db, Milestone, paging.cursor, project.id)
        query = query.where(
            tuple_(Milestone.target_date, Milestone.id)
            > tuple_(anchor.target_date, anchor.id)
        )
    rows = list(
        db.scalars(
            query.order_by(Milestone.target_date, Milestone.id).limit(paging.limit + 1)
        )
    )
    return {
        "items": [record(m) for m in rows[: paging.limit]],
        "next_cursor": rows[paging.limit - 1].id if len(rows) > paging.limit else None,
    }


@router.post("/{project_id}/milestones", status_code=201, response_model=MilestoneView)
def create_milestone(
    data: MilestoneData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    milestone = Milestone(**data.model_dump(exclude={"version"}), project_id=project.id)
    db.add(milestone)
    audit(db, user, "milestone_created", project.id)
    db.commit()
    return record(milestone)


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneView)
def update_milestone(
    milestone_id: int,
    data: MilestoneData,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    milestone = child(db, Milestone, milestone_id, project.id)
    versioned(db, milestone, data)
    audit(db, user, "milestone_updated", project.id)
    db.commit()
    return record(milestone)


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    milestone_id: int,
    project: Project = Depends(project_editor),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.delete(child(db, Milestone, milestone_id, project.id))
    audit(db, user, "milestone_deleted", project.id)
    db.commit()


@router.get("/{project_id}/updates/{post_id}/comments")
def comments(
    post_id: int,
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    child(db, Post, post_id, project.id)
    return author_page(
        db, select(Comment).where(Comment.post_id == post_id), Comment, paging
    )


def project_page(db, query, user, paging):
    result = page(db, query, Project, paging, descending=True)
    ids = [p.id for p in result["items"]]
    names = dict(
        db.execute(
            select(ClientOrg.id, ClientOrg.name).where(
                ClientOrg.id.in_([p.client_org_id for p in result["items"]])
            )
        ).all()
    )
    counts = dict(
        db.execute(
            select(Message.project_id, func.count())
            .outerjoin(
                ReadMarker,
                (ReadMarker.project_id == Message.project_id)
                & (ReadMarker.user_id == user.id),
            )
            .where(
                Message.project_id.in_(ids),
                Message.author_id != user.id,
                Message.id > func.coalesce(ReadMarker.last_message_id, 0),
            )
            .group_by(Message.project_id)
        ).all()
    )
    result["items"] = [
        {
            **record(p),
            "client_name": names[p.client_org_id],
            "unread_count": counts.get(p.id, 0),
        }
        for p in result["items"]
    ]
    return result


@router.get("/{project_id}/messages/history")
def message_history(
    before: int = 0,
    paging: Paging = Depends(),
    project: Project = Depends(project_access),
    db: Session = Depends(get_db),
):
    query = select(Message).where(Message.project_id == project.id)
    if before:
        query = query.where(Message.id < before)
    return author_page(db, query, Message, paging, descending=True)
