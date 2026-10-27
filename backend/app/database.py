from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


def connection_args(database_url: str):
    args = {"connect_timeout": 5}
    if "-pooler." not in (make_url(database_url).host or ""):
        args["options"] = "-c statement_timeout=10000 -c lock_timeout=5000"
    return args


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.pool_size,
    max_overflow=0,
    pool_timeout=5,
    connect_args=connection_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
