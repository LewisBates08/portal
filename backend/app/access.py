from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import Agency, Candidate, Membership, Project, User
from .security import current_user


def project_access(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        db.scalar(select(Agency).where(Agency.id == user.agency_id).with_for_update())
        project = db.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )
    else:
        project = db.get(Project, project_id)
    if not project or project.agency_id != user.agency_id:
        raise HTTPException(404, "Project not found.")
    if user.role != "admin" and not db.get(Membership, (project_id, user.id)):
        raise HTTPException(404, "Project not found.")
    if project.archived_at and request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(409, "Archived searches are read-only.")
    return project


def project_editor(
    project: Project = Depends(project_access), user: User = Depends(current_user)
):
    if user.role == "client":
        raise HTTPException(403, "Only agency staff can edit search details.")
    return project


def child(db, model, resource_id, project_id):
    resource = db.get(model, resource_id)
    if not resource or resource.project_id != project_id:
        raise HTTPException(404, "Item not found.")
    return resource


def visible_candidate(db, candidate_id, project_id, user):
    candidate = child(db, Candidate, candidate_id, project_id)
    if user.role == "client" and not candidate.client_visible:
        raise HTTPException(404, "Candidate not found.")
    return candidate
