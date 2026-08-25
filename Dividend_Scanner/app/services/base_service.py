"""
Base Service

Shared functionality for all services.
"""

from __future__ import annotations

from app.cache.cache_manager import CacheManager
from app.storage.scan_repository import ScanRepository


class BaseService:
    """Base class for application services."""

    def __init__(
        self,
        repository: ScanRepository | None = None,
        cache: CacheManager | None = None,
    ) -> None:

        self.repo: ScanRepository = (
            repository
            if repository is not None
            else ScanRepository()
        )

        self.cache: CacheManager = (
            cache
            if cache is not None
            else CacheManager()
        )