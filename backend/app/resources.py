"""Bounded queries, optimistic edits and retry-safe collaboration writes."""

import json
from fastapi import Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from .models import User, Project, Submission, Agency
from .security import digest, current_user, throttle, audit
from .database import get_db
from .config import get_settings


class Paging:
    def __init__(
        self, cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
    ):
        self.cursor, self.limit = cursor, limit


def page(db, query, model, paging, render=None, descending=False):
    query = (
        query.where(model.id < paging.cursor)
        if descending and paging.cursor
        else query.where(model.id > paging.cursor)
        if paging.cursor
        else query
    )
    rows = list(
        db.scalars(
            query.order_by(model.id.desc() if descending else model.id).limit(
                paging.limit + 1
            )
        )
    )
    visible = rows[: paging.limit]
    return {
        "items": [render(row) if render else row for row in visible],
        "next_cursor": visible[-1].id if len(rows) > paging.limit else None,
    }


def author_page(db, query, model, paging, descending=False):
    result = page(db, query, model, paging, descending=descending)
    names = dict(
        db.execute(
            select(User.id, User.name).where(
                User.id.in_({r.author_id for r in result["items"]})
            )
        ).all()
    )
    from .serializers import record

    result["items"] = [
        {**record(r), "author_name": names[r.author_id]} for r in result["items"]
    ]
    return result


def versioned(db, row, data):
    # Lock and refresh before comparing, including under READ COMMITTED.
    db.refresh(row, with_for_update=True)
    if data.version is None:
        raise HTTPException(428, "Reload this record before editing it.")
    if row.version != data.version:
        raise HTTPException(
            409,
            "Someone changed this record. Reload it and reapply your changes; your form has been preserved.",
        )
    for key, value in data.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    row.version += 1


def write_limit(request: Request, db=Depends(get_db), user=Depends(current_user)):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        throttle(db, f"write-user:{user.id}", 120)
        throttle(
            db, f"write-agency:{user.agency_id}", get_settings().daily_writes, 86400
        )
    else:
        throttle(db, f"read-user:{user.id}", 600)


def lock_project(db, project_id):
    return db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def submission(db, request, user, project, data, create):
    key = request.headers.get("idempotency-key", "")
    import uuid

    try:
        uuid.UUID(key)
    except ValueError:
        raise HTTPException(
            400, "A UUID Idempotency-Key is required for this submission."
        )
    hashed = digest(f"{user.id}:{project.id}:{key}")
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(hashed[:15], 16)}
    )
    fingerprint = digest(
        request.url.path + json.dumps(data.model_dump(), sort_keys=True)
    )
    existing = db.get(Submission, hashed)
    if existing:
        if existing.fingerprint != fingerprint:
            raise HTTPException(
                409, "This submission key was already used for different content."
            )
        return existing.result
    result = jsonable_encoder(create())
    db.add(
        Submission(
            key=hashed,
            user_id=user.id,
            project_id=project.id,
            fingerprint=fingerprint,
            result=result,
        )
    )
    audit(db, user, "collaboration_created", request.url.path)
    db.commit()
    return result


def require_retention(db, agency_id):
    agency = db.scalar(select(Agency).where(Agency.id == agency_id).with_for_update())
    if not agency.retention_days:
        raise HTTPException(
            409,
            "Set the agency retention policy in Administration before adding search data.",
        )
    return agency
