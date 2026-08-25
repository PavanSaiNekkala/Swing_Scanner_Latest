"""
Dividend Storage
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session
from app.database.tables import DividendTable


class DividendStore:

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    def get(
        self,
        symbol: str,
    ) -> list[DividendTable]:

        with get_session() as session:

            return list(

                session.scalars(

                    select(
                        DividendTable,
                    ).where(

                        DividendTable.symbol == symbol,

                    )

                )

            )

    # ---------------------------------------------------------
    # Save / Upsert
    # ---------------------------------------------------------

    def save_many(
        self,
        rows: list[DividendTable],
    ) -> list[DividendTable]:

        saved: list[DividendTable] = []

        with get_session() as session:

            for row in rows:

                existing = session.scalar(

                    select(
                        DividendTable,
                    ).where(

                        DividendTable.symbol == row.symbol,
                        DividendTable.ex_date == row.ex_date,

                    )

                )

                if existing:

                    existing.record_date = row.record_date
                    existing.payment_date = row.payment_date
                    existing.amount = row.amount
                    existing.dividend_type = row.dividend_type
                    existing.currency = row.currency

                    #existing.provider = row.provider

                    session.flush()
                    session.refresh(existing)

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


    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    def delete(

        self,

        symbol: str,

    ) -> None:

        with get_session() as session:

            session.query(

                DividendTable,

            ).filter(

                DividendTable.symbol == symbol,

            ).delete(

                synchronize_session=False,

            )

    def clear(

        self,

    ) -> None:

        with get_session() as session:

            session.query(

                DividendTable,

            ).delete(

                synchronize_session=False,

            )