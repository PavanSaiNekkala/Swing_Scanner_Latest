from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from nselib.capital_market import (
    equity_list,
    top_gainers_or_losers,
)

from config.config import (
    TOP_GAINERS_COUNT,
    TOP_LOSERS_COUNT,
)

from config.logging_config import logger

NSELIB_GAINERS = "gainers"
NSELIB_LOSERS = "loosers"
NSELIB_ALL_SECURITIES = "allSec"


class NSELibProvider:
    """
    Market data provider using nselib instead of direct NSE HTTP requests.
    """

    def __init__(self):
        self.provider_name = "nselib"
        self.company_master = self._load_company_master()


    def _load_company_master(
        self,
    ) -> Dict[str, str]:
        """
        Load NSE equity master and build:
        Symbol -> Company Name
        """

        try:

            master = equity_list()

            if master is None:
                return {}

            if not isinstance(
                master,
                pd.DataFrame,
            ):
                master = pd.DataFrame(master)

            if master.empty:
                return {}

            symbol_column = next(
                (
                    column
                    for column in [
                        "SYMBOL",
                        "symbol",
                        "Symbol",
                    ]
                    if column in master.columns
                ),
                None,
            )

            company_column = next(
                (
                    column
                    for column in [
                        "NAME OF COMPANY",
                        "NAME_OF_COMPANY",
                        "companyName",
                        "Company",
                    ]
                    if column in master.columns
                ),
                None,
            )

            if not symbol_column or not company_column:
                return {}

            master = master[
                [
                    symbol_column,
                    company_column,
                ]
            ].copy()

            master[symbol_column] = (
                master[symbol_column]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            master[company_column] = (
                master[company_column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            return dict(
                zip(
                    master[symbol_column],
                    master[company_column],
                )
            )

        except Exception as ex:

            logger.exception(
                "Unable to load NSE company master: %s",
                ex,
            )

            return {}

    ###########################################################################
    # NORMALIZATION
    ###########################################################################

    def _normalize(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Convert nselib output into the project's standard market schema.
        """

        if df.empty:
            return pd.DataFrame()

        rename_map = {
            "symbol": "Symbol",
            "series": "Series",
            "ltp": "CMP",
            "open_price": "Open",
            "high_price": "High",
            "low_price": "Low",
            "prev_price": "Previous Close",
            "net_price": "Net Change",
            "perChange": "1 Day Change %",
            "trade_quantity": "Volume",
            "turnover": "Turnover",
            "market_type": "Market",
            "legend": "Index",
            "ca_ex_dt": "Ex-Date",
            "ca_purpose": "Corporate Action",
        }

        df = df.rename(
            columns=rename_map
        )

        #######################################################################
        # CLOSE
        #######################################################################

        if "CMP" in df.columns:

            df["Close"] = pd.to_numeric(
                df["CMP"],
                errors="coerce",
            )

        #######################################################################
        # NUMERIC NORMALIZATION
        #######################################################################

        numeric_columns = [
            "CMP",
            "Open",
            "High",
            "Low",
            "Previous Close",
            "Close",
            "Net Change",
            "1 Day Change %",
            "Volume",
            "Turnover",
        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        #######################################################################
        # REQUIRED PROJECT COLUMNS
        #######################################################################

        if "Company" not in df.columns:

            df["Company"] = (
                df["Symbol"]
                .astype(str)
                .str.upper()
                .map(self.company_master)
                .fillna("")
            )

        else:

            df["Company"] = (
                df["Company"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        if "Category" not in df.columns:

            df["Category"] = ""

        return df

    ###############################################################################
    # TOP NSE-WIDE GAINERS
    ###############################################################################

    def fetch_top_gainers(
        self,
    ) -> pd.DataFrame:
        """
        Return Top NSE-Wide Gainers.

        Uses nselib's `allSec` section to identify
        NSE-wide gainers rather than an index-specific section.
        """

        try:

            data = top_gainers_or_losers(
                NSELIB_GAINERS
            )

        except Exception as ex:

            logger.exception(
                "[NSELIB] Failed to fetch NSE-wide gainers: %s",
                ex,
            )

            return pd.DataFrame()

        if data is None:

            logger.warning(
                "[NSELIB] Gainers provider returned None."
            )

            return pd.DataFrame()

        if not isinstance(
            data,
            pd.DataFrame,
        ):

            try:

                data = pd.DataFrame(
                    data
                )

            except Exception as ex:

                logger.exception(
                    "[NSELIB] Unable to convert "
                    "gainers response: %s",
                    ex,
                )

                return pd.DataFrame()

        if data.empty:

            logger.warning(
                "[NSELIB] Gainers dataframe is empty."
            )

            return pd.DataFrame()

        #######################################################################
        # FILTER NSE-WIDE ALL-SECURITIES SECTION
        #######################################################################

        if "legend" not in data.columns:

            logger.error(
                "[NSELIB] Gainers response does not "
                "contain 'legend' column."
            )

            return pd.DataFrame()

        data["legend"] = (
            data["legend"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        data = data.loc[
            data["legend"].eq(
                NSELIB_ALL_SECURITIES.lower()
            )
        ].copy()

        if data.empty:

            logger.warning(
                "[NSELIB] NSE-wide gainers section "
                "'allSec' returned no rows."
            )

            return pd.DataFrame()

        #######################################################################
        # NUMERIC CHANGE
        #######################################################################

        data["perChange"] = pd.to_numeric(
            data["perChange"],
            errors="coerce",
        )

        data = data.dropna(
            subset=["perChange"]
        )

        #######################################################################
        # SORT NSE-WIDE GAINERS
        #######################################################################

        data.sort_values(
            by=[
                "perChange",
                "symbol",
            ],
            ascending=[
                False,
                True,
            ],
            inplace=True,
            kind="stable",
        )

        #######################################################################
        # REMOVE DUPLICATE SYMBOLS
        #######################################################################

        data.drop_duplicates(
            subset=["symbol"],
            keep="first",
            inplace=True,
        )

        #######################################################################
        # TOP N
        #######################################################################

        data = data.head(
            TOP_GAINERS_COUNT
        ).copy()

        data = self._normalize(
            data
        )

        if data.empty:

            logger.warning(
                "[NSELIB] Normalized NSE-wide "
                "gainers dataframe is empty."
            )

            return pd.DataFrame()

        data["Category"] = "Gainer"

        logger.info(
            "[NSELIB] NSE-wide gainers selected=%d | "
            "MaxChange=%.2f%% | MinChange=%.2f%%",
            len(data),
            data["1 Day Change %"].max(),
            data["1 Day Change %"].min(),
        )

        return data

    ###############################################################################
    # TOP NSE-WIDE LOSERS
    ###############################################################################

    def fetch_top_losers(
        self,
    ) -> pd.DataFrame:
        """
        Return Top NSE-Wide Losers.

        Uses nselib's `allSec` section.
        """

        try:

            data = top_gainers_or_losers(
                NSELIB_LOSERS
            )

        except Exception as ex:

            logger.exception(
                "[NSELIB] Failed to fetch NSE-wide losers: %s",
                ex,
            )

            return pd.DataFrame()

        if data is None:

            logger.warning(
                "[NSELIB] Losers provider returned None."
            )

            return pd.DataFrame()

        if not isinstance(
            data,
            pd.DataFrame,
        ):

            try:

                data = pd.DataFrame(
                    data
                )

            except Exception as ex:

                logger.exception(
                    "[NSELIB] Unable to convert "
                    "losers response: %s",
                    ex,
                )

                return pd.DataFrame()

        if data.empty:

            logger.warning(
                "[NSELIB] Losers dataframe is empty."
            )

            return pd.DataFrame()

        #######################################################################
        # FILTER NSE-WIDE ALL-SECURITIES SECTION
        #######################################################################

        if "legend" not in data.columns:

            logger.error(
                "[NSELIB] Losers response does not "
                "contain 'legend' column."
            )

            return pd.DataFrame()

        data["legend"] = (
            data["legend"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        data = data.loc[
            data["legend"].eq(
                NSELIB_ALL_SECURITIES.lower()
            )
        ].copy()

        if data.empty:

            logger.warning(
                "[NSELIB] NSE-wide losers section "
                "'allSec' returned no rows."
            )

            return pd.DataFrame()

        #######################################################################
        # NUMERIC CHANGE
        #######################################################################

        data["perChange"] = pd.to_numeric(
            data["perChange"],
            errors="coerce",
        )

        data = data.dropna(
            subset=["perChange"]
        )

        #######################################################################
        # SORT NSE-WIDE LOSERS
        #######################################################################

        data.sort_values(
            by=[
                "perChange",
                "symbol",
            ],
            ascending=[
                True,
                True,
            ],
            inplace=True,
            kind="stable",
        )

        #######################################################################
        # REMOVE DUPLICATE SYMBOLS
        #######################################################################

        data.drop_duplicates(
            subset=["symbol"],
            keep="first",
            inplace=True,
        )

        #######################################################################
        # TOP N
        #######################################################################

        data = data.head(
            TOP_LOSERS_COUNT
        ).copy()

        data = self._normalize(
            data
        )

        if data.empty:

            logger.warning(
                "[NSELIB] Normalized NSE-wide "
                "losers dataframe is empty."
            )

            return pd.DataFrame()

        data["Category"] = "Loser"

        logger.info(
            "[NSELIB] NSE-wide losers selected=%d",
            len(data),
        )

        return data

    ###########################################################################
    # MARKET REPORT
    ###########################################################################

    def fetch_market_report(
        self,
    ) -> pd.DataFrame:
        """
        Combine gainers and losers into one DataFrame.
        """

        gainers = self.fetch_top_gainers()

        losers = self.fetch_top_losers()

        report = pd.concat(
            [
                gainers,
                losers,
            ],
            ignore_index=True,
        )

        if report.empty:
            return pd.DataFrame()

        before_dedup = len(
            report
        )

        report.drop_duplicates(
            subset=["Symbol"],
            keep="first",
            inplace=True,
        )

        duplicates_removed = (
            before_dedup
            - len(report)
        )

        if duplicates_removed:

            logger.warning(
                "[NSELIB] Duplicate symbols removed "
                "from combined market report=%d",
                duplicates_removed,
            )
            
        report.reset_index(
            drop=True,
            inplace=True,
        )

        return report

    ###########################################################################
    # QUOTES
    ###########################################################################

    def fetch_quotes(self):
        """
        Placeholder for quote API.
        """

        raise NotImplementedError(
            "Quote retrieval is not implemented for NSELibProvider."
        )

    ###########################################################################
    # OHLC
    ###########################################################################

    def fetch_ohlc(self):
        """
        Placeholder for OHLC API.
        """

        raise NotImplementedError(
            "OHLC retrieval is not implemented for NSELibProvider."
        )

    ###########################################################################
    # HEALTH
    ###########################################################################

    def health(
        self,
    ) -> Dict[str, Any]:
        """
        Provider health information.
        """

        return {
            "provider": self.provider_name,
            "status": "ready",
        }