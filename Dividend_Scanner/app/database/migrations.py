"""
Database Initialization
"""

from __future__ import annotations

from app.database.database import Base
from app.database.database import engine

# Import tables so SQLAlchemy registers them.
from app.database import tables  # noqa: F401


def migrate():

    Base.metadata.create_all(
        bind=engine,
    )