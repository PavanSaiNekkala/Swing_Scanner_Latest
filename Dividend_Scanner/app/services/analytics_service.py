"""
Analytics Service

Facade for all analytics modules.
"""

from __future__ import annotations

from app.analytics.dividend_metrics import DividendMetrics
from app.analytics.ohlc_window import OHLCWindow
from app.analytics.returns import ReturnAnalytics
from app.analytics.scoring import ScoringEngine
from app.analytics.volume import VolumeAnalytics


class AnalyticsService:
    """Provides access to all analytics engines."""

    def __init__(
        self,
        metrics: DividendMetrics | None = None,
        returns: ReturnAnalytics | None = None,
        volume: VolumeAnalytics | None = None,
        window: OHLCWindow | None = None,
        scoring: ScoringEngine | None = None,
    ) -> None:

        self.metrics = metrics or DividendMetrics()

        self.returns = returns or ReturnAnalytics()

        self.volume = volume or VolumeAnalytics()

        self.window = window or OHLCWindow()

        self.scoring = scoring or ScoringEngine()