"""
===============================================================================
Module    : ohlc.py
Package   : data
Purpose   : OHLC data service
Architecture : Foundation Layer
Provider  : Yahoo Finance
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config.logging_config import get_logger
from config.timezone import ist_now
from data.providers.yfinance_provider import YahooFinanceProvider

logger = get_logger(__name__)


###############################################################################
# CONFIGURATION
###############################################################################

DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"

CACHE_DIR = Path("cache/ohlc")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


###############################################################################
# DATA MODEL
###############################################################################

@dataclass(slots=True)
class OHLCRequest:
    """
    Represents one OHLC download request.
    """

    symbol: str
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    use_cache: bool = True


###############################################################################
# OHLC SERVICE
###############################################################################

class OHLCData:
    """
    Central OHLC service.

    Responsibilities
    ----------------
    • Download historical candles
    • Normalize Yahoo Finance output
    • Maintain cache
    • Health monitoring
    """

    def __init__(
        self,
        provider: Optional[YahooFinanceProvider] = None,
    ) -> None:

        logger.info("Initializing OHLCData...")

        self.provider = provider or YahooFinanceProvider()

        self.cache_dir = CACHE_DIR

        self.cache_enabled = True

        logger.info("OHLCData initialized successfully.")


###############################################################################
# PUBLIC API
###############################################################################

    def fetch(
        self,
        symbol: str,
        period: str = DEFAULT_PERIOD,
        interval: str = DEFAULT_INTERVAL,
    ) -> pd.DataFrame:
        """
        Fetch OHLC history for one symbol.
        """

        request = OHLCRequest(
            symbol=symbol,
            period=period,
            interval=interval,
        )

        return self._load_history(request)


###############################################################################
# FETCH MULTIPLE SYMBOLS
###############################################################################

    def fetch_many(
        self,
        symbols: list[str],
        period: str = DEFAULT_PERIOD,
        interval: str = DEFAULT_INTERVAL,
    ) -> dict[str, pd.DataFrame]:
        """
        Download OHLC for multiple symbols.
        """

        result: dict[str, pd.DataFrame] = {}

        for symbol in symbols:

            try:

                result[symbol] = self.fetch(
                    symbol=symbol,
                    period=period,
                    interval=interval,
                )

            except Exception:

                logger.exception(
                    "Unable to fetch OHLC for %s",
                    symbol,
                )

                result[symbol] = pd.DataFrame()

        return result


    ###############################################################################
    # MERGE
    ###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:

        symbols = (
            report_df["Symbol"]
            .dropna()
            .unique()
            .tolist()
        )

        ohlc_map = self.fetch_many(
            symbols=symbols,
        )

        rows = []

        for symbol, df in ohlc_map.items():

            if df.empty:

                continue

            latest = df.iloc[-1]

            rows.append(
                {
                    "Symbol": symbol,
                    "Open": latest.get(
                        "Open"
                    ),
                    "High": latest.get(
                        "High"
                    ),
                    "Low": latest.get(
                        "Low"
                    ),
                    "Close": latest.get(
                        "Close"
                    ),
                    "Volume": latest.get(
                        "Volume"
                    ),
                }
            )

        ohlc_df = pd.DataFrame(
            rows
        )

        if ohlc_df.empty:

            logger.warning(
                "No OHLC data downloaded."
            )

            return report_df

        return report_df.merge(
            ohlc_df,
            on="Symbol",
            how="left",
        )


###############################################################################
# CACHE
###############################################################################

    def cache_file(
        self,
        symbol: str,
        period: str,
        interval: str,
    ) -> Path:

        filename = (
            f"{symbol}_{period}_{interval}.parquet"
        )

        return self.cache_dir / filename


    def clear_cache(self) -> None:

        if not self.cache_dir.exists():
            return

        for file in self.cache_dir.glob("*.parquet"):

            try:

                file.unlink()

            except Exception:

                logger.exception(
                    "Unable to remove cache %s",
                    file,
                )


###############################################################################
# HEALTH
###############################################################################

    def health_check(self) -> dict:

        return {

            "component": "OHLCData",

            "status": "ready",

            "provider": "YahooFinance",

            "cache_enabled": self.cache_enabled,

            "timestamp": ist_now(),

        }


###############################################################################
# INTERNAL API (implemented in Part 2)
###############################################################################

    def _load_history(
        self,
        request: OHLCRequest,
    ) -> pd.DataFrame:
        """
        Implemented in Part 2.
        """
        raise NotImplementedError


    def _download_history(
        self,
        request: OHLCRequest,
    ) -> pd.DataFrame:
        """
        Implemented in Part 2.
        """
        raise NotImplementedError


    def _normalize_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Implemented in Part 2.
        """
        raise NotImplementedError


    def _read_cache(
        self,
        path: Path,
    ) -> Optional[pd.DataFrame]:
        """
        Implemented in Part 2.
        """
        raise NotImplementedError


    def _write_cache(
        self,
        path: Path,
        df: pd.DataFrame,
    ) -> None:
        """
        Implemented in Part 2.
        """
        raise NotImplementedError

