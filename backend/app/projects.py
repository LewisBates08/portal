from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .access import child, project_access, project_editor, visible_candidate
from .database import get_db
from .models import Candidate, ClientOrg, Comment, Document, Feedback, Membership, Message, Milestone, Post, Project, ReadMarker, User
from .schemas import CandidateData, DocumentData, MilestoneData, PostData, ProjectCreate, ProjectData, ReadData, TextData
from .security import admin, current_user
from .serializers import authored, project_view, record

from .responses import ProjectView, CandidateView, FeedbackView, DocumentView, PostView, CommentView, MessageView, MilestoneView

router = APIRouter(prefix='/projects', tags=['Projects'])


@router.get('', response_model=list[ProjectView])
def projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Project).where(Project.agency_id == user.agency_id)
    if user.role != 'admin':
        query = query.join(Membership).where(Membership.user_id == user.id)
    return [project_view(db, p, user) for p in db.scalars(query.order_by(Project.created_at.desc()))]


@router.post('', status_code=201, response_model=ProjectView)
def create_project(data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(admin)):
    org = db.get(ClientOrg, data.client_org_id)
    if not org or org.agency_id != user.agency_id:
        raise HTTPException(400, 'Choose a client organisation in your agency.')
    project = Project(**data.model_dump(), agency_id=user.agency_id)
    db.add(project)
    db.commit()
    return project_view(db, project, user)


