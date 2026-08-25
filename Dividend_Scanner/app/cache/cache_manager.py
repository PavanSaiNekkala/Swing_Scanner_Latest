"""
Cache Manager
"""

from __future__ import annotations

from config.settings import CACHE_TTL_DAYS

from app.cache.disk_cache import DiskCache


class CacheManager:

    def __init__(

        self,

    ):

        self.disk = DiskCache()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _cache_key(

        model,

        key,

    ) -> str:

        if isinstance(

            model,

            str,

        ):

            prefix = model.lower()

        else:

            prefix = model.__name__.lower()

        return f"{prefix}:{key}"

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    def get(

        self,

        model,

        key,

    ):

        return self.disk.get(

            self._cache_key(

                model,

                key,

            )

        )

    def set(

        self,

        model,

        key,

        value,

    ):

        self.disk.set(

            self._cache_key(

                model,

                key,

            ),

            value,

            expire=86400 * CACHE_TTL_DAYS,

        )

    def delete(

        self,

        model,

        key,

    ):

        self.disk.delete(

            self._cache_key(

                model,

                key,

            )

        )

    def clear(

        self,

    ):

        self.disk.clear()