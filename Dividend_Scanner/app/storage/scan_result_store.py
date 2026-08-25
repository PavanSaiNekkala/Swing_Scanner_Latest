"""
Scan Result Storage
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session
from app.database.tables import ScanResultTable
from app.storage.base_repository import BaseRepository


class ScanResultStore(
    BaseRepository[ScanResultTable],
):

    def __init__(
        self,
    ) -> None:

        super().__init__(
            ScanResultTable,
        )

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    def get_by_symbol(
        self,
        symbol: str,
    ) -> ScanResultTable | None:

        with get_session() as session:

            return session.scalar(

                select(
                    ScanResultTable,
                ).where(

                    ScanResultTable.symbol == symbol,

                )

            )

    # ---------------------------------------------------------
    # Save / Upsert
    # ---------------------------------------------------------

    def save(
        self,
        result: ScanResultTable,
    ) -> ScanResultTable:

        with get_session() as session:

            existing = session.scalar(

                select(
                    ScanResultTable,
                ).where(

                    ScanResultTable.symbol == result.symbol,

                )

            )

            if existing:

                existing.score = result.score
                existing.dividend_yield = result.dividend_yield
                existing.dividend_growth = result.dividend_growth
                existing.consistency_score = result.consistency_score
                existing.return_score = result.return_score
                existing.volume_score = result.volume_score
                existing.recommendation = result.recommendation
                existing.updated_at = result.updated_at

                session.flush()

                session.refresh(
                    existing,
                )

                return existing

            session.add(
                result,
            )

            session.flush()

            session.refresh(
                result,
            )

            return result