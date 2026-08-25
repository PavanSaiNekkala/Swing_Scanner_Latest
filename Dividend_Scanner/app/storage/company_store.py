"""
Company Repository
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session
from app.database.tables import CompanyTable
from app.storage.base_repository import BaseRepository


class CompanyStore(
    BaseRepository[CompanyTable],
):

    def __init__(
        self,
    ) -> None:

        super().__init__(
            CompanyTable,
        )

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    def get_by_symbol(
        self,
        symbol: str,
    ) -> CompanyTable | None:

        with get_session() as session:

            return session.scalar(

                select(
                    CompanyTable,
                ).where(

                    CompanyTable.symbol == symbol,

                )

            )

    def exists(
        self,
        symbol: str,
    ) -> bool:

        return self.get_by_symbol(
            symbol,
        ) is not None

    # ---------------------------------------------------------
    # Save / Upsert
    # ---------------------------------------------------------

    def save(
        self,
        company: CompanyTable,
    ) -> CompanyTable:

        with get_session() as session:

            existing = session.scalar(

                select(
                    CompanyTable,
                ).where(

                    CompanyTable.symbol == company.symbol,

                )

            )

            if existing:

                existing.company_name = company.company_name
                existing.sector = company.sector
                existing.industry = company.industry
                existing.market_cap = company.market_cap
                existing.exchange = company.exchange
                existing.currency = company.currency
                existing.country = company.country
                existing.website = company.website
                existing.employees = company.employees

                session.flush()
                session.refresh(existing)

                return existing

            session.add(
                company,
            )

            session.flush()

            session.refresh(
                company,
            )

            return company