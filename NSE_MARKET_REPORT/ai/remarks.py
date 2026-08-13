"""
ai/remarks.py

AI-powered Final Remarks Generator for NSE Market Report.

Responsibilities
----------------
- Initialize configured AI provider.
- Build prompts.
- Call Gemini.
- Validate and parse structured JSON responses.
- Generate single and batch remarks.
- Apply shared Gemini rate limiting.
- Merge remarks into the market report.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

import json
import time

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd

import google.generativeai as genai

from ai.prompts import (
    build_remarks_prompt,
)

from ai.rate_limiter import (
    GEMINI_RATE_LIMITER,
)

from config.config import (
    AI_PROVIDER,
    DEFAULT_BACKOFF,
    DEFAULT_RETRIES,
    GEMINI_API_KEY,
    MAX_TOKENS,
    MAX_WORKERS,
    MODEL_NAME,
    OPENAI_API_KEY,
    REQUEST_DELAY,
    TEMPERATURE,
)

from config.logging_config import logger

from config.timezone import (
    now_ist,
)


###############################################################################
# OUTPUT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Symbol",

    "Sentiment",

    "Strength Score",

    "Risk",

    "Final Remarks",

]


###############################################################################
# EXCEPTIONS
###############################################################################


class AIRemarkError(Exception):
    """
    Base AI remarks exception.
    """


class AIConnectionError(AIRemarkError):
    """
    AI connection failure.
    """


class AIResponseError(AIRemarkError):
    """
    Invalid AI response.
    """


###############################################################################
# AI REMARKS ENGINE
###############################################################################


class AIRemarks:
    """
    AI Remarks Generator.

    Public API
    ----------
    generate()
    generate_many()
    merge()
    statistics()
    health_check()
    refresh()
    test_connection()
    info()
    reset()
    close()
    """

    ###########################################################################
    # INITIALIZATION
    ###########################################################################

    def __init__(
        self,
    ) -> None:

        logger.info(
            "[REMARKS] Initializing AI Remarks Engine..."
        )

        self.timestamp = now_ist()

        self.provider = (
            str(
                AI_PROVIDER or ""
            )
            .strip()
            .lower()
        )

        self.model = (
            self._initialize_model()
        )

        logger.info(
            "[REMARKS] %s initialized.",
            self.provider,
        )

    ###########################################################################
    # MODEL INITIALIZATION
    ###########################################################################

    def _initialize_model(
        self,
    ) -> Any:
        """
        Initialize the configured AI provider.
        """

        if self.provider == "gemini":

            if not GEMINI_API_KEY:

                logger.warning(
                    "GEMINI_API_KEY not configured."
                )

                logger.warning(
                    "AI remarks will be disabled."
                )

                return None

            try:

                genai.configure(
                    api_key=GEMINI_API_KEY,
                )

                generation_config = {
                    "temperature": TEMPERATURE,
                    "max_output_tokens": MAX_TOKENS,
                }

                model = (
                    genai.GenerativeModel(
                        model_name=MODEL_NAME,
                        generation_config=(
                            generation_config
                        ),
                    )
                )

                logger.info(
                    "[REMARKS] Gemini model initialized."
                )

                return model

            except Exception as ex:

                logger.exception(
                    "[REMARKS] "
                    "Gemini initialization failed: %s",
                    ex,
                )

                logger.warning(
                    "[REMARKS] "
                    "AI remarks will be disabled."
                )

                return None

        if self.provider == "openai":

            if not OPENAI_API_KEY:

                logger.warning(
                    "OPENAI_API_KEY not configured."
                )

            raise NotImplementedError(
                "OpenAI support will be added later."
            )

        raise AIRemarkError(
            f"Unsupported AI provider: "
            f"{AI_PROVIDER}"
        )

    ###########################################################################
    # PROVIDER
    ###########################################################################

    @property
    def provider_name(
        self,
    ) -> str:
        """
        Return active provider.
        """

        return self.provider

    ###########################################################################
    # HEALTH CHECK
    ###########################################################################

    def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Return AI engine health information.
        """

        return {

            "provider":
                self.provider,

            "model":
                MODEL_NAME,

            "timestamp":
                self.timestamp,

            "status": (
                "ready"
                if self.model is not None
                else "disabled"
            ),

        }

    ###########################################################################
    # REFRESH
    ###########################################################################

    def refresh(
        self,
    ) -> None:
        """
        Reinitialize AI model.
        """

        self.timestamp = now_ist()

        self.model = (
            self._initialize_model()
        )

        logger.info(
            "[REMARKS] AI model refreshed (%s).",
            (
                "enabled"
                if self.model is not None
                else "disabled"
            ),
        )

    ###########################################################################
    # PROMPT BUILDER
    ###########################################################################

    def _build_prompt(
        self,
        stock: Dict[str, Any],
    ) -> str:
        """
        Build AI remarks prompt.
        """

        return build_remarks_prompt(
            stock
        )

    ###########################################################################
    # RESPONSE VALIDATION
    ###########################################################################

    @staticmethod
    def _validate_response(
        text: Optional[str],
    ) -> str:
        """
        Validate raw AI response.
        """

        if text is None:

            raise AIResponseError(
                "Empty AI response."
            )

        text = str(
            text
        ).strip()

        if not text:

            raise AIResponseError(
                "Blank AI response."
            )

        return text

    ###########################################################################
    # CLEAN RESPONSE
    ###########################################################################

    @staticmethod
    def _clean_response(
        text: str,
    ) -> str:
        """
        Remove common markdown wrappers around JSON.
        """

        text = text.strip()

        if text.startswith(
            "```json"
        ):

            text = text[
                len("```json"):
            ]

        elif text.startswith(
            "```"
        ):

            text = text[
                len("```"):
            ]

        if text.endswith(
            "```"
        ):

            text = text[
                :-len("```")
            ]

        return text.strip()

    ###########################################################################
    # GEMINI REQUEST
    ###########################################################################

    def _call_gemini(
        self,
        prompt: str,
    ) -> str:
        """
        Call Gemini using the shared rate limiter.
        """

        if self.model is None:

            raise AIConnectionError(
                "Gemini model is not initialized."
            )

        last_exception: Optional[
            Exception
        ] = None

        for attempt in range(
            1,
            DEFAULT_RETRIES + 1,
        ):

            try:

                ################################################################
                # GLOBAL RATE LIMIT
                ################################################################

                GEMINI_RATE_LIMITER.wait()

                ################################################################
                # REQUEST
                ################################################################

                response = (
                    self.model.generate_content(
                        prompt
                    )
                )

                if not hasattr(
                    response,
                    "text",
                ):

                    raise AIResponseError(
                        "Invalid Gemini response."
                    )

                text = (
                    self._validate_response(
                        response.text
                    )
                )

                return (
                    self._clean_response(
                        text
                    )
                )

            except Exception as ex:

                last_exception = ex

                logger.warning(
                    "[REMARKS] "
                    "Attempt %d/%d failed: %s",
                    attempt,
                    DEFAULT_RETRIES,
                    ex,
                )

                if (
                    attempt
                    < DEFAULT_RETRIES
                ):

                    time.sleep(
                        DEFAULT_BACKOFF
                        ** attempt
                    )

        raise AIConnectionError(
            "Gemini request failed: "
            f"{last_exception}"
        )

    ###########################################################################
    # PROVIDER ROUTER
    ###########################################################################

    def _call_model(
        self,
        prompt: str,
    ) -> str:
        """
        Call configured AI provider.
        """

        if self.provider == "gemini":

            if self.model is None:

                return (
                    "AI remarks unavailable "
                    "(Gemini API key not configured)."
                )

            return self._call_gemini(
                prompt
            )

        raise AIRemarkError(
            f"Unsupported AI provider: "
            f"{self.provider}"
        )

    ###########################################################################
    # JSON PARSER
    ###########################################################################

    @staticmethod
    def _parse_response(
        response: str,
    ) -> Dict[str, Any]:
        """
        Parse and validate AI JSON response.
        """

        response = str(
            response or ""
        ).strip()

        if not response:

            raise AIResponseError(
                "AI returned empty JSON response."
            )

        try:

            result = json.loads(
                response
            )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as ex:

            raise AIResponseError(
                "Invalid JSON returned by AI: "
                f"{ex}"
            ) from ex

        if not isinstance(
            result,
            dict,
        ):

            raise AIResponseError(
                "AI JSON response must be an object."
            )

        required_fields = [

            "sentiment",

            "strength_score",

            "risk",

            "final_remark",

        ]

        for field in required_fields:

            if field not in result:

                raise AIResponseError(
                    f"Missing field: {field}"
                )

        return result

    ###########################################################################
    # SINGLE STOCK GENERATION
    ###########################################################################

    def generate(
        self,
        stock: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate AI remarks for one stock.
        """

        symbol = str(
            stock.get(
                "Symbol",
                "UNKNOWN",
            )
        ).strip()

        logger.info(
            "[REMARKS] Generating remarks for %s",
            symbol,
        )

        try:

            prompt = (
                self._build_prompt(
                    stock
                )
            )

            response = (
                self._call_model(
                    prompt
                )
            )

            result = (
                self._parse_response(
                    response
                )
            )

            return {

                "Symbol":
                    symbol,

                "Sentiment":
                    result.get(
                        "sentiment"
                    ),

                "Strength Score":
                    result.get(
                        "strength_score"
                    ),

                "Risk":
                    result.get(
                        "risk"
                    ),

                "Final Remarks":
                    result.get(
                        "final_remark"
                    ),

            }

        except Exception as ex:

            logger.exception(
                "[REMARKS] Failed for %s : %s",
                symbol,
                ex,
            )

            return {

                "Symbol":
                    symbol,

                "Sentiment":
                    "Unknown",

                "Strength Score":
                    None,

                "Risk":
                    "Unknown",

                "Final Remarks":
                    "Unable to generate AI remarks.",

            }

    ###########################################################################
    # WORKER
    ###########################################################################

    def _generate_worker(
        self,
        stock: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Worker used by ThreadPoolExecutor.
        """

        return self.generate(
            stock
        )

###############################################################################
# MULTIPLE STOCKS
###############################################################################

    def generate_many(
        self,
        stocks: List[
            Dict[str, Any]
        ],
    ) -> pd.DataFrame:
        """
        Generate AI remarks for multiple stocks.
        """

        if not stocks:

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

        logger.info(
            "[REMARKS] Processing %d stocks.",
            len(stocks),
        )

        #######################################################################
        # AI UNAVAILABLE
        #######################################################################

        if self.model is None:

            logger.warning(
                "[REMARKS] AI model unavailable. "
                "Using fallback remarks for %d stocks.",
                len(stocks),
            )

            rows = [

                {
                    "Symbol":
                        stock.get(
                            "Symbol"
                        ),

                    "Sentiment":
                        "Unknown",

                    "Strength Score":
                        None,

                    "Risk":
                        "Unknown",

                    "Final Remarks":
                        "AI remarks unavailable.",

                }

                for stock in stocks

            ]

            return pd.DataFrame(
                rows,
                columns=OUTPUT_COLUMNS,
            )

        #######################################################################
        # GENERATE
        #######################################################################

        rows: List[
            Dict[str, Any]
        ] = []

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
        ) as executor:

            futures = {

                executor.submit(
                    self._generate_worker,
                    stock,
                ):
                    stock.get(
                        "Symbol"
                    )

                for stock in stocks

            }

            for future in as_completed(
                futures
            ):

                symbol = futures[
                    future
                ]

                try:

                    rows.append(
                        future.result()
                    )

                except Exception as ex:

                    logger.exception(
                        "[REMARKS] "
                        "Failed for %s: %s",
                        symbol,
                        ex,
                    )

                    rows.append(
                        {

                            "Symbol":
                                symbol,

                            "Sentiment":
                                "Unknown",

                            "Strength Score":
                                None,

                            "Risk":
                                "Unknown",

                            "Final Remarks":
                                "Unable to generate AI remarks.",

                        }
                    )

        #######################################################################
        # RESULT
        #######################################################################

        df = pd.DataFrame(
            rows,
            columns=OUTPUT_COLUMNS,
        )

        if not df.empty:

            df.drop_duplicates(
                subset=["Symbol"],
                keep="first",
                inplace=True,
            )

            df.sort_values(
                by="Symbol",
                inplace=True,
            )

            df.reset_index(
                drop=True,
                inplace=True,
            )

        logger.info(
            "[REMARKS] Completed for %d stocks.",
            len(df),
        )

        return df


