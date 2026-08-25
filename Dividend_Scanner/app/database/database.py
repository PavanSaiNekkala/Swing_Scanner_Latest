"""
Database Configuration

Creates the SQLAlchemy engine and session factory.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from config.settings import SQLITE_URL


class Base(
    DeclarativeBase,
):
    """
    Base ORM class.
    """


engine = create_engine(

    SQLITE_URL,

    future=True,

)

SessionLocal = sessionmaker(

    bind=engine,

    autoflush=False,

    expire_on_commit=False,

    class_=Session,

)

# ---------------------------------------------------------
# Create Database Tables
# ---------------------------------------------------------

from app.database.tables import *

Base.metadata.create_all(

    bind=engine,

)


@contextmanager
def get_session():

    session = SessionLocal()

    try:

        yield session

        session.commit()

    except Exception:

        session.rollback()

        raise

    finally:

        session.close()