"""
News Storage
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session
from app.database.tables import NewsArticleTable


class NewsStore:

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    def get(
        self,
        symbol: str,
    ) -> list[NewsArticleTable]:

        with get_session() as session:

            return list(

                session.scalars(

                    select(
                        NewsArticleTable,
                    ).where(

                        NewsArticleTable.symbol == symbol,

                    )

                )

            )

    # ---------------------------------------------------------
    # Save / Upsert
    # ---------------------------------------------------------

    def save_many(
        self,
        rows: list[NewsArticleTable],
    ) -> list[NewsArticleTable]:

        saved: list[NewsArticleTable] = []

        with get_session() as session:

            for row in rows:

                existing = session.scalar(

                    select(
                        NewsArticleTable,
                    ).where(

                        NewsArticleTable.url == row.url,

                    )

                )

                if existing:

                    existing.title = row.title
                    existing.publisher = row.publisher
                    existing.published_at = row.published_at
                    existing.summary = row.summary
                    existing.sentiment = row.sentiment

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