@router.get('/{project_id}', response_model=ProjectView)
def get_project(project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return project_view(db, project, user)


@router.put('/{project_id}', response_model=ProjectView)
def update_project(data: ProjectData, project: Project = Depends(project_editor), db: Session = Depends(get_db), user: User = Depends(current_user)):
    for key, value in data.model_dump().items():
        setattr(project, key, value)
    db.commit()
    return project_view(db, project, user)


@router.get('/{project_id}/candidates', response_model=list[CandidateView])
def candidates(project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Candidate).where(Candidate.project_id == project.id)
    if user.role == 'client':
        query = query.where(Candidate.client_visible.is_(True))
    return [record(c) for c in db.scalars(query.order_by(Candidate.id))]


@router.post('/{project_id}/candidates', status_code=201, response_model=CandidateView)
def create_candidate(data: CandidateData, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    candidate = Candidate(**data.model_dump(), project_id=project.id)
    db.add(candidate)
    db.commit()
    return record(candidate)


@router.get('/{project_id}/candidates/{candidate_id}', response_model=CandidateView)
def get_candidate(candidate_id: int, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return record(visible_candidate(db, candidate_id, project.id, user))


@router.put('/{project_id}/candidates/{candidate_id}', response_model=CandidateView)
def update_candidate(candidate_id: int, data: CandidateData, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    candidate = child(db, Candidate, candidate_id, project.id)
    for key, value in data.model_dump().items():
        setattr(candidate, key, value)
    db.commit()
    return record(candidate)


@router.get('/{project_id}/candidates/{candidate_id}/feedback', response_model=list[FeedbackView])
def feedback(candidate_id: int, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    visible_candidate(db, candidate_id, project.id, user)
    return [authored(db, f) for f in db.scalars(select(Feedback).where(Feedback.candidate_id == candidate_id).order_by(Feedback.id))]


@router.post('/{project_id}/candidates/{candidate_id}/feedback', status_code=201, response_model=FeedbackView)
def create_feedback(candidate_id: int, data: TextData, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    visible_candidate(db, candidate_id, project.id, user)
    feedback = Feedback(candidate_id=candidate_id, author_id=user.id, body=data.body)
    db.add(feedback)
    db.commit()
    return authored(db, feedback)


@router.get('/{project_id}/documents', response_model=list[DocumentView])
def documents(project: Project = Depends(project_access), db: Session = Depends(get_db)):
    return [record(d) for d in db.scalars(select(Document).where(Document.project_id == project.id).order_by(Document.id))]


@router.post('/{project_id}/documents', status_code=201, response_model=DocumentView)
def create_document(data: DocumentData, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    document = Document(**data.model_dump(), project_id=project.id)
    db.add(document)
    db.commit()
    return record(document)


@router.delete('/{project_id}/documents/{document_id}', status_code=204)
def delete_document(document_id: int, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    db.delete(child(db, Document, document_id, project.id))
    db.commit()


@router.get('/{project_id}/updates', response_model=list[PostView])
def posts(project: Project = Depends(project_access), db: Session = Depends(get_db)):
    result = []
    for post in db.scalars(select(Post).where(Post.project_id == project.id).order_by(Post.id.desc())):
        result.append({**authored(db, post), 'comments': [authored(db, c) for c in db.scalars(select(Comment).where(Comment.post_id == post.id).order_by(Comment.id))]})
    return result


@router.post('/{project_id}/updates', status_code=201, response_model=PostView)
def create_post(data: PostData, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    post = Post(**data.model_dump(), project_id=project.id, author_id=user.id)
    db.add(post)
    db.commit()
    return {**authored(db, post), 'comments': []}


@router.post('/{project_id}/updates/{post_id}/comments', status_code=201, response_model=CommentView)
def create_comment(post_id: int, data: TextData, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    child(db, Post, post_id, project.id)
    comment = Comment(**data.model_dump(), post_id=post_id, author_id=user.id)
    db.add(comment)
    db.commit()
    return authored(db, comment)


@router.get('/{project_id}/messages', response_model=list[MessageView])
def messages(project: Project = Depends(project_access), db: Session = Depends(get_db)):
    return [authored(db, m) for m in db.scalars(select(Message).where(Message.project_id == project.id).order_by(Message.id))]


@router.post('/{project_id}/messages', status_code=201, response_model=MessageView)
def create_message(data: TextData, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    message = Message(**data.model_dump(), project_id=project.id, author_id=user.id)
    db.add(message)
    db.commit()
    return authored(db, message)


@router.put('/{project_id}/messages/read', status_code=204)
def mark_read(data: ReadData, project: Project = Depends(project_access), db: Session = Depends(get_db), user: User = Depends(current_user)):
    # Only acknowledge messages actually received, not messages arriving during the request.
    if data.last_message_id:
        child(db, Message, data.last_message_id, project.id)
    marker = db.scalar(select(ReadMarker).where(ReadMarker.project_id == project.id, ReadMarker.user_id == user.id).with_for_update())
    if not marker:
        marker = ReadMarker(project_id=project.id, user_id=user.id, last_message_id=0)
        db.add(marker)
    marker.last_message_id = max(marker.last_message_id, data.last_message_id)
    db.commit()


@router.get('/{project_id}/milestones', response_model=list[MilestoneView])
def milestones(project: Project = Depends(project_access), db: Session = Depends(get_db)):
    return [record(m) for m in db.scalars(select(Milestone).where(Milestone.project_id == project.id).order_by(Milestone.target_date, Milestone.id))]


@router.post('/{project_id}/milestones', status_code=201, response_model=MilestoneView)
def create_milestone(data: MilestoneData, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    milestone = Milestone(**data.model_dump(), project_id=project.id)
    db.add(milestone)
    db.commit()
    return record(milestone)


@router.put('/{project_id}/milestones/{milestone_id}', response_model=MilestoneView)
def update_milestone(milestone_id: int, data: MilestoneData, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    milestone = child(db, Milestone, milestone_id, project.id)
    for key, value in data.model_dump().items():
        setattr(milestone, key, value)
    db.commit()
    return record(milestone)


@router.delete('/{project_id}/milestones/{milestone_id}', status_code=204)
def delete_milestone(milestone_id: int, project: Project = Depends(project_editor), db: Session = Depends(get_db)):
    db.delete(child(db, Milestone, milestone_id, project.id))
    db.commit()
