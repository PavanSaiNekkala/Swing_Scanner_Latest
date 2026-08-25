"""
Company Service
"""

from __future__ import annotations

from app.database.tables import CompanyTable
from app.providers.yahoo.company_provider import CompanyProvider
from app.services.base_service import BaseService


class CompanyService(BaseService):

    def __init__(self):

        super().__init__()

        self.provider = CompanyProvider()

    def get(
        self,
        symbol: str,
    ):

        # ---------------------------------------------------------
        # Cache
        # ---------------------------------------------------------

        cached = self.cache.get(
            "company",
            symbol,
        )

        if cached:

            return cached

        # ---------------------------------------------------------
        # Yahoo Finance
        #
        # During development we always refresh the company profile
        # to avoid stale database records.
        # ---------------------------------------------------------

        company = self.provider.get_company(
            symbol,
        )

        if company is None:

            return None

        # ---------------------------------------------------------
        # Existing Database Record
        # ---------------------------------------------------------

        existing = self.repo.company.find_one(
            symbol=symbol,
        )

        if existing:

            existing.company_name = company.company_name

            existing.sector = company.sector

            existing.industry = company.industry

            existing.market_cap = company.market_cap

            self.repo.company.update(
                existing,
            )

            self.cache.set(
                "company",
                symbol,
                existing,
            )

            return existing

        # ---------------------------------------------------------
        # Create ORM object
        # ---------------------------------------------------------

        table = CompanyTable(

            symbol=company.symbol,

            company_name=company.company_name,

            sector=company.sector,

            industry=company.industry,

            market_cap=company.market_cap,

        )

        self.repo.company.add(
            table,
        )

        self.cache.set(
            "company",
            symbol,
            table,
        )

        return table