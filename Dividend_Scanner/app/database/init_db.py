"""
Database Initialization
"""

from __future__ import annotations

from app.database.database import Base
from app.database.database import engine

# Import ALL ORM models so SQLAlchemy registers them
from app.database.tables import (
    CompanyTable,
    DividendTable,
    MarketTable,
    NewsArticleTable,
    ScanResultTable,
)


def init_database() -> None:

    Base.metadata.create_all(
        bind=engine,
    )