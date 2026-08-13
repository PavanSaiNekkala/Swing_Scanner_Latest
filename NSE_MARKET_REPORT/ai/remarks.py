"""
==============================================================================
File        : ai/remarks.py
Project     : NSE Market Report

Description
-----------
AI-powered Final Remarks Generator.

This module generates concise professional remarks for each NSE stock
based on:

    • OHLC Data
    • Daily Change
    • Volume
    • News Headlines
    • AI Summary

Output is suitable for Excel reports.

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

import time

from datetime import datetime

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd

import google.generativeai as genai

from config.config import (

    AI_PROVIDER,

    GEMINI_API_KEY,

    OPENAI_API_KEY,

    MODEL_NAME,

    TEMPERATURE,

    MAX_TOKENS,

    DEFAULT_RETRIES,

    DEFAULT_BACKOFF,

    REQUEST_DELAY,

    MAX_WORKERS,

)
from ai.rate_limiter import (
    GEMINI_RATE_LIMITER,
)

from config.logging_config import logger

from ai.prompts import build_remarks_prompt

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
    Base Remarks exception.
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
    """

    ###########################################################################

    def __init__(self):

        logger.info(

            "[REMARKS] Initializing AI Remarks Engine..."

        )

        self.timestamp = datetime.now()

        self.provider = AI_PROVIDER.lower()

        self.model = self._initialize_model()

        logger.info(

            "[REMARKS] %s initialized.",

            self.provider,

        )

    ###########################################################################

    def _initialize_model(self):
        """
        Initialize configured AI provider.
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

            genai.configure(

                api_key=GEMINI_API_KEY,

            )

            generation_config = {

                "temperature": TEMPERATURE,

                "max_output_tokens": MAX_TOKENS,

            }

            return genai.GenerativeModel(

                model_name=MODEL_NAME,

                generation_config=generation_config,

            )

        elif self.provider == "openai":

            raise NotImplementedError(

                "OpenAI support will be added later."

            )

        raise AIRemarkError(

            f"Unsupported provider: {AI_PROVIDER}"

        )

    ###########################################################################

    @property
    def provider_name(self) -> str:
        """
        Active AI provider.
        """

        return self.provider

    ###########################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        AI engine status.
        """

        return {

            "provider": self.provider,

            "model": MODEL_NAME,

            "timestamp": self.timestamp,

<<<<<<< HEAD
            "status": (
                "ready"
                if self.model is not None
                else "disabled"
            ),
=======
            "status": "ready",
>>>>>>> 263a17d ("13/08/2026")

        }

    ###########################################################################

    def refresh(self) -> None:
        """
        Reinitialize AI model.
        """

        self.timestamp = datetime.now()

        self.model = self._initialize_model()

        logger.info(

            "[REMARKS] AI model refreshed."

        )


###############################################################################
# PROMPT BUILDER
###############################################################################

    def _build_prompt(
        self,
        stock: Dict[str, Any],
    ) -> str:
        """
        Build AI prompt for remarks generation.
        """

        return build_remarks_prompt(stock)

###############################################################################
# RESPONSE VALIDATION
###############################################################################

    @staticmethod
    def _validate_response(
        text: Optional[str],
    ) -> str:
        """
        Validate AI response.
        """

        if text is None:

            raise AIResponseError(
                "Empty AI response."
            )

        text = text.strip()

        if not text:

            raise AIResponseError(
                "Blank AI response."
            )

        return text

###############################################################################
# CLEAN RESPONSE
###############################################################################

    @staticmethod
    def _clean_response(
        text: str,
    ) -> str:
        """
        Clean AI output.
        """

        text = text.replace("```json", "")

        text = text.replace("```", "")

        return text.strip()

###############################################################################
# GEMINI REQUEST
###############################################################################

    def _call_gemini(
        self,
        prompt: str,
    ) -> str:
        """
        Call Gemini API.
        """

        if self.model is None:

