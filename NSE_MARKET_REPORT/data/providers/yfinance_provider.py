"""
Yahoo Finance market-data provider.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import yfinance as yf

from .base import MarketDataProvider


class YahooFinanceProvider(
    MarketDataProvider,
):
    """
    Yahoo Finance implementation of MarketDataProvider.

    NSE-listed equities use the Yahoo Finance .NS suffix.
    """

    def __init__(
        self,
        symbols: Iterable[str] | None = None,
    ) -> None:

        self.symbols = [
            self._normalize_symbol(
                symbol
            )
            for symbol in (
                symbols or []
            )
        ]

    # ========================================================
    # SYMBOL HELPERS
    # ========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """
        Convert an NSE symbol to Yahoo Finance format.
        """

        value = (
            str(
                symbol
            )
            .strip()
            .upper()
        )

        if not value:
            raise ValueError(
                "Symbol cannot be empty."
            )

        if value.endswith(
            ".NS"
        ):
            return value

        return f"{value}.NS"

    @staticmethod
    def _display_symbol(
        symbol: str,
    ) -> str:

        return (
            str(
                symbol
            )
            .strip()
            .upper()
            .removesuffix(".NS")
            .removesuffix(".BO")
        )

    # ========================================================
    # HEALTH
    # ========================================================

    def health(
        self,
    ) -> dict:

        try:

            data = yf.download(
                "^NSEI",
                period="1d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if data.empty:

                return {
                    "provider": "Yahoo Finance",
                    "status": "WARNING",
                    "message": (
                        "Yahoo Finance responded, "
                        "but no NSE index data was returned."
                    ),
                }

            return {
                "provider": "Yahoo Finance",
                "status": "OK",
                "message": (
                    "Yahoo Finance connection is healthy."
                ),
            }

        except Exception as exc:

            return {
                "provider": "Yahoo Finance",
                "status": "FAILED",
                "message": str(
                    exc
                ),
            }

    # ========================================================
    # QUOTES
    # ========================================================

    def fetch_quotes(
        self,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Fetch latest quote information.
        """

        requested_symbols = (
            symbols
            if symbols is not None
            else self.symbols
        )

        if not requested_symbols:

            return pd.DataFrame(
                columns=[
                    "Symbol",
                    "Price",
                    "Previous Close",
                    "Day High",
                    "Day Low",
                    "Volume",
                    "Change %",
                ]
            )

        rows: list[dict] = []

        for raw_symbol in requested_symbols:

            yahoo_symbol = (
                self._normalize_symbol(
                    raw_symbol
                )
            )

            display_symbol = (
                self._display_symbol(
                    yahoo_symbol
                )
            )

            try:

                ticker = yf.Ticker(
                    yahoo_symbol
                )

                fast_info = (
                    ticker.fast_info
                )

                price = fast_info.get(
                    "lastPrice"
                )

                previous_close = (
                    fast_info.get(
                        "previousClose"
                    )
                )

                day_high = (
                    fast_info.get(
                        "dayHigh"
                    )
                )

                day_low = (
                    fast_info.get(
                        "dayLow"
                    )
                )

                volume = (
                    fast_info.get(
                        "lastVolume"
                    )
                )

                change_pct = None

                if (
                    price is not None
                    and previous_close is not None
                    and float(
                        previous_close
                    ) != 0
                ):

                    change_pct = (
                        (
                            float(price)
                            / float(
                                previous_close
                            )
                        )
                        - 1.0
                    ) * 100.0

                rows.append(
                    {
                        "Symbol": display_symbol,
                        "Price": price,
                        "Previous Close": (
                            previous_close
                        ),
                        "Day High": day_high,
                        "Day Low": day_low,
                        "Volume": volume,
                        "Change %": change_pct,
                    }
                )

            except Exception as exc:

                rows.append(
                    {
                        "Symbol": display_symbol,
                        "Price": None,
                        "Previous Close": None,
                        "Day High": None,
                        "Day Low": None,
                        "Volume": None,
                        "Change %": None,
                        "_error": str(exc),
                    }
                )

        return pd.DataFrame(
            rows
        )

    ###############################################################################
    # HISTORY
    ###############################################################################

    def fetch_history(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ):

        ticker = yf.Ticker(
            f"{symbol}.NS"
        )

        df = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=False,
            actions=False,
        )

        if df.empty:

            return df

        df = df.reset_index()

        return df

    # ========================================================
    # OHLC
    # ========================================================

    def fetch_ohlc(
        self,
        symbol: str,
        *,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for one NSE symbol.
        """

        yahoo_symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        dataframe = yf.download(
            yahoo_symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if dataframe.empty:

            return pd.DataFrame()

        if isinstance(
            dataframe.columns,
            pd.MultiIndex,
        ):

            dataframe.columns = [
                column[0]
                for column in dataframe.columns
            ]

        dataframe = (
            dataframe.reset_index()
        )

        dataframe.columns = [
            str(
                column
            ).strip()
            for column in dataframe.columns
        ]

        if "Datetime" in dataframe.columns:

            dataframe = dataframe.rename(
                columns={
                    "Datetime": "Date",
                }
            )

        if "Date" in dataframe.columns:

            dataframe["Date"] = pd.to_datetime(
                dataframe["Date"],
                errors="coerce",
            )

        dataframe["Symbol"] = (
            self._display_symbol(
                yahoo_symbol
            )
        )

        return dataframe

    # ========================================================
    # MARKET MOVERS
    # ========================================================

    def fetch_top_gainers(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Calculate top gainers from the supplied universe.

        Yahoo Finance does not provide the same NSE
        top-gainers endpoint used by the previous NSE
        implementation, so movers are calculated from
        price change.
        """

        return self._fetch_market_movers(
            symbols=symbols,
            limit=limit,
            ascending=False,
        )

    def fetch_top_losers(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Calculate top losers from the supplied universe.
        """

        return self._fetch_market_movers(
            symbols=symbols,
            limit=limit,
            ascending=True,
        )

    def _fetch_market_movers(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 20,
        ascending: bool,
    ) -> pd.DataFrame:
        """
        Calculate market movers from the configured
        symbol universe.

        A universe must be available. We do not silently
        invent one.
        """

        requested_symbols = (
            symbols
            if symbols is not None
            else [
                self._display_symbol(
                    symbol
                )
                for symbol in self.symbols
            ]
        )

        requested_symbols = [
            str(symbol).strip()
            for symbol in requested_symbols
            if str(symbol).strip()
        ]

        if not requested_symbols:

            raise RuntimeError(
                "No market symbol universe was supplied "
                "to YahooFinanceProvider."
            )

        yahoo_symbols = [
            self._normalize_symbol(
                symbol
            )
            for symbol in requested_symbols
        ]

        dataframe = yf.download(
            yahoo_symbols,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="ticker",
        )

        if dataframe.empty:

            raise RuntimeError(
                "Yahoo Finance returned no market data "
                "for the configured universe."
            )

        rows: list[dict] = []

        # Single-symbol downloads have a flat structure.
        # Multi-symbol downloads use a ticker MultiIndex.
        if isinstance(
            dataframe.columns,
            pd.MultiIndex,
        ):

            available_tickers = (
                dataframe.columns
                .get_level_values(
                    0
                )
                .unique()
                .tolist()
            )

            for yahoo_symbol in (
                available_tickers
            ):

                try:

                    ticker_frame = (
                        dataframe[
                            yahoo_symbol
                        ]
                    )

                    if ticker_frame.empty:
                        continue

                    close = (
                        ticker_frame[
                            "Close"
                        ]
                        .dropna()
                    )

                    if len(
                        close
                    ) < 2:

                        continue

                    previous_close = float(
                        close.iloc[-2]
                    )

                    current_price = float(
                        close.iloc[-1]
                    )

                    if previous_close == 0:
                        continue

                    change_pct = (
                        (
                            current_price
                            / previous_close
                        )
                        - 1.0
                    ) * 100.0

                    rows.append(
                        {
                            "Symbol": (
                                self._display_symbol(
                                    yahoo_symbol
                                )
                            ),
                            "Price": (
                                current_price
                            ),
                            "Previous Close": (
                                previous_close
                            ),
                            "Change %": (
                                change_pct
                            ),
                        }
                    )

                except (
                    KeyError,
                    IndexError,
                    TypeError,
                    ValueError,
                ):

                    continue

        result = pd.DataFrame(
            rows
        )

        if result.empty:

            raise RuntimeError(
                "Unable to calculate market movers "
                "from Yahoo Finance data."
            )

        result = result.sort_values(
            "Change %",
            ascending=ascending,
            kind="stable",
        )

        return (
            result
            .head(
                limit
            )
            .reset_index(
                drop=True
            )
        )