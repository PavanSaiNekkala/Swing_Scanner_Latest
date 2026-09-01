"""
Telegram Notification Gateway.

Responsibilities
----------------
1. Read Telegram credentials from environment variables.
2. Format institutional recommendations.
3. Send messages through Telegram Bot API.
4. Support dry-run mode.
5. Apply timeout and retry controls.
6. Never expose credentials in logs.

No institutional scoring or ranking logic belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import os
import time
from typing import Final
from urllib import error as urllib_error
from urllib import parse
from urllib import request


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

TELEGRAM_API_BASE: Final[str] = (
    "https://api.telegram.org"
)

DEFAULT_TIMEOUT_SECONDS: Final[int] = 20

DEFAULT_MAX_RETRIES: Final[int] = 3

MAX_TELEGRAM_MESSAGE_LENGTH: Final[int] = 4096


# ============================================================
# EXCEPTIONS
# ============================================================


class TelegramError(RuntimeError):
    """Base Telegram notification exception."""


class TelegramConfigurationError(
    TelegramError
):
    """Raised when Telegram configuration is invalid."""


class TelegramDeliveryError(
    TelegramError
):
    """Raised when Telegram delivery fails."""


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    """
    Telegram transport configuration.
    """

    bot_token: str

    chat_id: str

    timeout_seconds: int = (
        DEFAULT_TIMEOUT_SECONDS
    )

    max_retries: int = (
        DEFAULT_MAX_RETRIES
    )

    retry_backoff_seconds: float = 2.0

    parse_mode: str = "HTML"

    disable_web_page_preview: bool = True

    def __post_init__(self) -> None:

        if not self.bot_token.strip():
            raise TelegramConfigurationError(
                "Telegram bot token is empty."
            )

        if not self.chat_id.strip():
            raise TelegramConfigurationError(
                "Telegram chat ID is empty."
            )

        if (
            self.timeout_seconds
            <= 0
        ):
            raise ValueError(
                "timeout_seconds must be positive."
            )

        if (
            self.max_retries
            < 1
        ):
            raise ValueError(
                "max_retries must be at least 1."
            )


# ============================================================
# FACTORY
# ============================================================


def telegram_config_from_environment() -> TelegramConfig:
    """
    Build Telegram configuration from environment variables.

    Required
    --------
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    """

    bot_token = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "",
    ).strip()

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID",
        "",
    ).strip()

    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
    )


# ============================================================
# MESSAGE FORMATTER
# ============================================================

class TelegramMessageFormatter:
    """
    Formats institutional recommendations into
    a concise Telegram message.
    """

    def format(
        self,
        recommendations,
        *,
        generated_at: datetime | None = None,
        candidate_count: int | None = None,
        eligible_signal_count: int | None = None,
    ) -> str:
        """
        Create the daily institutional message.
        """

        generated_at = (
            generated_at
            or datetime.now()
        )

        lines: list[str] = []

        lines.append(
            "🏛️ <b>INSTITUTIONAL DAILY PICKS</b>"
        )

        lines.append(
            f"📅 {generated_at:%d-%b-%Y %H:%M:%S}"
        )

        lines.append("")

        if (
            recommendations is None
            or recommendations.empty
        ):
            lines.extend(
                [
                    "⚠️ <b>No qualifying recommendations today.</b>",
                    "",
                    "No active stock passed the configured "
                    "institutional recommendation filters.",
                ]
            )

        else:

            lines.append(
                "<b>Top Institutional Recommendations</b>"
            )

            lines.append("")

            for _, row in (
                recommendations.iterrows()
            ):

                recommendation_rank = (
                    self._safe_int(
                        row.get(
                            "Recommendation Rank",
                            0,
                        )
                    )
                )


                stock = self._escape(
                    row.get(
                        "Stock",
                        "UNKNOWN",
                    )
                )


                institutional_score = (
                    self._safe_float(
                        row.get(
                            "Institutional Score"
                        )
                    )
                )


                priority_score = (
                    self._safe_float(
                        row.get(
                            "Institutional Priority Score"
                        )
                    )
                )


                conviction_score = (
                    self._safe_float(
                        row.get(
                            "Rank Score"
                        )
                    )
                )

                rating = self._escape(
                    row.get(
                        "Institutional Rating",
                        "-",
                    )
                )


                decision = self._escape(
                    row.get(
                        "Institutional Decision",
                        "-",
                    )
                )


                lines.append(
                    f"<b>#{recommendation_rank} "
                    f"{stock}</b>"
                )


                lines.append(
                    f"   Priority Score: "
                    f"{priority_score:.2f}"
                )


                lines.append(
                    f"   Institutional Score: "
                    f"{institutional_score:.2f}"
                )


                lines.append(
                    f"   Conviction Score: "
                    f"{conviction_score:.2f}"
                )

                lines.append(
                    f"   Rating: {rating}"
                )


                lines.append(
                    f"   Decision: {decision}"
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "RS%",
                    "RS",
                    suffix="%",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "Exp/DAY%",
                    "Exp/Day",
                    suffix="%",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "CAGR%",
                    "CAGR",
                    suffix="%",
                )

                self._append_optional_metric(
                    lines,
                    row,
                    "CMP",
                    "CMP",
                    prefix="₹",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "Entry #",
                    "Entry",
                    prefix="₹",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "Target #",
                    "Target",
                    prefix="₹",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "Stop #",
                    "Stop Loss",
                    prefix="₹",
                )


                self._append_optional_metric(
                    lines,
                    row,
                    "Trail #",
                    "Trail",
                    prefix="₹",
                )


                lines.append("")

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

        if candidate_count is not None:

            lines.append(
                f"Eligible candidates: "
                f"{candidate_count}"
            )

        if eligible_signal_count is not None:

            lines.append(
                f"Eligible signals: "
                f"{eligible_signal_count}"
            )

        lines.append("")

        lines.append(
            "⚠️ <i>Institutional screening signal. "
            "Not financial advice.</i>"
        )

        message = "\n".join(
            lines
        )

        if len(message) > MAX_TELEGRAM_MESSAGE_LENGTH:

            message = (
                message[
                    : MAX_TELEGRAM_MESSAGE_LENGTH
                    - 30
                ]
                + "\n\n<i>Message truncated.</i>"
            )

        return message

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _escape(
        value,
    ) -> str:
        """
        Escape Telegram HTML-sensitive characters.
        """

        text = str(
            value
        )

        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _safe_float(
        value,
    ) -> float:

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        return result

    @staticmethod
    def _safe_int(
        value,
    ) -> int:

        try:

            return int(
                float(value)
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0

    @classmethod
    def _append_optional_metric(
        cls,
        lines: list[str],
        row,
        column: str,
        label: str,
        *,
        suffix: str = "",
        prefix: str = "",
    ) -> None:

        value = row.get(
            column
        )

        if value is None:
            return

        try:

            numeric = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        lines.append(
            f"   {label}: "
            f"{prefix}{numeric:.2f}{suffix}"
        )


# ============================================================
# TELEGRAM CLIENT
# ============================================================


class TelegramClient:
    """
    Minimal production Telegram Bot API client.

    Uses Python standard library only.
    """

    def __init__(
        self,
        config: TelegramConfig,
    ) -> None:

        self.config = config

        self.endpoint = (
            f"{TELEGRAM_API_BASE}"
            f"/bot{config.bot_token}"
            "/sendMessage"
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def send_message(
        self,
        message: str,
    ) -> dict:
        """
        Send a Telegram message.
        """

        if not message.strip():
            raise TelegramDeliveryError(
                "Cannot send an empty Telegram message."
            )

        payload = {
            "chat_id": self.config.chat_id,
            "text": message,
            "parse_mode": self.config.parse_mode,
            "disable_web_page_preview": (
                self.config.disable_web_page_preview
            ),
        }

        encoded = parse.urlencode(
            payload
        ).encode(
            "utf-8"
        )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.config.max_retries + 1,
        ):

            try:

                request_object = request.Request(
                    self.endpoint,
                    data=encoded,
                    method="POST",
                    headers={
                        "Content-Type": (
                            "application/x-www-form-urlencoded"
                        ),
                        "User-Agent": (
                            "SwingScanner/"
                            "InstitutionalMetrics"
                        ),
                    },
                )

                with request.urlopen(
                    request_object,
                    timeout=(
                        self.config.timeout_seconds
                    ),
                ) as response:

                    body = (
                        response.read()
                        .decode(
                            "utf-8"
                        )
                    )

                if response.status != 200:

                    raise TelegramDeliveryError(
                        "Telegram API returned "
                        f"HTTP {response.status}."
                    )

                import json

                result = json.loads(
                    body
                )

                if not result.get(
                    "ok",
                    False,
                ):

                    raise TelegramDeliveryError(
                        "Telegram API rejected "
                        "the message."
                    )

                logger.info(
                    "Telegram message delivered successfully."
                )

                return result

            except (
                urllib_error.URLError,
                urllib_error.HTTPError,
                TelegramDeliveryError,
                TimeoutError,
            ) as exc:

                last_error = exc

                logger.warning(
                    "Telegram delivery attempt failed | "
                    "Attempt=%d/%d | Error=%s",
                    attempt,
                    self.config.max_retries,
                    type(exc).__name__,
                )

                if (
                    attempt
                    < self.config.max_retries
                ):

                    time.sleep(
                        self.config.retry_backoff_seconds
                        * attempt
                    )

        raise TelegramDeliveryError(
            "Telegram delivery failed after "
            f"{self.config.max_retries} attempts."
        ) from last_error


# ============================================================
# SERVICE
# ============================================================


class TelegramNotificationService:
    """
    High-level notification service.

    Combines formatting and transport.
    """

    def __init__(
        self,
        client: TelegramClient,
        formatter: TelegramMessageFormatter | None = None,
    ) -> None:

        self.client = client

        self.formatter = (
            formatter
            or TelegramMessageFormatter()
        )

    def send_recommendations(
        self,
        recommendations,
        *,
        generated_at: datetime | None = None,
        candidate_count: int | None = None,
        eligible_signal_count: int | None = None,
        dry_run: bool = False,
    ) -> str:
        """
        Format and optionally deliver recommendations.

        Returns
        -------
        str
            Final Telegram message.
        """

        message = (
            self.formatter.format(
                recommendations,
                generated_at=generated_at,
                candidate_count=candidate_count,
                eligible_signal_count=eligible_signal_count,
            )
        )

        if dry_run:

            logger.info(
                "Telegram dry-run enabled; "
                "message was not sent."
            )

            return message

        self.client.send_message(
            message
        )

        return message


# ============================================================
# MESSAGE FINGERPRINT
# ============================================================


def recommendation_fingerprint(
    recommendations,
) -> str:
    """
    Create a deterministic fingerprint for a recommendation set.

    Useful for preventing accidental duplicate sends during
    workflow retries.
    """

    if recommendations is None:
        return hashlib.sha256(
            b"EMPTY"
        ).hexdigest()

    columns = [
        column
        for column in (
            "Recommendation Rank",
            "Stock",
            "Institutional Rank",
            "Institutional Score",
            "Institutional Decision",
        )
        if column in recommendations.columns
    ]

    normalized = (
        recommendations[
            columns
        ]
        .fillna("")
        .astype(str)
        .to_csv(
            index=False
        )
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()
