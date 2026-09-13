from .models import ClientOrg, Message, ReadMarker, User
from sqlalchemy import func, select


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def user_view(user):
    return {key: getattr(user, key) for key in ('id', 'name', 'email', 'role', 'agency_id', 'client_org_id')}


def authored(db, row):
    return {**record(row), 'author_name': db.get(User, row.author_id).name}


def project_view(db, project, user):
    marker = db.get(ReadMarker, (project.id, user.id))
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.project_id == project.id, Message.author_id != user.id, Message.id > (marker.last_message_id if marker else 0)))
    return {**record(project), 'client_name': db.get(ClientOrg, project.client_org_id).name, 'unread_count': unread}
