from __future__ import annotations

import threading
import time


class GeminiRateLimiter:

    def __init__(
        self,
        minimum_interval: float = 5.0,
    ) -> None:

        self.minimum_interval = (
            minimum_interval
        )

        self._lock = threading.Lock()

        self._last_request_at = 0.0

    def wait(self) -> None:

        with self._lock:

            now = time.monotonic()

            elapsed = (
                now
                - self._last_request_at
            )

            remaining = (
                self.minimum_interval
                - elapsed
            )

            if remaining > 0:

                time.sleep(
                    remaining
                )

            self._last_request_at = (
                time.monotonic()
            )

    def cooldown(
        self,
        seconds: float,
    ) -> None:

        with self._lock:

            self._last_request_at = (
                max(
                    self._last_request_at,
                    time.monotonic(),
                )
                + seconds
            )


GEMINI_RATE_LIMITER = GeminiRateLimiter(
    minimum_interval=5.0
)