###############################################################################
# MERGE INTO REPORT
###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge AI remarks into report dataframe.
        """

        if report_df.empty:

            logger.warning(
                "[REMARKS] Empty report dataframe."
            )

            return report_df

        stocks = (
            report_df.to_dict(
                orient="records"
            )
        )

        remarks_df = (
            self.generate_many(
                stocks
            )
        )

        if remarks_df.empty:

            logger.warning(
                "[REMARKS] "
                "No remarks generated."
            )

            return report_df

        #######################################################################
        # REMOVE EXISTING REMARK COLUMNS
        #######################################################################

        existing_columns = [
            column
            for column in OUTPUT_COLUMNS
            if column in report_df.columns
            and column != "Symbol"
        ]

        if existing_columns:

            report_df = (
                report_df.drop(
                    columns=existing_columns
                )
            )

        #######################################################################
        # MERGE
        #######################################################################

        merged = report_df.merge(
            remarks_df,
            on="Symbol",
            how="left",
        )

        logger.info(
            "[REMARKS] "
            "Report merged successfully."
        )

        return merged


###############################################################################
# STATISTICS
###############################################################################

    def statistics(
        self,
        remarks_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Return AI remarks generation statistics.
        """

        if remarks_df is None:

            return {

                "total": 0,

                "generated": 0,

                "failed": 0,

                "provider":
                    self.provider,

                "model":
                    MODEL_NAME,

                "status":
                    "unavailable",

            }

        if remarks_df.empty:

            return {

                "total": 0,

                "generated": 0,

                "failed": 0,

                "provider":
                    self.provider,

                "model":
                    MODEL_NAME,

                "status":
                    "empty",

            }

        if (
            "Final Remarks"
            not in remarks_df.columns
        ):

            return {

                "total":
                    len(remarks_df),

                "generated":
                    0,

                "failed":
                    0,

                "provider":
                    self.provider,

                "model":
                    MODEL_NAME,

                "status":
                    "invalid",

            }

        remarks_series = (
            remarks_df[
                "Final Remarks"
            ]
            .fillna("")
            .astype(str)
        )

        failed = (
            remarks_series
            .str.contains(
                "Unable to generate AI remarks|"
                "AI remarks unavailable",
                case=False,
                regex=True,
                na=False,
            )
            .sum()
        )

        return {

            "total":
                len(remarks_df),

            "generated":
                len(remarks_df) - failed,

            "failed":
                int(failed),

            "provider":
                self.provider,

            "model":
                MODEL_NAME,

            "status": (
                "ready"
                if self.model is not None
                else "disabled"
            ),

        }


