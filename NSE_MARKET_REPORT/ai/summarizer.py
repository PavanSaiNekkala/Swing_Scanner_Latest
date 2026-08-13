"""
==============================================================================
File        : ai/summarizer.py
Project     : NSE Market Report

Description
-----------
AI Summarization Engine.

Responsibilities
----------------
✓ Initialize AI provider
✓ Build prompts
✓ Call Gemini/OpenAI
✓ Validate responses
✓ Batch summarization
✓ Error handling
✓ Logging

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

import time

from datetime import datetime
from typing import Any
from typing import Any, Optional
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
)

from config.config import MAX_WORKERS

from config.logging_config import logger

from ai.prompts import (
    build_summary_prompt,
)

###############################################################################
# EXCEPTIONS
###############################################################################


class AIError(Exception):
    """Base AI exception."""


class AIConnectionError(AIError):
    """Raised when AI provider cannot be reached."""


class AIResponseError(AIError):
    """Raised when AI response is invalid."""


###############################################################################
# OUTPUT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Symbol",

    "AI Summary",

]

###############################################################################
# AI SUMMARIZER
###############################################################################


class AISummarizer:
    """
    AI Market Summarizer.

    Public Methods
    --------------
    summarize()

    summarize_many()

    health_check()
    """

    ###########################################################################

    def __init__(self):

        logger.info(

            "[AI] Initializing summarizer..."

        )

        self.timestamp = datetime.now()

        self.provider = AI_PROVIDER.lower()

        self.model = self._initialize_model()

        logger.info(

            "[AI] %s initialized.",

            self.provider,

        )

    ###########################################################################

    def _initialize_model(self):
        """
        Initialize the configured AI provider.

        Returns
        -------
        GenerativeModel | None
            Configured AI model, or None if AI is disabled.
        """

        if self.provider == "gemini":

            if not GEMINI_API_KEY:

                logger.warning(
                    "GEMINI_API_KEY not configured."
                )

                logger.warning(
                    "AI summarization will be disabled."
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

                model = genai.GenerativeModel(
                    model_name=MODEL_NAME,
                    generation_config=generation_config,
                )

                logger.info(
                    "Gemini model initialized successfully."
                )

                return model

            except Exception:

                logger.exception(
                    "Failed to initialize Gemini model."
                )

                logger.warning(
                    "AI summarization will be disabled."
                )

                return None

        elif self.provider == "openai":

            logger.warning(
                "OpenAI provider is not implemented yet."
            )

            return None

        logger.warning(
            "Unsupported AI provider '%s'. AI disabled.",
            self.provider,
        )

        return None

    ###########################################################################

    @property
    def provider_name(self) -> str:
        """
        Active AI provider.
        """

        return self.provider

    ###########################################################################

    def health_check(self) -> dict[str, Any]:
        """
        Return AI service information.
        """

        return {

            "provider": self.provider,

            "model": MODEL_NAME,

            "timestamp": self.timestamp,

            "status": "ready" if self.model else "disabled",

        }

    ###########################################################################

    def refresh(self) -> None:
        """
        Reinitialize AI model.
        """

        self.timestamp = datetime.now()

        self.model = self._initialize_model()

        logger.info(

            "[AI] Model refreshed (%s).",
            "enabled" if self.model else "disabled",

        )

###############################################################################
# PROMPT LAYER
###############################################################################

    def _build_prompt(
        self,
        stock: dict[str, Any],
    ) -> str:
        """
        Build AI prompt for a stock.
        """

        return build_summary_prompt(stock)

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
                "AI returned an empty response."
            )

        text = text.strip()

        if not text:

            raise AIResponseError(
                "AI returned blank text."
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
        Normalize AI output.
        """

        text = text.replace("\r", "")

        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

###############################################################################
# GEMINI REQUEST
###############################################################################

    def _call_gemini(
        self,
        prompt: str,
    ) -> str:
        """
        Call Gemini model with retry support.
        """

        last_exception = None

        if self.model is None:

            raise AIConnectionError(
                "Gemini model is not initialized."
            )

        for attempt in range(1, DEFAULT_RETRIES + 1):

            try:

                time.sleep(REQUEST_DELAY)

                response = self.model.generate_content(
                    prompt
                )

                if not hasattr(response, "text"):

                    raise AIResponseError(
                        "Gemini returned an invalid response."
                    )

                text = self._validate_response(
                    response.text
                )

                return self._clean_response(
                    text
                )

            except Exception as ex:

                last_exception = ex

                logger.warning(

                    "[AI] Attempt %d/%d failed: %s",

                    attempt,

                    DEFAULT_RETRIES,

                    ex,

                )

                if attempt < DEFAULT_RETRIES:

                    time.sleep(

                        DEFAULT_BACKOFF ** attempt

                    )

        raise AIConnectionError(

            f"Gemini request failed: {last_exception}"

        )

###############################################################################
# PROVIDER ROUTER
###############################################################################

    def _call_model(
        self,
        prompt: str,
    ) -> str:
        """
        Dispatch request to configured AI provider.
        """

        if self.provider == "gemini":

            if self.model is None:

                return (
                    "AI summary unavailable "
                    "(Gemini API key not configured)."
                )

            return self._call_gemini(prompt)

        raise AIError(

            f"Unsupported provider: {self.provider}"

        )

