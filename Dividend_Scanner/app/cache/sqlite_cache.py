"""
SQLite Cache
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.database import get_session


class SQLiteCache:

    def get(

        self,

        table,

        **filters,

    ):

        with get_session() as session:

            query = select(

                table

            )

            for key, value in filters.items():

                query = query.where(

                    getattr(

                        table,

                        key,

                    ) == value

                )

            return session.execute(

                query

            ).scalars().first()

    def get_all(

        self,

        table,

    ):

        with get_session() as session:

            return list(

                session.execute(

                    select(table)

                ).scalars()

            )

    def insert(

        self,

        row,

    ):

        with get_session() as session:

            session.add(

                row,

            )

    def bulk_insert(

        self,

        rows,

    ):

        if not rows:

            return

        with get_session() as session:

            session.add_all(

                rows,

            )

    def update(

        self,

        row,

    ):

        with get_session() as session:

            session.merge(

                row,

            )

    def delete(

        self,

        row,

    ):

        with get_session() as session:

            session.delete(

                row,

            )

    def exists(

        self,

        table,

        **filters,

    ) -> bool:

        return (

            self.get(

                table,

                **filters,

            )

            is not None

        )