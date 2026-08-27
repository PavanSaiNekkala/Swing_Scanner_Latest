from __future__ import annotations



class InstitutionalMetricsError(
    Exception
):
    """
    Base exception for institutional metrics pipeline.
    """



class SchemaValidationError(
    InstitutionalMetricsError
):
    """
    Raised when input scanner data
    does not satisfy required schema.
    """



class NoSourceDataError(
    InstitutionalMetricsError
):
    """
    Raised when no valid scanner data
    is available for processing.
    """



class MetricsCalculationError(
    InstitutionalMetricsError
):
    """
    Raised when deterministic metric
    calculation fails.
    """



class ScoringError(
    InstitutionalMetricsError
):
    """
    Raised when institutional scoring
    calculation fails.
    """



class GovernanceError(
    InstitutionalMetricsError
):
    """
    Raised when governance evaluation
    fails.
    """



class RankingError(
    InstitutionalMetricsError
):
    """
    Raised when institutional ranking
    fails.
    """



class ExportError(
    InstitutionalMetricsError
):
    """
    Raised when CSV/Excel output
    generation fails.
    """



class RecommendationError(
    InstitutionalMetricsError
):
    """
    Raised when recommendation generation
    fails.
    """