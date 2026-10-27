from sqlalchemy import create_engine
from contextlib import contextmanager
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=get_settings().pool_size,
    max_overflow=0,
    pool_timeout=5,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=10000 -c lock_timeout=5000",
    },
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db


@contextmanager
def rate_limit_session():
    """A separate durability boundary that must never be a business session."""
    with SessionLocal() as db:
        yield db
