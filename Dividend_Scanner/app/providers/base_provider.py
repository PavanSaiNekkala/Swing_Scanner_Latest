"""
Base Provider

Abstract base class for all external data providers.

Responsibilities
----------------
- Standard interface
- Shared logger
- Shared retry support
- Shared timeout
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from app.utils.logger import get_logger


class BaseProvider(ABC):
    """
    Base class for all providers.
    """

    PROVIDER = "Base Provider"

    def __init__(self) -> None:

        self.logger = get_logger(
            self.__class__.__name__
        )


    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        symbol = symbol.strip().upper()

        if "." in symbol:
            return symbol

        return f"{symbol}.NS"


    @abstractmethod
    def health_check(
        self,
    ) -> bool:
        """
        Returns whether provider
        is currently available.
        """

        raise NotImplementedError