"""Connexion à la base et session par requête."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import reglages


class Base(DeclarativeBase):
    pass


@lru_cache
def moteur() -> Engine:
    return create_engine(reglages().database_url, pool_pre_ping=True)


@lru_cache
def fabrique_sessions() -> sessionmaker[Session]:
    return sessionmaker(bind=moteur(), expire_on_commit=False)


def session() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, fermée à la fin."""
    s = fabrique_sessions()()
    try:
        yield s
    finally:
        s.close()