<<<<<<< HEAD
            raise AIConnectionError(
                "Gemini API key not configured."
=======
            raise AIRemarkError(
                "Gemini model is not initialized."
>>>>>>> 263a17d ("13/08/2026")
            )
        
        last_exception = None

        for attempt in range(

            1,

            DEFAULT_RETRIES + 1,

        ):

            try:

                time.sleep(

                    REQUEST_DELAY,

                )

                response = self.model.generate_content(

                    prompt,

                )

                if not hasattr(

                    response,

                    "text",

                ):

                    raise AIResponseError(

                        "Invalid Gemini response."

                    )

                text = self._validate_response(

                    response.text,

                )

                return self._clean_response(

                    text,

                )

            except Exception as ex:

                last_exception = ex

                logger.warning(

                    "[REMARKS] Attempt %d/%d failed : %s",

                    attempt,

                    DEFAULT_RETRIES,

                    ex,

                )

                if attempt < DEFAULT_RETRIES:

                    time.sleep(

                        DEFAULT_BACKOFF ** attempt,

                    )

        raise AIConnectionError(

            f"Gemini request failed : {last_exception}"

        )

###############################################################################
# PROVIDER ROUTER
###############################################################################

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

            return self._call_gemini(prompt)

        raise AIRemarkError(

            f"Unsupported AI provider: {self.provider}"

        )

###############################################################################
# JSON PARSER
###############################################################################

    @staticmethod
    def _parse_response(
        response: str,
    ) -> Dict[str, Any]:
        """
        Parse AI JSON response.
        """

        import json

        try:

            result = json.loads(

                response,

            )

        except Exception as ex:

            raise AIResponseError(

                f"Invalid JSON returned by AI: {ex}"

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


###############################################################################
# SINGLE STOCK REMARK GENERATION
###############################################################################

    def generate(
        self,
        stock: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate AI remarks for a single stock.

        Parameters
        ----------
        stock : dict

        Returns
        -------
        dict
        """

        symbol = stock.get("Symbol", "UNKNOWN")

        logger.info(

            "[REMARKS] Generating remarks for %s",

            symbol,

        )

        try:

            prompt = self._build_prompt(

                stock,

            )

            response = self._call_model(

                prompt,

            )

            result = self._parse_response(

                response,

            )

            return {

                "Symbol": symbol,

                "Sentiment": result["sentiment"],

                "Strength Score": result["strength_score"],

                "Risk": result["risk"],

                "Final Remarks": result["final_remark"],

            }

        except Exception as ex:

            logger.exception(

                "[REMARKS] Failed for %s : %s",

                symbol,

                ex,

            )

            return {

                "Symbol": symbol,

                "Sentiment": "Unknown",

                "Strength Score": None,

                "Risk": "Unknown",

                "Final Remarks": "Unable to generate AI remarks.",

            }

###############################################################################
# THREAD WORKER
###############################################################################

    def _generate_worker(
        self,
        stock: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Worker used by ThreadPoolExecutor.
        """

        return self.generate(

            stock,

        )

###############################################################################
# MULTIPLE STOCKS
###############################################################################

    def generate_many(
        self,
        stocks: List[Dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Generate AI remarks for multiple stocks.

<<<<<<< HEAD
        If the AI model is unavailable, return fallback remarks
        immediately without creating unnecessary model requests.
=======
        Parameters
        ----------
        stocks : List[dict]

        Returns
        -------
        DataFrame
>>>>>>> 263a17d ("13/08/2026")
        """

        if not stocks:

            return pd.DataFrame(
<<<<<<< HEAD
                columns=OUTPUT_COLUMNS,
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
                    "Symbol": stock.get("Symbol"),
                    "Sentiment": "Unknown",
                    "Strength Score": None,
                    "Risk": "Unknown",
                    "Final Remarks": "AI remarks unavailable.",
                }
                for stock in stocks
            ]

            return pd.DataFrame(
                rows,
                columns=OUTPUT_COLUMNS,
            )

        #######################################################################
        # PARALLEL AI GENERATION
        #######################################################################

=======

                columns=OUTPUT_COLUMNS,

            )

        logger.info(

            "[REMARKS] Processing %d stocks.",

            len(stocks),

        )

>>>>>>> 263a17d ("13/08/2026")
        rows: List[Dict[str, Any]] = []

        from concurrent.futures import (
            ThreadPoolExecutor,
            as_completed,
        )

        with ThreadPoolExecutor(
<<<<<<< HEAD
            max_workers=MAX_WORKERS,
        ) as executor:

            futures = {
                executor.submit(
                    self._generate_worker,
                    stock,
                ): stock.get("Symbol")
                for stock in stocks
            }

            for future in as_completed(
                futures,
=======

            max_workers=MAX_WORKERS,

        ) as executor:

            futures = {

                executor.submit(

                    self._generate_worker,

                    stock,

                ): stock.get("Symbol")

                for stock in stocks

            }

            for future in as_completed(

                futures,

>>>>>>> 263a17d ("13/08/2026")
            ):

                symbol = futures[future]

                try:

                    rows.append(
<<<<<<< HEAD
                        future.result()
=======

                        future.result()

>>>>>>> 263a17d ("13/08/2026")
                    )

                except Exception as ex:

<<<<<<< HEAD
                    logger.error(
                        "[REMARKS] Failed for %s: %s",
                        symbol,
                        ex,
                    )

                    rows.append(
                        {
                            "Symbol": symbol,
                            "Sentiment": "Unknown",
                            "Strength Score": None,
                            "Risk": "Unknown",
                            "Final Remarks":
                                "Unable to generate AI remarks.",
                        }
                    )

        #######################################################################
        # BUILD RESULT
        #######################################################################

        df = pd.DataFrame(
            rows,
            columns=OUTPUT_COLUMNS,
        )

        if not df.empty:

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
=======
                    logger.exception(

                        "[REMARKS] %s : %s",

                        symbol,

                        ex,

                    )

                    rows.append(

                        {

                            "Symbol": symbol,

                            "Sentiment": "Unknown",

                            "Strength Score": None,

                            "Risk": "Unknown",

                            "Final Remarks":

                                "Unable to generate AI remarks.",

                        }

                    )

        df = pd.DataFrame(

            rows,

            columns=OUTPUT_COLUMNS,

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

>>>>>>> 263a17d ("13/08/2026")
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

        stocks = report_df.to_dict(

            orient="records",

        )

        remarks_df = self.generate_many(

            stocks,

        )

        if remarks_df.empty:

            logger.warning(

                "[REMARKS] No remarks generated."

            )

            return report_df

        merged = report_df.merge(

            remarks_df,

            on="Symbol",

            how="left",

        )

        logger.info(

            "[REMARKS] Report merged successfully."

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

        if remarks_df.empty:

            return {

                "total": 0,

                "generated": 0,

                "failed": 0,

                "provider": self.provider,

                "model": MODEL_NAME,

            }

        failed = (

            remarks_df["Final Remarks"]

            == "Unable to generate AI remarks."

        ).sum()

        return {

            "total": len(remarks_df),

            "generated": len(remarks_df) - failed,

            "failed": failed,

            "provider": self.provider,

            "model": MODEL_NAME,

        }

###############################################################################
# CONNECTION TEST
###############################################################################

    def test_connection(self) -> bool:
        """
        Test AI connectivity.
        """

        logger.info(

            "[REMARKS] Testing AI connection..."

        )

        try:

            response = self._call_model(

                "Reply with exactly one word: OK"

            )

            return response.strip().upper() == "OK"

        except Exception as ex:

            logger.exception(ex)

            return False

###############################################################################
# SERVICE INFO
###############################################################################

    def info(self) -> Dict[str, Any]:
        """
        Return AI engine information.
        """

        return {
<<<<<<< HEAD
            "provider": self.provider,
            "model": MODEL_NAME,
            "timestamp": self.timestamp,
            "status": (
                "ready"
                if self.model is not None
                else "disabled"
            ),
=======

            "provider": self.provider,

            "model": MODEL_NAME,

            "temperature": TEMPERATURE,

            "max_tokens": MAX_TOKENS,

            "timestamp": self.timestamp,

            "status": "ready",

>>>>>>> 263a17d ("13/08/2026")
        }

###############################################################################
# RESET
###############################################################################

    def reset(self) -> None:
        """
        Reset AI model.
        """

        logger.info(

            "[REMARKS] Resetting AI engine..."

        )

        self.refresh()

###############################################################################
# CLOSE
###############################################################################

    def close(self) -> None:
        """
        Cleanup resources.
        """

        logger.info(

            "[REMARKS] Service closed."

        )