###############################################################################
# CONNECTION TEST
###############################################################################

    def test_connection(
        self,
    ) -> bool:
        """
        Test AI connectivity.
        """

        logger.info(
            "[REMARKS] Testing AI connection..."
        )

        if self.model is None:

            logger.warning(
                "[REMARKS] "
                "Connection test skipped."
            )

            return False

        try:

            response = (
                self._call_model(
                    "Reply with exactly one word: OK"
                )
            )

            return (
                bool(response)
                and response.strip()
                .upper()
                == "OK"
            )

        except Exception as ex:

            logger.exception(
                "[REMARKS] "
                "Connection test failed: %s",
                ex,
            )

            return False


###############################################################################
# SERVICE INFORMATION
###############################################################################

    def info(
        self,
    ) -> Dict[str, Any]:
        """
        Return AI remarks service information.
        """

        return {

            "provider":
                self.provider,

            "model":
                MODEL_NAME,

            "temperature":
                TEMPERATURE,

            "max_tokens":
                MAX_TOKENS,

            "timestamp":
                self.timestamp,

            "status": (
                "ready"
                if self.model is not None
                else "disabled"
            ),

        }


###############################################################################
# RESET
###############################################################################

    def reset(
        self,
    ) -> None:
        """
        Reset AI engine.
        """

        logger.info(
            "[REMARKS] Resetting AI engine..."
        )

        self.refresh()


###############################################################################
# CLOSE
###############################################################################

    def close(
        self,
    ) -> None:
        """
        Cleanup AI resources.
        """

        logger.info(
            "[REMARKS] Service closed."
        )
