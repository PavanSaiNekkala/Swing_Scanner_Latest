"""
Disk Cache
"""

from __future__ import annotations

from diskcache import Cache

from config.settings import DISKCACHE_DIR


class DiskCache:

    def __init__(

        self,

    ):

        self.cache = Cache(

            DISKCACHE_DIR,

        )

    def get(

        self,

        key,

    ):

        return self.cache.get(

            key,

        )

    def set(

        self,

        key,

        value,

        expire=None,

    ):

        self.cache.set(

            key,

            value,

            expire=expire,

        )

    def delete(

        self,

        key,

    ):

        self.cache.pop(

            key,

            None,

        )

    def clear(

        self,

    ):

        self.cache.clear()