###############################################################################
# INTERNAL IMPLEMENTATION
###############################################################################

    def _load_history(
        self,
        request: OHLCRequest,
    ) -> pd.DataFrame:
        """
        Load OHLC data from cache or provider.
        """

        cache_path = self.cache_file(
            request.symbol,
            request.period,
            request.interval,
        )

        if request.use_cache and cache_path.exists():

            cached = self._read_cache(cache_path)

            if cached is not None and not cached.empty:

                logger.debug(
                    "Loaded %s from cache.",
                    request.symbol,
                )

                return cached

        logger.info(
            "Downloading OHLC : %s",
            request.symbol,
        )

        df = self._download_history(request)

        if request.use_cache:

            self._write_cache(
                cache_path,
                df,
            )

        return df


###############################################################################
# DOWNLOAD
###############################################################################

    def _download_history(
        self,
        request: OHLCRequest,
    ) -> pd.DataFrame:
        """
        Download historical candles from Yahoo Finance.
        """

        try:

            df = self.provider.fetch_history(
                symbol=request.symbol,
                period=request.period,
                interval=request.interval,
            )

        except Exception:

            logger.exception(
                "Yahoo download failed for %s",
                request.symbol,
            )

            raise

        if df is None or df.empty:

            raise RuntimeError(
                f"No OHLC data returned for {request.symbol}"
            )

        return self._normalize_dataframe(df)


###############################################################################
# NORMALIZATION
###############################################################################

    def _normalize_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Convert Yahoo dataframe into project standard.
        """

        df = df.copy()

        if "Date" not in df.columns:

            df = df.reset_index()

        rename = {

            "Date": "date",

            "Datetime": "date",

            "Open": "open",

            "High": "high",

            "Low": "low",

            "Close": "close",

            "Adj Close": "adj_close",

            "Volume": "volume",

        }

        df.rename(
            columns=rename,
            inplace=True,
        )

        required = [

            "date",

            "open",

            "high",

            "low",

            "close",

            "volume",

        ]

        missing = [

            col
            for col in required
            if col not in df.columns
        ]

        if missing:

            raise RuntimeError(
                f"Missing OHLC columns : {missing}"
            )

        numeric = [

            "open",

            "high",

            "low",

            "close",

            "volume",

        ]

        for column in numeric:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        if "adj_close" not in df.columns:

            df["adj_close"] = df["close"]

        df["symbol"] = ""

        df["retrieved_at"] = ist_now()

        df.dropna(
            subset=["close"],
            inplace=True,
        )

        df.sort_values(
            "date",
            inplace=True,
        )

        df.reset_index(
            drop=True,
            inplace=True,
        )

        return df


###############################################################################
# CACHE
###############################################################################

    def _read_cache(
        self,
        path: Path,
    ) -> Optional[pd.DataFrame]:
        """
        Read cached parquet.
        """

        try:

            return pd.read_parquet(path)

        except Exception:

            logger.warning(
                "Ignoring corrupted cache %s",
                path.name,
            )

            return None


    def _write_cache(
        self,
        path: Path,
        df: pd.DataFrame,
    ) -> None:
        """
        Persist cache.
        """

        try:

            df.to_parquet(
                path,
                index=False,
            )

        except Exception:

            logger.exception(
                "Unable to write cache %s",
                path.name,
            )


###############################################################################
# OPTIONAL UTILITIES
###############################################################################

    def latest_close(
        self,
        symbol: str,
    ) -> float:
        """
        Latest closing price.
        """

        df = self.fetch(symbol)

        return float(df.iloc[-1]["close"])


    def latest_row(
        self,
        symbol: str,
    ) -> pd.Series:
        """
        Latest OHLC row.
        """

        df = self.fetch(symbol)

        return df.iloc[-1]


    def latest_volume(
        self,
        symbol: str,
    ) -> int:
        """
        Latest traded volume.
        """

        df = self.fetch(symbol)

        return int(df.iloc[-1]["volume"])


###############################################################################
# CLOSE
###############################################################################

    def close(self) -> None:
        """
        Shutdown service.
        """

        logger.info(
            "OHLCData closed."
        )