###############################################################################
# SINGLE STOCK SUMMARIZATION
###############################################################################

    def summarize(
        self,
        stock: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate AI summary for a single stock.

        Parameters
        ----------
        stock : dict

        Returns
        -------
        dict
        """

        symbol = stock.get("Symbol", "UNKNOWN")

        logger.info(

            "[AI] Summarizing %s",

            symbol,

        )

        try:

            prompt = self._build_prompt(

                stock,

            )

            summary = self._call_model(

                prompt,

            )

            return {

                "Symbol": symbol,

                "AI Summary": summary,

            }

        except Exception as ex:

            logger.exception(

                "[AI] Failed for %s : %s",

                symbol,

                ex,

            )

            return {

                "Symbol": symbol,

                "AI Summary": "Summary unavailable.",

            }

###############################################################################
# WORKER
###############################################################################

    def _summarize_worker(
        self,
        stock: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Thread worker.
        """

        return self.summarize(

            stock,

        )

###############################################################################
# MULTIPLE STOCKS
###############################################################################

    def summarize_many(
        self,
        stocks: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Generate summaries for multiple stocks.

        Parameters
        ----------
        stocks : list

        Returns
        -------
        DataFrame
        """

        if not stocks:

            return pd.DataFrame(

                columns=OUTPUT_COLUMNS,

            )

        logger.info(

            "[AI] Summarizing %d stocks.",

            len(stocks),

        )

        rows: list[dict[str, Any]] = []

        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import as_completed

        with ThreadPoolExecutor(

            max_workers=MAX_WORKERS,

        ) as executor:

            futures = {

                executor.submit(

                    self._summarize_worker,

                    stock,

                ): stock.get("Symbol")

                for stock in stocks

            }

            for future in as_completed(

                futures,

            ):

                symbol = futures[future]

                try:

                    result = future.result()

                    rows.append(result)

                except Exception as ex:

                    logger.exception(

                        "[AI] %s : %s",

                        symbol,

                        ex,

                    )

                    rows.append(

                        {

                            "Symbol": symbol,

                            "AI Summary": "Summary unavailable.",

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

            "[AI] Generated %d summaries.",

            len(df),

        )

        return df

###############################################################################
# MERGE WITH REPORT
###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge AI summaries into report dataframe.
        """

        if report_df.empty:

            logger.warning(

                "[AI] Empty report dataframe."

            )

            return report_df

        stocks = report_df.to_dict(

            orient="records",

        )

        summary_df = self.summarize_many(

            stocks,

        )

        if summary_df.empty:

            logger.warning(

                "[AI] No summaries generated."

            )

            return report_df

        if "AI Summary" in report_df.columns:

            report_df = report_df.drop(
                columns=["AI Summary"]
            )

        merged = report_df.merge(

            summary_df,

            on="Symbol",

            how="left",

        )

        logger.info(

            "[AI] Report merged."

        )

        return merged

    
###############################################################################
# STATISTICS
###############################################################################

    def statistics(
        self,
        summary_df: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Return summary generation statistics.

        Parameters
        ----------
        summary_df : DataFrame

        Returns
        -------
        dict
        """

        if summary_df is None:

            return {
                "total": 0,
                "generated": 0,
                "failed": 0,
                "provider": self.provider,
                "model": MODEL_NAME,
                "status": "unavailable",
            }

        if summary_df.empty:

            return {
                "total": 0,
                "generated": 0,
                "failed": 0,
                "provider": self.provider,
                "model": MODEL_NAME,
                "status": "empty",
            }

        #######################################################################
        # AI SUMMARY COLUMN NOT PRESENT
        #######################################################################

        if "AI Summary" not in summary_df.columns:

            logger.warning(
                "[AI] AI Summary column not present in dataframe. "
                "AI summary statistics unavailable."
            )

            return {
                "total": len(summary_df),
                "generated": 0,
                "failed": 0,
                "provider": self.provider,
                "model": MODEL_NAME,
                "status": (
                    "ready"
                    if self.model is not None
                    else "disabled"
                ),
            }

        #######################################################################
        # CALCULATE STATISTICS
        #######################################################################

        summary_series = (
            summary_df["AI Summary"]
            .fillna("")
            .astype(str)
        )

        failed = (
            summary_series
            .str.contains(
                "unavailable",
                case=False,
                na=False,
            )
            .sum()
        )

        return {
            "total": len(summary_df),
            "generated": len(summary_df) - failed,
            "failed": failed,
            "provider": self.provider,
            "model": MODEL_NAME,
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
        Verify AI connectivity.
        """

        logger.info(
            "[AI] Testing AI connection..."
        )

        # AI is disabled
        if self.model is None:

            logger.warning(
                "[AI] Connection test skipped: "
                "AI model is not initialized."
            )

            return False

        try:

            response = self._call_model(
                "Reply with exactly one word: OK"
            )

            if not response:

                logger.warning(
                    "[AI] Empty response received."
                )

                return False

            if "OK" in response.upper():

                logger.info(
                    "[AI] Connection successful."
                )

                return True

            logger.warning(
                "[AI] Unexpected response: %s",
                response,
            )

            return False

        except Exception as ex:

            logger.exception(
                "[AI] Connection test failed: %s",
                ex,
            )

            return False

###############################################################################
# SERVICE INFORMATION
###############################################################################

    def info(self) -> dict[str, Any]:
        """
        Return AI service information.
        """

        return {

            "provider": self.provider,

            "model": MODEL_NAME,

            "temperature": TEMPERATURE,

            "max_tokens": MAX_TOKENS,

            "timestamp": self.timestamp,

            "status": "ready" if self.model else "disabled",

        }

###############################################################################
# RESET
###############################################################################

    def reset(self) -> None:
        """
        Reinitialize AI service.
        """

        logger.info(

            "[AI] Resetting service..."

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

            "[AI] Service closed."

        )