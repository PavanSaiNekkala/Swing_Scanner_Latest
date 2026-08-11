class InstitutionalMetricsError(Exception):
    """Base exception."""


class SchemaValidationError(
    InstitutionalMetricsError
):
    """Raised when scanner data fails schema validation."""


class DuplicateStockError(
    InstitutionalMetricsError
):
    """Raised when duplicate handling fails."""


class NoSourceDataError(
    InstitutionalMetricsError
):
    """Raised when no valid Latest Scan data exists."""


class ExportError(
    InstitutionalMetricsError
):
    """Raised when output generation fails."""