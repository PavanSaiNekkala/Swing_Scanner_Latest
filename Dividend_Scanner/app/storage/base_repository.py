"""
Base Repository

Generic repository implementation for SQLAlchemy models.
"""

from __future__ import annotations

from typing import Generic
from typing import Optional
from typing import Type
from typing import TypeVar

from sqlalchemy import select

from app.database.database import get_session

T = TypeVar("T")


class BaseRepository(
    Generic[T],
):

    def __init__(
        self,
        model: Type[T],
    ) -> None:

        self.model = model

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def add(
        self,
        entity: T,
    ) -> T:

        with get_session() as session:

            session.add(
                entity,
            )

            session.flush()

            session.refresh(
                entity,
            )

            return entity

    def add_many(
        self,
        entities: list[T],
    ) -> list[T]:

        with get_session() as session:

            session.add_all(
                entities,
            )

            session.flush()

            for entity in entities:

                session.refresh(
                    entity,
                )

            return entities

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    def get(
        self,
        primary_key,
    ) -> Optional[T]:

        with get_session() as session:

            return session.get(
                self.model,
                primary_key,
            )

    def find_one(
        self,
        **filters,
    ) -> Optional[T]:

        with get_session() as session:

            statement = (

                select(
                    self.model,
                ).filter_by(
                    **filters,
                )

            )

            return session.scalar(
                statement,
            )

    def find_all(
        self,
        **filters,
    ) -> list[T]:

        with get_session() as session:

            statement = (

                select(
                    self.model,
                ).filter_by(
                    **filters,
                )

            )

            return list(
                session.scalars(
                    statement,
                )
            )

    def get_all(
        self,
    ) -> list[T]:

        with get_session() as session:

            return list(

                session.scalars(

                    select(
                        self.model,
                    )

                )

            )

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    def update(
        self,
        entity: T,
    ) -> T:

        with get_session() as session:

            merged = session.merge(
                entity,
            )

            session.flush()

            session.refresh(
                merged,
            )

            return merged

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    def save(
        self,
        entity: T,
    ) -> T:

        return self.update(
            entity,
        )

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    def delete(
        self,
        entity: T,
    ) -> None:

        with get_session() as session:

            merged = session.merge(
                entity,
            )

            session.delete(
                merged,
            )

    # ---------------------------------------------------------
    # Exists
    # ---------------------------------------------------------

    def exists(
        self,
        **filters,
    ) -> bool:

        return (

            self.find_one(
                **filters,
            )

            is not None

        )

    # ---------------------------------------------------------
    # Count
    # ---------------------------------------------------------

    def count(
        self,
        **filters,
    ) -> int:

        return len(

            self.find_all(
                **filters,
            )

        )