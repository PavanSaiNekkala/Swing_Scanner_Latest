"""
===============================================================================
File: exceptions.py

Description:
    Custom exceptions for the NSE Daily Report application.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations


class NSEReportError(Exception):
    """
    Base exception for the application.

    All custom exceptions should inherit from this class.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# =============================================================================
# Configuration
# =============================================================================


class ConfigurationError(NSEReportError):
    """Raised when configuration is invalid."""


# =============================================================================
# File System
# =============================================================================


class FileError(NSEReportError):
    """Base class for file-related errors."""


class FileNotFoundError(FileError):
    """Raised when an expected file is missing."""


class InvalidCSVError(FileError):
    """Raised when CSV format is invalid."""


class OutputWriteError(FileError):
    """Raised when Excel output cannot be written."""


# =============================================================================
# Validation
# =============================================================================


class ValidationError(NSEReportError):
    """Raised when validation fails."""


class MissingColumnError(ValidationError):
    """Raised when a required DataFrame column is missing."""


class EmptyDataFrameError(ValidationError):
    """Raised when an empty DataFrame is encountered."""


class InvalidSymbolError(ValidationError):
    """Raised when a ticker symbol is invalid."""


# =============================================================================
# Market Data
# =============================================================================


class MarketDataError(NSEReportError):
    """Base exception for market data."""


class DownloadError(MarketDataError):
    """Raised when Yahoo Finance download fails."""


class NoMarketDataError(MarketDataError):
    """Raised when Yahoo Finance returns no data."""


# =============================================================================
# News
# =============================================================================


class NewsError(NSEReportError):
    """Base exception for news."""


class NewsFetchError(NewsError):
    """Raised when news retrieval fails."""


class NoNewsFoundError(NewsError):
    """Raised when no news is available."""


# =============================================================================
# Excel
# =============================================================================


class ExcelError(NSEReportError):
    """Base Excel exception."""


class ExcelGenerationError(ExcelError):
    """Raised when Excel workbook creation fails."""


class WorksheetError(ExcelError):
    """Raised when worksheet generation fails."""


# =============================================================================
# Ranking
# =============================================================================


class RankingError(NSEReportError):
    """Raised during ranking operations."""


# =============================================================================
# Returns
# =============================================================================


class ReturnCalculationError(NSEReportError):
    """Raised when return calculation fails."""


# =============================================================================
# Retry
# =============================================================================


class RetryLimitExceededError(NSEReportError):
    """Raised after all retry attempts fail."""


# =============================================================================
# Network
# =============================================================================


class NetworkError(NSEReportError):
    """Raised for HTTP/network failures."""


class TimeoutError(NetworkError):
    """Raised when a request times out."""