"""
Market Storage
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session
from app.database.tables import MarketTable


class MarketStore:

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    def get(
        self,
        symbol: str,
    ) -> list[MarketTable]:

        with get_session() as session:

            return list(

                session.scalars(

                    select(
                        MarketTable,
                    ).where(

                        MarketTable.symbol == symbol,

                    )

                )

            )

    # ---------------------------------------------------------
    # Save / Upsert
    # ---------------------------------------------------------

    def save_many(
        self,
        rows: list[MarketTable],
    ) -> list[MarketTable]:

        saved: list[MarketTable] = []

        with get_session() as session:

            for row in rows:

                existing = session.scalar(

                    select(
                        MarketTable,
                    ).where(

                        MarketTable.symbol == row.symbol,
                        MarketTable.trading_date == row.trading_date,

                    )

                )

                if existing:

                    existing.open_price = row.open_price
                    existing.high_price = row.high_price
                    existing.low_price = row.low_price
                    existing.close_price = row.close_price
                    existing.adjusted_close = row.adjusted_close
                    existing.volume = row.volume

                    session.flush()

                    session.refresh(
                        existing,
                    )

                    saved.append(
                        existing,
                    )

                else:

                    session.add(
                        row,
                    )

                    session.flush()

                    session.refresh(
                        row,
                    )

                    saved.append(
                        row,
                    )

        return saved